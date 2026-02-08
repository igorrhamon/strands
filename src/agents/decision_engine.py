"""
Decision Engine Agent - Orchestrator for Rules vs LLM

Generates structured recommendations using:
1. Deterministic rules (first)
2. LLM fallback (only if confidence < threshold)

Constitution Principle II: Determinismo - Rules BEFORE LLM.
"""

import logging
import json
from typing import Optional
from uuid import UUID

from src.models.cluster import AlertCluster
from src.models.metric_trend import MetricTrend
from src.models.decision import Decision, DecisionState, HumanValidationStatus, SemanticEvidence
from src.rules.decision_rules import RuleEngine, RuleResult
from src.providers.github_models import GitHubModels, MissingTokenError
from src.services.semantic_recovery_service import SemanticRecoveryService

logger = logging.getLogger(__name__)


class DecisionEngineError(Exception):
    """Raised when decision engine fails."""
    pass


class DecisionEngine:
    """
    Agent responsible for:
    1. Evaluating deterministic rules on alert context
    2. Invoking LLM fallback when confidence is low
    3. Producing structured Decision output
    
    Constitution Principle II: Rules execute BEFORE any LLM invocation.
    """
    
    AGENT_NAME = "DecisionEngine"
    TIMEOUT_SECONDS = 30.0
    
    # Threshold below which LLM is invoked
    LLM_FALLBACK_THRESHOLD = 0.60
    
    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
        llm_fallback_threshold: float = LLM_FALLBACK_THRESHOLD,
        llm_enabled: bool = True,
    ):
        """
        Initialize decision engine.
        
        Args:
            rule_engine: RuleEngine for deterministic evaluation.
            llm_fallback_threshold: Confidence below which LLM is invoked.
            llm_enabled: Whether LLM fallback is enabled.
        """
        self._rule_engine = rule_engine or RuleEngine(
            confidence_threshold=llm_fallback_threshold
        )
        self._llm_threshold = llm_fallback_threshold
        self._llm_enabled = llm_enabled
        self._semantic_recovery = SemanticRecoveryService(threshold=llm_fallback_threshold)
    
    async def decide(
        self,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
        semantic_evidence: list[SemanticEvidence],
    ) -> Decision:
        """
        Generate a decision for an alert cluster.
        
        Args:
            cluster: Alert cluster being analyzed.
            trends: Metric trends for enrichment.
            semantic_evidence: Historical context from RAG.
        
        Returns:
            Decision with recommendation and justification.
        """
        logger.info(
            f"[{self.AGENT_NAME}] Deciding for cluster {cluster.cluster_id} "
            f"({cluster.alert_count} alerts, {cluster.primary_severity} severity)"
        )
        
        # Step 1: Evaluate deterministic rules
        rule_result, fired_rules = self._rule_engine.evaluate(
            cluster=cluster,
            trends=trends,
            semantic_evidence=semantic_evidence,
        )
        
        logger.info(
            f"[{self.AGENT_NAME}] Rules result: {rule_result.decision_state.value} "
            f"(confidence: {rule_result.confidence:.2f}, rules: {fired_rules})"
        )
        
        # Step 2: Check if LLM fallback is needed
        llm_contribution = False
        llm_reason = None
        
        if (
            rule_result.confidence < self._llm_threshold
            and rule_result.decision_state != DecisionState.MANUAL_REVIEW
        ):
            # Try Semantic Recovery first
            semantic_result = await self._semantic_recovery.recover(cluster, rule_result.confidence)

            if semantic_result:
                logger.info(
                    f"[{self.AGENT_NAME}] [RECOVERY_TYPE:SEMANTIC] "
                    f"Successful recovery (confidence: {semantic_result.confidence:.2f})"
                )
                rule_result = semantic_result
                llm_contribution = False # It was semantic, not raw LLM
            elif self._llm_enabled:
                logger.info(
                    f"[{self.AGENT_NAME}] [RECOVERY_TYPE:LLM_FALLBACK] "
                    f"Confidence {rule_result.confidence:.2f} < {self._llm_threshold}, invoking LLM"
                )

                llm_result = await self._invoke_llm_fallback(
                    cluster=cluster,
                    trends=trends,
                    semantic_evidence=semantic_evidence,
                    rule_result=rule_result,
                )

                if llm_result:
                    rule_result = llm_result
                    llm_contribution = True
                    llm_reason = "Rule confidence below threshold"
        
        # Step 3: Create Decision object
        decision = Decision(
            decision_state=rule_result.decision_state,
            confidence=rule_result.confidence,
            justification=rule_result.justification,
            rules_applied=fired_rules,
            semantic_evidence=semantic_evidence,
            llm_contribution=llm_contribution,
            llm_reason=llm_reason,
        )
        
        logger.info(
            f"[{self.AGENT_NAME}] Decision: {decision.decision_state.value} "
            f"(confidence: {decision.confidence:.2f}, LLM: {llm_contribution})"
        )
        
        return decision
    
    async def _invoke_llm_fallback(
        self,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
        semantic_evidence: list[SemanticEvidence],
        rule_result: RuleResult,
    ) -> Optional[RuleResult]:
        """
        Invoke LLM for decision assistance.
        
        Constitution Principle II: LLM is only invoked after rules.
        
        Args:
            cluster: Alert cluster.
            trends: Metric trends.
            semantic_evidence: Historical context.
            rule_result: Result from rule evaluation.
        
        Returns:
            Enhanced RuleResult or None if LLM fails.
        """
        # Build context for LLM
        context = self._build_llm_context(
            cluster=cluster,
            trends=trends,
            semantic_evidence=semantic_evidence,
            rule_result=rule_result,
        )

        logger.info(f"[{self.AGENT_NAME}] LLM context: {len(context)} chars")

        # Compose prompt with instruction to return JSON
        system_prompt = (
            "You are an automated assistant that recommends an action for an alert.\n"
            "Return only a JSON object with fields: decision_state (CLOSE/OBSERVE/ESCALATE/MANUAL_REVIEW),"
            " confidence (float 0.0-1.0), justification (short string)."
        )

        user_prompt = context + "\n\nBased on the above, provide the JSON response as described."

        # Try to call GitHubModels provider; if not available, fall back to simulated reply
        try:
            gh = GitHubModels()
            # Use provider stream API to get assistant text
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            assistant_text = ""
            async for ev in gh.stream(messages):
                # collect deltas (provider yields a single event in current impl)
                cb = ev.get("contentBlockDelta", {})
                delta = cb.get("delta", {})
                text = delta.get("text") if isinstance(delta, dict) else None
                if text:
                    assistant_text += text

            # Attempt to parse JSON from assistant_text
            try:
                payload = json.loads(assistant_text)
                ds = payload.get("decision_state")
                conf = float(payload.get("confidence", 0.0))
                just = str(payload.get("justification", ""))

                # Validate decision_state
                if ds not in {s.value for s in DecisionState}:
                    raise ValueError(f"Invalid decision_state from LLM: {ds}")

                return RuleResult(
                    decision_state=DecisionState(ds),
                    confidence=conf,
                    rule_id="llm_fallback",
                    justification=f"LLM: {just}",
                )
            except Exception as e:
                logger.warning(f"[{self.AGENT_NAME}] Failed to parse LLM output: {e}; output: {assistant_text}")

        except MissingTokenError as me:
            logger.warning(f"[{self.AGENT_NAME}] GitHubModels token missing: {me}; using simulated LLM response")
        except Exception as e:
            logger.warning(f"[{self.AGENT_NAME}] GitHubModels call failed: {e}; using simulated LLM response")

        # Fallback simulated LLM behavior: recommend MANUAL_REVIEW with modest confidence
        return RuleResult(
            decision_state=DecisionState.MANUAL_REVIEW,
            confidence=0.70,
            rule_id="llm_fallback_simulated",
            justification=f"Simulated LLM analysis: {rule_result.justification}. Recommend manual review.",
        )
    
    def _build_llm_context(
        self,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
        semantic_evidence: list[SemanticEvidence],
        rule_result: RuleResult,
    ) -> str:
        """
        Build context string for LLM prompt.
        
        Args:
            cluster: Alert cluster.
            trends: Metric trends.
            semantic_evidence: Historical context.
            rule_result: Current rule result.
        
        Returns:
            Formatted context string.
        """
        parts = [
            "# Alert Cluster Analysis",
            "",
            "## Cluster Summary",
            f"- Service: {cluster.primary_service}",
            f"- Severity: {cluster.primary_severity}",
            f"- Alert Count: {cluster.alert_count}",
            f"- Correlation Score: {cluster.correlation_score:.2f}",
            "",
            "## Alert Descriptions",
        ]
        
        for alert in cluster.alerts[:5]:  # Limit to first 5
            parts.append(f"- {alert.description}")
        
        parts.extend([
            "",
            "## Metric Trends",
        ])
        
        for name, trend in trends.items():
            parts.append(f"- {name}: {trend.trend_state.value} (confidence: {trend.confidence:.2f})")
        
        parts.extend([
            "",
            "## Historical Evidence",
        ])
        
        if semantic_evidence:
            for evidence in semantic_evidence[:3]:  # Limit to first 3
                parts.append(f"- Score {evidence.similarity_score:.2f}: {evidence.summary}")
        else:
            parts.append("- No historical matches found")
        
        parts.extend([
            "",
            "## Rule Evaluation",
            f"- Result: {rule_result.decision_state.value if rule_result.decision_state else 'None'}",
            f"- Confidence: {rule_result.confidence:.2f}",
            f"- Rule: {rule_result.rule_id}",
            f"- Justification: {rule_result.justification}",
        ])
        
        return "\n".join(parts)
    
    def decide_sync(
        self,
        cluster: AlertCluster,
        trends: dict[str, MetricTrend],
        semantic_evidence: list[SemanticEvidence],
    ) -> Decision:
        """
        Synchronous version of decide() - rules only, no LLM.
        
        Useful for testing and when LLM is not available.
        """
        rule_result, fired_rules = self._rule_engine.evaluate(
            cluster=cluster,
            trends=trends,
            semantic_evidence=semantic_evidence,
        )
        
        return Decision(
            decision_state=rule_result.decision_state,
            confidence=rule_result.confidence,
            justification=rule_result.justification,
            rules_applied=fired_rules,
            semantic_evidence=semantic_evidence,
            llm_contribution=False,
        )


