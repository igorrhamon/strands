"""
Integration Test for Swarm Execution.

Verifies:
1. Parallel execution of agents.
2. Result aggregation.
3. Partial failure handling (Resilience).
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from datetime import datetime

from src.models.alert import NormalizedAlert, AlertSource, ValidationStatus
from src.agents.swarm.orchestrator import SwarmOrchestrator
from src.agents.analysis.metrics_analysis import MetricsAnalysisAgent
from src.agents.analysis.repository_context import RepositoryContextAgent
from src.agents.analysis.correlator import CorrelatorAgent
from src.agents.analysis.embedding_agent import EmbeddingAgent
from src.agents.analysis.graph_agent import GraphAgent
from src.models.swarm import SwarmResult

# Mock Repos
from src.graph.neo4j_repo import Neo4jRepository
from src.graph.qdrant_repo import QdrantRepository

class FailingAgent:
    """Agent that always fails for testing resilience."""
    agent_id = "failing_agent"
    
    async def analyze(self, alert):
        raise RuntimeError("I crashed!")

@pytest.mark.asyncio
async def test_full_swarm_execution():
    """Test happy path with all agents."""
    
    # Setup Mocks
    mock_neo4j = MagicMock(spec=Neo4jRepository)
    mock_qdrant = MagicMock(spec=QdrantRepository)
    
    # Instantiate Agents
    agents = [
        MetricsAnalysisAgent(),
        RepositoryContextAgent(),
        CorrelatorAgent(),
        EmbeddingAgent(mock_qdrant),
        GraphAgent(mock_neo4j)
    ]
    
    orchestrator = SwarmOrchestrator(agents)
    
    alert = NormalizedAlert(
        fingerprint="test-alert-1",
        timestamp=datetime.utcnow(),
        service="checkout-service",
        severity="critical",
        description="High CPU usage and errors",
        source=AlertSource.GRAFANA,
        validation_status=ValidationStatus.VALID
    )
    
    results = await orchestrator.run_swarm(alert)
    
    assert len(results) == 5
    ids = [r.agent_id for r in results]
    assert "metrics_analysis" in ids
    assert "graph_agent" in ids
    assert "embedding_agent" in ids

@pytest.mark.asyncio
async def test_swarm_partial_failure():
    """Test that swarm continues even if one agent fails."""
    
    agents = [
        MetricsAnalysisAgent(),
        FailingAgent() # This one will crash
    ]
    
    orchestrator = SwarmOrchestrator(agents)
    
    alert = NormalizedAlert(
        fingerprint="test-alert-2",
        timestamp=datetime.utcnow(),
        service="payment-service",
        severity="warning",
        description="Testing failure",
        source=AlertSource.GRAFANA,
        validation_status=ValidationStatus.VALID
    )
    
    results = await orchestrator.run_swarm(alert)
    
    # Should get 1 valid result, not 0 and not Exception
    assert len(results) == 1
    assert results[0].agent_id == "metrics_analysis"
    
