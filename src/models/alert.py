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


class AlertSource(str, Enum):
    """Source of the alert."""
    GRAFANA = "GRAFANA"
    SERVICENOW = "SERVICENOW"


class Alert(BaseModel):
    """
    Raw immutable event from Grafana/Prometheus or ServiceNow.
    
    This is the input format received from external systems.
    """
    
    timestamp: datetime = Field(..., description="Time of alert generation (ISO8601)")
    fingerprint: str = Field(..., description="Unique hash from Prometheus or Ticket ID")
    # Allow legacy Grafana-shaped payloads: if `service`/`severity`/`description` are
    # missing, they will be derived from `labels`/`annotations` provided by Grafana.
    service: str | None = Field(None, description="Service name (e.g., 'checkout-service')")
    severity: str | None = Field(None, description="Alert severity: critical, warning, info")
    description: str | None = Field(None, description="Human-readable alert text")
    source: AlertSource = Field(default=AlertSource.GRAFANA, description="Source system of the alert")
    labels: dict[str, str] = Field(default_factory=dict, description="Key-value pairs from source")
    # Legacy Grafana fields
    annotations: dict[str, str] | None = Field(None, description="Grafana annotations (summary, description)")
    status: str | None = Field(None, description="Grafana alert status (firing/ok)")
    generator_url: str | None = Field(None, description="Generator URL from Grafana")
    
    class Config:
        frozen = True  # Immutable after creation

    def __init__(self, **data):
        # Derive common fields from legacy Grafana payload shapes when needed
        labels = data.get("labels") or {}
        annotations = data.get("annotations") or {}

        if not data.get("service"):
            data["service"] = labels.get("service") or labels.get("app") or "unknown"
        if not data.get("severity"):
            data["severity"] = labels.get("severity") or labels.get("level") or "warning"
        if not data.get("description"):
            data["description"] = annotations.get("summary") or annotations.get("description") or ""

        super().__init__(**data)


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
