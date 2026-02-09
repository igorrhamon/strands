"""
Contratos entre Agentes - Garantir compatibilidade de interfaces.

Este módulo define contratos que todos os agentes devem cumprir.
Utiliza Pydantic V2 para validação rigorosa de tipos.

Padrão: Contract Testing (inspirado em Pact.io)
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class AgentType(str, Enum):
    """Tipos de agentes no sistema."""
    
    THREAT_INTEL = "threat_intel"
    LOG_ANALYZER = "log_analyzer"
    METRICS_ANALYZER = "metrics_analyzer"
    HUMAN_ANALYST = "human_analyst"
    DECISION_ENGINE = "decision_engine"


class EvidenceLevel(str, Enum):
    """Níveis de evidência."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class AgentInputContract(BaseModel):
    """Contrato de entrada que todos os agentes devem aceitar."""
    
    execution_id: str = Field(..., description="ID único da execução")
    plan_id: str = Field(..., description="ID do plano de execução")
    step_index: int = Field(..., ge=0, description="Índice do passo")
    
    alert_data: Dict[str, Any] = Field(..., description="Dados do alerta")
    context: Dict[str, Any] = Field(default_factory=dict, description="Contexto da execução")
    
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Timeout em segundos")
    
    class Config:
        """Configuração Pydantic V2."""
        frozen = True  # Imutável
        json_schema_extra = {
            "example": {
                "execution_id": "exec_123",
                "plan_id": "plan_456",
                "step_index": 0,
                "alert_data": {"severity": "high", "source": "prometheus"},
                "context": {"user": "sre_team"},
                "timeout_seconds": 30
            }
        }


class AgentOutputContract(BaseModel):
    """Contrato de saída que todos os agentes devem produzir."""
    
    execution_id: str = Field(..., description="ID da execução")
    agent_type: AgentType = Field(..., description="Tipo do agente")
    agent_id: str = Field(..., description="ID único do agente")
    
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confiança 0-1")
    evidence_count: int = Field(..., ge=0, description="Número de evidências")
    evidence_level: EvidenceLevel = Field(..., description="Nível de evidência")
    
    analysis: str = Field(..., min_length=10, description="Análise textual")
    recommendations: List[str] = Field(default_factory=list, description="Recomendações")
    
    execution_time_ms: float = Field(..., ge=0, description="Tempo de execução em ms")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")
    
    error: Optional[str] = Field(default=None, description="Erro se houver")
    
    @validator('confidence')
    def validate_confidence(cls, v):
        """Validar confiança entre 0 e 1."""
        if not (0.0 <= v <= 1.0):
            raise ValueError('Confiança deve estar entre 0 e 1')
        return v
    
    @validator('evidence_count')
    def validate_evidence_count(cls, v):
        """Validar contagem de evidências."""
        if v < 0:
            raise ValueError('Contagem de evidências não pode ser negativa')
        return v
    
    class Config:
        """Configuração Pydantic V2."""
        frozen = True
        json_schema_extra = {
            "example": {
                "execution_id": "exec_123",
                "agent_type": "threat_intel",
                "agent_id": "agent_threat_001",
                "confidence": 0.85,
                "evidence_count": 3,
                "evidence_level": "high",
                "analysis": "Detectado padrão de ataque conhecido",
                "recommendations": ["Bloquear IP", "Aumentar monitoramento"],
                "execution_time_ms": 125.5,
                "timestamp": "2026-02-08T10:30:00Z"
            }
        }


