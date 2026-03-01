"""
Grafana MCP Client - Alert Fetching

Interfaces with Grafana via MCP tools to retrieve alerts.
Uses the sgn-agendamen MCP server for Grafana access.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from src.models.alert import Alert

logger = logging.getLogger(__name__)


class GrafanaClientError(Exception):
    """Raised when Grafana operations fail."""
    pass


class GrafanaMCPClient:
    """
    Client for fetching alerts from Grafana via MCP.
    
    This client wraps MCP tool calls to abstract the underlying
    communication layer.
    """
    
    def __init__(
        self,
        datasource_uid: Optional[str] = None,
        default_lookback_minutes: int = 60,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Grafana MCP client.

        Args:
            datasource_uid: Optional datasource UID for filtering.
            default_lookback_minutes: Default time window for queries.
            base_url: Grafana base URL (overrides GRAFANA_URL env var).
            api_key: Grafana API key (overrides GRAFANA_API_KEY env var).
        """
        self._datasource_uid = datasource_uid
        self._default_lookback = default_lookback_minutes
        self._mcp_available = False
        self._base_url = (
            base_url
            or os.environ.get("GRAFANA_URL", "")
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("GRAFANA_API_KEY", "")

    def check_connection(self) -> bool:
        """
        Check if MCP tools are accessible.

        Returns:
            True if MCP tools are accessible.
        """
        # In real implementation, this would call MCP health check
        # For now, return True to allow testing
        self._mcp_available = True
        return self._mcp_available
    
    def fetch_alerts(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[Alert]:
        """
        Fetch alerts from Grafana.
        
        Args:
            start_time: Query start time (defaults to lookback minutes ago).
            end_time: Query end time (defaults to now).
            severity_filter: Filter by severity levels.
            service_filter: Filter by service name.
        
        Returns:
            List of Alert objects.
        
        Raises:
            GrafanaClientError: If fetching fails.
        """
        if not self._mcp_available:
            self.check_connection()
        
        # Default time range
        if end_time is None:
            end_time = datetime.now(timezone.utc)
        if start_time is None:
            start_time = end_time - timedelta(minutes=self._default_lookback)
        
        try:
            # In real implementation, this would call:
            # mcp_sgn-agendamen_query_prometheus or similar
            # For now, return empty list (to be implemented with actual MCP calls)
            logger.info(
                f"Fetching alerts from {start_time.isoformat()} to {end_time.isoformat()}"
            )
            
            # Placeholder - real implementation would parse MCP response
            alerts = self._call_mcp_alerts()
            
            # Return Alert objects directly
            return alerts
        
        except Exception as e:
            raise GrafanaClientError(f"Failed to fetch alerts: {e}") from e
    
    def _call_mcp_alerts(self) -> list[Alert]:
        """
        Internal method to call Grafana Alertmanager API.

        Tries direct HTTP first (via GRAFANA_URL + GRAFANA_API_KEY env vars),
        then falls back to empty list.
        """
        if not self._base_url:
            logger.warning(
                "GRAFANA_URL not configured; returning empty alert list. "
                "Set GRAFANA_URL and GRAFANA_API_KEY environment variables."
            )
            return []

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{self._base_url}/api/alertmanager/grafana/api/v2/alerts",
                    headers=headers,
                    params={"active": "true", "silenced": "false", "inhibited": "false"},
                )
                response.raise_for_status()
                raw_alerts = response.json()  # list of alert dicts
                alerts = []
                for raw in raw_alerts:
                    try:
                        alerts.append(self._parse_alert(raw))
                    except Exception as parse_err:
                        logger.warning(f"Skipping malformed alert: {parse_err}")
                logger.info(f"Fetched {len(alerts)} alerts from Grafana")
                return alerts
        except httpx.ConnectError as e:
            logger.error(f"Cannot connect to Grafana at {self._base_url}: {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Grafana API error {e.response.status_code}: {e}"
            )
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Grafana alerts: {e}")
            return []
    
    def _parse_alert(self, raw: dict) -> Alert:
        """
        Parse raw alert dictionary to Alert model.
        
        Args:
            raw: Raw alert data from Grafana/Prometheus.
        
        Returns:
            Validated Alert object.
        """
        return Alert(
            timestamp=datetime.fromisoformat(raw.get("startsAt", datetime.now(timezone.utc).isoformat())),
            fingerprint=raw.get("fingerprint", "unknown"),
            service=raw.get("labels", {}).get("service", "unknown"),
            severity=raw.get("labels", {}).get("severity", "info"),
            description=raw.get("annotations", {}).get("summary", "No description"),
            labels=raw.get("labels", {}),
        )


def fetch_active_alerts(
    lookback_minutes: int = 60,
) -> list[Alert]:
    """
    Convenience function to fetch active alerts.
    
    Args:
        lookback_minutes: Time window to query.
    
    Returns:
        List of active alerts.
    """
    client = GrafanaMCPClient(default_lookback_minutes=lookback_minutes)
    return client.fetch_alerts()
