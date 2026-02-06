"""
Estratégias de Consenso - Padrão Strategy para Votação Ponderada

Implementa o padrão Strategy (similar a Spring's Strategy Pattern em Java)
para calcular consenso entre múltiplos agentes com pesos configuráveis.

Inspiração: LangGraph's state management e Temporal.io's workflow orchestration
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Papéis de agentes com pesos padrão."""
    THREAT_INTEL = "threat_intel"           # Peso: 2.0 (crítico)
    LOG_ANALYZER = "log_analyzer"           # Peso: 1.5
    METRICS_ANALYZER = "metrics_analyzer"   # Peso: 1.0
    POLICY_ENGINE = "policy_engine"         # Peso: 1.5
    HUMAN_ANALYST = "human_analyst"         # Peso: 3.0 (máximo)


class ConsensusResult(BaseModel):
    """Resultado do cálculo de consenso."""
    
    final_score: float = Field(..., ge=0.0, le=1.0, description="Score final agregado")
    consensus_type: str = Field(..., description="Tipo de consenso (unanimous, majority, etc)")
    agent_votes: Dict[str, float] = Field(default_factory=dict, description="Votos individuais dos agentes")
    weighted_scores: Dict[str, float] = Field(default_factory=dict, description="Scores ponderados")
    requires_human_review: bool = Field(False, description="Se requer revisão humana")
    hallucination_flag: Optional[str] = Field(None, description="Flag se possível alucinação detectada")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Quando foi calculado")
    
    class Config:
        frozen = True


@dataclass
class AgentExecution:
    """Representa a execução de um agente."""
    
    agent_id: str
    agent_name: str
    agent_role: AgentRole
    confidence_score: float  # 0.0 a 1.0
    evidence_count: int      # Número de evidências
    result: str              # Resultado (approve, reject, escalate, etc)
    reasoning: str           # Explicação
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        """Valida valores após inicialização."""
        if not (0.0 <= self.confidence_score <= 1.0):
            raise ValueError(f"confidence_score deve estar entre 0.0 e 1.0, recebido {self.confidence_score}")
        if self.evidence_count < 0:
            raise ValueError(f"evidence_count não pode ser negativo, recebido {self.evidence_count}")


class ConsensusStrategy(ABC):
    """Classe abstrata para estratégias de consenso.
    
    Define a interface que todas as estratégias devem implementar.
    """
    
    def __init__(self, name: str):
        """Inicializa estratégia.
        
        Args:
            name: Nome descritivo da estratégia
        """
        self.name = name
        self.logger = logging.getLogger(f"consensus.{name}")
    
    @abstractmethod
    def calculate(self, executions: List[AgentExecution]) -> ConsensusResult:
        """Calcula consenso baseado nas execuções dos agentes.
        
        Args:
            executions: Lista de execuções de agentes
        
        Returns:
            ConsensusResult com score agregado e metadados
        """
        pass
    
    def _get_agent_weight(self, role: AgentRole, context: Optional[Dict] = None) -> float:
        """Obtém peso do agente baseado em seu papel.
        
        Args:
            role: Papel do agente
            context: Contexto adicional (ex: tipo de decisão)
        
        Returns:
            Peso do agente (1.0 a 3.0)
        """
        # Pesos padrão
        weights = {
            AgentRole.THREAT_INTEL: 2.0,
            AgentRole.LOG_ANALYZER: 1.5,
            AgentRole.METRICS_ANALYZER: 1.0,
            AgentRole.POLICY_ENGINE: 1.5,
            AgentRole.HUMAN_ANALYST: 3.0,
        }
        
        # Ajustar peso baseado em contexto
        weight = weights.get(role, 1.0)
        
        if context and context.get("is_security_decision"):
            if role == AgentRole.THREAT_INTEL:
                weight *= 1.5  # Aumentar peso para decisões de segurança
        
        return weight


