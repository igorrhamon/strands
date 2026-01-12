"""
Swarm Models - Output entities for Swarm Agents

Represents the standardized output from parallel analysis agents.
"""

from enum import Enum
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class EvidenceType(str, Enum):
    """Types of evidence collected by agents."""
    METRIC = "METRIC"
    LOG = "LOG"
    CODE = "CODE"
    TRACE = "TRACE"
    DOCUMENT = "DOCUMENT"

class EvidenceItem(BaseModel):
    """
    Supporting evidence for a hypothesis.
    """
    type: EvidenceType = Field(..., description="Type of evidence")
    description: str = Field(..., description="Human readable description")
    source_url: str = Field(..., description="Link to source (Grafana, GitHub, etc)")
    timestamp: datetime = Field(..., description="Time of evidence occurrence")
    
    class Config:
        frozen = True

class SwarmResult(BaseModel):
    """
    Standardized output from any analysis agent.
    
    FR-006: Each Swarm agent must return a standardized output object containing:
    Hypothesis, Evidence list, and Confidence Score.
    """
    agent_id: str = Field(..., description="Identifier of the agent producing this result")
    hypothesis: str = Field(..., description="Natural language explanation of findings")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="List of supporting evidence")
    suggested_actions: List[str] = Field(default_factory=list, description="Optional list of suggested actions")

    class Config:
        frozen = True
