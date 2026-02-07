import pytest
from fastapi.testclient import TestClient
from server_fastapi import app
from unittest.mock import MagicMock, patch

client = TestClient(app)

@pytest.fixture
def mock_repo():
    with patch("server_fastapi.repo") as mock:
        yield mock

@pytest.fixture
def mock_human_review():
    with patch("server_fastapi.human_review") as mock:
        yield mock

def test_read_dashboard(mock_repo):
    mock_repo.get_pending_decisions.return_value = []
    response = client.get("/")
    assert response.status_code == 200
    assert "Strands Governance" in response.text

def test_get_pending_decisions(mock_repo):
    mock_repo.get_pending_decisions.return_value = [{"decision_id": "123"}]
    response = client.get("/api/decisions/pending")
    assert response.status_code == 200
    assert response.json() == [{"decision_id": "123"}]

def test_review_decision(mock_human_review):
    mock_human_review.review_decision.return_value = True
    review_data = {
        "decision_id": "123",
        "is_approved": True,
        "validated_by": "Human Operator",
        "feedback": "Looks good"
    }
    response = client.post("/api/decisions/review", json=review_data)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    mock_human_review.review_decision.assert_called_once_with(
        "123", True, "Human Operator", "Looks good"
    )

def test_simulate_alert():
    response = client.post("/simulate/alert?active=true")
    assert response.status_code == 200
    assert response.json()["status"] == "alert_active"
