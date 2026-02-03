from enum import Enum


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


class ConfidenceCauseType(Enum):
    """Enumeration for the types of causes for a confidence snapshot."""
    DECISION = "Decision"
    SYSTEM_EVENT = "SystemEvent"
    RETRY_DECISION = "RetryDecision"
    REPLAY_REPORT = "ReplayReport"
