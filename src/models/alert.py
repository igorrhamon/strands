"""
Alert Models - Immutable Event Entities

Represents raw and normalized alerts from Grafana/Prometheus.
No inference of entities from external data.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    """Validation status for normalized alerts."""
    VALID = "VALID"
    MALFORMED = "MALFORMED"


class Alert(BaseModel):
    """
    Raw immutable event from Grafana/Prometheus.
    
    This is the input format received from external systems.
    """
    
    timestamp: datetime = Field(..., description="Time of alert generation (ISO8601)")
    fingerprint: str = Field(..., description="Unique hash from Prometheus")
    service: str = Field(..., description="Service name (e.g., 'checkout-service')")
    severity: str = Field(..., description="Alert severity: critical, warning, info")
    description: str = Field(..., description="Human-readable alert text")
    labels: dict[str, str] = Field(default_factory=dict, description="Key-value pairs from source")
    
    class Config:
        frozen = True  # Immutable after creation


class NormalizedAlert(BaseModel):
    """
    Canonical representation used internally.
    
    Created by AlertNormalizer after validation.
    """
    
    # Inherited from Alert
    timestamp: datetime = Field(..., description="Time of alert generation")
    fingerprint: str = Field(..., description="Unique hash from Prometheus")
    service: str = Field(..., description="Service name")
    severity: str = Field(...                               , description="Alert severity")
    description: str = Field(..., description="Human-readable alert text")
    labels: dict[str, str] = Field(default_factory=dict, description="Key-value pairs")
    
    # Normalization metadata
    validation_status: ValidationStatus = Field(..., description="VALID or MALFORMED")
    normalization_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Time of ingestion/normalization"
    )
    validation_errors: Optional[list[str]] = Field(None, description="List of validation errors if MALFORMED")
    
    class Config:
        frozen = True
