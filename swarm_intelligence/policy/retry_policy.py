
from abc import ABC, abstractmethod
import random
from typing import Dict, Any

class RetryPolicy(ABC):
    """
    Abstract base class for serializable and versionable retry policies.
    This defines the contract for deciding if and when a step should be retried.
    """
    version: str = "1.0"

    @abstractmethod
    def should_retry(self, attempt: int, error: Exception = None) -> bool:
        """Determines if a retry should be attempted."""
        pass

    @abstractmethod
    def next_delay(self, attempt: int) -> float:
        """Calculates the delay before the next retry."""
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serializes the policy's configuration to a dictionary for persistence."""
        pass

class ExponentialBackoffPolicy(RetryPolicy):
    """
    Implements an exponential backoff retry strategy with jitter.
    This policy is serializable and versioned.
    """
    version = "1.1"

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        jitter: bool = True,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def should_retry(self, attempt: int, error: Exception = None) -> bool:
        """Retries if the attempt is within the max_attempts limit."""
        # Expert extension: In a real system, this could inspect the error
        # to differentiate between transient (e.g., network timeout) and
        # fatal errors (e.g., invalid credentials), returning False for fatal ones.
        return attempt < self.max_attempts

    def next_delay(self, attempt: int) -> float:
        """Calculates the next delay using exponential backoff."""
        delay = self.base_delay * (2 ** attempt)
        if self.jitter:
            delay += random.uniform(0, self.base_delay)

        return min(delay, self.max_delay)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the policy to a dictionary for persistence in Neo4j."""
        return {
            "policy_name": self.__class__.__name__,
            "policy_version": self.version,
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "jitter": self.jitter,
        }
