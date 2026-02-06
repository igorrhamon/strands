"""
Log Inspector Agent - Strands Agent Wrapper

Interacts with Kubernetes to fetch and analyze logs from pods.
"""

import logging
from datetime import datetime, timezone
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed

from src.models.alert import NormalizedAlert
from src.models.swarm import SwarmResult, EvidenceItem, EvidenceType

logger = logging.getLogger(__name__)


class LogInspectorAgent:
    """
    Agent responsible for inspecting logs from Kubernetes pods.
    """

    AGENT_NAME = "LogInspectorAgent"
    agent_id = "log_inspector"

    def __init__(self):
        """
        Initialize Log Inspector agent.
        """
        try:
            # Try to load in-cluster configuration
            config.load_incluster_config()
        except config.ConfigException:
            # Fallback to kube-config for local development
            config.load_kube_config()

        self.v1 = client.CoreV1Api()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def get_pod_logs(self, service_name: str, namespace: str = "default", since_seconds: int = 600) -> Dict[str, Any]:
        """
        Get logs from pods for a given service and return a structured analysis.

        Args:
            service_name: The name of the service.
            namespace: The namespace of the service.
            since_seconds: The time in seconds to look back for logs.

        Returns:
            A dictionary containing the analysis of the logs.
        """
        pods = self._find_pods_by_service(service_name, namespace)
        if not pods:
            return {
                "hypothesis": f"Service '{service_name}' has no active pods.",
                "evidence": [],
                "suggested_action": "Verify the deployment status and check for scaling issues."
            }

        all_errors = []
        for pod in pods:
            try:
                logs = self.v1.read_namespaced_pod_log(
                    name=pod.metadata.name,
                    namespace=namespace,
                    since_seconds=since_seconds,
                    _preload_content=True,
                ).decode("utf-8")
                errors = self._parse_logs(logs)
                if errors:
                    all_errors.append({"pod": pod.metadata.name, "errors": errors})
            except ApiException as e:
                logger.error(f"Error reading logs for pod {pod.metadata.name}: {e}")
                all_errors.append({"pod": pod.metadata.name, "errors": [f"Could not retrieve logs: {e}"]})

        return self._format_analysis(service_name, all_errors, len(pods))

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _find_pods_by_service(self, service_name: str, namespace: str) -> List[Any]:
        """
        Find pods by service name.

        Args:
            service_name: The name of the service.
            namespace: The namespace of the service.

        Returns:
            A list of pod objects.
        """
        try:
            # First, try to get the service to find its labels
            service = self.v1.read_namespaced_service(name=service_name, namespace=namespace)
            label_selector = ",".join([f"{k}={v}" for k, v in service.spec.selector.items()])
            pods = self.v1.list_namespaced_pod(namespace, label_selector=label_selector)
            return pods.items
        except ApiException as e:
            if e.status == 404:
                # If service not found, fallback to common labels
                common_labels = [f"app={service_name}", f"app.kubernetes.io/name={service_name}"]
                for label in common_labels:
                    try:
                        pods = self.v1.list_namespaced_pod(namespace, label_selector=label)
                        if pods.items:
                            return pods.items
                    except ApiException:
                        continue
            logger.error(f"Error finding pods for service {service_name}: {e}")
            return []

    def _parse_logs(self, logs: str) -> List[str]:
        """
        Parse logs for keywords and multi-line stack traces.

        Args:
            logs: The logs to parse.

        Returns:
            A list of strings, where each string is an error block or a stack trace.
        """
        keywords = ["ERROR", "CRITICAL", "Exception", "Panic", "Traceback"]
        lines = logs.split('\n')
        errors = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            # Check if line contains a keyword AND is not part of an existing stack trace context
            # (Simple heuristic: usually keywords start the line or follow a timestamp)
            if any(keyword in line for keyword in keywords):
                # Found an error start. Capture it.
                error_block = [line]
                i += 1
                
                # Capture subsequent lines until we hit a new log entry
                while i < len(lines):
                    next_line = lines[i]
                    stripped = next_line.strip()
                    
                    # Heuristic: A new log entry usually starts with a timestamp (202X-...) or a log level (INFO, DEBUG, WARN, ERROR)
                    # If it doesn't start with these, assume it's part of the previous error (stack trace, multi-line message)
                    is_new_log_entry = (
                        stripped.startswith(("202", "INFO", "DEBUG", "WARN", "WARNING")) or
                        (stripped.startswith("ERROR") and "at " not in stripped) or # ERROR could be start of new error, unless it's inside a stack trace (rare)
                        stripped.startswith("CRITICAL")
                    )
                    
                    # Special case: If the line is indented, it's definitely a continuation (stack trace)
                    is_indented = next_line.startswith((' ', '\t'))
                    
                    if is_indented or not is_new_log_entry:
                        error_block.append(next_line)
                        i += 1
                    else:
                        break
                
                errors.append("\n".join(error_block))
                # Continue the outer loop from the current i, skipping the increment below
                continue

            i += 1
                
        return errors

    async def analyze(self, alert: NormalizedAlert) -> SwarmResult:
        """
        Analyze logs for the service mentioned in the alert.
        
        Args:
            alert: The normalized alert object.
            
        Returns:
            SwarmResult containing the analysis.
        """
        logger.info(f"[{self.agent_id}] Analyzing logs for {alert.service}...")
        
        # Call the synchronous method (or refactor to async if k8s client supports it)
        # For now, we wrap the result in SwarmResult
        analysis = self.get_pod_logs(alert.service)
        
        # Convert dictionary evidence to EvidenceItem objects
        evidence_items = []
        for ev in analysis.get("evidence", []):
            # Create a description from the log snippets
            snippets = "\n".join(ev.get("log_snippets", []))
            evidence_items.append(EvidenceItem(
                type=EvidenceType.LOG,
                description=f"Logs from pod {ev.get('pod_name')}:\n{snippets[:500]}...", # Truncate for brevity
                source_url=f"kubectl logs {ev.get('pod_name')}",
                timestamp=datetime.now(timezone.utc),
                metadata={"pod": ev.get("pod_name"), "full_logs": snippets}
            ))
            
        return SwarmResult(
            agent_id=self.agent_id,
            hypothesis=analysis.get("hypothesis", "No analysis performed."),
            confidence=0.9 if analysis.get("evidence") else 0.5, # High confidence if we found errors
            evidence=evidence_items,
            suggested_actions=[analysis.get("suggested_action", "Check logs manually.")]
        )

    def _format_analysis(self, service_name: str, all_errors: List[Dict[str, Any]], total_pods: int) -> Dict[str, Any]:
        """
        Formats the analysis into a dictionary (internal helper).
        """
        if not all_errors:
            return {
                "hypothesis": f"No critical errors found in the logs for service '{service_name}'.",
                "evidence": [],
                "suggested_action": "No immediate action required. Continue monitoring."
            }

        error_pods_count = len(all_errors)
        hypothesis = (
            f"Errors detected in {error_pods_count} of {total_pods} pods for the service '{service_name}'."
        )

        evidence = []
        for error_info in all_errors:
            evidence.append({
                "pod_name": error_info['pod'],
                "log_snippets": error_info['errors']
            })

        suggested_action = (
            f"Investigate the health of the affected pods: {[e['pod'] for e in all_errors]}. "
            "Consider restarting the deployment if the errors persist."
        )

        return {
            "hypothesis": hypothesis,
            "evidence": evidence,
            "suggested_action": suggested_action
        }
