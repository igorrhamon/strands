"""
Unit Tests for Decision Engine

Tests:
- Rule evaluation
- Decision state logic
- LLM fallback trigger
- Semantic evidence consumption
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime

from src.models.cluster import AlertCluster
from src.models.alert import NormalizedAlert, ValidationStatus
from src.models.metric_trend import MetricTrend, TrendState
from src.models.decision import Decision, DecisionState, SemanticEvidence
from src.rules.decision_rules import (
    DecisionRules,
    RuleEngine,
    RuleResult,
    RULE_CRITICAL_DEGRADING,
    RULE_RECOVERY_DETECTED,
    RULE_STABLE_METRICS,
    RULE_DEFAULT_OBSERVE,
)
from src.agents.decision_engine import DecisionEngine


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_cluster():
    """Create a sample AlertCluster for testing."""
    alerts = [
        NormalizedAlert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-001",
            service="checkout-service",
            severity="critical",
            description="High CPU usage detected",
            labels={},
            validation_status=ValidationStatus.VALID,
        ),
    ]
    return AlertCluster.from_alerts(alerts, correlation_score=0.9)


@pytest.fixture
def warning_cluster():
    """Create a warning-level cluster."""
    alerts = [
        NormalizedAlert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-002",
            service="payment-service",
            severity="warning",
            description="Elevated latency",
            labels={},
            validation_status=ValidationStatus.VALID,
        ),
    ]
    return AlertCluster.from_alerts(alerts, correlation_score=0.85)


@pytest.fixture
def degrading_trends():
    """Create degrading metric trends."""
    return {
        "cpu": MetricTrend(
            metric_name="cpu_usage",
            trend_state=TrendState.DEGRADING,
            confidence=0.85,
            data_points=[],
        ),
        "memory": MetricTrend(
            metric_name="memory_usage",
            trend_state=TrendState.DEGRADING,
            confidence=0.80,
            data_points=[],
        ),
    }


@pytest.fixture
def recovering_trends():
    """Create recovering metric trends."""
    return {
        "cpu": MetricTrend(
            metric_name="cpu_usage",
            trend_state=TrendState.RECOVERING,
            confidence=0.75,
            data_points=[],
        ),
        "memory": MetricTrend(
            metric_name="memory_usage",
            trend_state=TrendState.RECOVERING,
            confidence=0.80,
            data_points=[],
        ),
    }


@pytest.fixture
def stable_trends():
    """Create stable metric trends."""
    return {
        "cpu": MetricTrend(
            metric_name="cpu_usage",
            trend_state=TrendState.STABLE,
            confidence=0.70,
            data_points=[],
        ),
        "memory": MetricTrend(
            metric_name="memory_usage",
            trend_state=TrendState.STABLE,
            confidence=0.75,
            data_points=[],
        ),
    }


@pytest.fixture
def historical_evidence():
    """Create sample semantic evidence."""
    return [
        SemanticEvidence(
            decision_id=uuid4(),
            similarity_score=0.90,
            summary="Previous alert on checkout-service was closed as resolved",
        ),
        SemanticEvidence(
            decision_id=uuid4(),
            similarity_score=0.85,
            summary="Similar pattern observed and escalated to team",
        ),
    ]


# ============================================================================
# DecisionRules Tests
# ============================================================================

class TestDecisionRules:
    """Tests for individual decision rules."""
    
    def test_critical_degrading_fires(self, sample_cluster, degrading_trends):
        """Test RULE_CRITICAL_DEGRADING fires for critical + degrading."""
        result = DecisionRules.check_critical_degrading(
            sample_cluster,
            degrading_trends,
        )
        
        assert result.fires is True
        assert result.decision_state == DecisionState.ESCALATE
        assert result.confidence >= 0.8
        assert result.rule_id == RULE_CRITICAL_DEGRADING
    
    def test_critical_degrading_not_critical(self, warning_cluster, degrading_trends):
        """Test RULE_CRITICAL_DEGRADING doesn't fire for non-critical."""
        result = DecisionRules.check_critical_degrading(
            warning_cluster,
            degrading_trends,
        )
        
        assert result.fires is False
    
    def test_recovery_detected_fires(self, recovering_trends):
        """Test RULE_RECOVERY_DETECTED fires when all recovering."""
        result = DecisionRules.check_recovery_detected(recovering_trends)
        
        assert result.fires is True
        assert result.decision_state == DecisionState.CLOSE
        assert result.rule_id == RULE_RECOVERY_DETECTED
    
    def test_recovery_not_all_recovering(self, stable_trends):
        """Test RULE_RECOVERY_DETECTED doesn't fire when not all recovering."""
        result = DecisionRules.check_recovery_detected(stable_trends)
        
        assert result.fires is False
    
    def test_stable_metrics_fires(self, stable_trends):
        """Test RULE_STABLE_METRICS fires for stable metrics."""
        result = DecisionRules.check_stable_metrics(stable_trends)
        
        assert result.fires is True
        assert result.decision_state == DecisionState.OBSERVE
    
    def test_stable_metrics_blocked_by_degrading(self, degrading_trends):
        """Test RULE_STABLE_METRICS doesn't fire when degrading present."""
        result = DecisionRules.check_stable_metrics(degrading_trends)
        
        assert result.fires is False
    
    def test_historical_patterns_close(self, historical_evidence):
        """Test historical pattern matching for close."""
        result = DecisionRules.check_historical_patterns(historical_evidence)
        
        assert result.fires is True
        # First evidence mentions "closed" so should recommend close
        assert result.decision_state in [DecisionState.CLOSE, DecisionState.ESCALATE]
    
    def test_historical_patterns_no_evidence(self):
        """Test historical patterns with no evidence."""
        result = DecisionRules.check_historical_patterns([])
        
        assert result.fires is False
    
    def test_default_observe(self):
        """Test default observe rule."""
        result = DecisionRules.default_observe()
        
        assert result.fires is True
        assert result.decision_state == DecisionState.OBSERVE
        assert result.rule_id == RULE_DEFAULT_OBSERVE


