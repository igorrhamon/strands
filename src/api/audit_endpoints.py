"""
Audit Endpoints - Endpoints FastAPI para Auditoria

Expõe funcionalidades de auditoria através de API REST com
validação, tratamento de erros e documentação automática.

Padrão: RESTful API + Async Processing
Resiliência: Validação de entrada, error handling, rate limiting
"""

import logging
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditRequestDTO(BaseModel):
    """DTO para requisição de auditoria."""
    
    execution_id: str = Field(..., description="ID da execução a auditar")
    include_recommendations: bool = Field(True, description="Incluir recomendações?")
    include_lineage: bool = Field(True, description="Incluir linhagem?")
    
    class Config:
        schema_extra = {
            "example": {
                "execution_id": "exec_123",
                "include_recommendations": True,
                "include_lineage": True,
            }
        }


class ReplayAuditRequestDTO(BaseModel):
    """DTO para requisição de replay com auditoria."""
    
    execution_id: str = Field(..., description="ID da execução a replayar")
    run_audit: bool = Field(True, description="Executar auditoria após replay?")
    save_results: bool = Field(True, description="Salvar resultados?")
    
    class Config:
        schema_extra = {
            "example": {
                "execution_id": "exec_123",
                "run_audit": True,
                "save_results": True,
            }
        }


class AuditResponseDTO(BaseModel):
    """DTO para resposta de auditoria."""
    
    audit_id: str = Field(..., description="ID único da auditoria")
    execution_id: str = Field(..., description="ID da execução auditada")
    audit_timestamp: datetime = Field(..., description="Quando foi auditada")
    overall_risk_level: str = Field(..., description="Nível de risco geral")
    coherence_score: float = Field(..., ge=0, le=1, description="Score de coerência")
    loop_detected: bool = Field(..., description="Loop detectado?")
    findings_count: int = Field(..., description="Número de achados")
    critical_findings: int = Field(..., description="Achados críticos")
    recommendations: Optional[List[str]] = Field(None, description="Recomendações")
    summary: str = Field(..., description="Resumo executivo")
    
    class Config:
        schema_extra = {
            "example": {
                "audit_id": "audit_abc123",
                "execution_id": "exec_123",
                "audit_timestamp": "2026-02-06T10:30:00Z",
                "overall_risk_level": "medium",
                "coherence_score": 0.75,
                "loop_detected": False,
                "findings_count": 2,
                "critical_findings": 0,
                "recommendations": ["Revisar prompt", "Aumentar timeout"],
                "summary": "Execução com risco médio...",
            }
        }


class ReplayAuditResponseDTO(BaseModel):
    """DTO para resposta de replay com auditoria."""
    
    original_execution_id: str = Field(..., description="ID da execução original")
    replay_execution_id: str = Field(..., description="ID da execução de replay")
    success: bool = Field(..., description="Replay bem-sucedido?")
    confidence_improvement: float = Field(..., description="Melhora de confiança")
    coherence_improvement: float = Field(..., description="Melhora de coerência")
    recommendation: str = Field(..., description="Recomendação de ação")
    original_audit: dict = Field(..., description="Auditoria original")
    replay_audit: dict = Field(..., description="Auditoria de replay")
    
    class Config:
        schema_extra = {
            "example": {
                "original_execution_id": "exec_123",
                "replay_execution_id": "exec_124",
                "success": True,
                "confidence_improvement": 0.15,
                "coherence_improvement": 0.10,
                "recommendation": "✅ BOM: Considerar aplicar com monitoramento",
                "original_audit": {},
                "replay_audit": {},
            }
        }


class TaskStatusDTO(BaseModel):
    """DTO para status de tarefa."""
    
    task_id: str = Field(..., description="ID da tarefa")
    status: str = Field(..., description="Status (pending, running, completed, failed)")
    created_at: datetime = Field(..., description="Quando foi criada")
    updated_at: datetime = Field(..., description="Última atualização")
    result: Optional[dict] = Field(None, description="Resultado (se completo)")
    error: Optional[str] = Field(None, description="Erro (se falhou)")
    
    class Config:
        schema_extra = {
            "example": {
                "task_id": "task_abc123",
                "status": "completed",
                "created_at": "2026-02-06T10:30:00Z",
                "updated_at": "2026-02-06T10:31:00Z",
                "result": {},
                "error": None,
            }
        }


