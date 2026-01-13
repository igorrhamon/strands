
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import uuid
from datetime import datetime
from swarm_intelligence.policy.retry_policy import RetryPolicy

class EvidenceType(Enum):
    """Enumeration for the types of evidence that can be produced."""
    RAW_DATA = "raw_data"
    METRICS = "metrics"
    SEMANTIC = "semantic"
    RULES = "rules"
    HYPOTHESIS = "hypothesis"
    HUMAN_VALIDATED = "human_validated"

class HumanAction(Enum):
    """Enumeration for the actions a human can take on a swarm's decision."""
    ACCEPT = "accept"
    REJECT = "reject"
    OVERRIDE = "override"

@dataclass
class SwarmResult:
    """Represents the output of a single agent execution."""
    agent_id: str
    output: Any
    confidence: float  # 0.0 to 1.0
    actionable: bool
    evidence_type: EvidenceType
    error: Optional[str] = None

    def is_successful(self) -> bool:
        """Returns True if the execution was successful."""
        return self.error is None

@dataclass
class SwarmStep:
    """Defines a single step in a SwarmPlan."""
    agent_id: str
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mandatory: bool = True
    min_confidence: float = 0.7
    parameters: Dict[str, Any] = field(default_factory=dict)
    retry_policy: Optional[RetryPolicy] = None

@dataclass
class SwarmPlan:
    """Defines the overall objective and steps for the swarm."""
    objective: str
    steps: List[SwarmStep]
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class Decision:
    """Represents a final decision made by the SwarmController."""
    summary: str
    action_proposed: str
    confidence: float
    supporting_evidence: List[SwarmResult]
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    human_decision: Optional['HumanDecision'] = None

@dataclass
class Alert:
    """Represents an incoming event that may trigger a swarm run."""
    alert_id: str
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HumanDecision:
    """Represents a decision made by a human reviewer, potentially overriding the swarm."""
    action: HumanAction
    author: str
    override_reason: Optional[str] = None
    overridden_action_proposed: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    domain_expertise: str = "default_expert"
    human_decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class OperationalOutcome:
    """Represents the final, real-world outcome after an action is taken."""
    status: str  # e.g., "success", "partial_success", "failure"
    impact_level: str = "not_assessed"  # e.g., "low", "medium", "high"
    resolution_time_seconds: Optional[float] = None
    details: Optional[str] = None
    outcome_id: str = field(default_factory=lambda: str(uuid.uuid4()))
