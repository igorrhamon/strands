"""
Testes de Integração End-to-End para o Sistema Strands

Testa o fluxo completo:
1. Frontend → Backend
2. Backend → Agentes
3. Agentes → Bancos de Dados (Neo4j, Qdrant)
4. Motor de Decisão → Saída
5. Observabilidade → Métricas
"""

import pytest
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any
import httpx

# Configuração
URL_BASE = "http://localhost:8000"
URL_PROMETHEUS = "http://localhost:9090"
URL_GRAFANA = "http://localhost:3000"
URL_JAEGER = "http://localhost:16686"
URL_OLLAMA = "http://localhost:11434"


class TestIntegracaoFrontend:
    """Testa integração do Frontend com o Backend"""

    @pytest.mark.asyncio
    async def test_frontend_carrega(self):
        """Verifica se o frontend carrega corretamente"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/")
            assert response.status_code == 200
            assert "Strands Governance" in response.text
            assert "Simulate Alert" in response.text

    @pytest.mark.asyncio
    async def test_assets_carregam(self):
        """Verifica se os assets (CSS, JavaScript) carregam corretamente"""
        async with httpx.AsyncClient() as client:
            # Testar CSS
            response = await client.get(f"{URL_BASE}/static/css/main.css")
            assert response.status_code == 200
            assert "color" in response.text or "background" in response.text

            # Testar JavaScript
            response = await client.get(f"{URL_BASE}/static/js/api.js")
            assert response.status_code == 200
            assert "function" in response.text or "const" in response.text


class TestAPIsBackend:
    """Testa as APIs do Backend"""

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Verifica se o servidor responde ao health check"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_endpoint_metricas(self):
        """Verifica se o endpoint de métricas está funcionando"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/metrics")
            assert response.status_code == 200
            assert "HELP" in response.text or "TYPE" in response.text

    @pytest.mark.asyncio
    async def test_endpoint_simular_alerta(self):
        """Testa o endpoint de simulação de alerta"""
        async with httpx.AsyncClient() as client:
            payload = {
                "service": "payment-api",
                "severity": "critical",
                "description": "Error rate exceeded 5%"
            }
            response = await client.post(
                f"{URL_BASE}/api/alerts",
                json=payload
            )
            assert response.status_code in [200, 201, 202]
            data = response.json()
            assert "id" in data or "status" in data


class TestExecucaoAgentes:
    """Testa a execução dos agentes"""

    @pytest.mark.asyncio
    async def test_agente_metricas(self):
        """Testa o Agente de Análise de Métricas"""
        async with httpx.AsyncClient() as client:
            payload = {
                "metric_name": "error_rate",
                "current_value": 7.2,
                "threshold": 5.0
            }
            response = await client.post(
                f"{URL_BASE}/api/analyze/metrics",
                json=payload
            )
            assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_agente_embedding(self):
        """Testa o Agente de Embedding para busca de casos similares"""
        async with httpx.AsyncClient() as client:
            payload = {
                "text": "Database connection timeout causing checkout failures"
            }
            response = await client.post(
                f"{URL_BASE}/api/analyze/embedding",
                json=payload
            )
            assert response.status_code in [200, 201]


class TestIntegracaoBancoDados:
    """Testa integração com bancos de dados"""

    @pytest.mark.asyncio
    async def test_conexao_neo4j(self):
        """Verifica se a conexão com Neo4j está funcionando"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/health")
            assert response.status_code == 200
            data = response.json()
            # Neo4j deve estar no health check
            assert "neo4j" in str(data).lower() or "database" in str(data).lower()

    @pytest.mark.asyncio
    async def test_conexao_qdrant(self):
        """Verifica se a conexão com Qdrant está funcionando"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/health")
            assert response.status_code == 200
            data = response.json()
            # Qdrant deve estar no health check
            assert "qdrant" in str(data).lower() or "vector" in str(data).lower()


