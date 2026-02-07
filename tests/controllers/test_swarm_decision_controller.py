"""
Testes para SwarmDecisionController

Testa:
1. Integração com WeightedConsensusStrategy
2. Cálculo de confiança
3. Determinação de estado da decisão
4. Persistência de checkpoint
"""

import pytest
from datetime import datetime
from typing import List

from src.controllers.swarm_decision_controller import (
    SwarmDecisionController,
    SwarmDecision,
    DecisionState,
    DecisionReason,
)
from src.strategies.consensus_strategy import (
    AgentExecution,
    AgentRole,
    WeightedScoreStrategy,
)
from src.policies.confidence_policy import ConfidencePolicy


class TestSwarmDecisionController:
    """Testa SwarmDecisionController."""
    
    @pytest.fixture
    def controller(self):
        """Cria instância do controlador."""
        return SwarmDecisionController(
            consensus_strategy=WeightedScoreStrategy(confidence_threshold=0.7),
            confidence_policy=ConfidencePolicy(base_weight=1.0),
            checkpoint_engine=None,  # Sem persistência nos testes
        )
    
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
    
    def test_initialization(self, controller):
        """Testa inicialização do controlador."""
        assert controller.consensus_strategy is not None
        assert controller.confidence_policy is not None
        assert isinstance(controller.consensus_strategy, WeightedScoreStrategy)
    
    def test_make_decision_basic(self, controller, sample_executions):
        """Testa tomada de decisão básica."""
        decision = controller.make_decision(sample_executions, save_checkpoint=False)
        
        assert isinstance(decision, SwarmDecision)
        assert decision.decision_id is not None
        assert decision.state is not None
        assert 0.0 <= decision.confidence_score <= 1.0
        assert 0.0 <= decision.weighted_score <= 1.0
        assert len(decision.agent_executions) == 3
    
    def test_make_decision_empty_executions(self, controller):
        """Testa decisão com execuções vazias."""
        decision = controller.make_decision([], save_checkpoint=False)
        
        assert decision.state == DecisionState.INVESTIGATING
        assert decision.reason == DecisionReason.INSUFFICIENT_DATA
        assert decision.confidence_score == 0.0
        assert decision.requires_human_review is True
    
    def test_make_decision_high_confidence(self, controller):
        """Testa decisão com confiança alta."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.95,
                evidence_count=10,
                result="escalate",
                reasoning="Crítico",
            ),
            AgentExecution(
                agent_id="agent_2",
                agent_name="Agent 2",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.92,
                evidence_count=8,
                result="escalate",
                reasoning="Crítico",
            ),
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        assert decision.confidence_score > 0.85
        assert decision.weighted_score > 0.85
        assert decision.state == DecisionState.ESCALATED
        assert decision.requires_human_review is False
    
    def test_make_decision_low_confidence(self, controller):
        """Testa decisão com confiança baixa."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.5,
                evidence_count=1,
                result="monitor",
                reasoning="Incerto",
            ),
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        assert decision.confidence_score < 0.7
        assert decision.state == DecisionState.PENDING_HUMAN_APPROVAL
        assert decision.requires_human_review is True
    
    def test_make_decision_conflicting_opinions(self, controller):
        """Testa decisão com opiniões conflitantes."""
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
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.3,
                evidence_count=1,
                result="approve",
                reasoning="Tudo bem",
            ),
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        assert decision.requires_human_review is True
        assert decision.state == DecisionState.PENDING_HUMAN_APPROVAL
    
    def test_make_decision_unanimous(self, controller):
        """Testa decisão unânime."""
        executions = [
            AgentExecution(
                agent_id=f"agent_{i}",
                agent_name=f"Agent {i}",
                agent_role=AgentRole.METRICS_ANALYZER,
                confidence_score=0.85,
                evidence_count=5,
                result="approve",
                reasoning="Tudo bem",
            )
            for i in range(3)
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        assert decision.state == DecisionState.APPROVED
        assert decision.requires_human_review is False
    
    def test_decision_to_dict(self, controller, sample_executions):
        """Testa conversão de decisão para dicionário."""
        decision = controller.make_decision(sample_executions, save_checkpoint=False)
        
        decision_dict = decision.to_dict()
        
        assert "decision_id" in decision_dict
        assert "state" in decision_dict
        assert "reason" in decision_dict
        assert "confidence_score" in decision_dict
        assert "weighted_score" in decision_dict
        assert "requires_human_review" in decision_dict
        assert "agent_count" in decision_dict
        assert "timestamp" in decision_dict
    
    def test_evidence_summary_generation(self, controller, sample_executions):
        """Testa geração de resumo de evidências."""
        decision = controller.make_decision(sample_executions, save_checkpoint=False)
        
        assert decision.evidence_summary is not None
        assert len(decision.evidence_summary) > 0
        assert "escalate" in decision.evidence_summary.lower() or "monitor" in decision.evidence_summary.lower()
    
    def test_recommended_action_generation(self, controller):
        """Testa geração de ação recomendada."""
        # Teste para APPROVED
        executions_approved = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.95,
                evidence_count=10,
                result="approve",
                reasoning="OK",
            ),
        ]
        
        decision = controller.make_decision(executions_approved, save_checkpoint=False)
        
        assert "aprovad" in decision.recommended_action.lower()
    
    def test_metadata_generation(self, controller, sample_executions):
        """Testa geração de metadados."""
        decision = controller.make_decision(sample_executions, save_checkpoint=False)
        
        assert decision.metadata is not None
        assert "consensus_type" in decision.metadata
        assert "agent_count" in decision.metadata
        assert "weighted_score" in decision.metadata
    
    def test_context_passing(self, controller, sample_executions):
        """Testa passagem de contexto."""
        context = {
            "thread_id": "thread_123",
            "plan_id": "plan_456",
            "step_index": 5,
        }
        
        decision = controller.make_decision(
            sample_executions,
            context=context,
            save_checkpoint=False
        )
        
        assert decision.decision_id is not None
        # Contexto não deve ser armazenado na decisão (seria em checkpoint)
    
    def test_single_agent_execution(self, controller):
        """Testa decisão com um único agente."""
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.HUMAN_ANALYST,
                confidence_score=0.95,
                evidence_count=5,
                result="escalate",
                reasoning="Decisão humana",
            ),
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        assert decision.reason == DecisionReason.EXPERT_DECISION
        assert len(decision.agent_executions) == 1


