
import logging
from typing import List, Dict, Optional, Callable
from swarm_intelligence.core.models import (
    SwarmPlan,
    SwarmStep,
    SwarmResult,
    Decision,
    EvidenceType,
    Alert,
)
from swarm_intelligence.core.swarm import SwarmOrchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SwarmController:
    """
    Manages the end-to-end lifecycle of a swarm run, including planning,
    execution, evaluation, re-execution, and decision-making.
    """

    def __init__(
        self,
        orchestrator: SwarmOrchestrator,
        max_retries: int = 2,
        llm_agent_id: Optional[str] = "llm_agent",
    ):
        self.orchestrator = orchestrator
        self.max_retries = max_retries
        self.llm_agent_id = llm_agent_id
        self.human_confirm_hook: Optional[Callable[[Decision], bool]] = None
        self.human_reject_hook: Optional[Callable[[Decision], None]] = None

    def register_human_hooks(
        self,
        confirm_hook: Callable[[Decision], bool],
        reject_hook: Callable[[Decision], None],
    ):
        """Registers callbacks for human-in-the-loop governance."""
        self.human_confirm_hook = confirm_hook
        self.human_reject_hook = reject_hook

    async def aexecute_plan(self, plan: SwarmPlan, alert: Alert) -> (Decision, Dict[str, List[SwarmResult]]):
        """
        Executes a swarm plan, evaluates results, performs retries,
        and formulates a final decision.

        Returns a tuple of (Decision, run_history).
        """
        run_history: Dict[str, List[SwarmResult]] = {step.step_id: [] for step in plan.steps}
        final_results: Dict[str, SwarmResult] = {}

        current_steps = list(plan.steps)

        for i in range(self.max_retries + 1):
            logging.info(f"Execution Cycle {i+1}/{self.max_retries + 1}. Steps to run: {len(current_steps)}")

            results = await self.orchestrator.execute_swarm(current_steps)

            for res in results:
                step = next((s for s in current_steps if s.agent_id == res.agent_id), None)
                if step:
                    run_history[step.step_id].append(res)

            needs_retry = self._evaluate_results(plan.steps, run_history, final_results)

            if not needs_retry:
                logging.info("All mandatory steps successful and meet confidence thresholds.")
                break

            current_steps = needs_retry
            logging.warning(f"Retrying {len(current_steps)} steps.")

        # If after all retries, mandatory steps are still not met, escalate
        decision: Decision
        if self._still_requires_action(plan.steps, final_results) and self.llm_agent_id:
            logging.info("Deterministic steps failed or have low confidence. Escalating to LLM.")
            decision = await self._escalate_to_llm(plan, final_results, alert)
        else:
            decision = self._formulate_decision(final_results)

        return self._request_human_confirmation(decision), run_history

    def _evaluate_results(
        self,
        all_plan_steps: List[SwarmStep],
        run_history: Dict[str, List[SwarmResult]],
        final_results: Dict[str, SwarmResult],
    ) -> List[SwarmStep]:
        """
        Evaluates the latest results and determines which steps need a retry.
        Populates final_results with successful outcomes.
        """
        steps_to_retry = []

        for step in all_plan_steps:
            if step.step_id in final_results:
                continue  # Already have a passing result for this step

            latest_result = run_history[step.step_id][-1] if run_history[step.step_id] else None

            if not latest_result:
                continue

            is_successful = latest_result.is_successful()
            meets_confidence = latest_result.confidence >= step.min_confidence

            if is_successful and meets_confidence:
                final_results[step.step_id] = latest_result
                logging.info(f"Step {step.step_id} ({step.agent_id}) succeeded and met confidence.")
            elif step.mandatory:
                if step.retryable and len(run_history[step.step_id]) <= self.max_retries:
                    steps_to_retry.append(step)
                    logging.warning(f"Mandatory step {step.step_id} ({step.agent_id}) failed or confidence too low. Scheduling retry.")
                else:
                    final_results[step.step_id] = latest_result # Failed permanently
                    logging.error(f"Mandatory step {step.step_id} ({step.agent_id}) failed and is not retryable or exceeded retries.")

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

    def _request_human_confirmation(self, decision: Decision) -> Decision:
        """Handles the human-in-the-loop governance step."""
        if self.human_confirm_hook and self.human_reject_hook:
            logging.info("Decision requires human confirmation.")
            is_confirmed = self.human_confirm_hook(decision)
            if is_confirmed:
                decision.is_human_confirmed = True
                logging.info("Human confirmed the decision.")
            else:
                self.human_reject_hook(decision)
                decision.is_human_confirmed = False
                logging.warning("Human rejected the decision.")
        else:
            logging.info("No human hooks registered. Proceeding without confirmation.")

        return decision
