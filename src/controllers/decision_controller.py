"""
DecisionController - Controlador responsável por orquestrar decisões entre múltiplos agentes.

Implementa lógica de consenso, validação cruzada e geração de decisões finais.

Padrão: Controller Pattern + Strategy Pattern (similar a Spring's @RestController em Java)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging
import json

from src.agents.base_agent import AgentOutput, AgentStatus
from src.services.confidence_service import ConfidenceService, ConfidenceStrategy

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Tipos de decisões que o sistema pode tomar."""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    INVESTIGATE = "investigate"
    MONITOR = "monitor"
    REMEDIATE = "remediate"


class DecisionReason(str, Enum):
    """Razões para uma decisão."""
    CONSENSUS = "consensus"
    MAJORITY = "majority"
    EXPERT = "expert"
    THRESHOLD = "threshold"
    CONFLICT = "conflict"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class Decision:
    """Representa uma decisão tomada pelo sistema.
    
    Atributos:
        decision_id: ID único da decisão
        decision_type: Tipo de decisão (approve, reject, escalate, etc)
        reason: Razão para a decisão
        confidence: Score de confiança (0.0 a 1.0)
        agent_outputs: Outputs dos agentes que contribuíram
        evidence_summary: Resumo das evidências
        recommended_action: Ação recomendada
        requires_human_review: Se requer revisão humana
        timestamp: Quando foi tomada
        metadata: Dados adicionais
    """
    decision_id: str
    decision_type: DecisionType
    reason: DecisionReason
    confidence: float
    agent_outputs: List[AgentOutput] = field(default_factory=list)
    evidence_summary: str = ""
    recommended_action: str = ""
    requires_human_review: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "reason": self.reason.value,
            "confidence": round(self.confidence, 3),
            "agent_count": len(self.agent_outputs),
            "evidence_summary": self.evidence_summary,
            "recommended_action": self.recommended_action,
            "requires_human_review": self.requires_human_review,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class DecisionPolicy:
    """Define políticas de decisão baseadas em regras.
    
    Similar a um Specification Pattern em Java.
    """
    
    def __init__(self, name: str, confidence_threshold: float = 0.7,
                 consensus_threshold: float = 0.8):
        """Inicializa política.
        
        Args:
            name: Nome da política
            confidence_threshold: Threshold mínimo de confiança
            consensus_threshold: Threshold mínimo de consenso
        """
        self.name = name
        self.confidence_threshold = confidence_threshold
        self.consensus_threshold = consensus_threshold
    
    def evaluate(self, outputs: List[AgentOutput], confidence: float) -> Tuple[bool, str]:
        """Avalia se a política é satisfeita.
        
        Args:
            outputs: Outputs dos agentes
            confidence: Score de confiança
        
        Returns:
            Tupla (satisfeito, razão)
        """
        # Verificar confiança
        if confidence < self.confidence_threshold:
            return False, f"Confiança {confidence:.1%} abaixo do threshold {self.confidence_threshold:.1%}"
        
        # Verificar consenso
        if len(outputs) > 1:
            results = [str(o.result).lower() for o in outputs]
            most_common = max(set(results), key=results.count)
            agreement_ratio = results.count(most_common) / len(results)
            
            if agreement_ratio < self.consensus_threshold:
                return False, f"Consenso {agreement_ratio:.1%} abaixo do threshold {self.consensus_threshold:.1%}"
        
        return True, "Política satisfeita"


