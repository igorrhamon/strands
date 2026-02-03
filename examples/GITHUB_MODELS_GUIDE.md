# Using GitHub Models with Multi-Agent System

This guide shows how to use **GitHub Models** for intelligent LLM-based alert routing in the multi-agent system.

## Prerequisites

1. **GitHub Token** with `models:use` scope
   - Create at: https://github.com/settings/tokens
   - Select scopes: `repo`, `models:use`
   - Save the token securely

2. **Strands SDK** (already installed)
   ```bash
   pip list | grep strands-agents
   # Should show: strands-agents==1.21.0 or later
   ```

## Quick Start

### Step 1: Set Environment Variable
```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### Step 2: Run Demo with GitHub Models
```bash
cd /home/wsl/agents/strads
python examples/multi_agent_demo.py github
```

## What GitHub Models Does

The **GitHub Models** mode enables intelligent task routing:

```
Raw Alerts
    ↓
Supervisor Agent (powered by GitHub Models)
    ├─ "Should we correlate first?"
    ├─ "Which metrics matter?"
    └─ "Is this critical?"
    ↓
Routes to Analyst/Judge/Reporter intelligently
    ↓
Better Decisions
```

## Code Example: Using GitHub Models Directly

### In Python Code
```python
from src.agents.multi_agent.supervisor import SupervisorAgent
from src.models.alert import Alert
from datetime import datetime, timezone

# Create alerts
alerts = [
    Alert(
        timestamp=datetime.now(timezone.utc),
        fingerprint="alert-001",
        service="checkout-service",
        severity="critical",
        description="CPU exceeds 90%",
        labels={"region": "us-east-1"}
    ),
]

# Initialize with GitHub Models
supervisor = SupervisorAgent(model="github")

# Process alerts intelligently
report = supervisor.process_alerts(alerts)

# Print decision report
print(report)
```

### Using the Provider Directly
```python
from src.providers.github_models import GitHubModels

# Initialize GitHub Models provider
model = GitHubModels(
    endpoint="https://models.github.ai/inference",
    model_name="openai/gpt-5",  # Or other available models
    timeout=30
)

# Use with Strands Agent
from strands import Agent

agent = Agent(
    system_prompt="You are an alert decision expert",
    model=model,
    tools=[...]
)

response = agent("Analyze these alerts...")
```

## Available Models on GitHub

Check what's available:
```bash
# GitHub Models supports various providers:
- openai/gpt-5
- google/gemini-2.0-flash
- claude-3-5-sonnet-20241022
- mistral-large
- llama-2-70b-chat
# (List updates frequently)
```

See current availability: https://github.com/marketplace/models

## Configuration Options

### Default Configuration
```python
# Uses environment defaults
supervisor = SupervisorAgent(model="github")
```

### Custom Configuration
```python
from src.providers.github_models import GitHubModels

model = GitHubModels(
    endpoint="https://models.github.ai/inference",  # GitHub default
    model_name="openai/gpt-5",                       # Change model
    timeout=60                                        # Increase timeout
)

supervisor = SupervisorAgent(model=model)
```

### Custom System Prompt
```python
from src.agents.multi_agent.supervisor import SupervisorAgent

class CustomSupervisor(SupervisorAgent):
    SUPERVISOR_SYSTEM_PROMPT = """
You are an expert in security alert triage.
Your job is to coordinate specialized agents to:
1. Correlate alerts into clusters
2. Analyze metrics and context
3. Generate actionable recommendations

Be thorough but concise. Always explain your reasoning.
"""

supervisor = CustomSupervisor(model="github")
```

## Troubleshooting

### Error: "GITHUB_TOKEN not found in environment"
```bash
# Ensure token is exported
export GITHUB_TOKEN="ghp_..."

