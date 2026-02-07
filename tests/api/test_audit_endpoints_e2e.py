"""
Testes E2E - Endpoints de Auditoria

Testa integração completa dos endpoints de auditoria com FastAPI.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.audit_endpoints import (
    AuditRouter,
    AuditRequestDTO,
    ReplayAuditRequestDTO,
    AuditResponseDTO,
    ReplayAuditResponseDTO,
)
from src.agents.auditor_agent import AuditReport, AuditRiskLevel, ExecutionLineage
from src.auditing.audit_rules import AuditFinding


class TestAuditEndpoints:
    """Testes para endpoints de auditoria."""
    
    @pytest.fixture
    def mock_auditor_agent(self):
        """Cria mock do auditor."""
        agent = Mock()
        
        # Mock do relatório de auditoria
        report = Mock(spec=AuditReport)
        report.audit_id = "audit_123"
        report.execution_id = "exec_123"
        report.audit_timestamp = datetime.now(timezone.utc)
        report.overall_risk_level = AuditRiskLevel.MEDIUM
        report.coherence_score = 0.75
        report.loop_detected = False
        report.findings = [
            Mock(risk_level=Mock(value="medium")),
        ]
        report.prompt_refinement_suggestions = ["Revisar prompt"]
        report.summary = "Execução com risco médio"
        
        agent.audit_execution = Mock(return_value=report)
        return agent
    
    @pytest.fixture
    def mock_replay_audit_orchestrator(self):
        """Cria mock do orquestrador."""
        orchestrator = Mock()
        
        # Mock do resultado de replay
        result = Mock()
        result.original_execution_id = "exec_123"
        result.replay_execution_id = "exec_124"
        result.success = True
        result.confidence_improvement = 0.15
        result.coherence_improvement = 0.10
        result.recommendation = "✅ BOM: Considerar aplicar"
        result.original_audit_report = {}
        result.replay_audit_report = {}
        
        orchestrator.run_replay_with_audit = AsyncMock(return_value=result)
        return orchestrator
    
    @pytest.fixture
    def audit_router(self, mock_auditor_agent, mock_replay_audit_orchestrator):
        """Cria router de auditoria."""
        return AuditRouter(mock_auditor_agent, mock_replay_audit_orchestrator)
    
    @pytest.fixture
    def app(self, audit_router):
        """Cria aplicação FastAPI."""
        app = FastAPI()
        app.include_router(audit_router.get_router())
        return app
    
    @pytest.fixture
    def client(self, app):
        """Cria cliente de teste."""
        return TestClient(app)
    
    def test_execute_audit_success(self, client):
        """Testa execução bem-sucedida de auditoria."""
        response = client.post(
            "/api/v1/audit/execute",
            json={
                "execution_id": "exec_123",
                "include_recommendations": True,
                "include_lineage": True,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == "exec_123"
        assert data["overall_risk_level"] == "medium"
        assert data["coherence_score"] == 0.75
        assert data["loop_detected"] == False
        assert len(data["recommendations"]) > 0
    
    def test_execute_audit_not_found(self, client, mock_auditor_agent):
        """Testa auditoria com execução não encontrada."""
        mock_auditor_agent.audit_execution.side_effect = ValueError("Execução não encontrada")
        
        response = client.post(
            "/api/v1/audit/execute",
            json={
                "execution_id": "exec_not_found",
                "include_recommendations": True,
                "include_lineage": True,
            }
        )
        
        assert response.status_code == 404
    
    def test_execute_audit_async(self, client):
        """Testa execução assíncrona de auditoria."""
        response = client.post(
            "/api/v1/audit/execute-async",
            json={
                "execution_id": "exec_123",
                "include_recommendations": True,
                "include_lineage": True,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "task_id" in data
        assert data["task_id"].startswith("audit_")
    
    @pytest.mark.asyncio
    async def test_execute_replay_audit_success(self, client):
        """Testa execução bem-sucedida de replay com auditoria."""
        response = client.post(
            "/api/v1/audit/replay",
            json={
                "execution_id": "exec_123",
                "run_audit": True,
                "save_results": True,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["original_execution_id"] == "exec_123"
        assert data["replay_execution_id"] == "exec_124"
        assert data["success"] == True
        assert data["confidence_improvement"] == 0.15
    
    def test_execute_replay_audit_async(self, client):
        """Testa execução assíncrona de replay com auditoria."""
        response = client.post(
            "/api/v1/audit/replay-async",
            json={
                "execution_id": "exec_123",
                "run_audit": True,
                "save_results": True,
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "task_id" in data
        assert data["task_id"].startswith("replay_")
    
    def test_get_task_status_pending(self, client):
        """Testa obtenção de status de tarefa pendente."""
        # Primeiro, criar uma tarefa
        response = client.post(
            "/api/v1/audit/execute-async",
            json={
                "execution_id": "exec_123",
                "include_recommendations": True,
                "include_lineage": True,
            }
        )
        
        task_id = response.json()["task_id"]
        
        # Obter status
        response = client.get(f"/api/v1/audit/task/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "pending"
    
    def test_get_task_status_not_found(self, client):
        """Testa obtenção de status de tarefa não encontrada."""
        response = client.get("/api/v1/audit/task/task_not_found")
        
        assert response.status_code == 404
    
    def test_get_audit_history(self, client):
        """Testa obtenção de histórico de auditorias."""
        response = client.get("/api/v1/audit/history?limit=10&offset=0")
        
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "tasks" in data
    
    def test_audit_request_validation(self, client):
        """Testa validação de requisição."""
        # Requisição sem execution_id
        response = client.post(
            "/api/v1/audit/execute",
            json={
                "include_recommendations": True,
            }
        )
        
        assert response.status_code == 422  # Validation error


class TestAuditRouter:
    """Testes para AuditRouter."""
    
    @pytest.fixture
    def mock_auditor_agent(self):
        """Cria mock do auditor."""
        agent = Mock()
        report = Mock(spec=AuditReport)
        report.audit_id = "audit_123"
        report.execution_id = "exec_123"
        report.audit_timestamp = datetime.now(timezone.utc)
        report.overall_risk_level = AuditRiskLevel.MEDIUM
        report.coherence_score = 0.75
        report.loop_detected = False
        report.findings = []
        report.prompt_refinement_suggestions = []
        report.summary = "Test"
        
        agent.audit_execution = Mock(return_value=report)
        return agent
    
    @pytest.fixture
    def mock_replay_audit_orchestrator(self):
        """Cria mock do orquestrador."""
        orchestrator = Mock()
        result = Mock()
        result.original_execution_id = "exec_123"
        result.replay_execution_id = "exec_124"
        result.success = True
        result.confidence_improvement = 0.15
        result.coherence_improvement = 0.10
        result.recommendation = "Test"
        result.original_audit_report = {}
        result.replay_audit_report = {}
        
        orchestrator.run_replay_with_audit = AsyncMock(return_value=result)
        return orchestrator
    
    @pytest.fixture
    def router(self, mock_auditor_agent, mock_replay_audit_orchestrator):
        """Cria router."""
        return AuditRouter(mock_auditor_agent, mock_replay_audit_orchestrator)
    
    def test_router_initialization(self, router):
        """Testa inicialização do router."""
        assert router.auditor_agent is not None
        assert router.replay_audit_orchestrator is not None
        assert router.router is not None
    
    def test_router_has_routes(self, router):
        """Testa se router tem rotas registradas."""
        routes = router.get_router().routes
        assert len(routes) > 0
    
    def test_task_store_isolation(self, router):
        """Testa isolamento de armazenamento de tarefas."""
        router1 = AuditRouter(Mock(), Mock())
        router2 = AuditRouter(Mock(), Mock())
        
        # Cada router deve ter seu próprio task_store
        assert router1._task_store is not router2._task_store


class TestStructuredLogging:
    """Testes para logging estruturado."""
    
    def test_correlation_id_middleware(self):
        """Testa middleware de Correlation ID."""
        from src.utils.structured_logging import CorrelationIdMiddleware, ContextManager
        
        app = FastAPI()
        app.add_middleware(CorrelationIdMiddleware)
        
        client = TestClient(app)
        
        # Requisição sem Correlation ID
        @app.get("/test")
        def test_endpoint():
            return {"correlation_id": ContextManager.get_correlation_id()}
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "x-correlation-id" in response.headers
    
    def test_context_manager(self):
        """Testa gerenciador de contexto."""
        from src.utils.structured_logging import ContextManager
        
        # Limpar contexto
        ContextManager.clear_context()
        
        # Definir Correlation ID
        corr_id = ContextManager.set_correlation_id()
        assert ContextManager.get_correlation_id() == corr_id
        
        # Definir Plan ID
        ContextManager.set_plan_id("plan_123")
        assert ContextManager.get_plan_id() == "plan_123"
        
        # Definir Execution ID
        ContextManager.set_execution_id("exec_123")
        assert ContextManager.get_execution_id() == "exec_123"
        
        # Limpar contexto
        ContextManager.clear_context()
        assert ContextManager.get_correlation_id() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
