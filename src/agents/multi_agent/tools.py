"""
Specialized agents wrapped as Strands tools for multi-agent pipeline.

Each tool wraps an existing agent and exposes it as a callable for the supervisor.
"""

import logging
import json
from typing import Optional, Dict, Any
from strands.tools import tool

from src.models.cluster import AlertCluster
from src.models.alert import Alert
from src.agents.alert_correlation import AlertCorrelationAgent
from src.agents.metrics_analysis import MetricsAnalysisAgent
from src.agents.repository_context import RepositoryContextAgent
from src.agents.decision_engine import DecisionEngine

logger = logging.getLogger(__name__)


@tool
def analyst_agent(alerts_json: str) -> str:
    """
    Analyst Agent: Correlates and enriches alerts with metrics and context.
    
    Performs:
    1. Alert correlation into clusters
    2. Metrics trend analysis
    3. Semantic context retrieval (RAG)
    
    Args:
        alerts_json: JSON string of Alert objects
    
    Returns:
        JSON string with analysis results (clusters + enrichment data)
    """
    try:
        logger.info("[Analyst] Processing alerts...")
        
        # Parse input
        alerts_data = json.loads(alerts_json)
        if not isinstance(alerts_data, list):
            alerts_data = [alerts_data]
        
        # Convert to Alert objects
        alerts = [Alert(**alert) for alert in alerts_data]
        
        # Step 1: Correlate
        correlation_agent = AlertCorrelationAgent()
        clusters = correlation_agent.correlate_existing(alerts)
        logger.info(f"[Analyst] Created {len(clusters)} clusters")
        
        # Step 2: Analyze metrics for each cluster
        metrics_agent = MetricsAnalysisAgent()
        enriched_clusters = []
        for cluster in clusters:
            try:
                trends = metrics_agent.analyze_cluster_sync(cluster)
                enriched_clusters.append({
                    "cluster_id": str(cluster.cluster_id),
                    "alert_count": cluster.alert_count,
                    "service": cluster.primary_service,
                    "severity": cluster.primary_severity,
                    "trends": {k: v.model_dump() for k, v in trends.items()} if isinstance(trends, dict) else {}
                })
            except Exception as e:
                logger.warning(f"[Analyst] Metrics analysis failed for cluster {cluster.cluster_id}: {e}")
                enriched_clusters.append({
                    "cluster_id": str(cluster.cluster_id),
                    "alert_count": cluster.alert_count,
                    "service": cluster.primary_service,
                    "severity": cluster.primary_severity,
                    "trends": {}
                })
        
        # Step 3: Get semantic context
        context_agent = RepositoryContextAgent()
        for enriched in enriched_clusters:
            try:
                cluster = next(c for c in clusters if str(c.cluster_id) == enriched["cluster_id"])
                context = context_agent.get_context_sync(cluster)
                enriched["semantic_evidence"] = context.get("semantic_evidence", [])
            except Exception as e:
                logger.warning(f"[Analyst] Context retrieval failed: {e}")
                enriched["semantic_evidence"] = []
        
        result = {
            "status": "success",
            "cluster_count": len(enriched_clusters),
            "clusters": enriched_clusters
        }
        
        logger.info(f"[Analyst] Analysis complete: {len(enriched_clusters)} enriched clusters")
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"[Analyst] Error: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e)
        })


