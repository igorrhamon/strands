"""Grafana MCP client wrapper"""
import httpx
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

from src.config.settings import config
from src.models.alert import Alert


logger = logging.getLogger(__name__)


class GrafanaMCPClient:
    """Wrapper for Grafana MCP operations"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        # Prefer explicit argument, then config, then environment variable GRAFANA_URL
        self.base_url = base_url or config.mcp.grafana_url or os.getenv("GRAFANA_URL", "")
        self.timeout = timeout
        self.client = self._build_http_client(timeout)

    def _build_http_client(self, timeout: int) -> httpx.Client:
        """Construct an httpx.Client with the preferred auth method.

        Order: service-account token -> basic auth -> no-auth headers
        """
        headers = {}
        token = os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            return httpx.Client(timeout=timeout, headers=headers)

        user = os.getenv("GRAFANA_ADMIN_USER")
        pwd = os.getenv("GRAFANA_ADMIN_PASSWORD")
        if user and pwd:
            return httpx.Client(timeout=timeout, auth=(user, pwd))

        return httpx.Client(timeout=timeout, headers=headers)
    
    def fetch_active_alerts(self) -> List[Alert]:
        """Fetch currently firing alerts from Grafana
        
        Returns:
            List of Alert objects
            
        Raises:
            httpx.HTTPError: On connection or HTTP errors
        """
        try:
            resp = self.client.get(f"{self.base_url}/api/prometheus/grafana/api/v1/alerts")
            if resp.status_code == 404:
                logger.info("New API not found, falling back to /alerts/active")
                resp = self.client.get(f"{self.base_url}/alerts/active")

            # Authentication / redirect check
            if resp.status_code == 302 and "/login" in resp.headers.get("location", ""):
                raise httpx.HTTPStatusError(
                    "Redirect to login - Grafana requires authentication",
                    request=resp.request,
                    response=resp,
                )

            resp.raise_for_status()
            data = resp.json()

            alerts = self._extract_alerts_from_response(data)
            logger.info(f"Fetched {len(alerts)} active alerts from Grafana")
            return alerts
            
        except httpx.HTTPError as e:
            logger.error(f"Grafana MCP request failed: {e}")
            raise
    
    def fetch_historical_alerts(
        self, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[Alert]:
        """Fetch historical alerts within a time range
        
        Args:
            start_time: Start of time range
            end_time: End of time range (defaults to now)
            
        Returns:
            List of Alert objects
        """
        end_time = end_time or datetime.now(timezone.utc)
        
        try:
            response = self.client.get(
                f"{self.base_url}/alerts/historical",
                params={
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                }
            )
            response.raise_for_status()
            data = response.json()
            
            alerts = []
            for alert_data in data.get("alerts", []):
                try:
                    alert = self._parse_alert(alert_data)
                    alerts.append(alert)
                except Exception as e:
                    logger.error(f"Failed to parse historical alert: {e}")
                    continue
            
            logger.info(f"Fetched {len(alerts)} historical alerts from Grafana")
            return alerts
            
        except httpx.HTTPError as e:
            logger.error(f"Grafana historical query failed: {e}")
            raise
    
    def _parse_alert(self, data: Dict[str, Any]) -> Alert:
        """Parse raw Grafana alert data into Alert model"""
        ts = data.get("startsAt") or data.get("timestamp")
        if ts:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(timezone.utc)

        return Alert(
            timestamp=timestamp,
            fingerprint=data.get("fingerprint", ""),
            service=data.get("labels", {}).get("service", "unknown"),
            severity=(data.get("severity") or "warning").lower(),
            description=data.get("annotations", {}).get("summary", data.get("name", "Unknown")),
            labels=data.get("labels", {}),
        )

    def _extract_alerts_from_response(self, data: Dict[str, Any]) -> list[Alert]:
        """Extract alerts array from either Prometheus-style or legacy payloads."""
        alerts: list[Alert] = []
        if isinstance(data, dict) and "data" in data and "alerts" in data["data"]:
            alert_list = data["data"]["alerts"]
        else:
            alert_list = data.get("alerts", []) if isinstance(data, dict) else []

        for alert_data in alert_list:
            try:
                alerts.append(self._parse_alert(alert_data))
            except Exception as e:
                logger.error(f"Failed to parse alert: {e}", exc_info=True)
                continue

        return alerts
    
    def close(self) -> None:
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
