"""
AlertCluster Model - Grouped Correlated Alerts

Represents a group of related alerts clustered by fingerprint,
service, and temporal proximity.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.models.alert import NormalizedAlert


class AlertCluster(BaseModel):
    """
    Group of related alerts.

    Created by CorrelationEngine based on:
    - Fingerprint matching
    - Service proximity
    - Time window (default 5 minutes)
    """

    cluster_id: UUID = Field(default_factory=uuid4, description="Unique cluster identifier")
    alerts: list[NormalizedAlert] = Field(..., min_length=1, description="Constituent alerts")
    correlation_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence of grouping (0.0-1.0)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Cluster formation time"
    )

    # Computed properties
    primary_service: str = Field(..., description="Most common service in cluster")
    primary_severity: str = Field(..., description="Highest severity in cluster")
    alert_count: int = Field(..., ge=1, description="Number of alerts in cluster")

    # Optional metadata for custom configuration (US4)
    metadata: dict = Field(
        default_factory=dict,
        description="Custom metadata (e.g., explicit_metrics, lookback_override)",
    )

    class Config:
        frozen = False  # Allow metadata updates

    @classmethod
    def from_alerts(cls, alerts: list[NormalizedAlert], correlation_score: float) -> "AlertCluster":
        """Factory method to create cluster from alerts with computed properties."""
        if not alerts:
            raise ValueError("Cannot create cluster from empty alert list")

        # Compute primary service (most common)
        service_counts: dict[str, int] = {}
        for alert in alerts:
            service_counts[alert.service] = service_counts.get(alert.service, 0) + 1
        primary_service = max(service_counts, key=lambda k: service_counts[k])

        # Compute primary severity (highest)
        severity_order = {"critical": 3, "warning": 2, "info": 1}
        primary_severity = max(
            (a.severity for a in alerts), key=lambda s: severity_order.get(s.lower(), 0)
        )

        return cls(
            alerts=alerts,
            correlation_score=correlation_score,
            primary_service=primary_service,
            primary_severity=primary_severity,
            alert_count=len(alerts),
        )
