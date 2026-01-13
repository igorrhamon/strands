
import logging
import asyncio
import random
from typing import List, Dict, Optional, Callable, Any
from swarm_intelligence.core.models import (
    SwarmPlan,
    SwarmStep,
    AgentExecution,
    Decision,
    Evidence,
    Alert,
    HumanDecision,
    HumanAction,
    RetryAttempt,
)
from swarm_intelligence.policy.retry_policy import RetryContext
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
        self.replay_mode = False
        self.replay_results: Dict[str, SwarmResult] = {}

    def set_replay_mode(self, historical_results: Dict[str, AgentExecution]):
        """Puts the controller in replay mode, using historical results instead of live execution."""
        self.replay_mode = True
        self.replay_results = historical_results

    def disable_replay_mode(self):
        """Disables replay mode."""
        self.replay_mode = False
        self.replay_results = {}

    def register_human_hooks(self, review_hook: Callable[[Decision], HumanDecision]):
        """Registers a single, comprehensive callback for human review."""
        self.human_review_hook = review_hook

    async def aexecute_plan(self, plan: SwarmPlan, alert: Alert, run_id: str, master_seed: int = None) -> (Decision, List[AgentExecution], List[RetryAttempt], int):
        """
        Executes a swarm plan, evaluates results, performs retries,
        and formulates a final decision.
        """
        master_seed = master_seed if master_seed is not None else random.randint(0, 1_000_000)

        executions: List[AgentExecution] = []
        all_retry_attempts: List[RetryAttempt] = []

        steps_to_process = list(plan.steps)

        while steps_to_process:
            if self.replay_mode:
                # In replay mode, we fetch results, not execute them
                new_executions = [self.replay_results.get(s.step_id) for s in steps_to_process]
            else:
                new_executions = await self.orchestrator.execute_swarm(steps_to_process)

            executions.extend(new_executions)

            steps_to_process, new_retries = await self._evaluate_and_get_next_steps(
                plan, run_id, master_seed, executions, all_retry_attempts
            )
            all_retry_attempts.extend(new_retries)

            if steps_to_process:
                logging.info(f"{len(steps_to_process)} steps require retries. Applying policies.")

        successful_executions = [ex for ex in executions if ex.is_successful()]

        # If after all retries, all mandatory steps are still not successful, escalate
        if not all(s.step_id in {ex.step_id for ex in successful_executions} for s in plan.steps if s.mandatory):
            logging.warning("Not all mandatory steps succeeded. Escalating to LLM.")
            decision = await self._escalate_to_llm(plan, successful_executions, alert)
        else:
            decision = self._formulate_decision(successful_executions)

        return self._request_human_review(decision), executions, all_retry_attempts, master_seed

    async def _evaluate_and_get_next_steps(
        self, plan: SwarmPlan, run_id: str, master_seed: int,
        all_executions: List[AgentExecution],
        all_retry_attempts: List[RetryAttempt]
    ) -> (List[SwarmStep], List[RetryAttempt]):

        steps_to_retry = []
        new_retry_attempts = []
        max_delay = 0.0

        successful_steps = {ex.step_id for ex in all_executions if ex.is_successful()}

        for step in plan.steps:
            if step.step_id in successful_steps:
                continue

            executions_for_step = [ex for ex in all_executions if ex.step_id == step.step_id]
            retries_for_step = [r for r in all_retry_attempts if r.step_id == step.step_id]
            total_attempts = len(executions_for_step) + len(retries_for_step)

            if step.mandatory and step.retry_policy:
                context = RetryContext(
                    run_id=run_id,
                    step_id=step.step_id,
                    agent_id=step.agent_id,
                    attempt=total_attempts + 1,
                    error=Exception(executions_for_step[-1].error) if executions_for_step and executions_for_step[-1].error else None,
                    random_seed=master_seed + total_attempts # Deterministic seed
                )

                if step.retry_policy.should_retry(context):
                    delay = step.retry_policy.next_delay(context)
                    max_delay = max(max_delay, delay)
                    steps_to_retry.append(step)
                    new_retry_attempts.append(RetryAttempt(
                        step_id=step.step_id,
                        attempt_number=context.attempt,
                        delay_seconds=delay,
                        reason=str(context.error),
                        failed_execution_id=executions_for_step[-1].execution_id
                    ))

        if max_delay > 0:
            await asyncio.sleep(max_delay)

        return steps_to_retry, new_retry_attempts

    async def _escalate_to_llm(self, plan: SwarmPlan, successful_executions: List[AgentExecution], alert: Alert) -> Decision:
        """Generates a hypothesis from an LLM when deterministic agents fail."""
        if not self.llm_agent_id:
            return self._formulate_decision(successful_executions)

        llm_step = SwarmStep(agent_id=self.llm_agent_id, mandatory=True)
        llm_execution = (await self.orchestrator.execute_swarm([llm_step]))[0]

        all_evidence = [ev for ex in successful_executions for ev in ex.output_evidence]
        all_evidence.extend(llm_execution.output_evidence)

        # Here you would typically have a more sophisticated aggregation logic
        summary = llm_execution.output_evidence[0].content.get('summary', 'N/A')
        action = llm_execution.output_evidence[0].content.get('action', 'manual_review')
        confidence = llm_execution.output_evidence[0].confidence

        return Decision(
            summary=f"LLM Hypothesis: {summary}",
            action_proposed=action,
            confidence=confidence,
            supporting_evidence=all_evidence
        )

    def _formulate_decision(self, successful_executions: List[AgentExecution]) -> Decision:
        """Formulates a final decision from the evidence of successful executions."""
        all_evidence = [ev for ex in successful_executions for ev in ex.output_evidence]

        if not all_evidence:
            return Decision(summary="No evidence produced.", action_proposed="manual_review", confidence=0.0, supporting_evidence=[])

        # A more sophisticated model would weigh evidence based on agent reputation (confidence snapshots)
        avg_confidence = sum(ev.confidence for ev in all_evidence) / len(all_evidence)

        # Simple summary for demonstration
        summary = "; ".join([str(ev.content) for ev in all_evidence])

        return Decision(
            summary=f"Aggregated Evidence: {summary}",
            action_proposed="auto_remediate" if avg_confidence > 0.8 else "log_for_review",
            confidence=avg_confidence,
            supporting_evidence=all_evidence
        )

    def _request_human_review(self, decision: Decision) -> Decision:
        """Handles the human-in-the-loop governance step, processing a structured HumanDecision."""
        if self.human_review_hook:
            logging.info("Decision requires human review.")
            human_decision = self.human_review_hook(decision)
            decision.human_decision = human_decision
            logging.info(f"Human reviewed the decision: {human_decision.action.value}")

            if human_decision.action == HumanAction.OVERRIDE:
                for evidence in decision.supporting_evidence:
                    self.confidence_service.penalize_for_override(evidence.agent_id, decision.decision_id)
        else:
            logging.info("No human review hook registered. Proceeding without human governance.")

        return decision
