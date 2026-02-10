"""
Recommender Agent com Aprendizado Autônomo

Versão que integra:
- Busca de playbooks conhecidos (Neo4j)
- Geração de novos playbooks (LLM)
- Workflow de curação (aprovação humana)
"""

import logging
import uuid
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
    3. Se encontrar, usa imediatamente
    4. Se não encontrar, gera novo playbook via LLM
    5. Armazena como PENDING_REVIEW
    6. Humano aprova/rejeita
    7. Próxima vez, playbook aprovado é reutilizado
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
    
    def recommend(
        self,
        correlation_result: SwarmResult,
        alert_fingerprint: str
    ) -> Dict[str, Any]:
        """
        Recomenda ações baseado em correlação.
        
        Fluxo híbrido:
        1. Buscar playbook ACTIVE no Neo4j
        2. Se não encontrar, gerar via LLM
        3. Retornar recomendação com playbook
        """
        decision_id = str(uuid.uuid4())
        
        logger.info(f"[{self.agent_id}] Recomendando ações para {alert_fingerprint} (decision_id: {decision_id})")
        
        try:
            # Extrair tipo de padrão da correlação
            pattern_type = self._extract_pattern_type(correlation_result.hypothesis)
            service_name = self._extract_service_name(correlation_result.evidence)
            
            # 1️⃣ BUSCAR PLAYBOOK CONHECIDO
            playbook = self._lookup_active_playbook(pattern_type, service_name)
            
            if playbook:
                logger.info(f"Found active playbook: {playbook.get('playbook_id')}")
                return self._build_recommendation(
                    decision_id=decision_id,
                    playbook=playbook,
                    source="KNOWN",
                    correlation_result=correlation_result
                )
            
            # 2️⃣ GERAR NOVO PLAYBOOK VIA LLM
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
                return self._build_recommendation(
                    decision_id=decision_id,
                    playbook=self._playbook_to_dict(generated_playbook),
                    source="GENERATED",
                    correlation_result=correlation_result,
                    requires_approval=True
                )
            
            # 3️⃣ FALLBACK: Usar ações sugeridas do correlator
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
    
    def _lookup_active_playbook(
        self,
        pattern_type: str,
        service_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Busca playbook ativo no Neo4j."""
        if not self.playbook_store.connected:
            logger.debug("Playbook store not connected")
            return None
        
        try:
            # Verificar cache local primeiro
            cache_key = f"{pattern_type}:{service_name}"
            if cache_key in self.cache:
                logger.debug(f"Using cached playbook: {cache_key}")
                return self.cache[cache_key]
            
            # Buscar no Neo4j
            playbooks = self.playbook_store.get_active_playbooks_for_pattern(
                pattern_type=pattern_type,
                service_name=service_name
            )
            
            if playbooks:
                # Usar playbook com maior taxa de sucesso
                best_playbook = max(
                    playbooks,
                    key=lambda p: self._calculate_playbook_score(p)
                )
                
                # Cachear
                self.cache[cache_key] = best_playbook
                
                return best_playbook
            
            return None
        
        except Exception as e:
            logger.error(f"Error looking up playbook: {e}")
            return None
    
    def _calculate_playbook_score(self, playbook: Dict[str, Any]) -> float:
        """Calcula score de um playbook."""
        executions = playbook.get("executions_count", 1)
        successes = playbook.get("success_count", 0)
        
        if executions == 0:
            return 0.0
        
        success_rate = successes / executions
        
        # Favorecer playbooks com mais execuções bem-sucedidas
        return success_rate * (1 + (executions / 100))
    
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
            # Tentar extrair do source_url
            for e in evidence:
                if hasattr(e, 'source_url') and e.source_url:
                    # Simples heurística
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
                "rollback_available": bool(playbook.get("rollback_procedure"))
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
            # Limpar cache
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
            # Limpar cache
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
