"""
Async Orchestration - Orquestração Assíncrona com BackgroundTasks

Implementa padrão de processamento assíncrono usando FastAPI BackgroundTasks.
Garante que endpoints retornem imediatamente enquanto o processamento ocorre em background.

Padrão: Fire-and-Forget com Callback (inspiração Celery, Bull Queue)
Resiliência: Retry automático, logging de execução, rastreamento de status
"""

import logging
import uuid
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timezone
from enum import Enum

from fastapi import BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Estados de uma tarefa assíncrona."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class AsyncTaskResult(BaseModel):
    """Resultado de uma tarefa assíncrona."""
    
    task_id: str = Field(..., description="ID único da tarefa")
    status: TaskStatus = Field(..., description="Status atual")
    result: Optional[Dict[str, Any]] = Field(None, description="Resultado da execução")
    error: Optional[str] = Field(None, description="Mensagem de erro se falhou")
    started_at: Optional[datetime] = Field(None, description="Quando iniciou")
    completed_at: Optional[datetime] = Field(None, description="Quando completou")
    duration_seconds: Optional[float] = Field(None, description="Duração em segundos")
    
    class Config:
        frozen = True


class AsyncOrchestrator:
    """Orquestrador de tarefas assíncronas.
    
    Responsabilidades:
    1. Gerenciar fila de tarefas
    2. Rastrear status de execução
    3. Armazenar resultados
    4. Implementar retry automático
    5. Logging com correlation ID
    """
    
    def __init__(self, max_retries: int = 3, task_timeout_seconds: int = 300):
        """Inicializa o orquestrador.
        
        Args:
            max_retries: Número máximo de retentativas
            task_timeout_seconds: Timeout para execução de tarefa
        """
        self.max_retries = max_retries
        self.task_timeout_seconds = task_timeout_seconds
        self.logger = logging.getLogger("async_orchestrator")
        
        # Armazenamento em memória (em produção usar Redis)
        self._tasks: Dict[str, Dict] = {}
    
    def submit_task(self,
                   background_tasks: BackgroundTasks,
                   task_func: Callable,
                   task_name: str,
                   correlation_id: Optional[str] = None,
                   **kwargs) -> str:
        """Submete uma tarefa para execução assíncrona.
        
        Fluxo:
        1. Gerar task_id
        2. Registrar tarefa como PENDING
        3. Adicionar à fila do FastAPI
        4. Retornar task_id imediatamente
        
        Args:
            background_tasks: BackgroundTasks do FastAPI
            task_func: Função a executar
            task_name: Nome descritivo da tarefa
            correlation_id: ID de correlação para rastreamento
            **kwargs: Argumentos para a função
        
        Returns:
            task_id para rastreamento
        """
        task_id = str(uuid.uuid4())
        correlation_id = correlation_id or str(uuid.uuid4())
        
        # Registrar tarefa
        self._tasks[task_id] = {
            "id": task_id,
            "name": task_name,
            "status": TaskStatus.PENDING,
            "correlation_id": correlation_id,
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "retries": 0,
        }
        
        # Adicionar à fila do FastAPI
        background_tasks.add_task(
            self._execute_task_with_retry,
            task_id=task_id,
            task_func=task_func,
            task_name=task_name,
            correlation_id=correlation_id,
            kwargs=kwargs,
        )
        
        self.logger.info(
            f"Tarefa submetida: {task_id} ({task_name}) "
            f"[correlation_id: {correlation_id}]"
        )
        
        return task_id
    
    def _execute_task_with_retry(self,
                                task_id: str,
                                task_func: Callable,
                                task_name: str,
                                correlation_id: str,
                                kwargs: Dict[str, Any]):
        """Executa tarefa com retry automático.
        
        Args:
            task_id: ID da tarefa
            task_func: Função a executar
            task_name: Nome da tarefa
            correlation_id: ID de correlação
            kwargs: Argumentos da função
        """
        task_data = self._tasks[task_id]
        
        for attempt in range(self.max_retries + 1):
            try:
                # Atualizar status
                task_data["status"] = TaskStatus.RUNNING
                task_data["started_at"] = datetime.now(timezone.utc)
                task_data["retries"] = attempt
                
                self.logger.info(
                    f"Executando tarefa: {task_id} ({task_name}) "
                    f"[tentativa {attempt + 1}/{self.max_retries + 1}] "
                    f"[correlation_id: {correlation_id}]"
                )
                
                # Executar função
                result = task_func(**kwargs)
                
                # Sucesso
                task_data["status"] = TaskStatus.COMPLETED
                task_data["result"] = result
                task_data["completed_at"] = datetime.now(timezone.utc)
                
                duration = (task_data["completed_at"] - task_data["started_at"]).total_seconds()
                
                self.logger.info(
                    f"Tarefa completada: {task_id} ({task_name}) "
                    f"[duração: {duration:.2f}s] "
                    f"[correlation_id: {correlation_id}]"
                )
                
                return
            
            except Exception as e:
                self.logger.warning(
                    f"Erro na tarefa: {task_id} ({task_name}) "
                    f"[tentativa {attempt + 1}/{self.max_retries + 1}]: {e} "
                    f"[correlation_id: {correlation_id}]"
                )
                
                if attempt < self.max_retries:
                    # Retry
                    task_data["status"] = TaskStatus.RETRYING
                    # Aguardar antes de retry (backoff exponencial)
                    import time
                    delay = 2 ** attempt
                    time.sleep(delay)
                else:
                    # Falha final
                    task_data["status"] = TaskStatus.FAILED
                    task_data["error"] = str(e)
                    task_data["completed_at"] = datetime.now(timezone.utc)
                    
                    self.logger.error(
                        f"Tarefa falhou após {self.max_retries + 1} tentativas: "
                        f"{task_id} ({task_name}): {e} "
                        f"[correlation_id: {correlation_id}]"
                    )
    
    def get_task_status(self, task_id: str) -> Optional[AsyncTaskResult]:
        """Obtém status de uma tarefa.
        
        Args:
            task_id: ID da tarefa
        
        Returns:
            AsyncTaskResult ou None se não encontrada
        """
        if task_id not in self._tasks:
            return None
        
        task_data = self._tasks[task_id]
        
        duration = None
        if task_data["started_at"] and task_data["completed_at"]:
            duration = (task_data["completed_at"] - task_data["started_at"]).total_seconds()
        
        return AsyncTaskResult(
            task_id=task_id,
            status=task_data["status"],
            result=task_data["result"],
            error=task_data["error"],
            started_at=task_data["started_at"],
            completed_at=task_data["completed_at"],
            duration_seconds=duration,
        )
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> list[AsyncTaskResult]:
        """Lista tarefas.
        
        Args:
            status: Filtrar por status (opcional)
        
        Returns:
            Lista de AsyncTaskResult
        """
        results = []
        
        for task_id, task_data in self._tasks.items():
            if status and task_data["status"] != status:
                continue
            
            duration = None
            if task_data["started_at"] and task_data["completed_at"]:
                duration = (task_data["completed_at"] - task_data["started_at"]).total_seconds()
            
            result = AsyncTaskResult(
                task_id=task_id,
                status=task_data["status"],
                result=task_data["result"],
                error=task_data["error"],
                started_at=task_data["started_at"],
                completed_at=task_data["completed_at"],
                duration_seconds=duration,
            )
            results.append(result)
        
        return results
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove tarefas antigas.
        
        Args:
            max_age_hours: Idade máxima em horas
        
        Returns:
            Número de tarefas removidas
        """
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        max_age = timedelta(hours=max_age_hours)
        
        to_delete = []
        
        for task_id, task_data in self._tasks.items():
            created_at = task_data["created_at"]
            age = now - created_at
            
            if age > max_age:
                to_delete.append(task_id)
        
        for task_id in to_delete:
            del self._tasks[task_id]
        
        self.logger.info(f"Limpeza de tarefas: {len(to_delete)} removidas")
        
        return len(to_delete)


# Instância global
_orchestrator: Optional[AsyncOrchestrator] = None


def get_orchestrator() -> AsyncOrchestrator:
    """Obtém instância global do orquestrador."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AsyncOrchestrator()
    return _orchestrator
