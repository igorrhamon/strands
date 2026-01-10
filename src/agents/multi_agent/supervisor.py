"""
Supervisor Agent - Multi-agent orchestrator using Strands Agents SDK.

Implements the "Agent as Tool" pattern where specialized agents are wrapped
as tools and coordinated by a central supervisor.

Pipeline:
1. Supervisor receives raw alerts
2. Routes to Analyst (correlation + enrichment)
3. Routes to Judge (decision generation)
4. Routes to Reporter (report generation)
5. Returns final report to user

Supports GitHub Models via GITHUB_TOKEN environment variable.
"""

import logging
import json
from typing import Optional, Union, Any
from strands import Agent
from strands.models import Model

from src.agents.multi_agent.tools import analyst_agent, judge_agent, reporter_agent

logger = logging.getLogger(__name__)


def _process_with_rules_only(alerts: list[dict]) -> dict:
    """Fallback: Process alerts using rules-only mode (no LLM)."""
    try:
        logger.info("[SupervisorAgent] Falling back to rules-only mode")
        
        alerts_json = json.dumps(alerts)
        
        # Call agents directly without LLM
        analysis_json = analyst_agent(alerts_json)
        if isinstance(analysis_json, str):
            analysis_data = json.loads(analysis_json)
        else:
            analysis_data = analysis_json
        
        decisions_json = judge_agent(json.dumps(analysis_data))
        if isinstance(decisions_json, str):
            decisions_data = json.loads(decisions_json)
        else:
            decisions_data = decisions_json
        
        report_json = reporter_agent(json.dumps(decisions_data))
        if isinstance(report_json, str):
            return json.loads(report_json)
        return report_json
        
    except Exception as e:
        logger.error(f"[SupervisorAgent] Rules-only fallback failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": f"GitHub Models rate limited and rules fallback failed: {e}"
        }


