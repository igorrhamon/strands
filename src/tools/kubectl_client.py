"""kubectl MCP wrapper (read-only operations only)"""
import httpx
from typing import List, Dict, Any, Optional
import logging

from src.config.settings import config


logger = logging.getLogger(__name__)


class KubectlMCPClient:
    """Wrapper for kubectl MCP operations (read-only)"""
    
    # Whitelist of safe read-only commands
    SAFE_COMMANDS = {
        "get", "describe", "logs", "top", "explain"
    }
    
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = base_url or config.mcp.kubectl_url
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def get_pods(
        self,
        namespace: str = "default",
        label_selector: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get pod information
        
        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector (e.g., "app=api")
            
        Returns:
            List of pod metadata dicts
        """
        try:
            params = {"namespace": namespace}
            if label_selector:
                params["label_selector"] = label_selector
            
            response = self.client.get(
                f"{self.base_url}/pods",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            pods = data.get("pods", [])
            logger.info(f"Fetched {len(pods)} pods from namespace {namespace}")
            return pods
            
        except httpx.HTTPError as e:
            logger.error(f"kubectl get pods failed: {e}")
            return []
    
    def get_logs(
        self,
        pod_name: str,
        namespace: str = "default",
        container: Optional[str] = None,
        tail_lines: int = 100
    ) -> str:
        """Get pod logs
        
        Args:
            pod_name: Pod name
            namespace: Kubernetes namespace
            container: Container name (if pod has multiple)
            tail_lines: Number of recent lines to fetch
            
        Returns:
            Log content as string
        """
        try:
            params = {
                "namespace": namespace,
                "tail_lines": tail_lines
            }
            if container:
                params["container"] = container
            
            response = self.client.get(
                f"{self.base_url}/pods/{pod_name}/logs",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            logs = data.get("logs", "")
            logger.info(f"Fetched {len(logs)} bytes of logs from {pod_name}")
            return logs
            
        except httpx.HTTPError as e:
            logger.error(f"kubectl logs failed: {e}")
            return ""
    
    def describe_resource(
        self,
        resource_type: str,
        resource_name: str,
        namespace: str = "default"
    ) -> Dict[str, Any]:
        """Describe a Kubernetes resource
        
        Args:
            resource_type: Resource type (e.g., "pod", "service")
            resource_name: Resource name
            namespace: Kubernetes namespace
            
        Returns:
            Resource description dict
        """
        try:
            response = self.client.get(
                f"{self.base_url}/describe/{resource_type}/{resource_name}",
                params={"namespace": namespace}
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            logger.error(f"kubectl describe failed: {e}")
            return {}
    
    def close(self) -> None:
        """Close HTTP client"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
