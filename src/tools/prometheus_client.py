"""Prometheus client for metrics queries"""
import httpx
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from src.config.settings import config


logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for Prometheus HTTP API with retry logic"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or config.prometheus.url
        self.timeout = config.prometheus.timeout_seconds
        self.max_retries = config.prometheus.max_retries
        self.retry_delays = config.prometheus.retry_delays
        self.client = httpx.Client(timeout=self.timeout)
    
    def query_range(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str = "1m"
    ) -> Dict[str, Any]:
        """Execute range query with exponential backoff retry
        
        Args:
            query: PromQL query string
            start_time: Start of time range
            end_time: End of time range
            step: Query resolution (e.g., "1m", "5m")
            
        Returns:
            Prometheus query result dict
            
        Raises:
            httpx.HTTPError: After all retries exhausted
        """
        params = {
            "query": query,
            "start": int(start_time.timestamp()),
            "end": int(end_time.timestamp()),
            "step": step
        }
        
        for attempt in range(self.max_retries):
            try:
                start = time.time()
                response = self.client.get(
                    f"{self.base_url}/api/v1/query_range",
                    params=params
                )
                latency_ms = int((time.time() - start) * 1000)
                
                response.raise_for_status()
                data = response.json()
                
                if data.get("status") != "success":
                    raise ValueError(f"Prometheus query failed: {data.get('error')}")
                
                logger.info(f"Prometheus query succeeded (latency: {latency_ms}ms)")
                return {
                    "result": data.get("data", {}).get("result", []),
                    "latency_ms": latency_ms
                }
                
            except (httpx.HTTPError, ValueError) as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delays[attempt]
                    logger.warning(f"Prometheus query failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"Prometheus query failed after {self.max_retries} attempts: {e}")
                    raise
    
    def query_instant(self, query: str, time_param: Optional[datetime] = None) -> Dict[str, Any]:
        """Execute instant query
        
        Args:
            query: PromQL query
            time_param: Evaluation timestamp (defaults to now)
            
        Returns:
            Prometheus query result dict
        """
        params = {"query": query}
        if time_param:
            params["time"] = int(time_param.timestamp())
        
        try:
            start = time.time()
            response = self.client.get(
                f"{self.base_url}/api/v1/query",
                params=params
            )
            latency_ms = int((time.time() - start) * 1000)
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "success":
                raise ValueError(f"Prometheus instant query failed: {data.get('error')}")
            
            return {
                "result": data.get("data", {}).get("result", []),
                "latency_ms": latency_ms
            }
            
        except (httpx.HTTPError, ValueError) as e:
            logger.error(f"Prometheus instant query failed: {e}")
            raise
    
    def close(self) -> None:
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
