"""
Error Handling Utilities

Provides:
- Timeout decorators
- Retry logic with exponential backoff
- Fallback mechanisms
- Error classification
"""

import asyncio
import functools
import logging
from typing import Callable, Optional, TypeVar, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when an operation times out."""
    pass


class RetryExhaustedError(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


def with_timeout(
    timeout_seconds: float,
    fallback: Optional[Callable[[], T]] = None,
):
    """
    Decorator to add timeout to an async function.
    
    Args:
        timeout_seconds: Maximum execution time.
        fallback: Optional fallback function if timeout occurs.
    
    Returns:
        Decorated function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"[Timeout] {func.__name__} timed out after {timeout_seconds}s"
                )
                if fallback:
                    return fallback()
                raise TimeoutError(
                    f"{func.__name__} timed out after {timeout_seconds}s"
                )
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
):
    """
    Decorator to add retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts.
        initial_delay: Initial delay between retries (seconds).
        max_delay: Maximum delay between retries (seconds).
        exponential_base: Base for exponential backoff.
        retryable_exceptions: Tuple of exceptions to retry on.
    
    Returns:
        Decorated function.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = initial_delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        break
                    
                    logger.warning(
                        f"[Retry] {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed: {e}. Retrying in {delay:.1f}s"
                    )
                    
                    await asyncio.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise RetryExhaustedError(
                f"{func.__name__} failed after {max_attempts} attempts: {last_exception}"
            )
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.
    
    States:
    - CLOSED: Normal operation
    - OPEN: Failing, reject calls immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name for logging.
            failure_threshold: Number of failures before opening.
            recovery_timeout: Time before trying half-open (seconds).
            half_open_max_calls: Max calls in half-open state.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
    
    @property
    def state(self) -> str:
        """Get current state, checking for recovery timeout."""
        if self._state == self.OPEN and self._last_failure_time:
            elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
            if elapsed >= self.recovery_timeout:
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"[CircuitBreaker:{self.name}] Transitioning to HALF_OPEN")
        return self._state
    
    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == self.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = self.CLOSED
                self._failure_count = 0
                logger.info(f"[CircuitBreaker:{self.name}] Transitioning to CLOSED")
        else:
            self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.now(timezone.utc)
        
        if self.state == self.HALF_OPEN:
            self._state = self.OPEN
            logger.warning(f"[CircuitBreaker:{self.name}] Transitioning to OPEN (half-open failed)")
        elif self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                f"[CircuitBreaker:{self.name}] Transitioning to OPEN "
                f"(threshold reached: {self._failure_count})"
            )
    
    def __call__(
        self,
        func: Callable[..., T],
    ) -> Callable[..., T]:
        """
        Decorator to wrap a function with circuit breaker.
        
        Args:
            func: Function to wrap.
        
        Returns:
            Wrapped function.
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            if self.state == self.OPEN:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )
            
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        
        return wrapper


def classify_error(error: Exception) -> str:
    """
    Classify an error for appropriate handling.
    
    Args:
        error: Exception to classify.
    
    Returns:
        Error category string.
    """
    error_name = type(error).__name__.lower()
    error_msg = str(error).lower()
    
    # Network errors
    if any(x in error_name for x in ["connection", "network", "socket"]):
        return "network"
    if any(x in error_msg for x in ["connection refused", "network unreachable"]):
        return "network"
    
    # Timeout errors
    if "timeout" in error_name or "timeout" in error_msg:
        return "timeout"
    
    # Authentication errors
    if any(x in error_name for x in ["auth", "permission", "forbidden"]):
        return "auth"
    if any(x in error_msg for x in ["401", "403", "unauthorized"]):
        return "auth"
    
    # Validation errors
    if "validation" in error_name or "invalid" in error_msg:
        return "validation"
    
    # Rate limiting
    if "rate" in error_msg or "429" in error_msg:
        return "rate_limit"
    
    # Default
    return "unknown"


class ErrorContext:
    """
    Context manager for structured error handling.
    
    Usage:
        async with ErrorContext("operation_name") as ctx:
            result = await risky_operation()
        
        if ctx.failed:
            print(f"Error: {ctx.error}")
    """
    
    def __init__(
        self,
        operation_name: str,
        suppress: bool = False,
    ):
        self.operation_name = operation_name
        self.suppress = suppress
        self.error: Optional[Exception] = None
        self.error_category: Optional[str] = None
        self.failed = False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.failed = True
            self.error = exc_val
            self.error_category = classify_error(exc_val)
            
            logger.error(
                f"[ErrorContext:{self.operation_name}] "
                f"Category: {self.error_category}, Error: {exc_val}"
            )
            
            return self.suppress
        return False
