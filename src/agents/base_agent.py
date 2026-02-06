"""
BaseAgent - Classe abstrata que define o contrato para todos os agentes do Strands.

Seguindo princípios SOLID (Single Responsibility, Open/Closed, Liskov Substitution,
Interface Segregation, Dependency Inversion), esta classe garante que todos os agentes
implementem os métodos obrigatórios e sigam o mesmo padrão de execução.

Padrão inspirado em Java Interfaces e Abstract Classes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
import logging
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Estados possíveis de um agente durante execução."""
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"


class EvidenceType(str, Enum):
    """Tipos de evidência que um agente pode gerar."""
    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    ALERT = "alert"
    INFERENCE = "inference"
    HEURISTIC = "heuristic"


@dataclass
class Evidence:
    """Representa uma evidência coletada por um agente.
    
    Atributos:
        type: Tipo de evidência (métrica, log, trace, etc)
        source: Origem da evidência (ex: prometheus, jaeger, neo4j)
        value: Valor ou conteúdo da evidência
        timestamp: Quando foi coletada
        confidence: Score de confiança (0.0 a 1.0)
        metadata: Dados adicionais
    """
    type: EvidenceType
    source: str
    value: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Valida a evidência após inicialização."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence deve estar entre 0.0 e 1.0, recebido: {self.confidence}")
        
        if not self.source:
            raise ValueError("Source é obrigatório")


