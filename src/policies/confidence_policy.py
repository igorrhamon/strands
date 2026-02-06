"""
Política de Confiança - Cálculo Bayesiano de Confiança

Implementa cálculo de confiança baseado em densidade de evidências
com detecção de possível alucinação (divergência > 20%).

Fórmula:
    final_confidence = (agent_confidence * weight) + (evidence_count * 0.1)

Se |agent_confidence - calculated_confidence| > 0.2:
    Flag como "Potential Hallucination"
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Níveis de confiança."""
    VERY_LOW = "very_low"      # 0.0 - 0.2
    LOW = "low"                # 0.2 - 0.4
    MEDIUM = "medium"          # 0.4 - 0.6
    HIGH = "high"              # 0.6 - 0.8
    VERY_HIGH = "very_high"    # 0.8 - 1.0


class HallucinationFlag(str, Enum):
    """Tipos de flag de alucinação."""
    NO_HALLUCINATION = "no_hallucination"
    POTENTIAL_HALLUCINATION = "potential_hallucination"
    LIKELY_HALLUCINATION = "likely_hallucination"
    CONFIRMED_HALLUCINATION = "confirmed_hallucination"


@dataclass
class EvidenceItem:
    """Representa uma evidência individual."""
    
    source: str                 # Origem da evidência (log, métrica, etc)
    confidence: float          # Confiança desta evidência (0.0-1.0)
    weight: float = 1.0        # Peso da evidência
    description: str = ""      # Descrição
    timestamp: datetime = None
    
    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confiança deve estar entre 0.0 e 1.0, recebido {self.confidence}")
        if self.weight < 0:
            raise ValueError(f"Peso não pode ser negativo, recebido {self.weight}")
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class ConfidenceCalculation(BaseModel):
    """Resultado do cálculo de confiança."""
    
    final_confidence: float = Field(..., ge=0.0, le=1.0, description="Confiança final calculada")
    agent_reported_confidence: float = Field(..., ge=0.0, le=1.0, description="Confiança reportada pelo agente")
    evidence_count: int = Field(..., ge=0, description="Número de evidências")
    evidence_weight_sum: float = Field(..., ge=0.0, description="Soma dos pesos das evidências")
    confidence_level: ConfidenceLevel = Field(..., description="Nível de confiança")
    hallucination_flag: HallucinationFlag = Field(..., description="Flag de possível alucinação")
    divergence: float = Field(..., ge=0.0, le=1.0, description="Divergência entre reportado e calculado")
    divergence_percentage: float = Field(..., ge=0.0, le=100.0, description="Divergência em percentual")
    calculation_details: Dict = Field(default_factory=dict, description="Detalhes do cálculo")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        frozen = True


