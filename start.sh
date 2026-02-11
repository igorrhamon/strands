#!/bin/bash
# Startup script for Strands development environment
# This script sets up the environment and starts the services

set -e  # Exit on error

echo "🚀 Strands Startup Script"
echo "========================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "📋 Copying .env.example to .env..."
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and set the following required values:"
    echo "   - NEO4J_PASSWORD"
    echo "   - GRAFANA_ADMIN_PASSWORD"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Validate required environment variables
echo "🔍 Validating configuration..."
source .env

if [ -z "$NEO4J_PASSWORD" ] || [ "$NEO4J_PASSWORD" = "changeme_secure_password_here" ]; then
    echo "❌ NEO4J_PASSWORD is not set or still has default value"
    echo "   Please update .env with a secure password"
    exit 1
fi

if [ -z "$GRAFANA_ADMIN_PASSWORD" ] || [ "$GRAFANA_ADMIN_PASSWORD" = "changeme_grafana_password" ]; then
    echo "❌ GRAFANA_ADMIN_PASSWORD is not set or still has default value"
    echo "   Please update .env with a secure password"
    exit 1
fi

echo "✅ Configuration validated"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running"
    echo "   Please start Docker and try again"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Start services
echo "🐳 Starting Docker Compose services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo ""
echo "🏥 Checking service health..."

# Neo4j
if curl -s -f http://localhost:7474 > /dev/null 2>&1; then
    echo "✅ Neo4j is ready (http://localhost:7474)"
else
    echo "⚠️  Neo4j might not be ready yet"
fi

# Grafana
if curl -s -f http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Grafana is ready (http://localhost:3000)"
else
    echo "⚠️  Grafana might not be ready yet"
fi

# Prometheus
if curl -s -f http://localhost:9090 > /dev/null 2>&1; then
    echo "✅ Prometheus is ready (http://localhost:9090)"
else
    echo "⚠️  Prometheus might not be ready yet"
fi

# Qdrant
if curl -s -f http://localhost:6333 > /dev/null 2>&1; then
    echo "✅ Qdrant is ready (http://localhost:6333)"
else
    echo "⚠️  Qdrant might not be ready yet"
fi

# Dashboard
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Dashboard is ready (http://localhost:8000)"
else
    echo "⚠️  Dashboard might not be ready yet"
fi

echo ""
echo "🎉 Strands is starting up!"
echo ""
echo "📊 Service URLs:"
echo "   - Dashboard:   http://localhost:8000"
echo "   - Neo4j:       http://localhost:7474 (user: neo4j, pass: from .env)"
echo "   - Grafana:     http://localhost:3000 (user: admin, pass: from .env)"
echo "   - Prometheus:  http://localhost:9090"
echo "   - Qdrant:      http://localhost:6333"
echo ""
echo "📝 Useful commands:"
echo "   docker-compose logs -f           # View all logs"
echo "   docker-compose logs -f neo4j     # View Neo4j logs"
echo "   docker-compose ps                # List running services"
echo "   docker-compose down              # Stop all services"
echo ""
echo "🧪 To run the swarm intelligence demo:"
echo "   source .venv-1/bin/activate"
echo "   python main.py"
echo ""
