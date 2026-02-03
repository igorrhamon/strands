#!/bin/bash
uv run uvicorn server_fastapi:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &
