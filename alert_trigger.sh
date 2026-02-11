#!/bin/bash
# Strands Alert Trigger Script
# Easily send test alerts to the orchestrator

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ORCHESTRATOR_HOST="${ORCHESTRATOR_HOST:-localhost}"
ORCHESTRATOR_PORT="${ORCHESTRATOR_PORT:-8080}"
API_URL="http://${ORCHESTRATOR_HOST}:${ORCHESTRATOR_PORT}/api/v1"

print_header() {
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_orchestrator_health() {
    local response=$(curl -s -w "\n%{http_code}" "${API_URL}/health" 2>&1 || echo "error")
    local http_code=$(echo "$response" | tail -n1)
    
    if [[ "$http_code" == "200" ]]; then
        print_success "Orchestrator is healthy"
        return 0
    else
        print_error "Cannot reach orchestrator at ${API_URL}"
        echo "  Make sure it's running: docker compose up -d"
        return 1
    fi
}

send_test_alert() {
    local alert_name=$1
    local severity=$2
    local instance=$3
    local description=$4
    
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    local payload=$(cat <<EOF
{
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "${alert_name}",
        "severity": "${severity}",
        "instance": "${instance}",
        "alert_type": "infrastructure"
      },
      "annotations": {
        "summary": "${alert_name} on ${instance}",
        "description": "${description}"
      },
      "startsAt": "${timestamp}",
      "endsAt": "0001-01-01T00:00:00Z"
    }
  ],
  "groupLabels": {
    "alertname": "${alert_name}"
  },
  "commonLabels": {
    "alertname": "${alert_name}",
    "severity": "${severity}",
    "instance": "${instance}"
  },
  "commonAnnotations": {
    "summary": "${alert_name} on ${instance}",
    "description": "${description}"
  },
  "externalURL": "http://prometheus:9090",
  "version": "4",
  "groupKey": "${alert_name}",
  "receiver": "strands-webhook"
}
EOF
)
    
    local response=$(curl -s -X POST "${API_URL}/alerts" \
        -H "Content-Type: application/json" \
        -d "${payload}")
    
    local run_id=$(echo "$response" | grep -o '"run_id":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
    
    if [[ "$run_id" != "unknown" ]]; then
        print_success "Alert sent: ${alert_name}"
        echo "  Run ID: ${run_id}"
        echo "  Instance: ${instance}"
        return 0
    else
        print_error "Failed to send alert"
        echo "  Response: $response"
        return 1
    fi
}

show_help() {
    cat <<EOF
${BLUE}Strands Alert Trigger${NC}

Usage: $0 [command] [options]

Commands:
  health              Check orchestrator health
  send <num>          Send predefined test alert #<num> (1-3)
  custom <name>       Send custom alert with name
  list                Show available test alerts
  monitor             Follow orchestrator logs
  
Predefined Alerts:
  1. HighCPUUsage (warning) - CPU usage above 80%
  2. PodCrashLooping (critical) - Pod restart loop
  3. ServiceDown (critical) - HTTP service not responding

Environment Variables:
  ORCHESTRATOR_HOST   (default: localhost)
  ORCHESTRATOR_PORT   (default: 8080)

Examples:
  $0 health
  $0 send 1
  $0 send 2 
  $0 custom "DatabaseSlowQueries"
  $0 monitor

EOF
}

case "${1:-help}" in
    health)
        print_header "Checking Orchestrator Health"
        check_orchestrator_health
        ;;
    
    send)
        if [[ -z "$2" ]]; then
            print_error "Alert number required (1-3)"
            exit 1
        fi
        
        check_orchestrator_health || exit 1
        
        case "$2" in
            1)
                print_header "Sending Alert #1: HighCPUUsage"
                send_test_alert "HighCPUUsage" "warning" "web-prod-03" "CPU usage above 80% for more than 5 minutes"
                ;;
            2)
                print_header "Sending Alert #2: PodCrashLooping"
                send_test_alert "PodCrashLooping" "critical" "web-prod-03" "Pod is crash looping"
                ;;
            3)
                print_header "Sending Alert #3: ServiceDown"
                send_test_alert "ServiceDown" "critical" "api-prod-01" "HTTP service is not responding"
                ;;
            *)
                print_error "Invalid alert number. Try 1, 2, or 3"
                exit 1
                ;;
        esac
        
        echo ""
        echo "Follow execution with: $0 monitor"
        ;;
    
    custom)
        if [[ -z "$2" ]]; then
            print_error "Alert name required"
            exit 1
        fi
        
        check_orchestrator_health || exit 1
        
        print_header "Sending Custom Alert: $2"
        send_test_alert "$2" "critical" "prod-host-01" "Custom alert triggered"
        ;;
    
    list)
        print_header "Available Test Alerts"
        cat <<EOF
1. ${YELLOW}HighCPUUsage${NC} (warning)
   Instance: web-prod-03
   Description: CPU usage above 80% for more than 5 minutes
   
2. ${RED}PodCrashLooping${NC} (critical)
   Instance: web-prod-03
   Description: Pod is crash looping
   
3. ${RED}ServiceDown${NC} (critical)
   Instance: api-prod-01
   Description: HTTP service is not responding

Usage:
  $0 send 1
  $0 send 2
  $0 send 3
EOF
        ;;
    
    monitor)
        print_header "Following Orchestrator Logs"
        docker compose logs -f strands-agent-orchestrator 2>/dev/null | grep -E "RECEIVED|successfully|Report|error|ERROR"
        ;;
    
    *)
        show_help
        ;;
esac
