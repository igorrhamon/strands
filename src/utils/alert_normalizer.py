"""
Alert Normalizer - Schema Validation Utility

Converts raw alerts from various sources into canonical NormalizedAlert format.
Validates required fields and marks malformed alerts accordingly.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from src.models.alert import Alert, NormalizedAlert, ValidationStatus

logger = logging.getLogger(__name__)


class AlertValidationError(Exception):
    """Raised when alert validation fails critically."""
    pass


class AlertNormalizer:
    """
    Normalizes and validates incoming alerts.
    
    Transforms raw Alert objects into NormalizedAlert with validation status.
    Malformed alerts are preserved but marked as MALFORMED.
    """
    
    # Required fields for valid alerts
    REQUIRED_FIELDS = {"fingerprint", "service", "severity", "description"}
    
    # Valid severity levels
    VALID_SEVERITIES = {"critical", "warning", "info"}
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize normalizer.
        
        Args:
            strict_mode: If True, raise on validation errors instead of marking MALFORMED.
        """
        self._strict_mode = strict_mode
    
    def normalize(self, alert: Alert) -> NormalizedAlert:
        """
        Normalize a single alert.
        
        Args:
            alert: Raw Alert object to normalize.
        
        Returns:
            NormalizedAlert with validation status.
        
        Raises:
            AlertValidationError: In strict mode, if validation fails.
        """
        errors = self._validate(alert)
        
        if errors and self._strict_mode:
            raise AlertValidationError(f"Validation failed: {errors}")
        
        status = ValidationStatus.VALID if not errors else ValidationStatus.MALFORMED
        
        return NormalizedAlert(
            timestamp=alert.timestamp,
            fingerprint=alert.fingerprint,
            service=self._normalize_service(alert.service),
            severity=self._normalize_severity(alert.severity),
            description=alert.description,
            labels=alert.labels,
            validation_status=status,
            validation_errors=errors if errors else None,
        )
    
    def normalize_batch(self, alerts: list[Alert]) -> list[NormalizedAlert]:
        """
        Normalize multiple alerts.
        
        Args:
            alerts: List of raw Alert objects.
        
        Returns:
            List of NormalizedAlert objects.
        """
        return [self.normalize(alert) for alert in alerts]
    
    def _validate(self, alert: Alert) -> Optional[list[str]]:
        """
        Validate alert fields.
        
        Returns:
            List of validation errors, or None if valid.
        """
        errors = []
        
        # Check required fields
        if not alert.fingerprint or not alert.fingerprint.strip():
            errors.append("Missing or empty fingerprint")
        
        if not alert.service or not alert.service.strip():
            errors.append("Missing or empty service")
        
        if not alert.description or not alert.description.strip():
            errors.append("Missing or empty description")
        
        # Validate severity
        if alert.severity.lower() not in self.VALID_SEVERITIES:
            errors.append(f"Invalid severity: {alert.severity}")
        
        # Validate timestamp
        if alert.timestamp > datetime.now(timezone.utc):
            errors.append("Timestamp is in the future")
        
        return errors if errors else None
    
    def _normalize_service(self, service: str) -> str:
        """Normalize service name to lowercase with hyphens."""
        return service.lower().replace("_", "-").strip()
    
    def _normalize_severity(self, severity: str) -> str:
        """Normalize severity to lowercase."""
        normalized = severity.lower().strip()
        return normalized if normalized in self.VALID_SEVERITIES else "info"


def normalize_alerts(alerts: list[Alert]) -> list[NormalizedAlert]:
    """
    Convenience function to normalize a batch of alerts.
    
    Args:
        alerts: List of raw alerts.
    
    Returns:
        List of normalized alerts.
    """
    normalizer = AlertNormalizer()
    return normalizer.normalize_batch(alerts)
