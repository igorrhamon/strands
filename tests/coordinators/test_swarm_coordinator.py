import pytest
import asyncio
import logging
from unittest.mock import MagicMock, patch
from src.controllers.swarm_coordinator import (
    SwarmCoordinator,
    CoordinationRequest,
    ExecutionMode,
    DeduplicationPolicy
)
from src.controllers.swarm_decision_controller import (
    SwarmDecisionController,
    SwarmDecision,
    DecisionState,
    DecisionReason
)
from src.strategies.consensus_strategy import AgentExecution, AgentRole

@pytest.fixture
def mock_controller():
    return MagicMock(spec=SwarmDecisionController)

@pytest.fixture
def coordinator(mock_controller):
    policy = DeduplicationPolicy(enabled=True, ttl_minutes=10)
    return SwarmCoordinator(
        swarm_decision_controller=mock_controller,
        deduplication_policy=policy
    )

@pytest.mark.asyncio
async def test_execute_new_swarm_returns_decision_id(coordinator, mock_controller):
    # Setup
    request = CoordinationRequest(
        source_id="test_source_123",
        event_data={"agent_executions": []},
        event_type="security_alert",
        source_system="prometheus",
        priority=5
    )

    expected_decision_id = "test_decision_uuid"
    mock_decision = SwarmDecision(
        decision_id=expected_decision_id,
        state=DecisionState.APPROVED,
        reason=DecisionReason.WEIGHTED_CONSENSUS,
        confidence_score=0.9
    )
    mock_controller.make_decision.return_value = mock_decision

    # Execute
    execution_id = await coordinator._execute_new_swarm(request)

    # Assert
    assert execution_id == expected_decision_id
    assert mock_controller.make_decision.called

@pytest.mark.asyncio
async def test_execute_new_swarm_calls_controller_with_context(coordinator, mock_controller):
    # Setup
    request = CoordinationRequest(
        source_id="test_source_456",
        event_data={"agent_executions": [
            {
                "agent_id": "agent_1",
                "agent_name": "Test Agent",
                "agent_role": "log_analyzer",
                "confidence_score": 0.8,
                "evidence_count": 2,
                "result": "approve",
                "reasoning": "Reasoning"
            }
        ]},
        event_type="network_failure",
        source_system="grafana",
        priority=8
    )

    mock_decision = SwarmDecision(decision_id="dec_456")
    mock_controller.make_decision.return_value = mock_decision

    # Execute
    await coordinator._execute_new_swarm(request)

    # Assert
    args, kwargs = mock_controller.make_decision.call_args
    agent_executions = args[0]
    context = args[1]

    assert len(agent_executions) == 1
    assert agent_executions[0].agent_id == "agent_1"
    assert agent_executions[0].agent_role == AgentRole.LOG_ANALYZER

    assert context["source_id"] == "test_source_456"
    assert context["event_type"] == "network_failure"
    assert context["source_system"] == "grafana"
    assert context["priority"] == 8

@pytest.mark.asyncio
async def test_execute_new_swarm_propagates_exception(coordinator, mock_controller):
    # Setup
    request = CoordinationRequest(
        source_id="test_source_err",
        event_data={},
        priority=1
    )

    mock_controller.make_decision.side_effect = RuntimeError("Controller failure")

    # Execute & Assert
    with pytest.raises(RuntimeError, match="Controller failure"):
        with patch.object(coordinator.logger, 'error') as mock_log_error:
            await coordinator._execute_new_swarm(request)
            assert mock_log_error.called

@pytest.mark.asyncio
async def test_coordinate_new_execution_end_to_end(coordinator, mock_controller):
    # Disable deduplication for end-to-end test
    coordinator.deduplication_policy = DeduplicationPolicy(enabled=False)

    request = CoordinationRequest(
        source_id="test_source_e2e",
        event_data={},
        event_type="generic_event"
    )

    mock_decision = SwarmDecision(decision_id="dec_e2e", confidence_score=0.75, state=DecisionState.APPROVED)
    mock_controller.make_decision.return_value = mock_decision

    # Execute
    result = await coordinator.coordinate(request)

    # Assert
    assert result.execution_mode == ExecutionMode.NEW_SWARM
    assert result.execution_id == "dec_e2e"
    assert result.execution_id != ""
    assert mock_controller.make_decision.called
