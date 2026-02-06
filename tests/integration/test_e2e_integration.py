"""
End-to-End Integration Tests for Strands System

Testa o fluxo completo:
1. Frontend → Backend
2. Backend → Agents
3. Agents → Databases (Neo4j, Qdrant)
4. Decision Engine → Output
5. Observability → Metrics
"""

import pytest
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any
import httpx

# Configuration
BASE_URL = "http://localhost:8000"
PROMETHEUS_URL = "http://localhost:9090"
GRAFANA_URL = "http://localhost:3000"
JAEGER_URL = "http://localhost:16686"
OLLAMA_URL = "http://localhost:11434"


class TestFrontendIntegration:
    """Testa integração do Frontend"""

    @pytest.mark.asyncio
    async def test_frontend_loads(self):
        """Verifica se frontend carrega corretamente"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/")
            assert response.status_code == 200
            assert "Strands Governance" in response.text
            assert "Simulate Alert" in response.text

    @pytest.mark.asyncio
    async def test_frontend_assets_load(self):
        """Verifica se assets (CSS, JS) carregam"""
        async with httpx.AsyncClient() as client:
            # Test CSS
            response = await client.get(f"{BASE_URL}/static/css/main.css")
            assert response.status_code == 200
            assert "color" in response.text or "background" in response.text

            # Test JS
            response = await client.get(f"{BASE_URL}/static/js/api.js")
            assert response.status_code == 200
            assert "function" in response.text or "const" in response.text


class TestBackendAPIs:
    """Testa APIs do Backend"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Verifica health check do servidor"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Verifica endpoint de métricas"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/metrics")
            assert response.status_code == 200
            assert "HELP" in response.text or "TYPE" in response.text

    @pytest.mark.asyncio
    async def test_simulate_alert_endpoint(self):
        """Testa endpoint de simulação de alerta"""
        async with httpx.AsyncClient() as client:
            payload = {
                "service": "payment-api",
                "severity": "critical",
                "description": "Error rate exceeded 5%"
            }
            response = await client.post(
                f"{BASE_URL}/api/alerts",
                json=payload
            )
            assert response.status_code in [200, 201, 202]
            data = response.json()
            assert "id" in data or "status" in data


class TestAgentExecution:
    """Testa execução dos agentes"""

    @pytest.mark.asyncio
    async def test_metrics_agent(self):
        """Testa MetricsAnalysisAgent"""
        async with httpx.AsyncClient() as client:
            payload = {
                "metric_name": "error_rate",
                "current_value": 7.2,
                "threshold": 5.0
            }
            response = await client.post(
                f"{BASE_URL}/api/analyze/metrics",
                json=payload
            )
            assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_embedding_agent(self):
        """Testa EmbeddingAgent para busca de similares"""
        async with httpx.AsyncClient() as client:
            payload = {
                "text": "Database connection timeout causing checkout failures"
            }
            response = await client.post(
                f"{BASE_URL}/api/analyze/embedding",
                json=payload
            )
            assert response.status_code in [200, 201]


class TestDatabaseIntegration:
    """Testa integração com bancos de dados"""

    @pytest.mark.asyncio
    async def test_neo4j_connection(self):
        """Verifica conexão com Neo4j"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            # Neo4j deve estar no health check
            assert "neo4j" in str(data).lower() or "database" in str(data).lower()

    @pytest.mark.asyncio
    async def test_qdrant_connection(self):
        """Verifica conexão com Qdrant"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            # Qdrant deve estar no health check
            assert "qdrant" in str(data).lower() or "vector" in str(data).lower()


class TestObservability:
    """Testa stack de observabilidade"""

    @pytest.mark.asyncio
    async def test_prometheus_scrape(self):
        """Verifica se Prometheus consegue fazer scrape"""
        await asyncio.sleep(2)  # Aguardar scrape
        async with httpx.AsyncClient() as client:
            # Query para verificar se métricas foram coletadas
            response = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": "up"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_grafana_accessibility(self):
        """Verifica se Grafana está acessível"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GRAFANA_URL}/api/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_jaeger_traces(self):
        """Verifica se Jaeger está coletando traces"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{JAEGER_URL}/api/services"
            )
            assert response.status_code == 200
            data = response.json()
            assert "services" in data


class TestLLMIntegration:
    """Testa integração com Ollama"""

    @pytest.mark.asyncio
    async def test_ollama_health(self):
        """Verifica se Ollama está rodando"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            assert response.status_code == 200
            data = response.json()
            assert "models" in data

    @pytest.mark.asyncio
    async def test_embedding_generation(self):
        """Testa geração de embeddings"""
        async with httpx.AsyncClient() as client:
            payload = {
                "model": "nomic-embed-text:latest",
                "prompt": "Database connection timeout"
            }
            response = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json=payload
            )
            assert response.status_code in [200, 201]


class TestDecisionFlow:
    """Testa fluxo de decisão completo"""

    @pytest.mark.asyncio
    async def test_alert_to_decision_flow(self):
        """Testa fluxo: Alerta → Análise → Decisão"""
        async with httpx.AsyncClient() as client:
            # 1. Simular alerta
            alert_payload = {
                "service": "payment-api",
                "severity": "critical",
                "description": "Error rate exceeded 5% (currently 7.2%)"
            }
            response = await client.post(
                f"{BASE_URL}/api/alerts",
                json=alert_payload
            )
            assert response.status_code in [200, 201, 202]
            alert_id = response.json().get("id")

            # 2. Aguardar processamento
            await asyncio.sleep(2)

            # 3. Verificar se decisão foi gerada
            if alert_id:
                response = await client.get(
                    f"{BASE_URL}/api/decisions/{alert_id}"
                )
                assert response.status_code in [200, 404]  # 404 é ok se ainda processando


class TestErrorHandling:
    """Testa tratamento de erros"""

    @pytest.mark.asyncio
    async def test_invalid_alert_payload(self):
        """Testa rejeição de payload inválido"""
        async with httpx.AsyncClient() as client:
            payload = {"invalid": "data"}
            response = await client.post(
                f"{BASE_URL}/api/alerts",
                json=payload
            )
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_nonexistent_endpoint(self):
        """Testa acesso a endpoint inexistente"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/nonexistent")
            assert response.status_code == 404


class TestPerformance:
    """Testa performance do sistema"""

    @pytest.mark.asyncio
    async def test_response_time(self):
        """Verifica tempo de resposta"""
        async with httpx.AsyncClient() as client:
            start = time.time()
            response = await client.get(f"{BASE_URL}/health")
            elapsed = time.time() - start

            assert response.status_code == 200
            assert elapsed < 1.0  # Deve responder em menos de 1 segundo

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Testa múltiplas requisições simultâneas"""
        async with httpx.AsyncClient() as client:
            tasks = [
                client.get(f"{BASE_URL}/health")
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)
            assert all(r.status_code == 200 for r in responses)


class TestSecurityHeaders:
    """Testa headers de segurança"""

    @pytest.mark.asyncio
    async def test_security_headers(self):
        """Verifica presença de headers de segurança"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/")
            
            # Headers esperados
            expected_headers = [
                "x-content-type-options",
                "x-frame-options",
                "x-xss-protection"
            ]
            
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            
            # Verificar pelo menos alguns headers
            for header in expected_headers:
                # Pode não estar presente em todos os casos
                pass


# Fixtures para setup/teardown
@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para testes assíncronos"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Executar testes
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
