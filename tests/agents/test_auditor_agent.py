"""
Testes Unitários - AuditorAgent

Testa funcionalidades de auditoria, análise de linhagem e geração de relatórios.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from src.agents.auditor_agent import (
    AuditorAgent,
    AuditRiskLevel,
    AuditFinding,
    ExecutionLineage,
    AuditReport,
)
from src.auditing.audit_rules import (
    AuditRuleEngine,
    CoherenceValidationRule,
    InfiniteLoopDetectionRule,
    AgentConfidenceRule,
    RuleStatus,
    RuleSeverity,
)


class TestAuditorAgent:
    """Testes para AuditorAgent."""
    
    @pytest.fixture
    def mock_neo4j_adapter(self):
        """Cria mock do adaptador Neo4j."""
        adapter = Mock()
        adapter.execute_query = MagicMock(return_value=[])
        return adapter
    
    @pytest.fixture
    def auditor_agent(self, mock_neo4j_adapter):
        """Cria instância do auditor."""
        return AuditorAgent(mock_neo4j_adapter)
    
    def test_auditor_initialization(self, auditor_agent, mock_neo4j_adapter):
        """Testa inicialização do auditor."""
        assert auditor_agent.neo4j_adapter == mock_neo4j_adapter
        assert auditor_agent.logger is not None
    
    def test_extract_lineage_success(self, auditor_agent, mock_neo4j_adapter):
        """Testa extração bem-sucedida de linhagem."""
        # Mock do resultado da query
        mock_neo4j_adapter.execute_query.return_value = [{
            "execution_id": "exec_123",
            "start_time": datetime.now(timezone.utc),
            "end_time": datetime.now(timezone.utc),
            "agents": ["agent_1", "agent_2"],
            "evidence_count": 5,
            "decision_count": 2,
            "final_decision": {"value": "approve", "confidence": 0.9},
        }]
        
        lineage = auditor_agent._extract_lineage("exec_123")
        
        assert lineage is not None
        assert lineage.execution_id == "exec_123"
        assert len(lineage.agents_involved) == 2
        assert lineage.evidence_count == 5
        assert lineage.decisions_made == 2
    
    def test_extract_lineage_not_found(self, auditor_agent, mock_neo4j_adapter):
        """Testa extração quando execução não existe."""
        mock_neo4j_adapter.execute_query.return_value = []
        
        lineage = auditor_agent._extract_lineage("exec_not_found")
        
        assert lineage is None
    
    def test_validate_coherence_high_score(self, auditor_agent, mock_neo4j_adapter):
        """Testa validação de coerência com score alto."""
        mock_neo4j_adapter.execute_query.return_value = [
            {"weight": 2.0, "evidence_value": 0.8, "decision_value": 0.85, "decision_confidence": 0.9},
            {"weight": 1.0, "evidence_value": 0.7, "decision_value": 0.75, "decision_confidence": 0.85},
        ]
        
        lineage = ExecutionLineage(
            execution_id="exec_123",
            start_time=datetime.now(timezone.utc),
            agents_involved=["agent_1"],
            evidence_count=2,
            decisions_made=1,
        )
        
        findings, coherence_score = auditor_agent._validate_coherence("exec_123", lineage)
        
        assert coherence_score >= 0.7
        assert len(findings) == 0  # Sem achados se coerência alta
    
    def test_validate_coherence_low_score(self, auditor_agent, mock_neo4j_adapter):
        """Testa validação de coerência com score baixo."""
        mock_neo4j_adapter.execute_query.return_value = [
            {"weight": 1.0, "evidence_value": 0.2, "decision_value": 0.9, "decision_confidence": 0.95},
        ]
        
        lineage = ExecutionLineage(
            execution_id="exec_123",
            start_time=datetime.now(timezone.utc),
            agents_involved=["agent_1"],
            evidence_count=1,
            decisions_made=1,
        )
        
        findings, coherence_score = auditor_agent._validate_coherence("exec_123", lineage)
        
        assert coherence_score < 0.7
        assert len(findings) > 0
        assert findings[0].risk_level in [AuditRiskLevel.HIGH, AuditRiskLevel.MEDIUM]
    
    def test_detect_loops_no_loop(self, auditor_agent, mock_neo4j_adapter):
        """Testa detecção de loop quando não há loop."""
        mock_neo4j_adapter.execute_query.return_value = [
            {"agent_name": "agent_1", "retry_count": 2, "confidence_values": [0.5, 0.8]},
        ]
        
        lineage = ExecutionLineage(
            execution_id="exec_123",
            start_time=datetime.now(timezone.utc),
            agents_involved=["agent_1"],
            evidence_count=2,
            decisions_made=1,
        )
        
        findings, loop_detected = auditor_agent._detect_loops("exec_123", lineage)
        
        assert not loop_detected
        assert len(findings) == 0
    
    def test_detect_loops_infinite_loop(self, auditor_agent, mock_neo4j_adapter):
        """Testa detecção de loop infinito."""
        mock_neo4j_adapter.execute_query.return_value = [
            {"agent_name": "agent_1", "retry_count": 10, "confidence_values": [0.5, 0.51, 0.52, 0.51, 0.52]},
        ]
        
        lineage = ExecutionLineage(
            execution_id="exec_123",
            start_time=datetime.now(timezone.utc),
            agents_involved=["agent_1"],
            evidence_count=5,
            decisions_made=1,
        )
        
        findings, loop_detected = auditor_agent._detect_loops("exec_123", lineage)
        
        assert loop_detected
        assert len(findings) > 0
        assert findings[0].risk_level == AuditRiskLevel.CRITICAL
    
    def test_analyze_patterns_low_confidence(self, auditor_agent, mock_neo4j_adapter):
        """Testa análise de padrões com confiança baixa."""
        mock_neo4j_adapter.execute_query.return_value = [
            {"agent_name": "agent_1", "avg_confidence": 0.3, "min_confidence": 0.2, "max_confidence": 0.4, "confidence_stdev": 0.08},
        ]
        
        lineage = ExecutionLineage(
            execution_id="exec_123",
            start_time=datetime.now(timezone.utc),
            agents_involved=["agent_1"],
            evidence_count=3,
            decisions_made=1,
        )
        
        findings = auditor_agent._analyze_patterns("exec_123", lineage)
        
        assert len(findings) > 0
        assert any(f.risk_level == AuditRiskLevel.MEDIUM for f in findings)
    
    def test_calculate_overall_risk_no_findings(self, auditor_agent):
        """Testa cálculo de risco sem achados."""
        risk = auditor_agent._calculate_overall_risk([])
        assert risk == AuditRiskLevel.NONE
    
    def test_calculate_overall_risk_with_critical(self, auditor_agent):
        """Testa cálculo de risco com achado crítico."""
        findings = [
            AuditFinding(
                finding_id="f1",
                rule_name="test",
                risk_level=AuditRiskLevel.CRITICAL,
                description="test",
                evidence={},
                recommendation="test",
            )
        ]
        
        risk = auditor_agent._calculate_overall_risk(findings)
        assert risk == AuditRiskLevel.CRITICAL
    
    def test_generate_refinement_suggestions(self, auditor_agent):
        """Testa geração de sugestões de refino."""
        findings = [
            AuditFinding(
                finding_id="f1",
                rule_name="Análise de Padrões",
                risk_level=AuditRiskLevel.MEDIUM,
                description="test",
                evidence={"agent_name": "agent_1"},
                recommendation="test",
            )
        ]
        
        suggestions = auditor_agent._generate_refinement_suggestions(
            findings=findings,
            coherence_score=0.6,
            loop_detected=True,
        )
        
        assert len(suggestions) > 0
        assert any("CRÍTICO" in s for s in suggestions)


class TestAuditRuleEngine:
    """Testes para AuditRuleEngine."""
    
    @pytest.fixture
    def rule_engine(self):
        """Cria instância do motor de regras."""
        return AuditRuleEngine()
    
    def test_engine_initialization(self, rule_engine):
        """Testa inicialização do motor."""
        assert len(rule_engine.rules) >= 5
    
    def test_coherence_rule_passed(self, rule_engine):
        """Testa regra de coerência - passou."""
        rule = CoherenceValidationRule(threshold=0.7)
        context = {"coherence_score": 0.85}
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.PASSED
        assert result.severity == RuleSeverity.ERROR
    
    def test_coherence_rule_warning(self, rule_engine):
        """Testa regra de coerência - aviso."""
        rule = CoherenceValidationRule(threshold=0.7)
        context = {"coherence_score": 0.6}
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.WARNING
    
    def test_coherence_rule_failed(self, rule_engine):
        """Testa regra de coerência - falhou."""
        rule = CoherenceValidationRule(threshold=0.7)
        context = {"coherence_score": 0.3}
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.FAILED
    
    def test_infinite_loop_rule_no_loop(self, rule_engine):
        """Testa regra de loop - sem loop."""
        rule = InfiniteLoopDetectionRule(max_retries=5, min_improvement=0.05)
        context = {
            "retry_count": 3,
            "confidence_improvement": 0.1,
        }
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.PASSED
    
    def test_infinite_loop_rule_detected(self, rule_engine):
        """Testa regra de loop - loop detectado."""
        rule = InfiniteLoopDetectionRule(max_retries=5, min_improvement=0.05)
        context = {
            "retry_count": 10,
            "confidence_improvement": 0.02,
        }
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.FAILED
        assert result.severity == RuleSeverity.CRITICAL
    
    def test_agent_confidence_rule_passed(self, rule_engine):
        """Testa regra de confiança de agente - passou."""
        rule = AgentConfidenceRule(min_confidence=0.4)
        context = {
            "agent_confidences": {
                "agent_1": 0.8,
                "agent_2": 0.6,
            }
        }
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.PASSED
    
    def test_agent_confidence_rule_warning(self, rule_engine):
        """Testa regra de confiança de agente - aviso."""
        rule = AgentConfidenceRule(min_confidence=0.4)
        context = {
            "agent_confidences": {
                "agent_1": 0.8,
                "agent_2": 0.3,
            }
        }
        
        result = rule.execute(context)
        
        assert result.status == RuleStatus.WARNING
        assert len(result.details["low_confidence_agents"]) == 1
    
    def test_execute_all_rules(self, rule_engine):
        """Testa execução de todas as regras."""
        context = {
            "coherence_score": 0.8,
            "retry_count": 3,
            "confidence_improvement": 0.1,
            "agent_confidences": {"agent_1": 0.7},
            "contradiction_rate": 0.1,
            "decision_duration_seconds": 2.0,
        }
        
        results = rule_engine.execute_all(context)
        
        assert len(results) >= 5
        assert all(hasattr(r, "status") for r in results)
    
    def test_filter_results_by_status(self, rule_engine):
        """Testa filtragem de resultados por status."""
        context = {"coherence_score": 0.85}
        results = rule_engine.execute_all(context)
        
        passed = rule_engine.get_results_by_status(results, RuleStatus.PASSED)
        
        assert len(passed) > 0
    
    def test_generate_summary(self, rule_engine):
        """Testa geração de sumário."""
        context = {
            "coherence_score": 0.8,
            "retry_count": 3,
            "confidence_improvement": 0.1,
            "agent_confidences": {"agent_1": 0.7},
            "contradiction_rate": 0.1,
            "decision_duration_seconds": 2.0,
        }
        
        results = rule_engine.execute_all(context)
        summary = rule_engine.generate_summary(results)
        
        assert "total_rules" in summary
        assert "passed" in summary
        assert "warnings" in summary
        assert "failed" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
