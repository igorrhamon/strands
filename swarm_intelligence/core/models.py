from typing import List, Dict, Any, Optional, Set
from swarm_intelligence.core.monitor_policy import MonitorPolicy
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from swarm_intelligence.policy.retry_policy import RetryPolicy
from .enums import EvidenceType, HumanAction, RiskLevel

from pydantic import BaseModel, Field
from swarm_intelligence.policy.retry_policy import RetryPolicy
from .enums import EvidenceType, HumanAction, RiskLevel

class RetryDecision(BaseModel):
    """Represents a decision made by the RetryController about a failed execution."""
    step_id: str
    reason: str
    policy_name: str
    policy_version: str
    policy_logic_hash: str
    attempt_id: str
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class Evidence(BaseModel):
    """Represents a piece of evidence produced by an agent execution."""
    source_agent_execution_id: str
    agent_id: str
    content: Any
    confidence: float
    evidence_type: EvidenceType
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class AgentExecution(BaseModel):
    """Represents a single, auditable execution of an agent."""
    agent_id: str
    agent_version: str
    logic_hash: str
    step_id: str
    input_parameters: Dict[str, Any]
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    output_evidence: List[Evidence] = Field(default_factory=list)
    error: Optional[str] = None # Changed to str for serialization
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def is_successful(self) -> bool:
        return self.error is None

class SwarmStep(BaseModel):
    """Defines a single step in a SwarmPlan."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    agent_id: str
    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mandatory: bool = True
    min_confidence: float = 0.7
    parameters: Dict[str, Any] = Field(default_factory=dict)
    retry_policy: Optional[RetryPolicy] = None

class SwarmPlan(BaseModel):
    """Defines the overall objective and steps for the swarm."""
    objective: str
    steps: List[SwarmStep]
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class DecisionContext(BaseModel):
    """Captures the context in which a decision was made. For replay and audit."""
    context_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    aggregation_strategy: str = "default_average"
    policy_versions: Dict[str, str] = Field(default_factory=dict)
    replayable: bool = True

class Decision(BaseModel):
    """Represents a final decision made by the SwarmController."""
    summary: str
    action_proposed: str
    confidence: float
    supporting_evidence: List[Evidence]
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    human_decision: Optional["HumanDecision"] = None
    context: DecisionContext = Field(default_factory=DecisionContext)
    monitor_policy: Optional[MonitorPolicy] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Alert(BaseModel):
    """Represents an incoming event that may trigger a swarm run."""
    alert_id: str
    data: Dict[str, Any] = Field(default_factory=dict)

class HumanDecision(BaseModel):
    """Represents a decision made by a human reviewer, potentially overriding the swarm."""
    action: HumanAction
    author: str
    override_reason: Optional[str] = None
    overridden_action_proposed: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    domain_expertise: str = "default_expert"
    human_decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class OperationalOutcome(BaseModel):
    """Represents the final, real-world outcome after an action is taken."""
    status: str  # e.g., "success", "partial_success", "failure"
    impact_level: str = "not_assessed"  # e.g., "low", "medium", "high"
    resolution_time_seconds: Optional[float] = None
    details: Optional[str] = None
    outcome_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class ConfidenceSnapshot(BaseModel):
    """Records an immutable, point-in-time confidence value for an agent."""
    agent_id: str
    value: float
    source_event: str  # e.g., "time_decay", "human_override", "successful_outcome"
    sequence_id: int
    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow) # For informational purposes only

class RetryAttempt(BaseModel):
    """Represents a single, auditable retry event."""
    step_id: str
    attempt_number: int
    delay_seconds: float
    reason: str
    failed_execution_id: str
    attempt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

class ReplayReport(BaseModel):
    """A persistable report detailing the outcome of a decision replay for audit."""
    original_decision_id: str
    replayed_decision_id: str
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    causal_divergences: List[str] = Field(default_factory=list)
    confidence_delta: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class RetryEvaluationResult(BaseModel):
    """A structured result from the SwarmRetryController."""
    steps_to_retry: List[SwarmStep] = Field(default_factory=list)
    retry_attempts: List[RetryAttempt] = Field(default_factory=list)
    retry_decisions: List[RetryDecision] = Field(default_factory=list)
    max_delay_seconds: float = 0.0
    newly_successful_step_ids: Set[str] = Field(default_factory=set)

class Domain(BaseModel):
    """Represents a cognitive domain of operation."""
    id: str
    name: str
    description: str
    risk_level: RiskLevel

class SwarmRun(BaseModel):
    """Represents a single, complete execution of a swarm against a plan."""
    run_id: str
    domain: Domain
    plan: SwarmPlan
    master_seed: int
    executions: List[AgentExecution] = Field(default_factory=list)
    final_decision: Optional[Decision] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
