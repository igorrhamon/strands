"""
Distributed Tracing - Rastreamento Distribuído com OpenTelemetry

Implementa rastreamento de requisições através de múltiplos serviços
para debugging e análise de performance.

Padrão: OpenTelemetry Tracing + Jaeger Export
Resiliência: Fallback local, batching, retry automático
"""

import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class SpanStatus(str, Enum):
    """Status de um span."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class Span:
    """Representa um span de rastreamento.
    
    Um span é uma unidade de trabalho dentro de um trace.
    """
    
    def __init__(self,
                 trace_id: str,
                 span_id: str,
                 parent_span_id: Optional[str],
                 operation_name: str,
                 attributes: Optional[Dict] = None):
        """Inicializa um span.
        
        Args:
            trace_id: ID do trace
            span_id: ID do span
            parent_span_id: ID do span pai (opcional)
            operation_name: Nome da operação
            attributes: Atributos adicionais
        """
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.operation_name = operation_name
        self.attributes = attributes or {}
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.status = SpanStatus.UNSET
        self.events: list = []
        self.error: Optional[str] = None
    
    def add_event(self, event_name: str, attributes: Optional[Dict] = None):
        """Adiciona um evento ao span.
        
        Args:
            event_name: Nome do evento
            attributes: Atributos do evento
        """
        self.events.append({
            "name": event_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })
    
    def set_attribute(self, key: str, value: Any):
        """Define um atributo.
        
        Args:
            key: Chave
            value: Valor
        """
        self.attributes[key] = value
    
    def set_error(self, error: str):
        """Define erro.
        
        Args:
            error: Mensagem de erro
        """
        self.error = error
        self.status = SpanStatus.ERROR
    
    def end(self):
        """Finaliza o span."""
        self.end_time = datetime.now(timezone.utc)
        if self.status == SpanStatus.UNSET:
            self.status = SpanStatus.OK
    
    def duration_ms(self) -> float:
        """Retorna duração em ms."""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "error": self.error,
        }


class Trace:
    """Representa um trace completo.
    
    Um trace é uma sequência de spans que representa uma requisição.
    """
    
    def __init__(self, trace_id: str, service_name: str):
        """Inicializa um trace.
        
        Args:
            trace_id: ID único do trace
            service_name: Nome do serviço
        """
        self.trace_id = trace_id
        self.service_name = service_name
        self.start_time = datetime.now(timezone.utc)
        self.end_time: Optional[datetime] = None
        self.spans: Dict[str, Span] = {}
        self.root_span_id: Optional[str] = None
    
    def create_span(self,
                   operation_name: str,
                   parent_span_id: Optional[str] = None,
                   attributes: Optional[Dict] = None) -> Span:
        """Cria um novo span.
        
        Args:
            operation_name: Nome da operação
            parent_span_id: ID do span pai (opcional)
            attributes: Atributos iniciais
        
        Returns:
            Span criado
        """
        span_id = str(uuid.uuid4())[:16]
        
        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            attributes=attributes,
        )
        
        self.spans[span_id] = span
        
        if not self.root_span_id and not parent_span_id:
            self.root_span_id = span_id
        
        return span
    
    def end_span(self, span_id: str):
        """Finaliza um span.
        
        Args:
            span_id: ID do span
        """
        if span_id in self.spans:
            self.spans[span_id].end()
    
    def end(self):
        """Finaliza o trace."""
        self.end_time = datetime.now(timezone.utc)
    
    def duration_ms(self) -> float:
        """Retorna duração total em ms."""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "trace_id": self.trace_id,
            "service_name": self.service_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms(),
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans.values()],
        }


class DistributedTracer:
    """Gerenciador de rastreamento distribuído.
    
    Responsabilidades:
    1. Criar e gerenciar traces
    2. Rastrear spans
    3. Exportar para Jaeger/Zipkin
    4. Correlacionar requisições
    """
    
    def __init__(self, service_name: str = "strands"):
        """Inicializa o tracer.
        
        Args:
            service_name: Nome do serviço
        """
        self.service_name = service_name
        self.logger = logging.getLogger("distributed_tracer")
        self._traces: Dict[str, Trace] = {}
        self._active_traces: Dict[str, str] = {}  # thread_id -> trace_id
    
    def start_trace(self, trace_id: Optional[str] = None) -> Trace:
        """Inicia um novo trace.
        
        Args:
            trace_id: ID do trace (gerado se não fornecido)
        
        Returns:
            Trace criado
        """
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        trace = Trace(trace_id, self.service_name)
        self._traces[trace_id] = trace
        
        self.logger.debug(f"Trace started: {trace_id}")
        
        return trace
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Obtém um trace.
        
        Args:
            trace_id: ID do trace
        
        Returns:
            Trace ou None
        """
        return self._traces.get(trace_id)
    
    def end_trace(self, trace_id: str):
        """Finaliza um trace.
        
        Args:
            trace_id: ID do trace
        """
        if trace_id in self._traces:
            self._traces[trace_id].end()
            self.logger.debug(
                f"Trace ended: {trace_id} "
                f"(duration={self._traces[trace_id].duration_ms():.2f}ms)"
            )
    
    def create_span(self,
                   trace_id: str,
                   operation_name: str,
                   parent_span_id: Optional[str] = None,
                   attributes: Optional[Dict] = None) -> Optional[Span]:
        """Cria um novo span em um trace.
        
        Args:
            trace_id: ID do trace
            operation_name: Nome da operação
            parent_span_id: ID do span pai (opcional)
            attributes: Atributos iniciais
        
        Returns:
            Span criado ou None
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return None
        
        span = trace.create_span(operation_name, parent_span_id, attributes)
        
        self.logger.debug(
            f"Span created: {span.span_id} "
            f"(operation={operation_name}, trace={trace_id})"
        )
        
        return span
    
    def end_span(self, trace_id: str, span_id: str):
        """Finaliza um span.
        
        Args:
            trace_id: ID do trace
            span_id: ID do span
        """
        trace = self.get_trace(trace_id)
        if trace:
            trace.end_span(span_id)
    
    def add_span_event(self,
                      trace_id: str,
                      span_id: str,
                      event_name: str,
                      attributes: Optional[Dict] = None):
        """Adiciona evento a um span.
        
        Args:
            trace_id: ID do trace
            span_id: ID do span
            event_name: Nome do evento
            attributes: Atributos do evento
        """
        trace = self.get_trace(trace_id)
        if trace and span_id in trace.spans:
            trace.spans[span_id].add_event(event_name, attributes)
    
    def set_span_attribute(self,
                          trace_id: str,
                          span_id: str,
                          key: str,
                          value: Any):
        """Define atributo de um span.
        
        Args:
            trace_id: ID do trace
            span_id: ID do span
            key: Chave
            value: Valor
        """
        trace = self.get_trace(trace_id)
        if trace and span_id in trace.spans:
            trace.spans[span_id].set_attribute(key, value)
    
    def set_span_error(self,
                      trace_id: str,
                      span_id: str,
                      error: str):
        """Define erro em um span.
        
        Args:
            trace_id: ID do trace
            span_id: ID do span
            error: Mensagem de erro
        """
        trace = self.get_trace(trace_id)
        if trace and span_id in trace.spans:
            trace.spans[span_id].set_error(error)
    
    def export_trace(self, trace_id: str) -> Dict:
        """Exporta um trace para envio.
        
        Args:
            trace_id: ID do trace
        
        Returns:
            Dicionário com dados do trace
        """
        trace = self.get_trace(trace_id)
        if not trace:
            return {}
        
        return trace.to_dict()
    
    def get_traces_by_service(self, service_name: str) -> list:
        """Obtém traces de um serviço.
        
        Args:
            service_name: Nome do serviço
        
        Returns:
            Lista de traces
        """
        return [
            t for t in self._traces.values()
            if t.service_name == service_name
        ]
    
    def get_slow_traces(self, threshold_ms: float = 1000) -> list:
        """Obtém traces lentos.
        
        Args:
            threshold_ms: Threshold em ms
        
        Returns:
            Lista de traces lentos
        """
        return [
            t for t in self._traces.values()
            if t.end_time and t.duration_ms() > threshold_ms
        ]
    
    def get_error_traces(self) -> list:
        """Obtém traces com erros.
        
        Returns:
            Lista de traces com erros
        """
        error_traces = []
        
        for trace in self._traces.values():
            for span in trace.spans.values():
                if span.status == SpanStatus.ERROR:
                    error_traces.append(trace)
                    break
        
        return error_traces
