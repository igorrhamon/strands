"""
Prometheus Queries - PromQL Builder

Builds and executes PromQL queries for metric trend analysis.
Uses the Grafana MCP server for Prometheus data source access.

Enhanced with exponential backoff retry logic (FR-012).
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryCallState,
    before_sleep_log,
)

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
            label_matchers = ", ".join(f'{k}="{v}"' for k, v in self._labels.items())
            selector = f"{self._metric}{{{label_matchers}}}"
        else:
            selector = self._metric

        # Apply rate if specified
        if self._rate_window:
            selector = f"rate({selector}[{self._rate_window}])"

        # Apply aggregation if specified
        if self._aggregation:
            if self._by_labels:
                by_clause = ", ".join(self._by_labels)
                selector = f"{self._aggregation} by ({by_clause}) ({selector})"
            else:
                selector = f"{self._aggregation}({selector})"

        return selector


class PrometheusClient:
    """
    Client for executing Prometheus queries via MCP.

    Enhanced with exponential backoff retry logic (FR-012):
    - 3 retries with delays: 1s, 2s, 4s
    - Retries on ConnectError and TimeoutException
    - Tracks retry count and query latency
    """

    def __init__(
        self,
        datasource_uid: Optional[str] = None,
        default_step_seconds: int = 30,  # Changed from 60 to 30 per research
        timeout_seconds: float = 5.0,
        base_url: Optional[str] = None,
    ):
        """
        Initialize Prometheus client.

        Args:
            datasource_uid: UID of Prometheus datasource in Grafana.
            default_step_seconds: Default step size for range queries (default: 30s).
            timeout_seconds: HTTP request timeout (default: 5s).
            base_url: Prometheus HTTP API base URL (for direct HTTP mode).
        """
        self._datasource_uid = datasource_uid
        self._default_step = default_step_seconds
        self._timeout = timeout_seconds
        self._base_url = base_url

        # Track retry metadata
        self._last_retry_count = 0
        self._last_query_latency_ms = 0

        # Initialize async HTTP client if base_url provided
        if base_url:
            transport = httpx.AsyncHTTPTransport(retries=0)  # Manual retry via tenacity
            self._http_client = httpx.AsyncClient(
                base_url=base_url,
                timeout=timeout_seconds,
                transport=transport,
            )
        else:
            self._http_client = None

    def close(self):
        """Close the HTTP client connection if initialized."""
        if self._http_client:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    task = asyncio.create_task(self._http_client.aclose())
                    # Keep a reference to prevent garbage collection
                    if not hasattr(self, '_cleanup_tasks'):
                        self._cleanup_tasks = []
                    self._cleanup_tasks.append(task)
                else:
                    asyncio.run(self._http_client.aclose())
            except Exception:
                pass  # Best-effort cleanup

    def query_instant(
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
            raw_result = self._call_mcp_query()

            return self._parse_instant_result(raw_result, time)

        except Exception as e:
            raise PrometheusQueryError(f"Instant query failed: {e}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),  # 1s, 2s, 4s
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def query_range_async(
        self,
        expr: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step_seconds: Optional[int] = None,
    ) -> list[DataPoint]:
        """
        Execute a range query over a time window with retry logic.

        Args:
            expr: PromQL expression.
            start: Query start time (defaults to 15 minutes ago).
            end: Query end time (defaults to now).
            step_seconds: Step size in seconds.

        Returns:
            List of DataPoint objects ordered by timestamp.

        Raises:
            PrometheusQueryError: If query fails after all retries.
        """
        if end is None:
            end = datetime.now(timezone.utc)
        if start is None:
            start = end - timedelta(minutes=15)
        if step_seconds is None:
            step_seconds = self._default_step

        query_start_time = time.perf_counter()

        try:
            logger.info(
                f"Range query: {expr} from {start.isoformat()} to {end.isoformat()} "
                f"(step={step_seconds}s)"
            )

            if self._http_client:
                # Direct HTTP API mode
                response = await self._http_client.get(
                    "/api/v1/query_range",
                    params={
                        "query": expr,
                        "start": int(start.timestamp()),
                        "end": int(end.timestamp()),
                        "step": f"{step_seconds}s",
                    },
                )
                response.raise_for_status()
                raw_result = response.json()
            else:
                # MCP mode (fallback)
                raw_result = self._call_mcp_query()

            data_points = self._parse_range_result(raw_result)

            # Track latency
            query_end_time = time.perf_counter()
            self._last_query_latency_ms = int((query_end_time - query_start_time) * 1000)

            logger.info(
                f"Query completed: {len(data_points)} points in {self._last_query_latency_ms}ms"
            )

            return data_points

        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Prometheus connection error: {e}")
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Metric not found: {expr}")
                return []  # Graceful degradation for missing metrics
            raise PrometheusQueryError(f"HTTP {e.response.status_code}: {e}") from e
        except Exception as e:
            raise PrometheusQueryError(f"Range query failed: {e}") from e

    def query_range(
        self,
        expr: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        step_seconds: Optional[int] = None,
    ) -> list[DataPoint]:
        """
        Execute a range query over a time window (synchronous wrapper).

        Args:
            expr: PromQL expression.
            start: Query start time (defaults to 15 minutes ago).
            end: Query end time (defaults to now).
            step_seconds: Step size in seconds.

        Returns:
            List of DataPoint objects ordered by timestamp.
        """
        # Synchronous wrapper for backward compatibility
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - raise to prevent returning Task
                raise RuntimeError(
                    "query_range called from async context; use query_range_async instead"
                )
        except RuntimeError:
            # No running loop, fall through to run synchronously
            pass

        return asyncio.run(self.query_range_async(expr, start, end, step_seconds))

    def _call_mcp_query(self) -> dict:
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

    def _parse_instant_result(self, raw: dict, time: datetime) -> list[DataPoint]:
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


async def query_multiple_metrics(
    client: PrometheusClient,
    service_id: str,
    metric_names: List[str],
    lookback_minutes: int = 15,
    step_seconds: int = 30,
) -> Dict[str, List[DataPoint]]:
    """
    Query multiple Prometheus metrics in parallel (FR-012 optimization).

    Uses asyncio.gather to fetch all metrics concurrently, reducing total
    query latency compared to sequential queries.

    Args:
        client: PrometheusClient instance with retry logic.
        service_id: Service identifier for label filtering.
        metric_names: List of metric types to query (e.g., ["cpu", "memory", "error_rate"]).
        lookback_minutes: Time window for queries (default: 15 minutes).
        step_seconds: Step interval for range queries (default: 30 seconds).

    Returns:
        Dictionary mapping metric_name to list of DataPoints.
        Exceptions from individual queries are caught and logged; failed metrics
        return empty lists (graceful degradation).

    Example:
        >>> client = PrometheusClient(base_url="http://prometheus:9090")
        >>> results = await query_multiple_metrics(
        ...     client, "api-gateway", ["cpu_usage", "memory_usage", "error_rate"]
        ... )
        >>> results["cpu_usage"]
        [DataPoint(timestamp=..., value=0.45), ...]
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=lookback_minutes)

    # Build and attempt PromQL queries for each metric with graceful fallbacks
    logger.info(
        f"Querying {len(metric_names)} metrics in parallel for service '{service_id}' "
        f"(window={lookback_minutes}m, step={step_seconds}s)"
    )

    async def try_candidates(metric_name: str) -> list[DataPoint]:
        """Try a set of candidate PromQL expressions for a metric until one returns data."""
        candidates: list[str] = []

        # Direct metric name convention: {service}_{metric}
        candidates.append(f"{service_id}_{metric_name}")

        # Alternate suffix convention: {service}_{metric}_usage
        candidates.append(f"{service_id}_{metric_name}_usage")

        # For cpu/memory prefer label-based PromQL builders
        if metric_name == "cpu":
            candidates.append(build_service_cpu_query(service_id))
        elif metric_name == "memory":
            candidates.append(build_service_memory_query(service_id))

        last_exc: Exception | None = None
        for expr in candidates:
            try:
                logger.debug(f"Trying PromQL '{expr}' for metric '{metric_name}'")
                res = await client.query_range_async(
                    expr=expr,
                    start=start_time,
                    end=end_time,
                    step_seconds=step_seconds,
                )
                if res:
                    logger.debug(f"PromQL '{expr}' returned {len(res)} points for '{metric_name}'")
                    return res
            except Exception as e:
                logger.warning(f"Candidate query '{expr}' failed: {e}")
                last_exc = e

        # If all candidates failed or returned empty, return empty list (caller logs)
        if last_exc:
            logger.debug(f"All candidates for '{metric_name}' failed, last error: {last_exc}")
        return []

    # Launch all candidate attempts in parallel (one coroutine per metric)
    tasks = [try_candidates(metric_name) for metric_name in metric_names]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Map results back to metric names
    metric_data: Dict[str, List[DataPoint]] = {}
    for metric_name, result in zip(metric_names, results):
        metric_data[metric_name] = result or []
        logger.debug(f"Metric '{metric_name}': {len(metric_data[metric_name])} data points")

    return metric_data
