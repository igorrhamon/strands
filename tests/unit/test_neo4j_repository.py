"""
Unit tests for Neo4jRepository — create_incident_from_alert and save_swarm_hypothesis.

Uses pytest-mock to stub the neo4j Driver so no live Neo4j instance is needed.
"""
import pytest
from unittest.mock import MagicMock, patch
from src.graph.neo4j_repo import Neo4jRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo_with_driver(mock_session):
    """Return a Neo4jRepository whose internal driver returns *mock_session*."""
    repo = Neo4jRepository.__new__(Neo4jRepository)
    mock_driver = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    repo._driver = mock_driver
    return repo


# ---------------------------------------------------------------------------
# create_incident_from_alert
# ---------------------------------------------------------------------------

class TestCreateIncidentFromAlert:

    def test_creates_incident_and_returns_id(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": "inc-123"}
        mock_session.run.return_value = mock_result

        repo = _make_repo_with_driver(mock_session)
        incident_id = repo.create_incident_from_alert("fp-abc")

        assert incident_id == "inc-123"
        mock_session.run.assert_called_once()
        # The Cypher query must match on the given fingerprint
        call_args = mock_session.run.call_args
        assert "fp-abc" == call_args[0][1]["fingerprint"]

    def test_returns_none_when_alert_not_found(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        repo = _make_repo_with_driver(mock_session)
        result = repo.create_incident_from_alert("nonexistent-fp")

        assert result is None

    def test_incident_id_is_a_uuid(self):
        import re
        mock_session = MagicMock()
        captured = {}

        def capture_run(query, params):
            captured["params"] = params
            r = MagicMock()
            r.single.return_value = {"id": params["incident_id"]}
            return r

        mock_session.run.side_effect = capture_run

        repo = _make_repo_with_driver(mock_session)
        incident_id = repo.create_incident_from_alert("fp-xyz")

        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(incident_id)


# ---------------------------------------------------------------------------
# save_swarm_hypothesis
# ---------------------------------------------------------------------------

class TestSaveSwarmHypothesis:

    def test_saves_dict_result(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": "hyp-999"}
        mock_session.run.return_value = mock_result

        repo = _make_repo_with_driver(mock_session)
        swarm_result = {
            "summary": "CPU spike",
            "action_proposed": "restart pod",
            "confidence": 0.87,
            "risk_level": "HIGH",
        }
        hyp_id = repo.save_swarm_hypothesis("inc-123", swarm_result)

        assert hyp_id == "hyp-999"
        call_params = mock_session.run.call_args[0][1]
        assert call_params["summary"] == "CPU spike"
        assert call_params["confidence"] == pytest.approx(0.87)

    def test_saves_object_result(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"id": "hyp-001"}
        mock_session.run.return_value = mock_result

        repo = _make_repo_with_driver(mock_session)

        class FakeDecision:
            summary = "Memory leak"
            action_proposed = "scale up"
            confidence = 0.75
            risk_level = "MEDIUM"

        hyp_id = repo.save_swarm_hypothesis("inc-abc", FakeDecision())
        assert hyp_id == "hyp-001"

    def test_returns_none_when_incident_not_found(self):
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = None
        mock_session.run.return_value = mock_result

        repo = _make_repo_with_driver(mock_session)
        result = repo.save_swarm_hypothesis("ghost-inc", {})

        assert result is None
