from enum import Enum


class ConfidenceCauseType(Enum):
    """Enumeration for the types of causes for a confidence snapshot."""
    DECISION = "Decision"
    SYSTEM_EVENT = "SystemEvent"
    RETRY_DECISION = "RetryDecision"
    REPLAY_REPORT = "ReplayReport"
