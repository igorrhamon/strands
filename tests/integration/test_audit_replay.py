"""
Integration Tests for Audit Replay

Tests the full replay mechanism:
1. Log a decision
2. Retrieve replay context
3. Re-run decision logic
4. Verify consistency
"""

import pytest
from pathlib import Path
from uuid import uuid4
from datetime import datetime
import tempfile

from src.models.alert import NormalizedAlert, ValidationStatus
from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend, TrendState
from src.models.decision import Decision, DecisionState
from src.utils.audit_logger import AuditLogger
from src.agents.decision_engine import DecisionEngine


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for audit logs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def audit_logger(temp_log_dir):
    """Create an AuditLogger with temp directory."""
    return AuditLogger(log_dir=temp_log_dir)


@pytest.fixture
def decision_engine():
    """Create a DecisionEngine."""
    return DecisionEngine(llm_enabled=False)


@pytest.fixture
def sample_cluster():
    """Create a sample AlertCluster."""
    alerts = [
        NormalizedAlert(
            timestamp=datetime.utcnow(),
            fingerprint="fp-replay-001",
            service="payment-service",
            severity="warning",
            description="High latency detected",
            labels={"env": "production"},
            validation_status=ValidationStatus.VALID,
        ),
    ]
    return AlertCluster.from_alerts(alerts, correlation_score=0.85)


@pytest.fixture
def recovering_trends():
    """Create recovering trends."""
    return {
        "latency": MetricTrend(
            metric_name="request_latency_ms",
            trend_state=TrendState.RECOVERING,
            confidence=0.80,
            data_points=[],
        ),
    }


# ============================================================================
# Replay Integration Tests
# ============================================================================

class TestAuditReplay:
    """Integration tests for audit replay mechanism."""
    
    @pytest.mark.asyncio
    async def test_decision_logged_and_retrieved(
        self, audit_logger, decision_engine, sample_cluster, recovering_trends
    ):
        """Test that a decision can be logged and retrieved."""
        # Generate decision
        decision = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        # Log decision
        audit_log = audit_logger.log_decision(
            decision=decision,
            cluster_id=sample_cluster.cluster_id,
            alert_fingerprints=[a.fingerprint for a in sample_cluster.alerts],
        )
        
        # Retrieve logs
        logs = audit_logger.find_decision_logs(decision.decision_id)
        
        assert len(logs) == 1
        assert logs[0]["decision_state"] == decision.decision_state.value
        assert logs[0]["rules_applied"] == decision.rules_applied
    
    @pytest.mark.asyncio
    async def test_replay_context_includes_all_events(
        self, audit_logger, decision_engine, sample_cluster, recovering_trends
    ):
        """Test that replay context includes all lifecycle events."""
        # Generate decision
        decision = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        # Log decision
        audit_logger.log_decision(
            decision=decision,
            cluster_id=sample_cluster.cluster_id,
            alert_fingerprints=[a.fingerprint for a in sample_cluster.alerts],
        )
        
        # Log validation
        audit_logger.log_validation(
            decision_id=decision.decision_id,
            validated_by="reviewer-123",
            approved=True,
        )
        
        # Log embedding
        audit_logger.log_embedding_created(
            decision_id=decision.decision_id,
            point_id="point-abc-123",
        )
        
        # Get replay context
        context = audit_logger.get_replay_context(decision.decision_id)
        
        assert context is not None
        assert context["can_replay"] is True
        assert context["decision"] is not None
        assert context["validation"] is not None
        assert context["validation"]["approved"] is True
        assert context["embedding"] is not None
    
    @pytest.mark.asyncio
    async def test_replayed_decision_matches_original(
        self, audit_logger, decision_engine, sample_cluster, recovering_trends
    ):
        """Test that replaying produces the same decision."""
        # Generate original decision
        original = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        # Log original
        audit_logger.log_decision(
            decision=original,
            cluster_id=sample_cluster.cluster_id,
            alert_fingerprints=[a.fingerprint for a in sample_cluster.alerts],
        )
        
        # Get replay context
        context = audit_logger.get_replay_context(original.decision_id)
        
        # Verify context has rules needed for replay
        assert context["rules_applied"] == original.rules_applied
        
        # Replay decision with same inputs
        replayed = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        # Core decision should match (deterministic rules)
        assert replayed.decision_state == original.decision_state
        assert replayed.rules_applied == original.rules_applied
    
    @pytest.mark.asyncio
    async def test_partial_replay_without_validation(
        self, audit_logger, decision_engine, sample_cluster, recovering_trends
    ):
        """Test replay context when validation hasn't occurred."""
        # Generate and log decision only
        decision = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        audit_logger.log_decision(
            decision=decision,
            cluster_id=sample_cluster.cluster_id,
            alert_fingerprints=[a.fingerprint for a in sample_cluster.alerts],
        )
        
        # Get replay context (no validation or embedding yet)
        context = audit_logger.get_replay_context(decision.decision_id)
        
        assert context is not None
        assert context["decision"] is not None
        assert context["validation"] is None
        assert context["embedding"] is None
        assert context["can_replay"] is True


# ============================================================================
# Constitution Principle Tests
# ============================================================================

class TestConstitutionCompliance:
    """Tests for Constitution compliance in replay."""
    
    @pytest.mark.asyncio
    async def test_all_rules_logged_for_replay(
        self, audit_logger, decision_engine, sample_cluster, recovering_trends
    ):
        """
        Constitution Principle IV: All rules must be logged for replay.
        """
        decision = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=[],
        )
        
        audit_logger.log_decision(
            decision=decision,
            cluster_id=sample_cluster.cluster_id,
            alert_fingerprints=[a.fingerprint for a in sample_cluster.alerts],
        )
        
        context = audit_logger.get_replay_context(decision.decision_id)
        
        # Verify rules are present for replay
        assert "rules_applied" in context
        assert len(context["rules_applied"]) > 0
    
    @pytest.mark.asyncio
    async def test_semantic_evidence_ids_logged(
        self, audit_logger, decision_engine, sample_cluster, recovering_trends
    ):
        """
        Test that semantic evidence IDs are logged for replay context.
        """
        from src.models.decision import SemanticEvidence
        
        evidence = [
            SemanticEvidence(
                decision_id=uuid4(),
                similarity_score=0.88,
                summary="Previous alert resolved automatically",
            ),
        ]
        
        decision = await decision_engine.decide(
            cluster=sample_cluster,
            trends=recovering_trends,
            semantic_evidence=evidence,
        )
        
        audit_logger.log_decision(
            decision=decision,
            cluster_id=sample_cluster.cluster_id,
            alert_fingerprints=[a.fingerprint for a in sample_cluster.alerts],
        )
        
        context = audit_logger.get_replay_context(decision.decision_id)
        
        # Verify semantic evidence IDs are present
        assert "semantic_evidence_ids" in context
        assert len(context["semantic_evidence_ids"]) == 1
