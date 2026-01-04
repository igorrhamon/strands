#!/usr/bin/env python3
"""Orchestrator for example pipelines in this workspace.

Usage:
  orchestrator.py full       # run examples/full_grafana_analysis.py
  orchestrator.py correlator # run examples/agent_with_correlator.py
  orchestrator.py llm       # run examples/full_grafana_analysis_llm.py
  orchestrator.py embed     # run scripts/test_github_embedding.py (remote embeddings)
  orchestrator.py logs      # tail docker logs for sgn stack (requires docker-compose started)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_module(path: str) -> int:
    """Run a python script relative to repo root using venv python if available."""
    python = os.environ.get("VENV_PYTHON") or sys.executable
    full = ROOT.joinpath(path)
    if not full.exists():
        print(f"Script not found: {full}")
        return 2
    print(f"Running: {python} {full}")
    return subprocess.call([python, str(full)])


def tail_logs() -> int:
    """Tail docker-compose logs for the SGN agendamento stack.

    Uses the compose file at ../sgn-agendamento-massificado-api/run/docker-compose.yaml
    if present. This is a convenience helper for local dev.
    """
    compose_path = Path(__file__).resolve().parents[2] / "sgn" / "sgn-agendamento-massificado-api" / "run" / "docker-compose.yaml"
    if not compose_path.exists():
        print(f"Compose file not found: {compose_path}")
        return 2
    cmd = ["docker", "compose", "-f", str(compose_path), "logs", "-f"]
    print("Tailing logs (ctrl-c to stop)...")
    return subprocess.call(cmd)


def main() -> int:
    p = argparse.ArgumentParser(description="Examples orchestrator")
    p.add_argument("pipeline", choices=["full", "correlator", "llm", "embed", "logs"], help="Which example to run")
    args = p.parse_args()

    if args.pipeline == "full":
        return run_module("examples/full_grafana_analysis.py")
    if args.pipeline == "correlator":
        return run_module("examples/agent_with_correlator.py")
    if args.pipeline == "llm":
        return run_module("examples/full_grafana_analysis_llm.py")
    if args.pipeline == "embed":
        return run_module("scripts/test_github_embedding.py")
    if args.pipeline == "logs":
        return tail_logs()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
