
import logging
import asyncio
from typing import List, Dict, Optional, Callable
from swarm_intelligence.core.models import (
    SwarmPlan,
    SwarmStep,
    SwarmResult,
    Decision,
    EvidenceType,
    Alert,
    HumanDecision,
)
from swarm_intelligence.core.swarm import SwarmOrchestrator
from swarm_intelligence.services.confidence_service import ConfidenceService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SwarmController:
    """
    Manages the end-to-end lifecycle of a swarm run, including planning,
    execution, evaluation, re-execution, and decision-making.
    """

    def __init__(
        self,
        orchestrator: SwarmOrchestrator,
        confidence_service: ConfidenceService,
        llm_agent_id: Optional[str] = "llm_agent",
    ):
        self.orchestrator = orchestrator
        self.confidence_service = confidence_service
        self.llm_agent_id = llm_agent_id
        self.human_review_hook: Optional[Callable[[Decision], HumanDecision]] = None

    def register_human_hooks(self, review_hook: Callable[[Decision], HumanDecision]):
        """Registers a single, comprehensive callback for human review."""
        self.human_review_hook = review_hook

    async def aexecute_plan(self, plan: SwarmPlan, alert: Alert) -> (Decision, Dict[str, List[SwarmResult]]):
        """
        Executes a swarm plan, evaluates results, performs retries,
        and formulates a final decision.

        Returns a tuple of (Decision, run_history).
        """
        run_history: Dict[str, List[SwarmResult]] = {step.step_id: [] for step in plan.steps}
        final_results: Dict[str, SwarmResult] = {}

        steps_to_process = list(plan.steps)

        while steps_to_process:
            results = await self.orchestrator.execute_swarm(steps_to_process)

            for res in results:
                step = next((s for s in steps_to_process if s.agent_id == res.agent_id), None)
                if step:
                    run_history[step.step_id].append(res)

            steps_to_process = await self._evaluate_and_get_next_steps(plan.steps, run_history, final_results)

            if steps_to_process:
                logging.info(f"{len(steps_to_process)} steps require retries. Applying policies.")

        # If after all retries, mandatory steps are still not met, escalate
        decision: Decision
        if self._still_requires_action(plan.steps, final_results) and self.llm_agent_id:
            logging.info("Deterministic steps failed or have low confidence. Escalating to LLM.")
            decision = await self._escalate_to_llm(plan, final_results, alert)
        else:
            decision = self._formulate_decision(final_results)

        return self._request_human_review(decision), run_history
    async def _evaluate_and_get_next_steps(
        self,
        all_plan_steps: List[SwarmStep],
        run_history: Dict[str, List[SwarmResult]],
        final_results: Dict[str, SwarmResult],
    ) -> List[SwarmStep]:
        """
        Evaluates results, applies retry policies, and returns the next batch of steps to execute.
        """
        steps_to_retry = []
        max_delay = 0.0

        for step in all_plan_steps:
            if step.step_id in final_results:
                continue

            latest_result = run_history[step.step_id][-1] if run_history[step.step_id] else None
            if not latest_result:
                continue

            is_successful = latest_result.is_successful()
            meets_confidence = latest_result.confidence >= step.min_confidence

            if is_successful and meets_confidence:
                final_results[step.step_id] = latest_result
                logging.info(f"Step {step.step_id} ({step.agent_id}) successful.")
            elif step.mandatory and step.retry_policy:
                attempt = len(run_history[step.step_id])
                error = Exception(latest_result.error) if latest_result.error else None

                if step.retry_policy.should_retry(error, attempt):
                    delay = step.retry_policy.next_delay(attempt)
                    max_delay = max(max_delay, delay)
                    steps_to_retry.append(step)
                    logging.warning(f"Step {step.step_id} failed. Will retry after a delay.")
                else:
                    final_results[step.step_id] = latest_result
                    logging.error(f"Step {step.step_id} failed and exhausted its retry policy.")
            else:
                 final_results[step.step_id] = latest_result
                 logging.error(f"Mandatory step {step.step_id} failed with no retry policy.")

        if max_delay > 0:
            await asyncio.sleep(max_delay)

        return steps_to_retry

    def _still_requires_action(self, all_plan_steps: List[SwarmStep], final_results: Dict[str, SwarmResult]) -> bool:
        """Checks if any mandatory steps have ultimately failed."""
        for step in all_plan_steps:
            if step.mandatory:
                result = final_results.get(step.step_id)
                if not result or not result.is_successful() or result.confidence < step.min_confidence:
                    return True
        return False

    async def _escalate_to_llm(self, plan: SwarmPlan, current_results: Dict[str, SwarmResult], alert: Alert) -> Decision:
        """
        When deterministic methods fail, this method is called to get a hypothesis from an LLM.
        """
        if not self.llm_agent_id:
            return self._formulate_decision(current_results)

        llm_step = SwarmStep(
            agent_id=self.llm_agent_id,
            mandatory=True,
            retryable=False,
            parameters={
                "objective": plan.objective,
                "failed_steps": [res for res in current_results.values() if not res.is_successful()],
                "alert_data": alert.data
            }
        )

        llm_result = (await self.orchestrator.execute_swarm([llm_step]))[0]

        # Tag LLM output as a hypothesis
        llm_result.evidence_type = EvidenceType.HYPOTHESIS

        final_evidence = list(current_results.values()) + [llm_result]

        return Decision(
            summary=f"LLM Hypothesis: {llm_result.output.get('summary', 'N/A')}",
            action_proposed=llm_result.output.get('action', 'manual_review'),
            confidence=llm_result.confidence,
            supporting_evidence=final_evidence
        )

    def _formulate_decision(self, final_results: Dict[str, SwarmResult]) -> Decision:
        """Formulates a final decision based on the collected evidence."""
        successful_results = [res for res in final_results.values() if res.is_successful()]

        if not successful_results:
            return Decision(
                summary="Complete failure. No successful agent executions.",
                action_proposed="manual_review",
                confidence=0.0,
                supporting_evidence=list(final_results.values())
            )

        # Simple aggregation logic: average the confidence
        # In a real system, this could be a more complex voting or weighting mechanism
        avg_confidence = sum(r.confidence for r in successful_results) / len(successful_results)

        # For this example, we'll just summarize the outputs
        summary = "; ".join([str(r.output) for r in successful_results])

        decision = Decision(
            summary=f"Aggregated results: {summary}",
            action_proposed="auto_remediate" if avg_confidence > 0.8 else "log_for_review",
            confidence=avg_confidence,
            supporting_evidence=list(final_results.values())
        )

        return decision

    def _request_human_review(self, decision: Decision) -> Decision:
        """Handles the human-in-the-loop governance step, processing a structured HumanDecision."""
        if self.human_review_hook:
            logging.info("Decision requires human review.")
            human_decision = self.human_review_hook(decision)
            decision.human_decision = human_decision
            logging.info(f"Human reviewed the decision: {human_decision.action.value}")
        else:
            logging.info("No human review hook registered. Proceeding without human governance.")

        return decision
