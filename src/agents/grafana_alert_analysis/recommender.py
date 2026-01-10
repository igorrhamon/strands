from typing import List, Dict
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
            
            action = "OBSERVE"
            hypothesis = "Ambiguous pattern, requires observation."
            confidence = 0.5
            
            # Simple heuristic rules
            
            # Rule: High recurrence + low impact (assuming LOW severity is low impact)
            if count > 5 and severity == "LOW":
                action = "CLOSE"
                hypothesis = "High recurrence of low severity alerts, likely noise."
                confidence = 0.8
            
            # Rule: Short duration (Placeholder logic as we don't have duration calculated yet)
            # if duration < 5 mins: action = "CLOSE"
            
            # Rule: Critical severity
            elif severity == "CRITICAL":
                action = "ESCALATE"
                hypothesis = "Critical severity alert detected."
                confidence = 0.9
                
            # Rule: Affects multiple services (Placeholder: cluster logic currently groups by service)
            # If we had a meta-cluster of clusters, we could check this.
            
            rec = AlertRecommendation(
                cluster_id=str(cluster.get('cluster_id', 'unknown')),
                severity=severity,
                services=[str(service)] if service else [],
                root_cause_hypothesis=hypothesis,
                recommended_action=action,
                confidence=confidence
            )
            recommendations.append(rec)
            
        return recommendations
