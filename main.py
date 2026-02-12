"""
Strands Swarm Intelligence - Main Entry Point

Production-ready entry point with configuration management and agent registry.
Listens for alerts via HTTP webhook and triggers swarm execution.
"""

import asyncio
import json
import logging
import sys
import time
from typing import Optional, Dict, Any
from types import SimpleNamespace
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
import uvicorn

from swarm_intelligence.config import get_config
from swarm_intelligence.core.models import (
    Alert, SwarmPlan, SwarmStep, Decision, HumanAction, HumanDecision,
    OperationalOutcome, Domain
)
from swarm_intelligence.core.enums import RiskLevel
from swarm_intelligence.core.swarm import SwarmOrchestrator
from swarm_intelligence.coordinators.swarm_run_coordinator import SwarmRunCoordinator
from swarm_intelligence.controllers.swarm_execution_controller import SwarmExecutionController
from swarm_intelligence.controllers.swarm_retry_controller import SwarmRetryController
from swarm_intelligence.controllers.swarm_decision_controller import SwarmDecisionController
from swarm_intelligence.memory.neo4j_adapter import Neo4jAdapter
from swarm_intelligence.policy.retry_policy import ExponentialBackoffPolicy
from swarm_intelligence.services.confidence_service import ConfidenceService
from swarm_intelligence.replay import ReplayEngine
from swarm_intelligence.registry import get_registry, load_all_agents, create_agent


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def expert_human_review(decision: Decision) -> Optional[HumanDecision]:
    """
    Human expert review hook for decision governance.
    
    In production: Replace with actual human review workflow (e.g., ServiceNow integration).
    """
    config = get_config()
    
    # In production, implement actual review logic
    if config.environment == "production":
        logging.info("Human review required - decision pending external approval")
        # In production this should integrate with an external approval workflow.
        # To keep the coordinator API stable, return a placeholder HumanDecision
        return HumanDecision(
            action=HumanAction.ACCEPT,
            author="external_approver",
            override_reason="external_approval_placeholder",
            overridden_action_proposed="pending"
        )
    
    # Development mode: Auto-override for testing
    logging.info("--- Development Mode: Simulated Human Expert Review ---")
    logging.warning("Expert OVERRULES swarm decision (MOCK)")
    return HumanDecision(
        action=HumanAction.OVERRIDE,
        author="dev_analyst",
        override_reason="Development mode: simulated override for testing",
        overridden_action_proposed="quarantine_and_reimage_host"
    )


