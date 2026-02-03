# Utils Package
"""
Cross-cutting utilities.

- alert_normalizer.py: Schema validation for alerts
- audit_logger.py: Immutable log writing
- error_handling.py: Timeouts and retries
"""

from src.utils.alert_normalizer import AlertNormalizer, normalize_alerts, AlertValidationError
from src.utils.audit_logger import AuditLogger, AuditLoggerError
from src.utils.error_handling import (
    with_timeout,
    with_retry,
    CircuitBreaker,
    TimeoutError,
    RetryExhaustedError,
    CircuitBreakerOpenError,
    classify_error,
    ErrorContext,
)

__all__ = [
    "AlertNormalizer",
    "normalize_alerts",
    "AlertValidationError",
    "AuditLogger",
    "AuditLoggerError",
    "with_timeout",
    "with_retry",
    "CircuitBreaker",
    "TimeoutError",
    "RetryExhaustedError",
    "CircuitBreakerOpenError",
    "classify_error",
    "ErrorContext",
]
