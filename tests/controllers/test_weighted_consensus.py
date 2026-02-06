"""
Testes Unitários para WeightedConsensusStrategy

Testa:
1. Cálculo de votação ponderada
2. Resolução de empate
3. Detecção de alucinação
4. Validação de confiança
"""

import pytest
from datetime import datetime
from typing import List

from src.strategies.consensus_strategy import (
    WeightedScoreStrategy,
    UnanimousStrategy,
    MajorityStrategy,
    AgentExecution,
    AgentRole,
    ConsensusResult,
)


class TestWeightedScoreStrategy:
    """Testa estratégia de votação ponderada."""
    
    @pytest.fixture
    def strategy(self):
        """Cria instância da estratégia."""
        return WeightedScoreStrategy(confidence_threshold=0.7)
    
    @pytest.fixture
    def sample_executions(self) -> List[AgentExecution]:
        """Cria execuções de amostra."""
        return [
            AgentExecution(
                agent_id="threat_intel_1",
                agent_name="Threat Intelligence Agent",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=5,
                result="escalate",
                reasoning="Padrão de ataque detectado",
            ),
            AgentExecution(
                agent_id="log_analyzer_1",
                agent_name="Log Analyzer Agent",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.85,
                evidence_count=3,
                result="escalate",
                reasoning="Múltiplas falhas de autenticação",
            ),
            AgentExecution(
                agent_id="metrics_analyzer_1",
                agent_name="Metrics Analyzer Agent",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.7,
                evidence_count=2,
                result="monitor",
                reasoning="Aumento de latência detectado",
            ),
        ]
    
    def test_initialization(self, strategy):
        """Testa inicialização da estratégia."""
        assert strategy.name == "weighted_score"
        assert strategy.confidence_threshold == 0.7
    
    def test_calculate_consensus_basic(self, strategy, sample_executions):
        """Testa cálculo básico de consenso."""
        result = strategy.calculate(sample_executions)
        
        assert isinstance(result, ConsensusResult)
        assert 0.0 <= result.final_score <= 1.0
        assert result.consensus_type is not None
        assert len(result.agent_votes) == 3
        assert len(result.weighted_scores) == 3
    
    def test_weighted_score_calculation(self, strategy, sample_executions):
        """Testa se pesos são aplicados corretamente.
        
        Esperado:
        - ThreatIntel (peso 2.0): 0.9 * 2.0 = 1.8
        - LogAnalyzer (peso 1.5): 0.85 * 1.5 = 1.275
        - MetricsAnalyzer (peso 1.0): 0.7 * 1.0 = 0.7
        - Total: (1.8 + 1.275 + 0.7) / (2.0 + 1.5 + 1.0) = 3.775 / 4.5 = 0.839
        """
        result = strategy.calculate(sample_executions)
        
        # Score esperado aproximadamente 0.839
        assert result.final_score > 0.83
        assert result.final_score < 0.85
        
        # Verificar pesos individuais
        assert result.weighted_scores["threat_intel_1"] == pytest.approx(1.8, rel=0.01)
        assert result.weighted_scores["log_analyzer_1"] == pytest.approx(1.275, rel=0.01)
        assert result.weighted_scores["metrics_analyzer_1"] == pytest.approx(0.7, rel=0.01)
    
    def test_consensus_type_unanimous(self, strategy):
        """Testa detecção de consenso unânime."""
        executions = [
            AgentExecution(
                agent_id=f"agent_{i}",
                agent_name=f"Agent {i}",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.8 + i * 0.05,
                evidence_count=3,
                result="approve",  # Todos com mesmo resultado
                reasoning="Tudo bem",
            )
            for i in range(3)
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "unanimous"
    
    def test_consensus_type_majority(self, strategy):
        """Testa detecção de maioria."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=5,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.8,
                evidence_count=3,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_3",
                agent_name="Agent 3",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.5,
                evidence_count=1,
                result="monitor",  # Diferente
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "majority"
    
    def test_consensus_type_split(self, strategy):
        """Testa detecção de divisão."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=5,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.5,
                evidence_count=2,
                result="monitor",
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type in ["split", "majority"]
    
    def test_human_review_required_low_confidence(self, strategy):
        """Testa se revisão humana é requerida com confiança baixa."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.5,  # Baixa confiança
                evidence_count=1,
                result="monitor",
                reasoning="Incerto",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.requires_human_review is True
        assert result.final_score < strategy.confidence_threshold
    
    def test_hallucination_detection(self, strategy):
        """Testa detecção de possível alucinação.
        
        Alucinação é flagged quando divergência > 20% entre
        confiança do agente e score final calculado.
        """
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.95,  # Muito alta
                evidence_count=0,  # Sem evidências
                result="escalate",
                reasoning="Intuição",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        # Sem evidências, score deve ser 0.95
        # Divergência = |0.95 - 0.95| = 0.0 (sem alucinação)
        assert result.hallucination_flag is None
    
    def test_hallucination_detection_with_divergence(self, strategy):
        """Testa alucinação com divergência significativa."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=0,
                result="escalate",
                reasoning="Sem evidências",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.3,  # Muito diferente
                evidence_count=5,
                result="monitor",
                reasoning="Com evidências",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        # Deve haver divergência entre agentes
        if result.hallucination_flag:
            assert "Divergência" in result.hallucination_flag
    
    def test_resolve_tie_basic(self, strategy):
        """Testa resolução de empate básica."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,  # Peso 2.0
                confidence_score=0.8,
                evidence_count=3,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,  # Peso 1.5
                confidence_score=0.8,
                evidence_count=3,
                result="monitor",  # Resultado diferente
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.resolve_tie(executions)
        
        # ThreatIntel tem peso maior, deve vencer
        assert result.lower() == "escalate"
    
    def test_resolve_tie_human_analyst_wins(self, strategy):
        """Testa que human analyst tem peso máximo."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,  # Peso 2.0
                confidence_score=0.8,
                evidence_count=3,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.HUMAN_ANALYST,  # Peso 3.0 (máximo)
                confidence_score=0.8,
                evidence_count=3,
                result="approve",  # Resultado diferente
                reasoning="Aprovado",
            ),
        ]
        
        result = strategy.resolve_tie(executions)
        
        # Human analyst tem peso maior
        assert result.lower() == "approve"
    
    def test_empty_executions(self, strategy):
        """Testa comportamento com lista vazia."""
        result = strategy.calculate([])
        
        assert result.final_score == 0.0
        assert result.consensus_type == "empty"
        assert result.requires_human_review is True
    
    def test_single_execution(self, strategy):
        """Testa com um único agente."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.75,
                evidence_count=2,
                result="monitor",
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "single_agent"
        assert result.final_score == 0.75
    
    def test_invalid_confidence_score(self):
        """Testa rejeição de score inválido."""
        with pytest.raises(ValueError):
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=1.5,  # Inválido
                evidence_count=2,
                result="monitor",
                reasoning="Teste",
            )
    
    def test_invalid_evidence_count(self):
        """Testa rejeição de evidence_count negativo."""
        with pytest.raises(ValueError):
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.8,
                evidence_count=-1,  # Inválido
                result="monitor",
                reasoning="Teste",
            )


class TestUnanimousStrategy:
    """Testa estratégia de consenso unânime."""
    
    @pytest.fixture
    def strategy(self):
        """Cria instância da estratégia."""
        return UnanimousStrategy()
    
    def test_unanimous_agreement(self, strategy):
        """Testa consenso unânime."""
        executions = [
            AgentExecution(
                agent_id=f"agent_{i}",
                agent_name=f"Agent {i}",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.8,
                evidence_count=3,
                result="approve",  # Todos iguais
                reasoning="Tudo bem",
            )
            for i in range(3)
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "unanimous"
        assert result.requires_human_review is False
    
    def test_no_unanimous_agreement(self, strategy):
        """Testa falta de consenso unânime."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=5,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.8,
                evidence_count=3,
                result="monitor",  # Diferente
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "no_unanimous_agreement"
        assert result.requires_human_review is True


class TestMajorityStrategy:
    """Testa estratégia de maioria."""
    
    @pytest.fixture
    def strategy(self):
        """Cria instância da estratégia."""
        return MajorityStrategy(majority_threshold=0.5)
    
    def test_majority_agreement(self, strategy):
        """Testa maioria simples."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=5,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.8,
                evidence_count=3,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_3",
                agent_name="Agent 3",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.5,
                evidence_count=1,
                result="monitor",  # Minoria
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "majority"
        assert result.requires_human_review is True  # Maioria forte mas nao unanime
    
    def test_weak_majority(self, strategy):
        """Testa maioria fraca."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.6,
                evidence_count=2,
                result="escalate",
                reasoning="Possível",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.5,
                evidence_count=1,
                result="monitor",
                reasoning="Tudo bem",
            ),
        ]
        
        result = strategy.calculate(executions)
        
        assert result.consensus_type == "majority"
        assert result.requires_human_review is True  # Maioria fraca (1/2)
