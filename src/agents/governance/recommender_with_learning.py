"""
Recommender Agent com Aprendizado Autônomo (Adaptive V2)

Versão que integra:
- Busca de playbooks conhecidos (Neo4j)
- Geração de novos playbooks (LLM)
- Workflow de curação (aprovação humana)
- Scoring adaptativo baseado em sucesso histórico e volume
"""

import logging
import uuid
import math
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from src.models.swarm import SwarmResult
from src.core.neo4j_playbook_store import Neo4jPlaybookStore, PlaybookStatus
from src.agents.governance.playbook_generator import PlaybookGeneratorAgent

logger = logging.getLogger(__name__)


class RecommenderAgentWithLearning:
    """
    Recommender que aprende e evolui com o tempo.
    
    Fluxo:
    1. Recebe correlação do CorrelatorAgent
    2. Busca playbooks conhecidos (ACTIVE) no Neo4j
    3. Rankeia playbooks usando Score Adaptativo (Confiança * Sucesso * Volume)
    4. Se encontrar, usa imediatamente (com downgrade de segurança se necessário)
    5. Se não encontrar, gera novo playbook via LLM
    6. Armazena como PENDING_REVIEW
    """
    
    agent_id = "recommender-with-learning"
    
    def __init__(
        self,
        playbook_store: Neo4jPlaybookStore,
        playbook_generator: PlaybookGeneratorAgent
    ):
        """Inicializa recommender com aprendizado."""
        self.playbook_store = playbook_store
        self.playbook_generator = playbook_generator
        self.cache = {}  # Cache local de playbooks
        
        # Configurações de Scoring e Segurança
        self.MIN_EXECUTIONS_FOR_CONFIDENCE = 5
        self.DOWNGRADE_THRESHOLD = 0.5  # Taxa de sucesso < 50% causa downgrade
    
    def recommend(
        self,
        correlation_result: SwarmResult,
        alert_fingerprint: str
    ) -> Dict[str, Any]:
        """
        Recomenda ações baseado em correlação e aprendizado histórico.
        """
        decision_id = str(uuid.uuid4())
        
        logger.info(f"[{self.agent_id}] Recomendando ações para {alert_fingerprint} (decision_id: {decision_id})")
        
        try:
            # Extrair tipo de padrão da correlação
            pattern_type = self._extract_pattern_type(correlation_result.hypothesis)
            service_name = self._extract_service_name(correlation_result.evidence)
            
            # 1️⃣ BUSCAR PLAYBOOKS CONHECIDOS
            playbooks = self._lookup_active_playbooks(pattern_type, service_name)
            
            if playbooks:
                # 2️⃣ RANKEAR PLAYBOOKS (Score Adaptativo)
                ranked_playbooks = self._rank_playbooks(playbooks, correlation_result.confidence)
                best_playbook = ranked_playbooks[0]
                
                logger.info(f"Selected playbook via history: {best_playbook['playbook_id']} (Score: {best_playbook.get('score', 0):.2f})")
                
                # 3️⃣ VERIFICAR NECESSIDADE DE DOWNGRADE (Safety Check)
                best_playbook = self._apply_safety_downgrade(best_playbook)
                
                return self._build_recommendation(
                    decision_id=decision_id,
                    playbook=best_playbook,
                    source="KNOWN",
                    correlation_result=correlation_result
                )
            
            # 4️⃣ GERAR NOVO PLAYBOOK VIA LLM (Cold Start)
            logger.info(f"No active playbook found. Generating via LLM...")
            
            generated_playbook = self.playbook_generator.generate_playbook(
                pattern_type=pattern_type,
                service_name=service_name,
                hypothesis=correlation_result.hypothesis,
                evidence=[
                    {
                        "type": str(e.type),
                        "description": e.description,
                        "source": e.source_url
                    }
                    for e in correlation_result.evidence
                ],
                suggested_actions=correlation_result.suggested_actions,
                correlation_data={
                    "confidence": correlation_result.confidence,
                    "hypothesis": correlation_result.hypothesis
                }
            )
            
            if generated_playbook:
                logger.info(f"Generated playbook: {generated_playbook.playbook_id} (PENDING_REVIEW)")
                # Salvar no Neo4j
                self.playbook_store.store_playbook(generated_playbook)
                
                return self._build_recommendation(
                    decision_id=decision_id,
                    playbook=self._playbook_to_dict(generated_playbook),
                    source="GENERATED",
                    correlation_result=correlation_result,
                    requires_approval=True
                )
            
            # 5️⃣ FALLBACK
            logger.warning("Failed to generate playbook. Using fallback actions.")
            return self._build_fallback_recommendation(
                decision_id=decision_id,
                correlation_result=correlation_result
            )
        
        except Exception as e:
            logger.error(f"Error during recommendation: {e}", exc_info=True)
            return self._build_fallback_recommendation(
                decision_id=decision_id,
                correlation_result=correlation_result,
                error=str(e)
            )
    
    def _lookup_active_playbooks(
        self,
        pattern_type: str,
        service_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Busca todos os playbooks ativos no Neo4j."""
        if not self.playbook_store.connected:
            return []
        
        try:
            return self.playbook_store.get_active_playbooks_for_pattern(
                pattern_type=pattern_type,
                service_name=service_name
            )
        except Exception as e:
            logger.error(f"Error looking up playbooks: {e}")
            return []

    def _rank_playbooks(self, playbooks: List[Dict[str, Any]], correlation_confidence: float) -> List[Dict[str, Any]]:
        """Rankeia playbooks usando Score Adaptativo.
        
        Fórmula:
        Score = Correlation * SuccessRate * log(1 + Executions)
        """
        ranked = []
        for pb in playbooks:
            success_rate = pb.get('success_rate', 0.0)
            total_executions = pb.get('total_executions', 0)
            
            # Logarithmic boost para volume (recompensa experiência)
            # log(1) = 0, então usamos log(1 + executions) para garantir score positivo
            # Se executions=0, boost=0.1 (penalidade para cold start)
            volume_boost = math.log1p(total_executions) if total_executions > 0 else 0.1
            
            # Score final
            score = correlation_confidence * success_rate * volume_boost
            
            pb['score'] = score
            ranked.append(pb)
        
        # Ordenar por score decrescente
        return sorted(ranked, key=lambda x: x['score'], reverse=True)

    def _apply_safety_downgrade(self, playbook: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica downgrade de automação se performance for ruim."""
        success_rate = playbook.get('success_rate', 1.0)
        total_executions = playbook.get('total_executions', 0)
        
        # Só penaliza se tiver volume mínimo estatístico
        if total_executions >= self.MIN_EXECUTIONS_FOR_CONFIDENCE:
            if success_rate < self.DOWNGRADE_THRESHOLD:
                logger.warning(f"Downgrading playbook {playbook['playbook_id']} due to low success rate ({success_rate:.2f})")
                playbook['automation_level'] = "MANUAL"
                playbook['risk_level'] = "HIGH"
                playbook['downgrade_reason'] = f"Low success rate: {success_rate:.2f}"
                
        return playbook
    
    def _extract_pattern_type(self, hypothesis: str) -> str:
        """Extrai tipo de padrão da hipótese."""
        if "log" in hypothesis.lower() and "metric" in hypothesis.lower():
            return "LOG_METRIC"
        elif "metric" in hypothesis.lower() and "cpu" in hypothesis.lower():
            return "METRIC_METRIC"
        elif "restart" in hypothesis.lower() or "temporal" in hypothesis.lower():
            return "TEMPORAL"
        else:
            return "UNKNOWN"
    
    def _extract_service_name(self, evidence: List[Any]) -> Optional[str]:
        """Extrai nome do serviço da evidência."""
        if evidence:
            for e in evidence:
                if hasattr(e, 'source_url') and e.source_url:
                    if "app=" in e.source_url:
                        return e.source_url.split("app=")[1].split("&")[0]
        return None
    
    def _playbook_to_dict(self, playbook) -> Dict[str, Any]:
        """Converte Playbook para dict."""
        return {
            "playbook_id": playbook.playbook_id,
            "title": playbook.title,
            "description": playbook.description,
            "pattern_type": playbook.pattern_type,
            "service_name": playbook.service_name,
            "status": playbook.status.value,
            "source": playbook.source.value,
            "steps": playbook.steps,
            "estimated_time_minutes": playbook.estimated_time_minutes,
            "automation_level": playbook.automation_level,
            "risk_level": playbook.risk_level,
            "prerequisites": playbook.prerequisites,
            "success_criteria": playbook.success_criteria,
            "rollback_procedure": playbook.rollback_procedure,
            "metadata": playbook.metadata
        }
    
    def _build_recommendation(
        self,
        decision_id: str,
        playbook: Dict[str, Any],
        source: str,
        correlation_result: SwarmResult,
        requires_approval: bool = False
    ) -> Dict[str, Any]:
        """Constrói recomendação com playbook."""
        return {
            "decision_id": decision_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "REQUIRES_APPROVAL" if requires_approval else "READY",
            "source": source,
            "playbook": playbook,
            "correlation": {
                "hypothesis": correlation_result.hypothesis,
                "confidence": correlation_result.confidence,
                "evidence_count": len(correlation_result.evidence),
                "suggested_actions": correlation_result.suggested_actions
            },
            "execution_steps": self._extract_execution_steps(playbook),
            "estimated_duration_minutes": playbook.get("estimated_time_minutes", 30),
            "risk_assessment": {
                "risk_level": playbook.get("risk_level", "UNKNOWN"),
                "requires_approval": requires_approval,
                "rollback_available": bool(playbook.get("rollback_procedure")),
                "downgrade_reason": playbook.get("downgrade_reason")
            }
        }
    
    def _build_fallback_recommendation(
        self,
        decision_id: str,
        correlation_result: SwarmResult,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Constrói recomendação fallback."""
        return {
            "decision_id": decision_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "FALLBACK",
            "source": "FALLBACK",
            "playbook": None,
            "correlation": {
                "hypothesis": correlation_result.hypothesis,
                "confidence": correlation_result.confidence,
                "evidence_count": len(correlation_result.evidence),
                "suggested_actions": correlation_result.suggested_actions
            },
            "execution_steps": correlation_result.suggested_actions,
            "estimated_duration_minutes": 30,
            "risk_assessment": {
                "risk_level": "MEDIUM",
                "requires_approval": True,
                "rollback_available": False
            },
            "error": error
        }
    
    def _extract_execution_steps(self, playbook: Dict[str, Any]) -> List[str]:
        """Extrai passos de execução do playbook."""
        steps = []
        for step in playbook.get("steps", []):
            if isinstance(step, dict):
                title = step.get("title", "Unknown step")
                steps.append(title)
            else:
                steps.append(str(step))
        return steps
    
    def approve_playbook(
        self,
        playbook_id: str,
        approved_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """Aprova um playbook gerado."""
        if not self.playbook_store.connected:
            logger.warning("Playbook store not connected")
            return False
        
        success = self.playbook_store.approve_playbook(
            playbook_id=playbook_id,
            approved_by=approved_by,
            notes=notes
        )
        
        if success:
            self.cache.clear()
            logger.info(f"Playbook approved and cache cleared: {playbook_id}")
        
        return success
    
    def reject_playbook(
        self,
        playbook_id: str,
        rejected_by: str,
        reason: str
    ) -> bool:
        """Rejeita um playbook gerado."""
        if not self.playbook_store.connected:
            logger.warning("Playbook store not connected")
            return False
        
        success = self.playbook_store.reject_playbook(
            playbook_id=playbook_id,
            rejected_by=rejected_by,
            reason=reason
        )
        
        if success:
            self.cache.clear()
            logger.info(f"Playbook rejected: {playbook_id}")
        
        return success
    
    def get_pending_playbooks(self) -> List[Dict[str, Any]]:
        """Retorna playbooks aguardando aprovação."""
        if not self.playbook_store.connected:
            return []
        
        return self.playbook_store.get_pending_review_playbooks()
    
    def get_status(self) -> dict:
        """Retorna status do agente."""
        return {
            "agent_id": self.agent_id,
            "playbook_store_connected": self.playbook_store.connected,
            "playbook_generator_connected": self.playbook_generator.llm_client is not None,
            "cache_size": len(self.cache)
        }
