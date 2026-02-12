#!/usr/bin/env bash
set -euo pipefail

# send_test_alert.sh
# Small helper to POST test alerts to Alertmanager (v2) or directly to the
# strands orchestrator webhook. Use this locally to validate the end-to-end flow.

ALERTMANAGER_URL=${ALERTMANAGER_URL:-http://localhost:9093/api/v2/alerts}
ORCHESTRATOR_URL=${ORCHESTRATOR_URL:-http://localhost:8080/api/v1/alerts}

usage() {
  cat <<EOF
Usage: $0 <target>

Targets:
  alertmanager   Send a minimal Alertmanager v2 payload to ${ALERTMANAGER_URL}
  orchestrator   Send a webhook-style payload directly to ${ORCHESTRATOR_URL}
  both           Send to Alertmanager then to orchestrator

Examples:
  $0 alertmanager
  $0 orchestrator
  $0 both

Note: ensure the services are reachable on localhost (docker compose must be running).
EOF
}

send_to_alertmanager() {
  cat <<'JSON' | curl -sS -X POST "${ALERTMANAGER_URL}" -H 'Content-Type: application/json' -d @-
[
  {
    "labels": {
      "alertname": "ManualTestAlert",
      "severity": "critical",
      "instance": "local-manual:9090",
      "job": "manual_test",
      "alert_type": "infrastructure"
    },
    "annotations": {
      "summary": "Manual test alert",
      "description": "Testing Alertmanager v2 -> Strands webhook flow"
    },
    "startsAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "endsAt": "$(date -u -d '+1 hour' +%Y-%m-%dT%H:%M:%SZ)",
    "generatorURL": "http://localhost:9090/graph"
  }
]
JSON

  echo "\nSent to Alertmanager at ${ALERTMANAGER_URL}"
}

send_to_orchestrator() {
  cat <<'JSON' | curl -sS -X POST "${ORCHESTRATOR_URL}" -H 'Content-Type: application/json' -d @-
{
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "ManualTestAlert",
        "severity": "critical",
        "instance": "local-manual:9090",
        "alert_type": "infrastructure"
      },
      "annotations": {
        "summary": "Manual test alert",
        "description": "Direct POST to strands orchestrator"
      },
      "startsAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "endsAt": "0001-01-01T00:00:00Z"
    }
  ],
  "groupLabels": {"alertname": "ManualTestAlert"},
  "commonLabels": {"alertname": "ManualTestAlert", "severity": "critical"},
  "commonAnnotations": {"summary": "Manual test alert"},
  "externalURL": "http://localhost:9090",
  "version": "4",
  "groupKey": "ManualTestAlert",
  "receiver": "manual"
}
JSON

  echo "\nSent direct webhook to ${ORCHESTRATOR_URL}"
}

if [ "$#" -ne 1 ]; then
  usage
  exit 1
fi

case "$1" in
  alertmanager)
    send_to_alertmanager
    ;;
  orchestrator)
    send_to_orchestrator
    ;;
  both)
    send_to_alertmanager
    sleep 1
    send_to_orchestrator
    ;;
  -h|--help)
    usage
    ;;
  *)
    echo "Unknown target: $1" >&2
    usage
    exit 2
    ;;
esac

echo "Done."
