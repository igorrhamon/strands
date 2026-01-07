"""Alert Normalizer Agent - validates and normalizes alerts"""
from typing import List
import logging

from src.models.alert import Alert, NormalizedAlert, ValidationStatus


logger = logging.getLogger(__name__)


class AlertNormalizerAgent:
    """
    Agent responsible for normalizing and validating alerts.
    
    Input: List[Alert]
    Output: List[NormalizedAlert]
    Side Effects: Rejects malformed alerts, logs validation
    """
    
    def __init__(self):
        self.agent_name = "AlertNormalizerAgent"
    
    def normalize(self, alerts: List[Alert]) -> List[NormalizedAlert]:
        """Normalize and validate alerts
        
        Args:
            alerts: Raw alerts from collectors
            
        Returns:
            List of validated NormalizedAlert objects
        """
        logger.info(f"Normalizing {len(alerts)} alerts")
        
        normalized = []
        for alert in alerts:
            try:
                norm_alert = self._normalize_single(alert)
                
                # Reject if validation failed
                if norm_alert.validation_status == ValidationStatus.MALFORMED:
                    logger.warning(
                        f"Alert {alert.fingerprint} failed validation: {norm_alert.validation_errors}"
                    )
                    continue
                
                normalized.append(norm_alert)
                logger.debug(f"Normalized alert {alert.fingerprint} for service {alert.service}")
                
            except Exception as e:
                logger.error(f"Failed to normalize alert {alert.fingerprint}: {e}", exc_info=True)
                continue
        
        logger.info(f"Normalized {len(normalized)} / {len(alerts)} alerts")
        return normalized
    
    def _normalize_single(self, alert: Alert) -> NormalizedAlert:
        """Normalize a single alert with validation
        
        Args:
            alert: Raw alert
            
        Returns:
            NormalizedAlert with validation errors if any
        """
        validation_errors = []
        
        # Validate required fields
        if not alert.fingerprint:
            validation_errors.append("Missing fingerprint")
        
        if not alert.service:
            validation_errors.append("Missing service")
        
        if not alert.severity:
            validation_errors.append("Missing severity")
        elif alert.severity.lower() not in ["critical", "warning", "info", "low", "medium"]:
            validation_errors.append(f"Invalid severity: {alert.severity}")
        
        if not alert.description:
            validation_errors.append("Missing description")
        
        # Determine validation status
        validation_status = ValidationStatus.MALFORMED if validation_errors else ValidationStatus.VALID
        
        return NormalizedAlert(
            timestamp=alert.timestamp,
            fingerprint=alert.fingerprint,
            service=alert.service,
            severity=alert.severity,
            description=alert.description,
            labels=alert.labels,
            validation_status=validation_status,
            validation_errors=validation_errors if validation_errors else None
        )
