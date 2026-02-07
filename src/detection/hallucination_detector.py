"""
Hallucination Detector - Detecção Avançada de Alucinações

Implementa detecção de alucinações em agentes LLM através de múltiplas
técnicas: divergência de confiança, análise de padrões, validação cruzada.

Padrão: Anomaly Detection + Pattern Analysis
Resiliência: Múltiplas técnicas, fallback, histórico
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DetectionMethod(str, Enum):
    """Métodos de detecção."""
    CONFIDENCE_DIVERGENCE = "confidence_divergence"  # Divergência de confiança
    PATTERN_ANALYSIS = "pattern_analysis"            # Análise de padrões
    CROSS_VALIDATION = "cross_validation"            # Validação cruzada
    SEMANTIC_CONSISTENCY = "semantic_consistency"    # Consistência semântica
    STATISTICAL_ANOMALY = "statistical_anomaly"      # Anomalia estatística


class HallucinationLevel(str, Enum):
    """Níveis de alucinação."""
    NONE = "none"                  # Sem alucinação
    MINOR = "minor"                # Alucinação menor
    MODERATE = "moderate"          # Alucinação moderada
    SEVERE = "severe"              # Alucinação severa
    CRITICAL = "critical"          # Alucinação crítica


@dataclass
class HallucinationEvidence:
    """Evidência de alucinação."""
    
    method: DetectionMethod
    confidence: float              # Confiança da detecção (0-1)
    description: str
    details: Dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class HallucinationReport(BaseModel):
    """Relatório de detecção de alucinação."""
    
    agent_id: str = Field(..., description="ID do agente")
    detection_timestamp: datetime = Field(..., description="Quando foi detectado")
    hallucination_level: HallucinationLevel = Field(..., description="Nível de alucinação")
    overall_confidence: float = Field(..., ge=0, le=1, description="Confiança geral")
    evidence: List[Dict] = Field(..., description="Evidências coletadas")
    affected_fields: List[str] = Field(..., description="Campos afetados")
    recommendations: List[str] = Field(..., description="Recomendações")
    similar_past_cases: List[Dict] = Field(..., description="Casos similares passados")
    
    class Config:
        frozen = True


class HallucinationDetector:
    """Detector de alucinações em agentes LLM.
    
    Responsabilidades:
    1. Detectar alucinações usando múltiplas técnicas
    2. Rastrear padrões de alucinação
    3. Fornecer recomendações
    4. Aprender com histórico
    """
    
    def __init__(self,
                 confidence_divergence_threshold: float = 0.20,
                 pattern_threshold: float = 0.15,
                 history_retention_days: int = 30):
        """Inicializa o detector.
        
        Args:
            confidence_divergence_threshold: Threshold de divergência de confiança
            pattern_threshold: Threshold para padrões
            history_retention_days: Dias para manter histórico
        """
        self.confidence_threshold = confidence_divergence_threshold
        self.pattern_threshold = pattern_threshold
        self.history_retention_days = history_retention_days
        self.logger = logging.getLogger("hallucination_detector")
        self._detection_history: List[HallucinationReport] = []
        self._agent_patterns: Dict[str, List[Dict]] = {}
    
    def detect(self,
              agent_id: str,
              agent_output: Dict,
              expected_output: Optional[Dict] = None,
              context: Optional[Dict] = None) -> HallucinationReport:
        """Detecta alucinações em saída de agente.
        
        Args:
            agent_id: ID do agente
            agent_output: Saída do agente
            expected_output: Saída esperada (opcional)
            context: Contexto adicional (opcional)
        
        Returns:
            HallucinationReport
        """
        evidence_list: List[HallucinationEvidence] = []
        
        # Técnica 1: Divergência de Confiança
        confidence_evidence = self._detect_confidence_divergence(
            agent_output,
            expected_output
        )
        if confidence_evidence:
            evidence_list.append(confidence_evidence)
        
        # Técnica 2: Análise de Padrões
        pattern_evidence = self._detect_pattern_anomaly(agent_id, agent_output)
        if pattern_evidence:
            evidence_list.append(pattern_evidence)
        
        # Técnica 3: Validação Cruzada
        if expected_output:
            cross_val_evidence = self._detect_cross_validation_failure(
                agent_output,
                expected_output
            )
            if cross_val_evidence:
                evidence_list.append(cross_val_evidence)
        
        # Técnica 4: Consistência Semântica
        semantic_evidence = self._detect_semantic_inconsistency(agent_output)
        if semantic_evidence:
            evidence_list.append(semantic_evidence)
        
        # Técnica 5: Anomalia Estatística
        statistical_evidence = self._detect_statistical_anomaly(
            agent_id,
            agent_output
        )
        if statistical_evidence:
            evidence_list.append(statistical_evidence)
        
        # Calcular nível geral
        overall_confidence = self._calculate_overall_confidence(evidence_list)
        hallucination_level = self._classify_hallucination_level(overall_confidence)
        
        # Identificar campos afetados
        affected_fields = self._identify_affected_fields(evidence_list)
        
        # Gerar recomendações
        recommendations = self._generate_recommendations(
            hallucination_level,
            evidence_list,
            agent_id
        )
        
        # Encontrar casos similares
        similar_cases = self._find_similar_cases(agent_id, agent_output)
        
        # Criar relatório
        report = HallucinationReport(
            agent_id=agent_id,
            detection_timestamp=datetime.now(timezone.utc),
            hallucination_level=hallucination_level,
            overall_confidence=overall_confidence,
            evidence=[e.__dict__ for e in evidence_list],
            affected_fields=affected_fields,
            recommendations=recommendations,
            similar_past_cases=similar_cases,
        )
        
        # Rastrear
        self._detection_history.append(report)
        self._update_agent_patterns(agent_id, agent_output)
        
        # Log
        if hallucination_level != HallucinationLevel.NONE:
            self.logger.warning(
                f"Hallucination detected in {agent_id}: "
                f"level={hallucination_level.value}, "
                f"confidence={overall_confidence:.2f}"
            )
        
        return report
    
    def _detect_confidence_divergence(self,
                                     agent_output: Dict,
                                     expected_output: Optional[Dict]) -> Optional[HallucinationEvidence]:
        """Detecta divergência de confiança.
        
        Args:
            agent_output: Saída do agente
            expected_output: Saída esperada
        
        Returns:
            HallucinationEvidence ou None
        """
        agent_confidence = agent_output.get("confidence", 0.5)
        
        if not expected_output:
            return None
        
        # Calcular confiança esperada
        expected_confidence = expected_output.get("confidence", 0.5)
        
        divergence = abs(agent_confidence - expected_confidence)
        
        if divergence > self.confidence_threshold:
            return HallucinationEvidence(
                method=DetectionMethod.CONFIDENCE_DIVERGENCE,
                confidence=min(divergence, 1.0),
                description=f"Confidence divergence: {divergence:.2%}",
                details={
                    "agent_confidence": agent_confidence,
                    "expected_confidence": expected_confidence,
                    "divergence": divergence,
                },
            )
        
        return None
    
    def _detect_pattern_anomaly(self,
                               agent_id: str,
                               agent_output: Dict) -> Optional[HallucinationEvidence]:
        """Detecta anomalias em padrões.
        
        Args:
            agent_id: ID do agente
            agent_output: Saída do agente
        
        Returns:
            HallucinationEvidence ou None
        """
        if agent_id not in self._agent_patterns:
            return None
        
        patterns = self._agent_patterns[agent_id]
        if not patterns:
            return None
        
        # Calcular desvio do padrão
        avg_confidence = sum(p.get("confidence", 0.5) for p in patterns) / len(patterns)
        current_confidence = agent_output.get("confidence", 0.5)
        
        deviation = abs(current_confidence - avg_confidence)
        
        if deviation > self.pattern_threshold:
            return HallucinationEvidence(
                method=DetectionMethod.PATTERN_ANALYSIS,
                confidence=min(deviation, 1.0),
                description=f"Pattern anomaly: deviation {deviation:.2%}",
                details={
                    "average_confidence": avg_confidence,
                    "current_confidence": current_confidence,
                    "deviation": deviation,
                    "pattern_count": len(patterns),
                },
            )
        
        return None
    
    def _detect_cross_validation_failure(self,
                                        agent_output: Dict,
                                        expected_output: Dict) -> Optional[HallucinationEvidence]:
        """Detecta falha em validação cruzada.
        
        Args:
            agent_output: Saída do agente
            expected_output: Saída esperada
        
        Returns:
            HallucinationEvidence ou None
        """
        # Comparar campos principais
        agent_result = agent_output.get("result", "")
        expected_result = expected_output.get("result", "")
        
        # Calcular similaridade simples (Jaccard)
        agent_words = set(str(agent_result).lower().split())
        expected_words = set(str(expected_result).lower().split())
        
        if not agent_words or not expected_words:
            return None
        
        intersection = len(agent_words & expected_words)
        union = len(agent_words | expected_words)
        
        similarity = intersection / union if union > 0 else 0
        
        if similarity < 0.5:
            return HallucinationEvidence(
                method=DetectionMethod.CROSS_VALIDATION,
                confidence=1 - similarity,
                description=f"Cross-validation failed: similarity {similarity:.2%}",
                details={
                    "similarity": similarity,
                    "agent_result": agent_result[:100],
                    "expected_result": expected_result[:100],
                },
            )
        
        return None
    
    def _detect_semantic_inconsistency(self,
                                      agent_output: Dict) -> Optional[HallucinationEvidence]:
        """Detecta inconsistência semântica.
        
        Args:
            agent_output: Saída do agente
        
        Returns:
            HallucinationEvidence ou None
        """
        # Verificar campos obrigatórios
        required_fields = ["result", "confidence", "reasoning"]
        missing_fields = [f for f in required_fields if f not in agent_output]
        
        if missing_fields:
            return HallucinationEvidence(
                method=DetectionMethod.SEMANTIC_CONSISTENCY,
                confidence=0.5,
                description=f"Missing required fields: {missing_fields}",
                details={"missing_fields": missing_fields},
            )
        
        # Verificar valores válidos
        confidence = agent_output.get("confidence", 0)
        if not (0 <= confidence <= 1):
            return HallucinationEvidence(
                method=DetectionMethod.SEMANTIC_CONSISTENCY,
                confidence=0.8,
                description=f"Invalid confidence value: {confidence}",
                details={"confidence": confidence},
            )
        
        return None
    
    def _detect_statistical_anomaly(self,
                                   agent_id: str,
                                   agent_output: Dict) -> Optional[HallucinationEvidence]:
        """Detecta anomalia estatística.
        
        Args:
            agent_id: ID do agente
            agent_output: Saída do agente
        
        Returns:
            HallucinationEvidence ou None
        """
        if agent_id not in self._agent_patterns or not self._agent_patterns[agent_id]:
            return None
        
        patterns = self._agent_patterns[agent_id]
        
        # Calcular desvio padrão
        confidences = [p.get("confidence", 0.5) for p in patterns]
        mean = sum(confidences) / len(confidences)
        variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)
        std_dev = variance ** 0.5
        
        current_confidence = agent_output.get("confidence", 0.5)
        z_score = abs(current_confidence - mean) / std_dev if std_dev > 0 else 0
        
        # Z-score > 2 é considerado anomalia
        if z_score > 2:
            return HallucinationEvidence(
                method=DetectionMethod.STATISTICAL_ANOMALY,
                confidence=min(z_score / 5, 1.0),  # Normalizar
                description=f"Statistical anomaly: z-score {z_score:.2f}",
                details={
                    "z_score": z_score,
                    "mean": mean,
                    "std_dev": std_dev,
                    "current_confidence": current_confidence,
                },
            )
        
        return None
    
    def _calculate_overall_confidence(self, evidence_list: List[HallucinationEvidence]) -> float:
        """Calcula confiança geral.
        
        Args:
            evidence_list: Lista de evidências
        
        Returns:
            Confiança geral (0-1)
        """
        if not evidence_list:
            return 0.0
        
        # Média ponderada
        total_confidence = sum(e.confidence for e in evidence_list)
        return min(total_confidence / len(evidence_list), 1.0)
    
    def _classify_hallucination_level(self, confidence: float) -> HallucinationLevel:
        """Classifica nível de alucinação.
        
        Args:
            confidence: Confiança da detecção
        
        Returns:
            HallucinationLevel
        """
        if confidence < 0.1:
            return HallucinationLevel.NONE
        elif confidence < 0.3:
            return HallucinationLevel.MINOR
        elif confidence < 0.6:
            return HallucinationLevel.MODERATE
        elif confidence < 0.8:
            return HallucinationLevel.SEVERE
        else:
            return HallucinationLevel.CRITICAL
    
    def _identify_affected_fields(self, evidence_list: List[HallucinationEvidence]) -> List[str]:
        """Identifica campos afetados.
        
        Args:
            evidence_list: Lista de evidências
        
        Returns:
            Lista de campos afetados
        """
        affected = set()
        
        for evidence in evidence_list:
            if evidence.method == DetectionMethod.CONFIDENCE_DIVERGENCE:
                affected.add("confidence")
            elif evidence.method == DetectionMethod.CROSS_VALIDATION:
                affected.add("result")
            elif evidence.method == DetectionMethod.SEMANTIC_CONSISTENCY:
                affected.update(evidence.details.get("missing_fields", []))
        
        return list(affected)
    
    def _generate_recommendations(self,
                                 level: HallucinationLevel,
                                 evidence_list: List[HallucinationEvidence],
                                 agent_id: str) -> List[str]:
        """Gera recomendações.
        
        Args:
            level: Nível de alucinação
            evidence_list: Lista de evidências
            agent_id: ID do agente
        
        Returns:
            Lista de recomendações
        """
        recommendations = []
        
        if level == HallucinationLevel.CRITICAL:
            recommendations.append("🚨 CRÍTICO: Requer ação imediata")
            recommendations.append("→ Rejeitar resultado do agente")
            recommendations.append("→ Investigar logs do agente")
            recommendations.append("→ Considerar retentativa com prompt diferente")
        elif level == HallucinationLevel.SEVERE:
            recommendations.append("⚠️ SEVERO: Requer revisão humana")
            recommendations.append("→ Não confiar automaticamente no resultado")
            recommendations.append("→ Validar com fonte externa")
        elif level == HallucinationLevel.MODERATE:
            recommendations.append("🟠 MODERADO: Monitorar com atenção")
            recommendations.append("→ Registrar para análise posterior")
        elif level == HallucinationLevel.MINOR:
            recommendations.append("ℹ️ MENOR: Registrar para histórico")
        
        return recommendations
    
    def _find_similar_cases(self, agent_id: str, agent_output: Dict) -> List[Dict]:
        """Encontra casos similares no histórico.
        
        Args:
            agent_id: ID do agente
            agent_output: Saída do agente
        
        Returns:
            Lista de casos similares
        """
        similar = []
        
        for report in self._detection_history[-10:]:  # Últimos 10
            if report.agent_id == agent_id and report.hallucination_level != HallucinationLevel.NONE:
                similar.append({
                    "timestamp": report.detection_timestamp.isoformat(),
                    "level": report.hallucination_level.value,
                    "confidence": report.overall_confidence,
                })
        
        return similar
    
    def _update_agent_patterns(self, agent_id: str, agent_output: Dict):
        """Atualiza padrões do agente.
        
        Args:
            agent_id: ID do agente
            agent_output: Saída do agente
        """
        if agent_id not in self._agent_patterns:
            self._agent_patterns[agent_id] = []
        
        self._agent_patterns[agent_id].append({
            "confidence": agent_output.get("confidence", 0.5),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Manter apenas histórico recente
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=self.history_retention_days)
        self._agent_patterns[agent_id] = [
            p for p in self._agent_patterns[agent_id]
            if datetime.fromisoformat(p["timestamp"]) > cutoff_time
        ]
    
    def get_statistics(self) -> Dict:
        """Obtém estatísticas de detecção.
        
        Returns:
            Dicionário com estatísticas
        """
        if not self._detection_history:
            return {"total_detections": 0}
        
        by_level = {}
        for report in self._detection_history:
            level = report.hallucination_level.value
            by_level[level] = by_level.get(level, 0) + 1
        
        return {
            "total_detections": len(self._detection_history),
            "by_level": by_level,
            "tracked_agents": len(self._agent_patterns),
        }
