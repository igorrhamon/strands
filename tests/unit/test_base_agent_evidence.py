"""
Unit tests for BaseAgent.register_evidence.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
from src.agents.base_agent import BaseAgent, Evidence, EvidenceType, AgentOutput


# ---------------------------------------------------------------------------
# Minimal concrete subclass for testing
# ---------------------------------------------------------------------------

class _ConcreteAgent(BaseAgent):
    async def execute(self, input_data):
        pass

    async def collect_data(self, input_data):
        return {}

    def analyze(self, data):
        return {}

    def validate_output(self, result):
        return True

    async def generate_evidence(self, data, result):
        return []


# ---------------------------------------------------------------------------
# register_evidence — no Neo4j adapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_evidence_without_adapter_returns_true():
    agent = _ConcreteAgent("test-agent")
    evidence = [
        Evidence(type=EvidenceType.METRIC, source="prometheus", value=42, confidence=0.9)
    ]
    result = await agent.register_evidence(evidence, "ctx-001")
    assert result is True


@pytest.mark.asyncio
async def test_register_evidence_empty_list_returns_true():
    agent = _ConcreteAgent("test-agent")
    result = await agent.register_evidence([], "ctx-002")
    assert result is True


# ---------------------------------------------------------------------------
# register_evidence — with Neo4j adapter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_evidence_calls_neo4j_run_transaction():
    mock_adapter = MagicMock()
    mock_adapter.run_transaction = MagicMock()

    agent = _ConcreteAgent("test-agent", neo4j_adapter=mock_adapter)
    evidence = [
        Evidence(type=EvidenceType.LOG, source="logstash", value="error spike", confidence=0.8),
        Evidence(type=EvidenceType.TRACE, source="jaeger", value="latency 500ms", confidence=0.7),
    ]

    result = await agent.register_evidence(evidence, "ctx-neo4j")

    assert result is True
    mock_adapter.run_transaction.assert_called_once()

    # Verify the parameters passed to run_transaction
    call_args = mock_adapter.run_transaction.call_args
    params = call_args[0][1]  # second positional arg is the params dict
    assert params["context_id"] == "ctx-neo4j"
    assert params["agent_id"] == agent.agent_id
    assert params["agent_name"] == "test-agent"
    assert len(params["evidence"]) == 2


@pytest.mark.asyncio
async def test_register_evidence_returns_false_on_neo4j_error():
    mock_adapter = MagicMock()
    mock_adapter.run_transaction.side_effect = Exception("Neo4j connection refused")

    agent = _ConcreteAgent("test-agent", neo4j_adapter=mock_adapter)
    evidence = [
        Evidence(type=EvidenceType.ALERT, source="grafana", value="CPU high", confidence=1.0)
    ]

    result = await agent.register_evidence(evidence, "ctx-err")
    assert result is False
