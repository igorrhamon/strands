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
import time
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge

# Import configuration FIRST, before any other src imports
try:
    from swarm_intelligence.config import get_config
    config = get_config()
except Exception as e:
    print(f"FATAL: Failed to load configuration: {e}", file=sys.stderr)
    print("Ensure .env file exists with required values (see .env.example)", file=sys.stderr)
    sys.exit(1)

# Now import src modules with error handling - each independently
Neo4jRepository = None
HumanReviewAgent = None
DecisionValidation = None
_src_modules_available = False

try:
    from src.graph.neo4j_repo import Neo4jRepository
    _src_modules_available = True
except ImportError as e:
    logging.getLogger("server_startup").warning(f"Neo4j repository modules not available - some features will be disabled")

try:
    from src.agents.governance.human_review import HumanReviewAgent
except ImportError as e:
    logging.getLogger("server_startup").warning(f"Human review modules not available - governance features disabled")

try:
    from src.models.decision import DecisionValidation
except ImportError as e:
    logging.getLogger("server_startup").warning(f"Decision validation modules not available")

# Logging Setup
log_level = getattr(logging, config.api.log_level, logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("dashboard")
logger.info(f"Starting server in {config.environment} mode")
logger.info("✅ Server imports successfully")

# Prometheus Metrics
PAYMENT_SERVICE_CPU = Gauge('payment_service_cpu_usage', 'CPU usage of payment service')
DB_CPU = Gauge('db_cpu_usage', 'CPU usage of database')
# Simulated additional metrics for demo
PAYMENT_SERVICE_MEMORY = Gauge('payment_service_memory_usage', 'Memory usage of payment service')
PAYMENT_SERVICE_REQUEST_RATE = Gauge('payment_service_request_rate_usage', 'Request rate of payment service')

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
        allow_origins=["*"],  # In production, specify allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS enabled for all origins")

templates = Jinja2Templates(directory="templates")

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Dependencies (Global for demo simplicity)
# In production, use dependency injection
repo = None
human_review = None

if _src_modules_available and Neo4jRepository is not None:
    try:
        repo = Neo4jRepository()
        human_review = HumanReviewAgent(repo)
        logger.info("Neo4j repository initialized")
    except Exception as e:
        logger.warning(f"Could not initialize Neo4j repository: {e}")
        repo = None
        human_review = None
else:
    logger.warning("Neo4j repository modules not available - some features will be disabled")

# Request Models
class ReviewRequest(BaseModel):
    decision_id: str
    is_approved: bool
    feedback: Optional[str] = None
    validated_by: str

class GenerateRequest(BaseModel):
    prompt: str

@app.on_event("startup")
async def startup_event():
    """Initialize application services on startup."""
    if repo is None:
        logger.warning("Neo4j repository not initialized at startup")
        return
    
    try:
        repo.connect()
        logger.info(f"Connected to Neo4j at {config.neo4j.uri}")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        if config.environment == "production":
            # In production, fail fast if critical services are unavailable
            raise
        logger.warning("Dashboard will run with limited functionality")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    if repo is None:
        return
    
    try:
        repo.close()
        logger.info("Neo4j connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# --- Health Check Endpoints ---

@app.get("/health")
async def health_check() -> JSONResponse:
    """Basic health check - returns OK if the service is running."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "environment": config.environment,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.get("/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness check - verifies that all dependent services are available.
    Returns 200 if ready, 503 if not ready.
    """
    checks: Dict[str, Any] = {
        "neo4j": "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    # Check Neo4j connection if available
    if repo is None:
        checks["neo4j"] = "unavailable (modules not loaded)"
        return JSONResponse(
            status_code=200,  # Still ready, just without Neo4j
            content={
                "status": "ready_degraded",
                "checks": checks
            }
        )
    
    try:
        repo.get_pending_decisions()  # Simple query to verify connectivity
        checks["neo4j"] = "healthy"
    except Exception as e:
        checks["neo4j"] = f"unhealthy: {str(e)}"
        logger.error(f"Readiness check failed for Neo4j: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": checks
            }
        )
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": checks
        }
    )

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/generate")
async def generate(request: GenerateRequest):
    """A simple endpoint used by agent_http.py for demo purposes."""
    return {"text": f"Echo: {request.prompt}"}

@app.post("/simulate/alert")
async def simulate_alert(request: Request, active: bool = True):
    """Simulate an alert by setting metrics on the Prometheus registry."""
    params = dict(request.query_params)
    force_ambiguous = params.get("force_ambiguous", "false").lower() in ("1", "true", "yes")

    if force_ambiguous:
        cpu_value = random.choice([48.0, 52.0, 45.0, 55.0])
        memory_value = random.choice([40.0, 60.0, 47.0, 53.0])
        req_rate = random.choice([40.0, 60.0, 50.0, 52.0])
    else:
        if active:
            cpu_value = 95.0
            memory_value = 95.0
            req_rate = 120.0
        else:
            cpu_value = 15.0
            memory_value = 15.0
            req_rate = 5.0

    PAYMENT_SERVICE_CPU.set(cpu_value)
    DB_CPU.set(cpu_value * 0.9)
    try:
        PAYMENT_SERVICE_MEMORY.set(memory_value)
        PAYMENT_SERVICE_REQUEST_RATE.set(req_rate)
    except NameError:
        pass

    status = "ambiguous" if force_ambiguous else ("alert_active" if active else "alert_cleared")
    return {"status": status, "cpu": cpu_value}

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """Render the dashboard HTML with pending decisions."""
    decisions = []
    if repo is not None:
        try:
            decisions = repo.get_pending_decisions()
        except Exception as e:
            logger.error(f"Error fetching decisions: {e}")
    
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "decisions": decisions}
    )

@app.get("/api/decisions/pending")
async def get_pending_decisions():
    """API to get raw JSON list of pending decisions."""
    if repo is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j repository not available"
        )
    return repo.get_pending_decisions()

@app.post("/api/decisions/review")
async def review_decision(review: ReviewRequest):
    """API to submit a human review for a decision."""
    if repo is None or human_review is None:
        raise HTTPException(
            status_code=503,
            detail="Human review service not available"
        )
    success = human_review.review_decision(
        review.decision_id,
        review.is_approved,
        review.validated_by,
        review.feedback
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to process review")
    return {"status": "success"}
