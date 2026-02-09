"""
Testes para contratos entre agentes.

Valida que todos os agentes cumprem contratos obrigatórios.
"""

import pytest
from datetime import datetime

from src.contracts.agent_contracts import (
    AgentInputContract,
    AgentOutputContract,
    AgentType,
    EvidenceLevel,
    ContractValidator,
    ContractViolation,
    ContractMonitor,
)


class TestAgentInputContract:
    """Testes para contrato de entrada."""
    
    def test_valid_input_contract(self):
        """Validar entrada válida."""
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": 0,
            "alert_data": {"severity": "high"},
            "context": {"user": "sre"},
            "timeout_seconds": 30
        }
        
        contract = AgentInputContract(**data)
        assert contract.execution_id == "exec_123"
        assert contract.plan_id == "plan_456"
        assert contract.step_index == 0
        assert contract.timeout_seconds == 30
    
    def test_invalid_step_index(self):
        """Rejeitar step_index negativo."""
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": -1,
            "alert_data": {"severity": "high"},
        }
        
        with pytest.raises(ValueError):
            AgentInputContract(**data)
    
    def test_invalid_timeout(self):
        """Rejeitar timeout fora do intervalo."""
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": 0,
            "alert_data": {"severity": "high"},
            "timeout_seconds": 400  # > 300
        }
        
        with pytest.raises(ValueError):
            AgentInputContract(**data)
    
    def test_contract_is_frozen(self):
        """Verificar que contrato é imutável."""
        contract = AgentInputContract(
            execution_id="exec_123",
            plan_id="plan_456",
            step_index=0,
            alert_data={"severity": "high"}
        )
        
        with pytest.raises(Exception):
            contract.execution_id = "exec_999"


class TestAgentOutputContract:
    """Testes para contrato de saída."""
    
    def test_valid_output_contract(self):
        """Validar saída válida."""
        data = {
            "execution_id": "exec_123",
            "agent_type": AgentType.THREAT_INTEL,
            "agent_id": "agent_threat_001",
            "confidence": 0.85,
            "evidence_count": 3,
            "evidence_level": EvidenceLevel.HIGH,
            "analysis": "Detectado padrão de ataque conhecido",
            "recommendations": ["Bloquear IP"],
            "execution_time_ms": 125.5
        }
        
        contract = AgentOutputContract(**data)
        assert contract.confidence == 0.85
        assert contract.evidence_count == 3
        assert contract.agent_type == AgentType.THREAT_INTEL
    
    def test_invalid_confidence(self):
        """Rejeitar confiança fora do intervalo."""
        data = {
            "execution_id": "exec_123",
            "agent_type": AgentType.THREAT_INTEL,
            "agent_id": "agent_threat_001",
            "confidence": 1.5,  # > 1.0
            "evidence_count": 3,
            "evidence_level": EvidenceLevel.HIGH,
            "analysis": "Análise válida",
            "execution_time_ms": 125.5
        }
        
        with pytest.raises(ValueError):
            AgentOutputContract(**data)
    
    def test_invalid_evidence_count(self):
        """Rejeitar contagem negativa de evidências."""
        data = {
            "execution_id": "exec_123",
            "agent_type": AgentType.THREAT_INTEL,
            "agent_id": "agent_threat_001",
            "confidence": 0.85,
            "evidence_count": -1,
            "evidence_level": EvidenceLevel.HIGH,
            "analysis": "Análise válida",
            "execution_time_ms": 125.5
        }
        
        with pytest.raises(ValueError):
            AgentOutputContract(**data)
    
    def test_short_analysis_rejected(self):
        """Rejeitar análise muito curta."""
        data = {
            "execution_id": "exec_123",
            "agent_type": AgentType.THREAT_INTEL,
            "agent_id": "agent_threat_001",
            "confidence": 0.85,
            "evidence_count": 3,
            "evidence_level": EvidenceLevel.HIGH,
            "analysis": "Curta",  # < 10 caracteres
            "execution_time_ms": 125.5
        }
        
        with pytest.raises(ValueError):
            AgentOutputContract(**data)


