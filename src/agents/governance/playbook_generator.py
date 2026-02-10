"""
Playbook Generator Agent - Gerar Playbooks via LLM

Usa LLM para gerar playbooks de remediação dinamicamente,
permitindo que o sistema aprenda e evolua com o tempo.
"""

import logging
import uuid
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import json

from strands import Agent
try:
    from http_provider import HTTPModel
except ImportError:
    # Handle cases where root is not in path but src is
    try:
        import sys
        import os
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
        from http_provider import HTTPModel
    except ImportError:
        logger.warning("Could not import HTTPModel from root. LLM generation may fail.")
        HTTPModel = None

from src.core.neo4j_playbook_store import (
    Neo4jPlaybookStore, Playbook, PlaybookStatus, PlaybookSource
)

logger = logging.getLogger(__name__)


class PlaybookGeneratorAgent:
    """
    Agente que gera playbooks usando LLM.
    
    Fluxo:
    1. Recebe padrão de correlação não reconhecido
    2. Consulta LLM para gerar playbook
    3. Armazena com status PENDING_REVIEW
    4. Aguarda aprovação humana
    5. Após aprovação, fica disponível para reutilização
    """
    
    agent_id = "playbook-generator"
    
    def __init__(self, playbook_store: Neo4jPlaybookStore, endpoint: Optional[str] = None):
        """Inicializa gerador de playbooks."""
        self.playbook_store = playbook_store
        self.endpoint = endpoint or os.environ.get("AGENT_MODEL_ENDPOINT", "http://localhost:8000/generate")
        self.llm_agent = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Inicializa agente LLM usando strands-agents."""
        try:
            model = HTTPModel(self.endpoint)
            self.llm_agent = Agent(self.agent_id, model)
            logger.info(f"LLM agent initialized with endpoint: {self.endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM agent: {e}")
    
    def generate_playbook(
        self,
        pattern_type: str,
        service_name: str,
        hypothesis: str,
        evidence: List[Dict[str, Any]],
        suggested_actions: List[str],
        correlation_data: Dict[str, Any]
    ) -> Optional[Playbook]:
        """
        Gera playbook usando LLM.
        
        Args:
            pattern_type: Tipo de padrão (LOG_METRIC, METRIC_METRIC, etc)
            service_name: Nome do serviço
            hypothesis: Hipótese da correlação
            evidence: Evidências coletadas
            suggested_actions: Ações sugeridas pelo correlator
            correlation_data: Dados de correlação (r, p-value, lag, etc)
        
        Returns:
            Playbook gerado ou None
        """
        try:
            # Construir prompt para LLM
            prompt = self._build_prompt(
                pattern_type,
                service_name,
                hypothesis,
                evidence,
                suggested_actions,
                correlation_data
            )
            
            # Chamar LLM
            playbook_data = self._call_llm(prompt)
            
            if not playbook_data:
                logger.warning(f"LLM failed to generate playbook for {pattern_type}")
                return None
            
            # Criar objeto Playbook
            playbook = Playbook(
                playbook_id=str(uuid.uuid4()),
                title=playbook_data.get("title", f"Playbook for {pattern_type}"),
                description=playbook_data.get("description", ""),
                pattern_type=pattern_type,
                service_name=service_name,
                status=PlaybookStatus.PENDING_REVIEW,
                source=PlaybookSource.LLM_GENERATED,
                steps=playbook_data.get("steps", []),
                estimated_time_minutes=playbook_data.get("estimated_time_minutes", 30),
                automation_level=playbook_data.get("automation_level", "MANUAL"),
                risk_level=playbook_data.get("risk_level", "MEDIUM"),
                prerequisites=playbook_data.get("prerequisites", []),
                success_criteria=playbook_data.get("success_criteria", []),
                rollback_procedure=playbook_data.get("rollback_procedure", ""),
                created_at=datetime.now(timezone.utc),
                created_by="llm-generator",
                updated_at=datetime.now(timezone.utc),
                updated_by=None,
                approved_at=None,
                approved_by=None,
                executions_count=0,
                success_count=0,
                failure_count=0,
                metadata={
                    "hypothesis": hypothesis,
                    "correlation_data": correlation_data,
                    "generated_from_evidence": len(evidence),
                    "llm_model": "gpt-4",
                    "generation_timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            # Armazenar playbook
            if self.playbook_store.store_playbook(playbook):
                logger.info(f"Playbook generated and stored: {playbook.playbook_id}")
                return playbook
            else:
                logger.error("Failed to store generated playbook")
                return None
        
        except Exception as e:
            logger.error(f"Error generating playbook: {e}", exc_info=True)
            return None
    
    def _build_prompt(
        self,
        pattern_type: str,
        service_name: str,
        hypothesis: str,
        evidence: List[Dict[str, Any]],
        suggested_actions: List[str],
        correlation_data: Dict[str, Any]
    ) -> str:
        """Constrói prompt para LLM."""
        evidence_text = "\n".join([
            f"- {e.get('description', 'Unknown evidence')}"
            for e in evidence
        ])
        
        actions_text = "\n".join([f"- {a}" for a in suggested_actions])
        
        prompt = f"""
You are an expert SRE/DevOps engineer. Generate a detailed remediation playbook based on the following incident analysis.

**Incident Pattern:** {pattern_type}
**Service:** {service_name}
**Hypothesis:** {hypothesis}

**Evidence Collected:**
{evidence_text}

**Suggested Actions:**
{actions_text}

**Correlation Data:**
- Correlation Coefficient: {correlation_data.get('correlation_coefficient', 'N/A')}
- P-Value: {correlation_data.get('p_value', 'N/A')}
- Lag Offset: {correlation_data.get('lag_offset', 0)}
- Significance: {correlation_data.get('significance', 'UNKNOWN')}

Generate a JSON response with the following structure:
{{
    "title": "Clear, descriptive title",
    "description": "Detailed description of the issue and remediation approach",
    "steps": [
        {{
            "step": 1,
            "title": "Step title",
            "description": "Detailed description",
            "commands": ["command1", "command2"],
            "expected_output": "What to expect",
            "rollback_command": "How to undo this step"
        }}
    ],
    "estimated_time_minutes": 30,
    "automation_level": "MANUAL|ASSISTED|FULL",
    "risk_level": "MINIMAL|LOW|MEDIUM|HIGH|CRITICAL",
    "prerequisites": ["Prerequisite 1", "Prerequisite 2"],
    "success_criteria": ["Criterion 1", "Criterion 2"],
    "rollback_procedure": "How to rollback the entire playbook",
    "notes": "Additional notes and considerations"
}}

Generate a practical, executable playbook that an SRE can follow step-by-step.
"""
        return prompt
    
    def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Chama LLM para gerar playbook via strands-agents.
        """
        try:
            if not self.llm_agent:
                logger.error("LLM agent not initialized")
                return None
            
            logger.info("Calling LLM to generate playbook...")
            response_text = self.llm_agent.think(prompt)
            
            if not response_text:
                logger.warning("LLM returned empty response")
                return None

            # Clean up markdown code blocks if present
            cleaned_text = response_text.strip()
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.debug(f"Raw response: {response_text}")
                # Tentativa de recuperação básica se o JSON estiver quase certo
                return None

        except Exception as e:
            logger.error(f"Error calling LLM: {e}", exc_info=True)
            return None
    
    def get_status(self) -> dict:
        """Retorna status do agente."""
        return {
            "agent_id": self.agent_id,
            "llm_connected": self.llm_agent is not None,
            "endpoint": self.endpoint
        }
