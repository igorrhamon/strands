"""
ConfidenceService - Serviço responsável por calcular scores de confiança.

Este serviço implementa múltiplas estratégias de cálculo de confiança:
1. Evidence-based: Baseado na qualidade e quantidade de evidências
2. Consensus-based: Baseado em consenso entre múltiplos agentes
3. Historical: Baseado em histórico de acurácia do agente
4. Cross-validation: Baseado em validação cruzada com outros agentes

Padrão: Strategy Pattern (similar a Java's Strategy interface)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from enum import Enum
import numpy as np

from src.agents.base_agent import AgentOutput, Evidence, EvidenceType

logger = logging.getLogger(__name__)


class ConfidenceStrategy(str, Enum):
    """Estratégias de cálculo de confiança."""
    EVIDENCE_BASED = "evidence_based"
    CONSENSUS_BASED = "consensus_based"
    HISTORICAL = "historical"
    CROSS_VALIDATION = "cross_validation"
    ENSEMBLE = "ensemble"  # Combina todas as estratégias


@dataclass
class ConfidenceScore:
    """Representa um score de confiança calculado.
    
    Atributos:
        base_score: Score base (0.0 a 1.0)
        strategy: Estratégia usada para calcular
        factors: Fatores que influenciaram o score
        evidence_quality: Qualidade das evidências (0.0 a 1.0)
        consensus_level: Nível de consenso entre agentes (0.0 a 1.0)
        historical_accuracy: Acurácia histórica do agente (0.0 a 1.0)
        final_score: Score final após ajustes (0.0 a 1.0)
        explanation: Explicação legível do score
    """
    base_score: float
    strategy: ConfidenceStrategy
    factors: Dict[str, float]
    evidence_quality: float
    consensus_level: float
    historical_accuracy: float
    final_score: float
    explanation: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        
        # Validar que todos os scores estão entre 0.0 e 1.0
        for score_name in ["base_score", "evidence_quality", "consensus_level", 
                          "historical_accuracy", "final_score"]:
            score = getattr(self, score_name)
            if not 0.0 <= score <= 1.0:
                raise ValueError(f"{score_name} deve estar entre 0.0 e 1.0, recebido: {score}")
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "base_score": round(self.base_score, 3),
            "strategy": self.strategy.value,
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
            "evidence_quality": round(self.evidence_quality, 3),
            "consensus_level": round(self.consensus_level, 3),
            "historical_accuracy": round(self.historical_accuracy, 3),
            "final_score": round(self.final_score, 3),
            "explanation": self.explanation,
            "timestamp": self.timestamp.isoformat(),
        }


class ConfidenceService:
    """Serviço centralizado para cálculo de confiança.
    
    Implementa múltiplas estratégias de cálculo e permite composição.
    """
    
    def __init__(self):
        """Inicializa o serviço."""
        self.logger = logging.getLogger("confidence_service")
        self._agent_history: Dict[str, List[float]] = {}  # Histórico de scores por agente
        self._max_history_size = 100  # Manter últimos 100 scores
    
    def calculate_evidence_quality(self, evidence: List[Evidence]) -> float:
        """Calcula qualidade das evidências.
        
        Fatores considerados:
        - Número de evidências
        - Confiança média das evidências
        - Diversidade de fontes
        - Recência das evidências
        
        Args:
            evidence: Lista de evidências
        
        Returns:
            Score de qualidade (0.0 a 1.0)
        """
        if not evidence:
            return 0.0
        
        # 1. Confiança média das evidências
        avg_confidence = np.mean([e.confidence for e in evidence])
        
        # 2. Diversidade de fontes (quanto mais fontes diferentes, melhor)
        unique_sources = len(set(e.source for e in evidence))
        source_diversity = min(unique_sources / 5.0, 1.0)  # Máximo 5 fontes
        
        # 3. Diversidade de tipos de evidência
        unique_types = len(set(e.type for e in evidence))
        type_diversity = min(unique_types / len(EvidenceType), 1.0)
        
        # 4. Recência (evidências recentes são melhores)
        now = datetime.utcnow()
        ages = [(now - e.timestamp).total_seconds() / 3600 for e in evidence]  # em horas
        recency = np.mean([max(0, 1 - age / 24) for age in ages])  # Decai após 24h
        
        # Combinar fatores com pesos
        quality = (
            avg_confidence * 0.4 +
            source_diversity * 0.3 +
            type_diversity * 0.2 +
            recency * 0.1
        )
        
        self.logger.debug(
            f"Evidence quality calculated: {quality:.3f} "
            f"(confidence={avg_confidence:.3f}, diversity={source_diversity:.3f}, "
            f"types={type_diversity:.3f}, recency={recency:.3f})"
        )
        
        return min(quality, 1.0)
    
    def calculate_consensus_score(self, agent_outputs: List[AgentOutput]) -> Tuple[float, str]:
        """Calcula nível de consenso entre múltiplos agentes.
        
        Estratégia:
        - Se todos os agentes concordam: score alto
        - Se maioria concorda: score médio
        - Se há discordância: score baixo
        
        Args:
            agent_outputs: Outputs de múltiplos agentes
        
        Returns:
            Tupla (consensus_score, explanation)
        """
        if not agent_outputs:
            return 0.0, "Nenhum agente forneceu output"
        
        if len(agent_outputs) == 1:
            return 0.8, "Apenas um agente disponível"
        
        # Extrair resultados (assumindo que são booleanos ou strings)
        results = [str(output.result).lower() for output in agent_outputs]
        
        # Contar concordância
        most_common = max(set(results), key=results.count)
        agreement_count = results.count(most_common)
        agreement_ratio = agreement_count / len(results)
        
        # Calcular score baseado em concordância
        if agreement_ratio >= 0.9:
            consensus = 0.95
            explanation = f"Consenso forte: {agreement_count}/{len(results)} agentes concordam"
        elif agreement_ratio >= 0.7:
            consensus = 0.75
            explanation = f"Consenso moderado: {agreement_count}/{len(results)} agentes concordam"
        elif agreement_ratio >= 0.5:
            consensus = 0.5
            explanation = f"Consenso fraco: {agreement_count}/{len(results)} agentes concordam"
        else:
            consensus = 0.3
            explanation = f"Discordância: agentes têm opiniões diferentes"
        
        # Ajustar por confiança média dos agentes
        avg_agent_confidence = np.mean([o.confidence for o in agent_outputs])
        consensus = consensus * avg_agent_confidence
        
        self.logger.debug(f"Consensus score: {consensus:.3f} - {explanation}")
        
        return consensus, explanation
    
    def calculate_historical_accuracy(self, agent_name: str) -> float:
        """Calcula acurácia histórica de um agente.
        
        Baseado no histórico de scores anteriores.
        
        Args:
            agent_name: Nome do agente
        
        Returns:
            Score de acurácia (0.0 a 1.0)
        """
        if agent_name not in self._agent_history:
            # Novo agente: assumir acurácia média
            return 0.7
        
        history = self._agent_history[agent_name]
        if not history:
            return 0.7
        
        # Calcular média com peso maior para scores recentes
        weights = np.linspace(0.5, 1.0, len(history))
        weighted_avg = np.average(history, weights=weights)
        
        self.logger.debug(f"Historical accuracy for {agent_name}: {weighted_avg:.3f}")
        
        return weighted_avg
    
    def record_agent_score(self, agent_name: str, score: float) -> None:
        """Registra um score no histórico do agente.
        
        Args:
            agent_name: Nome do agente
            score: Score a registrar
        """
        if agent_name not in self._agent_history:
            self._agent_history[agent_name] = []
        
        self._agent_history[agent_name].append(score)
        
        # Manter apenas últimos N scores
        if len(self._agent_history[agent_name]) > self._max_history_size:
            self._agent_history[agent_name] = self._agent_history[agent_name][-self._max_history_size:]
    
    def calculate_evidence_based(self, output: AgentOutput) -> ConfidenceScore:
        """Calcula confiança baseada em evidências.
        
        Args:
            output: Output do agente
        
        Returns:
            ConfidenceScore
        """
        evidence_quality = self.calculate_evidence_quality(output.evidence)
        
        # Score base é a confiança reportada pelo agente
        base_score = output.confidence
        
        # Ajustar por qualidade de evidências
        final_score = (base_score * 0.6) + (evidence_quality * 0.4)
        
        factors = {
            "agent_confidence": output.confidence,
            "evidence_quality": evidence_quality,
            "evidence_count": len(output.evidence),
        }
        
        explanation = (
            f"Baseado em {len(output.evidence)} evidências com qualidade {evidence_quality:.1%}. "
            f"Agente reportou {output.confidence:.1%} de confiança."
        )
        
        return ConfidenceScore(
            base_score=base_score,
            strategy=ConfidenceStrategy.EVIDENCE_BASED,
            factors=factors,
            evidence_quality=evidence_quality,
            consensus_level=0.0,
            historical_accuracy=0.0,
            final_score=final_score,
            explanation=explanation,
        )
    
    def calculate_consensus_based(self, outputs: List[AgentOutput]) -> ConfidenceScore:
        """Calcula confiança baseada em consenso.
        
        Args:
            outputs: Outputs de múltiplos agentes
        
        Returns:
            ConfidenceScore
        """
        consensus_score, explanation = self.calculate_consensus_score(outputs)
        
        # Score base é a confiança média
        base_score = np.mean([o.confidence for o in outputs])
        
        # Score final é influenciado pelo consenso
        final_score = (base_score * 0.5) + (consensus_score * 0.5)
        
        factors = {
            "agent_count": len(outputs),
            "avg_agent_confidence": base_score,
            "consensus_score": consensus_score,
        }
        
        return ConfidenceScore(
            base_score=base_score,
            strategy=ConfidenceStrategy.CONSENSUS_BASED,
            factors=factors,
            evidence_quality=0.0,
            consensus_level=consensus_score,
            historical_accuracy=0.0,
            final_score=final_score,
            explanation=explanation,
        )
    
    def calculate_historical(self, output: AgentOutput) -> ConfidenceScore:
        """Calcula confiança baseada em histórico.
        
        Args:
            output: Output do agente
        
        Returns:
            ConfidenceScore
        """
        historical_accuracy = self.calculate_historical_accuracy(output.agent_name)
        
        # Score base é a confiança reportada
        base_score = output.confidence
        
        # Ajustar por acurácia histórica
        final_score = (base_score * 0.6) + (historical_accuracy * 0.4)
        
        factors = {
            "agent_confidence": output.confidence,
            "historical_accuracy": historical_accuracy,
        }
        
        explanation = (
            f"Agente {output.agent_name} tem acurácia histórica de {historical_accuracy:.1%}. "
            f"Score ajustado para {final_score:.1%}."
        )
        
        return ConfidenceScore(
            base_score=base_score,
            strategy=ConfidenceStrategy.HISTORICAL,
            factors=factors,
            evidence_quality=0.0,
            consensus_level=0.0,
            historical_accuracy=historical_accuracy,
            final_score=final_score,
            explanation=explanation,
        )
    
    def calculate_ensemble(self, output: AgentOutput, 
                          other_outputs: Optional[List[AgentOutput]] = None) -> ConfidenceScore:
        """Calcula confiança usando ensemble de estratégias.
        
        Combina múltiplas estratégias para resultado mais robusto.
        
        Args:
            output: Output principal do agente
            other_outputs: Outputs de outros agentes para consenso
        
        Returns:
            ConfidenceScore
        """
        # Calcular cada estratégia
        evidence_score = self.calculate_evidence_based(output)
        historical_score = self.calculate_historical(output)
        
        scores = [
            evidence_score.final_score * 0.4,
            historical_score.final_score * 0.3,
        ]
        
        # Se houver múltiplos outputs, incluir consenso
        if other_outputs:
            consensus_score = self.calculate_consensus_based([output] + other_outputs)
            scores.append(consensus_score.final_score * 0.3)
        else:
            consensus_score = None
        
        # Média ponderada
        final_score = np.mean(scores)
        
        factors = {
            "evidence_weight": 0.4,
            "historical_weight": 0.3,
            "consensus_weight": 0.3 if other_outputs else 0.0,
            "evidence_score": evidence_score.final_score,
            "historical_score": historical_score.final_score,
        }
        
        if consensus_score:
            factors["consensus_score"] = consensus_score.final_score
        
        explanation = (
            f"Ensemble score combinando evidências ({evidence_score.final_score:.1%}), "
            f"histórico ({historical_score.final_score:.1%})"
        )
        
        if consensus_score:
            explanation += f", e consenso ({consensus_score.final_score:.1%})"
        
        explanation += f". Score final: {final_score:.1%}"
        
        return ConfidenceScore(
            base_score=output.confidence,
            strategy=ConfidenceStrategy.ENSEMBLE,
            factors=factors,
            evidence_quality=evidence_score.evidence_quality,
            consensus_level=consensus_score.consensus_level if consensus_score else 0.0,
            historical_accuracy=historical_score.historical_accuracy,
            final_score=final_score,
            explanation=explanation,
        )
    
    def calculate(self, output: AgentOutput, 
                 strategy: ConfidenceStrategy = ConfidenceStrategy.ENSEMBLE,
                 other_outputs: Optional[List[AgentOutput]] = None) -> ConfidenceScore:
        """Calcula confiança usando estratégia especificada.
        
        Args:
            output: Output do agente
            strategy: Estratégia a usar
            other_outputs: Outputs de outros agentes (para consenso)
        
        Returns:
            ConfidenceScore
        """
        if strategy == ConfidenceStrategy.EVIDENCE_BASED:
            return self.calculate_evidence_based(output)
        elif strategy == ConfidenceStrategy.HISTORICAL:
            return self.calculate_historical(output)
        elif strategy == ConfidenceStrategy.CONSENSUS_BASED:
            if not other_outputs:
                raise ValueError("other_outputs é obrigatório para CONSENSUS_BASED")
            return self.calculate_consensus_based([output] + other_outputs)
        elif strategy == ConfidenceStrategy.ENSEMBLE:
            return self.calculate_ensemble(output, other_outputs)
        else:
            raise ValueError(f"Estratégia desconhecida: {strategy}")