class TestContractValidator:
    """Testes para validador de contratos."""
    
    def test_validate_valid_input(self):
        """Validar entrada válida."""
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": 0,
            "alert_data": {"severity": "high"}
        }
        
        contract = ContractValidator.validate_input(data)
        assert isinstance(contract, AgentInputContract)
        assert contract.execution_id == "exec_123"
    
    def test_validate_invalid_input(self):
        """Rejeitar entrada inválida."""
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": -1,
            "alert_data": {"severity": "high"}
        }
        
        with pytest.raises(ValueError):
            ContractValidator.validate_input(data)
    
    def test_validate_valid_output(self):
        """Validar saída válida."""
        data = {
            "execution_id": "exec_123",
            "agent_type": AgentType.THREAT_INTEL,
            "agent_id": "agent_threat_001",
            "confidence": 0.85,
            "evidence_count": 3,
            "evidence_level": EvidenceLevel.HIGH,
            "analysis": "Análise válida com mais de 10 caracteres",
            "execution_time_ms": 125.5
        }
        
        contract = ContractValidator.validate_output(data)
        assert isinstance(contract, AgentOutputContract)
        assert contract.confidence == 0.85
    
    def test_validate_chain_valid(self):
        """Validar cadeia válida."""
        outputs = [
            AgentOutputContract(
                execution_id="exec_123",
                agent_type=AgentType.THREAT_INTEL,
                agent_id="agent_1",
                confidence=0.85,
                evidence_count=3,
                evidence_level=EvidenceLevel.HIGH,
                analysis="Análise válida com mais de 10 caracteres",
                execution_time_ms=125.5
            ),
            AgentOutputContract(
                execution_id="exec_123",
                agent_type=AgentType.LOG_ANALYZER,
                agent_id="agent_2",
                confidence=0.75,
                evidence_count=2,
                evidence_level=EvidenceLevel.HIGH,
                analysis="Outra análise válida com mais de 10 caracteres",
                execution_time_ms=100.0
            )
        ]
        
        assert ContractValidator.validate_chain(outputs) is True
    
    def test_validate_chain_different_execution_ids(self):
        """Rejeitar cadeia com execution_ids diferentes."""
        outputs = [
            AgentOutputContract(
                execution_id="exec_123",
                agent_type=AgentType.THREAT_INTEL,
                agent_id="agent_1",
                confidence=0.85,
                evidence_count=3,
                evidence_level=EvidenceLevel.HIGH,
                analysis="Análise válida com mais de 10 caracteres",
                execution_time_ms=125.5
            ),
            AgentOutputContract(
                execution_id="exec_999",  # Diferente!
                agent_type=AgentType.LOG_ANALYZER,
                agent_id="agent_2",
                confidence=0.75,
                evidence_count=2,
                evidence_level=EvidenceLevel.HIGH,
                analysis="Outra análise válida com mais de 10 caracteres",
                execution_time_ms=100.0
            )
        ]
        
        assert ContractValidator.validate_chain(outputs) is False
    
    def test_validate_chain_no_evidence(self):
        """Rejeitar cadeia sem evidências."""
        outputs = [
            AgentOutputContract(
                execution_id="exec_123",
                agent_type=AgentType.THREAT_INTEL,
                agent_id="agent_1",
                confidence=0.85,
                evidence_count=0,  # Sem evidências!
                evidence_level=EvidenceLevel.LOW,
                analysis="Análise válida com mais de 10 caracteres",
                execution_time_ms=125.5
            )
        ]
        
        assert ContractValidator.validate_chain(outputs) is False


class TestContractMonitor:
    """Testes para monitor de conformidade."""
    
    def test_monitor_valid_input(self):
        """Monitor registra entrada válida."""
        monitor = ContractMonitor()
        
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": 0,
            "alert_data": {"severity": "high"}
        }
        
        result = monitor.check_input("threat_intel", data)
        assert result is True
        assert monitor.passed_checks == 1
        assert monitor.total_checks == 1
    
    def test_monitor_invalid_input(self):
        """Monitor registra entrada inválida."""
        monitor = ContractMonitor()
        
        data = {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": -1,  # Inválido!
            "alert_data": {"severity": "high"}
        }
        
        result = monitor.check_input("threat_intel", data)
        assert result is False
        assert monitor.passed_checks == 0
        assert monitor.total_checks == 1
        assert len(monitor.violations) == 1
    
    def test_monitor_compliance_rate(self):
        """Monitor calcula taxa de conformidade."""
        monitor = ContractMonitor()
        
        # 2 válidas
        for _ in range(2):
            monitor.check_input("threat_intel", {
                "execution_id": "exec_123",
                "plan_id": "plan_456",
                "step_index": 0,
                "alert_data": {"severity": "high"}
            })
        
        # 1 inválida
        monitor.check_input("threat_intel", {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": -1,
            "alert_data": {"severity": "high"}
        })
        
        assert monitor.get_compliance_rate() == pytest.approx(2/3, abs=0.01)
    
    def test_monitor_reset(self):
        """Monitor pode ser resetado."""
        monitor = ContractMonitor()
        
        monitor.check_input("threat_intel", {
            "execution_id": "exec_123",
            "plan_id": "plan_456",
            "step_index": -1,
            "alert_data": {"severity": "high"}
        })
        
        assert monitor.total_checks == 1
        assert len(monitor.violations) == 1
        
        monitor.reset()
        
        assert monitor.total_checks == 0
        assert len(monitor.violations) == 0
        assert monitor.get_compliance_rate() == 1.0


class TestContractViolation:
    """Testes para exceção de violação."""
    
    def test_violation_creation(self):
        """Criar violação de contrato."""
        violation = ContractViolation(
            agent_type="threat_intel",
            violation="Confiança inválida"
        )
        
        assert violation.agent_type == "threat_intel"
        assert violation.violation == "Confiança inválida"
        assert "threat_intel" in str(violation)