class ConfidencePolicy:
    """Política de cálculo de confiança com lógica Bayesiana.
    
    Responsabilidades:
    1. Calcular confiança baseada em evidências
    2. Detectar possível alucinação
    3. Validar divergência entre reportado e calculado
    4. Gerar recomendações
    """
    
    # Constantes de cálculo
    EVIDENCE_WEIGHT_FACTOR = 0.1  # Fator para peso de evidência
    HALLUCINATION_THRESHOLD = 0.2  # Threshold para divergência (20%)
    LIKELY_HALLUCINATION_THRESHOLD = 0.3  # Threshold para alucinação provável (30%)
    
    def __init__(self, base_weight: float = 1.0):
        """Inicializa política.
        
        Args:
            base_weight: Peso base para cálculos
        """
        self.base_weight = base_weight
        self.logger = logging.getLogger("confidence_policy")
    
    def calculate_confidence(self, 
                            agent_confidence: float,
                            evidence_items: List[EvidenceItem],
                            context: Optional[Dict] = None) -> ConfidenceCalculation:
        """Calcula confiança usando fórmula Bayesiana.
        
        Fórmula:
            final_confidence = (agent_confidence * base_weight) + 
                              (sum(evidence_confidence * evidence_weight) / evidence_count * EVIDENCE_WEIGHT_FACTOR)
        
        Args:
            agent_confidence: Confiança reportada pelo agente (0.0-1.0)
            evidence_items: Lista de evidências
            context: Contexto adicional
        
        Returns:
            ConfidenceCalculation com resultado detalhado
        """
        if not (0.0 <= agent_confidence <= 1.0):
            raise ValueError(f"agent_confidence deve estar entre 0.0 e 1.0, recebido {agent_confidence}")
        
        # Calcular contribuição das evidências
        evidence_count = len(evidence_items)
        
        if evidence_count == 0:
            # Sem evidências, usar confiança do agente
            final_confidence = agent_confidence
            evidence_contribution = 0.0
            evidence_weight_sum = 0.0
        else:
            # Calcular média ponderada das evidências
            weighted_sum = sum(
                item.confidence * item.weight 
                for item in evidence_items
            )
            weight_sum = sum(item.weight for item in evidence_items)
            
            evidence_average = weighted_sum / weight_sum if weight_sum > 0 else 0.0
            evidence_contribution = evidence_average * self.EVIDENCE_WEIGHT_FACTOR
            evidence_weight_sum = weight_sum
            
            # Aplicar fórmula Bayesiana
            final_confidence = min(
                1.0,  # Capped at 1.0
                (agent_confidence * self.base_weight) + evidence_contribution
            )
        
        # Calcular divergência
        divergence = abs(agent_confidence - final_confidence)
        divergence_percentage = divergence * 100.0
        
        # Determinar flag de alucinação
        hallucination_flag = self._determine_hallucination_flag(divergence_percentage)
        
        # Determinar nível de confiança
        confidence_level = self._determine_confidence_level(final_confidence)
        
        # Preparar detalhes do cálculo
        calculation_details = {
            "agent_confidence": agent_confidence,
            "evidence_count": evidence_count,
            "evidence_average": evidence_average if evidence_count > 0 else 0.0,
            "evidence_contribution": evidence_contribution,
            "base_weight": self.base_weight,
            "formula": "final_confidence = (agent_confidence * base_weight) + (evidence_average * EVIDENCE_WEIGHT_FACTOR)",
            "evidence_sources": [item.source for item in evidence_items],
        }
        
        # Log
        self.logger.info(
            f"Confiança calculada: final={final_confidence:.3f}, "
            f"reportada={agent_confidence:.3f}, "
            f"divergência={divergence_percentage:.1f}%, "
            f"flag={hallucination_flag.value}, "
            f"evidências={evidence_count}"
        )
        
        return ConfidenceCalculation(
            final_confidence=final_confidence,
            agent_reported_confidence=agent_confidence,
            evidence_count=evidence_count,
            evidence_weight_sum=evidence_weight_sum,
            confidence_level=confidence_level,
            hallucination_flag=hallucination_flag,
            divergence=divergence,
            divergence_percentage=divergence_percentage,
            calculation_details=calculation_details,
        )
    
    def _determine_hallucination_flag(self, divergence_percentage: float) -> HallucinationFlag:
        """Determina flag de alucinação baseado em divergência.
        
        Args:
            divergence_percentage: Divergência em percentual (0-100)
        
        Returns:
            Flag de alucinação
        """
        if divergence_percentage < self.HALLUCINATION_THRESHOLD * 100:
            return HallucinationFlag.NO_HALLUCINATION
        elif divergence_percentage < self.LIKELY_HALLUCINATION_THRESHOLD * 100:
            return HallucinationFlag.POTENTIAL_HALLUCINATION
        else:
            return HallucinationFlag.LIKELY_HALLUCINATION
    
    def _determine_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Determina nível de confiança.
        
        Args:
            confidence: Score de confiança (0.0-1.0)
        
        Returns:
            Nível de confiança
        """
        if confidence < 0.2:
            return ConfidenceLevel.VERY_LOW
        elif confidence < 0.4:
            return ConfidenceLevel.LOW
        elif confidence < 0.6:
            return ConfidenceLevel.MEDIUM
        elif confidence < 0.8:
            return ConfidenceLevel.HIGH
        else:
            return ConfidenceLevel.VERY_HIGH
    
    def validate_confidence(self, 
                           agent_confidence: float,
                           evidence_items: List[EvidenceItem],
                           context: Optional[Dict] = None) -> Tuple[bool, str]:
        """Valida se confiança é confiável.
        
        Args:
            agent_confidence: Confiança reportada
            evidence_items: Evidências
            context: Contexto
        
        Returns:
            Tupla (é_válida, razão)
        """
        calculation = self.calculate_confidence(agent_confidence, evidence_items, context)
        
        # Verificar alucinação
        if calculation.hallucination_flag == HallucinationFlag.LIKELY_HALLUCINATION:
            return False, (
                f"Possível alucinação detectada: divergência de {calculation.divergence_percentage:.1f}% "
                f"entre reportado ({agent_confidence:.3f}) e calculado ({calculation.final_confidence:.3f})"
            )
        
        # Verificar se há evidências suficientes
        if calculation.evidence_count == 0 and agent_confidence < 0.5:
            return False, "Confiança baixa sem evidências de suporte"
        
        return True, "Confiança validada"
    
    def get_recommendation(self, 
                          calculation: ConfidenceCalculation,
                          context: Optional[Dict] = None) -> str:
        """Gera recomendação baseada no cálculo.
        
        Args:
            calculation: Resultado do cálculo
            context: Contexto adicional
        
        Returns:
            Recomendação em texto
        """
        recommendations = []
        
        # Baseado no nível de confiança
        if calculation.confidence_level == ConfidenceLevel.VERY_LOW:
            recommendations.append("⚠️ CONFIANÇA MUITO BAIXA: Requer revisão humana urgente")
        elif calculation.confidence_level == ConfidenceLevel.LOW:
            recommendations.append("⚠️ CONFIANÇA BAIXA: Recomenda-se revisão humana")
        elif calculation.confidence_level == ConfidenceLevel.VERY_HIGH:
            recommendations.append("✅ CONFIANÇA MUITO ALTA: Pode proceder automaticamente")
        
        # Baseado em alucinação
        if calculation.hallucination_flag == HallucinationFlag.LIKELY_HALLUCINATION:
            recommendations.append(
                f"🚨 POSSÍVEL ALUCINAÇÃO: Divergência de {calculation.divergence_percentage:.1f}% "
                f"entre reportado e calculado"
            )
        elif calculation.hallucination_flag == HallucinationFlag.POTENTIAL_HALLUCINATION:
            recommendations.append(
                f"⚠️ POSSÍVEL ALUCINAÇÃO: Divergência de {calculation.divergence_percentage:.1f}% "
                f"(próxima ao threshold)"
            )
        
        # Baseado em evidências
        if calculation.evidence_count == 0:
            recommendations.append("ℹ️ Sem evidências de suporte: Confiança baseada apenas no agente")
        elif calculation.evidence_count < 3:
            recommendations.append(f"ℹ️ Poucas evidências ({calculation.evidence_count}): Considere coletar mais dados")
        
        return " | ".join(recommendations) if recommendations else "✅ Sem recomendações especiais"
    
    def batch_calculate(self, 
                       calculations_data: List[Dict]) -> List[ConfidenceCalculation]:
        """Calcula confiança para múltiplos casos em lote.
        
        Args:
            calculations_data: Lista de dicts com agent_confidence e evidence_items
        
        Returns:
            Lista de ConfidenceCalculation
        """
        results = []
        
        for data in calculations_data:
            agent_confidence = data.get("agent_confidence", 0.0)
            evidence_items = data.get("evidence_items", [])
            context = data.get("context")
            
            try:
                result = self.calculate_confidence(agent_confidence, evidence_items, context)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Erro ao calcular confiança em lote: {e}")
                # Retornar cálculo com erro
                results.append(
                    ConfidenceCalculation(
                        final_confidence=0.0,
                        agent_reported_confidence=agent_confidence,
                        evidence_count=0,
                        evidence_weight_sum=0.0,
                        confidence_level=ConfidenceLevel.VERY_LOW,
                        hallucination_flag=HallucinationFlag.CONFIRMED_HALLUCINATION,
                        divergence=1.0,
                        divergence_percentage=100.0,
                        calculation_details={"error": str(e)},
                    )
                )
        
        return results
