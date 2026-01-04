"""
Grafana MCP Client - Alert Fetching

Interfaces with Grafana via MCP tools to retrieve alerts.
Uses the sgn-agendamen MCP server for Grafana access.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

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
    ):
        """
        Initialize Grafana MCP client.
        
        Args:
            datasource_uid: Optional datasource UID for filtering.
            default_lookback_minutes: Default time window for queries.
        """
        self._datasource_uid = datasource_uid
        self._default_lookback = default_lookback_minutes
        self._mcp_available = False
    
    def check_connection(self) -> bool:
        """
        Verify MCP connection is available.
        
        Returns:
            True if MCP tools are accessible.
        """
        # In real implementation, this would call MCP health check
        # For now, return True to allow testing
        self._mcp_available = True
        return self._mcp_available
    
    async def fetch_alerts(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity_filter: Optional[list[str]] = None,
        service_filter: Optional[str] = None,
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
            raw_alerts = await self._call_mcp_alerts(
                start_time=start_time,
                end_time=end_time,
                severity_filter=severity_filter,
                service_filter=service_filter,
            )
            
            # Convert to Alert objects
            return [self._parse_alert(raw) for raw in raw_alerts]
        
        except Exception as e:
            raise GrafanaClientError(f"Failed to fetch alerts: {e}") from e
    
    async def _call_mcp_alerts(
        self,
        start_time: datetime,
        end_time: datetime,
        severity_filter: Optional[list[str]] = None,
        service_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Internal method to call MCP tools.
        
        Returns raw alert dictionaries from MCP response.
        """
        # This would be implemented with actual MCP tool calls
        # Example: mcp_sgn-agendamen_get_alert_rules, etc.
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


async def fetch_active_alerts(
    lookback_minutes: int = 60,
    severity_filter: Optional[list[str]] = None,
) -> list[Alert]:
    """
    Convenience function to fetch active alerts.
    
    Args:
        lookback_minutes: Time window to query.
        severity_filter: Optional severity filter.
    
    Returns:
        List of active alerts.
    """
    client = GrafanaMCPClient(default_lookback_minutes=lookback_minutes)
    return await client.fetch_alerts(severity_filter=severity_filter)
