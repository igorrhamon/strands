"""
Correlation Rules - Alert Clustering Logic

Implements deterministic rules for grouping related alerts.
Constitution Principle II: Rules execute BEFORE any LLM invocation.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from src.models.alert import NormalizedAlert
from src.models.cluster import AlertCluster

logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_TIME_WINDOW_MINUTES = 5
DEFAULT_MIN_CORRELATION_SCORE = 0.5


class CorrelationConfig:
    """Configuration for correlation rules."""
    
    def __init__(
        self,
        time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
        min_correlation_score: float = DEFAULT_MIN_CORRELATION_SCORE,
        group_by_service: bool = True,
        group_by_fingerprint: bool = True,
    ):
        self.time_window_minutes = time_window_minutes
        self.min_correlation_score = min_correlation_score
        self.group_by_service = group_by_service
        self.group_by_fingerprint = group_by_fingerprint


class CorrelationEngine:
    """
    Deterministic engine for grouping related alerts.
    
    Grouping criteria (in priority order):
    1. Same fingerprint (exact match)
    2. Same service within time window
    3. Temporal proximity (5-minute window)
    """
    
    def __init__(self, config: Optional[CorrelationConfig] = None):
        """
        Initialize correlation engine.
        
        Args:
            config: Correlation configuration. Defaults to sensible values.
        """
        self._config = config or CorrelationConfig()
    
    def correlate(self, alerts: list[NormalizedAlert]) -> list[AlertCluster]:
        """
        Group alerts into correlated clusters.
        
        Args:
            alerts: List of normalized alerts to correlate.
        
        Returns:
            List of AlertCluster objects.
        """
        if not alerts:
            return []
        
        # Sort by timestamp for temporal grouping
        sorted_alerts = sorted(alerts, key=lambda a: a.timestamp)
        
        # Phase 1: Group by fingerprint (highest confidence)
        fingerprint_groups = self._group_by_fingerprint(sorted_alerts)
        
        # Phase 2: Group remaining by service + time
        service_groups = self._group_by_service_time(sorted_alerts)
        
        # Merge groups and calculate correlation scores
        clusters = []
        
        # Fingerprint-based clusters (high confidence)
        for fingerprint, group_alerts in fingerprint_groups.items():
            if len(group_alerts) >= 1:
                cluster = AlertCluster.from_alerts(
                    alerts=group_alerts,
                    correlation_score=self._calculate_fingerprint_score(group_alerts),
                )
                clusters.append(cluster)
        
        # Service-based clusters for alerts not in fingerprint groups
        processed_fingerprints = set(fingerprint_groups.keys())
        for service, group_alerts in service_groups.items():
            # Filter out alerts already in fingerprint groups
            remaining_alerts = [
                a for a in group_alerts 
                if a.fingerprint not in processed_fingerprints
            ]
            if remaining_alerts:
                cluster = AlertCluster.from_alerts(
                    alerts=remaining_alerts,
                    correlation_score=self._calculate_service_score(remaining_alerts),
                )
                clusters.append(cluster)
        
        logger.info(f"Correlated {len(alerts)} alerts into {len(clusters)} clusters")
        return clusters
    
    def _group_by_fingerprint(
        self, alerts: list[NormalizedAlert]
    ) -> dict[str, list[NormalizedAlert]]:
        """Group alerts by fingerprint."""
        groups: dict[str, list[NormalizedAlert]] = defaultdict(list)
        
        if not self._config.group_by_fingerprint:
            return groups
        
        for alert in alerts:
            groups[alert.fingerprint].append(alert)
        
        return groups
    
    def _group_by_service_time(
        self, alerts: list[NormalizedAlert]
    ) -> dict[str, list[NormalizedAlert]]:
        """Group alerts by service within time window."""
        groups: dict[str, list[NormalizedAlert]] = defaultdict(list)
        
        if not self._config.group_by_service:
            return groups
        
        time_window = timedelta(minutes=self._config.time_window_minutes)
        
        for alert in alerts:
            key = alert.service
            
            # Check if this alert fits within time window of existing group
            if groups[key]:
                last_alert_time = groups[key][-1].timestamp
                if alert.timestamp - last_alert_time <= time_window:
                    groups[key].append(alert)
                # else: Start new group implicitly on next iteration
            else:
                groups[key].append(alert)
        
        return groups
    
    def _calculate_fingerprint_score(self, alerts: list[NormalizedAlert]) -> float:
        """
        Calculate correlation score for fingerprint-based grouping.
        
        Same fingerprint = high confidence (0.9-1.0).
        """
        if len(alerts) <= 1:
            return 1.0
        
        # Check temporal proximity for bonus
        timestamps = [a.timestamp for a in alerts]
        time_span = (max(timestamps) - min(timestamps)).total_seconds()
        
        # Base score + temporal bonus
        base_score = 0.9
        temporal_bonus = 0.1 if time_span <= 300 else 0.05  # 5-minute window
        
        return min(1.0, base_score + temporal_bonus)
    
    def _calculate_service_score(self, alerts: list[NormalizedAlert]) -> float:
        """
        Calculate correlation score for service-based grouping.
        
        Same service = moderate confidence (0.6-0.8).
        """
        if len(alerts) <= 1:
            return 0.7
        
        # Factors: severity consistency, temporal proximity
        severities = [a.severity for a in alerts]
        severity_consistency = len(set(severities)) == 1
        
        timestamps = [a.timestamp for a in alerts]
        time_span = (max(timestamps) - min(timestamps)).total_seconds()
        temporal_tight = time_span <= 180  # 3-minute window
        
        base_score = 0.6
        if severity_consistency:
            base_score += 0.1
        if temporal_tight:
            base_score += 0.1
        
        return min(0.85, base_score)


def correlate_alerts(
    alerts: list[NormalizedAlert],
    time_window_minutes: int = DEFAULT_TIME_WINDOW_MINUTES,
) -> list[AlertCluster]:
    """
    Convenience function to correlate alerts.
    
    Args:
        alerts: List of normalized alerts.
        time_window_minutes: Time window for grouping.
    
    Returns:
        List of AlertCluster objects.
    """
    config = CorrelationConfig(time_window_minutes=time_window_minutes)
    engine = CorrelationEngine(config)
    return engine.correlate(alerts)
