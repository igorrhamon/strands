
from abc import ABC, abstractmethod
import random
import time

class RetryPolicy(ABC):
    """Abstract base class for retry policies."""

    @abstractmethod
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determines if a retry should be attempted."""
        pass

    @abstractmethod
    def next_delay(self, attempt: int) -> float:
        """Calculates the delay before the next retry."""
        pass

class ExponentialBackoffRetryPolicy(RetryPolicy):
    """
    Implements an exponential backoff retry strategy with jitter.
    """
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Retries if the attempt is within the max_retries limit.
        In a real system, this could inspect the error to distinguish
        between transient and fatal errors.
        """
        return attempt < self.max_retries

    def next_delay(self, attempt: int) -> float:
        """
        Calculates the next delay using exponential backoff.
        Formula: min(max_delay, base_delay * 2 ** attempt) + random_jitter
        """
        delay = self.base_delay * (2 ** attempt)
        if self.jitter:
            delay = random.uniform(0, delay)

        return min(delay, self.max_delay)
