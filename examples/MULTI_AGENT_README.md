# Multi-Agent Alert Processing Demo

This demo showcases the **Strands Agents "Agent as Tool" pattern** for alert decision-making with two modes:

## Architecture

The system uses a **Supervisor Agent** that coordinates three specialized agents:

1. **Analyst Agent** - Correlates alerts and enriches with metrics/context
2. **Judge Agent** - Generates structured decisions from analysis  
3. **Reporter Agent** - Creates human-readable reports

```
┌─────────────────────────────────────────────────────────┐
│              Supervisor Agent                           │
│    (Routes tasks to specialized agents)                │
└──────────┬────────────────────────────┬─────────────────┘
           │                            │
     ┌─────▼─────┐              ┌──────▼────────┐
     │  Analyst  │              │   Judge       │
     │  (Tools)  │──────────────│   (Tools)     │
     └───────────┘              └───────┬───────┘
                                        │
                                  ┌─────▼────────┐
                                  │  Reporter    │
                                  │  (Tools)     │
                                  └──────────────┘
```

## Modes

### 1. Rules-Only Mode (No LLM)
Deterministic decisions based on hardcoded rules:
```bash
python examples/multi_agent_demo.py rules
```

**Features:**
- ✅ No API keys needed
- ✅ Fast execution
- ✅ Completely deterministic
- ✅ Good for testing and CI/CD
- ❌ No intelligent reasoning

**Example Output:**
```
📊 Summary:
   Total Clusters: 3
   ⚠️  Escalate:     0
   🔍 Observe:      3
   ✋ Manual Review: 0

📌 Cluster Details:
   Service: checkout-service
   Recommendation: OBSERVE (80% confidence)
```

### 2. GitHub Models Mode (Intelligent)
Uses GitHub's inference API for smart routing:
```bash
export GITHUB_TOKEN="ghp_..."
python examples/multi_agent_demo.py github
```

**Features:**
- ✅ Intelligent reasoning with LLM
- ✅ Natural language explanations
- ✅ Dynamic task routing
- ✅ Better decisions for edge cases
- ❌ Requires GitHub token and API access
- ❌ Slightly slower execution

**Required:**
- `GITHUB_TOKEN` environment variable with `models:use` scope
- GitHub Models provider installed

## Code Structure

- `src/agents/multi_agent/supervisor.py` - Main orchestrator
- `src/agents/multi_agent/tools.py` - Specialized agents as tools
- `examples/multi_agent_demo.py` - CLI demo with both modes

## Implementation Details

### Supervisor Agent
```python
from src.agents.multi_agent.supervisor import SupervisorAgent

# Mode 1: Rules-only (no LLM)
from src.agents.multi_agent.tools import analyst_agent, judge_agent, reporter_agent
analysis = analyst_agent(json.dumps(alerts))
decisions = judge_agent(analysis)
report = reporter_agent(decisions)

# Mode 2: GitHub Models (with LLM)
supervisor = SupervisorAgent(model="github")
report = supervisor.process_alerts(alerts)
```

### Tool Pattern
Each specialized agent is wrapped as a Strands `@tool`:
```python
@tool
def analyst_agent(alerts_json: str) -> str:
    """Correlates alerts and enriches with metrics/context."""
    # Parse → Correlate → Enrich → Return JSON
    pass
```

## Constitution Principles

The system follows 4 core principles:

1. **Human-in-the-Loop** - Decisions require human confirmation
2. **Determinismo** - Rules evaluated BEFORE any LLM
3. **Controle de Aprendizado** - Embeddings persisted after confirmation only
4. **Rastreabilidade** - Full immutable audit trail

## Testing

```bash
# Rules mode (always works)
python examples/multi_agent_demo.py rules

# GitHub Models mode (requires token)
export GITHUB_TOKEN="ghp_..."
python examples/multi_agent_demo.py github

# Unit tests
pytest tests/unit/ -v
```

## Next Steps

1. **Add Memory** - Implement conversation history for multi-turn decisions
2. **Add Metrics** - Track decision accuracy and latency
3. **Add Web UI** - FastAPI endpoint for interactive alerts
4. **Add Persistence** - Store decision history and embeddings
5. **Add Escalation** - Route critical alerts to on-call teams

## References

- [Strands Agents SDK](https://strandsagents.com)
- [Agent as Tool Pattern](https://strandsagents.com/latest/documentation/docs/examples/python/multi_agent_example/)
- [GitHub Models](https://github.com/marketplace/models)
