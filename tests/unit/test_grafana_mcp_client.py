"""
Unit tests for GrafanaMCPClient.fetch_alerts — direct HTTP mode.
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import httpx

from src.tools.grafana_mcp import GrafanaMCPClient

RAW_GRAFANA_ALERTS = [
    {
        "fingerprint": "fp-001",
        "startsAt": "2025-01-01T10:00:00Z",
        "labels": {"service": "payment", "severity": "critical"},
        "annotations": {"summary": "Payment service down"},
        "status": {"state": "active"},
    },
    {
        "fingerprint": "fp-002",
        "startsAt": "2025-01-01T10:05:00Z",
        "labels": {"service": "auth", "severity": "warning"},
        "annotations": {"summary": "High login failure rate"},
        "status": {"state": "active"},
    },
]


def _make_mock_client_ctx(json_data=None, status_code=200, raise_exc=None):
    mock_response = MagicMock()
    if raise_exc:
        mock_response.raise_for_status.side_effect = raise_exc
    else:
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = json_data or []
        mock_response.status_code = status_code

    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    mock_ctx.get.return_value = mock_response
    return mock_ctx


# ---------------------------------------------------------------------------
# With GRAFANA_URL configured
# ---------------------------------------------------------------------------

def test_fetch_alerts_returns_parsed_alerts():
    with patch("httpx.Client") as MockClient:
        MockClient.return_value = _make_mock_client_ctx(json_data=RAW_GRAFANA_ALERTS)
        client = GrafanaMCPClient(base_url="http://grafana:3000", api_key="token123")
        alerts = client.fetch_alerts()

    assert len(alerts) == 2
    fingerprints = {a.fingerprint for a in alerts}
    assert "fp-001" in fingerprints
    assert "fp-002" in fingerprints


def test_fetch_alerts_empty_when_no_base_url():
    client = GrafanaMCPClient()  # no base_url, no GRAFANA_URL env var
    assert client._base_url == ""
    alerts = client.fetch_alerts()
    assert alerts == []


def test_fetch_alerts_empty_on_connection_error():
    with patch("httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.side_effect = httpx.ConnectError("refused")
        MockClient.return_value = mock_ctx

        client = GrafanaMCPClient(base_url="http://grafana:3000")
        alerts = client.fetch_alerts()

    assert alerts == []


def test_fetch_alerts_skips_malformed_entries():
    """Malformed entries should be skipped without raising."""
    bad_alert = {"fingerprint": "bad", "startsAt": "not-a-date"}
    with patch("httpx.Client") as MockClient:
        MockClient.return_value = _make_mock_client_ctx(
            json_data=[RAW_GRAFANA_ALERTS[0], bad_alert]
        )
        # Patch _parse_alert to raise on the bad entry
        original_parse = GrafanaMCPClient._parse_alert

        def patched_parse(self, raw):
            if raw.get("fingerprint") == "bad":
                raise ValueError("bad date")
            return original_parse(self, raw)

        with patch.object(GrafanaMCPClient, "_parse_alert", patched_parse):
            client = GrafanaMCPClient(base_url="http://grafana:3000")
            alerts = client.fetch_alerts()

    assert len(alerts) == 1
    assert alerts[0].fingerprint == "fp-001"
