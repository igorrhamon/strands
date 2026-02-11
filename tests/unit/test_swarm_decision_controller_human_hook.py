from unittest.mock import Mock

from swarm_intelligence.controllers.swarm_decision_controller import SwarmDecisionController
from swarm_intelligence.core.enums import EvidenceType, HumanAction
from swarm_intelligence.core.models import (
    AgentExecution,
    Alert,
    Decision,
    Evidence,
    HumanDecision,
    SwarmPlan,
    SwarmStep,
)


def _build_execution() -> AgentExecution:
    evidence = Evidence(
        source_agent_execution_id="exec-1",
        agent_id="agent-1",
        content={"signal": "malicious"},
        confidence=0.9,
        evidence_type=EvidenceType.METRICS,
    )
    execution = AgentExecution(
        agent_id="agent-1",
        agent_version="1.0",
        logic_hash="abc123",
        step_id="step-1",
        input_parameters={"foo": "bar"},
    )
    execution.output_evidence.append(evidence)
    return execution


async def test_decide_tolerates_pending_human_review_without_override_penalty():
    controller = SwarmDecisionController()
    confidence_service = Mock()
    confidence_policy = Mock()

    decision = await controller.decide(
        plan=SwarmPlan(objective="investigate", steps=[SwarmStep(agent_id="agent-1")]),
        successful_executions=[_build_execution()],
        alert=Alert(alert_id="alert-1", data={}),
        confidence_service=confidence_service,
        confidence_policy=confidence_policy,
        human_hook=lambda _decision: None,
        run_id="run-1",
        master_seed=42,
    )

    assert decision.human_decision is None
    confidence_service.penalize_for_override.assert_not_called()


def test_request_human_review_penalizes_on_override():
    controller = SwarmDecisionController()
    confidence_service = Mock()
    confidence_policy = Mock()

    evidence = Evidence(
        source_agent_execution_id="exec-1",
        agent_id="agent-1",
        content="indicator",
        confidence=0.8,
        evidence_type=EvidenceType.RULES,
    )
    decision = Decision(
        summary="summary",
        action_proposed="human_review_required",
        confidence=0.8,
        supporting_evidence=[evidence],
    )

    human_decision = HumanDecision(
        action=HumanAction.OVERRIDE,
        author="sec_ops",
        override_reason="manual remediation",
        overridden_action_proposed="quarantine",
    )

    reviewed = controller._request_human_review(
        decision=decision,
        human_hook=lambda _decision: human_decision,
        confidence_service=confidence_service,
        confidence_policy=confidence_policy,
    )

    assert reviewed.human_decision == human_decision
    confidence_service.penalize_for_override.assert_called_once_with(
        "agent-1",
        decision.decision_id,
        confidence_policy,
    )
