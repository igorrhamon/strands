"""
SwarmDecisionController - Orquestrador de Decisões com Consenso Ponderado

Implementa votação ponderada entre múltiplos agentes usando WeightedConsensusStrategy.
Cada agente tem um peso baseado em seu papel e domínio de autoridade.

Padrão: Strategy Pattern + Dependency Injection (inspiração Spring Framework)
Resiliência: Integração com CheckpointEngine para persistência de estado
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import logging
import uuid

from pydantic import BaseModel, Field, validator

from src.agents.base_agent import AgentOutput, AgentStatus
from src.strategies.consensus_strategy import (
    WeightedScoreStrategy,
    UnanimousStrategy,
    MajorityStrategy,
    ConsensusStrategy,
    AgentExecution,
    AgentRole,
    ConsensusResult,
)
from src.policies.confidence_policy import ConfidencePolicy, EvidenceItem, ConfidenceCalculation

logger = logging.getLogger(__name__)


class DecisionState(str, Enum):
    """Estados possíveis de uma decisão."""
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    PENDING_HUMAN_APPROVAL = "pending_human_approval"
    MONITORING = "monitoring"
    INVESTIGATING = "investigating"


class DecisionReason(str, Enum):
    """Razões para uma decisão."""
    WEIGHTED_CONSENSUS = "weighted_consensus"
    UNANIMOUS_AGREEMENT = "unanimous_agreement"
    MAJORITY_VOTE = "majority_vote"
    EXPERT_DECISION = "expert_decision"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING_OPINIONS = "conflicting_opinions"
    INSUFFICIENT_DATA = "insufficient_data"
    HALLUCINATION_DETECTED = "hallucination_detected"


class DecisionMetadata(BaseModel):
    """Metadados da decisão para auditoria."""
    
    consensus_type: str = Field(..., description="Tipo de consenso alcançado")
    agent_count: int = Field(..., ge=0, description="Número de agentes")
    weighted_score: float = Field(..., ge=0.0, le=1.0, description="Score ponderado")
    confidence_calculation: Optional[Dict] = Field(None, description="Detalhes do cálculo de confiança")
    hallucination_flag: Optional[str] = Field(None, description="Flag de possível alucinação")
    divergence_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Divergência entre agentes")
    
    class Config:
        frozen = True


@dataclass
class SwarmDecision:
    """Decisão tomada pelo SwarmDecisionController.
    
    Atributos:
        decision_id: ID único da decisão
        state: Estado da decisão
        reason: Razão para a decisão
        confidence_score: Score de confiança (0.0-1.0)
        weighted_score: Score ponderado
        requires_human_review: Se requer revisão humana
        agent_executions: Execuções dos agentes
        evidence_summary: Resumo das evidências
        recommended_action: Ação recomendada
        metadata: Metadados para auditoria
        timestamp: Quando foi tomada
        checkpoint_id: ID do checkpoint salvo (se aplicável)
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: DecisionState = field(default=DecisionState.PENDING_HUMAN_APPROVAL)
    reason: DecisionReason = field(default=DecisionReason.INSUFFICIENT_DATA)
    confidence_score: float = field(default=0.0)
    weighted_score: float = field(default=0.0)
    requires_human_review: bool = field(default=True)
    agent_executions: List[AgentExecution] = field(default_factory=list)
    evidence_summary: str = field(default="")
    recommended_action: str = field(default="")
    metadata: Optional[Dict] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checkpoint_id: Optional[str] = field(default=None)
    
    def to_dict(self) -> Dict:
        """Converte para dicionário."""
        return {
            "decision_id": self.decision_id,
            "state": self.state.value,
            "reason": self.reason.value,
            "confidence_score": round(self.confidence_score, 3),
            "weighted_score": round(self.weighted_score, 3),
            "requires_human_review": self.requires_human_review,
            "agent_count": len(self.agent_executions),
            "evidence_summary": self.evidence_summary,
            "recommended_action": self.recommended_action,
            "timestamp": self.timestamp.isoformat(),
            "checkpoint_id": self.checkpoint_id,
        }


