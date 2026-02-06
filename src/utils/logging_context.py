"""
Logging Context - Rastreamento Distribuído com Correlation ID

Implementa contexto de logging para rastreamento de requisições através de múltiplos serviços.
Cada log inclui correlation_id, plan_id, thread_id para facilitar debugging no Grafana.

Padrão: Distributed Tracing (inspiração OpenTelemetry, Jaeger)
Resiliência: Context-local storage, thread-safe
"""

import logging
import uuid
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime, timezone

# Context vars thread-safe
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')
_plan_id: ContextVar[str] = ContextVar('plan_id', default='')
_thread_id: ContextVar[str] = ContextVar('thread_id', default='')
_user_id: ContextVar[str] = ContextVar('user_id', default='')
_request_id: ContextVar[str] = ContextVar('request_id', default='')


class CorrelationIdFilter(logging.Filter):
    """Filter que adiciona correlation_id aos logs.
    
    Adiciona os seguintes campos ao LogRecord:
    - correlation_id: ID de correlação para rastreamento distribuído
    - plan_id: ID do plano de execução
    - thread_id: ID da thread de execução
    - user_id: ID do usuário
    - request_id: ID da requisição
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Adiciona contexto ao registro de log.
        
        Args:
            record: LogRecord do logging
        
        Returns:
            True para permitir o log
        """
        record.correlation_id = _correlation_id.get() or 'N/A'
        record.plan_id = _plan_id.get() or 'N/A'
        record.thread_id = _thread_id.get() or 'N/A'
        record.user_id = _user_id.get() or 'N/A'
        record.request_id = _request_id.get() or 'N/A'
        
        return True


class LoggingContext:
    """Gerenciador de contexto de logging.
    
    Responsabilidades:
    1. Gerar e gerenciar correlation_id
    2. Armazenar contexto thread-safe
    3. Fornecer métodos de acesso
    4. Limpar contexto quando necessário
    """
    
    @staticmethod
    def set_correlation_id(correlation_id: Optional[str] = None) -> str:
        """Define correlation_id.
        
        Args:
            correlation_id: ID de correlação (gera novo se não fornecido)
        
        Returns:
            correlation_id definido
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        
        _correlation_id.set(correlation_id)
        return correlation_id
    
    @staticmethod
    def get_correlation_id() -> str:
        """Obtém correlation_id atual.
        
        Returns:
            correlation_id ou string vazia
        """
        return _correlation_id.get()
    
    @staticmethod
    def set_plan_id(plan_id: str) -> str:
        """Define plan_id.
        
        Args:
            plan_id: ID do plano
        
        Returns:
            plan_id definido
        """
        _plan_id.set(plan_id)
        return plan_id
    
    @staticmethod
    def get_plan_id() -> str:
        """Obtém plan_id atual.
        
        Returns:
            plan_id ou string vazia
        """
        return _plan_id.get()
    
    @staticmethod
    def set_thread_id(thread_id: str) -> str:
        """Define thread_id.
        
        Args:
            thread_id: ID da thread
        
        Returns:
            thread_id definido
        """
        _thread_id.set(thread_id)
        return thread_id
    
    @staticmethod
    def get_thread_id() -> str:
        """Obtém thread_id atual.
        
        Returns:
            thread_id ou string vazia
        """
        return _thread_id.get()
    
    @staticmethod
    def set_user_id(user_id: str) -> str:
        """Define user_id.
        
        Args:
            user_id: ID do usuário
        
        Returns:
            user_id definido
        """
        _user_id.set(user_id)
        return user_id
    
    @staticmethod
    def get_user_id() -> str:
        """Obtém user_id atual.
        
        Returns:
            user_id ou string vazia
        """
        return _user_id.get()
    
    @staticmethod
    def set_request_id(request_id: Optional[str] = None) -> str:
        """Define request_id.
        
        Args:
            request_id: ID da requisição (gera novo se não fornecido)
        
        Returns:
            request_id definido
        """
        if not request_id:
            request_id = str(uuid.uuid4())
        
        _request_id.set(request_id)
        return request_id
    
    @staticmethod
    def get_request_id() -> str:
        """Obtém request_id atual.
        
        Returns:
            request_id ou string vazia
        """
        return _request_id.get()
    
    @staticmethod
    def get_context() -> Dict[str, str]:
        """Obtém contexto completo.
        
        Returns:
            Dicionário com todos os valores de contexto
        """
        return {
            "correlation_id": _correlation_id.get(),
            "plan_id": _plan_id.get(),
            "thread_id": _thread_id.get(),
            "user_id": _user_id.get(),
            "request_id": _request_id.get(),
        }
    
    @staticmethod
    def set_context(context: Dict[str, str]):
        """Define contexto completo.
        
        Args:
            context: Dicionário com valores de contexto
        """
        if "correlation_id" in context:
            _correlation_id.set(context["correlation_id"])
        if "plan_id" in context:
            _plan_id.set(context["plan_id"])
        if "thread_id" in context:
            _thread_id.set(context["thread_id"])
        if "user_id" in context:
            _user_id.set(context["user_id"])
        if "request_id" in context:
            _request_id.set(context["request_id"])
    
    @staticmethod
    def clear_context():
        """Limpa todo o contexto."""
        _correlation_id.set('')
        _plan_id.set('')
        _thread_id.set('')
        _user_id.set('')
        _request_id.set('')


class ContextualLogger:
    """Logger que inclui contexto automaticamente.
    
    Exemplo:
        logger = ContextualLogger.get_logger(__name__)
        logger.info("Processando alerta")  # Inclui correlation_id, plan_id, etc
    """
    
    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Obtém logger com contexto.
        
        Args:
            name: Nome do logger
        
        Returns:
            Logger configurado com CorrelationIdFilter
        """
        logger = logging.getLogger(name)
        
        # Adicionar filter se não existir
        if not any(isinstance(f, CorrelationIdFilter) for f in logger.filters):
            logger.addFilter(CorrelationIdFilter())
        
        return logger
    
    @staticmethod
    def configure_logging(log_format: Optional[str] = None):
        """Configura logging com contexto.
        
        Args:
            log_format: Formato customizado (usa padrão se não fornecido)
        """
        if not log_format:
            log_format = (
                '[%(asctime)s] %(levelname)-8s '
                '[correlation_id=%(correlation_id)s] '
                '[plan_id=%(plan_id)s] '
                '[thread_id=%(thread_id)s] '
                '[user_id=%(user_id)s] '
                '%(name)s: %(message)s'
            )
        
        # Configurar root logger
        root_logger = logging.getLogger()
        
        # Remover handlers existentes
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Adicionar handler com formato
        handler = logging.StreamHandler()
        formatter = logging.Formatter(log_format)
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationIdFilter())
        
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)


# Exemplo de uso
def example_usage():
    """Exemplo de como usar o logging context."""
    
    # Configurar logging
    ContextualLogger.configure_logging()
    
    # Obter logger
    logger = ContextualLogger.get_logger(__name__)
    
    # Definir contexto
    LoggingContext.set_correlation_id()
    LoggingContext.set_plan_id("plan_123")
    LoggingContext.set_thread_id("thread_456")
    
    # Logs incluem contexto automaticamente
    logger.info("Iniciando processamento")
    logger.warning("Aviso importante")
    logger.error("Erro encontrado")
    
    # Obter contexto
    context = LoggingContext.get_context()
    print(f"Contexto: {context}")
    
    # Limpar contexto
    LoggingContext.clear_context()
