"""
SRE Curation Dashboard API

Backend para o dashboard de curação de playbooks.
Permite listar, aprovar, rejeitar e editar playbooks.
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.core.neo4j_playbook_store import Neo4jPlaybookStore, PlaybookStatus
from src.agents.governance.playbook_generator import PlaybookGeneratorAgent

app = FastAPI(title="Strands Curation API", version="1.0.0")

# Dependência para PlaybookStore
def get_playbook_store():
    store = Neo4jPlaybookStore()
    try:
        yield store
    finally:
        store.close()

class PlaybookResponse(BaseModel):
    playbook_id: str
    title: str
    description: str
    pattern_type: str
    service_name: str
    status: str
    source: str
    steps: List[Dict[str, Any]]
    estimated_time_minutes: int
    risk_level: str
    created_at: datetime
    metadata: Dict[str, Any]

class ApprovalRequest(BaseModel):
    approved_by: str
    notes: Optional[str] = None

class RejectionRequest(BaseModel):
    rejected_by: str
    reason: str

@app.get("/playbooks/pending", response_model=List[PlaybookResponse])
async def list_pending_playbooks(
    limit: int = Query(50, ge=1, le=100),
    store: Neo4jPlaybookStore = Depends(get_playbook_store)
):
    """Lista playbooks aguardando revisão."""
    playbooks = store.get_pending_review_playbooks(limit=limit)
    return playbooks

@app.post("/playbooks/{playbook_id}/approve")
async def approve_playbook(
    playbook_id: str,
    request: ApprovalRequest,
    store: Neo4jPlaybookStore = Depends(get_playbook_store)
):
    """Aprova um playbook."""
    success = store.approve_playbook(
        playbook_id=playbook_id,
        approved_by=request.approved_by,
        notes=request.notes
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Playbook not found or failed to approve")
    
    return {"status": "success", "message": f"Playbook {playbook_id} approved"}

@app.post("/playbooks/{playbook_id}/reject")
async def reject_playbook(
    playbook_id: str,
    request: RejectionRequest,
    store: Neo4jPlaybookStore = Depends(get_playbook_store)
):
    """Rejeita um playbook."""
    success = store.reject_playbook(
        playbook_id=playbook_id,
        rejected_by=request.rejected_by,
        reason=request.reason
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Playbook not found or failed to reject")
    
    return {"status": "success", "message": f"Playbook {playbook_id} rejected"}

@app.get("/playbooks/{playbook_id}/stats")
async def get_playbook_stats(
    playbook_id: str,
    store: Neo4jPlaybookStore = Depends(get_playbook_store)
):
    """Retorna estatísticas de um playbook."""
    stats = store.get_playbook_statistics(playbook_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Playbook not found")
    return stats
