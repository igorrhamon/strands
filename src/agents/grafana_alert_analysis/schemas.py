from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class AgentInput(BaseModel):
    start: str = Field(..., description="ISO-8601 start time")
    end: str = Field(..., description="ISO-8601 end time")
    environment: str = Field(..., description="Target environment (e.g., prod, hml)")
    filters: Optional[Dict[str, str]] = Field(None, description="Optional label filters")
    dashboard_url: Optional[str] = Field(
        None,
        description="Optional Grafana dashboard URL. If provided, the agent will read dashboard panel queries and fetch data for the given time range.",
    )

class AlertRecommendation(BaseModel):
    cluster_id: str
    severity: str
    services: List[str]
    root_cause_hypothesis: str
    recommended_action: str
    confidence: float

class AgentOutput(BaseModel):
    recommendations: List[AlertRecommendation]
    summary: str
