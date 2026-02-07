"""
Structured Logging - Logging Estruturado com Correlation ID

Implementa logging estruturado com suporte a Correlation ID para
rastreamento distribuído e integração com Grafana.

Padrão: Structured Logging + Context Propagation
Resiliência: Thread-safe, async-safe, JSON output
"""

import logging
import json
import uuid
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime, timezone
from enum import Enum

# Context variables para rastreamento
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
plan_id_var: ContextVar[str] = ContextVar("plan_id", default="")
execution_id_var: ContextVar[str] = ContextVar("execution_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")


class LogLevel(str, Enum):
    """Níveis de log."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """Logger estruturado com suporte a Correlation ID."""
    
    def __init__(self, name: str):
        """Inicializa logger estruturado.
        
        Args:
            name: Nome do logger
        """
        self.name = name
        self.logger = logging.getLogger(name)
    
    def _get_context(self) -> Dict[str, str]:
        """Obtém contexto atual.
        
        Returns:
            Dicionário com contexto
        """
        return {
            "correlation_id": correlation_id_var.get(),
            "plan_id": plan_id_var.get(),
            "execution_id": execution_id_var.get(),
            "user_id": user_id_var.get(),
        }
    
    def _format_message(self,
                       level: LogLevel,
                       message: str,
                       extra: Optional[Dict[str, Any]] = None) -> str:
        """Formata mensagem estruturada.
        
        Args:
            level: Nível de log
            message: Mensagem
            extra: Dados extras
        
        Returns:
            Mensagem formatada em JSON
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.value,
            "logger": self.name,
            "message": message,
            "context": self._get_context(),
        }
        
        if extra:
            log_entry["extra"] = extra
        
        return json.dumps(log_entry, ensure_ascii=False)
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log em nível DEBUG.
        
        Args:
            message: Mensagem
            extra: Dados extras
        """
        formatted = self._format_message(LogLevel.DEBUG, message, extra)
        self.logger.debug(formatted)
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log em nível INFO.
        
        Args:
            message: Mensagem
            extra: Dados extras
        """
        formatted = self._format_message(LogLevel.INFO, message, extra)
        self.logger.info(formatted)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log em nível WARNING.
        
        Args:
            message: Mensagem
            extra: Dados extras
        """
        formatted = self._format_message(LogLevel.WARNING, message, extra)
        self.logger.warning(formatted)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log em nível ERROR.
        
        Args:
            message: Mensagem
            extra: Dados extras
        """
        formatted = self._format_message(LogLevel.ERROR, message, extra)
        self.logger.error(formatted)
    
    def critical(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log em nível CRITICAL.
        
        Args:
            message: Mensagem
            extra: Dados extras
        """
        formatted = self._format_message(LogLevel.CRITICAL, message, extra)
        self.logger.critical(formatted)
    
    def audit(self,
             action: str,
             resource: str,
             result: str,
             extra: Optional[Dict[str, Any]] = None):
        """Log de auditoria.
        
        Args:
            action: Ação realizada
            resource: Recurso afetado
            result: Resultado (success, failure)
            extra: Dados extras
        """
        audit_data = {
            "action": action,
            "resource": resource,
            "result": result,
        }
        
        if extra:
            audit_data.update(extra)
        
        self.info(f"AUDIT: {action} on {resource}", audit_data)


class ContextManager:
    """Gerenciador de contexto para rastreamento."""
    
    @staticmethod
    def set_correlation_id(correlation_id: Optional[str] = None) -> str:
        """Define Correlation ID.
        
        Args:
            correlation_id: ID customizado (gera novo se None)
        
        Returns:
            Correlation ID definido
        """
        if correlation_id is None:
            correlation_id = f"corr_{uuid.uuid4().hex[:12]}"
        
        correlation_id_var.set(correlation_id)
        return correlation_id
    
    @staticmethod
    def get_correlation_id() -> str:
        """Obtém Correlation ID atual.
        
        Returns:
            Correlation ID
        """
        return correlation_id_var.get()
    
    @staticmethod
    def set_plan_id(plan_id: str):
        """Define Plan ID.
        
        Args:
            plan_id: ID do plano
        """
        plan_id_var.set(plan_id)
    
    @staticmethod
    def get_plan_id() -> str:
        """Obtém Plan ID atual.
        
        Returns:
            Plan ID
        """
        return plan_id_var.get()
    
    @staticmethod
    def set_execution_id(execution_id: str):
        """Define Execution ID.
        
        Args:
            execution_id: ID da execução
        """
        execution_id_var.set(execution_id)
    
    @staticmethod
    def get_execution_id() -> str:
        """Obtém Execution ID atual.
        
        Returns:
            Execution ID
        """
        return execution_id_var.get()
    
    @staticmethod
    def set_user_id(user_id: str):
        """Define User ID.
        
        Args:
            user_id: ID do usuário
        """
        user_id_var.set(user_id)
    
    @staticmethod
    def get_user_id() -> str:
        """Obtém User ID atual.
        
        Returns:
            User ID
        """
        return user_id_var.get()
    
    @staticmethod
    def clear_context():
        """Limpa contexto."""
        correlation_id_var.set("")
        plan_id_var.set("")
        execution_id_var.set("")
        user_id_var.set("")


class AuditLogger:
    """Logger especializado para auditoria."""
    
    def __init__(self, name: str = "audit"):
        """Inicializa audit logger.
        
        Args:
            name: Nome do logger
        """
        self.logger = StructuredLogger(name)
    
    def log_audit_execution(self,
                           execution_id: str,
                           status: str,
                           risk_level: str,
                           findings_count: int,
                           extra: Optional[Dict[str, Any]] = None):
        """Log de execução auditada.
        
        Args:
            execution_id: ID da execução
            status: Status da auditoria
            risk_level: Nível de risco
            findings_count: Número de achados
            extra: Dados extras
        """
        data = {
            "execution_id": execution_id,
            "audit_status": status,
            "risk_level": risk_level,
            "findings_count": findings_count,
        }
        
        if extra:
            data.update(extra)
        
        self.logger.audit(
            action="AUDIT_EXECUTION",
            resource=f"execution:{execution_id}",
            result=status,
            extra=data
        )
    
    def log_replay_audit(self,
                        original_id: str,
                        replay_id: str,
                        success: bool,
                        confidence_improvement: float,
                        extra: Optional[Dict[str, Any]] = None):
        """Log de replay auditado.
        
        Args:
            original_id: ID da execução original
            replay_id: ID da execução de replay
            success: Replay bem-sucedido?
            confidence_improvement: Melhora de confiança
            extra: Dados extras
        """
        data = {
            "original_execution_id": original_id,
            "replay_execution_id": replay_id,
            "success": success,
            "confidence_improvement": confidence_improvement,
        }
        
        if extra:
            data.update(extra)
        
        self.logger.audit(
            action="REPLAY_AUDIT",
            resource=f"execution:{original_id}",
            result="success" if success else "failure",
            extra=data
        )
    
    def log_rule_violation(self,
                          rule_name: str,
                          execution_id: str,
                          severity: str,
                          description: str,
                          extra: Optional[Dict[str, Any]] = None):
        """Log de violação de regra.
        
        Args:
            rule_name: Nome da regra
            execution_id: ID da execução
            severity: Severidade
            description: Descrição
            extra: Dados extras
        """
        data = {
            "rule_name": rule_name,
            "execution_id": execution_id,
            "severity": severity,
            "description": description,
        }
        
        if extra:
            data.update(extra)
        
        self.logger.audit(
            action="RULE_VIOLATION",
            resource=f"rule:{rule_name}",
            result="violation",
            extra=data
        )


# Middleware FastAPI para Correlation ID
class CorrelationIdMiddleware:
    """Middleware para extrair/gerar Correlation ID."""
    
    def __init__(self, app):
        """Inicializa middleware.
        
        Args:
            app: Aplicação FastAPI
        """
        self.app = app
    
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
        
        # Extrair Correlation ID do header
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(b"x-correlation-id", b"").decode()
        
        # Definir Correlation ID (gera novo se não fornecido)
        ContextManager.set_correlation_id(correlation_id or None)
        
        # Extrair Plan ID se fornecido
        plan_id = headers.get(b"x-plan-id", b"").decode()
        if plan_id:
            ContextManager.set_plan_id(plan_id)
        
        # Extrair Execution ID se fornecido
        execution_id = headers.get(b"x-execution-id", b"").decode()
        if execution_id:
            ContextManager.set_execution_id(execution_id)
        
        # Extrair User ID se fornecido
        user_id = headers.get(b"x-user-id", b"").decode()
        if user_id:
            ContextManager.set_user_id(user_id)
        
        # Processar requisição
        async def send_with_correlation(message):
            """Adiciona Correlation ID na resposta."""
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((
                    b"x-correlation-id",
                    ContextManager.get_correlation_id().encode()
                ))
                message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_correlation)


def get_logger(name: str) -> StructuredLogger:
    """Factory para criar StructuredLogger.
    
    Args:
        name: Nome do logger
    
    Returns:
        StructuredLogger
    """
    return StructuredLogger(name)


def get_audit_logger(name: str = "audit") -> AuditLogger:
    """Factory para criar AuditLogger.
    
    Args:
        name: Nome do logger
    
    Returns:
        AuditLogger
    """
    return AuditLogger(name)
