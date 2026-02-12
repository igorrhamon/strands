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
    Returns real data from Neo4j for the given decision ID.
    """
    if not repo:
        raise HTTPException(status_code=503, detail="Repository not available")
    
    try:
        # Get all incidents and find the one matching incident_id
        # Note: incident_id here is actually the decision_id from DecisionCandidate
        all_incidents = repo.get_all_incidents()
        
        # Find matching incident by decision_id
        matching_incident = None
        for inc in all_incidents:
            if inc["decision_id"] == incident_id:
                matching_incident = dict(inc)  # Make a copy
                break
        
        if matching_incident is None:
            # Return basic structure as fallback
            matching_incident = {
                "decision_id": incident_id,
                "summary": f"Unknown Decision {incident_id}",
                "severity": "unknown",
                "created_at": "",
                "status": "PENDING",
                "execution_count": 0
            }
        
        # Get timeline for this decision (use decision_id, not incident_id)
        decision_id = matching_incident.get("decision_id", incident_id)
        timeline_data = repo.get_incident_timeline(decision_id) or {}
        
        # Handle created_at serialization
        created_at = matching_incident.get('created_at')
        if hasattr(created_at, 'iso_format'):
            created_at_str = created_at.iso_format()
        else:
            created_at_str = str(created_at)
        
        # Ensure all fields from incident are strings or numbers (JSON serializable)
        incident_data = {
            "id": str(incident_id),
            "alert_name": str(matching_incident.get("summary", ""))[:100],
            "title": f"Incidente #{incident_id}",
            "status": str(matching_incident.get("status", "PENDING")),
            "status_badge_color": "blue-500",
            "created_at": created_at_str,
            "trigger": str(matching_incident.get("summary", ""))[:100],
            "trigger_source": str(matching_incident.get("severity", "unknown")),
            
            # Swarm metrics
            "confidence": 0.5,  # TODO: Get from decision data
            "swarm_confidence": 50.0,
            "confidence_trend": "+0",
            "active_agents": int(len(timeline_data.get("executions", [])) or 0),
            "total_agents": 8,
            "execution_count": int(timeline_data.get("total_executions", 0) or 0),
            "elapsed_time_ms": "N/A",
            "estimated_cost": "$0.01",
            
            # Summary from decision
            "summary": str(matching_incident.get("full_summary", ""))[:500],
            "action_proposed": "manual_review",
            "automation_level": "PARTIAL",
            
            # Execution timeline and agents
            "executions": timeline_data.get("executions", []),
            "agents": timeline_data.get("agents", []),  # List of agents that executed
            "severity": str(matching_incident.get("severity", "warning")),
        }
        
        return incident_data
    
    except Exception as e:
        logger.error(f"Error fetching incident {incident_id}: {e}", exc_info=True)
        # Return error response
        return {
            "id": incident_id,
            "alert_name": "Error",
            "title": f"Erro ao carregar incidente {incident_id}",
            "status": "ERROR",
            "status_badge_color": "red-500",
            "created_at": "",
            "trigger": str(e),
            "severity": "critical",
            "confidence": 0,
            "swarm_confidence": 0,
            "execution_count": 0,
            "executions": [],
            "action_proposed": "manual_review"
        }


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
        # Transform the response to use "id" instead of "decision_id" for frontend compatibility
        # Also serialize DateTime objects
        transformed_incidents = []
        for inc in incidents:
            # Handle Neo4j DateTime object serialization
            created_at = inc.get('created_at')
            if hasattr(created_at, 'iso_format'):
                created_at_str = created_at.iso_format()
            else:
                created_at_str = str(created_at)
            
            transformed_incidents.append({
                "id": inc.get("decision_id"),  # Use decision_id as the incident id
                "alert_name": inc.get("summary", "")[:50] + "...",
                "severity": inc.get("severity", "unknown"),
                "created_at": created_at_str,
                "status": inc.get("status", "PROPOSED"),
                "action_proposed": "manual_review",
                "confidence": 0.5,  # TODO: Get from decision
                "decision_summary": inc.get("full_summary", ""),
                "execution_count": inc.get("execution_count", 0)
            })
        return transformed_incidents
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