@dataclass
class AgentOutput:
    """Saída padronizada de um agente.
    
    Atributos:
        agent_id: ID único do agente
        agent_name: Nome do agente
        status: Status da execução
        result: Resultado da análise
        confidence: Score de confiança geral (0.0 a 1.0)
        evidence: Lista de evidências coletadas
        execution_time_ms: Tempo de execução em milissegundos
        error_message: Mensagem de erro, se houver
        metadata: Dados adicionais
    """
    agent_id: str
    agent_name: str
    status: AgentStatus
    result: Any
    confidence: float
    evidence: List[Evidence] = field(default_factory=list)
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Valida a saída após inicialização."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence deve estar entre 0.0 e 1.0, recebido: {self.confidence}")
        
        if self.status == AgentStatus.FAILED and not self.error_message:
            raise ValueError("error_message é obrigatório quando status é FAILED")
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário para serialização."""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "status": self.status.value,
            "result": self.result,
            "confidence": self.confidence,
            "evidence_count": len(self.evidence),
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """Classe abstrata que define o contrato para todos os agentes.
    
    Um agente é responsável por:
    1. Coletar dados de uma fonte específica
    2. Analisar os dados
    3. Gerar evidências
    4. Retornar um resultado com score de confiança
    5. Registrar evidências no Neo4j
    
    Exemplo de implementação:
    
        class MyAgent(BaseAgent):
            def __init__(self, name: str, config: Dict):
                super().__init__(name, config)
            
            async def execute(self, input_data: Dict) -> AgentOutput:
                try:
                    # Coletar dados
                    data = await self.collect_data(input_data)
                    
                    # Analisar
                    result = self.analyze(data)
                    
                    # Validar
                    self.validate_output(result)
                    
                    # Gerar evidências
                    evidence = self.generate_evidence(data, result)
                    
                    # Retornar saída
                    return AgentOutput(
                        agent_id=self.agent_id,
                        agent_name=self.name,
                        status=AgentStatus.SUCCESS,
                        result=result,
                        confidence=0.95,
                        evidence=evidence,
                    )
                except Exception as e:
                    return AgentOutput(
                        agent_id=self.agent_id,
                        agent_name=self.name,
                        status=AgentStatus.FAILED,
                        result=None,
                        confidence=0.0,
                        error_message=str(e),
                    )
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """Inicializa o agente.
        
        Args:
            name: Nome único do agente
            config: Configuração do agente
        """
        self.agent_id = str(uuid4())
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"agent.{name}")
        self._execution_count = 0
        self._error_count = 0
        self._total_execution_time = 0.0
        
        self.logger.info(f"Agent initialized: {name} (ID: {self.agent_id})")
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> AgentOutput:
        """Executa o agente.
        
        Este é o método principal que deve ser implementado por cada agente.
        
        Args:
            input_data: Dados de entrada para o agente
        
        Returns:
            AgentOutput com resultado da análise
        """
        pass
    
    @abstractmethod
    async def collect_data(self, input_data: Dict[str, Any]) -> Any:
        """Coleta dados da fonte específica do agente.
        
        Args:
            input_data: Dados de entrada
        
        Returns:
            Dados coletados
        """
        pass
    
    @abstractmethod
    def analyze(self, data: Any) -> Any:
        """Analisa os dados coletados.
        
        Args:
            data: Dados a analisar
        
        Returns:
            Resultado da análise
        """
        pass
    
    @abstractmethod
    def validate_output(self, result: Any) -> bool:
        """Valida a saída do agente.
        
        Garante que o resultado está em formato esperado e não contém lixo.
        
        Args:
            result: Resultado a validar
        
        Returns:
            True se válido, False caso contrário
        
        Raises:
            ValueError: Se o resultado não for válido
        """
        pass
    
    @abstractmethod
    async def generate_evidence(self, data: Any, result: Any) -> List[Evidence]:
        """Gera evidências baseadas na análise.
        
        Args:
            data: Dados analisados
            result: Resultado da análise
        
        Returns:
            Lista de evidências
        """
        pass
    
    async def register_evidence(self, evidence: List[Evidence], context_id: str) -> bool:
        """Registra evidências no Neo4j.
        
        Este método é chamado automaticamente após análise bem-sucedida.
        
        Args:
            evidence: Evidências a registrar
            context_id: ID do contexto (alerta, incidente, etc)
        
        Returns:
            True se registrado com sucesso
        """
        try:
            # TODO: Implementar integração com Neo4j
            self.logger.info(f"Registering {len(evidence)} evidence items for context {context_id}")
            
            for ev in evidence:
                self.logger.debug(f"Evidence: {ev.type.value} from {ev.source} (confidence: {ev.confidence})")
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to register evidence: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas de execução do agente.
        
        Returns:
            Dicionário com métricas
        """
        avg_execution_time = (
            self._total_execution_time / self._execution_count
            if self._execution_count > 0
            else 0.0
        )
        
        error_rate = (
            self._error_count / self._execution_count
            if self._execution_count > 0
            else 0.0
        )
        
        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "error_rate": error_rate,
            "avg_execution_time_ms": avg_execution_time,
            "total_execution_time_ms": self._total_execution_time,
        }
    
    def __repr__(self) -> str:
        """Representação em string do agente."""
        return f"<{self.__class__.__name__} name={self.name} id={self.agent_id}>"


class AgentRegistry:
    """Registro centralizado de agentes.
    
    Garante que todos os agentes estão registrados e podem ser descobertos.
    Padrão: Registry Pattern (similar a Spring's ApplicationContext em Java).
    """
    
    _agents: Dict[str, BaseAgent] = {}
    
    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        """Registra um agente.
        
        Args:
            agent: Agente a registrar
        
        Raises:
            ValueError: Se agente com mesmo nome já existe
        """
        if agent.name in cls._agents:
            raise ValueError(f"Agent '{agent.name}' already registered")
        
        cls._agents[agent.name] = agent
        logger.info(f"Agent registered: {agent.name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[BaseAgent]:
        """Obtém um agente pelo nome.
        
        Args:
            name: Nome do agente
        
        Returns:
            Agente ou None se não encontrado
        """
        return cls._agents.get(name)
    
    @classmethod
    def get_all(cls) -> Dict[str, BaseAgent]:
        """Retorna todos os agentes registrados.
        
        Returns:
            Dicionário de agentes
        """
        return cls._agents.copy()
    
    @classmethod
    def unregister(cls, name: str) -> bool:
        """Remove um agente do registro.
        
        Args:
            name: Nome do agente
        
        Returns:
            True se removido, False se não encontrado
        """
        if name in cls._agents:
            del cls._agents[name]
            logger.info(f"Agent unregistered: {name}")
            return True
        return False
    
    @classmethod
    def clear(cls) -> None:
        """Remove todos os agentes do registro."""
        cls._agents.clear()
        logger.info("All agents unregistered")


# Exemplo de implementação (será expandido em arquivo separado)
class ExampleAgent(BaseAgent):
    """Agente de exemplo para demonstrar a implementação."""
    
    async def execute(self, input_data: Dict[str, Any]) -> AgentOutput:
        """Implementação de exemplo."""
        try:
            data = await self.collect_data(input_data)
            result = self.analyze(data)
            self.validate_output(result)
            evidence = await self.generate_evidence(data, result)
            
            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                result=result,
                confidence=0.95,
                evidence=evidence,
            )
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                result=None,
                confidence=0.0,
                error_message=str(e),
            )
    
    async def collect_data(self, input_data: Dict[str, Any]) -> Any:
        """Coleta dados de exemplo."""
        return input_data.get("data", {})
    
    def analyze(self, data: Any) -> Any:
        """Analisa dados de exemplo."""
        return {"status": "analyzed", "data": data}
    
    def validate_output(self, result: Any) -> bool:
        """Valida saída de exemplo."""
        if not isinstance(result, dict):
            raise ValueError("Result must be a dictionary")
        return True
    
    async def generate_evidence(self, data: Any, result: Any) -> List[Evidence]:
        """Gera evidências de exemplo."""
        return [
            Evidence(
                type=EvidenceType.INFERENCE,
                source="example_agent",
                value=result,
                confidence=0.95,
            )
        ]
