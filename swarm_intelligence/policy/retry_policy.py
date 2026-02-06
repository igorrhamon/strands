
from abc import ABC, abstractmethod
import random
import hashlib
from typing import Dict, Any, List
from dataclasses import dataclass, field
from swarm_intelligence.core.enums import EvidenceType

@dataclass
class RetryContext:
    """Encapsulates all data needed for a deterministic retry decision."""
    run_id: str
    step_id: str
    agent_id: str
    attempt: int
    error: Exception = None
    random_seed: int = 0
    domain_hints: List[str] = field(default_factory=list)
    last_confidence: float = 0.0
    evidence_type: EvidenceType = EvidenceType.RAW_DATA

class RetryPolicy(ABC):
    """
    Abstract base class for serializable and versionable retry policies.
    """
    version: str = "1.0"
    logic_hash: str = "undefined"

    @abstractmethod
    def should_retry(self, context: RetryContext) -> bool:
        """Determines if a retry should be attempted."""
        pass

    @abstractmethod
    def next_delay(self, context: RetryContext) -> float:
        """Calculates a deterministic delay before the next retry."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serializes the policy's configuration."""
        pass

class ExponentialBackoffPolicy(RetryPolicy):
    """
    Implements a deterministic exponential backoff strategy with seeded jitter.
    """
    version = "1.2"

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        use_jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.use_jitter = use_jitter

        # --- Logic Hash Calculation ---
        # A deterministic hash of the policy's core logic and parameters.
        # This is critical for auditing and replay.
        logic_str = f"{self.__class__.__name__}-{self.version}-{self.max_attempts}-{self.base_delay}-{self.max_delay}-{self.use_jitter}"
        self.logic_hash = hashlib.sha256(logic_str.encode('utf-8')).hexdigest()

    def should_retry(self, context: RetryContext) -> bool:
        """Retries if the attempt is within the max_attempts limit."""
        if isinstance(context.error, Exception):
            # Future-proofing: Allows agents to signal non-retryable errors.
            if getattr(context.error, 'fatal', False):
                return False
        return context.attempt <= self.max_attempts

    def next_delay(self, context: RetryContext) -> float:
        """Calculates the next delay deterministically using the context's seed."""
        delay = self.base_delay * (2 ** (context.attempt - 1))
        if self.use_jitter:
            # Seed the random generator to ensure determinism for replay
            seeded_random = random.Random(context.random_seed)
            delay += seeded_random.uniform(0, self.base_delay / 2)

        return min(delay, self.max_delay)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the policy for persistence."""
        return {
            "policy_name": self.__class__.__name__,
            "policy_version": self.version,
            "logic_hash": self.logic_hash,
            "parameters": {
                "max_attempts": self.max_attempts,
                "base_delay": self.base_delay,
                "max_delay": self.max_delay,
                "use_jitter": self.use_jitter,
            }
        }