class AuditRouter:
    """Router de endpoints de auditoria."""
    
    def __init__(self,
                 auditor_agent: object,
                 replay_audit_orchestrator: object):
        """Inicializa o router.
        
        Args:
            auditor_agent: Agente de auditoria
            replay_audit_orchestrator: Orquestrador de replay-audit
        """
        self.auditor_agent = auditor_agent
        self.replay_audit_orchestrator = replay_audit_orchestrator
        self.logger = logging.getLogger("audit_router")
        self.router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
        self._register_routes()
        self._task_store = {}  # Armazenar status de tarefas
    
    def _register_routes(self):
        """Registra rotas."""
        self.router.add_api_route(
            "/execute",
            self.execute_audit,
            methods=["POST"],
            response_model=AuditResponseDTO,
            summary="Executar auditoria",
            description="Audita uma execução e retorna relatório",
        )
        
        self.router.add_api_route(
            "/execute-async",
            self.execute_audit_async,
            methods=["POST"],
            response_model=TaskStatusDTO,
            summary="Executar auditoria assincronamente",
            description="Audita uma execução em background",
        )
        
        self.router.add_api_route(
            "/replay",
            self.execute_replay_audit,
            methods=["POST"],
            response_model=ReplayAuditResponseDTO,
            summary="Executar replay com auditoria",
            description="Executa replay e audita resultado",
        )
        
        self.router.add_api_route(
            "/replay-async",
            self.execute_replay_audit_async,
            methods=["POST"],
            response_model=TaskStatusDTO,
            summary="Executar replay com auditoria assincronamente",
            description="Executa replay e audita resultado em background",
        )
        
        self.router.add_api_route(
            "/task/{task_id}",
            self.get_task_status,
            methods=["GET"],
            response_model=TaskStatusDTO,
            summary="Obter status de tarefa",
            description="Retorna status de uma tarefa assíncrona",
        )
        
        self.router.add_api_route(
            "/history",
            self.get_audit_history,
            methods=["GET"],
            summary="Obter histórico de auditorias",
            description="Retorna histórico de auditorias recentes",
        )
    
    async def execute_audit(self, request: AuditRequestDTO) -> AuditResponseDTO:
        """Executa auditoria síncrona.
        
        Args:
            request: Requisição de auditoria
        
        Returns:
            AuditResponseDTO
        
        Raises:
            HTTPException: Se execução não encontrada
        """
        self.logger.info(f"Executando auditoria: {request.execution_id}")
        
        try:
            # Executar auditoria
            report = self.auditor_agent.audit_execution(request.execution_id)
            
            # Contar achados por severidade
            critical_findings = sum(
                1 for f in report.findings
                if f.risk_level.value == "critical"
            )
            
            # Construir resposta
            response = AuditResponseDTO(
                audit_id=report.audit_id,
                execution_id=report.execution_id,
                audit_timestamp=report.audit_timestamp,
                overall_risk_level=report.overall_risk_level.value,
                coherence_score=report.coherence_score,
                loop_detected=report.loop_detected,
                findings_count=len(report.findings),
                critical_findings=critical_findings,
                recommendations=report.prompt_refinement_suggestions if request.include_recommendations else None,
                summary=report.summary,
            )
            
            self.logger.info(
                f"Auditoria concluída: {request.execution_id} | "
                f"risk_level={response.overall_risk_level} | "
                f"findings={response.findings_count}"
            )
            
            return response
        
        except ValueError as e:
            self.logger.error(f"Execução não encontrada: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            self.logger.error(f"Erro ao executar auditoria: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def execute_audit_async(self,
                                 request: AuditRequestDTO,
                                 background_tasks: BackgroundTasks) -> TaskStatusDTO:
        """Executa auditoria assincronamente.
        
        Args:
            request: Requisição de auditoria
            background_tasks: Gerenciador de tarefas background
        
        Returns:
            TaskStatusDTO com status inicial
        """
        import uuid
        
        task_id = f"audit_{uuid.uuid4().hex[:12]}"
        
        self.logger.info(f"Criando tarefa assíncrona: {task_id}")
        
        # Criar entrada de tarefa
        self._task_store[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "result": None,
            "error": None,
        }
        
        # Agendar tarefa
        background_tasks.add_task(
            self._execute_audit_background,
            task_id,
            request.execution_id,
            request.include_recommendations,
        )
        
        return TaskStatusDTO(
            task_id=task_id,
            status="pending",
            created_at=self._task_store[task_id]["created_at"],
            updated_at=self._task_store[task_id]["updated_at"],
            result=None,
            error=None,
        )
    
    def _execute_audit_background(self,
                                 task_id: str,
                                 execution_id: str,
                                 include_recommendations: bool):
        """Executa auditoria em background.
        
        Args:
            task_id: ID da tarefa
            execution_id: ID da execução
            include_recommendations: Incluir recomendações?
        """
        try:
            self._task_store[task_id]["status"] = "running"
            self._task_store[task_id]["updated_at"] = datetime.now(timezone.utc)
            
            # Executar auditoria
            report = self.auditor_agent.audit_execution(execution_id)
            
            # Contar achados
            critical_findings = sum(
                1 for f in report.findings
                if f.risk_level.value == "critical"
            )
            
            # Armazenar resultado
            self._task_store[task_id]["result"] = {
                "audit_id": report.audit_id,
                "execution_id": report.execution_id,
                "overall_risk_level": report.overall_risk_level.value,
                "coherence_score": report.coherence_score,
                "loop_detected": report.loop_detected,
                "findings_count": len(report.findings),
                "critical_findings": critical_findings,
                "recommendations": report.prompt_refinement_suggestions if include_recommendations else None,
            }
            
            self._task_store[task_id]["status"] = "completed"
            self._task_store[task_id]["updated_at"] = datetime.now(timezone.utc)
            
            self.logger.info(f"Tarefa concluída: {task_id}")
        
        except Exception as e:
            self._task_store[task_id]["status"] = "failed"
            self._task_store[task_id]["error"] = str(e)
            self._task_store[task_id]["updated_at"] = datetime.now(timezone.utc)
            
            self.logger.error(f"Erro em tarefa: {task_id} - {e}")
    
    async def execute_replay_audit(self,
                                  request: ReplayAuditRequestDTO) -> ReplayAuditResponseDTO:
        """Executa replay com auditoria síncrona.
        
        Args:
            request: Requisição de replay-audit
        
        Returns:
            ReplayAuditResponseDTO
        
        Raises:
            HTTPException: Se execução não encontrada
        """
        self.logger.info(f"Executando replay com auditoria: {request.execution_id}")
        
        try:
            # Executar replay com auditoria
            result = await self.replay_audit_orchestrator.run_replay_with_audit(
                request.execution_id,
                run_audit=request.run_audit
            )
            
            if not result:
                raise ValueError("Falha ao executar replay")
            
            # Construir resposta
            response = ReplayAuditResponseDTO(
                original_execution_id=result.original_execution_id,
                replay_execution_id=result.replay_execution_id,
                success=result.success,
                confidence_improvement=result.confidence_improvement,
                coherence_improvement=result.coherence_improvement,
                recommendation=result.recommendation,
                original_audit=result.original_audit_report,
                replay_audit=result.replay_audit_report,
            )
            
            self.logger.info(
                f"Replay concluído: {request.execution_id} → {result.replay_execution_id} | "
                f"success={response.success}"
            )
            
            return response
        
        except ValueError as e:
            self.logger.error(f"Erro ao executar replay: {e}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            self.logger.error(f"Erro inesperado: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def execute_replay_audit_async(self,
                                        request: ReplayAuditRequestDTO,
                                        background_tasks: BackgroundTasks) -> TaskStatusDTO:
        """Executa replay com auditoria assincronamente.
        
        Args:
            request: Requisição de replay-audit
            background_tasks: Gerenciador de tarefas background
        
        Returns:
            TaskStatusDTO com status inicial
        """
        import uuid
        
        task_id = f"replay_{uuid.uuid4().hex[:12]}"
        
        self.logger.info(f"Criando tarefa de replay: {task_id}")
        
        # Criar entrada de tarefa
        self._task_store[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "result": None,
            "error": None,
        }
        
        # Agendar tarefa
        background_tasks.add_task(
            self._execute_replay_audit_background,
            task_id,
            request.execution_id,
            request.run_audit,
        )
        
        return TaskStatusDTO(
            task_id=task_id,
            status="pending",
            created_at=self._task_store[task_id]["created_at"],
            updated_at=self._task_store[task_id]["updated_at"],
            result=None,
            error=None,
        )
    
    def _execute_replay_audit_background(self,
                                        task_id: str,
                                        execution_id: str,
                                        run_audit: bool):
        """Executa replay com auditoria em background.
        
        Args:
            task_id: ID da tarefa
            execution_id: ID da execução
            run_audit: Executar auditoria?
        """
        import asyncio
        
        try:
            self._task_store[task_id]["status"] = "running"
            self._task_store[task_id]["updated_at"] = datetime.now(timezone.utc)
            
            # Executar replay com auditoria
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.replay_audit_orchestrator.run_replay_with_audit(
                    execution_id,
                    run_audit=run_audit
                )
            )
            
            if not result:
                raise ValueError("Falha ao executar replay")
            
            # Armazenar resultado
            self._task_store[task_id]["result"] = {
                "original_execution_id": result.original_execution_id,
                "replay_execution_id": result.replay_execution_id,
                "success": result.success,
                "confidence_improvement": result.confidence_improvement,
                "coherence_improvement": result.coherence_improvement,
                "recommendation": result.recommendation,
            }
            
            self._task_store[task_id]["status"] = "completed"
            self._task_store[task_id]["updated_at"] = datetime.now(timezone.utc)
            
            self.logger.info(f"Tarefa de replay concluída: {task_id}")
        
        except Exception as e:
            self._task_store[task_id]["status"] = "failed"
            self._task_store[task_id]["error"] = str(e)
            self._task_store[task_id]["updated_at"] = datetime.now(timezone.utc)
            
            self.logger.error(f"Erro em tarefa de replay: {task_id} - {e}")
    
    async def get_task_status(self, task_id: str) -> TaskStatusDTO:
        """Obtém status de uma tarefa.
        
        Args:
            task_id: ID da tarefa
        
        Returns:
            TaskStatusDTO
        
        Raises:
            HTTPException: Se tarefa não encontrada
        """
        if task_id not in self._task_store:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        
        task = self._task_store[task_id]
        
        return TaskStatusDTO(
            task_id=task["task_id"],
            status=task["status"],
            created_at=task["created_at"],
            updated_at=task["updated_at"],
            result=task["result"],
            error=task["error"],
        )
    
    async def get_audit_history(self,
                               limit: int = Query(10, ge=1, le=100),
                               offset: int = Query(0, ge=0)) -> dict:
        """Obtém histórico de auditorias.
        
        Args:
            limit: Número máximo de resultados
            offset: Deslocamento
        
        Returns:
            Dicionário com histórico
        """
        # Retornar tarefas completadas recentes
        completed_tasks = [
            t for t in self._task_store.values()
            if t["status"] == "completed"
        ]
        
        # Ordenar por data decrescente
        completed_tasks.sort(key=lambda x: x["updated_at"], reverse=True)
        
        # Aplicar paginação
        paginated = completed_tasks[offset:offset + limit]
        
        return {
            "total": len(completed_tasks),
            "limit": limit,
            "offset": offset,
            "tasks": paginated,
        }
    
    def get_router(self):
        """Retorna o router.
        
        Returns:
            APIRouter
        """
        return self.router
