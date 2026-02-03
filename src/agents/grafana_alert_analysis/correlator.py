from typing import List, Dict, Any
import hashlib

class AlertCorrelator:
    def cluster(self, alerts: List[Dict]) -> List[Dict]:
        """
        Cluster alerts based on fingerprint, service+alertname, and time window.
        
        Args:
            alerts: List of alert dictionaries
            
        Returns:
            List of clusters, where each cluster is a dictionary containing metadata and the list of alerts.
        """
        clusters = []
        processed_indices = set()

        for i, alert in enumerate(alerts):
            if i in processed_indices:
                continue

            # Start a new cluster
            cluster_alerts = [alert]
            processed_indices.add(i)
            
            for j, other_alert in enumerate(alerts):
                if j in processed_indices:
                    continue
                
                if self._alerts_match(alert, other_alert):
                    cluster_alerts.append(other_alert)
                    processed_indices.add(j)
            
            clusters.append(self._create_cluster_object(cluster_alerts))
            
        return clusters

    def _alerts_match(self, alert1: Dict, alert2: Dict) -> bool:
        """Check if two alerts should be clustered together."""
        # 1. Identical Fingerprint
        fp1 = alert1.get('fingerprint')
        fp2 = alert2.get('fingerprint')
        if fp1 and fp2 and fp1 == fp2:
            return True
        
        # 2. Same service + alertname
        labels1 = alert1.get('labels', {})
        labels2 = alert2.get('labels', {})
        
        service1 = labels1.get('service')
        alertname1 = labels1.get('alertname')
        
        if service1 and alertname1 and \
           service1 == labels2.get('service') and \
           alertname1 == labels2.get('alertname'):
            return True
            
        return False

    def _create_cluster_object(self, cluster_alerts: List[Dict]) -> Dict[str, Any]:
        """Create a cluster object from a list of alerts."""
        first_alert = cluster_alerts[0]
        labels = first_alert.get('labels', {})
        service = labels.get('service')
        alertname = labels.get('alertname')
        fingerprint = first_alert.get('fingerprint')
        
        cluster_id = hashlib.md5(f"{service}-{alertname}-{fingerprint}".encode()).hexdigest()
        
        return {
            "cluster_id": cluster_id,
            "alerts": cluster_alerts,
            "service": service,
            "alertname": alertname,
            "severity": labels.get('severity', 'unknown'),
            "count": len(cluster_alerts)
        }
