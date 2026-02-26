"""Retry policies for swarm execution with exponential backoff and context management."""

from pydantic import BaseModel
from typing import Optional, Dict, Any
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
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt using exponential backoff."""
        if attempt < 0:
            return 0.0
        
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if retry should be attempted."""
        if attempt >= self.max_retries:
            return False
        
        transient_errors = (ConnectionError, TimeoutError, OSError)
        return isinstance(error, transient_errors)


@dataclass
class RetryContext:
    """Context for tracking retry state during execution."""
    
    attempt: int = 0
    max_attempts: int = 3
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
