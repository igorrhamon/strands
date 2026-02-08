# Agents Package
"""
Multi-agent components for alert processing pipeline.

Each agent:
- Receives typed input
- Returns typed output
- Declares timeout
- Declares fallback behavior

Pipeline: AlertCorrelation → MetricsAnalysis → SemanticRecovery → DecisionEngine → Report
"""

from src.agents.alert_correlation import (
    AlertCorrelationAgent,
    ALERT_CORRELATION_TOOL,
    execute_correlation_tool,
)
from src.agents.metrics_analysis import (
    MetricsAnalysisAgent,
    METRICS_ANALYSIS_TOOL,
    execute_metrics_tool,
)
from src.agents.decision_engine import (
    DecisionEngine,
    DecisionEngineError,
    DECISION_ENGINE_TOOL,
    execute_decision_tool,
)
from src.agents.report_agent import (
    ReportAgent,
    ReportAgentError,
    REPORT_AGENT_TOOL,
)
from src.agents.alert_orchestrator import (
    AlertOrchestrator,
    OrchestratorConfig,
    OrchestratorError,
    ORCHESTRATOR_TOOL,
)

__all__ = [
    "AlertCorrelationAgent",
    "ALERT_CORRELATION_TOOL",
    "execute_correlation_tool",
    "MetricsAnalysisAgent",
    "METRICS_ANALYSIS_TOOL",
    "execute_metrics_tool",
    "DecisionEngine",
    "DecisionEngineError",
    "DECISION_ENGINE_TOOL",
    "execute_decision_tool",
    "ReportAgent",
    "ReportAgentError",
    "REPORT_AGENT_TOOL",
    "AlertOrchestrator",
    "OrchestratorConfig",
    "OrchestratorError",
    "ORCHESTRATOR_TOOL",
]
