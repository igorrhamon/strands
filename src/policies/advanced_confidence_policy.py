"""
Advanced Confidence Policy - Política de Confiança com Detecção de Alucinação

Implementa cálculo de confiança baseado em Bayesiano com detecção automática
de alucinações (divergências entre confiança reportada vs calculada).

Padrão: Bayesian Inference + Anomaly Detection
Resiliência: Validação de dados, detecção de outliers
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Níveis de confiança."""
    VERY_LOW = "very_low"          # 0.0 - 0.2
    LOW = "low"                    # 0.2 - 0.4
    MEDIUM = "medium"              # 0.4 - 0.6
    HIGH = "high"                  # 0.6 - 0.8
    VERY_HIGH = "very_high"        # 0.8 - 1.0


class AlucinationSeverity(str, Enum):
    """Severidade de alucinação."""
    NONE = "none"                  # Sem alucinação
    LOW = "low"                    # Divergência < 10%
    MEDIUM = "medium"              # Divergência 10-20%
    HIGH = "high"                  # Divergência 20-50%
    CRITICAL = "critical"          # Divergência > 50%


@dataclass
class BayesianCalculation:
    """Cálculo bayesiano de confiança."""
    
    prior_probability: float        # P(H) - Probabilidade prévia
    likelihood: float               # P(E|H) - Probabilidade da evidência dado H
    evidence_probability: float     # P(E) - Probabilidade da evidência
    posterior_probability: float    # P(H|E) - Probabilidade posterior
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "prior": self.prior_probability,
            "likelihood": self.likelihood,
            "evidence": self.evidence_probability,
            "posterior": self.posterior_probability,
        }


class ConfidenceCalculation(BaseModel):
    """Resultado do cálculo de confiança."""
    
    agent_confidence: float = Field(..., ge=0, le=1, description="Confiança reportada pelo agente")
    evidence_count: int = Field(..., ge=0, description="Número de evidências")
    evidence_weight: float = Field(..., ge=0, le=1, description="Peso das evidências")
    calculated_confidence: float = Field(..., ge=0, le=1, description="Confiança calculada")
    confidence_level: ConfidenceLevel = Field(..., description="Nível de confiança")
    bayesian_calculation: Dict = Field(..., description="Cálculo bayesiano")
    hallucination_detected: bool = Field(..., description="Alucinação detectada?")
    hallucination_severity: AlucinationSeverity = Field(..., description="Severidade da alucinação")
    divergence_percentage: float = Field(..., ge=0, le=100, description="Divergência em %")
    recommendations: List[str] = Field(..., description="Recomendações")
    
    class Config:
        frozen = True