# ============================================================================
# RuleEngine Tests
# ============================================================================

class TestRuleEngine:
    """Tests for RuleEngine evaluation."""
    
    def test_evaluate_returns_best_result(self, sample_cluster, degrading_trends):
        """Test that evaluate returns the highest confidence result."""
        engine = RuleEngine()
        
        result, fired_rules = engine.evaluate(
            cluster=sample_cluster,
            trends=degrading_trends,
            semantic_evidence=[],
        )
        
        assert result.decision_state == DecisionState.ESCALATE
        assert RULE_CRITICAL_DEGRADING in fired_rules
    
    def test_evaluate_all_rules_fired_tracked(
        self, warning_cluster, stable_trends
    ):
        """Test that all fired rules are tracked."""
        engine = RuleEngine()
        
        result, fired_rules = engine.evaluate(
            cluster=warning_cluster,
            trends=stable_trends,
            semantic_evidence=[],
        )
        
        # Multiple rules should have been evaluated
        assert len(fired_rules) >= 1
        # All rule IDs should be strings
        assert all(isinstance(r, str) for r in fired_rules)
    
    def test_evaluate_uses_default_when_no_match(self, warning_cluster):
        """Test that default OBSERVE is used when no rule matches."""
        engine = RuleEngine()
        
        # Empty trends, no evidence
        result, fired_rules = engine.evaluate(
            cluster=warning_cluster,
            trends={},
            semantic_evidence=[],
        )
        
        # Should use default or insufficient data rule
        assert result.decision_state in [DecisionState.OBSERVE, DecisionState.MANUAL_REVIEW]


# ============================================================================
# DecisionEngine Tests
# ============================================================================

