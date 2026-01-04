"""
Prometheus Queries - PromQL Builder

Builds and executes PromQL queries for metric trend analysis.
Uses the Grafana MCP server for Prometheus data source access.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models.metric_trend import DataPoint

logger = logging.getLogger(__name__)


class PrometheusQueryError(Exception):
    """Raised when Prometheus query fails."""
    pass


class PromQLBuilder:
    """
    Builder for constructing PromQL queries.
    
    Provides a fluent interface for building safe, structured queries.
    """
    
    def __init__(self, metric_name: str):
        """
        Initialize builder with metric name.
        
        Args:
            metric_name: Base metric name (e.g., 'cpu_usage', 'request_latency_seconds').
        """
        self._metric = metric_name
        self._labels: dict[str, str] = {}
        self._aggregation: Optional[str] = None
        self._rate_window: Optional[str] = None
        self._by_labels: list[str] = []
    
    def with_label(self, key: str, value: str) -> "PromQLBuilder":
        """Add a label filter."""
        self._labels[key] = value
        return self
    
    def with_labels(self, labels: dict[str, str]) -> "PromQLBuilder":
        """Add multiple label filters."""
        self._labels.update(labels)
        return self
    
    def rate(self, window: str = "5m") -> "PromQLBuilder":
        """Apply rate() function over window."""
        self._rate_window = window
        return self
    
    def sum_by(self, *labels: str) -> "PromQLBuilder":
        """Apply sum aggregation grouped by labels."""
        self._aggregation = "sum"
        self._by_labels = list(labels)
        return self
    
    def avg_by(self, *labels: str) -> "PromQLBuilder":
        """Apply avg aggregation grouped by labels."""
        self._aggregation = "avg"
        self._by_labels = list(labels)
        return self
    
    def max_by(self, *labels: str) -> "PromQLBuilder":
        """Apply max aggregation grouped by labels."""
        self._aggregation = "max"
        self._by_labels = list(labels)
        return self
    
    def build(self) -> str:
        """
        Build the final PromQL expression.
        
        Returns:
            Valid PromQL query string.
        """
        # Build base selector
        if self._labels:
            label_matchers = ", ".join(
                f'{k}="{v}"' for k, v in self._labels.items()
            )
            selector = f'{self._metric}{{{label_matchers}}}'
        else:
            selector = self._metric
        
        # Apply rate if specified
        if self._rate_window:
            selector = f'rate({selector}[{self._rate_window}])'
        
        # Apply aggregation if specified
        if self._aggregation:
            if self._by_labels:
                by_clause = ", ".join(self._by_labels)
                selector = f'{self._aggregation} by ({by_clause}) ({selector})'
            else:
                selector = f'{self._aggregation}({selector})'
        
        return selector


class PrometheusClient:
    """
    Client for executing Prometheus queries via MCP.
    
    Wraps MCP tool calls for Prometheus data retrieval.
    """
    
    def __init__(
        self,
        datasource_uid: Optional[str] = None,
        default_step_seconds: int = 60,
    ):
        """
        Initialize Prometheus client.
        
        Args:
            datasource_uid: UID of Prometheus datasource in Grafana.
            default_step_seconds: Default step size for range queries.
        """
        self._datasource_uid = datasource_uid
        self._default_step = default_step_seconds
    
    async def query_instant(
        self,
        expr: str,
        time: Optional[datetime] = None,
    ) -> list[DataPoint]:
        """
        Execute an instant query at a single point in time.
        
        Args:
            expr: PromQL expression.
            time: Query time (defaults to now).
        
        Returns:
            List of DataPoint objects.
        """
        if time is None:
            time = datetime.now(timezone.utc)
        
        try:
            # In real implementation, call mcp_sgn-agendamen_query_prometheus
            # with queryType="instant"
            logger.info(f"Instant query: {expr} at {time.isoformat()}")
            
            # Placeholder - real implementation would parse MCP response
            raw_result = await self._call_mcp_query(
                expr=expr,
                query_type="instant",
                time=time,
            )
            
            return self._parse_instant_result(raw_result, time)
        
        except Exception as e:
            raise PrometheusQueryError(f"Instant query failed: {e}") from e
    
    async def query_range(
        self,
        expr: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step_seconds: Optional[int] = None,
    ) -> list[DataPoint]:
        """
        Execute a range query over a time window.
        
        Args:
            expr: PromQL expression.
            start: Query start time (defaults to 15 minutes ago).
            end: Query end time (defaults to now).
            step_seconds: Step size in seconds.
        
        Returns:
            List of DataPoint objects ordered by timestamp.
        """
        if end is None:
            end = datetime.now(timezone.utc)
        if start is None:
            start = end - timedelta(minutes=15)
        if step_seconds is None:
            step_seconds = self._default_step
        
        try:
            logger.info(
                f"Range query: {expr} from {start.isoformat()} to {end.isoformat()}"
            )
            
            raw_result = await self._call_mcp_query(
                expr=expr,
                query_type="range",
                start=start,
                end=end,
                step_seconds=step_seconds,
            )
            
            return self._parse_range_result(raw_result)
        
        except Exception as e:
            raise PrometheusQueryError(f"Range query failed: {e}") from e
    
    async def _call_mcp_query(
        self,
        expr: str,
        query_type: str,
        time: Optional[datetime] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step_seconds: Optional[int] = None,
    ) -> dict:
        """
        Internal method to call MCP Prometheus tool.
        
        Returns raw query result from MCP.
        """
        # Real implementation would call:
        # mcp_sgn-agendamen_query_prometheus(
        #     datasourceUid=self._datasource_uid,
        #     expr=expr,
        #     queryType=query_type,
        #     startTime=start.isoformat() if start else None,
        #     endTime=end.isoformat() if end else None,
        #     stepSeconds=step_seconds,
        # )
        return {"data": {"result": []}}
    
    def _parse_instant_result(
        self, raw: dict, time: datetime
    ) -> list[DataPoint]:
        """Parse instant query result to DataPoints."""
        data_points = []
        
        result = raw.get("data", {}).get("result", [])
        for item in result:
            value = item.get("value", [])
            if len(value) >= 2:
                data_points.append(
                    DataPoint(
                        timestamp=time,
                        value=float(value[1]),
                    )
                )
        
        return data_points
    
    def _parse_range_result(self, raw: dict) -> list[DataPoint]:
        """Parse range query result to DataPoints."""
        data_points = []
        
        result = raw.get("data", {}).get("result", [])
        for item in result:
            values = item.get("values", [])
            for ts, val in values:
                data_points.append(
                    DataPoint(
                        timestamp=datetime.fromtimestamp(float(ts), tz=timezone.utc),
                        value=float(val),
                    )
                )
        
        # Sort by timestamp
        data_points.sort(key=lambda dp: dp.timestamp)
        return data_points


def build_service_cpu_query(service: str, rate_window: str = "5m") -> str:
    """Build a CPU usage query for a service."""
    return (
        PromQLBuilder("container_cpu_usage_seconds_total")
        .with_label("service", service)
        .rate(rate_window)
        .sum_by("service")
        .build()
    )


def build_service_memory_query(service: str) -> str:
    """Build a memory usage query for a service."""
    return (
        PromQLBuilder("container_memory_usage_bytes")
        .with_label("service", service)
        .sum_by("service")
        .build()
    )


def build_request_rate_query(service: str, rate_window: str = "5m") -> str:
    """Build a request rate query for a service."""
    return (
        PromQLBuilder("http_requests_total")
        .with_label("service", service)
        .rate(rate_window)
        .sum_by("service", "status_code")
        .build()
    )