class AdvancedConfidencePolicy:
    """Política de confiança avançada com detecção de alucinação.
    
    Responsabilidades:
    1. Calcular confiança usando Bayesiano
    2. Detectar alucinações (divergências)
    3. Fornecer recomendações
    4. Rastrear padrões de alucinação
    """
    
    def __init__(self,
                 hallucination_threshold_percentage: float = 20.0,
                 min_evidence_count: int = 2):
        """Inicializa a política.
        
        Args:
            hallucination_threshold_percentage: Threshold de divergência para flaggar alucinação
            min_evidence_count: Número mínimo de evidências
        """
        self.hallucination_threshold = hallucination_threshold_percentage
        self.min_evidence_count = min_evidence_count
        self.logger = logging.getLogger("advanced_confidence_policy")
        self._hallucination_history: List[Dict] = []
    
    def calculate_confidence(self,
                            agent_confidence: float,
                            evidence_count: int,
                            evidence_weight: float = 1.0,
                            agent_id: Optional[str] = None) -> ConfidenceCalculation:
        """Calcula confiança com detecção de alucinação.
        
        Fórmula Bayesiana:
        P(H|E) = P(E|H) * P(H) / P(E)
        
        Onde:
        - H = Hipótese (decisão correta)
        - E = Evidência (dados do agente)
        
        Args:
            agent_confidence: Confiança reportada pelo agente (0-1)
            evidence_count: Número de evidências
            evidence_weight: Peso das evidências (0-1)
            agent_id: ID do agente (para rastreamento)
        
        Returns:
            ConfidenceCalculation
        """
        # Validar entrada
        agent_confidence = max(0, min(1, agent_confidence))
        evidence_weight = max(0, min(1, evidence_weight))
        
        # Cálculo Bayesiano
        bayesian = self._calculate_bayesian(
            agent_confidence,
            evidence_count,
            evidence_weight
        )
        
        calculated_confidence = bayesian.posterior_probability
        
        # Detectar alucinação
        divergence_percentage = abs(agent_confidence - calculated_confidence) * 100
        hallucination_detected = divergence_percentage > self.hallucination_threshold
        hallucination_severity = self._classify_hallucination_severity(divergence_percentage)
        
        # Determinar nível de confiança
        confidence_level = self._classify_confidence_level(calculated_confidence)
        
        # Gerar recomendações
        recommendations = self._generate_recommendations(
            calculated_confidence,
            confidence_level,
            hallucination_detected,
            hallucination_severity,
            evidence_count
        )
        
        # Rastrear alucinação
        if hallucination_detected:
            self._hallucination_history.append({
                "agent_id": agent_id,
                "agent_confidence": agent_confidence,
                "calculated_confidence": calculated_confidence,
                "divergence_percentage": divergence_percentage,
                "severity": hallucination_severity.value,
            })
            
            self.logger.warning(
                f"Alucinação detectada [agent={agent_id}]: "
                f"reportada={agent_confidence:.2f}, "
                f"calculada={calculated_confidence:.2f}, "
                f"divergência={divergence_percentage:.1f}%"
            )
        
        return ConfidenceCalculation(
            agent_confidence=agent_confidence,
            evidence_count=evidence_count,
            evidence_weight=evidence_weight,
            calculated_confidence=calculated_confidence,
            confidence_level=confidence_level,
            bayesian_calculation=bayesian.to_dict(),
            hallucination_detected=hallucination_detected,
            hallucination_severity=hallucination_severity,
            divergence_percentage=divergence_percentage,
            recommendations=recommendations,
        )
    
    def _calculate_bayesian(self,
                           agent_confidence: float,
                           evidence_count: int,
                           evidence_weight: float) -> BayesianCalculation:
        """Calcula probabilidade bayesiana.
        
        Args:
            agent_confidence: Confiança do agente
            evidence_count: Número de evidências
            evidence_weight: Peso das evidências
        
        Returns:
            BayesianCalculation
        """
        # Prior: Probabilidade prévia baseada em histórico
        prior = 0.5  # Sem informação prévia, assume 50%
        
        # Likelihood: P(E|H) - Probabilidade da evidência dado que H é verdadeira
        # Aumenta com número e peso de evidências
        likelihood = min(1.0, 0.5 + (evidence_count * 0.15) + (evidence_weight * 0.2))
        
        # Evidence: P(E) - Probabilidade da evidência
        # Combina likelihood com prior
        evidence = (likelihood * prior) + ((1 - likelihood) * (1 - prior))
        
        # Posterior: P(H|E) - Probabilidade posterior (Bayes' theorem)
        posterior = (likelihood * prior) / evidence if evidence > 0 else 0.5
        
        # Ajustar posterior com confiança do agente
        adjusted_posterior = (posterior * 0.7) + (agent_confidence * 0.3)
        
        return BayesianCalculation(
            prior_probability=prior,
            likelihood=likelihood,
            evidence_probability=evidence,
            posterior_probability=adjusted_posterior,
        )
    
    def _classify_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Classifica nível de confiança.
        
        Args:
            confidence: Valor de confiança (0-1)
        
        Returns:
            ConfidenceLevel
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
    
    def _classify_hallucination_severity(self, divergence_percentage: float) -> AlucinationSeverity:
        """Classifica severidade de alucinação.
        
        Args:
            divergence_percentage: Divergência em percentual
        
        Returns:
            AlucinationSeverity
        """
        if divergence_percentage < 1:
            return AlucinationSeverity.NONE
        elif divergence_percentage < 10:
            return AlucinationSeverity.LOW
        elif divergence_percentage < 20:
            return AlucinationSeverity.MEDIUM
        elif divergence_percentage < 50:
            return AlucinationSeverity.HIGH
        else:
            return AlucinationSeverity.CRITICAL
    
    def _generate_recommendations(self,
                                 confidence: float,
                                 confidence_level: ConfidenceLevel,
                                 hallucination_detected: bool,
                                 hallucination_severity: AlucinationSeverity,
                                 evidence_count: int) -> List[str]:
        """Gera recomendações baseadas no cálculo.
        
        Args:
            confidence: Confiança calculada
            confidence_level: Nível de confiança
            hallucination_detected: Alucinação detectada?
            hallucination_severity: Severidade da alucinação
            evidence_count: Número de evidências
        
        Returns:
            Lista de recomendações
        """
        recommendations = []
        
        # Recomendações por nível de confiança
        if confidence_level == ConfidenceLevel.VERY_LOW:
            recommendations.append("🔴 CONFIANÇA MUITO BAIXA: Requer revisão humana obrigatória")
        elif confidence_level == ConfidenceLevel.LOW:
            recommendations.append("🟡 CONFIANÇA BAIXA: Recomenda-se revisão humana")
        elif confidence_level == ConfidenceLevel.MEDIUM:
            recommendations.append("🟠 CONFIANÇA MÉDIA: Monitorar resultado")
        elif confidence_level == ConfidenceLevel.HIGH:
            recommendations.append("🟢 CONFIANÇA ALTA: Pode proceder com monitoramento")
        elif confidence_level == ConfidenceLevel.VERY_HIGH:
            recommendations.append("✅ CONFIANÇA MUITO ALTA: Pode proceder automaticamente")
        
        # Recomendações por alucinação
        if hallucination_detected:
            if hallucination_severity == AlucinationSeverity.CRITICAL:
                recommendations.append("🚨 ALUCINAÇÃO CRÍTICA: Possível falha no agente")
                recommendations.append("→ Verificar logs do agente")
                recommendations.append("→ Considerar retentativa com dados diferentes")
            elif hallucination_severity == AlucinationSeverity.HIGH:
                recommendations.append("⚠️ ALUCINAÇÃO ALTA: Divergência significativa")
                recommendations.append("→ Investigar discrepância")
            elif hallucination_severity == AlucinationSeverity.MEDIUM:
                recommendations.append("⚡ ALUCINAÇÃO MÉDIA: Pequena divergência detectada")
                recommendations.append("→ Monitorar padrão")
            elif hallucination_severity == AlucinationSeverity.LOW:
                recommendations.append("ℹ️ ALUCINAÇÃO BAIXA: Variação normal")
        
        # Recomendações por evidência
        if evidence_count < self.min_evidence_count:
            recommendations.append(f"📊 EVIDÊNCIA INSUFICIENTE: Apenas {evidence_count} evidência(s)")
            recommendations.append(f"→ Coletar pelo menos {self.min_evidence_count} evidências")
        
        return recommendations
    
    def get_hallucination_statistics(self) -> Dict:
        """Obtém estatísticas de alucinações.
        
        Returns:
            Dicionário com estatísticas
        """
        if not self._hallucination_history:
            return {
                "total_hallucinations": 0,
                "by_severity": {},
                "average_divergence": 0,
            }
        
        by_severity = {}
        total_divergence = 0
        
        for record in self._hallucination_history:
            severity = record["severity"]
            by_severity[severity] = by_severity.get(severity, 0) + 1
            total_divergence += record["divergence_percentage"]
        
        return {
            "total_hallucinations": len(self._hallucination_history),
            "by_severity": by_severity,
            "average_divergence": total_divergence / len(self._hallucination_history),
            "critical_count": by_severity.get("critical", 0),
        }
    
    def clear_hallucination_history(self):
        """Limpa histórico de alucinações."""
        self._hallucination_history.clear()
        self.logger.info("Hallucination history cleared")
