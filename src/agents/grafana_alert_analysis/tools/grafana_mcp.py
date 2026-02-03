from __future__ import annotations

import os
import json
import atexit
from itertools import count
from typing import Any, Dict, List, Optional

from mcp.client.stdio import StdioServerParameters, stdio_client
from strands.tools.mcp.mcp_client import MCPClient
from strands_tools.mcp_client import mcp_client


_CONNECTION_ID = os.environ.get("GRAFANA_MCP_CONNECTION_ID", "grafana")
_CLIENT: MCPClient | None = None
_CLIENT_TOOL_USE_ID = count(1)


def _extract_first_text(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(result, dict):
        content = result.get("content", []) or []

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and "text" in item:
                return str(item["text"])
            text = getattr(item, "text", None)
            if isinstance(text, str):
                return text

    return str(result)


def _extract_first_json(result: Any) -> Any:
    content = getattr(result, "content", None)
    if isinstance(result, dict):
        content = result.get("content", []) or []

    if not isinstance(content, list):
        return None

    for item in content:
        if isinstance(item, dict) and "json" in item:
            return item["json"]

        text: Any = None
        if isinstance(item, dict):
            text = item.get("text")
        else:
            text = getattr(item, "text", None)

        if isinstance(text, str):
            stripped = text.strip()
            if stripped.startswith("{") or stripped.startswith("["):
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    pass

    return None


def _connect_streamable_or_sse(transport: str, timeout_seconds: float) -> Dict[str, Any]:
    server_url = os.environ.get("GRAFANA_MCP_SERVER_URL")
    if not server_url:
        raise RuntimeError("GRAFANA_MCP_SERVER_URL is required when using streamable_http/sse transport")

    headers: Dict[str, str] = {}
    token = (
        os.environ.get("GRAFANA_API_KEY")
        or os.environ.get("GRAFANA_TOKEN")
        or os.environ.get("GRAFANA_SERVICE_ACCOUNT_TOKEN")
    )
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return mcp_client(
        action="connect",
        connection_id=_CONNECTION_ID,
        transport=transport,
        server_url=server_url,
        headers=headers or None,
        timeout=timeout_seconds,
    )


def _connect_stdio() -> Dict[str, Any]:
    command = os.environ.get("GRAFANA_MCP_COMMAND")
    if not command:
        raise RuntimeError("GRAFANA_MCP_COMMAND is required when using stdio transport")

    args_json = os.environ.get("GRAFANA_MCP_ARGS_JSON")
    if args_json:
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GRAFANA_MCP_ARGS_JSON must be a JSON array of strings") from exc
        if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            raise RuntimeError("GRAFANA_MCP_ARGS_JSON must be a JSON array of strings")
    else:
        args_raw = os.environ.get("GRAFANA_MCP_ARGS", "")
        args = [a for a in args_raw.split(" ") if a]

    # Optional: pass Grafana connection details to the MCP server process
    env: Dict[str, str] = {}

    # Allow using a different Grafana URL for the MCP server process (e.g. container-network URL)
    # while keeping the host Grafana URL available for other tooling.
    grafana_url = os.environ.get("GRAFANA_MCP_GRAFANA_URL") or os.environ.get("GRAFANA_URL")
    if grafana_url:
        env["GRAFANA_URL"] = grafana_url

    for key in ("GRAFANA_API_KEY", "GRAFANA_TOKEN", "GRAFANA_SERVICE_ACCOUNT_TOKEN"):
        val = os.environ.get(key)
        if val:
            env[key] = val

    return mcp_client(
        action="connect",
        connection_id=_CONNECTION_ID,
        transport="stdio",
        command=command,
        args=args or None,
        env=env or None,
    )

def _ensure_stdio_client() -> MCPClient:
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    command = os.environ.get("GRAFANA_MCP_COMMAND")
    if not command:
        raise RuntimeError("GRAFANA_MCP_COMMAND is required when using stdio transport")

    args_json = os.environ.get("GRAFANA_MCP_ARGS_JSON")
    if args_json:
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GRAFANA_MCP_ARGS_JSON must be a JSON array of strings") from exc
        if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            raise RuntimeError("GRAFANA_MCP_ARGS_JSON must be a JSON array of strings")
    else:
        args_raw = os.environ.get("GRAFANA_MCP_ARGS", "")
        args = [a for a in args_raw.split(" ") if a]

    env: Dict[str, str] = {}
    grafana_url = os.environ.get("GRAFANA_MCP_GRAFANA_URL") or os.environ.get("GRAFANA_URL")
    if grafana_url:
        env["GRAFANA_URL"] = grafana_url

    for key in ("GRAFANA_API_KEY", "GRAFANA_TOKEN", "GRAFANA_SERVICE_ACCOUNT_TOKEN"):
        val = os.environ.get(key)
        if val:
            env[key] = val

    params = StdioServerParameters(command=command, args=args, env=env or None)

    def _transport_callable():
        return stdio_client(params)

    client = MCPClient(_transport_callable)
    client.__enter__()

    def _shutdown() -> None:
        try:
            client.__exit__(None, None, None)
        except Exception:
            pass

    atexit.register(_shutdown)
    _CLIENT = client
    return _CLIENT


def _call_tool(tool_name: str, tool_args: Dict[str, Any]) -> Any:
    transport = os.environ.get("GRAFANA_MCP_TRANSPORT")

    # If transport isn't explicitly set, infer it. This makes local usage work out-of-the-box
    # when the user configured stdio via GRAFANA_MCP_COMMAND/GRAFANA_MCP_ARGS(_JSON).
    if not transport:
        if os.environ.get("GRAFANA_MCP_COMMAND") or os.environ.get("GRAFANA_MCP_ARGS_JSON") or os.environ.get("GRAFANA_MCP_ARGS"):
            transport = "stdio"
        else:
            transport = "streamable_http"

    # Prefer a persistent in-process MCPClient for stdio to avoid re-spawning the Docker MCP
    # server on every call.
    if transport == "stdio":
        client = _ensure_stdio_client()
        tool_use_id = str(next(_CLIENT_TOOL_USE_ID))
        result = client.call_tool_sync(tool_use_id=tool_use_id, name=tool_name, arguments=tool_args)
        if getattr(result, "is_error", False):
            raise RuntimeError(_extract_first_text(result))
        return _extract_first_json(result)

    timeout_seconds = float(os.environ.get("GRAFANA_MCP_TIMEOUT", "5"))
    if transport in {"streamable_http", "sse"}:
        res = _connect_streamable_or_sse(transport, timeout_seconds)
        if res.get("status") != "success":
            raise RuntimeError(f"Failed to connect to Grafana MCP: {_extract_first_text(res)}")
    else:
        raise RuntimeError(f"Unsupported GRAFANA_MCP_TRANSPORT: {transport}. Supported: stdio, sse, streamable_http")

    res = mcp_client(
        action="call_tool",
        connection_id=_CONNECTION_ID,
        tool_name=tool_name,
        tool_args=tool_args,
    )
    if res.get("status") == "error":
        raise RuntimeError(_extract_first_text(res))
    return _extract_first_json(res)


def list_alerts(
    status: str,
    start_time: str,
    end_time: str,
    labels: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Compatibility shim.

    The MCP server does not expose a generic `list_alerts` tool; instead it exposes `list_alert_rules`.
    This function calls `list_alert_rules` and filters by current state.

    Note: `start_time`/`end_time` are ignored because alert rule state is point-in-time.
    """
    rules = list_alert_rules(label_filters=labels)
    desired = str(status or "").lower()
    if not desired:
        return rules

    filtered: List[Dict[str, Any]] = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        state = r.get("state")
        if isinstance(state, str) and state.lower() == desired:
            filtered.append(r)
    return filtered


def list_alert_rules(
    datasource_uid: Optional[str] = None,
    label_filters: Optional[Dict[str, str]] = None,
    limit: int = 100,
    page: int = 1,
) -> List[Dict[str, Any]]:
    """List Grafana alert rules via MCP (read-only)."""
    payload: Dict[str, Any] = {"limit": limit, "page": page}
    if datasource_uid:
        payload["datasourceUid"] = datasource_uid

    # Map simple dict filters to the MCP label selector schema.
    if label_filters:
        selectors = []
        for name, value in label_filters.items():
            if isinstance(name, str) and isinstance(value, str) and name and value:
                selectors.append({"filters": [{"name": name, "type": "=", "value": value}]})
        if selectors:
            payload["label_selectors"] = selectors

    data = _call_tool("list_alert_rules", payload)

    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict)]

    # Be defensive about alternate shapes.
    if isinstance(data, dict):
        for key in ("rules", "alertRules", "items"):
            if isinstance(data.get(key), list):
                return [d for d in data[key] if isinstance(d, dict)]

    return []


def get_alert_history(fingerprint: str) -> List[Dict[str, Any]]:
    """Get alert details/history from Grafana via MCP (read-only)."""
    data = _call_tool("get_alert_details", {"alertId": fingerprint})
    if isinstance(data, dict) and "history" in data and isinstance(data["history"], list):
        return data["history"]
    if isinstance(data, list):
        return data
    return []


def query_metrics(promql: str, start: str, end: str, datasource_uid: str, step_seconds: int = 60) -> Any:
    """Query Prometheus metrics via Grafana MCP (read-only)."""
    return _call_tool(
        "query_prometheus",
        {
            "datasourceUid": datasource_uid,
            "expr": promql,
            "startTime": start,
            "endTime": end,
            "queryType": "range",
            "stepSeconds": step_seconds,
        },
    )


def search_dashboards(query: str) -> List[Dict[str, Any]]:
    data = _call_tool("search_dashboards", {"query": query})
    if isinstance(data, list):
        return data
    return []


def get_dashboard_panel_queries(dashboard_uid: str) -> List[Dict[str, Any]]:
    data = _call_tool("get_dashboard_panel_queries", {"uid": dashboard_uid})
    if isinstance(data, list):
        return data
    return []


def list_datasources(ds_type: Optional[str] = None) -> List[Dict[str, Any]]:
    payload: Dict[str, Any] = {}
    if ds_type:
        payload["type"] = ds_type
    data = _call_tool("list_datasources", payload)
    if isinstance(data, list):
        return data
    return []
