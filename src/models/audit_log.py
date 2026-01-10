"""
AuditLog Model - Immutable Decision Record

Represents the complete audit trail for a decision.
Supports deterministic replay (Constitution Principle IV).
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.decision import Decision, HumanValidationStatus


class AuditLog(BaseModel):
    """
    Immutable record of the decision process.
    
    Constitution Principle IV: Append-only, no delete/overwrite.
    Supports replay to reproduce identical decisions.
    """
    
    log_id: UUID = Field(default_factory=uuid4, description="Unique log identifier")
    decision_id: UUID = Field(..., description="Link to the Decision")
    
    # Input context (for replay)
    alert_ids: list[str] = Field(..., description="Fingerprints of input alerts")
    cluster_id: UUID | None = Field(None, description="Cluster ID if grouped")
    metric_context: dict = Field(default_factory=dict, description="Summary of metrics used")
    
    # Semantic evidence IDs (for audit)
    semantic_evidence_ids: list[UUID] = Field(
        default_factory=list,
        description="IDs of similar decisions used as evidence"
    )
    
    # Decision output
    decision_output: Decision = Field(..., description="The final decision object")
    
    # Execution metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Execution time")
    agent_id: str = Field(..., description="ID of the agent instance")
    execution_duration_ms: int = Field(..., ge=0, description="Execution time in milliseconds")
    
    # Human validation
    human_validation_status: HumanValidationStatus = Field(
        default=HumanValidationStatus.PENDING,
        description="Current validation state"
    )
    
    # Embedding persistence tracking
    embedding_persisted: bool = Field(
        False,
        description="True if embedding was created (only after CONFIRMED)"
    )
    embedding_id: UUID | None = Field(None, description="ID of persisted embedding (if any)")
    
    class Config:
        frozen = True  # Immutable after creation
    
    def to_replay_context(self) -> dict:
        """
        Extract context needed for deterministic replay.
        
        Returns dict with all inputs needed to reproduce decision.
        """
        return {
            "alert_ids": self.alert_ids,
            "cluster_id": str(self.cluster_id) if self.cluster_id else None,
            "metric_context": self.metric_context,
            "semantic_evidence_ids": [str(eid) for eid in self.semantic_evidence_ids],
            "agent_id": self.agent_id,
        }