@tool
def judge_agent(analysis_json: str) -> str:
    """
    Judge Agent: Generates structured decision recommendations.
    
    Takes enriched cluster analysis and produces:
    1. Decision state (CLOSE, OBSERVE, ESCALATE, MANUAL_REVIEW)
    2. Confidence score
    3. Rules applied
    4. Recommended action
    
    Args:
        analysis_json: JSON string from analyst_agent output
    
    Returns:
        JSON string with decisions for each cluster
    """
    try:
        logger.info("[Judge] Evaluating analysis...")
        
        # Parse input
        analysis = json.loads(analysis_json)
        if analysis.get("status") != "success":
            return json.dumps({
                "status": "error",
                "error": "Analyst failed, cannot proceed"
            })
        
        # Initialize decision engine
        decision_engine = DecisionEngine(llm_enabled=False)
        
        # Generate decisions
        decisions = []
        for cluster_data in analysis.get("clusters", []):
            try:
                # Reconstruct enough data for decision engine
                # In a full implementation, we'd deserialize the full cluster object
                decision = {
                    "cluster_id": cluster_data["cluster_id"],
                    "service": cluster_data["service"],
                    "severity": cluster_data["severity"],
                    "alert_count": cluster_data["alert_count"],
                    "trends": cluster_data.get("trends", {}),
                    "semantic_evidence": cluster_data.get("semantic_evidence", []),
                }
                
                # Apply decision rules (simplified for demo)
                alert_count = cluster_data.get("alert_count", 0)
                trend_count = len(cluster_data.get("trends", {}))
                severity = cluster_data.get("severity", "unknown")
                
                if severity == "critical" and alert_count > 5:
                    recommendation = "ESCALATE"
                    confidence = 0.95
                elif trend_count > 0 and alert_count > 0:
                    recommendation = "OBSERVE"
                    confidence = 0.80
                else:
                    recommendation = "MANUAL_REVIEW"
                    confidence = 0.60
                
                decision["recommendation"] = {
                    "action": recommendation,
                    "confidence": confidence,
                    "reasoning": f"Service {cluster_data['service']}: {alert_count} alerts, {trend_count} metric trends"
                }
                
                decisions.append(decision)
                logger.info(f"[Judge] Decision for {cluster_data['cluster_id']}: {recommendation} ({confidence})")
                
            except Exception as e:
                logger.warning(f"[Judge] Decision generation failed for cluster: {e}")
                decisions.append({
                    "cluster_id": cluster_data.get("cluster_id", "unknown"),
                    "recommendation": {
                        "action": "MANUAL_REVIEW",
                        "confidence": 0.0,
                        "reasoning": f"Error during evaluation: {str(e)}"
                    }
                })
        
        result = {
            "status": "success",
            "decision_count": len(decisions),
            "decisions": decisions
        }
        
        logger.info(f"[Judge] Evaluation complete: {len(decisions)} decisions")
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"[Judge] Error: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e)
        })


@tool
def reporter_agent(decisions_json: str) -> str:
    """
    Reporter Agent: Generates human-readable reports and summaries.
    
    Produces:
    1. Executive summary
    2. Per-cluster detailed reports
    3. Audit trail for confirmations
    4. Recommended next steps
    
    Args:
        decisions_json: JSON string from judge_agent output
    
    Returns:
        JSON string with formatted report
    """
    try:
        logger.info("[Reporter] Generating report...")
        
        # Parse input
        decisions_data = json.loads(decisions_json)
        if decisions_data.get("status") != "success":
            return json.dumps({
                "status": "error",
                "error": "Judge failed, cannot generate report"
            })
        
        decisions = decisions_data.get("decisions", [])
        
        # Generate summary
        escalate_count = sum(1 for d in decisions if d.get("recommendation", {}).get("action") == "ESCALATE")
        observe_count = sum(1 for d in decisions if d.get("recommendation", {}).get("action") == "OBSERVE")
        review_count = sum(1 for d in decisions if d.get("recommendation", {}).get("action") == "MANUAL_REVIEW")
        
        report = {
            "status": "success",
            "report_type": "alert_decision_summary",
            "summary": {
                "total_clusters": len(decisions),
                "escalate": escalate_count,
                "observe": observe_count,
                "manual_review": review_count,
                "next_steps": []
            },
            "cluster_reports": []
        }
        
        # Generate next steps
        if escalate_count > 0:
            report["summary"]["next_steps"].append(
                f"URGENT: {escalate_count} cluster(s) require immediate escalation to on-call team"
            )
        if review_count > 0:
            report["summary"]["next_steps"].append(
                f"ACTION: {review_count} cluster(s) require manual human review"
            )
        if observe_count > 0:
            report["summary"]["next_steps"].append(
                f"INFO: {observe_count} cluster(s) are stable, continue monitoring"
            )
        
        # Detailed cluster reports
        for decision in decisions:
            cluster_report = {
                "cluster_id": decision.get("cluster_id"),
                "service": decision.get("service"),
                "severity": decision.get("severity"),
                "alert_count": decision.get("alert_count"),
                "recommendation": decision.get("recommendation", {}),
                "details": {
                    "metric_trends": len(decision.get("trends", {})),
                    "semantic_matches": len(decision.get("semantic_evidence", []))
                }
            }
            report["cluster_reports"].append(cluster_report)
        
        logger.info(f"[Reporter] Report generated: {escalate_count} escalate, {observe_count} observe, {review_count} review")
        return json.dumps(report)
        
    except Exception as e:
        logger.error(f"[Reporter] Error: {e}", exc_info=True)
        return json.dumps({
            "status": "error",
            "error": str(e)
        })
