"""Unit tests for Alert Normalizer Agent"""
import pytest
from datetime import datetime, UTC

from src.agents.alert_normalizer import AlertNormalizerAgent
from src.models.alert import Alert


def test_normalize_valid_alert():
    """Test normalization of a valid alert"""
    agent = AlertNormalizerAgent()
    
    alert = Alert(
        timestamp=datetime.now(UTC),
        fingerprint="abc123",
        service="api",
        severity="critical",
        description="CPU > 90%",
        labels={"environment": "prod"}
    )
    
    result = agent.normalize([alert])
    
    assert len(result) == 1
    norm_alert = result[0]
    assert norm_alert.validation_status.value == "VALID"
    assert norm_alert.service == "api"


def test_normalize_multiple_alerts():
    """Test normalization of multiple valid alerts"""
    agent = AlertNormalizerAgent()
    
    alert1 = Alert(
        timestamp=datetime.now(UTC),
        fingerprint="valid123",
        service="web",
        severity="warning",
        description="High latency",
        labels={"environment": "dev"}
    )
    
    alert2 = Alert(
        timestamp=datetime.now(UTC),
        fingerprint="valid456",
        service="db",
        severity="critical",
        description="Connection pool exhausted",
        labels={"environment": "prod"}
    )
    
    result = agent.normalize([alert1, alert2])
    
    assert len(result) == 2
    assert all(a.validation_status.value == "VALID" for a in result)

