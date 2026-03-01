"""
Unit tests for PrometheusClient.query_instant — direct HTTP mode.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx

from src.tools.prometheus_queries import PrometheusClient, PrometheusQueryError


INSTANT_RESPONSE = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [
            {"metric": {"job": "node"}, "value": [1700000000, "0.42"]},
        ],
    },
}


# ---------------------------------------------------------------------------
# With base_url (direct HTTP mode)
# ---------------------------------------------------------------------------

def test_query_instant_http_returns_datapoints():
    """query_instant should use httpx.Client when base_url is set."""
    mock_response = MagicMock()
    mock_response.json.return_value = INSTANT_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.return_value = mock_response
        MockClient.return_value = mock_ctx

        client = PrometheusClient(base_url="http://prometheus:9090")
        ts = datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc)
        points = client.query_instant("up", time=ts)

    assert len(points) == 1
    assert abs(points[0].value - 0.42) < 1e-9


def test_query_instant_http_passes_correct_params():
    """Verify that the PromQL expression and timestamp are forwarded."""
    mock_response = MagicMock()
    mock_response.json.return_value = INSTANT_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.return_value = mock_response
        MockClient.return_value = mock_ctx

        client = PrometheusClient(base_url="http://prometheus:9090")
        ts = datetime(2023, 11, 14, 0, 0, 0, tzinfo=timezone.utc)
        client.query_instant("rate(http_requests_total[5m])", time=ts)

        call_kwargs = mock_ctx.get.call_args
        assert call_kwargs[0][0] == "/api/v1/query"
        params = call_kwargs[1]["params"]
        assert params["query"] == "rate(http_requests_total[5m])"
        assert params["time"] == int(ts.timestamp())


# ---------------------------------------------------------------------------
# Without base_url (MCP fallback mode)
# ---------------------------------------------------------------------------

def test_query_instant_mcp_fallback_returns_empty():
    """Without base_url, _call_mcp_query returns empty result."""
    client = PrometheusClient()  # no base_url
    points = client.query_instant("up")
    assert points == []


def test_query_instant_404_returns_empty():
    """A 404 from Prometheus should return an empty list (metric not found)."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Not Found",
        request=MagicMock(),
        response=MagicMock(status_code=404),
    )

    with patch("httpx.Client") as MockClient:
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_ctx)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_ctx.get.return_value = mock_response
        MockClient.return_value = mock_ctx

        client = PrometheusClient(base_url="http://prometheus:9090")
        points = client.query_instant("nonexistent_metric")

    assert points == []
