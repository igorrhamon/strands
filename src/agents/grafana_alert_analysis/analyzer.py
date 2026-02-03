from __future__ import annotations

from urllib.parse import urlparse

from .correlator import AlertCorrelator
from .recommender import RecommendationEngine
from .tools.grafana_mcp import get_dashboard_panel_queries, list_alerts, list_datasources, query_metrics
from .schemas import AgentInput, AgentOutput

class AlertAnalyzer:
    def execute(self, input: AgentInput) -> AgentOutput:
        """
        Execute the alert analysis workflow.
        
        Args:
            input: AgentInput object containing parameters
            
        Returns:
            AgentOutput object containing recommendations and summary
        """
        if input.dashboard_url:
            return self._read_dashboard(input)

        # 1. Fetch alerts
        alerts = list_alerts(
            status="firing",
            start_time=input.start,
            end_time=input.end,
            labels=input.filters,
        )

        # 2. Correlate alerts into clusters
        clusters = AlertCorrelator().cluster(alerts)

        # 3. Generate recommendations
        recommendations = RecommendationEngine().recommend(clusters)

        # 4. Generate summary
        summary = (
            f"Analyzed {len(alerts)} alerts, grouped into {len(clusters)} clusters. "
            f"Generated {len(recommendations)} recommendations."
        )

        return AgentOutput(recommendations=recommendations, summary=summary)

    def _read_dashboard(self, input: AgentInput) -> AgentOutput:
        parsed = urlparse(input.dashboard_url or "")
        # Expected: /d/<uid>/<slug>
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 3 or parts[0] != "d":
            raise ValueError("dashboard_url must look like http(s)://<host>/d/<uid>/<slug>")

        dashboard_uid = parts[1]
        panel_queries = get_dashboard_panel_queries(dashboard_uid)

        datasources = list_datasources("prometheus")
        ds_uid = None
        for ds in datasources:
            if isinstance(ds, dict) and (ds.get("isDefault") or ds.get("default")):
                ds_uid = ds.get("uid")
                break
        if not ds_uid and datasources and isinstance(datasources[0], dict):
            ds_uid = datasources[0].get("uid")
        if not isinstance(ds_uid, str) or not ds_uid:
            raise RuntimeError("No Prometheus datasource found in Grafana")

        queried = 0
        for panel in panel_queries:
            if not isinstance(panel, dict):
                continue

            panel_ds_type = None
            if isinstance(panel.get("datasource"), dict):
                panel_ds_type = panel["datasource"].get("type")
            if isinstance(panel_ds_type, str) and panel_ds_type and panel_ds_type != "prometheus":
                continue

            query = panel.get("query")
            if not isinstance(query, str) or not query.strip():
                continue

            # Some dashboards return a list of queries in a single field; keep it minimal and only
            # run if it's a single PromQL string.
            panel_ds_uid = None
            if isinstance(panel.get("datasource"), dict):
                panel_ds_uid = panel["datasource"].get("uid")

            # If the panel datasource is templated ($datasource), prefer a concrete Prometheus UID.
            if not isinstance(panel_ds_uid, str) or not panel_ds_uid or panel_ds_uid.startswith("$"):
                panel_ds_uid = ds_uid

            query_metrics(query, start=input.start, end=input.end, datasource_uid=panel_ds_uid)
            queried += 1

        summary = f"Read dashboard '{dashboard_uid}': found {len(panel_queries)} panels with queries; executed {queried} PromQL queries for the provided time range."
        return AgentOutput(recommendations=[], summary=summary)
