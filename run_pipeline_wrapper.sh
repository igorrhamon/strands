#!/usr/bin/env bash
# Wrapper to run the pipeline with venv python and timestamped logging
PROJECT_ROOT="/mnt/c/Users/F4352981/Downloads/arquivosWsl/agents/strads"
cd "$PROJECT_ROOT" || exit 1
VENV_PY="$PROJECT_ROOT/.venv/bin/python"
if [ -x "$VENV_PY" ]; then
  PY="$VENV_PY"
else
  PY="python3"
fi
# Ensure project root is on PYTHONPATH so `from src...` imports work
export PYTHONPATH="$PROJECT_ROOT":${PYTHONPATH:-}
# Source environment if present
if [ -f "$PROJECT_ROOT/.env" ]; then
  # shellcheck disable=SC1090
  . "$PROJECT_ROOT/.env"
fi

# If running inside Docker (best-effort detection) or if GRAFANA_URL is empty, prefer docker service URL
if [ -n "$GRAFANA_URL_DOCKER" ] && ( [ -z "$GRAFANA_URL" ] || [ -n "$DOCKER_CONTAINER" ] || [ -n "$RUNNING_IN_DOCKER" ] ); then
  export GRAFANA_URL="$GRAFANA_URL_DOCKER"
fi
# Run the pipeline and prefix lines with timestamp
exec $PY examples/run_pipeline.py 2>&1 | while IFS= read -r line; do echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') $line"; done
