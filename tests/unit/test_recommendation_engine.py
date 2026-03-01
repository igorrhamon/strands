"""
Unit tests for RecommendationEngine — including duration and multi-service rules.
"""
import pytest
from src.agents.grafana_alert_analysis.recommender import RecommendationEngine


def _engine():
    return RecommendationEngine()


# ---------------------------------------------------------------------------
# Existing rules (regression)
# ---------------------------------------------------------------------------

def test_high_recurrence_low_severity_returns_close():
    result = _engine().recommend([
        {"cluster_id": "c1", "severity": "low", "service": "svc", "count": 10}
    ])
    assert result[0].recommended_action == "CLOSE"
    assert result[0].confidence >= 0.7


def test_critical_severity_returns_escalate():
    result = _engine().recommend([
        {"cluster_id": "c2", "severity": "CRITICAL", "service": "db", "count": 1}
    ])
    assert result[0].recommended_action == "ESCALATE"
    assert result[0].confidence >= 0.85


def test_unknown_pattern_returns_observe():
    result = _engine().recommend([
        {"cluster_id": "c3", "severity": "info", "service": "svc", "count": 2}
    ])
    assert result[0].recommended_action == "OBSERVE"


# ---------------------------------------------------------------------------
# Duration rule (new)
# ---------------------------------------------------------------------------

def test_short_duration_alert_returns_close():
    cluster = {
        "cluster_id": "c-dur",
        "severity": "warning",
        "service": "api",
        "count": 1,
        "starts_at": "2025-01-01T10:00:00+00:00",
        "ends_at": "2025-01-01T10:02:30+00:00",  # 2.5 minutes
    }
    result = _engine().recommend([cluster])
    assert result[0].recommended_action == "CLOSE"
    assert "transient" in result[0].root_cause_hypothesis.lower() or "2.5" in result[0].root_cause_hypothesis


def test_longer_duration_alert_not_auto_closed_by_duration_rule():
    cluster = {
        "cluster_id": "c-long",
        "severity": "warning",
        "service": "api",
        "count": 1,
        "starts_at": "2025-01-01T10:00:00+00:00",
        "ends_at": "2025-01-01T10:10:00+00:00",  # 10 minutes
    }
    result = _engine().recommend([cluster])
    # Not short → should not be CLOSE via duration rule
    assert result[0].recommended_action != "CLOSE"


def test_z_suffixed_timestamps_parse_correctly():
    cluster = {
        "cluster_id": "c-z",
        "severity": "info",
        "service": "api",
        "count": 1,
        "starts_at": "2025-01-01T10:00:00Z",
        "ends_at": "2025-01-01T10:01:00Z",  # 1 minute
    }
    # Should not raise; duration < 5 min → CLOSE
    result = _engine().recommend([cluster])
    assert result[0].recommended_action == "CLOSE"


def test_malformed_timestamps_do_not_raise():
    cluster = {
        "cluster_id": "c-bad",
        "severity": "info",
        "service": "api",
        "count": 1,
        "starts_at": "not-a-date",
        "ends_at": "also-not-a-date",
    }
    result = _engine().recommend([cluster])
    # Should fall through to default OBSERVE without raising
    assert result[0].recommended_action == "OBSERVE"


# ---------------------------------------------------------------------------
# Multi-service rule (new)
# ---------------------------------------------------------------------------

def test_many_services_returns_escalate():
    cluster = {
        "cluster_id": "c-multi",
        "severity": "warning",
        "service": "svc-a",
        "services": ["svc-a", "svc-b", "svc-c", "svc-d"],
        "count": 2,
    }
    result = _engine().recommend([cluster])
    assert result[0].recommended_action == "ESCALATE"
    assert result[0].confidence >= 0.8


def test_few_services_does_not_trigger_multi_rule():
    cluster = {
        "cluster_id": "c-few",
        "severity": "warning",
        "service": "svc-a",
        "services": ["svc-a", "svc-b"],
        "count": 2,
    }
    result = _engine().recommend([cluster])
    # Two services is fine; should not escalate on this rule alone
    assert result[0].recommended_action == "OBSERVE"


# ---------------------------------------------------------------------------
# Services field population
# ---------------------------------------------------------------------------

def test_services_field_populated_from_services_list():
    cluster = {
        "cluster_id": "c-srv",
        "severity": "info",
        "service": "ignored",
        "services": ["a", "b"],
        "count": 1,
    }
    result = _engine().recommend([cluster])
    assert result[0].services == ["a", "b"]


def test_services_field_populated_from_service_when_no_list():
    cluster = {
        "cluster_id": "c-single",
        "severity": "info",
        "service": "my-svc",
        "count": 1,
    }
    result = _engine().recommend([cluster])
    assert "my-svc" in result[0].services
