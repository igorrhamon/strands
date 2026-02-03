import pytest
from datetime import datetime, timezone
from uuid import uuid4
from src.models.alert import NormalizedAlert, AlertSource, ValidationStatus
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType
from src.models.decision import DecisionStatus, AutomationLevel
from src.agents.governance.decision_engine import DecisionEngine

@pytest.fixture
def mock_alert():
    return NormalizedAlert(
        fingerprint="test-alert-123",
        service="payment-service",
        description="High latency in payment processing",
        severity="critical",
        source=AlertSource.GRAFANA,
        timestamp=datetime.now(timezone.utc),
        validation_status=ValidationStatus.VALID
    )

@pytest.fixture
def swarm_results():
    return [
        SwarmResult(
            agent_id="metrics_analysis",
            hypothesis="CPU saturation",
            confidence=0.96,
            evidence=[
                EvidenceItem(
                    type=EvidenceType.METRIC,
                    description="CPU usage > 90%",
                    source_url="http://grafana/...",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
        ),
        SwarmResult(
            agent_id="correlator",
            hypothesis="CPU saturation",
            confidence=0.80,
            evidence=[]
        )
    ]

@pytest.mark.asyncio
async def test_consolidate_agreement(mock_alert, swarm_results):
    engine = DecisionEngine()
    candidate = await engine.consolidate(mock_alert, swarm_results)
    
    assert candidate.alert_reference == mock_alert.fingerprint
    assert candidate.primary_hypothesis == "CPU saturation"
    assert candidate.automation_level == AutomationLevel.FULL
    assert "CPU usage > 90%" in candidate.supporting_evidence[0]
    assert not candidate.conflicting_hypotheses

@pytest.mark.asyncio
async def test_consolidate_conflict(mock_alert):
    results = [
        SwarmResult(
            agent_id="metrics",
            hypothesis="CPU saturation",
            confidence=0.85,
            evidence=[]
        ),
        SwarmResult(
            agent_id="logs",
            hypothesis="Database lock",
            confidence=0.82,
            evidence=[]
        )
    ]
    
    engine = DecisionEngine()
    candidate = await engine.consolidate(mock_alert, results)
    
    assert candidate.primary_hypothesis == "CPU saturation" # Winner because 0.85 > 0.82
    assert candidate.conflicting_hypotheses
    # The conflict string includes agent id
    assert any("Database lock" in c for c in candidate.conflicting_hypotheses)
    assert candidate.automation_level == AutomationLevel.MANUAL

@pytest.mark.asyncio
async def test_empty_results(mock_alert):
    engine = DecisionEngine()
    candidate = await engine.consolidate(mock_alert, [])
    
    assert candidate.status == DecisionStatus.PROPOSED
    assert "No analysis results" in candidate.summary
