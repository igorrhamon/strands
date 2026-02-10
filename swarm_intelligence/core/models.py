
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
import uuid
from datetime import datetime
from swarm_intelligence.policy.retry_policy import RetryPolicy
from .enums import EvidenceType, HumanAction, RiskLevel

# Forward declaration for type hinting
class DecisionContext: pass
class ConfidenceSnapshot: pass
class RetryAttempt: pass
class AgentExecution: pass
class Evidence: pass
@dataclass
class RetryDecision:
    """Represents a decision made by the RetryController about a failed execution."""
    step_id: str
    reason: str
    policy_name: str
    policy_version: str
    policy_logic_hash: str
    attempt_id: str
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class Evidence:
    """Represents a piece of evidence produced by an agent execution."""
    source_agent_execution_id: str
    agent_id: str
    content: Any
    confidence: float
    evidence_type: EvidenceType
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class AgentExecution:
    """Represents a single, auditable execution of an agent."""
    agent_id: str
    agent_version: str
    logic_hash: str
    step_id: str
    input_parameters: Dict[str, Any]
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    output_evidence: List[Evidence] = field(default_factory=list)
    error: Optional[Exception] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def is_successful(self) -> bool:
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
class DecisionContext:
    """Captures the context in which a decision was made. For replay and audit."""
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregation_strategy: str = "default_average"
    policy_versions: Dict[str, str] = field(default_factory=dict)
    replayable: bool = True

@dataclass
class Decision:
    """Represents a final decision made by the SwarmController."""
    summary: str
    action_proposed: str
    confidence: float
    supporting_evidence: List[Evidence]
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    human_decision: Optional['HumanDecision'] = None
    context: DecisionContext = field(default_factory=DecisionContext)

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

@dataclass
class ConfidenceSnapshot:
    """Records an immutable, point-in-time confidence value for an agent."""
    agent_id: str
    value: float
    source_event: str  # e.g., "time_decay", "human_override", "successful_outcome"
    sequence_id: int
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow) # For informational purposes only

@dataclass
class RetryAttempt:
    """Represents a single, auditable retry event."""
    step_id: str
    attempt_number: int
    delay_seconds: float
    reason: str
    failed_execution_id: str
    attempt_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class ReplayReport:
    """A persistable report detailing the outcome of a decision replay for audit."""
    original_decision_id: str
    replayed_decision_id: str
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    causal_divergences: List[str] = field(default_factory=list)
    confidence_delta: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RetryEvaluationResult:
    """A structured result from the SwarmRetryController."""
    steps_to_retry: List[SwarmStep] = field(default_factory=list)
    retry_attempts: List[RetryAttempt] = field(default_factory=list)
    retry_decisions: List[RetryDecision] = field(default_factory=list)
    max_delay_seconds: float = 0.0
    newly_successful_step_ids: Set[str] = field(default_factory=set)

@dataclass(frozen=True)
class Domain:
    """Represents a cognitive domain of operation."""
    id: str
    name: str
    description: str
    risk_level: RiskLevel

@dataclass
class SwarmRun:
    """Represents a single, complete execution of a swarm against a plan."""
    run_id: str
    domain: Domain
    plan: SwarmPlan
    master_seed: int
    executions: List[AgentExecution] = field(default_factory=list)
    final_decision: Optional[Decision] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