# Strands agent tool definition
DECISION_ENGINE_TOOL = {
    "name": "decision_engine",
    "description": "Generate decision recommendation for alert cluster",
    "parameters": {
        "type": "object",
        "properties": {
            "cluster_id": {
                "type": "string",
                "description": "ID of the cluster to decide on",
            },
            "service": {
                "type": "string",
                "description": "Service name",
            },
            "severity": {
                "type": "string",
                "description": "Alert severity",
            },
            "trends_summary": {
                "type": "object",
                "description": "Summary of metric trends",
            },
        },
        "required": ["service", "severity"],
    },
}


async def execute_decision_tool(
    service: str,
    severity: str,
) -> dict:
    """
    Tool execution function for Strands integration.
    
    Returns dict format expected by Strands agent framework.
    """
    from datetime import datetime, timezone
    from src.models.alert import NormalizedAlert, ValidationStatus
    from src.models.cluster import AlertCluster
    
    # Create minimal cluster
    mock_alert = NormalizedAlert(
        timestamp=datetime.now(timezone.utc),
        fingerprint="decision-tool",
        service=service,
        severity=severity,
        description=f"Alert for {service}",
        labels={},
        validation_status=ValidationStatus.VALID,
        validation_errors=None,
    )
    cluster = AlertCluster.from_alerts([mock_alert], correlation_score=1.0)
    
    engine = DecisionEngine()
    decision = await engine.decide(
        cluster=cluster,
        trends={},  # No trends for simple tool call
        semantic_evidence=[],  # No evidence for simple tool call
    )
    
    return {
        "decision_id": str(decision.decision_id),
        "decision_state": decision.decision_state.value,
        "confidence": decision.confidence,
        "justification": decision.justification,
        "rules_applied": decision.rules_applied,
        "llm_contribution": decision.llm_contribution,
    }
