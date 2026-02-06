"""
Log Inspector Agent - Strands Agent Wrapper

Interacts with Kubernetes to fetch and analyze logs from pods.
"""

import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


class LogInspectorAgent:
    """
    Agent responsible for inspecting logs from Kubernetes pods.
    """

    AGENT_NAME = "LogInspectorAgent"

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
        Parse logs for keywords and stack traces.

        Args:
            logs: The logs to parse.

        Returns:
            A list of strings, where each string is an error or a stack trace.
        """
        keywords = ["ERROR", "CRITICAL", "Exception", "Panic"]
        lines = logs.split('\n')
        errors = []
        for i, line in enumerate(lines):
            for keyword in keywords:
                if keyword in line:
                    # Capture the line and the next few lines as context
                    context = "\n".join(lines[i:i+5])
                    errors.append(context)
                    break  # Move to the next line once a keyword is found
        return errors

    def _format_analysis(self, service_name: str, all_errors: List[Dict[str, Any]], total_pods: int) -> Dict[str, Any]:
        """
        Formats the analysis into the expected SwarmResult structure.

        Args:
            service_name: The name of the service.
            all_errors: A list of errors found in the logs.
            total_pods: The total number of pods for the service.

        Returns:
            A dictionary with the structured analysis.
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
