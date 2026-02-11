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
