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
import time
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

class GenerateRequest(BaseModel):
    prompt: str

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

@app.post("/api/decisions/review")
async def review_decision(review: ReviewRequest):
    """API to submit a human review for a decision."""
    success = human_review.review_decision(
        review.decision_id,
        review.is_approved,
        review.validated_by,
        review.feedback
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to process review")
    return {"status": "success"}
