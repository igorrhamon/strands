import pytest
from src.state.incident_registry import IncidentRegistry, IncidentSnapshot
from src.state.similarity_index import SimilarityIndex
from uuid import uuid4

def test_incident_registry_storage():
    registry = IncidentRegistry()
    snapshot = IncidentSnapshot(
        incident_id="test-123",
        service="checkout",
        severity="critical",
        description="DB error",
        decision_state="ESCALATE",
        confidence=0.9
    )

    registry.register_snapshot(snapshot)
    history = registry.get_history("test-123")

    assert len(history) == 1
    assert history[0].service == "checkout"

@pytest.mark.skip(reason="Requires sentence-transformers and numpy")
def test_similarity_index_retrieval():
    idx = SimilarityIndex()
    registry = IncidentRegistry()

    snap1 = IncidentSnapshot(
        incident_id="inc-1",
        service="payment",
        severity="critical",
        description="Payment timeout",
        decision_state="ESCALATE",
        confidence=0.95,
        findings=["Timeout in gateway"]
    )

    idx.add_snapshot(snap1)

    # Query similar to payment timeout
    results = idx.find_similar("Payment gateway is timing out", threshold=0.5)

    assert len(results) > 0
    assert results[0]["snapshot"].incident_id == "inc-1"
    assert results[0]["similarity"] > 0.5
