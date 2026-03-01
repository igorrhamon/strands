"""
Unit tests for ReplayEngine — replay_validation, replay_training, replay_simulation.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.engines.replay_engine import (
    ReplayEngine,
    ReplayEvent,
    ReplayMode,
    ReplayStatus,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_event(event_id: str, original_action: str | None = None) -> ReplayEvent:
    metadata = {}
    if original_action is not None:
        metadata["original_decision"] = {"action_proposed": original_action}
    return ReplayEvent(
        event_id=event_id,
        event_type="alert",
        timestamp=datetime(2025, 1, 1),
        data={"severity": "critical", "service": "checkout"},
        source="test",
        metadata=metadata,
    )


def _make_training_event(agent: str, outcome: str) -> ReplayEvent:
    return ReplayEvent(
        event_id=f"evt-{agent}-{outcome}",
        event_type="training",
        timestamp=datetime(2025, 1, 1),
        data={},
        source="test",
        metadata={"target_agent": agent, "outcome": outcome},
    )


# ---------------------------------------------------------------------------
# replay_validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validation_without_pipeline_uses_metadata_as_match():
    engine = ReplayEngine()  # no pipeline_executor
    session = engine.create_session(
        ReplayMode.VALIDATION,
        [
            _make_event("e1", original_action="restart"),
            _make_event("e2"),  # no original_decision
        ],
    )
    result = await engine.replay_validation(session)

    assert result["total_events"] == 2
    assert result["replayed_events"] == 2
    # e1 has original_decision → match; e2 does not → diverge
    assert result["matching_decisions"] == 1
    assert result["diverging_decisions"] == 1
    assert session.status == ReplayStatus.COMPLETED


@pytest.mark.asyncio
async def test_validation_with_pipeline_executor_matches_same_action():
    async def executor(data):
        return {"action_proposed": "restart", "confidence": 0.9}

    engine = ReplayEngine(pipeline_executor=executor)
    event = _make_event("e1", original_action="restart")
    session = engine.create_session(ReplayMode.VALIDATION, [event])
    result = await engine.replay_validation(session)

    assert result["matching_decisions"] == 1
    assert result["diverging_decisions"] == 0
    detail = result["details"][0]
    assert detail["status"] == "match"
    assert detail["replayed_decision"]["action_proposed"] == "restart"


@pytest.mark.asyncio
async def test_validation_with_pipeline_executor_detects_divergence():
    async def executor(data):
        return {"action_proposed": "scale-up", "confidence": 0.7}

    engine = ReplayEngine(pipeline_executor=executor)
    event = _make_event("e1", original_action="restart")
    session = engine.create_session(ReplayMode.VALIDATION, [event])
    result = await engine.replay_validation(session)

    assert result["diverging_decisions"] == 1
    assert result["matching_decisions"] == 0


# ---------------------------------------------------------------------------
# replay_training
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_training_groups_events_by_agent():
    engine = ReplayEngine()
    events = [
        _make_training_event("agent-A", "success"),
        _make_training_event("agent-A", "success"),
        _make_training_event("agent-B", "failure"),
    ]
    session = engine.create_session(ReplayMode.TRAINING, events)
    result = await engine.replay_training(session)

    agents = {a["agent_name"]: a for a in result["trained_agents"]}
    assert "agent-A" in agents
    assert "agent-B" in agents
    assert agents["agent-A"]["event_count"] == 2
    assert agents["agent-A"]["successful_outcomes"] == 2
    assert agents["agent-A"]["new_confidence"] == pytest.approx(1.0)
    assert agents["agent-B"]["successful_outcomes"] == 0
    assert agents["agent-B"]["new_confidence"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_training_calls_neo4j_create_confidence_snapshot():
    mock_adapter = MagicMock()
    engine = ReplayEngine(neo4j_adapter=mock_adapter)

    events = [
        _make_training_event("agent-X", "success"),
        _make_training_event("agent-X", "resolved"),
    ]
    session = engine.create_session(ReplayMode.TRAINING, events)
    await engine.replay_training(session)

    mock_adapter.create_confidence_snapshot.assert_called_once_with(
        agent_id="agent-X",
        value=pytest.approx(1.0),
        source_event="replay_training",
    )


# ---------------------------------------------------------------------------
# replay_simulation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_simulation_records_differences():
    engine = ReplayEngine()
    event = _make_event("e1", original_action="restart")
    session = engine.create_session(ReplayMode.SIMULATION, [event])
    modifications = {"severity": "warning"}
    result = await engine.replay_simulation(session, modifications)

    assert result["simulated_events"] == 1
    diff = result["differences"][0]
    assert diff["original_data"]["severity"] == "critical"
    assert diff["modified_data"]["severity"] == "warning"


@pytest.mark.asyncio
async def test_simulation_computes_action_changed_flag():
    async def executor(data):
        # If severity is warning, recommend OBSERVE instead of restart
        action = "restart" if data.get("severity") == "critical" else "OBSERVE"
        return {"action_proposed": action, "confidence": 0.6}

    engine = ReplayEngine(pipeline_executor=executor)
    event = _make_event("e1", original_action="restart")
    session = engine.create_session(ReplayMode.SIMULATION, [event])
    result = await engine.replay_simulation(session, {"severity": "warning"})

    diff = result["differences"][0]
    assert diff.get("action_changed") is True
