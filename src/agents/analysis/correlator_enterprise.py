"""
Correlator Agent - Enterprise Grade (Produção)

Versão com resiliência, observabilidade, correlação avançada e governança.
"""

import logging
import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType
from src.tools.prometheus_client import PrometheusClient
from src.tools.kubectl_client import KubectlMCPClient
from src.core.resilience import ResilienceContext, CircuitBreaker, RetryConfig
from src.core.observability import ObservabilityContext
from src.core.advanced_correlation import AdvancedCorrelationAnalyzer, BayesianConfidenceCalculator
from src.core.model_governance import ModelGovernance, ModelVersion

logger = logging.getLogger(__name__)


class CorrelatorAgentEnterprise:
    """
    Agente Correlator Enterprise-Grade com resiliência, observabilidade e governança.
    """
    
    agent_id = "correlator-enterprise"
    
    def __init__(self):
        """Inicializa agente com infraestrutura enterprise."""
        # Clientes de infraestrutura
        self.prometheus_client = PrometheusClient()
        self.kubectl_client = KubectlMCPClient()
        
        # Camadas de infraestrutura
        self.observability = ObservabilityContext(self.agent_id)
        self.governance = ModelGovernance(self.agent_id)
        self.correlation_analyzer = AdvancedCorrelationAnalyzer(min_sample_size=20)
        self.bayesian_calculator = BayesianConfidenceCalculator()
        
        # Resiliência
        self.prometheus_resilience = ResilienceContext(
            name="prometheus",
            circuit_breaker=CircuitBreaker("prometheus", failure_threshold=5, recovery_timeout_seconds=60),
            retry_config=RetryConfig(max_attempts=3, initial_delay_seconds=1.0),
            timeout_seconds=30.0
        )
        
        self.kubectl_resilience = ResilienceContext(
            name="kubectl",
            circuit_breaker=CircuitBreaker("kubectl", failure_threshold=5, recovery_timeout_seconds=60),
            retry_config=RetryConfig(max_attempts=3, initial_delay_seconds=1.0),
            timeout_seconds=30.0
        )
        
        self.detected_patterns: List[Dict[str, Any]] = []
    
    def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        """
        Analisa correlações com resiliência, observabilidade e governança.
        """
        decision_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"[{self.agent_id}] Iniciando análise para {alert.fingerprint} (decision_id: {decision_id})")
        self.observability.metrics.increment_counter("analysis_started")
        
        try:
            # Limpar padrões detectados
            self.detected_patterns = []
            
            # Executar análises com resiliência
            with self.observability.metrics.measure_time("log_metric_correlation"):
                self._analyze_log_metric_correlation_resilient(alert)
            
            with self.observability.metrics.measure_time("metric_metric_correlation"):
                self._analyze_metric_metric_correlation_resilient(alert)
            
            with self.observability.metrics.measure_time("temporal_correlation"):
                self._analyze_temporal_correlation_resilient(alert)
            
            # Consolidar resultados
            hypothesis, confidence, evidence, suggested_actions = self._consolidate_results(alert)
            
            # Registrar na governança
            config = self.governance.get_current_config()
            audit_log = self.governance.log_decision(
                decision_id=decision_id,
                alert_fingerprint=alert.fingerprint,
                hypothesis=hypothesis,
                confidence=confidence,
                correlation_type=self._get_primary_correlation_type(),
                evidence_count=len(evidence),
                suggested_actions=len(suggested_actions),
                metadata={
                    "patterns_detected": len(self.detected_patterns),
                    "model_version": self.governance.current_model_version.value,
                    "config_hash": config.get_hash()
                }
            )
            
            # Registrar tempo de execução
            execution_time_ms = (time.time() - start_time) * 1000
            self.governance.record_execution_time(decision_id, execution_time_ms)
            self.observability.metrics.record_timer("analysis_duration", execution_time_ms / 1000.0)
            
            # Log estruturado
            self.observability.logger.log_decision(
                decision_type="CORRELATION",
                hypothesis=hypothesis,
                confidence=confidence,
                evidence_count=len(evidence),
                suggested_actions=len(suggested_actions),
                metadata={
                    "decision_id": decision_id,
                    "execution_time_ms": execution_time_ms,
                    "patterns": len(self.detected_patterns)
                }
            )
            
            self.observability.metrics.increment_counter("analysis_completed")
            
            if confidence < config.confidence_threshold:
                logger.warning(
                    f"Confidence {confidence:.2f} below threshold {config.confidence_threshold:.2f}"
                )
                self.observability.metrics.increment_counter("low_confidence_decisions")
            
            return SwarmResult(
                agent_id=self.agent_id,
                hypothesis=hypothesis,
                confidence=confidence,
                evidence=evidence,
                suggested_actions=suggested_actions
            )
        
        except Exception as e:
            logger.error(f"Erro durante análise: {e}", exc_info=True)
            self.observability.logger.log_error(
                error_type="ANALYSIS_ERROR",
                message=str(e),
                exception=e,
                metadata={"decision_id": decision_id, "alert_fingerprint": alert.fingerprint}
            )
            self.observability.metrics.increment_counter("analysis_errors")
            
            # Retornar resultado degradado
            return SwarmResult(
                agent_id=self.agent_id,
                hypothesis=f"Erro durante análise: {str(e)}",
                confidence=0.0,
                evidence=[],
                suggested_actions=["Verificar logs do agente", "Tentar novamente mais tarde"]
            )
    
    def _analyze_log_metric_correlation_resilient(self, alert: NormalizedAlert) -> None:
        """Analisa correlação log-métrica com resiliência."""
        try:
            namespace = alert.labels.get("namespace", "default")
            pod_name = alert.labels.get("pod")
            
            if not pod_name:
                pods = self.kubectl_resilience.execute(
                    self.kubectl_client.get_pods,
                    namespace=namespace,
                    label_selector=f"app={alert.service}"
                )
                if pods:
                    pod_name = pods[0].get("metadata", {}).get("name")
            
            if not pod_name:
                logger.debug(f"Pod não encontrado para {alert.service}")
                return
            
            # Buscar logs com resiliência
            logs = self.kubectl_resilience.execute(
                self.kubectl_client.get_logs,
                pod_name=pod_name,
                namespace=namespace,
                tail_lines=200
            )
            
            error_count = logs.lower().count("error") + logs.lower().count("exception")
            
            if error_count == 0:
                return
            
            # Buscar métricas com resiliência
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=15)
            
            error_rate_query = f'rate(http_requests_total{{app="{alert.service}", status=~"5.."}}[5m])'
            metrics_result = self.prometheus_resilience.execute(
                self.prometheus_client.query_range,
                error_rate_query,
                start_time,
                end_time
            )
            
            has_metric_spike = False
            if metrics_result.get("result"):
                values = metrics_result["result"][0].get("values", [])
                if values:
                    recent_values = [float(v[1]) for v in values[-3:]]
                    if recent_values and max(recent_values) > 0.01:
                        has_metric_spike = True
            
            if has_metric_spike:
                # Usar correlação avançada
                correlation_result = self.correlation_analyzer.analyze_with_lag(
                    [float(v[1]) for v in values] if values else [],
                    [float(error_count)] * len(values) if values else [],
                    max_lag=2
                )
                
                # Calcular confiança Bayesiana
                bayesian_confidence = self.bayesian_calculator.calculate_posterior(
                    correlation_result.correlation_coefficient,
                    correlation_result.p_value,
                    correlation_result.sample_count
                )
                
                evidence = [
                    EvidenceItem(
                        type=EvidenceType.LOG,
                        description=f"Detectados {error_count} erros nos logs do pod {pod_name}",
                        source_url=f"kubectl logs {pod_name}",
                        timestamp=datetime.now(timezone.utc)
                    ),
                    EvidenceItem(
                        type=EvidenceType.METRIC,
                        description=f"Pico na taxa de erros HTTP (r={correlation_result.correlation_coefficient:.2f}, p={correlation_result.p_value:.4f})",
                        source_url=f"{self.prometheus_client.base_url}/graph?g0.expr={error_rate_query}",
                        timestamp=datetime.now(timezone.utc)
                    )
                ]
                
                pattern = {
                    "type": "LOG_METRIC_CORRELATION",
                    "confidence": bayesian_confidence,
                    "correlation_coefficient": correlation_result.correlation_coefficient,
                    "p_value": correlation_result.p_value,
                    "lag_offset": correlation_result.lag_offset,
                    "significance": correlation_result.significance.value,
                    "evidence": evidence,
                    "action": "Investigar stack traces nos logs e verificar dependências"
                }
                
                self.detected_patterns.append(pattern)
                self.observability.metrics.increment_counter("log_metric_correlations_found")
        
        except Exception as e:
            logger.error(f"Erro em log-metric correlation: {e}", exc_info=True)
            self.observability.logger.log_error(
                error_type="LOG_METRIC_ANALYSIS_ERROR",
                message=str(e),
                exception=e
            )
    
    def _analyze_metric_metric_correlation_resilient(self, alert: NormalizedAlert) -> None:
        """Analisa correlação métrica-métrica com resiliência."""
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(minutes=30)
            
            cpu_query = f'rate(container_cpu_usage_seconds_total{{pod=~"{alert.service}.*"}}[5m])'
            mem_query = f'container_memory_working_set_bytes{{pod=~"{alert.service}.*"}}'
            
            cpu_data = self.prometheus_resilience.execute(
                self.prometheus_client.query_range,
                cpu_query,
                start_time,
                end_time
            )
            
            mem_data = self.prometheus_resilience.execute(
                self.prometheus_client.query_range,
                mem_query,
                start_time,
                end_time
            )
            
            if not cpu_data.get("result") or not mem_data.get("result"):
                return
            
            cpu_values = [float(v[1]) for v in cpu_data["result"][0]["values"]]
            mem_values = [float(v[1]) for v in mem_data["result"][0]["values"]]
            
            # Usar análise avançada com lag
            correlation_result = self.correlation_analyzer.analyze_with_lag(
                cpu_values,
                mem_values,
                max_lag=3,
                normalize=True
            )
            
            if correlation_result.is_significant:
                # Calcular confiança Bayesiana
                bayesian_confidence = self.bayesian_calculator.calculate_posterior(
                    correlation_result.correlation_coefficient,
                    correlation_result.p_value,
                    correlation_result.sample_count
                )
                
                evidence = [
                    EvidenceItem(
                        type=EvidenceType.METRIC,
                        description=f"Correlação forte (r={correlation_result.correlation_coefficient:.2f}, lag={correlation_result.lag_offset}, p={correlation_result.p_value:.4f})",
                        source_url=f"{self.prometheus_client.base_url}/graph",
                        timestamp=datetime.now(timezone.utc)
                    )
                ]
                
                pattern = {
                    "type": "METRIC_METRIC_CORRELATION",
                    "confidence": bayesian_confidence,
                    "correlation_coefficient": correlation_result.correlation_coefficient,
                    "lag_offset": correlation_result.lag_offset,
                    "significance": correlation_result.significance.value,
                    "evidence": evidence,
                    "action": "Investigar operações intensivas de processamento ou memory leaks"
                }
                
                self.detected_patterns.append(pattern)
                self.observability.metrics.increment_counter("metric_metric_correlations_found")
        
        except Exception as e:
            logger.error(f"Erro em metric-metric correlation: {e}", exc_info=True)
            self.observability.logger.log_error(
                error_type="METRIC_METRIC_ANALYSIS_ERROR",
                message=str(e),
                exception=e
            )
    
    def _analyze_temporal_correlation_resilient(self, alert: NormalizedAlert) -> None:
        """Analisa correlação temporal com resiliência."""
        try:
            namespace = alert.labels.get("namespace", "default")
            pod_name = alert.labels.get("pod")
            
            if not pod_name:
                pods = self.kubectl_resilience.execute(
                    self.kubectl_client.get_pods,
                    namespace=namespace,
                    label_selector=f"app={alert.service}"
                )
                if pods:
                    pod_name = pods[0].get("metadata", {}).get("name")
            
            if not pod_name:
                return
            
            pods = self.kubectl_resilience.execute(
                self.kubectl_client.get_pods,
                namespace=namespace,
                label_selector=f"metadata.name={pod_name}"
            )
            
            if not pods:
                pods = self.kubectl_resilience.execute(
                    self.kubectl_client.get_pods,
                    namespace=namespace
                )
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
                        try:
                            dt = datetime.strptime(finished_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                            last_restart_time = dt
                        except ValueError:
                            pass
            
            if restart_count > 0 and last_restart_time:
                if (datetime.now(timezone.utc) - last_restart_time) < timedelta(minutes=30):
                    evidence = [
                        EvidenceItem(
                            type=EvidenceType.DOCUMENT,
                            description=f"Pod reiniciado {restart_count} vezes. Último restart: {last_restart_time}",
                            source_url=f"kubectl describe pod {pod_name}",
                            timestamp=last_restart_time
                        )
                    ]
                    
                    pattern = {
                        "type": "TEMPORAL_CORRELATION",
                        "confidence": 0.85,
                        "evidence": evidence,
                        "action": "Verificar logs anteriores ao crash (kubectl logs --previous)"
                    }
                    
                    self.detected_patterns.append(pattern)
                    self.observability.metrics.increment_counter("temporal_correlations_found")
        
        except Exception as e:
            logger.error(f"Erro em temporal correlation: {e}", exc_info=True)
            self.observability.logger.log_error(
                error_type="TEMPORAL_ANALYSIS_ERROR",
                message=str(e),
                exception=e
            )
    
    def _consolidate_results(self, alert: NormalizedAlert) -> tuple:
        """Consolida resultados de análises."""
        if not self.detected_patterns:
            return (
                f"Nenhuma correlação significativa detectada para {alert.service}.",
                0.0,
                [],
                ["Continuar monitorando", "Verificar integridade dos coletores"]
            )
        
        # Ordenar por confiança
        sorted_patterns = sorted(
            self.detected_patterns,
            key=lambda p: p.get("confidence", 0),
            reverse=True
        )
        
        strongest = sorted_patterns[0]
        hypothesis = f"Correlação detectada ({strongest['type']}): {strongest.get('action', 'Análise necessária')}"
        
        avg_confidence = sum(p.get("confidence", 0) for p in sorted_patterns) / len(sorted_patterns)
        
        all_evidence = []
        for pattern in sorted_patterns:
            all_evidence.extend(pattern.get("evidence", []))
        
        suggested_actions = list(set([p.get("action", "") for p in sorted_patterns if p.get("action")]))
        
        return hypothesis, avg_confidence, all_evidence, suggested_actions
    
    def _get_primary_correlation_type(self) -> str:
        """Retorna tipo de correlação primária."""
        if not self.detected_patterns:
            return "NONE"
        return self.detected_patterns[0].get("type", "UNKNOWN")
    
    def get_status(self) -> dict:
        """Retorna status completo do agente."""
        return {
            "agent_id": self.agent_id,
            "model_version": self.governance.current_model_version.value,
            "observability": self.observability.get_health_status(),
            "resilience": {
                "prometheus": self.prometheus_resilience.get_status(),
                "kubectl": self.kubectl_resilience.get_status()
            },
            "governance": self.governance.export_audit_trail()
        }