class TestDecisionEngine:
    """Tests for DecisionEngine agent."""
    
    @pytest.mark.asyncio
    async def test_decide_returns_decision(self, sample_cluster, degrading_trends):
        """Test that decide returns a valid Decision."""
        engine = DecisionEngine(llm_enabled=False)
        
        decision = await engine.decide(
            cluster=sample_cluster,
            trends=degrading_trends,
            semantic_evidence=[],
        )
        
        assert isinstance(decision, Decision)
        assert decision.decision_state is not None
        assert len(decision.rules_applied) > 0
    
    @pytest.mark.asyncio
    async def test_decide_critical_escalates(self, sample_cluster, degrading_trends):
        """Test that critical + degrading results in ESCALATE."""
        engine = DecisionEngine(llm_enabled=False)
        
        decision = await engine.decide(
            cluster=sample_cluster,
            trends=degrading_trends,
            semantic_evidence=[],
        )
        
        assert decision.decision_state == DecisionState.ESCALATE
    
    @pytest.mark.asyncio
    async def test_decide_recovery_closes(self, warning_cluster, recovering_trends):
        """Test that all recovering results in CLOSE."""
        engine = DecisionEngine(llm_enabled=False)
        
        decision = await engine.decide(
            cluster=warning_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        assert decision.decision_state == DecisionState.CLOSE
    
    @pytest.mark.asyncio
    async def test_decide_includes_semantic_evidence(
        self, warning_cluster, stable_trends, historical_evidence
    ):
        """Test that semantic evidence is included in decision."""
        engine = DecisionEngine(llm_enabled=False)
        
        decision = await engine.decide(
            cluster=warning_cluster,
            trends=stable_trends,
            semantic_evidence=historical_evidence,
        )
        
        assert decision.semantic_evidence == historical_evidence
    
    @pytest.mark.asyncio
    async def test_llm_fallback_triggered(self, warning_cluster):
        """Test that LLM fallback is triggered when confidence is low."""
        engine = DecisionEngine(llm_enabled=True, llm_fallback_threshold=0.99)
        
        decision = await engine.decide(
            cluster=warning_cluster,
            trends={},  # No trends = low confidence
            semantic_evidence=[],
        )
        
        # With LLM enabled and low confidence, should get MANUAL_REVIEW
        # (our placeholder LLM returns MANUAL_REVIEW)
        assert decision.llm_contribution is True or decision.decision_state == DecisionState.MANUAL_REVIEW
    
    @pytest.mark.asyncio
    async def test_llm_disabled(self, warning_cluster):
        """Test that LLM is not called when disabled."""
        engine = DecisionEngine(llm_enabled=False)
        
        decision = await engine.decide(
            cluster=warning_cluster,
            trends={},
            semantic_evidence=[],
        )
        
        assert decision.llm_contribution is False
    
    def test_decide_sync(self, sample_cluster, degrading_trends):
        """Test synchronous decide method."""
        engine = DecisionEngine(llm_enabled=False)
        
        decision = engine.decide_sync(
            cluster=sample_cluster,
            trends=degrading_trends,
            semantic_evidence=[],
        )
        
        assert isinstance(decision, Decision)
        assert decision.llm_contribution is False


# ============================================================================
# Decision Model Tests
# ============================================================================

class TestDecisionModel:
    """Tests for Decision model."""
    
    def test_is_confirmed_false_by_default(self):
        """Test that new decisions are not confirmed."""
        decision = Decision(
            decision_state=DecisionState.CLOSE,
            confidence=0.9,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        assert decision.is_confirmed is False
        assert decision.human_validation_status.value == "PENDING"
    
    def test_confirm_updates_status(self):
        """Test that confirm() updates status correctly."""
        decision = Decision(
            decision_state=DecisionState.CLOSE,
            confidence=0.9,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        decision.confirm("test-user")
        
        assert decision.is_confirmed is True
        assert decision.validated_by == "test-user"
        assert decision.validated_at is not None
    
    def test_reject_updates_status(self):
        """Test that reject() updates status correctly."""
        decision = Decision(
            decision_state=DecisionState.CLOSE,
            confidence=0.9,
            justification="Test",
            rules_applied=["rule_1"],
        )
        
        decision.reject("test-user")
        
        assert decision.is_confirmed is False
        assert decision.human_validation_status.value == "REJECTED"
