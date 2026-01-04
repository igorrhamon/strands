from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.grafana_alert_analysis.agent import GrafanaAlertAgent
from src.agents.grafana_alert_analysis.schemas import AgentInput


def main() -> None:
    dashboard_url = os.environ.get("GRAFANA_DASHBOARD_URL")
    if not dashboard_url:
        raise SystemExit("Set GRAFANA_DASHBOARD_URL to the full /d/<uid>/<slug> Grafana URL")

    agent = GrafanaAlertAgent()
    result = agent.run(
        AgentInput(
            start=os.environ.get("GRAFANA_FROM", "now-6h"),
            end=os.environ.get("GRAFANA_TO", "now"),
            environment=os.environ.get("ENVIRONMENT", "local"),
            filters=None,
            dashboard_url=dashboard_url,
        )
    )

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
