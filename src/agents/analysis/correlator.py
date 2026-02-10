"""
Correlator Agent - Análise de Correlação entre Domínios (Produção)

Correlaciona sinais de diferentes domínios (logs vs métricas, traces vs eventos)
para identificar causas raiz de incidentes usando fontes de dados reais.

Integrações:
- Prometheus: Métricas de infraestrutura e aplicação
- Kubernetes API: Logs de pods e eventos de cluster
- Jaeger (Futuro): Traces distribuídos
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType
from src.tools.prometheus_client import PrometheusClient
from src.tools.kubectl_client import KubectlMCPClient

logger = logging.getLogger(__name__)


class CorrelationType(str, Enum):
    """Tipos de correlação detectadas."""
    LOG_METRIC_CORRELATION = "LOG_METRIC_CORRELATION"
    TRACE_EVENT_CORRELATION = "TRACE_EVENT_CORRELATION"
    METRIC_METRIC_CORRELATION = "METRIC_METRIC_CORRELATION"
    EVENT_SEQUENCE_CORRELATION = "EVENT_SEQUENCE_CORRELATION"
    TEMPORAL_CORRELATION = "TEMPORAL_CORRELATION"


class CorrelationStrength(str, Enum):
    """Força da correlação detectada."""
    VERY_STRONG = "VERY_STRONG"  # > 0.9
    STRONG = "STRONG"             # 0.7 - 0.9
    MODERATE = "MODERATE"         # 0.5 - 0.7
    WEAK = "WEAK"                 # 0.3 - 0.5
    VERY_WEAK = "VERY_WEAK"       # < 0.3


class CorrelationPattern:
    """Representa um padrão de correlação detectado."""
    
    def __init__(
        self,
        correlation_type: CorrelationType,
        source_domain_1: str,
        source_domain_2: str,
        correlation_strength: float,
        description: str,
        evidence_items: List[EvidenceItem],
        suggested_action: str
    ):
        self.correlation_type = correlation_type
        self.source_domain_1 = source_domain_1
        self.source_domain_2 = source_domain_2
        self.correlation_strength = correlation_strength
        self.description = description
        self.evidence_items = evidence_items
        self.suggested_action = suggested_action
    
    def get_strength_label(self) -> CorrelationStrength:
        """Retorna o rótulo de força da correlação."""
        if self.correlation_strength > 0.9:
            return CorrelationStrength.VERY_STRONG
        elif self.correlation_strength > 0.7:
            return CorrelationStrength.STRONG
        elif self.correlation_strength > 0.5:
            return CorrelationStrength.MODERATE
        elif self.correlation_strength > 0.3:
            return CorrelationStrength.WEAK
        else:
            return CorrelationStrength.VERY_WEAK


class CorrelatorAgent:
    """
    Agente responsável por correlacionar sinais de diferentes domínios usando dados reais.
    """
    
    agent_id = "correlator"
    
    def __init__(self):
        """Inicializa o agente correlator com clientes reais."""
        self.detected_patterns: List[CorrelationPattern] = []
        # Clientes serão inicializados sob demanda ou injetados
        self.prometheus_client = PrometheusClient()
        self.kubectl_client = KubectlMCPClient()
    
    def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        """
        Analisa correlações de sinais para um alerta normalizado.
        """
        logger.info(f"[{self.agent_id}] Correlacionando sinais para {alert.fingerprint}...")
        
        # Limpar padrões detectados anteriormente
        self.detected_patterns = []
        
        try:
            # Executar análises de correlação com dados reais
            self._analyze_log_metric_correlation(alert)
            self._analyze_metric_metric_correlation(alert)
            self._analyze_temporal_correlation(alert)
            # Trace correlation requer Jaeger client (futuro)
            
        except Exception as e:
            logger.error(f"Erro durante análise de correlação: {e}", exc_info=True)
        
        # Consolidar resultados
        hypothesis, confidence, evidence, suggested_actions = self._consolidate_results(alert)
        
        return SwarmResult(
            agent_id=self.agent_id,
            hypothesis=hypothesis,
            confidence=confidence,
            evidence=evidence,
            suggested_actions=suggested_actions
        )
    
    def _analyze_log_metric_correlation(self, alert: NormalizedAlert) -> None:
        """
        Analisa correlação entre erros em logs (Kubernetes) e métricas (Prometheus).
        """
        logger.debug(f"Analisando correlação LOG-METRIC para {alert.service}...")
        
        # 1. Buscar logs recentes do pod
        namespace = alert.labels.get("namespace", "default")
        pod_name = alert.labels.get("pod")
        
        if not pod_name:
            # Tentar encontrar pod pelo serviço
            pods = self.kubectl_client.get_pods(namespace=namespace, label_selector=f"app={alert.service}")
            if pods:
                pod_name = pods[0].get("metadata", {}).get("name")
        
        if not pod_name:
            logger.warning(f"Pod não encontrado para serviço {alert.service}")
            return

        logs = self.kubectl_client.get_logs(pod_name=pod_name, namespace=namespace, tail_lines=200)
        
        # Contar erros nos logs
        error_count = logs.lower().count("error") + logs.lower().count("exception")
        
        if error_count == 0:
            return

        # 2. Buscar métricas de latência/erro no Prometheus
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=15)
        
        # Query para taxa de erro HTTP
        error_rate_query = f'rate(http_requests_total{{app="{alert.service}", status=~"5.."}}[5m])'
        metrics_result = self.prometheus_client.query_range(error_rate_query, start_time, end_time)
        
        has_metric_spike = False
        if metrics_result.get("result"):
            values = metrics_result["result"][0].get("values", [])
            # Verificar se houve aumento recente
            if values:
                recent_values = [float(v[1]) for v in values[-3:]] # Últimos 3 pontos
                if recent_values and max(recent_values) > 0.01: # Threshold arbitrário para exemplo
                    has_metric_spike = True
        
        # 3. Correlacionar
        if has_metric_spike:
            correlation_strength = 0.95 # Alta confiança pois ambos indicam erro
            
            evidence = [
                EvidenceItem(
                    type=EvidenceType.LOG,
                    description=f"Detectados {error_count} erros nos logs do pod {pod_name}",
                    source_url=f"kubectl logs {pod_name}",
                    timestamp=datetime.now(timezone.utc)
                ),
                EvidenceItem(
                    type=EvidenceType.METRIC,
                    description="Pico na taxa de erros HTTP (5xx) detectado no Prometheus",
                    source_url=f"{self.prometheus_client.base_url}/graph?g0.expr={error_rate_query}",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
            
            pattern = CorrelationPattern(
                correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
                source_domain_1="LOGS",
                source_domain_2="METRICS",
                correlation_strength=correlation_strength,
                description=f"Erros nos logs coincidem com aumento na taxa de erros HTTP para {alert.service}",
                evidence_items=evidence,
                suggested_action="Investigar stack traces nos logs e verificar dependências do serviço"
            )
            
            self.detected_patterns.append(pattern)

    def _analyze_metric_metric_correlation(self, alert: NormalizedAlert) -> None:
        """
        Analisa correlação entre CPU e Memória usando dados reais do Prometheus.
        """
        logger.debug(f"Analisando correlação METRIC-METRIC para {alert.service}...")
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=30)
        
        # Queries
        cpu_query = f'rate(container_cpu_usage_seconds_total{{pod=~"{alert.service}.*"}}[5m])'
        mem_query = f'container_memory_working_set_bytes{{pod=~"{alert.service}.*"}}'
        
        cpu_data = self.prometheus_client.query_range(cpu_query, start_time, end_time)
        mem_data = self.prometheus_client.query_range(mem_query, start_time, end_time)
        
        if not cpu_data.get("result") or not mem_data.get("result"):
            return
            
        # Extrair séries temporais (simplificado: pega a primeira série retornada)
        cpu_values = [float(v[1]) for v in cpu_data["result"][0]["values"]]
        mem_values = [float(v[1]) for v in mem_data["result"][0]["values"]]
        
        # Normalizar tamanhos para correlação (truncar para o menor tamanho)
        min_len = min(len(cpu_values), len(mem_values))
        if min_len < 5: # Precisa de dados suficientes
            return
            
        cpu_series = np.array(cpu_values[:min_len])
        mem_series = np.array(mem_values[:min_len])
        
        # Calcular correlação de Pearson
        correlation_matrix = np.corrcoef(cpu_series, mem_series)
        correlation = correlation_matrix[0, 1]
        
        if correlation > 0.7: # Forte correlação positiva
            evidence = [
                EvidenceItem(
                    type=EvidenceType.METRIC,
                    description=f"Correlação de Pearson detectada: {correlation:.2f} entre CPU e Memória",
                    source_url=f"{self.prometheus_client.base_url}/graph?g0.expr={cpu_query}&g1.expr={mem_query}",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
            
            pattern = CorrelationPattern(
                correlation_type=CorrelationType.METRIC_METRIC_CORRELATION,
                source_domain_1="CPU",
                source_domain_2="MEMORY",
                correlation_strength=float(correlation),
                description=f"Uso de CPU e Memória fortemente correlacionados ({correlation:.2f}) para {alert.service}",
                evidence_items=evidence,
                suggested_action="Investigar operações intensivas de processamento de dados ou memory leaks"
            )
            
            self.detected_patterns.append(pattern)

    def _analyze_temporal_correlation(self, alert: NormalizedAlert) -> None:
        """
        Analisa correlação temporal com eventos do Kubernetes (ex: Deployments).
        """
        # Simplificação: Verificar se houve restart recente do pod
        namespace = alert.labels.get("namespace", "default")
        pod_name = alert.labels.get("pod")
        
        if not pod_name:
             # Tentar encontrar pod pelo serviço
            pods = self.kubectl_client.get_pods(namespace=namespace, label_selector=f"app={alert.service}")
            if pods:
                pod_name = pods[0].get("metadata", {}).get("name")
        
        if not pod_name:
            return

        # Verificar restarts
        # Assumindo que get_pods retorna json completo
        pods = self.kubectl_client.get_pods(namespace=namespace, label_selector=f"metadata.name={pod_name}")
        
        if not pods:
            # Tentar buscar todos os pods e filtrar (caso label selector não funcione como esperado no mock)
            pods = self.kubectl_client.get_pods(namespace=namespace)
            pods = [p for p in pods if p.get("metadata", {}).get("name") == pod_name]
            
        if not pods:
            return
            
        pod = pods[0]
        container_statuses = pod.get("status", {}).get("containerStatuses", [])
        
        restart_count = 0
        last_restart_time = None
        
        for status in container_statuses:
            restart_count += status.get("restartCount", 0)
            state = status.get("lastState", {})
            if "terminated" in state:
                finished_at = state["terminated"].get("finishedAt")
                if finished_at:
                    # Parse timestamp (ex: 2023-10-27T10:00:00Z)
                    try:
                        dt = datetime.strptime(finished_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        last_restart_time = dt
                    except ValueError:
                        pass

        if restart_count > 0 and last_restart_time:
            # Verificar se restart foi recente (últimos 30 min)
            if (datetime.now(timezone.utc) - last_restart_time) < timedelta(minutes=30):
                evidence = [
                    EvidenceItem(
                        type=EvidenceType.DOCUMENT,
                        description=f"Pod reiniciado {restart_count} vezes. Último restart: {last_restart_time}",
                        source_url=f"kubectl describe pod {pod_name}",
                        timestamp=last_restart_time
                    )
                ]
                
                pattern = CorrelationPattern(
                    correlation_type=CorrelationType.TEMPORAL_CORRELATION,
                    source_domain_1="POD_LIFECYCLE",
                    source_domain_2="ALERT_TIMING",
                    correlation_strength=0.85,
                    description=f"Alerta coincide com restart recente do pod {pod_name}",
                    evidence_items=evidence,
                    suggested_action="Verificar logs anteriores ao crash (kubectl logs --previous)"
                )
                
                self.detected_patterns.append(pattern)

    def _consolidate_results(self, alert: NormalizedAlert) -> Tuple[str, float, List[EvidenceItem], List[str]]:
        """
        Consolida resultados de todas as análises de correlação.
        """
        if not self.detected_patterns:
            return (
                f"Nenhuma correlação significativa detectada para {alert.service} nos dados analisados.",
                0.0,
                [],
                ["Continuar monitorando", "Verificar integridade dos coletores de métricas"]
            )
        
        # Ordenar padrões por força de correlação
        sorted_patterns = sorted(
            self.detected_patterns,
            key=lambda p: p.correlation_strength,
            reverse=True
        )
        
        strongest_pattern = sorted_patterns[0]
        
        hypothesis_parts = [
            f"Correlação detectada ({strongest_pattern.correlation_type.value}): ",
            strongest_pattern.description
        ]
        
        if len(sorted_patterns) > 1:
            hypothesis_parts.append(f"\nOutras {len(sorted_patterns) - 1} correlações detectadas.")
        
        hypothesis = "".join(hypothesis_parts)
        avg_confidence = sum(p.correlation_strength for p in sorted_patterns) / len(sorted_patterns)
        
        all_evidence = []
        for pattern in sorted_patterns:
            all_evidence.extend(pattern.evidence_items)
        
        suggested_actions = list(set([p.suggested_action for p in sorted_patterns])) # Dedup
        
        return hypothesis, avg_confidence, all_evidence, suggested_actions
