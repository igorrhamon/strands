# Grafana Alert Analysis Examples

This directory contains examples demonstrating the full capabilities of the Grafana Alert Analysis Agent, including alert correlation and recommendation generation.

## Available Examples

### 1. `demo_correlator_recommender.py` - Interactive Demo
**Purpose**: Demonstrates correlation and recommendation logic with sample data (no Grafana required).

**What it does**:
- Shows how alerts are clustered by fingerprint and service+alertname
- Generates recommendations based on severity and cluster patterns
- Explains the logic behind each recommendation

**Usage**:
```bash
python examples/demo_correlator_recommender.py
```

**Output**: Detailed breakdown of clusters and recommendations with interpretation guide.

---

### 2. `agent_with_correlator.py` - Full Agent Workflow
**Purpose**: Runs the complete agent workflow against a live Grafana instance.

**What it does**:
- Fetches alert rules from Grafana via MCP
- Clusters alerts using `AlertCorrelator`
- Generates recommendations using `RecommendationEngine`
- Displays structured output with confidence scores

**Usage**:
```bash
export GRAFANA_FROM="now-24h"
export GRAFANA_TO="now"
export ENVIRONMENT="production"
python examples/agent_with_correlator.py
```

**Output**: Recommendations for each cluster + raw alert statistics + JSON export.

---

### 3. `full_grafana_analysis.py` - Comprehensive Report
**Purpose**: Generates a complete Grafana observability report (datasources, alerts, clusters, dashboard).

**What it does**:
- Lists all datasources (Prometheus, Loki, etc.)
- Fetches and clusters alert rules
- Generates recommendations via agent
- Executes dashboard panel queries (if `GRAFANA_DASHBOARD_URL` is set)
- Outputs structured JSON report

**Usage**:
```bash
export GRAFANA_DASHBOARD_URL="http://localhost:3000/d/<uid>/<slug>"
# OR
export GRAFANA_DASHBOARD_QUERY="SGN"  # Search by name
python examples/full_grafana_analysis.py
```

**Output**: JSON report with:
```json
{
  "datasources": {...},
  "alerts": {
    "agent_summary": "...",
    "recommendations": [...],
    "stats": {...},
    "clusters": {
      "total": 4,
      "items": [...]
    }
  },
  "dashboard": {...}
}
```

---

### 4. `full_grafana_analysis_llm.py` - LLM-Enhanced Analysis
**Purpose**: Combines the full report with GitHub Models LLM for narrative analysis in Portuguese.

**What it does**:
- Calls `full_grafana_analysis.py` internally (includes correlation)
- Sends the JSON report to GitHub Models (GPT-5)
- Returns a structured SRE analysis with:
  - Executive summary
  - Health signals
  - Risks and alerts
  - Hypotheses
  - Read-only investigation steps

**Usage**:
```bash
export GITHUB_TOKEN="ghp_..."
export GRAFANA_DASHBOARD_QUERY="SGN"
python examples/full_grafana_analysis_llm.py
```

**Output**: Portuguese SRE analysis text (printed to stdout, logs to stderr).

---

### 5. `read_grafana_dashboard.py` - Dashboard Query Execution
**Purpose**: Reads a specific dashboard and executes all panel PromQL queries.

**What it does**:
- Fetches panel definitions from a dashboard
- Executes PromQL queries against Prometheus
- Reports execution success and series counts

**Usage**:
```bash
export GRAFANA_DASHBOARD_URL="http://localhost:3000/d/abc123/my-dashboard"
export GRAFANA_FROM="now-6h"
export GRAFANA_TO="now"
python examples/read_grafana_dashboard.py
```

**Output**: Summary of panels and queries executed.

---

## Architecture Overview

```
examples/
├── demo_correlator_recommender.py  ← Standalone demo (sample data)
├── agent_with_correlator.py        ← Agent workflow (live Grafana)
├── full_grafana_analysis.py        ← Comprehensive report builder
└── full_grafana_analysis_llm.py    ← LLM-enhanced analysis

src/agents/grafana_alert_analysis/
├── agent.py           ← Thin wrapper around analyzer
├── analyzer.py        ← Main orchestrator (uses correlator + recommender)
├── correlator.py      ← AlertCorrelator: clusters alerts
├── recommender.py     ← RecommendationEngine: generates actions
├── schemas.py         ← Pydantic models
└── tools/
    └── grafana_mcp.py ← MCP client for Grafana
```

## How Correlation Works

**AlertCorrelator** groups alerts using:
1. **Identical fingerprint** → same cluster
2. **Same service + alertname** → same cluster

Each cluster contains:
- `cluster_id`: MD5 hash of service-alertname-fingerprint
- `alerts`: List of alert objects
- `service`, `alertname`, `severity`: Metadata
- `count`: Number of alerts in cluster

## How Recommendations Work

**RecommendationEngine** analyzes clusters and suggests:

| Pattern | Action | Hypothesis | Confidence |
|---------|--------|------------|------------|
| Count > 5 AND severity = LOW | CLOSE | High recurrence, likely noise | 80% |
| Severity = CRITICAL | ESCALATE | Critical alert detected | 90% |
| Other patterns | OBSERVE | Ambiguous, needs investigation | 50% |

Each recommendation includes:
- `cluster_id`: Which cluster it applies to
- `severity`, `services`: Context
- `recommended_action`: CLOSE / ESCALATE / OBSERVE
- `root_cause_hypothesis`: Explanation
- `confidence`: 0.0–1.0

## Environment Variables

### Required (Grafana MCP)
```bash
GRAFANA_URL=http://localhost:3000          # Grafana instance URL
GRAFANA_TOKEN=glsa_...                     # Service account token
GRAFANA_MCP_TRANSPORT=stdio                # MCP transport type
GRAFANA_MCP_COMMAND=docker                 # MCP server command
GRAFANA_MCP_ARGS_JSON='["run", ...]'       # MCP command args (JSON array)
```

### Optional (Query/Analysis)
```bash
GRAFANA_FROM=now-6h                        # Query start time
GRAFANA_TO=now                             # Query end time
ENVIRONMENT=local                          # Environment label
GRAFANA_DASHBOARD_URL=http://...           # Specific dashboard to analyze
GRAFANA_DASHBOARD_QUERY=SGN                # Search dashboards by name
```

### Optional (LLM Analysis)
```bash
GITHUB_TOKEN=ghp_...                       # GitHub Models API token
GITHUB_MODELS_MODEL=openai/gpt-5           # Model name (default)
GITHUB_MODELS_ENDPOINT=https://models...   # API endpoint (default)
GITHUB_MODELS_TIMEOUT=120                  # Request timeout seconds (default)
```

## Testing

Run the demo first to understand correlation/recommendation logic:
```bash
python examples/demo_correlator_recommender.py
```

Then try with real Grafana data:
```bash
python examples/agent_with_correlator.py
```

Finally, generate a full report with LLM analysis:
```bash
python examples/full_grafana_analysis_llm.py > analysis.txt
```

## Next Steps

1. **Add more correlation rules**: Extend `AlertCorrelator._alerts_match()` to cluster by time windows, label patterns, etc.
2. **Enhance recommendations**: Add more heuristics in `RecommendationEngine.recommend()` (e.g., blast radius, SLO impact).
3. **Integrate with incident management**: Auto-create tickets for ESCALATE recommendations.
4. **Add metrics export**: Track recommendation accuracy and cluster evolution over time.