class SwarmDecisionController:
    """Controlador que orquestra decisões usando consenso ponderado.
    
    Responsabilidades:
    1. Converter AgentOutput em AgentExecution
    2. Aplicar WeightedConsensusStrategy
    3. Calcular confiança com ConfidencePolicy
    4. Determinar se requer revisão humana
    5. Persistir checkpoint (se CheckpointEngine fornecido)
    
    Padrão: Strategy Pattern + Dependency Injection
    """
    
    def __init__(self,
                 consensus_strategy: Optional[ConsensusStrategy] = None,
                 confidence_policy: Optional[ConfidencePolicy] = None,
                 checkpoint_engine: Optional['CheckpointEngine'] = None):
        """Inicializa o controlador.
        
        Args:
            consensus_strategy: Estratégia de consenso (default: WeightedScoreStrategy)
            confidence_policy: Política de confiança (default: ConfidencePolicy)
            checkpoint_engine: Engine para persistência (optional)
        """
        self.consensus_strategy = consensus_strategy or WeightedScoreStrategy(confidence_threshold=0.7)
        self.confidence_policy = confidence_policy or ConfidencePolicy(base_weight=1.0)
        self.checkpoint_engine = checkpoint_engine
        self.logger = logging.getLogger("swarm_decision_controller")
    
    def make_decision(self,
                     agent_executions: List[AgentExecution],
                     context: Optional[Dict] = None,
                     save_checkpoint: bool = True) -> SwarmDecision:
        """Toma uma decisão baseada em execuções de agentes.
        
        Fluxo:
        1. Validar execuções
        2. Calcular consenso ponderado
        3. Calcular confiança
        4. Determinar estado
        5. Persistir checkpoint (se habilitado)
        
        Args:
            agent_executions: Lista de execuções de agentes
            context: Contexto adicional (thread_id, plan_id, etc)
            save_checkpoint: Se deve salvar checkpoint
        
        Returns:
            SwarmDecision com resultado
        """
        if not agent_executions:
            self.logger.warning("Nenhuma execução de agente fornecida")
            return self._create_empty_decision()
        
        # Calcular consenso ponderado
        consensus_result = self.consensus_strategy.calculate(agent_executions, context)
        
        # Extrair evidências para cálculo de confiança
        evidence_items = self._extract_evidence(agent_executions)
        
        # Calcular confiança com ConfidencePolicy
        confidence_calculation = self.confidence_policy.calculate_confidence(
            agent_confidence=consensus_result.final_score,
            evidence_items=evidence_items,
            context=context
        )
        
        # Determinar estado da decisão
        decision_state = self._determine_decision_state(
            consensus_result,
            confidence_calculation,
            agent_executions
        )
        
        # Determinar razão
        reason = self._determine_reason(consensus_result, confidence_calculation)
        
        # Gerar resumo de evidências
        evidence_summary = self._generate_evidence_summary(agent_executions, consensus_result)
        
        # Gerar ação recomendada
        recommended_action = self._generate_recommended_action(decision_state, agent_executions)
        
        # Criar decisão
        decision = SwarmDecision(
            state=decision_state,
            reason=reason,
            confidence_score=confidence_calculation.final_confidence,
            weighted_score=consensus_result.final_score,
            requires_human_review=consensus_result.requires_human_review or 
                                 confidence_calculation.hallucination_flag is not None,
            agent_executions=agent_executions,
            evidence_summary=evidence_summary,
            recommended_action=recommended_action,
            metadata={
                "consensus_type": consensus_result.consensus_type,
                "agent_count": len(agent_executions),
                "weighted_score": round(consensus_result.final_score, 3),
                "hallucination_flag": consensus_result.hallucination_flag,
                "divergence_percentage": confidence_calculation.divergence_percentage,
                "confidence_level": confidence_calculation.confidence_level.value,
            }
        )
        
        # Persistir checkpoint se habilitado
        if save_checkpoint and self.checkpoint_engine and context:
            try:
                checkpoint_id = self._save_checkpoint(decision, context)
                decision.checkpoint_id = checkpoint_id
                self.logger.info(f"Checkpoint salvo: {checkpoint_id}")
            except Exception as e:
                self.logger.error(f"Erro ao salvar checkpoint: {e}")
                # Não falhar a decisão por erro de checkpoint
        
        self.logger.info(
            f"Decisão tomada: {decision.state.value} "
            f"(confiança={decision.confidence_score:.3f}, "
            f"score_ponderado={decision.weighted_score:.3f}, "
            f"requer_revisão={decision.requires_human_review})"
        )
        
        return decision
    
    def _create_empty_decision(self) -> SwarmDecision:
        """Cria decisão vazia quando não há execuções."""
        return SwarmDecision(
            state=DecisionState.INVESTIGATING,
            reason=DecisionReason.INSUFFICIENT_DATA,
            confidence_score=0.0,
            weighted_score=0.0,
            requires_human_review=True,
            evidence_summary="Nenhuma execução de agente fornecida",
            recommended_action="Coletar dados de agentes",
        )
    
    def _extract_evidence(self, agent_executions: List[AgentExecution]) -> List[EvidenceItem]:
        """Extrai evidências das execuções dos agentes.
        
        Args:
            agent_executions: Execuções dos agentes
        
        Returns:
            Lista de EvidenceItem
        """
        evidence_items = []
        
        for execution in agent_executions:
            # Usar evidence_count como proxy para qualidade de evidência
            confidence = execution.confidence_score
            weight = 1.0 + (execution.evidence_count * 0.1)  # Aumentar peso com mais evidências
            
            evidence_item = EvidenceItem(
                source=f"{execution.agent_name} ({execution.agent_role.value})",
                confidence=confidence,
                weight=weight,
                description=execution.reasoning,
            )
            evidence_items.append(evidence_item)
        
        return evidence_items
    
    def _determine_decision_state(self,
                                 consensus_result: ConsensusResult,
                                 confidence_calculation: ConfidenceCalculation,
                                 agent_executions: List[AgentExecution]) -> DecisionState:
        """Determina o estado da decisão.
        
        Args:
            consensus_result: Resultado do consenso
            confidence_calculation: Cálculo de confiança
            agent_executions: Execuções dos agentes
        
        Returns:
            DecisionState
        """
        # Se confiança baixa, sempre requer revisão
        if consensus_result.final_score < 0.7:
            return DecisionState.PENDING_HUMAN_APPROVAL
        
        # Se possível alucinação, requer revisão
        if confidence_calculation.hallucination_flag is not None:
            return DecisionState.PENDING_HUMAN_APPROVAL
        
        # Se consenso unânime e confiança alta
        if consensus_result.consensus_type == "unanimous" and consensus_result.final_score > 0.85:
            # Usar resultado do agente
            result = agent_executions[0].result.lower()
            if "escalate" in result or "reject" in result:
                return DecisionState.ESCALATED
            elif "approve" in result or "ok" in result:
                return DecisionState.APPROVED
            else:
                return DecisionState.MONITORING
        
        # Se maioria forte
        if consensus_result.consensus_type in ["majority", "strong_majority"]:
            if consensus_result.final_score > 0.8:
                # Usar resultado mais comum
                results = [e.result.lower() for e in agent_executions]
                most_common = max(set(results), key=results.count)
                
                if "escalate" in most_common or "reject" in most_common:
                    return DecisionState.ESCALATED
                elif "approve" in most_common or "ok" in most_common:
                    return DecisionState.APPROVED
                else:
                    return DecisionState.MONITORING
        
        # Padrão: requer revisão
        return DecisionState.PENDING_HUMAN_APPROVAL
    
    def _determine_reason(self,
                         consensus_result: ConsensusResult,
                         confidence_calculation: ConfidenceCalculation) -> DecisionReason:
        """Determina a razão da decisão.
        
        Args:
            consensus_result: Resultado do consenso
            confidence_calculation: Cálculo de confiança
        
        Returns:
            DecisionReason
        """
        # Verificar alucinação
        if confidence_calculation.hallucination_flag is not None:
            return DecisionReason.HALLUCINATION_DETECTED
        
        # Verificar confiança baixa
        if consensus_result.final_score < 0.7:
            return DecisionReason.LOW_CONFIDENCE
        
        # Verificar tipo de consenso
        if consensus_result.consensus_type == "unanimous":
            return DecisionReason.UNANIMOUS_AGREEMENT
        elif consensus_result.consensus_type == "majority":
            return DecisionReason.MAJORITY_VOTE
        elif consensus_result.consensus_type == "strong_majority":
            return DecisionReason.WEIGHTED_CONSENSUS
        elif consensus_result.consensus_type == "single_agent":
            return DecisionReason.EXPERT_DECISION
        else:
            return DecisionReason.CONFLICTING_OPINIONS
    
    def _generate_evidence_summary(self,
                                  agent_executions: List[AgentExecution],
                                  consensus_result: ConsensusResult) -> str:
        """Gera resumo de evidências.
        
        Args:
            agent_executions: Execuções dos agentes
            consensus_result: Resultado do consenso
        
        Returns:
            Resumo em texto
        """
        if not agent_executions:
            return "Nenhuma evidência disponível"
        
        summary_parts = []
        
        # Contar agentes por resultado
        results = {}
        for execution in agent_executions:
            result = execution.result.lower()
            if result not in results:
                results[result] = []
            results[result].append(execution.agent_name)
        
        # Gerar texto
        for result, agents in results.items():
            summary_parts.append(f"{len(agents)} agente(s) votaram por '{result}': {', '.join(agents)}")
        
        # Adicionar score ponderado
        summary_parts.append(f"Score ponderado final: {consensus_result.final_score:.1%}")
        
        # Adicionar tipo de consenso
        summary_parts.append(f"Tipo de consenso: {consensus_result.consensus_type}")
        
        return " | ".join(summary_parts)
    
    def _generate_recommended_action(self,
                                    decision_state: DecisionState,
                                    agent_executions: List[AgentExecution]) -> str:
        """Gera ação recomendada.
        
        Args:
            decision_state: Estado da decisão
            agent_executions: Execuções dos agentes
        
        Returns:
            Ação recomendada em texto
        """
        if decision_state == DecisionState.APPROVED:
            return "Executar ação aprovada automaticamente"
        elif decision_state == DecisionState.REJECTED:
            return "Rejeitar ação e notificar stakeholders"
        elif decision_state == DecisionState.ESCALATED:
            return "Escalar para time de segurança/operações"
        elif decision_state == DecisionState.MONITORING:
            return "Monitorar situação e aguardar novos dados"
        elif decision_state == DecisionState.INVESTIGATING:
            return "Investigar e coletar mais informações"
        else:  # PENDING_HUMAN_APPROVAL
            return "Aguardar revisão e aprovação humana"
    
    def _save_checkpoint(self, decision: SwarmDecision, context: Dict) -> str:
        """Salva checkpoint da decisão.
        
        Args:
            decision: Decisão tomada
            context: Contexto (thread_id, plan_id, etc)
        
        Returns:
            ID do checkpoint
        """
        if not self.checkpoint_engine:
            raise RuntimeError("CheckpointEngine não configurado")
        
        # Preparar dados para checkpoint
        checkpoint_data = {
            "decision": decision.to_dict(),
            "agent_executions": [
                {
                    "agent_id": e.agent_id,
                    "agent_name": e.agent_name,
                    "confidence_score": e.confidence_score,
                    "result": e.result,
                }
                for e in decision.agent_executions
            ],
            "context": context,
        }
        
        # Salvar via CheckpointEngine
        thread_id = context.get("thread_id", "unknown")
        step_index = context.get("step_index", 0)
        
        return self.checkpoint_engine.persist_execution_step(
            thread_id=thread_id,
            step_index=step_index,
            agent_data=checkpoint_data
        )
