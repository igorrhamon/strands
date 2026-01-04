"""
Unit Tests for Audit Logger

Tests:
- Append-only logging
- Event types (decision, validation, embedding)
- Replay context generation
"""

import pytest
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime
import tempfile

from src.models.decision import Decision, DecisionState, SemanticEvidence
from src.utils.audit_logger import AuditLogger, AuditLoggerError


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
def sample_decision():
    """Create a sample Decision for testing."""
    return Decision(
        decision_state=DecisionState.CLOSE,
        confidence=0.85,
        justification="All metrics recovering, auto-close recommended",
        rules_applied=["rule_recovery_detected", "rule_stable_metrics"],
        semantic_evidence=[
            SemanticEvidence(
                decision_id=uuid4(),
                similarity_score=0.90,
                summary="Previous similar alert was closed",
            ),
        ],
    )


# ============================================================================
# AuditLogger Tests
# ============================================================================

class TestAuditLogger:
    """Tests for AuditLogger."""
    
    def test_log_decision_creates_file(self, audit_logger, sample_decision):
        """Test that log_decision creates log file."""
        audit_log = audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001", "fp-002"],
        )
        
        assert audit_logger._log_path.exists()
        assert audit_log.decision_id == sample_decision.decision_id
    
    def test_log_decision_append_only(self, audit_logger, sample_decision):
        """Test that log_decision appends to file."""
        # Log first decision
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        # Create and log second decision
        decision2 = Decision(
            decision_state=DecisionState.ESCALATE,
            confidence=0.75,
            justification="Critical with degrading metrics",
            rules_applied=["rule_critical_degrading"],
        )
        
        audit_logger.log_decision(
            decision=decision2,
            cluster_id="cluster-002",
            alert_fingerprints=["fp-003"],
        )
        
        # Verify both are in file
        logs = audit_logger.read_all_logs()
        assert len(logs) == 2
        assert logs[0]["cluster_id"] == "cluster-001"
        assert logs[1]["cluster_id"] == "cluster-002"
    
    def test_log_decision_includes_semantic_evidence_ids(
        self, audit_logger, sample_decision
    ):
        """Test that semantic evidence IDs are logged."""
        audit_log = audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        logs = audit_logger.read_all_logs()
        assert len(logs[0]["semantic_evidence_ids"]) == 1
    
    def test_log_validation(self, audit_logger, sample_decision):
        """Test that validation events are logged."""
        # Log decision first
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        # Log validation
        audit_logger.log_validation(
            decision_id=sample_decision.decision_id,
            validated_by="user-123",
            approved=True,
        )
        
        logs = audit_logger.read_all_logs()
        assert len(logs) == 2
        assert logs[1]["event_type"] == "validation"
        assert logs[1]["approved"] is True
    
    def test_log_embedding_created(self, audit_logger, sample_decision):
        """Test that embedding creation is logged."""
        # Log decision
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        # Log embedding
        point_id = "qdrant-point-001"
        audit_logger.log_embedding_created(
            decision_id=sample_decision.decision_id,
            point_id=point_id,
        )
        
        logs = audit_logger.read_all_logs()
        assert len(logs) == 2
        assert logs[1]["event_type"] == "embedding_created"
        assert logs[1]["point_id"] == point_id
    
    def test_read_all_logs_empty_file(self, temp_log_dir):
        """Test read_all_logs with no logs."""
        logger = AuditLogger(log_dir=temp_log_dir)
        logs = logger.read_all_logs()
        assert logs == []
    
    def test_find_decision_logs(self, audit_logger, sample_decision):
        """Test finding logs for a specific decision."""
        # Log decision
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        # Log validation
        audit_logger.log_validation(
            decision_id=sample_decision.decision_id,
            validated_by="user-123",
            approved=True,
        )
        
        # Find logs
        logs = audit_logger.find_decision_logs(sample_decision.decision_id)
        assert len(logs) == 2
    
    def test_get_replay_context(self, audit_logger, sample_decision):
        """Test getting replay context for a decision."""
        # Log full lifecycle
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        audit_logger.log_validation(
            decision_id=sample_decision.decision_id,
            validated_by="user-123",
            approved=True,
        )
        
        audit_logger.log_embedding_created(
            decision_id=sample_decision.decision_id,
            point_id="qdrant-point-001",
        )
        
        # Get replay context
        context = audit_logger.get_replay_context(sample_decision.decision_id)
        
        assert context is not None
        assert context["can_replay"] is True
        assert context["decision"] is not None
        assert context["validation"] is not None
        assert context["embedding"] is not None
        assert context["rules_applied"] == sample_decision.rules_applied
    
    def test_get_replay_context_not_found(self, audit_logger):
        """Test replay context for non-existent decision."""
        context = audit_logger.get_replay_context(uuid4())
        assert context is None
    
    def test_clear_logs(self, audit_logger, sample_decision):
        """Test clearing logs."""
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        assert audit_logger._log_path.exists()
        
        audit_logger.clear_logs()
        
        assert not audit_logger._log_path.exists()


# ============================================================================
# JSONL Format Tests
# ============================================================================

class TestJSONLFormat:
    """Tests for JSONL format compliance."""
    
    def test_each_line_is_valid_json(self, audit_logger, sample_decision):
        """Test that each log line is valid JSON."""
        # Log multiple events
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        audit_logger.log_validation(
            decision_id=sample_decision.decision_id,
            validated_by="user-123",
            approved=True,
        )
        
        # Read raw file
        with open(audit_logger._log_path, "r") as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        
        for line in lines:
            # Should not raise
            parsed = json.loads(line)
            assert "event_type" in parsed
    
    def test_timestamps_are_iso_format(self, audit_logger, sample_decision):
        """Test that timestamps are in ISO format."""
        audit_logger.log_decision(
            decision=sample_decision,
            cluster_id="cluster-001",
            alert_fingerprints=["fp-001"],
        )
        
        logs = audit_logger.read_all_logs()
        timestamp = logs[0]["timestamp"]
        
        # Should parse as ISO datetime
        parsed = datetime.fromisoformat(timestamp)
        assert parsed is not None
