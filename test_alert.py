#!/usr/bin/env python3
"""
Test Alert Dispatcher for Strands

Sends test alerts to the AlertManager webhook endpoint to trigger swarm execution.
"""

import requests
import json
import sys
import time
from datetime import datetime, timedelta

def send_alert(alert_name: str, severity: str = "critical", instance: str = "web-prod-03", description: str = "Test alert"):
    """Send a test alert to AlertManager webhook."""
    
    # AlertManager webhook payload format
    alert_payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": alert_name,
                    "severity": severity,
                    "instance": instance,
                    "alert_type": "infrastructure"
                },
                "annotations": {
                    "summary": f"{alert_name} on {instance}",
                    "description": description
                },
                "startsAt": datetime.utcnow().isoformat() + "Z",
                "endsAt": "0001-01-01T00:00:00Z"
            }
        ],
        "groupLabels": {
            "alertname": alert_name
        },
        "commonLabels": {
            "alertname": alert_name,
            "severity": severity,
            "instance": instance
        },
        "commonAnnotations": {
            "summary": f"{alert_name} on {instance}",
            "description": description
        },
        "externalURL": "http://prometheus:9090",
        "version": "4",
        "groupKey": f"{alert_name}",
        "receiver": "strands-webhook"
    }
    
    try:
        # Send to AlertManager first (if running locally)
        alertmanager_url = "http://localhost:9093/api/v1/alerts"
        print(f"📤 Sending alert to AlertManager: {alertmanager_url}")
        response = requests.post(alertmanager_url, json=[alert_payload["alerts"][0]], timeout=5)
        print(f"   ✓ AlertManager response: {response.status_code}")
        
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️  AlertManager not available on localhost:9093")
    except Exception as e:
        print(f"   ❌ Error sending to AlertManager: {e}")
    
    # Send directly to Strands webhook
    try:
        strands_url = "http://localhost:8080/api/v1/alerts"
        print(f"📤 Sending alert to Strands: {strands_url}")
        response = requests.post(strands_url, json=alert_payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Strands response: {result.get('status')} (run_id: {result.get('run_id')})")
            return True
        else:
            print(f"   ❌ Strands HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Cannot connect to Strands on localhost:8080")
        print(f"      Make sure orchestrator is running: docker compose logs strands-agent-orchestrator")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Send test alerts."""
    
    test_alerts = [
        {
            "alert_name": "HighCPUUsage",
            "severity": "warning",
            "instance": "web-prod-03",
            "description": "CPU usage above 80% for more than 5 minutes"
        },
        {
            "alert_name": "PodCrashLooping",
            "severity": "critical",
            "instance": "web-prod-03",
            "description": "Pod is crash looping"
        },
        {
            "alert_name": "ServiceDown",
            "severity": "critical",
            "instance": "api-prod-01",
            "description": "HTTP service is not responding"
        },
    ]
    
    print("\n🚀 Strands Alert Test Dispatcher")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        alert_index = int(sys.argv[1]) - 1 if sys.argv[1].isdigit() else 0
        if 0 <= alert_index < len(test_alerts):
            alert = test_alerts[alert_index]
            print(f"\n📍 Sending Alert #{alert_index + 1}: {alert['alert_name']}")
            send_alert(**alert)
        else:
            print(f"Alert #{sys.argv[1]} not found. Available alerts: 1-{len(test_alerts)}")
    else:
        print(f"\nAvailable test alerts:")
        for i, alert in enumerate(test_alerts, 1):
            print(f"  {i}. {alert['alert_name']} ({alert['severity']}) - {alert['description']}")
        
        print(f"\nUsage:")
        print(f"  python test_alert.py 1   # Send first alert")
        print(f"  python test_alert.py 2   # Send second alert")
        print(f"  python test_alert.py 3   # Send third alert")
    
    print()

if __name__ == "__main__":
    main()
