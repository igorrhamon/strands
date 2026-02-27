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
async def test_execute_new_swarm_returns_decision_id_and_dict(coordinator, mock_controller):
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
    execution_id, decision_dict = await coordinator._execute_new_swarm(request)

    # Assert
    assert execution_id == expected_decision_id
    assert decision_dict["decision_id"] == expected_decision_id
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
    assert result.decision is not None
    assert result.decision["decision_id"] == "dec_e2e"
    assert mock_controller.make_decision.called


@pytest.mark.asyncio
async def test_coordinate_update_graph_decision_is_none(coordinator, mock_controller):
    """UPDATE_GRAPH path must not set decision — _execute_new_swarm is never called."""
    mock_decision = SwarmDecision(decision_id="dec_first", confidence_score=0.9, state=DecisionState.APPROVED)
    mock_controller.make_decision.return_value = mock_decision

    request_first = CoordinationRequest(
        source_id="src_upd",
        event_data={"severity": "high"},
        event_type="security_alert",
        source_system="prometheus",
    )

    # First call registers execution in dedup cache
    result_first = await coordinator.coordinate(request_first)
    assert result_first.execution_mode == ExecutionMode.NEW_SWARM
    assert result_first.decision is not None

    # Second call with same source_id → UPDATE_GRAPH
    request_dup = CoordinationRequest(
        source_id="src_upd",
        event_data={"severity": "critical"},
        event_type="security_alert",
        source_system="prometheus",
    )

    result_dup = await coordinator.coordinate(request_dup)

    assert result_dup.execution_mode == ExecutionMode.UPDATE_GRAPH
    assert result_dup.decision is None
    assert result_dup.execution_id == result_first.execution_id
    assert result_dup.original_execution_id == result_first.execution_id


@pytest.mark.asyncio
async def test_coordinate_skip_execution_decision_is_none(mock_controller):
    """SKIP_EXECUTION path must not set decision — _execute_new_swarm is never called."""
    from src.deduplication.event_deduplicator import DeduplicationAction

    mock_decision = SwarmDecision(decision_id="dec_skip", confidence_score=0.9, state=DecisionState.APPROVED)
    mock_controller.make_decision.return_value = mock_decision

    # Use a policy that skips duplicates instead of updating
    policy = DeduplicationPolicy(
        enabled=True,
        ttl_minutes=30,
        action_on_duplicate=DeduplicationAction.SKIP_DUPLICATE,
    )
    coord = SwarmCoordinator(swarm_decision_controller=mock_controller, deduplication_policy=policy)

    request = CoordinationRequest(
        source_id="src_skip",
        event_data={"severity": "high"},
        event_type="cpu_alert",
    )

    # First execution registers source_id
    result_first = await coord.coordinate(request)
    assert result_first.execution_mode == ExecutionMode.NEW_SWARM

    # Manually register in dedup cache to simulate SKIP_DUPLICATE on next call
    # (EventDeduplicator always returns UPDATE_EXISTING; patch to SKIP_DUPLICATE)
    from unittest.mock import patch
    with patch.object(
        coord.deduplicator,
        "check_duplicate",
        return_value=(DeduplicationAction.SKIP_DUPLICATE, result_first.execution_id),
    ):
        result_skip = await coord.coordinate(request)

    assert result_skip.execution_mode == ExecutionMode.SKIP_EXECUTION
    assert result_skip.decision is None
    assert result_skip.execution_id == result_first.execution_id
