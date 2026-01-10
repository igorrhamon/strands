"""
VectorEmbedding Model - Semantic Memory Entity

This model represents the numerical representation of alert/decision context
for RAG retrieval. Embeddings are ONLY persisted after human confirmation
(Constitution Principle III).

NO automatic learning. NO implicit persistence.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class VectorEmbedding(BaseModel):
    """
    Semantic memory entry stored in Qdrant.
    
    Constraint: Only created when a Decision is CONFIRMED by human.
    """
    
    vector_id: UUID = Field(default_factory=uuid4, description="Unique identifier for the embedding")
    source_decision_id: UUID = Field(..., description="ID of the human-confirmed decision this represents")
    embedding_vector: list[float] = Field(..., description="High-dimensional vector (384 dims for MiniLM)")
    source_text: str = Field(..., description="Text chunk used to generate embedding (alert + decision summary)")
    
    # Metadata for filtering
    service: str = Field(..., description="Service name from alert")
    severity: str = Field(..., description="Alert severity (critical/warning/info)")
    rules_applied: list[str] = Field(default_factory=list, description="Rules that contributed to decision")
    human_validator: Optional[str] = Field(None, description="ID of human who confirmed the decision")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of embedding creation")
    
    class Config:
        frozen = True  # Immutable after creation


class SimilarityResult(BaseModel):
    """
    Result from semantic similarity search.
    
    Used to provide historical context to DecisionEngine.
    """
    
    decision_id: UUID = Field(..., description="ID of the similar past decision")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score")
    source_text: str = Field(..., description="Original text that was matched")
    service: str = Field(..., description="Service from the matched decision")
    rules_applied: list[str] = Field(default_factory=list, description="Rules from the matched decision")
    
    class Config:
        frozen = True
