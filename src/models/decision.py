"""
Decision Model - Structured Recommendation Output

Represents the output from the DecisionEngine.
All decisions require human validation before action.
"""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class DecisionState(str, Enum):
    """Possible decision recommendations."""
    CLOSE = "CLOSE"
    OBSERVE = "OBSERVE"
    ESCALATE = "ESCALATE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class HumanValidationStatus(str, Enum):
    """Human validation status for decisions."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class SemanticEvidence(BaseModel):
    """Evidence from semantic similarity search."""
    decision_id: UUID = Field(..., description="ID of similar past decision")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity")
    summary: str = Field(..., description="Brief summary of the past decision")
    
    class Config:
        frozen = True


class Decision(BaseModel):
    """
    Structured output from DecisionEngine.
    
    Constitution Principle I: This is a RECOMMENDATION only.
    No automatic action is executed without human validation.
    """
    
    decision_id: UUID = Field(default_factory=uuid4, description="Unique decision identifier")
    decision_state: DecisionState = Field(..., description="Recommended action")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    justification: str = Field(..., description="Human-readable explanation")
    rules_applied: list[str] = Field(default_factory=list, description="Deterministic rules that fired")
    
    # Semantic evidence (Constitution Principle III)
    semantic_evidence: list[SemanticEvidence] = Field(
        default_factory=list,
        description="Similar past decisions used as evidence"
    )
    
    # LLM tracking (Constitution Principle II)
    llm_contribution: bool = Field(False, description="True if LLM was invoked")
    llm_reason: str | None = Field(None, description="Why LLM was invoked (if applicable)")
    
    # Validation status
    human_validation_status: HumanValidationStatus = Field(
        default=HumanValidationStatus.PENDING,
        description="Human validation state"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Decision creation time")
    validated_at: datetime | None = Field(None, description="Human validation timestamp")
    validated_by: str | None = Field(None, description="Human validator ID")
    
    class Config:
        frozen = False  # Mutable for validation status updates
    
    def confirm(self, validator_id: str) -> "Decision":
        """Mark decision as confirmed by human."""
        self.human_validation_status = HumanValidationStatus.CONFIRMED
        self.validated_at = datetime.now(timezone.utc)
        self.validated_by = validator_id
        return self
    
    def reject(self, validator_id: str) -> "Decision":
        """Mark decision as rejected by human."""
        self.human_validation_status = HumanValidationStatus.REJECTED
        self.validated_at = datetime.now(timezone.utc)
        self.validated_by = validator_id
        return self
    
    @property
    def is_confirmed(self) -> bool:
        """Check if decision is confirmed (for embedding persistence)."""
        return self.human_validation_status == HumanValidationStatus.CONFIRMED


class DecisionValidation(BaseModel):
    """Result of a human review/validation of a Decision."""
    validation_id: str
    decision_id: UUID
    validated_by: str
    is_approved: bool
    feedback: str | None = None
    corrected_decision: DecisionState | None = None
    validated_at: datetime | None = None

    class Config:
        frozen = False


###############################################################################
#             NEW MODELS FOR DIAGNOSTIC SWARM ARCHITECTURE
###############################################################################

class DecisionStatus(str, Enum):
    """Lifecycle status of a DecisionCandidate."""
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class AutomationLevel(str, Enum):
    """Permitted level of automation for the decision."""
    FULL = "FULL"
    ASSISTED = "ASSISTED"
    MANUAL = "MANUAL"


class DecisionCandidate(BaseModel):
    """
    Consolidated hypothesis and plan awaiting approval.
    """
    decision_id: UUID = Field(default_factory=uuid4, description="Unique decision candidate identifier")
    alert_reference: str = Field(..., description="Fingerprint of the alert being addressed")
    summary: str = Field(..., description="High level summary of the decision")
    status: DecisionStatus = Field(default=DecisionStatus.PROPOSED, description="Current lifecycle status")
    
    primary_hypothesis: str = Field(..., description="The winning hypothesis from Swarm")
    risk_assessment: str = Field(..., description="Risk analysis of the proposed action")
    automation_level: AutomationLevel = Field(..., description="Suggested automation level")
    
    # Links to analysis
    supporting_evidence: list[str] = Field(default_factory=list, description="IDs or summaries of supporting evidence")
    conflicting_hypotheses: list[str] = Field(default_factory=list, description="Summaries of rejected hypotheses")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        frozen = False

