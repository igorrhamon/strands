#!/bin/bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Strands - Human-in-the-Loop Startup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Step 1: Cleanup
echo "📌 Step 1: Cleaning up existing containers..."
docker compose down --remove-orphans 2>/dev/null || true
echo "✅ Cleanup complete"
echo ""

# Step 2: Build and startup
echo "📌 Step 2: Building and starting all services..."
echo "   This may take 2-5 minutes on first run..."
echo ""

docker compose up -d --build

echo ""
echo "✅ All containers started!"
echo ""

# Step 3: Wait for services to be ready
echo "📌 Step 3: Waiting for services to stabilize (30 seconds)..."
sleep 30

# Step 4: Check status
echo ""
echo "📌 Step 4: Service Status:"
echo ""
docker compose ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 Human-in-the-Loop Dashboard:"
echo "   → http://localhost:8000"
echo ""
echo "📊 Monitoring & Visualization:"
echo "   → Prometheus: http://localhost:9090"
echo "   → Grafana: http://localhost:3100"
echo ""
echo "🔍 Data Stores:"
echo "   → Neo4j: http://localhost:7474"
echo "   → Qdrant: http://localhost:6333"
echo ""
echo "📈 LLM Analysis:"
echo "   → SEO Analyzer Health: http://localhost:8001/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 TIP: See STARTUP_GUIDE.md for full documentation"
echo "💡 TIP: Run 'docker compose logs -f strands-dashboard' to see real-time logs"
echo ""
