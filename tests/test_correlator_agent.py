"""
Testes para CorrelatorAgent - Análise de Correlação entre Domínios

Testa a capacidade do agente de detectar correlações entre:
- Logs e Métricas
- Traces e Eventos
- Métricas e Métricas
- Eventos Temporais
"""

import pytest
from datetime import datetime, timezone
from src.agents.analysis.correlator import (
    CorrelatorAgent,
    CorrelationType,
    CorrelationStrength,
    CorrelationPattern
)
from src.models.alert import NormalizedAlert, ValidationStatus
from src.models.swarm import SwarmResult, EvidenceType


class TestCorrelatorAgent:
    """Testes para CorrelatorAgent."""
    
    @pytest.fixture
    def correlator(self):
        """Fixture para instanciar CorrelatorAgent."""
        return CorrelatorAgent()
    
    @pytest.fixture
    def alert_critical_cpu(self):
        """Fixture para alerta crítico de CPU."""
        return NormalizedAlert(
            timestamp=datetime.now(timezone.utc),
            fingerprint="alert-cpu-001",
            service="api-service",
            severity="critical",
            description="CPU usage is 95.5%, exceeding threshold of 80%",
            labels={"pod": "api-service-pod-1", "namespace": "production"},
            validation_status=ValidationStatus.VALID
        )
    
    @pytest.fixture
    def alert_pod_restart(self):
        """Fixture para alerta de restart de pod."""
        return NormalizedAlert(
            timestamp=datetime.now(timezone.utc),
            fingerprint="alert-restart-001",
            service="worker-service",
            severity="critical",
            description="Pod has restarted 15 times in the last 10 minutes",
            labels={"pod": "worker-service-pod-2", "namespace": "production"},
            validation_status=ValidationStatus.VALID
        )
    
    @pytest.fixture
    def alert_memory(self):
        """Fixture para alerta de memória."""
        return NormalizedAlert(
            timestamp=datetime.now(timezone.utc),
            fingerprint="alert-memory-001",
            service="database-service",
            severity="warning",
            description="Memory usage is 85.2%, exceeding threshold of 80%",
            labels={"pod": "database-service-pod-1", "namespace": "production"},
            validation_status=ValidationStatus.VALID
        )
    
    def test_correlator_agent_initialization(self, correlator):
        """Testa inicialização do CorrelatorAgent."""
        assert correlator.agent_id == "correlator"
        assert correlator.detected_patterns == []
    
    def test_analyze_returns_swarm_result(self, correlator, alert_critical_cpu):
        """Testa se analyze retorna SwarmResult válido."""
        result = correlator.analyze(alert_critical_cpu)
        
        assert isinstance(result, SwarmResult)
        assert result.agent_id == "correlator"
        assert isinstance(result.hypothesis, str)
        assert 0.0 <= result.confidence <= 1.0
        assert isinstance(result.evidence, list)
        assert isinstance(result.suggested_actions, list)
    
    def test_log_metric_correlation_detection(self, correlator, alert_critical_cpu):
        """Testa detecção de correlação LOG-METRIC."""
        result = correlator.analyze(alert_critical_cpu)
        
        # Deve detectar correlação entre logs e métricas
        assert result.confidence > 0.5
        assert len(result.evidence) > 0
        assert "correlaciona" in result.hypothesis.lower() or "correlation" in result.hypothesis.lower()
    
    def test_trace_event_correlation_detection(self, correlator, alert_pod_restart):
        """Testa detecção de correlação TRACE-EVENT."""
        result = correlator.analyze(alert_pod_restart)
        
        # Deve detectar correlação entre traces e eventos
        assert result.confidence > 0.5
        assert len(result.evidence) > 0
        assert "restart" in result.hypothesis.lower() or "pod" in result.hypothesis.lower()
    
    def test_metric_metric_correlation_detection(self, correlator, alert_memory):
        """Testa detecção de correlação METRIC-METRIC."""
        result = correlator.analyze(alert_memory)
        
        # Deve detectar correlação entre métricas
        assert result.confidence > 0.0
        assert len(result.suggested_actions) > 0
    
    def test_temporal_correlation_detection(self, correlator, alert_critical_cpu):
        """Testa detecção de correlação TEMPORAL."""
        result = correlator.analyze(alert_critical_cpu)
        
        # Deve detectar sequência temporal de eventos
        assert len(result.evidence) > 0
        # Verificar se há evidência de tipo DOCUMENT (deployment)
        evidence_types = [e.type for e in result.evidence]
        assert any(t in evidence_types for t in [EvidenceType.DOCUMENT, EvidenceType.METRIC, EvidenceType.LOG])
    
    def test_evidence_items_have_required_fields(self, correlator, alert_critical_cpu):
        """Testa se itens de evidência têm campos obrigatórios."""
        result = correlator.analyze(alert_critical_cpu)
        
        for evidence in result.evidence:
            assert evidence.type in EvidenceType
            assert isinstance(evidence.description, str)
            assert isinstance(evidence.source_url, str)
            assert isinstance(evidence.timestamp, datetime)
    
    def test_suggested_actions_are_actionable(self, correlator, alert_critical_cpu):
        """Testa se ações sugeridas são acionáveis."""
        result = correlator.analyze(alert_critical_cpu)
        
        assert len(result.suggested_actions) > 0
        for action in result.suggested_actions:
            assert isinstance(action, str)
            assert len(action) > 10  # Deve ter descrição significativa
    
    def test_multiple_pattern_detection(self, correlator, alert_critical_cpu):
        """Testa detecção de múltiplos padrões de correlação."""
        result = correlator.analyze(alert_critical_cpu)
        
        # Deve detectar múltiplos padrões
        assert len(correlator.detected_patterns) > 0
        assert len(result.evidence) >= len(correlator.detected_patterns)
    
    def test_pattern_strength_calculation(self, correlator, alert_critical_cpu):
        """Testa cálculo de força de correlação."""
        correlator.analyze(alert_critical_cpu)
        
        for pattern in correlator.detected_patterns:
            assert 0.0 <= pattern.correlation_strength <= 1.0
            strength_label = pattern.get_strength_label()
            assert strength_label in CorrelationStrength
    
    def test_correlation_type_classification(self, correlator, alert_critical_cpu):
        """Testa classificação de tipo de correlação."""
        correlator.analyze(alert_critical_cpu)
        
        for pattern in correlator.detected_patterns:
            assert pattern.correlation_type in CorrelationType
            assert isinstance(pattern.source_domain_1, str)
            assert isinstance(pattern.source_domain_2, str)
    
    def test_consolidation_of_multiple_patterns(self, correlator, alert_critical_cpu):
        """Testa consolidação de múltiplos padrões em resultado único."""
        result = correlator.analyze(alert_critical_cpu)
        
        # Resultado consolidado deve ter confiança média dos padrões
        if correlator.detected_patterns:
            avg_confidence = sum(p.correlation_strength for p in correlator.detected_patterns) / len(correlator.detected_patterns)
            assert abs(result.confidence - avg_confidence) < 0.01
    
    def test_empty_patterns_handling(self, correlator):
        """Testa tratamento de caso sem padrões detectados."""
        # Criar alerta que não dispara correlações
        alert = NormalizedAlert(
            timestamp=datetime.now(timezone.utc),
            fingerprint="alert-info-001",
            service="unknown-service",
            severity="info",
            description="Informational alert",
            labels={},
            validation_status=ValidationStatus.VALID
        )
        
        result = correlator.analyze(alert)
        
        # Deve retornar resultado válido mesmo sem padrões
        assert isinstance(result, SwarmResult)
        assert result.agent_id == "correlator"
    
    def test_hypothesis_includes_service_name(self, correlator, alert_critical_cpu):
        """Testa se hipótese inclui nome do serviço."""
        result = correlator.analyze(alert_critical_cpu)
        
        assert alert_critical_cpu.service in result.hypothesis or "correlação" in result.hypothesis.lower()
    
    def test_confidence_reflects_pattern_strength(self, correlator, alert_critical_cpu):
        """Testa se confiança reflete força dos padrões detectados."""
        result = correlator.analyze(alert_critical_cpu)
        
        # Com padrões detectados, confiança deve ser > 0.5
        if correlator.detected_patterns:
            assert result.confidence > 0.5
    
    def test_different_alerts_produce_different_results(self, correlator, alert_critical_cpu, alert_pod_restart):
        """Testa se alertas diferentes produzem resultados diferentes."""
        result1 = correlator.analyze(alert_critical_cpu)
        
        # Limpar padrões para próxima análise
        correlator.detected_patterns = []
        
        result2 = correlator.analyze(alert_pod_restart)
        
        # Resultados devem ser diferentes
        assert result1.hypothesis != result2.hypothesis or result1.confidence != result2.confidence