class SupervisorAgent:
    """
    Multi-agent supervisor using Strands SDK.
    
    Coordinates specialized agents (Analyst, Judge, Reporter) to process
    alerts through a structured pipeline.
    
    Constitution Principles:
    - I: Human-in-the-Loop (final decisions require confirmation)
    - II: Determinismo (rules before LLM)
    - III: Controle de Aprendizado (embeddings after confirmation only)
    - IV: Rastreabilidade (full audit trail)
    """
    
    AGENT_NAME = "SupervisorAgent"
    VERSION = "2.0.0"  # Multi-agent version
    
    SUPERVISOR_SYSTEM_PROMPT = """
You are the Supervisor Agent for an intelligent alert decision system.
Your role is to coordinate specialized agents to process security alerts and generate recommendations.

You have access to three specialized agents:
1. analyst_agent: Correlates alerts, analyzes metrics, and retrieves semantic context
2. judge_agent: Evaluates enriched analysis and generates structured decisions
3. reporter_agent: Creates human-readable reports and summaries

Your workflow:
1. When given raw alerts, call analyst_agent with the alerts in JSON format
2. Take the analyst's output and pass it to judge_agent
3. Take the judge's decisions and pass them to reporter_agent
4. Return the final report to the user

Always maintain the following principles:
- Ensure alerts are properly formatted before analysis
- Handle errors gracefully - if one agent fails, report it clearly
- Provide clear audit trails showing which agent produced which insights
- Never skip steps in the pipeline
- Always return the final report from the reporter

Be concise and professional in your responses.
"""
    
    def __init__(self, model: Optional[Union[str, Model]] = None):
        """
        Initialize supervisor agent with Strands SDK.
        
        Args:
            model: LLM model to use. Can be:
                  - None: Uses ANTHROPIC_API_KEY from environment
                  - "github": Uses GitHubModels with GITHUB_TOKEN
                  - str: Model name (e.g., "claude-3-5-sonnet-20241022")
                  - Model instance: Custom Strands Model implementation
        """
        self._model = model
        
        # Resolve model
        resolved_model = None
        if model is None:
            # Default: use environment variable (Anthropic)
            resolved_model = None
        elif isinstance(model, str):
            if model.lower() == "github":
                # Use GitHub Models
                try:
                    from src.providers.github_models import GitHubModels
                    resolved_model = GitHubModels()
                    logger.info("[SupervisorAgent] Using GitHub Models provider")
                except Exception as e:
                    logger.error(f"[SupervisorAgent] Failed to initialize GitHub Models: {e}")
                    raise
            else:
                # Treat as model name string
                resolved_model = model
        elif isinstance(model, Model):
            resolved_model = model
        else:
            raise ValueError(f"Invalid model type: {type(model)}")
        
        # Create supervisor agent with tools
        try:
            self._supervisor = Agent(
                system_prompt=self.SUPERVISOR_SYSTEM_PROMPT,
                tools=[analyst_agent, judge_agent, reporter_agent],
                model=resolved_model,
            )
            logger.info(f"[{self.AGENT_NAME}] Initialized with tools: analyst, judge, reporter")
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Initialization failed: {e}")
            raise
    
    def process_alerts_async(self, alerts: list[dict]) -> Union[dict, Any]:
        """
        Process alerts through the multi-agent pipeline (async).
        
        Args:
            alerts: List of alert dictionaries
        
        Returns:
            Final report from reporter agent
        """
        try:
            logger.info(f"[{self.AGENT_NAME}] Processing {len(alerts)} alerts (async)")
            
            # Prepare input for supervisor
            alerts_json = json.dumps(alerts)
            prompt = f"""
Process these alerts through the complete pipeline:

Alerts (JSON):
{alerts_json}

Follow the workflow:
1. Call analyst_agent to correlate and enrich the alerts
2. Pass the analyst's output to judge_agent to generate decisions
3. Pass the judge's decisions to reporter_agent to generate the final report
4. Return the final report

Make sure each step completes successfully before proceeding to the next.
"""
            
            # Call supervisor agent
            result = self._supervisor(prompt)
            
            logger.info(f"[{self.AGENT_NAME}] Pipeline execution complete")
            
            # Extract report from agent response
            # The supervisor should return the reporter's output
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return {"status": "success", "raw_response": result}
            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for rate limit errors (429)
            if "429" in error_msg or "RateLimitReached" in error_msg or "rate" in error_msg.lower():
                logger.warning(f"[{self.AGENT_NAME}] GitHub Models rate limited: {e}")
                logger.info(f"[{self.AGENT_NAME}] Switching to rules-only mode")
                return _process_with_rules_only(alerts)
            
            # Check for authentication errors
            if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg.lower():
                logger.error(f"[{self.AGENT_NAME}] Authentication failed: {e}")
                logger.info(f"[{self.AGENT_NAME}] Switching to rules-only mode")
                return _process_with_rules_only(alerts)
            
            # Other errors
            logger.error(f"[{self.AGENT_NAME}] Error processing alerts: {e}", exc_info=True)
            logger.info(f"[{self.AGENT_NAME}] Switching to rules-only mode as fallback")
            return _process_with_rules_only(alerts)
    
    def process_alerts(self, alerts: list[dict]) -> Union[dict, Any]:
        """
        Process alerts through the multi-agent pipeline (sync wrapper).
        
        Args:
            alerts: List of alert dictionaries
        
        Returns:
            Final report from reporter agent
        """
        try:
            logger.info(f"[{self.AGENT_NAME}] Processing {len(alerts)} alerts (sync)")
            
            # Prepare input for supervisor
            alerts_json = json.dumps(alerts)
            prompt = f"""
Process these alerts through the complete pipeline:

Alerts (JSON):
{alerts_json}

Follow the workflow:
1. Call analyst_agent to correlate and enrich the alerts
2. Pass the analyst's output to judge_agent to generate decisions
3. Pass the judge's decisions to reporter_agent to generate the final report
4. Return the final report

Make sure each step completes successfully before proceeding to the next.
"""
            
            # Call supervisor agent
            result = self._supervisor(prompt)
            
            logger.info(f"[{self.AGENT_NAME}] Pipeline execution complete")
            
            # Extract report from agent response
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return {"status": "success", "raw_response": result}
            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for rate limit errors (429)
            if "429" in error_msg or "RateLimitReached" in error_msg or "rate" in error_msg.lower():
                logger.warning(f"[{self.AGENT_NAME}] GitHub Models rate limited: {e}")
                logger.info(f"[{self.AGENT_NAME}] Switching to rules-only mode")
                return _process_with_rules_only(alerts)
            
            # Check for authentication errors
            if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg.lower():
                logger.error(f"[{self.AGENT_NAME}] Authentication failed: {e}")
                logger.info(f"[{self.AGENT_NAME}] Switching to rules-only mode")
                return _process_with_rules_only(alerts)
            
            # Other errors
            logger.error(f"[{self.AGENT_NAME}] Error processing alerts: {e}", exc_info=True)
            logger.info(f"[{self.AGENT_NAME}] Switching to rules-only mode as fallback")
            return _process_with_rules_only(alerts)
    
    def explain_decision(self, cluster_id: str, decision: dict) -> str:
        """
        Ask supervisor to explain a specific decision in detail.
        
        Args:
            cluster_id: ID of alert cluster
            decision: Decision dictionary from judge agent
        
        Returns:
            Explanation text
        """
        try:
            prompt = f"""
Explain this decision in detail:

Cluster ID: {cluster_id}
Decision: {json.dumps(decision, indent=2)}

Provide:
1. Why this decision was made
2. What factors influenced it
3. What risks should be considered
4. Next steps for the operator
"""
            
            result = self._supervisor(prompt)
            return str(result)
            
        except Exception as e:
            logger.error(f"[{self.AGENT_NAME}] Explanation failed: {e}")
            return f"Error explaining decision: {e}"
