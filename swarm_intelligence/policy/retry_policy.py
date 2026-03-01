"""Retry policies for swarm execution with exponential backoff and context management."""

import hashlib
import json
import random as _random
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RetryPolicy(BaseModel):
    """Base retry policy configuration."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0


class ExponentialBackoffPolicy(RetryPolicy):
    """Exponential backoff retry policy for resilient execution."""

    # Allow mutation so that logic_hash reflects runtime changes
    model_config = ConfigDict(validate_assignment=True)

    # max_attempts is the canonical field; max_retries kept for backward compat
    max_attempts: int = 3
    use_jitter: bool = False
    version: str = "1.0"

    @property
    def logic_hash(self) -> str:
        """Deterministic SHA-256 fingerprint of key policy parameters.

        Recomputed on every access so mutations are immediately reflected.
        """
        params = {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
            "use_jitter": self.use_jitter,
            "version": self.version,
        }
        raw = json.dumps(params, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize policy configuration including logic_hash."""
        return {
            "max_attempts": self.max_attempts,
            "base_delay": self.base_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
            "use_jitter": self.use_jitter,
            "logic_hash": self.logic_hash,
            "policy_version": self.version,
        }

    def should_retry(self, ctx: "RetryContext") -> bool:  # type: ignore[override]
        """Determine whether to retry based on RetryContext.

        Returns False when:
        - ctx.attempt exceeds max_attempts
        - ctx.error has a truthy ``fatal`` attribute
        """
        if ctx.attempt > self.max_attempts:
            return False
        if ctx.error is not None and getattr(ctx.error, "fatal", False):
            return False
        return True

    def next_delay(self, ctx: "RetryContext") -> float:
        """Calculate next retry delay, optionally with seeded jitter."""
        attempt = max(0, ctx.attempt - 1)
        delay = self.base_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)
        if self.use_jitter:
            seed = ctx.random_seed if ctx.random_seed is not None else attempt
            rng = _random.Random(seed)
            delay = delay * rng.uniform(0.5, 1.5)
            delay = min(delay, self.max_delay)
        return delay

    def calculate_delay(self, attempt: int) -> float:
        """Legacy: calculate delay by attempt number (no context)."""
        if attempt < 0:
            return 0.0
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


class ImmediateRetryPolicy(RetryPolicy):
    """Retry policy with zero delay between attempts.

    Useful for fast, idempotent operations where immediate retry is
    preferred over exponential backoff (e.g., in-memory operations,
    lock acquisitions).
    """

    base_delay: float = 0.0
    max_delay: float = 0.0
    backoff_factor: float = 1.0
    max_attempts: int = 3

    @property
    def logic_hash(self) -> str:
        """Fingerprint for ImmediateRetryPolicy."""
        params = {
            "max_attempts": self.max_attempts,
            "base_delay": 0.0,
            "max_delay": 0.0,
            "backoff_factor": 1.0,
            "policy_type": "ImmediateRetryPolicy"
        }
        raw = json.dumps(params, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def calculate_delay(self, attempt: int) -> float:
        """Always returns 0.0 — retries are immediate."""
        return 0.0

    def should_retry(self, ctx: "RetryContext") -> bool:  # type: ignore[override]
        """Retry up to max_attempts regardless of error type."""
        return ctx.attempt <= self.max_attempts

    def next_delay(self, ctx: "RetryContext") -> float:
        """Always returns 0.0."""
        return 0.0


@dataclass
class RetryContext:
    """Context for tracking retry state during execution."""

    # Identifiers (required for production use; default to empty for legacy compat)
    run_id: str = ""
    step_id: str = ""
    agent_id: str = ""

    # Execution state
    attempt: int = 0
    max_attempts: int = 3
    error: Optional[Exception] = None
    random_seed: Optional[int] = None

    # Legacy fields kept for backward compatibility
    last_error: Optional[Exception] = None
    errors: list = field(default_factory=list)
    timestamps: Dict[str, datetime] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_attempt(self) -> None:
        """Record a retry attempt."""
        self.attempt += 1
        self.timestamps[f"attempt_{self.attempt}"] = datetime.utcnow()

    def record_error(self, error: Exception) -> None:
        """Record an error that occurred."""
        self.error = error
        self.last_error = error
        self.errors.append({
            "attempt": self.attempt,
            "error": str(error),
            "type": type(error).__name__,
            "timestamp": datetime.utcnow().isoformat()
        })

    def is_exhausted(self) -> bool:
        """Check if retry attempts are exhausted."""
        return self.attempt >= self.max_attempts

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of retry context."""
        return {
            "total_attempts": self.attempt,
            "max_attempts": self.max_attempts,
            "is_exhausted": self.is_exhausted(),
            "error_count": len(self.errors),
            "last_error": str(self.last_error) if self.last_error else None,
            "errors": self.errors,
            "metadata": self.metadata
        }
