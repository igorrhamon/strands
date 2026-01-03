# Strands Agents — HTTP custom model provider example

This example shows how to create a custom `Model` provider for Strands Agents
that forwards prompts to an HTTP endpoint (for example an open-source model
you hosted yourself). It also includes a minimal FastAPI demo server.

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

Notes
-----
- Production servers should implement streaming, authentication, retries,
  timeout control and proper error handling. The demo server only echoes the
  prompt for simplicity.
- If you have a model from GitHub Models, first serve it with a model server
  (Ollama, Llama-API, custom FastAPI wrapping a transformers pipeline, etc.)
  and then point `HTTPModel.endpoint_url` to that server.
