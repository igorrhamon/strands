import os
import logging
from uuid import UUID
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
import random
import time
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Gauge

from src.graph.neo4j_repo import Neo4jRepository
from src.agents.governance.human_review import HumanReviewAgent
from src.models.decision import DecisionValidation

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

# Prometheus Metrics
PAYMENT_SERVICE_CPU = Gauge('payment_service_cpu_usage', 'CPU usage of payment service')
DB_CPU = Gauge('db_cpu_usage', 'CPU usage of database')
# Simulated additional metrics for demo
PAYMENT_SERVICE_MEMORY = Gauge('payment_service_memory_usage', 'Memory usage of payment service')
PAYMENT_SERVICE_REQUEST_RATE = Gauge('payment_service_request_rate_usage', 'Request rate of payment service')

# App Setup
app = FastAPI(title="Strads Agents - Governance Dashboard")
templates = Jinja2Templates(directory="templates")

# Dependencies (Global for demo simplicity)
# In production, use dependency injection
repo = Neo4jRepository()
human_review = HumanReviewAgent(repo)

# Request Models
class ReviewRequest(BaseModel):
    decision_id: str
    is_approved: bool
    feedback: Optional[str] = None
    validated_by: str

@app.on_event("startup")
async def startup_event():
    try:
        repo.connect()
        logger.info("Connected to Neo4j")
    except Exception as e:
        logger.warning(f"Could not connect to Neo4j: {e}. Dashboard will be empty.")

@app.on_event("shutdown")
async def shutdown_event():
    repo.close()

# --- API Endpoints ---

class GenerateRequest(BaseModel):
    prompt: str
    max_tokens: Optional[int] = 1024

@app.post("/generate")
async def generate(request: GenerateRequest):
    """Echo endpoint for agent_http.py demo."""
    return {"text": f"Echo: {request.prompt[:100]}..."}

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/simulate/alert")
async def simulate_alert(request: Request, active: bool = True):
    """Simulate an alert by setting metrics on the Prometheus registry.
    When `active` is True the CPU gauge will be set high; otherwise low.
    If `force_ambiguous` is True, metrics will oscillate to create ambiguous trends
    that cause the deterministic rule engine to return a low confidence decision.
    """
    params = dict(request.query_params)
    force_ambiguous = params.get("force_ambiguous", "false").lower() in ("1", "true", "yes")

    if force_ambiguous:
        # produce an oscillating series by choosing a value near the decision boundary
        # alternate between medium and slightly high values so metrics look noisy
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
        # older versions may not have these gauges registered
        pass

    status = "ambiguous" if force_ambiguous else ("alert_active" if active else "alert_cleared")
    return {"status": status, "cpu": cpu_value}

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """Render the dashboard HTML with pending decisions."""
    try:
        decisions = repo.get_pending_decisions()
    except Exception as e:
        logger.error(f"Error fetching decisions: {e}")
        decisions = []
        
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "decisions": decisions}
    )

@app.get("/api/decisions/pending")
async def get_pending_decisions():
    """API to get raw JSON list of pending decisions."""
    return repo.get_pending_decisions()

@app.post("/decisions/{decision_id}/review")
async def submit_review(decision_id: str, review: ReviewRequest):
    """Submit a human approval or rejection."""
    try:
        if str(decision_id) != str(review.decision_id):
            raise HTTPException(status_code=400, detail="ID mismatch")
        
        # 1. Construct Validation Object
        # Note: In a real app we would fetch the candidate first to check existence
        # But HumanReviewAgent mainly needs the ID to update the graph.
        # However, .process_review expects a DecisionCandidate object.
        # We need a lightweight way to re-hydrate/mock it or change process_review signature.
        
        # For this demo, we will create a 'stub' candidate just enough to pass validation
        # or we fetch it from DB (but we didn't implement get_by_id yet).
        # Let's modify the process_review call slightly or stub the candidate.
        
        # Actually, let's create a stub since `process_review` mostly reads ID and updates status.
        from src.models.decision import DecisionCandidate, DecisionStatus, AutomationLevel
        
        stub_candidate = DecisionCandidate(
            decision_id=UUID(decision_id),
            alert_reference="unknown", # Not needed for update
            summary="stub",
            status=DecisionStatus.PROPOSED,
            primary_hypothesis="stub",
            risk_assessment="stub",
            automation_level=AutomationLevel.MANUAL
        )

        validation = DecisionValidation(
            validation_id=f"val-{datetime.now().timestamp()}",
            decision_id=UUID(decision_id),
            validated_by=review.validated_by,
            is_approved=review.is_approved,
            feedback=review.feedback,
            validated_at=datetime.now(timezone.utc)
        )

        human_review.process_review(stub_candidate, validation)
        
        return {"status": "success", "decision_id": decision_id, "action": "approved" if review.is_approved else "rejected"}

    except Exception as e:
        logger.error(f"Error processing review: {e}")
        raise HTTPException(status_code=500, detail=str(e))