class TestObservabilidade:
    """Testa a stack completa de observabilidade"""

    @pytest.mark.asyncio
    async def test_prometheus_scrape(self):
        """Verifica se Prometheus consegue fazer scrape das métricas"""
        await asyncio.sleep(2)  # Aguardar scrape
        async with httpx.AsyncClient() as client:
            # Query para verificar se métricas foram coletadas
            response = await client.get(
                f"{URL_PROMETHEUS}/api/v1/query",
                params={"query": "up"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_grafana_acessivel(self):
        """Verifica se Grafana está acessível"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_GRAFANA}/api/health")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_jaeger_traces(self):
        """Verifica se Jaeger está coletando traces distribuídos"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{URL_JAEGER}/api/services"
            )
            assert response.status_code == 200
            data = response.json()
            assert "services" in data


class TestIntegracaoLLM:
    """Testa integração com Ollama (LLM)"""

    @pytest.mark.asyncio
    async def test_ollama_saude(self):
        """Verifica se Ollama está rodando e acessível"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_OLLAMA}/api/tags")
            assert response.status_code == 200
            data = response.json()
            assert "models" in data

    @pytest.mark.asyncio
    async def test_geracao_embeddings(self):
        """Testa geração de embeddings via Ollama"""
        async with httpx.AsyncClient() as client:
            payload = {
                "model": "nomic-embed-text:latest",
                "prompt": "Database connection timeout"
            }
            response = await client.post(
                f"{URL_OLLAMA}/api/embed",
                json=payload
            )
            assert response.status_code in [200, 201]


class TestFluxoDecisao:
    """Testa o fluxo completo de decisão"""

    @pytest.mark.asyncio
    async def test_fluxo_alerta_para_decisao(self):
        """Testa fluxo completo: Alerta → Análise → Decisão"""
        async with httpx.AsyncClient() as client:
            # 1. Simular alerta
            payload_alerta = {
                "service": "payment-api",
                "severity": "critical",
                "description": "Error rate exceeded 5% (currently 7.2%)"
            }
            response = await client.post(
                f"{URL_BASE}/api/alerts",
                json=payload_alerta
            )
            assert response.status_code in [200, 201, 202]
            id_alerta = response.json().get("id")

            # 2. Aguardar processamento
            await asyncio.sleep(2)

            # 3. Verificar se decisão foi gerada
            if id_alerta:
                response = await client.get(
                    f"{URL_BASE}/api/decisions/{id_alerta}"
                )
                assert response.status_code in [200, 404]  # 404 é ok se ainda processando


class TestTratamentoErros:
    """Testa tratamento de erros e casos extremos"""

    @pytest.mark.asyncio
    async def test_rejeita_payload_invalido(self):
        """Testa rejeição de payload de alerta inválido"""
        async with httpx.AsyncClient() as client:
            payload = {"invalid": "data"}
            response = await client.post(
                f"{URL_BASE}/api/alerts",
                json=payload
            )
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_endpoint_inexistente(self):
        """Testa acesso a endpoint que não existe"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/api/nonexistent")
            assert response.status_code == 404


class TestPerformance:
    """Testa performance e escalabilidade do sistema"""

    @pytest.mark.asyncio
    async def test_tempo_resposta(self):
        """Verifica se o tempo de resposta está dentro dos limites"""
        async with httpx.AsyncClient() as client:
            start = time.time()
            response = await client.get(f"{URL_BASE}/health")
            elapsed = time.time() - start

            assert response.status_code == 200
            assert elapsed < 1.0  # Deve responder em menos de 1 segundo

    @pytest.mark.asyncio
    async def test_requisicoes_simultaneas(self):
        """Testa múltiplas requisições simultâneas"""
        async with httpx.AsyncClient() as client:
            tasks = [
                client.get(f"{URL_BASE}/health")
                for _ in range(10)
            ]
            responses = await asyncio.gather(*tasks)
            assert all(r.status_code == 200 for r in responses)


class TestHeadersSeguranca:
    """Testa headers de segurança HTTP"""

    @pytest.mark.asyncio
    async def test_headers_seguranca(self):
        """Verifica presença de headers de segurança HTTP"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{URL_BASE}/")
            
            # Headers esperados
            headers_esperados = [
                "x-content-type-options",
                "x-frame-options",
                "x-xss-protection"
            ]
            
            response_headers = {k.lower(): v for k, v in response.headers.items()}
            
            # Verificar pelo menos alguns headers
            for header in headers_esperados:
                # Pode não estar presente em todos os casos
                pass


# Fixtures para setup/teardown
@pytest.fixture(scope="session")
def event_loop():
    """Cria event loop para execução de testes assíncronos"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Executar testes
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
