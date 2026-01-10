from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agents.grafana_alert_analysis.agent import GrafanaAlertAgent
from src.agents.grafana_alert_analysis.schemas import AgentInput, AgentOutput
from src.agents.grafana_alert_analysis.correlator import AlertCorrelator
from src.agents.grafana_alert_analysis.tools.grafana_mcp import (
    get_dashboard_panel_queries,
    list_alerts,
    list_alert_rules,
    list_datasources,
    query_metrics,
    search_dashboards,
)


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _top_counts(items: Iterable[str], limit: int = 5) -> List[Tuple[str, int]]:
    c = Counter([i for i in items if i])
    return c.most_common(limit)


def _pick_default_prometheus_uid() -> str:
    datasources = list_datasources("prometheus")
    for ds in datasources:
        if isinstance(ds, dict) and (ds.get("isDefault") or ds.get("default")) and ds.get("uid"):
            return str(ds["uid"])
    if datasources and isinstance(datasources[0], dict) and datasources[0].get("uid"):
        return str(datasources[0]["uid"])
    raise RuntimeError("No Prometheus datasource found in Grafana")


def _resolve_dashboard_url() -> Optional[str]:
    direct = os.environ.get("GRAFANA_DASHBOARD_URL")
    if direct:
        return direct

    query = os.environ.get("GRAFANA_DASHBOARD_QUERY")
    if not query:
        return None

    matches = search_dashboards(query)
    if not matches:
        return None

    chosen = matches[0]
    uid = chosen.get("uid") if isinstance(chosen, dict) else None
    slug = chosen.get("slug") if isinstance(chosen, dict) else None

    if not uid:
        return None

    base = os.environ.get("GRAFANA_PUBLIC_URL") or os.environ.get("GRAFANA_URL")
    if not base:
        return None

    # If we don't have a slug, still form a URL; analyzer only needs the uid.
    slug = slug or "_"
    return f"{base.rstrip('/')}/d/{uid}/{slug}"


def _analyze_alerts(start: str, end: str, environment: str) -> AgentOutput:
    agent = GrafanaAlertAgent()
    return agent.run(
        AgentInput(
            start=start,
            end=end,
            environment=environment,
            filters=None,
            dashboard_url=None,
        )
    )


def _dashboard_probe(dashboard_url: str, start: str, end: str) -> Dict[str, Any]:
    # Extract uid from /d/<uid>/<slug>
    parts = [p for p in dashboard_url.split("/") if p]
    uid = None
    for i in range(len(parts) - 2):
        if parts[i] == "d":
            uid = parts[i + 1]
            break
    if not uid:
        raise ValueError("dashboard_url must contain /d/<uid>/...")

    prom_uid = _pick_default_prometheus_uid()
    panels = get_dashboard_panel_queries(uid)

    results: List[Dict[str, Any]] = []
    ok = 0
    series_total = 0

    for panel in panels:
        if not isinstance(panel, dict):
            continue
        title = _safe_str(panel.get("title"))
        query = panel.get("query")
        if not isinstance(query, str) or not query.strip():
            continue

        ds_uid = None
        ds_type = None
        if isinstance(panel.get("datasource"), dict):
            ds_uid = panel["datasource"].get("uid")
            ds_type = panel["datasource"].get("type")

        if isinstance(ds_type, str) and ds_type and ds_type != "prometheus":
            continue
        if not isinstance(ds_uid, str) or not ds_uid or ds_uid.startswith("$"):
            ds_uid = prom_uid

        try:
            data = query_metrics(query, start=start, end=end, datasource_uid=ds_uid)
            # query_prometheus often returns a list of series objects
            if isinstance(data, list):
                series = len(data)
            elif isinstance(data, dict):
                # best-effort: some implementations wrap results
                series = 0
                for key in ("data", "result", "series"):
                    if isinstance(data.get(key), list):
                        series = len(data[key])
                        break
            else:
                series = 0

            ok += 1
            series_total += series
            results.append({"panel": title, "ok": True, "series": series})
        except Exception as exc:  # noqa: BLE001
            results.append({"panel": title, "ok": False, "error": str(exc)})

    return {
        "dashboard_uid": uid,
        "panels": len(panels),
        "queries_executed": ok,
        "series_total": series_total,
        "panel_results": results,
    }


def _alerts_probe(start: str, end: str) -> Dict[str, Any]:
    # Alert rule state is point-in-time; start/end are included for report context.
    rules = list_alert_rules()
    firing = [r for r in rules if isinstance(r.get("state"), str) and r["state"].lower() == "firing"]

    def label(a: Dict[str, Any], k: str) -> str:
        labels = a.get("labels") if isinstance(a, dict) else None
        if isinstance(labels, dict):
            v = labels.get(k)
            if isinstance(v, str):
                return v
        return ""

    services = [label(a, "service") for a in firing]
    names = [label(a, "alertname") for a in firing]
    severities = [label(a, "severity") for a in firing]

    state_counts = Counter(
        [str(r.get("state")).lower() for r in rules if isinstance(r, dict) and isinstance(r.get("state"), str)]
    )

    return {
        "rules_total": len(rules),
        "state_counts": dict(state_counts),
        "firing": len(firing),
        "top_services": _top_counts(services, 5),
        "top_alertnames": _top_counts(names, 5),
        "top_severities": _top_counts(severities, 5),
    }


def main() -> None:
    start = os.environ.get("GRAFANA_FROM", "now-6h")
    end = os.environ.get("GRAFANA_TO", "now")
    environment = os.environ.get("ENVIRONMENT", "local")
    import json
    report = build_report(start=start, end=end, environment=environment)
    print(json.dumps(report, indent=2, ensure_ascii=False))


def build_report(*, start: str, end: str, environment: str) -> Dict[str, Any]:
    # 1) Datasources inventory
    all_ds = list_datasources(None)
    prom_ds = [d for d in all_ds if isinstance(d, dict) and d.get("type") == "prometheus"]

    # 2) Alerts analysis (agent heuristics with correlation)
    agent_out = _analyze_alerts(start, end, environment)
    
    # 2b) Explicit clustering of alert rules for detailed view
    alert_stats = _alerts_probe(start, end)
    rules = list_alert_rules()
    clusters = []
    if rules and len(rules) > 0:
        correlator = AlertCorrelator()
        clusters = correlator.cluster(rules)

    # 4) Dashboard probe (optional)
    dashboard_url = _resolve_dashboard_url()
    dashboard_probe = None
    if dashboard_url:
        dashboard_probe = _dashboard_probe(dashboard_url, start, end)

    report: Dict[str, Any] = {
        "time_range": {"from": start, "to": end},
        "environment": environment,
        "datasources": {
            "count": len(all_ds),
            "prometheus_count": len(prom_ds),
            "prometheus_uids": [d.get("uid") for d in prom_ds if isinstance(d, dict) and d.get("uid")],
        },
        "alerts": {
            "agent_summary": agent_out.summary,
            "recommendations": [r.model_dump() for r in agent_out.recommendations],
            "stats": alert_stats,
            "clusters": {
                "total": len(clusters),
                "items": clusters[:10] if len(clusters) > 10 else clusters,  # Limit to 10 for brevity
            },
        },
        "dashboard": {
            "url": dashboard_url,
            "probe": dashboard_probe,
        }
        if dashboard_url
        else {"url": None, "probe": None},
    }

    return report


if __name__ == "__main__":
    main()
