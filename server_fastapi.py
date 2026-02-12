import os
import logging
import sys
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import random
import time
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge

# Import configuration FIRST
try:
    from swarm_intelligence.config import get_config
    config = get_config()
except Exception as e:
    print(f"WARNING: Failed to load configuration: {e}", file=sys.stderr)
    # Provide a dummy config for tests if loading fails
    class DummyConfig:
        class API:
            log_level = "INFO"
            enable_cors = True
        api = API()
    config = DummyConfig()

# Import src modules
Neo4jRepository = None
HumanReviewAgent = None
_src_modules_available = False

try:
    from src.graph.neo4j_repo import Neo4jRepository
    _src_modules_available = True
except ImportError:
    logging.getLogger("server_startup").warning("Neo4j repository modules not available")

try:
    from src.agents.governance.human_review import HumanReviewAgent
except ImportError:
    logging.getLogger("server_startup").warning("Human review modules not available")

# Logging Setup
log_level = getattr(logging, config.api.log_level, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dashboard")

# App Setup
app = FastAPI(
    title="Strands Agents - Governance Dashboard",
    version="1.0.0",
    description="Multi-agent swarm intelligence with human-in-the-loop governance"
)

# CORS Configuration
if config.api.enable_cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

templates = Jinja2Templates(directory="templates")

# Mount static files
try:
    if not os.path.exists("static"):
        os.makedirs("static")
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Global references for demo
repo = None
human_review = None
swarm_coordinator = None # Will be populated if available

@app.on_event("startup")
async def startup_event():
    global repo, human_review
    if _src_modules_available and Neo4jRepository is not None:
        try:
            repo = Neo4jRepository()
            repo.connect()
            human_review = HumanReviewAgent(repo)
            logger.info("Neo4j repository initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Neo4j repository: {e}")

# --- Operational Console Endpoints ---

@app.get("/console", response_class=HTMLResponse)
async def get_console(request: Request):
    """Render the Operational Console."""
    return templates.TemplateResponse("console.html", {"request": request})

@app.get("/api/runs")
async def list_runs():
    """List all recent swarm runs."""
    if swarm_coordinator:
        return swarm_coordinator.get_all_runs()
    return []

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get details of a specific run."""
    if not swarm_coordinator:
        raise HTTPException(status_code=503, detail="Swarm Coordinator not available")
    run = swarm_coordinator.get_run_details(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run

@app.get("/api/runs/{run_id}/agents")
async def get_run_agents(run_id: str):
    if not swarm_coordinator: return []
    return swarm_coordinator.get_run_agents(run_id)

@app.get("/api/runs/{run_id}/confidence")
async def get_run_confidence(run_id: str):
    if not swarm_coordinator: return {}
    return swarm_coordinator.get_run_confidence(run_id)

@app.get("/api/runs/{run_id}/rag-evidence")
async def get_run_rag(run_id: str):
    if not swarm_coordinator: return []
    return swarm_coordinator.get_run_rag_evidence(run_id)

@app.get("/api/runs/{run_id}/retries")
async def get_run_retries(run_id: str):
    if not swarm_coordinator: return []
    return swarm_coordinator.get_run_retries(run_id)

# --- Legacy Dashboard Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    decisions = []
    if repo:
        try:
            decisions = repo.get_pending_decisions()
        except Exception as e:
            logger.error(f"Error fetching decisions: {e}")
    return templates.TemplateResponse("index.html", {"request": request, "decisions": decisions})

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/decisions")
async def api_decisions():
    """Return pending decisions as JSON for the dashboard frontend."""
    if not repo:
        return []
    try:
        decisions = repo.get_pending_decisions()
        # Ensure created_at is JSON-serializable (string)
        processed = []
        for d in decisions:
            item = dict(d)
            ca = item.get('created_at')
            try:
                if hasattr(ca, 'isoformat'):
                    item['created_at'] = ca.isoformat()
                else:
                    item['created_at'] = str(ca)
            except Exception:
                item['created_at'] = str(ca)
            processed.append(item)
        return processed
    except Exception as e:
        logger.error(f"Error fetching decisions for API: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch decisions")

@app.get("/api/incidents/{incident_id}")
async def get_incident_details(incident_id: str):
    """
    Return detailed execution data for a swarm incident.
    Maps decision data from Neo4j to timeline/execution format.
    """
    if not repo:
        raise HTTPException(status_code=503, detail="Repository not available")
    
    try:
        # Fetch all decisions; use first as "incident" representation
        decisions = repo.get_pending_decisions()
        
        if not decisions:
            raise HTTPException(status_code=404, detail="No decisions found")
        
        # Use first decision as the incident to display
        primary_decision = decisions[0]
        
        # Calculate swarm confidence from decision risk assessment
        risk_to_confidence = {
            "LOW": 0.95,
            "MEDIUM": 0.85,
            "HIGH": 0.65,
            "CRITICAL": 0.45
        }
        risk_level = primary_decision.get("risk_assessment", "MEDIUM").upper()
        swarm_confidence = risk_to_confidence.get(risk_level, 0.75)
        
        # Create mock agent execution data based on decision
        incident_data = {
            "incident_id": incident_id,
            "title": f"Incidente #{incident_id}",
            "status": "Executando",
            "status_badge_color": "blue-500",
            "created_at": primary_decision.get("created_at", datetime.now(timezone.utc).isoformat()),
            "trigger": "Webhook_Alerta_Lavagem_Dinheiro",
            "trigger_source": "ext_payment_gateway",
            
            # Swarm metrics
            "swarm_confidence": round(swarm_confidence * 100, 1),
            "confidence_trend": "+2.1",
            "active_agents": 2,
            "total_agents": 5,
            "elapsed_time_ms": random.randint(400, 500),
            "estimated_cost": f"${random.uniform(0.03, 0.05):.3f}",
            
            # Summary from decision
            "summary": primary_decision.get("summary", "")[:500],
            "hypothesis": primary_decision.get("primary_hypothesis", "Swarm Analysis Result"),
            "automation_level": primary_decision.get("automation_level", "PARTIAL"),
            
            # Timeline events (mock based on decision creation)
            "timeline_events": [
                {
                    "id": "event_1",
                    "title": "Ingestão de Alerta",
                    "icon": "input",
                    "color": "orange",
                    "timestamp": primary_decision.get("created_at"),
                    "details": {
                        "trigger": "Flag de Prevenção à Lavagem de Dinheiro (AML)",
                        "source": "ext_payment_gateway",
                        "payload_size": "2.4KB"
                    }
                },
                {
                    "id": "event_2",
                    "title": "Orquestração de Swarm",
                    "icon": "hub",
                    "color": "primary",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": {"agents": 2}
                },
                {
                    "id": "event_three",
                    "title": "Análise de Governança",
                    "icon": "verified_user",
                    "color": "green",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": {"status": "Em andamento"}
                }
            ],
            
            # Parallel execution paths
            "execution_paths": [
                {
                    "id": "path_a",
                    "label": "Caminho A",
                    "agent_name": "Sanctions Screener",
                    "agent_icon": "search_check",
                    "confidence": 98,
                    "status": "active",
                    "duration_ms": random.randint(100, 200),
                    "memory_mb": 128,
                    "model_version": "v4.2.0-beta",
                    "checks": ["Checagem_PEP", "Lista_OFAC"],
                    "input_params": {
                        "entity_id": "cust_8821",
                        "check_depth": "deep",
                        "sources": ["ofac", "eu_sanctions", "un_council"]
                    },
                    "output_flags": ["alto_risco", "correspondencia_encontrada"]
                },
                {
                    "id": "path_b",
                    "label": "Caminho B",
                    "agent_name": "Histórico de Transações",
                    "agent_icon": "history",
                    "confidence": 45,
                    "status": "pending",
                    "duration_ms": random.randint(150, 250),
                    "memory_mb": 96,
                    "model_version": "v3.9.0-stable",
                    "checks": ["Retroativo_30d"],
                    "input_params": {
                        "lookback_days": 30,
                        "min_transaction_amount": 10000
                    },
                    "output_flags": ["transacoes_suspeitas"]
                }
            ],
            
            # Artifacts/Evidence
            "artifacts": [
                {
                    "id": "artifact_1",
                    "name": "Relatorio_SAR_Final.pdf",
                    "type": "pdf",
                    "icon": "picture_as_pdf",
                    "size": "1.4MB",
                    "description": "Gerado via Template v2",
                    "color": "red"
                },
                {
                    "id": "artifact_2",
                    "name": "trilha_auditoria.json",
                    "type": "json",
                    "icon": "data_object",
                    "size": "42KB",
                    "description": "Grafo de causalidade completo",
                    "color": "yellow"
                }
            ],
            
            # Risk assessment from decision
            "risk_level": risk_level,
            "severity": primary_decision.get("severity", "warning")
        }
        
        return incident_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch incident details")


@app.get("/api/incidents")
async def list_incidents():
    """
    List all incidents (DecisionCandidate nodes) with execution count.
    Used by frontend incident selector dropdown.
    """
    if not repo:
        raise HTTPException(status_code=503, detail="Repository not available")
    
    try:
        incidents = repo.get_all_incidents()
        return incidents
    except Exception as e:
        logger.error(f"Error listing incidents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch incidents")


@app.get("/api/incidents/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str):
    """
    Get dynamic timeline of agent executions for an incident.
    Returns AgentExecution nodes linked to the DecisionCandidate.
    """
    if not repo:
        raise HTTPException(status_code=503, detail="Repository not available")
    
    try:
        timeline = repo.get_incident_timeline(incident_id)
        if timeline["total_executions"] == 0:
            logger.warning(f"No executions found for incident {incident_id}")
        return timeline
    except Exception as e:
        logger.error(f"Error fetching timeline for incident {incident_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch timeline")