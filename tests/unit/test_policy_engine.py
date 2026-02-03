"""Unit tests for Policy Engine"""
import pytest
from datetime import datetime, timezone

from src.rules.policy_engine import PolicyEngine
from src.models.cluster import AlertCluster
from src.models.alert import NormalizedAlert, ValidationStatus
from src.models.metrics import MetricsAnalysisResult, TrendClassification, MetricTrend
from src.models.decision import DecisionState


@pytest.fixture
def policy_engine():
    return PolicyEngine()


@pytest.fixture
def critical_cluster():
    """Create a cluster with critical alerts"""
    alert = NormalizedAlert(
        timestamp=datetime.now(timezone.utc),
        fingerprint="abc",
        service="api",
        severity="critical",
        description="Critical CPU usage",
        labels={"service": "api", "environment": "prod"},
        validation_status=ValidationStatus.VALID
    )
    
    return AlertCluster.from_alerts([alert], correlation_score=1.0)


@pytest.fixture
def degrading_metrics():
    """Create degrading metrics result"""
    trend = MetricTrend(
        metric_name="cpu_usage",
        query="rate(cpu[5m])",
        classification=TrendClassification.DEGRADING,
        confidence=0.9,
        slope=0.05,
        data_points=60,
        time_range_seconds=3600
    )
    
    return MetricsAnalysisResult(
        cluster_id="cluster-1",
        trends=[trend],
        overall_health=TrendClassification.DEGRADING,
        overall_confidence=0.9,
        query_latency_ms=250
    )


def test_critical_degrading_rule(policy_engine, critical_cluster, degrading_metrics):
    """Test critical + degrading = ESCALATE"""
    result = policy_engine.evaluate(critical_cluster, degrading_metrics, {})
    
    assert result["decision_state"] == DecisionState.ESCALATE
    assert result["confidence"] >= 0.8


def test_stable_metrics_rule(policy_engine, critical_cluster):
    """Test stable metrics = CLOSE (auto-resolve)"""
    stable_metrics = MetricsAnalysisResult(
        cluster_id="cluster-1",
        trends=[],
        overall_health=TrendClassification.STABLE,
        overall_confidence=0.85,
        query_latency_ms=200
    )
    
    result = policy_engine.evaluate(critical_cluster, stable_metrics, {})
    
    assert result["decision_state"] == DecisionState.CLOSE


def test_policy_engine_with_context(policy_engine, critical_cluster, degrading_metrics):
    """Test evaluation with additional context"""
    context = {
        "historical_outcomes": [],
        "related_incidents": []
    }
    
    result = policy_engine.evaluate(critical_cluster, degrading_metrics, context)
    
    assert result["decision_state"] in [DecisionState.ESCALATE, DecisionState.MANUAL_REVIEW, DecisionState.OBSERVE]
    assert "rules_applied" in result
    assert len(result["rules_applied"]) > 0

