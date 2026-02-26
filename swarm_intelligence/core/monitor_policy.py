from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum

class EscalationAction(str, Enum):
    NOTIFY = "notify"
    RAISE_RISK = "raise_risk"
    FORCE_ACTION = "force_action"
    HUMAN_INTERVENTION = "human_intervention"

class MonitorPolicy(BaseModel):
    """
    Defines how a MONITOR decision should behave over time.
    """
    recheck_after_minutes: int = Field(default=5, description="Interval between re-evaluations")
    max_rechecks: int = Field(default=3, description="Maximum number of automatic re-evaluations")
    escalation_action: EscalationAction = Field(default=EscalationAction.HUMAN_INTERVENTION)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MonitorState(BaseModel):
    """
    Tracks the current state of a monitored incident.
    """
    run_id: str
    original_alert_id: str
    recheck_count: int = 0
    last_recheck_timestamp: Optional[float] = None
    is_active: bool = True
