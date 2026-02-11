#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Strands - Real Swarm Intelligence Execution"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Check Python environment
echo "📌 Step 1: Checking Python environment..."
if ! python3 -c "import swarm_intelligence" 2>/dev/null; then
    echo "❌ swarm_intelligence not found in Python path"
    echo "   Activating virtual environment..."
    if [ -d ".venv-1" ]; then
        source .venv-1/bin/activate
    elif [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        echo "❌ No virtual environment found (.venv or .venv-1)"
        echo "   Install with: pip install -r requirements.txt"
        exit 1
    fi
fi
echo "✅ Python environment ready"
echo ""

# Step 2: Cleanup and restart infrastructure
echo "📌 Step 2: Starting infrastructure services..."
docker compose down --remove-orphans 2>/dev/null || true
sleep 2

# Start only the infra services (not the dashboard/analyzer web services)
docker compose up -d \
    neo4j-strads \
    qdrant-strads \
    prometheus-strads \
    grafana-strads \
    grafana-proxy-strads \
    ollama

echo "✅ Infrastructure services started"
echo ""

# Step 3: Wait for Neo4j to be ready
echo "📌 Step 3: Waiting for Neo4j to be ready..."

# Extract Neo4j password from .env
NEO4J_PASSWORD=$(grep "^NEO4J_PASSWORD=" .env | cut -d= -f2- | tr -d '\r' || echo "strands_dev_neo4j_2026_secure_k8xP9mQz")

MAX_RETRIES=30
RETRY_DELAY=2
RETRIES=0

while [ $RETRIES -lt $MAX_RETRIES ]; do
    if docker exec neo4j-strads cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; then
        echo "✅ Neo4j is ready!"
        break
    fi
    echo "   Waiting for Neo4j... ($((RETRIES+1))/$MAX_RETRIES)"
    sleep $RETRY_DELAY
    RETRIES=$((RETRIES+1))
done

if [ $RETRIES -eq $MAX_RETRIES ]; then
    echo "❌ Neo4j failed to start in time"
    docker logs neo4j-strads --tail 20
    exit 1
fi

echo ""

# Step 4: Show infrastructure status
echo "📌 Step 4: Infrastructure Status:"
echo ""
docker compose ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" \
    neo4j-strads \
    qdrant-strads \
    prometheus-strads \
    grafana-strads \
    ollama

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "▶️  RUNNING: python main.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 5: Run the main.py with real swarm execution
python3 main.py

EXIT_CODE=$?

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Swarm Execution Completed Successfully!"
    echo ""
    echo "📊 Check Neo4j for results:"
    echo "   → http://localhost:7474"
    echo ""
    echo "📈 Check metrics in Prometheus:"
    echo "   → http://localhost:9090"
    echo ""
    echo "📋 View dashboards in Grafana:"
    echo "   → http://localhost:3100"
else
    echo "❌ Swarm Execution Failed (exit code: $EXIT_CODE)"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

exit $EXIT_CODE
