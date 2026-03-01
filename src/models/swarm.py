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
    quantitative_value: Optional[float] = Field(None, description="Numerical value for correlation")
    qualitative_summary: Optional[str] = Field(None, description="Textual summary of the specific evidence")
    
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
    quantitative_metrics: dict[str, float] = Field(default_factory=dict, description="Consolidated quantitative metrics")
    qualitative_findings: List[str] = Field(default_factory=list, description="Consolidated qualitative findings")

    class Config:
        frozen = True
