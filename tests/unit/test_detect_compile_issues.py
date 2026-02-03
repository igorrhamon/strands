import uuid
from datetime import datetime
import pytest

from types import SimpleNamespace
from pathlib import Path

import src.utils.audit_logger as audit_logger_mod
from src.utils.alert_normalizer import AlertNormalizer
from src.tools import embedding_client
from src.models.metrics import MetricsAnalysisResult


def make_dummy_decision():
    # Minimal object that mimics attributes read by AuditLogger.log_decision
    ns = SimpleNamespace()
    ns.decision_id = uuid.uuid4()
    ns.semantic_evidence = []
    ns.decision_state = SimpleNamespace(value="CLOSE")
    ns.confidence = 0.5
    ns.rules_applied = []
    ns.llm_contribution = False
    ns.llm_reason = None
    ns.human_validation_status = SimpleNamespace(value="MANUAL")
    ns.validated_by = None
    ns.validated_at = None
    ns.justification = "test"
    return ns


def test_audit_logger_log_decision_raises_validation_error():
    logger = audit_logger_mod.AuditLogger(log_dir=Path("/tmp"))
    dummy = make_dummy_decision()
    # The current implementation produces a pydantic ValidationError when
    # required audit fields are missing or have invalid types.
    with pytest.raises(Exception):
        logger.log_decision(dummy, cluster_id="cluster-001", alert_fingerprints=["fp-001"])


def test_alert_normalizer_timestamp_naive_is_coerced():
    # AlertNormalizer should now coerce naive datetimes to UTC (fixed)
    normalizer = AlertNormalizer()
    # Create an alert-like simple object with a naive datetime timestamp
    alert = SimpleNamespace(
        timestamp=datetime.utcnow(),  # naive datetime
        fingerprint="fp-1",
        service="svc",
        severity="critical",
        description="desc",
        source=SimpleNamespace(),
        labels={}
    )
    # Should not raise; instead should return None or empty errors (valid after coercion)
    errors = normalizer._validate(alert)
    assert errors is None or (isinstance(errors, list) and len(errors) == 0)


def test_embedding_client_missing_sentence_transformer_attribute():
    # The module is expected to expose SentenceTransformer; current codebase
    # lacks it and tests earlier surfaced AttributeError. Assert behavior.
    # The module should expose `SentenceTransformer` (shim). Attempting to
    # instantiate the shim without the external dependency should raise a
    # RuntimeError with a helpful message.
    assert hasattr(embedding_client, "SentenceTransformer")
    with pytest.raises(RuntimeError):
        embedding_client.SentenceTransformer("model-name")


def test_metrics_analysisresult_validation_error():
    # Construct MetricsAnalysisResult with missing/incorrect fields to reproduce
    # pydantic validation errors observed in CI.
    with pytest.raises(Exception):
        MetricsAnalysisResult(cluster_id="cluster-1", trends=[], overall_health=0, overall_confidence=0.5, query_latency_ms=10)


def test_embedding_persist_methods_unexpected_kw():
    # Some persist methods are called with 'cluster=' kw in tests and raise
    # TypeError due to signature mismatch. Reproduce by calling if available.
    try:
        from src.agents.embedding import EmbeddingAgent
        agent = EmbeddingAgent()
        with pytest.raises(TypeError):
            agent.persist_confirmed_decision(cluster=SimpleNamespace())
    except Exception:
        pytest.skip("EmbeddingAgent not present or cannot be instantiated in this environment")
