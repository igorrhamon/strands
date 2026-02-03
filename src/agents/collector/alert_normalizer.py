"""
Alert Normalizer Agent - Sense Agent

Responsibility: Canonicalize raw alerts into the `Alert` model.
Integrates with Neo4j to persist the initial graph node.
"""

from typing import Dict, Any
from datetime import datetime, timezone

from src.models.alert import Alert, AlertSource
from src.graph.neo4j_repo import Neo4jRepository

class AlertNormalizer:
    """
    Normalizes raw dicts into immutable Alert objects and persists them.
    """
    
    def __init__(self, neo4j_repo: Neo4jRepository):
        self.repo = neo4j_repo

    def process(self, raw_data: Dict[str, Any]) -> Alert:
        """
        1. Validate/Transform raw data into Alert model.
        2. Persist to Graph.
        3. Return normalized Alert.
        """
        
        # 1. Normalization
        try:
            timestamp_str = raw_data.get("timestamp")
            if isinstance(timestamp_str, str):
                # Simple robust parsing, usually ISO8601
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(timezone.utc)

            alert = Alert(
                timestamp=timestamp,
                fingerprint=raw_data.get("fingerprint"),
                service=raw_data.get("service", "unknown"),
                severity=raw_data.get("severity", "unknown"),
                description=raw_data.get("description", "No description provided"),
                source=AlertSource(raw_data.get("source", "GRAFANA")),
                labels=raw_data.get("labels", {})
            )
        except Exception as e:
            # In a real system, we might push to a DLQ (Dead Letter Queue)
            raise ValueError(f"Failed to normalize alert: {e}") from e

        # 2. Persistence (Side Effect)
        # We assume connection is managed externally or lazy-loaded by repo
        try:
            self.repo.connect()
            self.repo.create_alert(alert)
        except Exception as e:
            # Log but don't fail processing? Spec says "Persist", so we should probably fail.
            raise RuntimeError(f"Failed to persist alert to Graph: {e}") from e

        return alert
