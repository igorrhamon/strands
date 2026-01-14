
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
from swarm_intelligence.policy.confidence_policy import ConfidencePolicy, DefaultConfidencePolicy
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
        confidence_policy: ConfidencePolicy = None,
    ):
        self.orchestrator = orchestrator
        self.confidence_service = confidence_service
        self.llm_agent_id = llm_agent_id
        self.confidence_policy = confidence_policy or DefaultConfidencePolicy()
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
        Executes a swarm plan, evaluates results, and formulates a final decision.
        The SwarmOrchestrator now handles all retry logic internally.
        """
        master_seed = master_seed if master_seed is not None else random.randint(0, 1_000_000)
        sequence_id = 0

        # Initial time decay application
        for step in plan.steps:
            sequence_id += 1
            self.confidence_service.apply_time_decay(step.agent_id, sequence_id, 0.001) # Example decay rate

        steps_context = {
            step.step_id: {
                "last_confidence": self.confidence_service.get_last_confidence(step.agent_id),
                "domain_hints": [] # Placeholder for future domain inference logic
            }
            for step in plan.steps
        }

        if self.replay_mode:
            # In replay mode, we assume historical results include all retries
            executions = list(self.replay_results.values())
            all_retry_attempts = [] # This needs to be enhanced for full replay fidelity
        else:
            executions, all_retry_attempts = await self.orchestrator.execute_swarm(
                plan.steps, run_id, master_seed, steps_context
            )

        # Filter for the final, successful execution for each step for decision making
        final_successful_executions = []
        processed_steps = set()
        # Iterate in reverse to find the last successful execution first
        for ex in reversed(executions):
            if ex.step_id not in processed_steps and ex.is_successful():
                final_successful_executions.append(ex)
                processed_steps.add(ex.step_id)

        # If any mandatory step is not in the set of successful steps, escalate
        successful_step_ids = {ex.step_id for ex in final_successful_executions}
        if not all(s.step_id in successful_step_ids for s in plan.steps if s.mandatory):
            logging.warning("Not all mandatory steps succeeded after retries. Escalating to LLM.")
            decision = await self._escalate_to_llm(plan, final_successful_executions, alert, run_id, master_seed)
        else:
            decision = self._formulate_decision(final_successful_executions)

        return self._request_human_review(decision, sequence_id), executions, all_retry_attempts, master_seed

    async def _escalate_to_llm(self, plan: SwarmPlan, successful_executions: List[AgentExecution], alert: Alert, run_id: str, master_seed: int) -> Decision:
        """Generates a hypothesis from an LLM when deterministic agents fail."""
        if not self.llm_agent_id:
            return self._formulate_decision(successful_executions)

        llm_step = SwarmStep(agent_id=self.llm_agent_id, mandatory=True)
        llm_context = {
            llm_step.step_id: {
                "last_confidence": self.confidence_service.get_last_confidence(self.llm_agent_id),
                "domain_hints": []
            }
        }
        # The call to the orchestrator for the LLM step must also be consistent
        llm_executions, _ = await self.orchestrator.execute_swarm([llm_step], run_id, master_seed, llm_context)
        llm_execution = llm_executions[0]

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

    def _request_human_review(self, decision: Decision, sequence_id: int) -> Decision:
        """Handles the human-in-the-loop governance step, processing a structured HumanDecision."""
        if self.human_review_hook:
            logging.info("Decision requires human review.")
            human_decision = self.human_review_hook(decision)
            decision.human_decision = human_decision
            logging.info(f"Human reviewed the decision: {human_decision.action.value}")

            if human_decision.action == HumanAction.OVERRIDE:
                for evidence in decision.supporting_evidence:
                    sequence_id += 1
                    self.confidence_service.penalize_for_override(evidence.agent_id, decision.decision_id, sequence_id, self.confidence_policy)
        else:
            logging.info("No human review hook registered. Proceeding without human governance.")

        return decision