class WeightedScoreStrategy(ConsensusStrategy):
    """Estratégia de votação ponderada com pesos por agente.
    
    Implementa:
    - Cálculo de score ponderado
    - Detecção de empate
    - Validação de confiança
    - Flag de possível alucinação
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        """Inicializa estratégia ponderada.
        
        Args:
            confidence_threshold: Threshold mínimo de confiança para decisão automática
        """
        super().__init__("weighted_score")
        self.confidence_threshold = confidence_threshold
    
    def calculate(self, executions: List[AgentExecution], 
                 context: Optional[Dict] = None) -> ConsensusResult:
        """Calcula consenso usando votação ponderada.
        
        Fórmula:
            weighted_score = sum(agent_confidence * weight) / sum(weights)
        
        Args:
            executions: Lista de execuções de agentes
            context: Contexto adicional
        
        Returns:
            ConsensusResult com score ponderado
        """
        if not executions:
            return ConsensusResult(
                final_score=0.0,
                consensus_type="empty",
                requires_human_review=True,
            )
        
        # Calcular scores ponderados
        weighted_scores: Dict[str, float] = {}
        total_weight = 0.0
        weighted_sum = 0.0
        
        for execution in executions:
            weight = self._get_agent_weight(execution.agent_role, context)
            weighted_score = execution.confidence_score * weight
            
            weighted_scores[execution.agent_id] = weighted_score
            weighted_sum += weighted_score
            total_weight += weight
        
        # Calcular score final
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Determinar tipo de consenso
        consensus_type = self._determine_consensus_type(executions, final_score)
        
        # Verificar possível alucinação
        hallucination_flag = self._check_hallucination(executions, final_score)
        
        # Determinar se requer revisão humana
        requires_review = final_score < self.confidence_threshold
        
        # Mapear votos individuais
        agent_votes = {
            execution.agent_id: execution.confidence_score 
            for execution in executions
        }
        
        self.logger.info(
            f"Consenso calculado: score={final_score:.3f}, "
            f"tipo={consensus_type}, requer_revisão={requires_review}"
        )
        
        return ConsensusResult(
            final_score=final_score,
            consensus_type=consensus_type,
            agent_votes=agent_votes,
            weighted_scores=weighted_scores,
            requires_human_review=requires_review,
            hallucination_flag=hallucination_flag,
        )
    
    def _determine_consensus_type(self, executions: List[AgentExecution], 
                                 final_score: float) -> str:
        """Determina o tipo de consenso.
        
        Args:
            executions: Execuções dos agentes
            final_score: Score final calculado
        
        Returns:
            Tipo de consenso (unanimous, majority, split, etc)
        """
        if len(executions) == 1:
            return "single_agent"
        
        # Contar resultados únicos
        results = [e.result.lower() for e in executions]
        unique_results = set(results)
        
        if len(unique_results) == 1:
            return "unanimous"
        
        # Verificar maioria
        most_common = max(set(results), key=results.count)
        agreement_ratio = results.count(most_common) / len(results)
        
        if agreement_ratio >= 0.75:
            return "strong_majority"
        elif agreement_ratio >= 0.5:
            return "majority"
        else:
            return "split"
    
    def _check_hallucination(self, executions: List[AgentExecution], 
                            final_score: float) -> Optional[str]:
        """Verifica possível alucinação (divergência > 20%).
        
        Fórmula:
            divergence = |agent_confidence - final_score|
            if divergence > 0.2: flag como possível alucinação
        
        Args:
            executions: Execuções dos agentes
            final_score: Score final
        
        Returns:
            Flag se possível alucinação detectada
        """
        hallucinations = []
        
        for execution in executions:
            divergence = abs(execution.confidence_score - final_score)
            
            if divergence > 0.2:
                hallucinations.append({
                    "agent_id": execution.agent_id,
                    "agent_confidence": execution.confidence_score,
                    "final_score": final_score,
                    "divergence": divergence,
                })
        
        if hallucinations:
            self.logger.warning(
                f"Possível alucinação detectada em {len(hallucinations)} agente(s): {hallucinations}"
            )
            return f"Divergência detectada em {len(hallucinations)} agente(s)"
        
        return None
    
    def resolve_tie(self, executions: List[AgentExecution]) -> str:
        """Resolve empate usando peso de agentes.
        
        Quando há empate (ex: 2 agentes com scores iguais),
        usa o peso do agente para desempatar.
        
        Args:
            executions: Execuções dos agentes
        
        Returns:
            Resultado do desempate
        """
        if len(executions) < 2:
            return executions[0].result if executions else "unknown"
        
        # Agrupar por resultado
        results_by_outcome = {}
        for execution in executions:
            outcome = execution.result.lower()
            if outcome not in results_by_outcome:
                results_by_outcome[outcome] = []
            results_by_outcome[outcome].append(execution)
        
        # Se não há empate, retornar resultado mais comum
        if len(results_by_outcome) == 1:
            return list(results_by_outcome.keys())[0]
        
        # Calcular peso total por resultado
        outcome_weights = {}
        for outcome, execs in results_by_outcome.items():
            total_weight = sum(self._get_agent_weight(e.agent_role) for e in execs)
            outcome_weights[outcome] = total_weight
        
        # Retornar resultado com maior peso
        winning_outcome = max(outcome_weights.items(), key=lambda x: x[1])[0]
        
        self.logger.info(f"Empate resolvido: {winning_outcome} (pesos: {outcome_weights})")
        
        return winning_outcome


class UnanimousStrategy(ConsensusStrategy):
    """Estratégia que requer consenso unânime.
    
    Útil para decisões críticas onde todos os agentes devem concordar.
    """
    
    def __init__(self):
        super().__init__("unanimous")
    
    def calculate(self, executions: List[AgentExecution], 
                 context: Optional[Dict] = None) -> ConsensusResult:
        """Calcula consenso unânime.
        
        Args:
            executions: Lista de execuções
            context: Contexto adicional
        
        Returns:
            ConsensusResult
        """
        if not executions:
            return ConsensusResult(
                final_score=0.0,
                consensus_type="empty",
                requires_human_review=True,
            )
        
        # Verificar se todos têm o mesmo resultado
        results = [e.result.lower() for e in executions]
        
        if len(set(results)) == 1:
            # Consenso unânime
            avg_confidence = sum(e.confidence_score for e in executions) / len(executions)
            
            return ConsensusResult(
                final_score=avg_confidence,
                consensus_type="unanimous",
                agent_votes={e.agent_id: e.confidence_score for e in executions},
                requires_human_review=False,
            )
        else:
            # Sem consenso unânime
            return ConsensusResult(
                final_score=0.0,
                consensus_type="no_unanimous_agreement",
                agent_votes={e.agent_id: e.confidence_score for e in executions},
                requires_human_review=True,
            )


class MajorityStrategy(ConsensusStrategy):
    """Estratégia que requer maioria simples (> 50%).
    
    Útil para decisões menos críticas onde maioria é suficiente.
    """
    
    def __init__(self, majority_threshold: float = 0.5):
        super().__init__("majority")
        self.majority_threshold = majority_threshold
    
    def calculate(self, executions: List[AgentExecution], 
                 context: Optional[Dict] = None) -> ConsensusResult:
        """Calcula consenso por maioria.
        
        Args:
            executions: Lista de execuções
            context: Contexto adicional
        
        Returns:
            ConsensusResult
        """
        if not executions:
            return ConsensusResult(
                final_score=0.0,
                consensus_type="empty",
                requires_human_review=True,
            )
        
        # Contar resultados
        results = [e.result.lower() for e in executions]
        most_common = max(set(results), key=results.count)
        agreement_ratio = results.count(most_common) / len(results)
        
        if agreement_ratio >= self.majority_threshold:
            # Maioria alcançada
            avg_confidence = sum(e.confidence_score for e in executions) / len(executions)
            
            return ConsensusResult(
                final_score=avg_confidence,
                consensus_type="majority",
                agent_votes={e.agent_id: e.confidence_score for e in executions},
                requires_human_review=agreement_ratio < 0.75,  # Revisar se maioria fraca
            )
        else:
            # Sem maioria
            return ConsensusResult(
                final_score=0.0,
                consensus_type="no_majority",
                agent_votes={e.agent_id: e.confidence_score for e in executions},
                requires_human_review=True,
            )