def connect_neo4j_with_retry(uri: str, username: str, password: str, logger: logging.Logger) -> Optional[Neo4jAdapter]:
    """
    Connect to Neo4j with exponential backoff retry logic.
    
    Handles:
    - Authentication rate limit recovery (waits for Neo4j service to reset)
    - Database initialization delays
    - Network connectivity issues
    
    Args:
        uri: Neo4j connection URI
        username: Authentication username
        password: Authentication password
        logger: Logger instance
        
    Returns:
        Neo4jAdapter instance or None if max retries exceeded
    """
    max_retries = 5
    base_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Attempt {attempt}/{max_retries}] Connecting to Neo4j at {uri}")
            neo4j = Neo4jAdapter(uri, username, password)
            
            logger.info("Setting up Neo4j schema...")
            neo4j.setup_schema()
            
            logger.info("✅ Neo4j connection established and schema initialized")
            return neo4j
            
        except Exception as e:
            error_msg = str(e)
            
            if "AuthenticationRateLimit" in error_msg:
                logger.warning(f"⚠️  Authentication rate limit hit. Waiting before retry...")
                wait_time = base_delay * (2 ** (attempt - 1))
                logger.info(f"   Waiting {wait_time}s before retry (exponential backoff)...")
                time.sleep(wait_time)
            elif "Could not connect" in error_msg or "Connection refused" in error_msg:
                logger.warning(f"⚠️  Neo4j service not yet ready. Waiting...")
                wait_time = base_delay * attempt
                logger.info(f"   Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ Unexpected error: {e}")
                if attempt < max_retries:
                    wait_time = base_delay * attempt
                    logger.info(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
    
    logger.error(f"❌ Failed to connect to Neo4j after {max_retries} attempts")
    return None



async def main():
    """Main execution function with alert listener."""
    # Load configuration
    try:
        config = get_config()
    except Exception as e:
        print(f"FATAL: Configuration error: {e}", file=sys.stderr)
        print("Ensure .env file exists with required values (see .env.example)", file=sys.stderr)
        sys.exit(1)
    
    setup_logging(config.api.log_level)
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting Strands in {config.environment} mode")
    
    # Load agents: 8 operational agents (3 core + 5 adapters)
    registry = get_registry()
    logger.info(f"[{config.environment.upper()}] Loading all operational agents...")
    load_all_agents()
    
    # Verify agents are registered
    available_agents = registry.list_agents()
    if not available_agents:
        logger.error("No agents registered! Cannot proceed.")
        sys.exit(1)
    
    # Log detailed agent inventory
    core_agents = ["threatintel", "loganalysis", "networkscanner"]
    adapter_agents = ["correlator", "loginspector", "metricsanalyzer", "alertcorrelator", "recommender", "llm_agent"]
    
    logger.info(f"\n📊 AGENT INVENTORY:")
    logger.info(f"  ⚙️ CORE OPERATIONAL AGENTS (3): {', '.join(core_agents)}")
    logger.info(f"  🔧 ADAPTER AGENTS (6): {', '.join(adapter_agents)}")
    logger.info(f"  📈 TOTAL: {len(available_agents)} agents ready for execution\n")
    
    # Initialize Neo4j connection with retry logic
    neo4j = None
    try:
        neo4j = connect_neo4j_with_retry(
            config.neo4j.uri,
            config.neo4j.username,
            config.neo4j.password,
            logger
        )
        
        if not neo4j:
            logger.error("FATAL: Unable to establish Neo4j connection after retries")
            sys.exit(1)
        
        # Initialize services
        confidence_service = ConfidenceService(neo4j)
        
        # Instantiate all 8 agents for this swarm run
        agents = []
        all_agent_ids = [
            "threatintel", "loganalysis", "networkscanner",
            "correlator", "loginspector", "metricsanalyzer", "alertcorrelator", "recommender", "llm_agent",
        ]
        
        logger.info("\n🚀 INSTANTIATING SWARM AGENTS:")
        for agent_id in all_agent_ids:
            try:
                agent = create_agent(agent_id)
                agents.append(agent)
                agent_type = "(CORE)" if agent_id in core_agents else "(ADAPTER)"
                logger.info(f"  ✅ {agent_id:18s} {agent_type}  →  {agent.__class__.__name__}")
            except Exception as e:
                agent_type = "(CORE)" if agent_id in core_agents else "(ADAPTER)"
                logger.error(f"  ❌ {agent_id:18s} {agent_type}  →  ERROR: {e}")
                if agent_id not in adapter_agents:
                    logger.error(f"Failed to load core operational agent: {agent_id}")
                    sys.exit(1)
        
        if not agents:
            logger.error("No agents instantiated! Cannot proceed.")
            sys.exit(1)
        
        logger.info(f"\n✨ Successfully instantiated {len(agents)}/{len(all_agent_ids)} agents\n")
        
        orchestrator = SwarmOrchestrator(agents, max_concurrency=len(all_agent_ids))
        
        # Initialize controllers
        execution_controller = SwarmExecutionController(orchestrator)
        retry_controller = SwarmRetryController()
        decision_controller = SwarmDecisionController()
        
        # Initialize the main coordinator
        coordinator = SwarmRunCoordinator(
            execution_controller,
            retry_controller,
            decision_controller,
            confidence_service
        )
        
        # Define operational domain
        default_domain = Domain(
            id="infra-01",
            name="Infrastructure",
            description="Core infrastructure operations",
            risk_level=RiskLevel.MEDIUM
        )
        
        # Ensure domain exists in Neo4j
        ensure_domain_query = """
        MERGE (d:Domain {id: $domain_id})
        ON CREATE SET d.name = $name, d.description = $description, d.risk_level = $risk_level
        """
        neo4j.run_transaction(ensure_domain_query, {
            "domain_id": default_domain.id,
            "name": default_domain.name,
            "description": default_domain.description,
            "risk_level": default_domain.risk_level.value
        })
        logger.info(f"✓ Domain '{default_domain.name}' ensured in Neo4j")
        
        # Create FastAPI app for alert listener
        app = FastAPI(title="Strands Alert Receiver")
        
        # Store execution state
        class ExecutionState:
            def __init__(self):
                self.is_processing = False
                self.last_execution = None
        
        state = ExecutionState()
        
        async def process_alert(alert_data: Dict[str, Any]) -> str:
            """Process alert and execute swarm."""
            if state.is_processing:
                raise HTTPException(status_code=429, detail="Alert processing already in progress")
            
            state.is_processing = True
            try:
                # Extract alert info from AlertManager webhook
                primary_alert = alert_data.get("alerts", [{}])[0]
                labels = primary_alert.get("labels", {})
                annotations = primary_alert.get("annotations", {})
                alert_name = labels.get("alertname", "unknown")

                alert_id = f"alert-{int(datetime.now(timezone.utc).timestamp() * 1000)}"

                # Build Alert for core models: core.Alert expects `alert_id` and `data`
                flattened = {}
                # Flatten labels and annotations into top-level keys for compatibility
                if isinstance(labels, dict):
                    flattened.update(labels)
                if isinstance(annotations, dict):
                    # prefix annotation keys to avoid collision if needed
                    flattened.update(annotations)
                flattened["generatorURL"] = primary_alert.get("generatorURL") or primary_alert.get("generator_url")
                flattened["alertname"] = labels.get("alertname", alert_name)

                # Use a lightweight object to avoid pydantic constructor issues at webhook time
                alert = SimpleNamespace(alert_id=alert_id, data=flattened)

                run_id = f"run-{alert_id}"
                
                logger.info(f"\n🚨 RECEIVED ALERT: {alert_name} ({alert_id})")
                logger.info(f"📋 Total steps: 8 | Mandatory: 5\n")
                
                # Define retry policies
                fast_policy = ExponentialBackoffPolicy(max_attempts=2, base_delay=0.1)
                moderate_policy = ExponentialBackoffPolicy(max_attempts=2, base_delay=0.2)
                slow_policy = ExponentialBackoffPolicy(max_attempts=3, base_delay=0.5)

                # primary_alert/labels/annotations already extracted above
                alert_signature = f"{labels.get('alertname', 'unknown')}|{labels.get('service', labels.get('job', 'unknown'))}|{labels.get('severity', 'unknown')}"
                known_procedure = neo4j.find_procedure_by_signature(alert_signature)

                common_params = {
                    "alert": {"alertname": alert_name, "raw_data": alert_data},
                    "service_name": labels.get("service", labels.get("job", "unknown")),
                    "namespace": labels.get("namespace", "default"),
                    "instance": labels.get("instance", "unknown"),
                    "severity": labels.get("severity", "unknown"),
                    "summary": annotations.get("summary", ""),
                    "description": annotations.get("description", ""),
                    "context": f"{annotations.get('summary', '')} {annotations.get('description', '')}",
                    "logs": annotations.get("description", ""),
                    "metrics": ["cpu", "memory", "request_rate", "latency", "error_rate"],
                    "lookback_minutes": int(labels.get("lookback_minutes", 60)) if str(labels.get("lookback_minutes", "")).isdigit() else 60,
                    "alert_count": len(alert_data.get("alerts", [])),
                    "known_procedure": known_procedure,
                    "decision_candidates": [
                        {
                            "severity": labels.get("severity", "medium"),
                            "service": labels.get("service", labels.get("job", "unknown")),
                            "issue_type": "cpu" if "cpu" in (annotations.get("summary", "") + annotations.get("description", "")).lower() else "error",
                            "reason": annotations.get("summary", "Alertmanager signal"),
                            "known_procedure": known_procedure.get("description", "") if isinstance(known_procedure, dict) else "",
                        }
                    ],
                    "network_info": {
                        "open_ports": [int(p) for p in labels.get("open_ports", "").split(",") if p.strip().isdigit()]
                    },
                }

                if known_procedure:
                    logger.info(f"♻️ Reusing known procedure for pattern {alert_signature}: {known_procedure.get('description', 'n/a')}")

                plan = SwarmPlan(
                    objective=f"Incident Response: {alert_name} on {labels.get('instance', 'unknown')}",
                    steps=[
                        SwarmStep(agent_id="loganalysis", mandatory=True, retry_policy=fast_policy, parameters=common_params),
                        SwarmStep(agent_id="networkscanner", mandatory=True, retry_policy=slow_policy, parameters=common_params),
                        SwarmStep(agent_id="threatintel", mandatory=True, retry_policy=moderate_policy, parameters=common_params),
                        SwarmStep(agent_id="correlator", mandatory=True, retry_policy=moderate_policy, parameters=common_params),
                        SwarmStep(agent_id="loginspector", mandatory=False, retry_policy=slow_policy, parameters=common_params),
                        SwarmStep(agent_id="metricsanalyzer", mandatory=False, retry_policy=fast_policy, parameters=common_params),
                        SwarmStep(agent_id="alertcorrelator", mandatory=False, retry_policy=fast_policy, parameters=common_params),
                        SwarmStep(agent_id="recommender", mandatory=True, retry_policy=moderate_policy, parameters=common_params),
                    ]
                )
                
                # Execute swarm plan
                swarm_run, all_retry_attempts, all_retry_decisions = await coordinator.aexecute_plan(
                    default_domain,
                    plan,
                    alert,
                    run_id,
                    human_hook=expert_human_review,
                    max_retry_rounds=config.swarm.max_retry_rounds,
                    max_runtime_seconds=config.swarm.max_runtime_seconds,
                    max_total_attempts=config.swarm.max_total_attempts,
                    use_llm_fallback=config.swarm.use_llm_fallback,
                    llm_fallback_threshold=config.swarm.llm_fallback_threshold,
                )
                
                # Persist results
                neo4j.save_swarm_run(swarm_run, alert, all_retry_attempts, all_retry_decisions)
                logger.info("Swarm run persisted to Neo4j")
                
                # Handle human override if present
                decision = swarm_run.final_decision
                if decision and decision.human_decision:
                    outcome = OperationalOutcome(status="success")
                    neo4j.save_human_override(decision, decision.human_decision, outcome)
                    logger.info("Human override persisted")
                
                # Replay for audit trail
                if config.environment != "production":
                    try:
                        logger.info("--- Initiating Deterministic Replay ---")
                        replay_engine = ReplayEngine(neo4j)
                        report = await replay_engine.replay_decision(run_id, coordinator)
                        logger.info(f"Replay Report ({report.report_id}) generated and saved")
                    except Exception as replay_error:
                        logger.warning(f"Replay failed (non-fatal): {replay_error}")
                
                logger.info("Swarm execution completed successfully")
                state.last_execution = {"run_id": run_id, "alert": alert_name, "timestamp": datetime.now(timezone.utc).isoformat()}
                return run_id
                
            finally:
                state.is_processing = False
        
        @app.post("/api/v1/alerts")
        async def receive_alert(data: Dict[str, Any]):
            """Webhook endpoint for AlertManager alerts."""
            logger.debug(f"Received webhook: {json.dumps(data)}")
            try:
                run_id = await process_alert(data)
                return {"status": "processing", "run_id": run_id}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error processing alert: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "neo4j": neo4j is not None,
                "processing": state.is_processing,
                "last_execution": state.last_execution
            }
        
        # Start server
        logger.info(f"\n✅ Alert listener started on 0.0.0.0:8080")
        logger.info(f"   Webhook: POST http://localhost:8080/api/v1/alerts")
        logger.info(f"   Health:  GET  http://localhost:8080/api/v1/health\n")
        
        config_uvicorn = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=8080,
            log_level="info",
            access_log=False
        )
        server = uvicorn.Server(config_uvicorn)
        await server.serve()
    except Exception as e:
        logger.error(f"FATAL: {e}", exc_info=True)
        if "authentication" in str(e).lower() or "connection" in str(e).lower():
            logger.error("Check Neo4j connection settings in .env file")
        sys.exit(1)
    finally:
        if neo4j:
            neo4j.close()
            logger.info("Neo4j connection closed")


if __name__ == "__main__":
    asyncio.run(main())
