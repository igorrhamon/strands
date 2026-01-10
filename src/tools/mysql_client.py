"""MySQL MCP client (read-only queries for outcomes and logs)"""
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from src.config.settings import config


logger = logging.getLogger(__name__)


class MySQLMCPClient:
    """Wrapper for MySQL MCP operations (read-only)"""
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url or config.mcp.mysql_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def query_historical_outcomes(
        self,
        cluster_fingerprint: Optional[str] = None,
        since_days: int = 90
    ) -> List[Dict[str, Any]]:
        """Query historical decision outcomes
        
        Args:
            cluster_fingerprint: Specific cluster fingerprint to search
            since_days: Look back period in days
            
        Returns:
            List of outcome records
        """
        try:
            params = {"since_days": since_days}
            if cluster_fingerprint:
                params["fingerprint"] = cluster_fingerprint
            
            response = self.client.get(
                f"{self.base_url}/query/outcomes",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            outcomes = data.get("outcomes", [])
            logger.info(f"Queried {len(outcomes)} historical outcomes")
            return outcomes
            
        except httpx.HTTPError as e:
            logger.error(f"MySQL outcomes query failed: {e}")
            return []
    
    def query_application_logs(
        self,
        service: str,
        start_time: datetime,
        end_time: datetime,
        level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query application logs
        
        Args:
            service: Service name
            start_time: Start of time range
            end_time: End of time range
            level: Log level filter (e.g., "ERROR", "WARN")
            
        Returns:
            List of log entries
        """
        try:
            params = {
                "service": service,
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            }
            if level:
                params["level"] = level
            
            response = self.client.get(
                f"{self.base_url}/query/logs",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            logs = data.get("logs", [])
            logger.info(f"Queried {len(logs)} log entries for service {service}")
            return logs
            
        except httpx.HTTPError as e:
            logger.error(f"MySQL logs query failed: {e}")
            return []
    
    def close(self) -> None:
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
