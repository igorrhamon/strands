"""
Main Audit Integration - Integração de Auditoria na Aplicação FastAPI

Configura e integra todos os componentes de auditoria na aplicação principal.

Padrão: Dependency Injection + Factory Pattern
Resiliência: Inicialização segura, validação de dependências
"""

import logging
from typing import Optional

from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class AuditDependencies:
    """Gerenciador de dependências de auditoria."""
    
    _instance: Optional["AuditDependencies"] = None
    _auditor_agent: Optional[object] = None
    _replay_audit_orchestrator: Optional[object] = None
    _audit_router: Optional[object] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self,
                  auditor_agent: object,
                  replay_audit_orchestrator: object):
        """Inicializa dependências.
        
        Args:
            auditor_agent: Agente de auditoria
            replay_audit_orchestrator: Orquestrador de replay-audit
        """
        self._auditor_agent = auditor_agent
        self._replay_audit_orchestrator = replay_audit_orchestrator
        
        logger.info("Dependências de auditoria inicializadas")
    
    def get_auditor_agent(self) -> object:
        """Obtém agente de auditoria.
        
        Returns:
            AuditorAgent
        
        Raises:
            RuntimeError: Se não inicializado
        """
        if self._auditor_agent is None:
            raise RuntimeError("AuditorAgent não inicializado")
        return self._auditor_agent
    
    def get_replay_audit_orchestrator(self) -> object:
        """Obtém orquestrador de replay-audit.
        
        Returns:
            ReplayAuditOrchestrator
        
        Raises:
            RuntimeError: Se não inicializado
        """
        if self._replay_audit_orchestrator is None:
            raise RuntimeError("ReplayAuditOrchestrator não inicializado")
        return self._replay_audit_orchestrator
    
    def get_audit_router(self) -> object:
        """Obtém router de auditoria.
        
        Returns:
            AuditRouter
        
        Raises:
            RuntimeError: Se não inicializado
        """
        if self._audit_router is None:
            from src.api.audit_endpoints import AuditRouter
            
            self._audit_router = AuditRouter(
                auditor_agent=self.get_auditor_agent(),
                replay_audit_orchestrator=self.get_replay_audit_orchestrator(),
            )
        
        return self._audit_router


def get_audit_dependencies() -> AuditDependencies:
    """Dependency injection para AuditDependencies.
    
    Returns:
        AuditDependencies singleton
    """
    return AuditDependencies()


def setup_audit_integration(app: FastAPI,
                           auditor_agent: object,
                           replay_audit_orchestrator: object) -> None:
    """Configura integração de auditoria na aplicação.
    
    Args:
        app: Aplicação FastAPI
        auditor_agent: Agente de auditoria
        replay_audit_orchestrator: Orquestrador de replay-audit
    """
    logger.info("Configurando integração de auditoria")
    
    # Inicializar dependências
    dependencies = AuditDependencies()
    dependencies.initialize(auditor_agent, replay_audit_orchestrator)
    
    # Obter router de auditoria
    audit_router = dependencies.get_audit_router()
    
    # Incluir router na aplicação
    app.include_router(audit_router.get_router())
    
    logger.info("Integração de auditoria configurada com sucesso")
    logger.info("Endpoints disponíveis:")
    logger.info("  POST   /api/v1/audit/execute")
    logger.info("  POST   /api/v1/audit/execute-async")
    logger.info("  POST   /api/v1/audit/replay")
    logger.info("  POST   /api/v1/audit/replay-async")
    logger.info("  GET    /api/v1/audit/task/{task_id}")
    logger.info("  GET    /api/v1/audit/history")


@asynccontextmanager
async def audit_lifespan(app: FastAPI):
    """Lifespan context manager para auditoria.
    
    Args:
        app: Aplicação FastAPI
    
    Yields:
        None
    """
    # Startup
    logger.info("Iniciando componentes de auditoria")
    
    yield
    
    # Shutdown
    logger.info("Encerrando componentes de auditoria")


