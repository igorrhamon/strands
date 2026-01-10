# Strands Agents — HTTP custom model provider example

This example shows how to create a custom `Model` provider for Strands Agents
that forwards prompts to an HTTP endpoint (for example an open-source model
you hosted yourself). It also includes a minimal FastAPI demo server.

## Features

- **Custom HTTP Model Provider**: HTTPModel implementation for Strands Agents SDK
- **GitHub Models Provider**: Integration with Microsoft Foundry Inference SDK (see [specs/001-github-model-provider](specs/001-github-model-provider/))
- **Ollama Provider**: Local LLM integration via Ollama API (see [src/providers/ollama_models.py](src/providers/ollama_models.py))
- **MetricsAnalysisAgent**: Enhanced agent with p95 filtering, exponential backoff, and multi-metric fusion (see [specs/008-metrics-analysis-agent/quickstart.md](specs/008-metrics-analysis-agent/quickstart.md))
- **Multi-Agent Pipeline**: Complete SRE workflow with 12-step orchestration (see [examples/PIPELINE_OLLAMA_README.md](examples/PIPELINE_OLLAMA_README.md))
- **FastAPI Demo Server**: Minimal server for testing HTTP model integration

Setup
-----

1. Create and activate a virtual environment

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

2. Run the demo server (FastAPI)

```bash
uvicorn server_fastapi:app --reload --port 8000
```

3. In another terminal (with `.venv` activated) run the agent example

```bash
python agent_http.py
```

Files
-----
- `my_http_model.py`: Custom `HTTPModel` provider that posts prompts to an endpoint.
- `agent_http.py`: Example that creates an `Agent` using the custom provider.
- `server_fastapi.py`: Small FastAPI demo server that returns an echoed response.
- `requirements.txt`: Packages used in the example.

Multi-Agent Pipeline Examples
------------------------------
Complete SRE workflows demonstrating agent orchestration:

### Ollama Pipeline (Local LLM)
Full 12-step pipeline with Ollama provider:
- **Quick Start**: `python examples/pipeline_ollama_test.py` (connectivity test)
- **Full Pipeline**: `python examples/pipeline_ollama.py` (complete workflow)
- **Documentation**: [examples/PIPELINE_OLLAMA_README.md](examples/PIPELINE_OLLAMA_README.md)
- **Summary**: [examples/PIPELINE_IMPLEMENTATION_SUMMARY.md](examples/PIPELINE_IMPLEMENTATION_SUMMARY.md)

Pipeline Flow:
```
AlertCollector → AlertNormalizer → AlertCorrelation → MetricsAnalysis
→ RepositoryContext ⟷ GraphKnowledge (feedback loop)
→ DecisionEngine → HumanReview → OutcomeSupervisor
→ MemoryValidation → GraphKnowledge → AuditReport
```

Prerequisites:
```bash
# Install and start Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve

# Pull a model
ollama pull llama3.1

# Set environment
export OLLAMA_HOST="http://localhost:11434"
export OLLAMA_MODEL="llama3.1"
```

Notes
-----
- Production servers should implement streaming, authentication, retries,
  timeout control and proper error handling. The demo server only echoes the
  prompt for simplicity.
- If you have a model from GitHub Models, first serve it with a model server
  (Ollama, Llama-API, custom FastAPI wrapping a transformers pipeline, etc.)
  and then point `HTTPModel.endpoint_url` to that server.