class AgentContract(ABC):
    """Contrato abstrato que todos os agentes devem implementar."""
    
    @abstractmethod
    async def analyze(self, input_data: AgentInputContract) -> AgentOutputContract:
        """
        Analisar dados de entrada e retornar saída padronizada.
        
        Args:
            input_data: Dados de entrada conforme AgentInputContract
            
        Returns:
            AgentOutputContract com análise completa
            
        Raises:
            ValueError: Se entrada não cumpre contrato
            TimeoutError: Se execução exceder timeout
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_data: AgentInputContract) -> bool:
        """
        Validar se entrada cumpre contrato.
        
        Args:
            input_data: Dados de entrada
            
        Returns:
            True se válido, False caso contrário
        """
        pass
    
    @abstractmethod
    def validate_output(self, output_data: AgentOutputContract) -> bool:
        """
        Validar se saída cumpre contrato.
        
        Args:
            output_data: Dados de saída
            
        Returns:
            True se válido, False caso contrário
        """
        pass


class ContractValidator:
    """Validador de contratos entre agentes."""
    
    @staticmethod
    def validate_input(data: Dict[str, Any]) -> AgentInputContract:
        """
        Validar entrada conforme contrato.
        
        Args:
            data: Dados de entrada
            
        Returns:
            AgentInputContract validado
            
        Raises:
            ValueError: Se dados não cumprem contrato
        """
        try:
            return AgentInputContract(**data)
        except Exception as e:
            raise ValueError(f"Entrada não cumpre contrato: {str(e)}")
    
    @staticmethod
    def validate_output(data: Dict[str, Any]) -> AgentOutputContract:
        """
        Validar saída conforme contrato.
        
        Args:
            data: Dados de saída
            
        Returns:
            AgentOutputContract validado
            
        Raises:
            ValueError: Se dados não cumprem contrato
        """
        try:
            return AgentOutputContract(**data)
        except Exception as e:
            raise ValueError(f"Saída não cumpre contrato: {str(e)}")
    
    @staticmethod
    def validate_chain(
        agent_outputs: List[AgentOutputContract]
    ) -> bool:
        """
        Validar cadeia de execução entre agentes.
        
        Args:
            agent_outputs: Lista de saídas de agentes
            
        Returns:
            True se cadeia é válida
        """
        if not agent_outputs:
            return False
        
        # Verificar que todos têm mesmo execution_id
        execution_ids = {output.execution_id for output in agent_outputs}
        if len(execution_ids) > 1:
            return False
        
        # Verificar que todos têm confiança válida
        for output in agent_outputs:
            if not (0.0 <= output.confidence <= 1.0):
                return False
        
        # Verificar que há pelo menos uma evidência
        total_evidence = sum(output.evidence_count for output in agent_outputs)
        if total_evidence == 0:
            return False
        
        return True


class ContractViolation(Exception):
    """Exceção para violação de contrato."""
    
    def __init__(self, agent_type: str, violation: str):
        """
        Inicializar exceção.
        
        Args:
            agent_type: Tipo de agente que violou contrato
            violation: Descrição da violação
        """
        self.agent_type = agent_type
        self.violation = violation
        super().__init__(f"Violação de contrato em {agent_type}: {violation}")


class ContractMonitor:
    """Monitor de conformidade com contratos."""
    
    def __init__(self):
        """Inicializar monitor."""
        self.violations: List[ContractViolation] = []
        self.total_checks = 0
        self.passed_checks = 0
    
    def check_input(
        self,
        agent_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Verificar entrada contra contrato.
        
        Args:
            agent_type: Tipo de agente
            data: Dados de entrada
            
        Returns:
            True se passou, False caso contrário
        """
        self.total_checks += 1
        
        try:
            AgentInputContract(**data)
            self.passed_checks += 1
            return True
        except Exception as e:
            violation = ContractViolation(agent_type, str(e))
            self.violations.append(violation)
            return False
    
    def check_output(
        self,
        agent_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Verificar saída contra contrato.
        
        Args:
            agent_type: Tipo de agente
            data: Dados de saída
            
        Returns:
            True se passou, False caso contrário
        """
        self.total_checks += 1
        
        try:
            AgentOutputContract(**data)
            self.passed_checks += 1
            return True
        except Exception as e:
            violation = ContractViolation(agent_type, str(e))
            self.violations.append(violation)
            return False
    
    def get_compliance_rate(self) -> float:
        """
        Obter taxa de conformidade.
        
        Returns:
            Taxa de conformidade (0-1)
        """
        if self.total_checks == 0:
            return 1.0
        return self.passed_checks / self.total_checks
    
    def get_violations(self) -> List[ContractViolation]:
        """
        Obter lista de violações.
        
        Returns:
            Lista de violações
        """
        return self.violations.copy()
    
    def reset(self):
        """Resetar monitor."""
        self.violations.clear()
        self.total_checks = 0
        self.passed_checks = 0