# Verify it's set
echo $GITHUB_TOKEN
```

### Error: "Unable to locate credentials"
The token might not have `models:use` scope:
1. Go to https://github.com/settings/tokens
2. Click on your token
3. Ensure `models:use` scope is checked
4. Regenerate if needed

### Error: "Permission denied" (403)
```bash
# Token might be invalid or expired
# Create a new one: https://github.com/settings/tokens/new
export GITHUB_TOKEN="ghp_new_token"
```

### Error: "Connection timeout"
The GitHub Models API might be unavailable:
- Check: https://www.githubstatus.com
- Increase timeout: `GitHubModels(timeout=60)`
- Try rules mode: `python examples/multi_agent_demo.py rules`

### Error: "Model not found"
The model name might not exist:
```python
# List available models at https://github.com/marketplace/models
model = GitHubModels(model_name="google/gemini-2.0-flash")  # Try another
```

## Performance Tips

### 1. Enable Caching
```python
supervisor = SupervisorAgent(model="github")
# Caching happens automatically via GitHub Models
```

### 2. Batch Alerts
Instead of processing one alert:
```python
# ✅ Good: Batch multiple alerts
supervisor.process_alerts(alerts)  # List of 10-100 alerts

# ❌ Avoid: Single alert per call
supervisor.process_alerts([alert])  # Only 1 alert
```

### 3. Use Rules Mode for Frequent Calls
```python
# For high-frequency alerts, use deterministic rules
from src.agents.multi_agent.tools import analyst_agent, judge_agent, reporter_agent

# Fast, no API calls
analysis = analyst_agent(json.dumps(alerts))
decisions = judge_agent(analysis)
report = reporter_agent(decisions)
```

## Cost Estimation

GitHub Models pricing (approximate):
- **Claude 3.5 Sonnet**: ~$0.003/K input tokens, ~$0.015/K output tokens
- **Gemini 2.0 Flash**: ~$0.0075/K tokens
- **OpenAI GPT-5**: Varies by availability

Typical alert analysis: 500-1000 tokens
- 10 alerts: ~5K tokens = $0.01-0.05 per batch
- 1000 alerts/day: ~$0.10-0.50 daily

## Running in Production

### Environment Setup
```bash
# In your CI/CD or deployment
export GITHUB_TOKEN="${{ secrets.GITHUB_TOKEN }}"
export SUPERVISOR_MODE="github"
```

### Async Usage (for servers)
```python
import asyncio

async def process_alerts_async(alerts):
    supervisor = SupervisorAgent(model="github")
    report = await supervisor.process_alerts_async(alerts)
    return report

# In FastAPI or async context
@app.post("/alerts")
async def handle_alerts(alerts: List[Alert]):
    report = await process_alerts_async(alerts)
    return report
```

### Error Handling
```python
try:
    supervisor = SupervisorAgent(model="github")
    report = supervisor.process_alerts(alerts)
except Exception as e:
    # Fallback to rules mode
    logger.warning(f"GitHub Models failed: {e}, using rules mode")
    from src.agents.multi_agent.tools import (
        analyst_agent, judge_agent, reporter_agent
    )
    analysis = analyst_agent(json.dumps(alerts))
    decisions = judge_agent(analysis)
    report = reporter_agent(decisions)

return report
```

## Monitoring and Logging

### Enable Detailed Logging
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("strands")
logger.setLevel(logging.DEBUG)

# Now see all agent decisions and reasoning
supervisor = SupervisorAgent(model="github")
report = supervisor.process_alerts(alerts)
```

### Metrics Collection
```python
import time

start = time.time()
report = supervisor.process_alerts(alerts)
duration = time.time() - start

print(f"Processing took {duration:.2f}s")
print(f"Decisions made: {len(report.get('decisions', []))}")
```

## See Also

- [Strands Agents Documentation](https://strandsagents.com/latest/documentation/)
- [GitHub Models Marketplace](https://github.com/marketplace/models)
- [Multi-Agent Demo](examples/multi_agent_demo.py)
- [SupervisorAgent Source](src/agents/multi_agent/supervisor.py)
