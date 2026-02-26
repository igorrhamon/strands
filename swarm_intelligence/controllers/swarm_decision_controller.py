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
        human_hook: Optional[Callable[[Decision], Optional[HumanDecision]]],
        run_id: str,
        master_seed: int,
    ) -> Decision:
        decision = self._formulate_decision(successful_executions)

        return self._request_human_review(
            decision, human_hook, confidence_service, confidence_policy
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
                metadata={}
            )

        avg_confidence = sum(ev.confidence for ev in all_evidence) / len(all_evidence)
        summary = "; ".join([str(ev.content) for ev in all_evidence])

        llm_hypotheses = []
        for ev in all_evidence:
            ev_type = getattr(ev, "evidence_type", None)
            ev_type_value = getattr(ev_type, "value", str(ev_type)).lower()
            if ev_type_value == "hypothesis":
                llm_hypotheses.append(ev)

        if llm_hypotheses:
            llm_content = llm_hypotheses[-1].content if isinstance(llm_hypotheses[-1].content, dict) else {"recommended_procedure": str(llm_hypotheses[-1].content)}
            root_cause = llm_content.get("root_cause", "LLM fallback analysis")
            procedure = llm_content.get("recommended_procedure", "manual_review")
            return Decision(
                summary=f"LLM-enriched analysis: {root_cause}; procedimento sugerido: {procedure}; evidence={summary}",
                action_proposed="human_review_required",
                confidence=avg_confidence,
                supporting_evidence=all_evidence,
                metadata={"llm_enriched": True, "llm_procedure": procedure}
            )

        return Decision(
            summary=f"Aggregated Evidence: {summary}",
            action_proposed="auto_remediate" if avg_confidence > 0.8 else "human_review_required",
            confidence=avg_confidence,
            supporting_evidence=all_evidence,
            metadata={"aggregated": True, "evidence_count": len(all_evidence)}
        )

    def _request_human_review(
        self,
        decision: Decision,
        human_hook: Optional[Callable[[Decision], Optional[HumanDecision]]],
        confidence_service: ConfidenceService,
        confidence_policy: ConfidencePolicy,
    ) -> Decision:
        from swarm_intelligence.core.models import HumanAction
        if human_hook:
            human_decision = human_hook(decision)
            decision.human_decision = human_decision
            if human_decision and human_decision.action == HumanAction.OVERRIDE:
                for evidence in decision.supporting_evidence:
                    confidence_service.penalize_for_override(
                        evidence.agent_id,
                        decision.decision_id,
                        confidence_policy,
                    )
        return decision
