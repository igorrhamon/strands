
import pytest
from fastapi.testclient import TestClient
from server_fastapi import app
import os

client = TestClient(app)

def test_console_page_loads():
    """Test that the console page loads correctly."""
    response = client.get("/console")
    assert response.status_code == 200
    assert "Strands Operational Console" in response.text
    assert "Agent Execution Timeline" in response.text

def test_api_runs_endpoint():
    """Test the /api/runs endpoint."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_api_metrics_endpoint():
    """Test the /metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "strands_decision_confidence_score" in response.text

if __name__ == "__main__":
    # Set dummy env for testing
    os.environ["NEO4J_PASSWORD"] = "dummy"
    pytest.main([__file__])
