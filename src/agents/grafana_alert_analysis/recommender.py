from datetime import datetime, timezone
from typing import List, Dict, Optional
from .schemas import AlertRecommendation


class RecommendationEngine:
    def recommend(self, clusters: List[Dict]) -> List[AlertRecommendation]:
        """
        Generate recommendations for alert clusters.
        
        Args:
            clusters: List of alert clusters
            
        Returns:
            List of AlertRecommendation objects
        """
        recommendations = []
        
        for cluster in clusters:
            severity = cluster.get('severity', 'unknown').upper()
            service = cluster.get('service', 'unknown')
            count = cluster.get('count', 0)
            services: List[str] = cluster.get('services', [str(service)] if service else [])

            # --- Duration rule -----------------------------------------------
            # Calculate alert duration in minutes when both timestamps provided.
            starts_at: Optional[str] = cluster.get('starts_at') or cluster.get('startsAt')
            ends_at: Optional[str] = cluster.get('ends_at') or cluster.get('endsAt')
            duration_minutes: Optional[float] = None
            if starts_at and ends_at:
                try:
                    dt_start = datetime.fromisoformat(
                        starts_at.replace("Z", "+00:00")
                    )
                    dt_end = datetime.fromisoformat(
                        ends_at.replace("Z", "+00:00")
                    )
                    duration_minutes = (
                        dt_end - dt_start
                    ).total_seconds() / 60.0
                except (ValueError, TypeError):
                    pass

            action = "OBSERVE"
            hypothesis = "Ambiguous pattern, requires observation."
            confidence = 0.5

            # --- Rule: Short-lived alert (< 5 min) → CLOSE -------------------
            if duration_minutes is not None and duration_minutes < 5.0:
                action = "CLOSE"
                hypothesis = (
                    f"Alert resolved itself within {duration_minutes:.1f} minutes; "
                    "likely transient or self-healing."
                )
                confidence = 0.7

            # --- Rule: High recurrence + low severity → CLOSE ----------------
            elif count > 5 and severity == "LOW":
                action = "CLOSE"
                hypothesis = "High recurrence of low severity alerts, likely noise."
                confidence = 0.8

            # --- Rule: Critical severity → ESCALATE --------------------------
            elif severity == "CRITICAL":
                action = "ESCALATE"
                hypothesis = "Critical severity alert detected."
                confidence = 0.9

            # --- Rule: Affects many services → ESCALATE ----------------------
            elif len(services) > 3:
                action = "ESCALATE"
                hypothesis = (
                    f"Alert spans {len(services)} services "
                    "({', '.join(services[:4])}{'...' if len(services) > 4 else ''}); "
                    "likely a systemic issue."
                )
                confidence = 0.85

            rec = AlertRecommendation(
                cluster_id=str(cluster.get('cluster_id', 'unknown')),
                severity=severity,
                services=services,
                root_cause_hypothesis=hypothesis,
                recommended_action=action,
                confidence=confidence
            )
            recommendations.append(rec)
            
        return recommendations
