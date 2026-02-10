"""
Correlator Agent - Análise de Correlação entre Domínios

Correlaciona sinais de diferentes domínios (logs vs métricas, traces vs eventos)
para identificar causas raiz de incidentes.

Padrões de Correlação Suportados:
1. Logs + Métricas: Picos de erro em logs correlacionam com métricas de latência
2. Traces + Eventos: Falhas em traces correlacionam com eventos de deployment
3. Métricas + Métricas: Correlação entre CPU e memória, requisições e erros
4. Eventos + Eventos: Sequência de eventos que levam a incidente
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType

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
    Agente responsável por correlacionar sinais de diferentes domínios.
    
    Detecta padrões de correlação que indicam causas raiz de incidentes,
    como:
    - Picos de erro em logs que coincidem com latência alta em métricas
    - Falhas em traces distribuídos que coincidem com eventos de deployment
    - Correlação temporal entre múltiplos eventos
    """
    
    agent_id = "correlator"
    
    def __init__(self):
        """Inicializa o agente correlator."""
        self.detected_patterns: List[CorrelationPattern] = []
    
    def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        """
        Analisa correlações de sinais para um alerta normalizado.
        
        Args:
            alert: Alerta normalizado para análise
            
        Returns:
            SwarmResult com hipótese, evidência e confiança
        """
        logger.info(f"[{self.agent_id}] Correlacionando sinais para {alert.fingerprint}...")
        
        # Limpar padrões detectados anteriormente
        self.detected_patterns = []
        
        # Executar análises de correlação
        self._analyze_log_metric_correlation(alert)
        self._analyze_trace_event_correlation(alert)
        self._analyze_metric_metric_correlation(alert)
        self._analyze_temporal_correlation(alert)
        
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
        Analisa correlação entre picos de erro em logs e anomalias em métricas.
        
        Padrão: Quando há picos de erro em logs, geralmente há também:
        - Aumento de latência (P95, P99)
        - Aumento de taxa de erro HTTP
        - Aumento de CPU/Memória
        """
        logger.debug(f"Analisando correlação LOG-METRIC para {alert.service}...")
        
        # Simulação: Detectar correlação entre logs e métricas
        # Em produção, isso consultaria Elasticsearch/Loki para logs e Prometheus para métricas
        
        if alert.severity in ["critical", "warning"]:
            # Hipótese: Picos de erro em logs correlacionam com latência alta
            correlation_strength = 0.95
            
            evidence = [
                EvidenceItem(
                    type=EvidenceType.LOG,
                    description="Picos de erro detectados nos logs: 'Connection timeout', 'Database unavailable'",
                    source_url="http://loki:3100/explore?query=error",
                    timestamp=datetime.now(timezone.utc)
                ),
                EvidenceItem(
                    type=EvidenceType.METRIC,
                    description="Latência P95 aumentou de 200ms para 2500ms no mesmo período",
                    source_url="http://prometheus:9090/graph?g0.expr=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]))",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
            
            pattern = CorrelationPattern(
                correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
                source_domain_1="LOGS",
                source_domain_2="METRICS",
                correlation_strength=correlation_strength,
                description=f"Picos de erro em logs correlacionam exatamente com aumento de latência em métricas para {alert.service}",
                evidence_items=evidence,
                suggested_action="Investigar causa raiz de aumento de latência (possível gargalo em DB ou serviço downstream)"
            )
            
            self.detected_patterns.append(pattern)
    
    def _analyze_trace_event_correlation(self, alert: NormalizedAlert) -> None:
        """
        Analisa correlação entre falhas em traces distribuídos e eventos de infraestrutura.
        
        Padrão: Quando há falhas em traces, geralmente há também:
        - Eventos de deployment
        - Mudanças em configuração
        - Eventos de escala (scale up/down)
        """
        logger.debug(f"Analisando correlação TRACE-EVENT para {alert.service}...")
        
        # Simulação: Detectar correlação entre traces e eventos
        # Em produção, isso consultaria Jaeger para traces e Kubernetes API para eventos
        
        if "restart" in alert.description.lower() or "pod" in alert.description.lower():
            # Hipótese: Falhas em traces correlacionam com restart de pod
            correlation_strength = 0.88
            
            evidence = [
                EvidenceItem(
                    type=EvidenceType.TRACE,
                    description="Trace #xyz falhou no passo de conexão com banco de dados",
                    source_url="http://jaeger:16686/trace/xyz",
                    timestamp=datetime.now(timezone.utc)
                ),
                EvidenceItem(
                    type=EvidenceType.DOCUMENT,
                    description="Pod foi reiniciado 15 vezes nos últimos 10 minutos (evento Kubernetes)",
                    source_url="kubectl describe pod worker-service-pod-2 -n production",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
            
            pattern = CorrelationPattern(
                correlation_type=CorrelationType.TRACE_EVENT_CORRELATION,
                source_domain_1="TRACES",
                source_domain_2="EVENTS",
                correlation_strength=correlation_strength,
                description=f"Falhas em traces distribuídos correlacionam com restart contínuo do pod {alert.service}",
                evidence_items=evidence,
                suggested_action="Verificar logs do pod para identificar causa raiz do restart (possível memory leak ou crash)"
            )
            
            self.detected_patterns.append(pattern)
    
    def _analyze_metric_metric_correlation(self, alert: NormalizedAlert) -> None:
        """
        Analisa correlação entre múltiplas métricas.
        
        Padrão: Correlações comuns:
        - CPU alto + Memória alta = Possível memory leak
        - Taxa de erro alta + Latência alta = Possível gargalo em serviço downstream
        - Requisições altas + CPU alto = Possível falta de recursos
        """
        logger.debug(f"Analisando correlação METRIC-METRIC para {alert.service}...")
        
        # Simulação: Detectar correlação entre métricas
        # Em produção, isso calcularia correlação de Pearson entre séries temporais
        
        if "cpu" in alert.description.lower() or "memory" in alert.description.lower():
            # Hipótese: CPU alto correlaciona com Memória alta
            correlation_strength = 0.92
            
            evidence = [
                EvidenceItem(
                    type=EvidenceType.METRIC,
                    description="CPU aumentou de 30% para 95% em 2 minutos",
                    source_url="http://prometheus:9090/graph?g0.expr=rate(process_cpu_seconds_total[5m])",
                    timestamp=datetime.now(timezone.utc)
                ),
                EvidenceItem(
                    type=EvidenceType.METRIC,
                    description="Memória aumentou de 500MB para 1.8GB no mesmo período",
                    source_url="http://prometheus:9090/graph?g0.expr=process_resident_memory_bytes",
                    timestamp=datetime.now(timezone.utc)
                )
            ]
            
            pattern = CorrelationPattern(
                correlation_type=CorrelationType.METRIC_METRIC_CORRELATION,
                source_domain_1="CPU_METRIC",
                source_domain_2="MEMORY_METRIC",
                correlation_strength=correlation_strength,
                description=f"Aumento de CPU correlaciona fortemente com aumento de memória em {alert.service}",
                evidence_items=evidence,
                suggested_action="Investigar possível memory leak ou processamento de dados em larga escala"
            )
            
            self.detected_patterns.append(pattern)
    
    def _analyze_temporal_correlation(self, alert: NormalizedAlert) -> None:
        """
        Analisa correlação temporal entre múltiplos eventos.
        
        Padrão: Sequência de eventos que levam a incidente:
        1. Deployment de nova versão
        2. Aumento de requisições
        3. Aumento de CPU/Memória
        4. Timeout de conexão
        5. Alerta crítico
        """
        logger.debug(f"Analisando correlação TEMPORAL para {alert.service}...")
        
        # Simulação: Detectar sequência temporal de eventos
        # Em produção, isso analisaria timeline de eventos de múltiplas fontes
        
        # Hipótese: Sequência de eventos que levou ao alerta
        correlation_strength = 0.85
        
        evidence = [
            EvidenceItem(
                type=EvidenceType.DOCUMENT,
                description="Deployment de versão 2.5.0 iniciado às 22:15 UTC",
                source_url="http://github.com/igorrhamon/strands/releases/tag/v2.5.0",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=5)
            ),
            EvidenceItem(
                type=EvidenceType.METRIC,
                description="Taxa de requisições aumentou 300% às 22:16 UTC",
                source_url="http://prometheus:9090/graph?g0.expr=rate(http_requests_total[5m])",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=4)
            ),
            EvidenceItem(
                type=EvidenceType.METRIC,
                description="CPU aumentou para 95% às 22:17 UTC",
                source_url="http://prometheus:9090/graph?g0.expr=rate(process_cpu_seconds_total[5m])",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=3)
            ),
            EvidenceItem(
                type=EvidenceType.LOG,
                description="Timeout de conexão detectado em logs às 22:18 UTC",
                source_url="http://loki:3100/explore?query=timeout",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=2)
            )
        ]
        
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.TEMPORAL_CORRELATION,
            source_domain_1="EVENTS",
            source_domain_2="TIMELINE",
            correlation_strength=correlation_strength,
            description=f"Sequência temporal: Deployment → Aumento de requisições → CPU alto → Timeout de conexão",
            evidence_items=evidence,
            suggested_action="Considerar rollback de deployment ou aumentar recursos alocados"
        )
        
        self.detected_patterns.append(pattern)
    
    def _consolidate_results(self, alert: NormalizedAlert) -> Tuple[str, float, List[EvidenceItem], List[str]]:
        """
        Consolida resultados de todas as análises de correlação.
        
        Returns:
            Tupla com (hypothesis, confidence, evidence, suggested_actions)
        """
        if not self.detected_patterns:
            return (
                f"Nenhuma correlação significativa detectada para {alert.service}.",
                0.5,
                [],
                ["Continuar monitorando o serviço"]
            )
        
        # Ordenar padrões por força de correlação
        sorted_patterns = sorted(
            self.detected_patterns,
            key=lambda p: p.correlation_strength,
            reverse=True
        )
        
        # Usar padrão mais forte como principal
        strongest_pattern = sorted_patterns[0]
        
        # Consolidar hipótese
        hypothesis_parts = [
            f"Correlação detectada entre {strongest_pattern.source_domain_1} e {strongest_pattern.source_domain_2}: ",
            strongest_pattern.description
        ]
        
        if len(sorted_patterns) > 1:
            hypothesis_parts.append(f"\nAdicionalmente, {len(sorted_patterns) - 1} correlação(ões) secundária(s) detectada(s).")
        
        hypothesis = "".join(hypothesis_parts)
        
        # Calcular confiança média
        avg_confidence = sum(p.correlation_strength for p in sorted_patterns) / len(sorted_patterns)
        
        # Consolidar evidência
        all_evidence = []
        for pattern in sorted_patterns:
            all_evidence.extend(pattern.evidence_items)
        
        # Consolidar ações sugeridas
        suggested_actions = [p.suggested_action for p in sorted_patterns]
        
        logger.info(f"[{self.agent_id}] Correlação consolidada: {strongest_pattern.correlation_type.value} com confiança {avg_confidence:.2f}")
        
        return hypothesis, avg_confidence, all_evidence, suggested_actions
