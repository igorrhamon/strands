"""
Unit tests for Alert Normalization flow.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock

from src.agents.collector.alert_collector import AlertCollector
from src.agents.collector.alert_normalizer import AlertNormalizer
from src.models.alert import Alert, AlertSource
from src.graph.neo4j_repo import Neo4jRepository

@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=Neo4jRepository)
    return repo

def test_collector_grafana_payload():
    """Test extracting fields from Grafana payload."""
    collector = AlertCollector()
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighCPU", "service": "payment", "severity": "critical"},
                "annotations": {"description": "CPU > 90%"},
                "startsAt": "2026-01-10T12:00:00Z",
                "fingerprint": "a1b2c3d4"
            }
        ]
    }
    
    result = collector.collect_from_grafana(payload)
    
    assert result["source"] == "GRAFANA"
    assert result["fingerprint"] == "a1b2c3d4"
    assert result["service"] == "payment"
    assert result["description"] == "CPU > 90%"


def test_normalizer_creates_alert_model(mock_repo):
    """Test that normalizer produces a valid Alert Pydantic model and calls repo."""
    normalizer = AlertNormalizer(mock_repo)
    
    raw_data = {
        "source": "GRAFANA",
        "fingerprint": "12345",
        "timestamp": "2026-01-10T12:00:00Z",
        "service": "checkout",
        "severity": "high",
        "description": "Slow response",
        "labels": {"region": "us-east-1"}
    }
    
    alert = normalizer.process(raw_data)
    
    assert isinstance(alert, Alert)
    assert alert.source == AlertSource.GRAFANA
    assert alert.fingerprint == "12345"
    assert alert.service == "checkout"
    
    # Verify Neo4j interaction
    mock_repo.connect.assert_called_once()
    mock_repo.create_alert.assert_called_once_with(alert)

def test_normalizer_handles_missing_data(mock_repo):
    """Test normalizer limits with unknowns."""
    normalizer = AlertNormalizer(mock_repo)
    
    raw_data = {
        "source": "SERVICENOW",
        "fingerprint": "INC001",
        # Missing timestamp, service, severity
        "description": "Something broke"
    }
    
    alert = normalizer.process(raw_data)
    
    assert alert.service == "unknown"
    assert alert.severity == "unknown"
    assert isinstance(alert.timestamp, datetime) # Should default to now
