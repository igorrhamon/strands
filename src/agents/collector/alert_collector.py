"""
Alert Collector Agent - Sense Agent

Responsibility: Ingest alerts from external systems (Grafana, ServiceNow)
and forward them to the Normalizer.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4

class AlertCollector:
    """
    Ingests raw alerts from supported sources.
    Uses the 'Sense' pattern: Input only, minimal processing.
    """
    
    def __init__(self):
        # No initialization needed - stateless collector
        pass

    def collect_from_grafana(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives raw webhook payload from Grafana Alertmanager.
        Extracts relevant fields for downstream processing.
        """
        # Grafana payload structure usually has a 'alerts' list
        # For this MVP, we ignore batching and assume single alert or take first
        alerts = payload.get("alerts", [])
        if not alerts:
            raise ValueError("No alerts found in Grafana payload")

        raw_alert = alerts[0]
        return {
            "source": "GRAFANA",
            "timestamp": raw_alert.get("startsAt", datetime.now(timezone.utc).isoformat()),
            "fingerprint": raw_alert.get("fingerprint", str(uuid4())),
            "service": raw_alert.get("labels", {}).get("service", "unknown-service"),
            "severity": raw_alert.get("labels", {}).get("severity", "unknown"),
            "description": raw_alert.get("annotations", {}).get("description", raw_alert.get("status", "")),
            "labels": raw_alert.get("labels", {}),
            "original_payload": raw_alert
        }

    def collect_from_servicenow(self, ticket_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives ticket data from ServiceNow.
        """
        return {
            "source": "SERVICENOW",
            "timestamp": ticket_payload.get("sys_created_on", datetime.now(timezone.utc).isoformat()),
            "fingerprint": ticket_payload.get("number", str(uuid4())),
            "service": ticket_payload.get("cmdb_ci", "unknown-ci"),
            "severity": ticket_payload.get("priority", "low"),  # Map 1=Critical later if needed
            "description": ticket_payload.get("short_description", "No description"),
            "labels": {
                "caller": ticket_payload.get("caller_id", ""),
                "category": ticket_payload.get("category", "")
            },
            "original_payload": ticket_payload
        }
