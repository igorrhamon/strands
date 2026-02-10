"""
Observability Layer - Metrics, Structured Logging, Correlation IDs

Implementa observabilidade enterprise com rastreamento de decisões.
"""

import logging
import json
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Tipos de métrica."""
    COUNTER = "COUNTER"           # Incrementa
    GAUGE = "GAUGE"               # Valor instantâneo
    HISTOGRAM = "HISTOGRAM"       # Distribuição
    TIMER = "TIMER"               # Duração


class Metric:
    """Representa uma métrica."""
    
    def __init__(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.name = name
        self.metric_type = metric_type
        self.value = value
        self.labels = labels or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat()
        }


class MetricsCollector:
    """Coleta métricas de agentes."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.metrics: List[Metric] = []
        self._lock = threading.Lock()
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.timers: Dict[str, List[float]] = {}
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None):
        """Incrementa contador."""
        with self._lock:
            key = self._make_key(name, labels)
            self.counters[key] = self.counters.get(key, 0) + value
            
            metric = Metric(name, MetricType.COUNTER, float(self.counters[key]), labels)
            self.metrics.append(metric)
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Define gauge."""
        with self._lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
            
            metric = Metric(name, MetricType.GAUGE, value, labels)
            self.metrics.append(metric)
    
    def record_timer(self, name: str, duration_seconds: float, labels: Optional[Dict[str, str]] = None):
        """Registra duração."""
        with self._lock:
            key = self._make_key(name, labels)
            if key not in self.timers:
                self.timers[key] = []
            self.timers[key].append(duration_seconds)
            
            metric = Metric(name, MetricType.TIMER, duration_seconds, labels)
            self.metrics.append(metric)
    
    @contextmanager
    def measure_time(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager para medir tempo."""
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.record_timer(name, duration, labels)
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Cria chave única para métrica."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_metrics(self) -> List[Dict[str, Any]]:
        """Retorna todas as métricas coletadas."""
        with self._lock:
            return [m.to_dict() for m in self.metrics]
    
    def get_summary(self) -> dict:
        """Retorna resumo de métricas."""
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "total_metrics": len(self.metrics),
                "counters": self.counters,
                "gauges": self.gauges,
                "timers": {
                    k: {
                        "count": len(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "avg": sum(v) / len(v) if v else 0
                    }
                    for k, v in self.timers.items()
                }
            }


class StructuredLogger:
    """Logger estruturado para rastreamento de decisões."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.correlation_id = str(uuid.uuid4())
        self.logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
    
    def log_decision(
        self,
        decision_type: str,
        hypothesis: str,
        confidence: float,
        evidence_count: int,
        suggested_actions: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log estruturado de decisão."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": self.correlation_id,
            "agent_id": self.agent_id,
            "event_type": "DECISION",
            "decision_type": decision_type,
            "hypothesis": hypothesis,
            "confidence": confidence,
            "evidence_count": evidence_count,
            "suggested_actions": suggested_actions,
            "metadata": metadata or {}
        }
        
        with self._lock:
            self.logs.append(log_entry)
        
        logger.info(json.dumps(log_entry))
    
    def log_error(
        self,
        error_type: str,
        message: str,
        exception: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log estruturado de erro."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": self.correlation_id,
            "agent_id": self.agent_id,
            "event_type": "ERROR",
            "error_type": error_type,
            "message": message,
            "exception": str(exception) if exception else None,
            "metadata": metadata or {}
        }
        
        with self._lock:
            self.logs.append(log_entry)
        
        logger.error(json.dumps(log_entry))
    
    def log_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log estruturado de métrica."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "correlation_id": self.correlation_id,
            "agent_id": self.agent_id,
            "event_type": "METRIC",
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "metadata": metadata or {}
        }
        
        with self._lock:
            self.logs.append(log_entry)
        
        logger.info(json.dumps(log_entry))
    
    def get_logs(self) -> List[Dict[str, Any]]:
        """Retorna todos os logs."""
        with self._lock:
            return self.logs.copy()
    
    def get_audit_trail(self) -> dict:
        """Retorna trilha de auditoria."""
        with self._lock:
            decisions = [l for l in self.logs if l.get("event_type") == "DECISION"]
            errors = [l for l in self.logs if l.get("event_type") == "ERROR"]
            
            return {
                "correlation_id": self.correlation_id,
                "agent_id": self.agent_id,
                "total_events": len(self.logs),
                "decisions": len(decisions),
                "errors": len(errors),
                "first_event": self.logs[0]["timestamp"] if self.logs else None,
                "last_event": self.logs[-1]["timestamp"] if self.logs else None,
                "events": self.logs
            }


class ObservabilityContext:
    """Contexto de observabilidade para um agente."""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.metrics = MetricsCollector(agent_id)
        self.logger = StructuredLogger(agent_id)
        self.start_time = datetime.now(timezone.utc)
    
    def get_health_status(self) -> dict:
        """Retorna status de saúde do agente."""
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        return {
            "agent_id": self.agent_id,
            "uptime_seconds": uptime,
            "correlation_id": self.logger.correlation_id,
            "metrics_summary": self.metrics.get_summary(),
            "audit_trail": self.logger.get_audit_trail()
        }
    
    def export_observability(self) -> dict:
        """Exporta todos os dados de observabilidade."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "health": self.get_health_status(),
            "metrics": self.metrics.get_metrics(),
            "logs": self.logger.get_logs()
        }
