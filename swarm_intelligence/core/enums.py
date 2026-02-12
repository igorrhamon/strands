from enum import Enum

class EvidenceType(str, Enum):
    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"

class HumanAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    OVERRIDE = "override"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