class DecisionController:
    """Controlador que orquestra decisões entre múltiplos agentes.
    
    Responsabilidades:
    1. Coletar outputs de múltiplos agentes
    2. Calcular confiança usando ConfidenceService
    3. Aplicar políticas de decisão
    4. Gerar decisão final
    5. Determinar se requer revisão humana
    """
    
    def __init__(self, confidence_service: Optional[ConfidenceService] = None):
        """Inicializa o controlador.
        
        Args:
            confidence_service: Serviço de cálculo de confiança
        """
        self.confidence_service = confidence_service or ConfidenceService()
        self.logger = logging.getLogger("decision_controller")
        
        # Políticas padrão
        self.policies = {
            "strict": DecisionPolicy("strict", confidence_threshold=0.9, consensus_threshold=0.95),
            "balanced": DecisionPolicy("balanced", confidence_threshold=0.7, consensus_threshold=0.8),
            "permissive": DecisionPolicy("permissive", confidence_threshold=0.5, consensus_threshold=0.6),
        }
    
    def _determine_decision_type(self, outputs: List[AgentOutput]) -> DecisionType:
        """Determina o tipo de decisão baseado nos outputs.
        
        Args:
            outputs: Outputs dos agentes
        
        Returns:
            Tipo de decisão
        """
        if not outputs:
            return DecisionType.INVESTIGATE
        
        # Extrair resultados
        results = [str(o.result).lower() for o in outputs]
        
        # Contar ocorrências
        approve_count = sum(1 for r in results if "approve" in r or "ok" in r or "pass" in r)
        reject_count = sum(1 for r in results if "reject" in r or "fail" in r or "critical" in r)
        
        total = len(results)
        
        # Lógica de decisão
        if approve_count >= total * 0.8:
            return DecisionType.APPROVE
        elif reject_count >= total * 0.8:
            return DecisionType.REJECT
        elif reject_count >= total * 0.5:
            return DecisionType.ESCALATE
        else:
            return DecisionType.MONITOR
    
    def _determine_reason(self, outputs: List[AgentOutput], 
                         confidence: float, policy_satisfied: bool) -> DecisionReason:
        """Determina a razão para a decisão.
        
        Args:
            outputs: Outputs dos agentes
            confidence: Score de confiança
            policy_satisfied: Se política foi satisfeita
        
        Returns:
            Razão da decisão
        """
        if not outputs:
            return DecisionReason.INSUFFICIENT_DATA
        
        if len(outputs) == 1:
            return DecisionReason.EXPERT
        
        # Verificar consenso
        results = [str(o.result).lower() for o in outputs]
        most_common = max(set(results), key=results.count)
        agreement_ratio = results.count(most_common) / len(results)
        
        if agreement_ratio >= 0.9:
            return DecisionReason.CONSENSUS
        elif agreement_ratio >= 0.6:
            return DecisionReason.MAJORITY
        elif agreement_ratio >= 0.5:
            return DecisionReason.CONFLICT
        else:
            return DecisionReason.CONFLICT
    
    def _should_require_human_review(self, confidence: float, 
                                     reason: DecisionReason,
                                     decision_type: DecisionType) -> bool:
        """Determina se decisão requer revisão humana.
        
        Args:
            confidence: Score de confiança
            reason: Razão da decisão
            decision_type: Tipo de decisão
        
        Returns:
            True se requer revisão
        """
        # Sempre revisar decisões críticas com baixa confiança
        if decision_type in [DecisionType.REJECT, DecisionType.ESCALATE]:
            if confidence < 0.7:
                return True
        
        # Revisar se há conflito entre agentes
        if reason == DecisionReason.CONFLICT:
            return True
        
        # Revisar se dados insuficientes
        if reason == DecisionReason.INSUFFICIENT_DATA:
            return True
        
        return False
    
    def make_decision(self, outputs: List[AgentOutput],
                     policy_name: str = "balanced",
                     context: Optional[Dict] = None) -> Decision:
        """Toma uma decisão baseada nos outputs dos agentes.
        
        Args:
            outputs: Outputs dos agentes
            policy_name: Nome da política a usar
            context: Contexto adicional (alerta, incidente, etc)
        
        Returns:
            Decision com resultado
        """
        if not outputs:
            self.logger.warning("No agent outputs provided")
            return Decision(
                decision_id=self._generate_decision_id(),
                decision_type=DecisionType.INVESTIGATE,
                reason=DecisionReason.INSUFFICIENT_DATA,
                confidence=0.0,
                evidence_summary="Nenhum agente forneceu output",
                requires_human_review=True,
            )
        
        # Calcular confiança usando ensemble
        confidence_score = self.confidence_service.calculate_ensemble(
            outputs[0],
            outputs[1:] if len(outputs) > 1 else None
        )
        
        # Aplicar política
        policy = self.policies.get(policy_name, self.policies["balanced"])
        policy_satisfied, policy_reason = policy.evaluate(outputs, confidence_score.final_score)
        
        # Determinar tipo de decisão
        decision_type = self._determine_decision_type(outputs)
        
        # Determinar razão
        reason = self._determine_reason(outputs, confidence_score.final_score, policy_satisfied)
        
        # Determinar se requer revisão humana
        requires_review = self._should_require_human_review(
            confidence_score.final_score,
            reason,
            decision_type
        )
        
        # Gerar resumo de evidências
        evidence_summary = self._generate_evidence_summary(outputs)
        
        # Gerar ação recomendada
        recommended_action = self._generate_recommended_action(decision_type, outputs)
        
        # Criar decisão
        decision = Decision(
            decision_id=self._generate_decision_id(),
            decision_type=decision_type,
            reason=reason,
            confidence=confidence_score.final_score,
            agent_outputs=outputs,
            evidence_summary=evidence_summary,
            recommended_action=recommended_action,
            requires_human_review=requires_review,
            metadata={
                "policy": policy_name,
                "policy_satisfied": policy_satisfied,
                "confidence_strategy": confidence_score.strategy.value,
                "confidence_factors": confidence_score.factors,
                "agent_count": len(outputs),
            }
        )
        
        self.logger.info(
            f"Decision made: {decision.decision_type.value} "
            f"(confidence={decision.confidence:.1%}, requires_review={requires_review})"
        )
        
        return decision
    
    def _generate_decision_id(self) -> str:
        """Gera ID único para decisão."""
        from uuid import uuid4
        return f"dec_{uuid4().hex[:12]}"
    
    def _generate_evidence_summary(self, outputs: List[AgentOutput]) -> str:
        """Gera resumo das evidências.
        
        Args:
            outputs: Outputs dos agentes
        
        Returns:
            Resumo em texto
        """
        if not outputs:
            return "Sem evidências"
        
        summary_parts = []
        
        for output in outputs:
            if output.evidence:
                evidence_count = len(output.evidence)
                avg_confidence = sum(e.confidence for e in output.evidence) / evidence_count
                summary_parts.append(
                    f"{output.agent_name}: {evidence_count} evidências "
                    f"(confiança média: {avg_confidence:.1%})"
                )
        
        return "; ".join(summary_parts) if summary_parts else "Sem evidências"
    
    def _generate_recommended_action(self, decision_type: DecisionType,
                                     outputs: List[AgentOutput]) -> str:
        """Gera ação recomendada.
        
        Args:
            decision_type: Tipo de decisão
            outputs: Outputs dos agentes
        
        Returns:
            Ação recomendada
        """
        actions = {
            DecisionType.APPROVE: "Prosseguir com a ação planejada",
            DecisionType.REJECT: "Bloquear a ação e notificar stakeholders",
            DecisionType.ESCALATE: "Escalar para time de segurança",
            DecisionType.INVESTIGATE: "Investigar mais antes de tomar decisão",
            DecisionType.MONITOR: "Monitorar situação e reavalia em 5 minutos",
            DecisionType.REMEDIATE: "Executar ações de remediação imediata",
        }
        
        return actions.get(decision_type, "Ação não definida")
    
    def validate_decision(self, decision: Decision) -> Tuple[bool, List[str]]:
        """Valida uma decisão.
        
        Args:
            decision: Decisão a validar
        
        Returns:
            Tupla (válida, lista de erros)
        """
        errors = []
        
        # Validar confiança
        if not 0.0 <= decision.confidence <= 1.0:
            errors.append(f"Confiança inválida: {decision.confidence}")
        
        # Validar que há pelo menos um output
        if not decision.agent_outputs:
            errors.append("Nenhum agente output fornecido")
        
        # Validar que todos os outputs têm status de sucesso
        for output in decision.agent_outputs:
            if output.status != AgentStatus.SUCCESS:
                errors.append(f"Agent {output.agent_name} falhou: {output.error_message}")
        
        return len(errors) == 0, errors
    
    def explain_decision(self, decision: Decision) -> str:
        """Gera explicação legível de uma decisão.
        
        Args:
            decision: Decisão a explicar
        
        Returns:
            Explicação em texto
        """
        explanation = f"""
DECISÃO: {decision.decision_type.value.upper()}
Confiança: {decision.confidence:.1%}
Razão: {decision.reason.value}
Timestamp: {decision.timestamp.isoformat()}

RESUMO DE EVIDÊNCIAS:
{decision.evidence_summary}

AÇÃO RECOMENDADA:
{decision.recommended_action}

REQUER REVISÃO HUMANA: {'Sim' if decision.requires_human_review else 'Não'}

AGENTES CONSULTADOS: {len(decision.agent_outputs)}
"""
        
        for output in decision.agent_outputs:
            explanation += f"\n- {output.agent_name}: {output.result} (confiança: {output.confidence:.1%})"
        
        return explanation