class TestCorrelationPattern:
    """Testes para CorrelationPattern."""
    
    def test_pattern_initialization(self):
        """Testa inicialização de CorrelationPattern."""
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
            source_domain_1="LOGS",
            source_domain_2="METRICS",
            correlation_strength=0.95,
            description="Test correlation",
            evidence_items=[],
            suggested_action="Test action"
        )
        
        assert pattern.correlation_type == CorrelationType.LOG_METRIC_CORRELATION
        assert pattern.source_domain_1 == "LOGS"
        assert pattern.source_domain_2 == "METRICS"
        assert pattern.correlation_strength == 0.95
    
    def test_strength_label_very_strong(self):
        """Testa rótulo de força VERY_STRONG."""
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
            source_domain_1="LOGS",
            source_domain_2="METRICS",
            correlation_strength=0.95,
            description="Test",
            evidence_items=[],
            suggested_action="Test"
        )
        
        assert pattern.get_strength_label() == CorrelationStrength.VERY_STRONG
    
    def test_strength_label_strong(self):
        """Testa rótulo de força STRONG."""
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
            source_domain_1="LOGS",
            source_domain_2="METRICS",
            correlation_strength=0.80,
            description="Test",
            evidence_items=[],
            suggested_action="Test"
        )
        
        assert pattern.get_strength_label() == CorrelationStrength.STRONG
    
    def test_strength_label_moderate(self):
        """Testa rótulo de força MODERATE."""
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
            source_domain_1="LOGS",
            source_domain_2="METRICS",
            correlation_strength=0.60,
            description="Test",
            evidence_items=[],
            suggested_action="Test"
        )
        
        assert pattern.get_strength_label() == CorrelationStrength.MODERATE
    
    def test_strength_label_weak(self):
        """Testa rótulo de força WEAK."""
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
            source_domain_1="LOGS",
            source_domain_2="METRICS",
            correlation_strength=0.40,
            description="Test",
            evidence_items=[],
            suggested_action="Test"
        )
        
        assert pattern.get_strength_label() == CorrelationStrength.WEAK
    
    def test_strength_label_very_weak(self):
        """Testa rótulo de força VERY_WEAK."""
        pattern = CorrelationPattern(
            correlation_type=CorrelationType.LOG_METRIC_CORRELATION,
            source_domain_1="LOGS",
            source_domain_2="METRICS",
            correlation_strength=0.20,
            description="Test",
            evidence_items=[],
            suggested_action="Test"
        )
        
        assert pattern.get_strength_label() == CorrelationStrength.VERY_WEAK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
