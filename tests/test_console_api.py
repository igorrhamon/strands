import pytest
from fastapi.testclient import TestClient
from server_fastapi import app, swarm_coordinator
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator
from unittest.mock import MagicMock

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_coordinator():
    exec_ctrl = MagicMock()
    retry_ctrl = MagicMock()
    decision_ctrl = MagicMock()
    conf_svc = MagicMock()
    return SwarmRunCoordinator(exec_ctrl, retry_ctrl, decision_ctrl, conf_svc)

def test_console_endpoints(client, mock_coordinator):
    # Inject mock coordinator into app
    import server_fastapi
    server_fastapi.swarm_coordinator = mock_coordinator
    
    # Create a fake run
    run_id = "test_run_123"
    mock_coordinator._execution_history[run_id] = {
        "run_id": run_id,
        "status": "FINISHED",
        "agents": [{"name": "TestAgent", "status": "SUCCESS"}]
    }
    
    # Test /api/runs
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["run_id"] == run_id
    
    # Test /api/runs/{id}
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    assert response.json()["run_id"] == run_id
    
    # Test /api/runs/{id}/agents
    response = client.get(f"/api/runs/{run_id}/agents")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "TestAgent"
