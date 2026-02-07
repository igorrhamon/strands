"""
Observability Metrics - Métricas Prometheus e Tracing Distribuído

Implementa coleta de métricas, tracing distribuído e alertas para
observabilidade completa do sistema Strands.

Padrão: Prometheus Metrics + OpenTelemetry Tracing
Resiliência: Retry automático, fallback local
"""

import logging
import time
from typing import Dict, Optional, Callable, Any
from functools import wraps
from datetime import datetime, timezone
from enum import Enum

try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
except ImportError:
    Counter = Histogram = Gauge = CollectorRegistry = None

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Tipos de métrica."""
    COUNTER = "counter"            # Incrementa
    HISTOGRAM = "histogram"        # Distribuição
    GAUGE = "gauge"                # Valor instantâneo


class AlertSeverity(str, Enum):
    """Severidade de alerta."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PrometheusMetrics:
    """Gerenciador de métricas Prometheus.
    
    Responsabilidades:
    1. Coletar métricas de execução
    2. Rastrear latência
    3. Contar erros
    4. Monitorar recursos
    """
    
    def __init__(self, namespace: str = "strands"):
        """Inicializa o gerenciador.
        
        Args:
            namespace: Namespace para as métricas
        """
        self.namespace = namespace
        self.logger = logging.getLogger("prometheus_metrics")
        self._metrics: Dict[str, Any] = {}
        self._alerts: list = []
        
        # Inicializar métricas
        self._init_metrics()
    
    def _init_metrics(self):
        """Inicializa métricas padrão."""
        if Counter is None:
            self.logger.warning("Prometheus client not installed")
            return
        
        # Contadores
        self._metrics["agent_executions_total"] = Counter(
            f"{self.namespace}_agent_executions_total",
            "Total de execuções de agentes",
            ["agent_name", "status"]
        )
        
        self._metrics["decisions_total"] = Counter(
            f"{self.namespace}_decisions_total",
            "Total de decisões tomadas",
            ["decision_type", "status"]
        )
        
        self._metrics["hallucinations_total"] = Counter(
            f"{self.namespace}_hallucinations_total",
            "Total de alucinações detectadas",
            ["severity"]
        )
        
        # Histogramas
        self._metrics["agent_execution_duration"] = Histogram(
            f"{self.namespace}_agent_execution_duration_seconds",
            "Duração da execução do agente",
            ["agent_name"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0)
        )
        
        self._metrics["decision_latency"] = Histogram(
            f"{self.namespace}_decision_latency_seconds",
            "Latência da tomada de decisão",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0)
        )
        
        self._metrics["neo4j_query_duration"] = Histogram(
            f"{self.namespace}_neo4j_query_duration_seconds",
            "Duração de queries Neo4j",
            ["query_type"],
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0)
        )
        
        # Gauges
        self._metrics["active_agents"] = Gauge(
            f"{self.namespace}_active_agents",
            "Número de agentes ativos"
        )
        
        self._metrics["pending_decisions"] = Gauge(
            f"{self.namespace}_pending_decisions",
            "Número de decisões pendentes"
        )
        
        self._metrics["hallucination_rate"] = Gauge(
            f"{self.namespace}_hallucination_rate",
            "Taxa de alucinação (%)"
        )
    
    def record_agent_execution(self,
                              agent_name: str,
                              duration_seconds: float,
                              status: str = "success",
                              error: Optional[str] = None):
        """Registra execução de agente.
        
        Args:
            agent_name: Nome do agente
            duration_seconds: Duração em segundos
            status: Status (success, error, timeout)
            error: Mensagem de erro (se houver)
        """
        if self._metrics.get("agent_executions_total"):
            self._metrics["agent_executions_total"].labels(
                agent_name=agent_name,
                status=status
            ).inc()
        
        if self._metrics.get("agent_execution_duration"):
            self._metrics["agent_execution_duration"].labels(
                agent_name=agent_name
            ).observe(duration_seconds)
        
        self.logger.info(
            f"Agent execution: {agent_name} | "
            f"duration={duration_seconds:.3f}s | "
            f"status={status}"
        )
        
        # Verificar SLA
        if duration_seconds > 5.0:
            self._create_alert(
                AlertSeverity.WARNING,
                f"Agent {agent_name} exceeded SLA: {duration_seconds:.2f}s > 5s"
            )
    
    def record_decision(self,
                       decision_type: str,
                       duration_seconds: float,
                       confidence: float,
                       status: str = "approved"):
        """Registra tomada de decisão.
        
        Args:
            decision_type: Tipo de decisão
            duration_seconds: Duração em segundos
            confidence: Score de confiança
            status: Status (approved, rejected, escalated)
        """
        if self._metrics.get("decisions_total"):
            self._metrics["decisions_total"].labels(
                decision_type=decision_type,
                status=status
            ).inc()
        
        if self._metrics.get("decision_latency"):
            self._metrics["decision_latency"].observe(duration_seconds)
        
        self.logger.info(
            f"Decision recorded: type={decision_type} | "
            f"duration={duration_seconds:.3f}s | "
            f"confidence={confidence:.2f} | "
            f"status={status}"
        )
        
        # Alertar se confiança baixa
        if confidence < 0.5:
            self._create_alert(
                AlertSeverity.WARNING,
                f"Low confidence decision: {confidence:.2f} < 0.5"
            )
    
    def record_hallucination(self,
                            agent_name: str,
                            severity: str,
                            divergence_percentage: float):
        """Registra detecção de alucinação.
        
        Args:
            agent_name: Nome do agente
            severity: Severidade (low, medium, high, critical)
            divergence_percentage: Divergência em percentual
        """
        if self._metrics.get("hallucinations_total"):
            self._metrics["hallucinations_total"].labels(
                severity=severity
            ).inc()
        
        self.logger.warning(
            f"Hallucination detected: agent={agent_name} | "
            f"severity={severity} | "
            f"divergence={divergence_percentage:.1f}%"
        )
        
        # Criar alerta
        alert_severity = {
            "low": AlertSeverity.INFO,
            "medium": AlertSeverity.WARNING,
            "high": AlertSeverity.CRITICAL,
            "critical": AlertSeverity.CRITICAL,
        }.get(severity, AlertSeverity.WARNING)
        
        self._create_alert(
            alert_severity,
            f"Hallucination in {agent_name}: {divergence_percentage:.1f}% divergence"
        )
    
    def record_neo4j_query(self,
                          query_type: str,
                          duration_seconds: float,
                          success: bool = True):
        """Registra query Neo4j.
        
        Args:
            query_type: Tipo de query
            duration_seconds: Duração em segundos
            success: Sucesso?
        """
        if self._metrics.get("neo4j_query_duration"):
            self._metrics["neo4j_query_duration"].labels(
                query_type=query_type
            ).observe(duration_seconds)
        
        status = "success" if success else "error"
        self.logger.debug(
            f"Neo4j query: type={query_type} | "
            f"duration={duration_seconds:.3f}s | "
            f"status={status}"
        )
        
        # Alertar se lento
        if duration_seconds > 1.0:
            self._create_alert(
                AlertSeverity.WARNING,
                f"Slow Neo4j query: {query_type} took {duration_seconds:.2f}s"
            )
    
    def update_active_agents(self, count: int):
        """Atualiza número de agentes ativos.
        
        Args:
            count: Número de agentes
        """
        if self._metrics.get("active_agents"):
            self._metrics["active_agents"].set(count)
    
    def update_pending_decisions(self, count: int):
        """Atualiza número de decisões pendentes.
        
        Args:
            count: Número de decisões
        """
        if self._metrics.get("pending_decisions"):
            self._metrics["pending_decisions"].set(count)
    
    def update_hallucination_rate(self, rate_percentage: float):
        """Atualiza taxa de alucinação.
        
        Args:
            rate_percentage: Taxa em percentual
        """
        if self._metrics.get("hallucination_rate"):
            self._metrics["hallucination_rate"].set(rate_percentage)
        
        # Alertar se taxa alta
        if rate_percentage > 10:
            self._create_alert(
                AlertSeverity.CRITICAL,
                f"High hallucination rate: {rate_percentage:.1f}% > 10%"
            )
    
    def _create_alert(self, severity: AlertSeverity, message: str):
        """Cria alerta.
        
        Args:
            severity: Severidade
            message: Mensagem
        """
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity.value,
            "message": message,
        }
        
        self._alerts.append(alert)
        
        # Log baseado em severidade
        if severity == AlertSeverity.CRITICAL:
            self.logger.critical(f"🚨 CRITICAL: {message}")
        elif severity == AlertSeverity.WARNING:
            self.logger.warning(f"⚠️ WARNING: {message}")
        else:
            self.logger.info(f"ℹ️ INFO: {message}")
    
    def get_alerts(self, severity: Optional[AlertSeverity] = None) -> list:
        """Obtém alertas.
        
        Args:
            severity: Filtrar por severidade (opcional)
        
        Returns:
            Lista de alertas
        """
        if severity:
            return [a for a in self._alerts if a["severity"] == severity.value]
        return self._alerts
    
    def clear_alerts(self):
        """Limpa alertas."""
        self._alerts.clear()


def track_execution_time(metric_name: str, labels: Optional[Dict] = None):
    """Decorator para rastrear tempo de execução.
    
    Args:
        metric_name: Nome da métrica
        labels: Labels adicionais
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                logger.debug(
                    f"Execution time: {metric_name} = {duration:.3f}s"
                )
        return wrapper
    return decorator


def track_errors(func: Callable) -> Callable:
    """Decorator para rastrear erros.
    
    Args:
        func: Função a rastrear
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Error in {func.__name__}: {str(e)}",
                exc_info=True
            )
            raise
    return wrapper
