from enum import Enum


class EvidenceType(str, Enum):
    # Core signal types
    LOG = "log"
    TRACE = "trace"
    METRIC = "metric"
    METRICS = "metric"

    # Common evidence categories used across adapters and examples
    DOCUMENT = "document"
    RAW_DATA = "raw"
    SEMANTIC = "semantic"
    HYPOTHESIS = "hypothesis"
    INFERENCE = "inference"
    RULES = "rules"

class HumanAction(str, Enum):
    APPROVE = "approve"
    ACCEPT = "accept"   # alias used in human-in-the-loop review flows
    REJECT = "reject"
    OVERRIDE = "override"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
