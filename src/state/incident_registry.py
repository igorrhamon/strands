"""
Incident Registry - Stores snapshots of incident contexts for historical analysis.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class IncidentSnapshot(BaseModel):
    """
    Point-in-time snapshot of an incident.
    """
    snapshot_id: UUID = Field(default_factory=uuid4)
    incident_id: str # alert fingerprint or cluster id
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    severity: str
    description: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    findings: List[str] = Field(default_factory=list)
    decision_state: str
    confidence: float
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_fingerprint_text(self) -> str:
        """
        Generates a textual representation for embedding.
        """
        metrics_str = ", ".join([f"{k}: {v}" for k, v in self.metrics.items()])
        findings_str = " | ".join(self.findings)
        return f"Service: {self.service}. Severity: {self.severity}. Description: {self.description}. Metrics: {metrics_str}. Findings: {findings_str}"

class IncidentRegistry:
    """
    In-memory registry for incident snapshots (should be backed by Neo4j/DB in prod).
    """
    def __init__(self):
        self._snapshots: Dict[str, List[IncidentSnapshot]] = {}

    def register_snapshot(self, snapshot: IncidentSnapshot):
        if snapshot.incident_id not in self._snapshots:
            self._snapshots[snapshot.incident_id] = []
        self._snapshots[snapshot.incident_id].append(snapshot)
        logger.info(f"Registered snapshot {snapshot.snapshot_id} for incident {snapshot.incident_id}")

    def get_history(self, incident_id: str) -> List[IncidentSnapshot]:
        return self._snapshots.get(incident_id, [])

    def get_all_snapshots(self) -> List[IncidentSnapshot]:
        all_snaps = []
        for snaps in self._snapshots.values():
            all_snaps.extend(snaps)
        return all_snaps
