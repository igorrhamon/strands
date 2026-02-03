"""Audit logging models"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import hashlib
import json


class AuditEventType(str, Enum):
    """Types of auditable events"""
    ALERT_RECEIVED = "alert_received"
    ALERT_NORMALIZED = "alert_normalized"
    CLUSTER_CREATED = "cluster_created"
    METRICS_ANALYZED = "metrics_analyzed"
    DECISION_MADE = "decision_made"
    HUMAN_REVIEW = "human_review"
    OUTCOME_EVALUATED = "outcome_evaluated"
    GRAPH_UPDATED = "graph_updated"
    INVESTIGATION_STARTED = "investigation_started"


class AuditLog(BaseModel):
    """Immutable audit log entry"""
    log_id: str = Field(..., description="Unique log identifier")
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_name: str = Field(..., description="Agent that generated this log")
    entity_id: str = Field(..., description="ID of entity being audited (alert, decision, etc)")
    event_data: Dict[str, Any] = Field(..., description="Event-specific payload")
    checksum: str = Field(..., description="SHA256 checksum for tamper detection")
    previous_checksum: Optional[str] = Field(None, description="Chain to previous log")
    
    @staticmethod
    def compute_checksum(data: Dict[str, Any]) -> str:
        """Compute SHA256 checksum of event data"""
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    @classmethod
    def create(
        cls,
        event_type: AuditEventType,
        agent_name: str,
        entity_id: str,
        event_data: Dict[str, Any],
        previous_checksum: Optional[str] = None
    ) -> "AuditLog":
        """Factory method to create audit log with automatic checksum"""
        log_id = f"{event_type.value}_{entity_id}_{datetime.now(timezone.utc).timestamp()}"
        checksum = cls.compute_checksum({
            "event_type": event_type.value,
            "agent_name": agent_name,
            "entity_id": entity_id,
            "event_data": event_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return cls(
            log_id=log_id,
            event_type=event_type,
            agent_name=agent_name,
            entity_id=entity_id,
            event_data=event_data,
            checksum=checksum,
            previous_checksum=previous_checksum
        )


class RepositoryAssociation(BaseModel):
    """Association between alert/incident and repository context"""
    association_id: str
    entity_id: str = Field(..., description="Alert or cluster ID")
    repository: str = Field(..., description="Repository identifier")
    pr_numbers: List[int] = Field(default_factory=list)
    commit_shas: List[str] = Field(default_factory=list)
    related_issues: List[int] = Field(default_factory=list)
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