class AuditMiddleware:
    """Middleware para logging estruturado de auditoria."""
    
    def __init__(self, app: FastAPI):
        """Inicializa middleware.
        
        Args:
            app: Aplicação FastAPI
        """
        self.app = app
        self.logger = logging.getLogger("audit_middleware")
    
    async def __call__(self, scope, receive, send):
        """Processa requisição.
        
        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extrair informações da requisição
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        # Log de requisição
        if path.startswith("/api/v1/audit"):
            self.logger.info(f"Audit Request: {method} {path}")
        
        # Processar requisição
        await self.app(scope, receive, send)


def add_audit_middleware(app: FastAPI) -> None:
    """Adiciona middleware de auditoria.
    
    Args:
        app: Aplicação FastAPI
    """
    app.add_middleware(AuditMiddleware)
    logger.info("Middleware de auditoria adicionado")


class AuditHealthCheck:
    """Health check para componentes de auditoria."""
    
    def __init__(self, dependencies: AuditDependencies):
        """Inicializa health check.
        
        Args:
            dependencies: Dependências de auditoria
        """
        self.dependencies = dependencies
        self.logger = logging.getLogger("audit_health_check")
    
    async def check_health(self) -> dict:
        """Verifica saúde dos componentes.
        
        Returns:
            Dicionário com status
        """
        status = {
            "auditor_agent": "unknown",
            "replay_audit_orchestrator": "unknown",
            "audit_router": "unknown",
        }
        
        try:
            # Verificar AuditorAgent
            auditor = self.dependencies.get_auditor_agent()
            status["auditor_agent"] = "healthy" if auditor else "unhealthy"
        except Exception as e:
            self.logger.error(f"Erro ao verificar AuditorAgent: {e}")
            status["auditor_agent"] = "unhealthy"
        
        try:
            # Verificar ReplayAuditOrchestrator
            orchestrator = self.dependencies.get_replay_audit_orchestrator()
            status["replay_audit_orchestrator"] = "healthy" if orchestrator else "unhealthy"
        except Exception as e:
            self.logger.error(f"Erro ao verificar ReplayAuditOrchestrator: {e}")
            status["replay_audit_orchestrator"] = "unhealthy"
        
        try:
            # Verificar AuditRouter
            router = self.dependencies.get_audit_router()
            status["audit_router"] = "healthy" if router else "unhealthy"
        except Exception as e:
            self.logger.error(f"Erro ao verificar AuditRouter: {e}")
            status["audit_router"] = "unhealthy"
        
        # Status geral
        all_healthy = all(v == "healthy" for v in status.values())
        status["overall"] = "healthy" if all_healthy else "degraded"
        
        return status


def add_audit_health_check(app: FastAPI, dependencies: AuditDependencies) -> None:
    """Adiciona health check de auditoria.
    
    Args:
        app: Aplicação FastAPI
        dependencies: Dependências de auditoria
    """
    health_check = AuditHealthCheck(dependencies)
    
    @app.get("/health/audit", tags=["health"])
    async def audit_health():
        """Health check de auditoria."""
        return await health_check.check_health()
    
    logger.info("Health check de auditoria adicionado: GET /health/audit")


# Exemplo de uso em main.py
"""
from fastapi import FastAPI
from src.api.main_audit_integration import (
    setup_audit_integration,
    add_audit_middleware,
    add_audit_health_check,
    get_audit_dependencies,
)
from src.agents.auditor_agent import AuditorAgent
from src.integration.replay_audit_integration import ReplayAuditOrchestrator

app = FastAPI()

# Inicializar componentes
auditor_agent = AuditorAgent(neo4j_adapter)
replay_audit_orchestrator = ReplayAuditOrchestrator(replay_engine, auditor_agent)

# Configurar integração
setup_audit_integration(app, auditor_agent, replay_audit_orchestrator)
add_audit_middleware(app)

# Adicionar health check
dependencies = get_audit_dependencies()
add_audit_health_check(app, dependencies)

# Iniciar aplicação
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
