"""
Testes para RecommenderAgent - Análise Avançada de Recomendações

Testa a capacidade do agente de:
- Refinar recomendações com planos de ação específicos
- Avaliar risco com base em padrões conhecidos
- Validar níveis de automação baseado em risco
- Incorporar insights de incidentes similares
- Gerar playbooks de remediação
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone

from src.agents.governance.recommender import (
    RecommenderAgent,
    RiskLevel,
    RemediationPlaybook
)
from src.models.decision import DecisionCandidate, AutomationLevel, DecisionStatus


class TestRecommenderAgent:
    """Testes para RecommenderAgent."""
    
    @pytest.fixture
    def recommender(self):
        """Fixture para instanciar RecommenderAgent."""
        return RecommenderAgent()
    
    @pytest.fixture
    def decision_candidate_cpu(self):
        """Fixture para candidato de decisão com problema de CPU."""
        return DecisionCandidate(
            alert_reference="alert-cpu-001",
            summary="CPU usage is 95.5%, exceeding threshold",
            primary_hypothesis="High CPU usage detected in api-service",
            confidence_score=0.92,
            risk_assessment="Potential CPU saturation",
            automation_level=AutomationLevel.FULL
        )
    
    @pytest.fixture
    def decision_candidate_memory(self):
        """Fixture para candidato de decisão com problema de memória."""
        return DecisionCandidate(
            alert_reference="alert-memory-001",
            summary="Memory usage is 85.2%, exceeding threshold",
            primary_hypothesis="Memory leak detected in worker-service",
            confidence_score=0.88,
            risk_assessment="Potential OOMKilled",
            automation_level=AutomationLevel.FULL
        )
    
    @pytest.fixture
    def decision_candidate_restart(self):
        """Fixture para candidato de decisão com problema de restart."""
        return DecisionCandidate(
            alert_reference="alert-restart-001",
            summary="Pod has restarted 15 times in 10 minutes",
            primary_hypothesis="CrashLoopBackOff detected in database-service",
            confidence_score=0.95,
            risk_assessment="Service instability",
            automation_level=AutomationLevel.FULL
        )
    
    def test_recommender_initialization(self, recommender):
        """Testa inicialização do RecommenderAgent."""
        assert recommender.agent_id == "recommender"
        assert recommender.detected_playbooks == []
        assert len(recommender.PLAYBOOK_TEMPLATES) == 5
    
    def test_refine_recommendation_returns_decision_candidate(self, recommender, decision_candidate_cpu):
        """Testa se refine_recommendation retorna DecisionCandidate válido."""
        result = recommender.refine_recommendation(decision_candidate_cpu)
        
        assert isinstance(result, DecisionCandidate)
        assert result.decision_id == decision_candidate_cpu.decision_id
        assert len(result.suggested_actions) > 0
    
    def test_cpu_issue_handling(self, recommender, decision_candidate_cpu):
        """Testa tratamento de problema de CPU."""
        result = recommender.refine_recommendation(decision_candidate_cpu)
        
        assert "CPU saturation" in result.risk_assessment
        assert len(result.suggested_actions) > 0
        assert "CPU" in result.selected_action or "cpu" in result.selected_action.lower()
    
    def test_memory_issue_handling(self, recommender, decision_candidate_memory):
        """Testa tratamento de problema de memória."""
        result = recommender.refine_recommendation(decision_candidate_memory)
        
        assert "Memory" in result.risk_assessment or "memory" in result.risk_assessment.lower()
        assert len(result.suggested_actions) > 0
        assert result.automation_level == AutomationLevel.MANUAL
    
    def test_restart_issue_handling(self, recommender, decision_candidate_restart):
        """Testa tratamento de problema de restart."""
        result = recommender.refine_recommendation(decision_candidate_restart)
        
        assert "instability" in result.risk_assessment.lower()
        assert len(result.suggested_actions) > 0
        assert result.automation_level == AutomationLevel.MANUAL
    
    def test_automation_level_downgrade_for_high_risk(self, recommender, decision_candidate_memory):
        """Testa downgrade de nível de automação para risco alto."""
        assert decision_candidate_memory.automation_level == AutomationLevel.FULL
        
        result = recommender.refine_recommendation(decision_candidate_memory)
        
        assert result.automation_level == AutomationLevel.MANUAL
    
    def test_automation_level_downgrade_for_critical_risk(self, recommender):
        """Testa downgrade de nível de automação para risco crítico."""
        candidate = DecisionCandidate(
            alert_reference="alert-critical-001",
            summary="Critical data loss detected",
            primary_hypothesis="Critical security vulnerability detected",
            confidence_score=0.99,
            risk_assessment="Critical risk",
            automation_level=AutomationLevel.FULL
        )
        
        result = recommender.refine_recommendation(candidate)
        
        assert result.automation_level == AutomationLevel.MANUAL
    
    def test_playbook_detection(self, recommender, decision_candidate_cpu):
        """Testa detecção de playbook apropriado."""
        recommender.refine_recommendation(decision_candidate_cpu)
        
        assert len(recommender.detected_playbooks) > 0
        assert recommender.detected_playbooks[0].name == "CPU Saturation Playbook"
    
    def test_multiple_playbooks_available(self, recommender):
        """Testa disponibilidade de múltiplos playbooks."""
        playbooks = recommender.get_all_playbooks()
        
        assert len(playbooks) == 5
        assert "cpu" in playbooks
        assert "memory" in playbooks
        assert "restart" in playbooks
        assert "latency" in playbooks
        assert "error_rate" in playbooks
    
    def test_get_playbook_for_hypothesis(self, recommender):
        """Testa busca de playbook para hipótese."""
        hypothesis = "High CPU usage detected"
        playbook = recommender.get_playbook_for_hypothesis(hypothesis)
        
        assert playbook is not None
        assert playbook.name == "CPU Saturation Playbook"
    
    def test_get_playbook_for_unknown_hypothesis(self, recommender):
        """Testa busca de playbook para hipótese desconhecida."""
        hypothesis = "Unknown issue detected"
        playbook = recommender.get_playbook_for_hypothesis(hypothesis)
        
        assert playbook is None
    
    def test_suggested_actions_are_specific(self, recommender, decision_candidate_cpu):
        """Testa se ações sugeridas são específicas e acionáveis."""
        result = recommender.refine_recommendation(decision_candidate_cpu)
        
        for action in result.suggested_actions:
            assert isinstance(action, str)
            assert len(action) > 10
            # Deve conter números de passos ou verbos de ação
            assert any(char.isdigit() for char in action) or any(
                verb in action.lower() for verb in ["check", "verify", "analyze", "consider"]
            )
    
    def test_risk_assessment_updated(self, recommender, decision_candidate_cpu):
        """Testa se avaliação de risco é atualizada."""
        original_assessment = decision_candidate_cpu.risk_assessment
        result = recommender.refine_recommendation(decision_candidate_cpu)
        
        assert result.risk_assessment != original_assessment
        assert len(result.risk_assessment) > len(original_assessment)
    
    def test_selected_action_is_set(self, recommender, decision_candidate_cpu):
        """Testa se ação selecionada é definida."""
        result = recommender.refine_recommendation(decision_candidate_cpu)
        
        assert result.selected_action != ""
        assert len(result.selected_action) > 0
    
    def test_similar_incident_incorporation(self, recommender):
        """Testa incorporação de insights de incidentes similares."""
        candidate = DecisionCandidate(
            alert_reference="alert-similar-001",
            summary="Similar incident detected in history",
            primary_hypothesis="High CPU usage - similar incident pattern",
            confidence_score=0.90,
            risk_assessment="Potential CPU saturation",
            automation_level=AutomationLevel.FULL
        )
        
        result = recommender.refine_recommendation(candidate)
        
        assert "similar" in result.risk_assessment.lower() or "pattern" in result.risk_assessment.lower()
    
    def test_playbook_steps_included_in_actions(self, recommender, decision_candidate_cpu):
        """Testa se passos do playbook são incluídos nas ações."""
        result = recommender.refine_recommendation(decision_candidate_cpu)
        
        # Deve ter múltiplos passos numerados
        numbered_steps = [a for a in result.suggested_actions if a[0].isdigit()]
        assert len(numbered_steps) > 0
    
    def test_latency_issue_handling(self, recommender):
        """Testa tratamento de problema de latência."""
        candidate = DecisionCandidate(
            alert_reference="alert-latency-001",
            summary="High latency detected",
            primary_hypothesis="High latency in API responses",
            confidence_score=0.85,
            risk_assessment="Performance degradation",
            automation_level=AutomationLevel.FULL
        )
        
        result = recommender.refine_recommendation(candidate)
        
        assert "latency" in result.risk_assessment.lower() or "performance" in result.risk_assessment.lower()
        assert len(result.suggested_actions) > 0
    
    def test_error_rate_issue_handling(self, recommender):
        """Testa tratamento de problema de taxa de erro."""
        candidate = DecisionCandidate(
            alert_reference="alert-error-001",
            summary="High error rate detected",
            primary_hypothesis="Error rate exceeds threshold",
            confidence_score=0.88,
            risk_assessment="High error rate",
            automation_level=AutomationLevel.FULL
        )
        
        result = recommender.refine_recommendation(candidate)
        
        assert "error" in result.risk_assessment.lower()
        assert len(result.suggested_actions) > 0
    
    def test_generic_issue_handling(self, recommender):
        """Testa tratamento de problema genérico."""
        candidate = DecisionCandidate(
            alert_reference="alert-generic-001",
            summary="Unknown issue detected",
            primary_hypothesis="Unknown pattern detected",
            confidence_score=0.50,
            risk_assessment="Unknown risk",
            automation_level=AutomationLevel.FULL
        )
        
        result = recommender.refine_recommendation(candidate)
        
        assert "Generic" in result.risk_assessment or "generic" in result.risk_assessment.lower()
        assert "diagnostic" in result.suggested_actions[0].lower()


class TestRemediationPlaybook:
    """Testes para RemediationPlaybook."""
    
    def test_playbook_initialization(self):
        """Testa inicialização de RemediationPlaybook."""
        playbook = RemediationPlaybook(
            name="Test Playbook",
            description="Test description",
            steps=["Step 1", "Step 2"],
            risk_level=RiskLevel.HIGH,
            estimated_time_minutes=30,
            requires_manual_approval=True
        )
        
        assert playbook.name == "Test Playbook"
        assert playbook.description == "Test description"
        assert len(playbook.steps) == 2
        assert playbook.risk_level == RiskLevel.HIGH
        assert playbook.estimated_time_minutes == 30
        assert playbook.requires_manual_approval is True
    
    def test_playbook_to_dict(self):
        """Testa conversão de playbook para dicionário."""
        playbook = RemediationPlaybook(
            name="Test Playbook",
            description="Test description",
            steps=["Step 1", "Step 2"],
            risk_level=RiskLevel.MEDIUM,
            estimated_time_minutes=20,
            requires_manual_approval=False
        )
        
        playbook_dict = playbook.to_dict()
        
        assert playbook_dict["name"] == "Test Playbook"
        assert playbook_dict["description"] == "Test description"
        assert playbook_dict["risk_level"] == "MEDIUM"
        assert playbook_dict["estimated_time_minutes"] == 20
        assert playbook_dict["requires_manual_approval"] is False


class TestRiskLevel:
    """Testes para RiskLevel enum."""
    
    def test_risk_level_values(self):
        """Testa valores do enum RiskLevel."""
        assert RiskLevel.CRITICAL.value == "CRITICAL"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.MEDIUM.value == "MEDIUM"
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MINIMAL.value == "MINIMAL"
    
    def test_risk_level_comparison(self):
        """Testa comparação de níveis de risco."""
        assert RiskLevel.CRITICAL != RiskLevel.HIGH
        assert RiskLevel.HIGH != RiskLevel.MEDIUM
        assert RiskLevel.CRITICAL in [RiskLevel.CRITICAL, RiskLevel.HIGH]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