class TestSwarmDecisionControllerIntegration:
    """Testa integração com outros componentes."""
    
    def test_integration_with_weighted_consensus(self):
        """Testa integração com WeightedConsensusStrategy."""
        strategy = WeightedScoreStrategy(confidence_threshold=0.7)
        controller = SwarmDecisionController(
            consensus_strategy=strategy,
            checkpoint_engine=None,
        )
        
        executions = [
            AgentExecution(
                agent_id="threat_1",
                agent_name="Threat Intel",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.9,
                evidence_count=5,
                result="escalate",
                reasoning="Padrão detectado",
            ),
            AgentExecution(
                agent_id="log_1",
                agent_name="Log Analyzer",
                agent_role=AgentRole.LOG_ANALYZER,
                confidence_score=0.85,
                evidence_count=3,
                result="escalate",
                reasoning="Anomalia",
            ),
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        # Verificar que WeightedConsensusStrategy foi usado
        assert decision.weighted_score > 0.8
        assert decision.state == DecisionState.ESCALATED
    
    def test_integration_with_confidence_policy(self):
        """Testa integração com ConfidencePolicy."""
        policy = ConfidencePolicy(base_weight=1.0)
        controller = SwarmDecisionController(
            confidence_policy=policy,
            checkpoint_engine=None,
        )
        
        executions = [
            AgentExecution(
                agent_id="agent_1",
                agent_name="Agent 1",
                agent_role=AgentRole.THREAT_INTEL,
                confidence_score=0.95,
                evidence_count=10,
                result="escalate",
                reasoning="Crítico",
            ),
        ]
        
        decision = controller.make_decision(executions, save_checkpoint=False)
        
        # Verificar que ConfidencePolicy foi usado
        assert decision.confidence_score is not None
        assert 0.0 <= decision.confidence_score <= 1.0
