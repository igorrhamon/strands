"""SwarmRetryController for managing retry logic in swarm execution."""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetryDecision:
    """Decision result from retry evaluation."""
    should_retry: bool
    delay_seconds: float
    reason: str
    attempt_number: int
    max_attempts: int


class SwarmRetryController:
    """Manages retry logic for swarm execution steps."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
        """Initialize retry controller.
        
        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._retry_history: Dict[str, list] = {}
    
    def evaluate(self, run_id: str, step_id: str, error: Exception) -> RetryDecision:
        """Evaluate whether a step should be retried.
        
        Args:
            run_id: Run identifier
            step_id: Step identifier
            error: Exception that occurred
        
        Returns:
            RetryDecision with retry recommendation
        """
        key = f"{run_id}:{step_id}"
        
        # Initialize history for this step if not present
        if key not in self._retry_history:
            self._retry_history[key] = []
        
        # Get current attempt count
        attempt_count = len(self._retry_history[key])
        
        # Record this attempt
        self._retry_history[key].append({
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(error),
            "error_type": type(error).__name__
        })
        
        # Determine if retry should happen
        should_retry = self._should_retry(attempt_count, error)
        
        # Calculate delay if retrying
        delay = self._calculate_delay(attempt_count) if should_retry else 0.0
        
        reason = self._get_retry_reason(attempt_count, error, should_retry)
        
        decision = RetryDecision(
            should_retry=should_retry,
            delay_seconds=delay,
            reason=reason,
            attempt_number=attempt_count + 1,
            max_attempts=self.max_retries
        )
        
        logger.debug(f"Retry evaluation for {key}: {decision}")
        
        return decision
    
    def _should_retry(self, attempt_count: int, error: Exception) -> bool:
        """Determine if retry should be attempted."""
        if attempt_count >= self.max_retries:
            return False
        
        # Retry on transient errors
        transient_errors = (
            ConnectionError,
            TimeoutError,
            OSError,
            RuntimeError,
        )
        
        return isinstance(error, transient_errors)
    
    def _calculate_delay(self, attempt_count: int) -> float:
        """Calculate delay using exponential backoff."""
        if attempt_count < 0:
            return 0.0
        
        delay = self.base_delay * (2 ** attempt_count)
        return min(delay, self.max_delay)
    
    def _get_retry_reason(self, attempt_count: int, error: Exception, should_retry: bool) -> str:
        """Get human-readable reason for retry decision."""
        if not should_retry:
            if attempt_count >= self.max_retries:
                return f"Max retries ({self.max_retries}) exhausted"
            else:
                return f"Non-transient error: {type(error).__name__}"
        
        return f"Transient error, retrying (attempt {attempt_count + 1}/{self.max_retries})"
    
    def get_retry_history(self, run_id: str, step_id: str) -> list:
        """Get retry history for a specific step."""
        key = f"{run_id}:{step_id}"
        return self._retry_history.get(key, [])
    
    def clear_history(self, run_id: str) -> None:
        """Clear retry history for a run."""
        keys_to_remove = [k for k in self._retry_history.keys() if k.startswith(f"{run_id}:")]
        for key in keys_to_remove:
            del self._retry_history[key]
        logger.debug(f"Cleared retry history for run {run_id}")
