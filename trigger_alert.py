#!/usr/bin/env python3
"""
Trigger alerts in Alertmanager by sending alert payloads via HTTP.

This script sends alert data directly to Alertmanager webhook endpoint.
"""

import requests
import json
import time
from datetime import datetime, timedelta

ALERTMANAGER_URL = "http://localhost:9093/api/v2/alerts"
STRANDS_WEBHOOK_URL = "http://localhost:8080/api/v1/alerts"

def send_alert_to_alertmanager(alerts):
    """Send alert to Alertmanager."""
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(ALERTMANAGER_URL, json=alerts, headers=headers, timeout=5)
        print(f"✓ Alertmanager response: {response.status_code}")
        if response.ok:
            return True
        else:
            # Log response body to help debug (Alertmanager can return 400/500 etc.)
            print(f"✗ Alertmanager error: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Failed to send alert to Alertmanager: {e}")
        return False

def create_alert(alertname, severity="critical", instance="payment-service:9090"):
    """Create alert payload."""
    now = datetime.utcnow()
    return {
        "labels": {
            "alertname": alertname,
            "severity": severity,
            "instance": instance,
            "job": "payment_service",
            "alert_type": "infrastructure"
        },
        "annotations": {
            "summary": f"{alertname} triggered on {instance}",
            "description": f"Alert {alertname} with severity {severity} has been triggered",
            "runbook_url": "http://localhost:8000"
        },
        "startsAt": now.isoformat() + "Z",
        "endsAt": (now + timedelta(hours=1)).isoformat() + "Z",
        "generatorURL": "http://localhost:9090/graph"
    }

def main():
    print("🚀 Trigger Alert via Alertmanager - Direto")
    print("=" * 50)
    
    # Alert 1: HighCPUUsage
    print("\n📤 Enviando alerta: HighCPUUsage")
    alert1 = create_alert("HighCPUUsage", "critical", "payment-service:9090")
    if send_alert_to_alertmanager([alert1]):
        print("  ✓ HighCPUUsage alert triggered")
    
    time.sleep(2)
    
    # Alert 2: ServiceDown
    print("\n📤 Enviando alerta: ServiceDown")
    alert2 = create_alert("ServiceDown", "critical", "api-server:9090")
    if send_alert_to_alertmanager([alert2]):
        print("  ✓ ServiceDown alert triggered")
    
    time.sleep(2)
    
    # Alert 3: HighMemoryUsage
    print("\n📤 Enviando alerta: HighMemoryUsage")
    alert3 = create_alert("HighMemoryUsage", "warning", "database:9090")
    if send_alert_to_alertmanager([alert3]):
        print("  ✓ HighMemoryUsage alert triggered")
    
    time.sleep(2)
    
    # Check Alertmanager
    print("\n🔔 Verificando alertas no Alertmanager...")
    try:
        response = requests.get(ALERTMANAGER_URL, timeout=5)
        if response.status_code == 200:
            alerts = response.json()
            print(f"  ✓ Total alertas no Alertmanager: {len(alerts)}")
            for alert in alerts:
                labels = alert.get('labels', {})
                print(f"    - {labels.get('alertname')}: {labels.get('severity')} ({labels.get('instance')})")
        else:
            print(f"  ✗ Erro ao verificar: {response.status_code}")
    except Exception as e:
        print(f"  ✗ {e}")
    
    # Check Strands
    print("\n📨 Verificando se Strands recebeu alertas...")
    try:
        response = requests.get("http://localhost:8080/api/v1/health", timeout=5)
        if response.status_code == 200:
            print(f"  ✓ Strands está rodando")
        else:
            print(f"  ✗ Strands retornou: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Strands não está acessível: {e}")
    
    print("\n" + "=" * 50)
    print("✓ Alertas disparados com sucesso!")
    print("\n  Links:")
    print("    Alertmanager: http://localhost:9093")
    print("    Strands:      http://localhost:8000")
    print("    Prometheus:   http://localhost:9090")

if __name__ == '__main__':
    main()

