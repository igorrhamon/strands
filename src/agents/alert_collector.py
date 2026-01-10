"""Alert Collector Agent - fetches alerts from monitoring systems"""
from typing import List
import logging
from datetime import datetime, timedelta

from src.models.alert import Alert
from src.tools.grafana_client import GrafanaMCPClient
from src.models.audit import AuditLog, AuditEventType


logger = logging.getLogger(__name__)


class AlertCollectorAgent:
    """
    Agent responsible for collecting alerts from Grafana and other monitoring systems.
    
    Input: None (queries external systems)
    Output: List[Alert]
    Side Effects: Logs audit events
    """
    
    def __init__(self, grafana_client: GrafanaMCPClient):
        self.grafana_client = grafana_client
        self.agent_name = "AlertCollectorAgent"
    
    def collect_active_alerts(self) -> List[Alert]:
        """Collect currently firing alerts
        
        Returns:
            List of Alert objects from Grafana
        """
        logger.info("Collecting active alerts from Grafana")
        
        try:
            alerts = self.grafana_client.fetch_active_alerts()
            
            # Audit log for each alert collected
            for alert in alerts:
                AuditLog.create(
                    event_type=AuditEventType.ALERT_RECEIVED,
                    agent_name=self.agent_name,
                    entity_id=alert.id,
                    event_data={
                        "alert_name": alert.name,
                        "severity": alert.severity.value,
                        "state": alert.state.value,
                        "source": alert.source
                    }
                )
            
            logger.info(f"Collected {len(alerts)} active alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to collect alerts: {e}", exc_info=True)
            return []
    
    def collect_historical_alerts(
        self,
        lookback_hours: int = 24
    ) -> List[Alert]:
        """Collect historical alerts within a time window
        
        Args:
            lookback_hours: Hours to look back from now
            
        Returns:
            List of historical Alert objects
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=lookback_hours)
        
        logger.info(f"Collecting historical alerts from {start_time} to {end_time}")
        
        try:
            alerts = self.grafana_client.fetch_historical_alerts(start_time, end_time)
            
            logger.info(f"Collected {len(alerts)} historical alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to collect historical alerts: {e}", exc_info=True)
            return []
