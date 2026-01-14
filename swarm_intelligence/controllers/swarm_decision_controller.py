from typing import List, Optional, Callable
from swarm_intelligence.core.models import (
    SwarmPlan,
    AgentExecution,
    Decision,
    Alert,
    HumanDecision,
    SwarmStep,
)
from swarm_intelligence.policy.confidence_policy import ConfidencePolicy
from swarm_intelligence.services.confidence_service import ConfidenceService


class SwarmDecisionController:
    """
    Transforms evidence into a final decision, with LLM and human in the loop.
    This controller is a stateless governance and decision engine.
    """

    async def decide(
        self,
        plan: SwarmPlan,
        successful_executions: List[AgentExecution],
        alert: Alert,
        confidence_service: ConfidenceService,
        confidence_policy: ConfidencePolicy,
        human_hook: Optional[Callable[[Decision], HumanDecision]],
        run_id: str,
        master_seed: int,
        sequence_id: int,
    ) -> Decision:
        decision = self._formulate_decision(successful_executions)

        return self._request_human_review(
            decision, human_hook, confidence_service, confidence_policy, sequence_id
        )

    def _formulate_decision(
        self, successful_executions: List[AgentExecution]
    ) -> Decision:
        all_evidence = [
            ev for ex in successful_executions for ev in ex.output_evidence
        ]

        if not all_evidence:
            return Decision(
                summary="No evidence produced.",
                action_proposed="manual_review",
                confidence=0.0,
                supporting_evidence=[],
            )

        avg_confidence = sum(ev.confidence for ev in all_evidence) / len(
            all_evidence
        )
        summary = "; ".join([str(ev.content) for ev in all_evidence])

        return Decision(
            summary=f"Aggregated Evidence: {summary}",
            action_proposed="auto_remediate"
            if avg_confidence > 0.8
            else "log_for_review",
            confidence=avg_confidence,
            supporting_evidence=all_evidence,
        )

    def _request_human_review(
        self,
        decision: Decision,
        human_hook: Optional[Callable[[Decision], HumanDecision]],
        confidence_service: ConfidenceService,
        confidence_policy: ConfidencePolicy,
        sequence_id: int,
    ) -> Decision:
        from swarm_intelligence.core.models import HumanAction
        if human_hook:
            human_decision = human_hook(decision)
            decision.human_decision = human_decision
            if human_decision.action == HumanAction.OVERRIDE:
                for evidence in decision.supporting_evidence:
                    sequence_id += 1
                    confidence_service.penalize_for_override(
                        evidence.agent_id,
                        decision.decision_id,
                        sequence_id,
                        confidence_policy,
                    )
        return decision
