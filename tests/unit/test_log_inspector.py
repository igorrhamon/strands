
import pytest
from unittest.mock import MagicMock, patch
from kubernetes.client.rest import ApiException

from src.agents.analysis.log_inspector import LogInspectorAgent

@pytest.fixture
def mock_k8s_client():
    """Mocks the Kubernetes API client."""
    with patch('src.agents.analysis.log_inspector.config.load_incluster_config'), \
         patch('src.agents.analysis.log_inspector.config.load_kube_config'), \
         patch('src.agents.analysis.log_inspector.client.CoreV1Api') as mock_core_v1_api:

        mock_api_instance = MagicMock()
        mock_core_v1_api.return_value = mock_api_instance
        yield mock_api_instance

def test_get_pod_logs_success(mock_k8s_client):
    """Tests that the agent correctly retrieves, parses, and formats logs."""
    # Arrange
    service_name = "payment-service"
    pod1_name = "payment-service-pod-1"
    pod2_name = "payment-service-pod-2"

    mock_pod1 = MagicMock()
    mock_pod1.metadata.name = pod1_name
    mock_pod2 = MagicMock()
    mock_pod2.metadata.name = pod2_name

    mock_service = MagicMock()
    mock_service.spec.selector = {"app": service_name}

    mock_k8s_client.read_namespaced_service.return_value = mock_service
    mock_k8s_client.list_namespaced_pod.return_value.items = [mock_pod1, mock_pod2]

    pod1_logs = "INFO: Starting up\nERROR: Database connection failed\n"
    pod2_logs = "INFO: All systems nominal\n"

    def read_log_side_effect(name, **kwargs):
        if name == pod1_name:
            return pod1_logs.encode('utf-8')
        return pod2_logs.encode('utf-8')

    mock_k8s_client.read_namespaced_pod_log.side_effect = read_log_side_effect

    agent = LogInspectorAgent()
    agent.v1 = mock_k8s_client

    # Act
    result = agent.get_pod_logs(service_name)

    # Assert
    assert result['hypothesis'] == "Errors detected in 1 of 2 pods for the service 'payment-service'."
    assert len(result['evidence']) == 1
    assert result['evidence'][0]['pod_name'] == pod1_name
    assert "ERROR: Database connection failed" in result['evidence'][0]['errors'][0]
    assert pod1_name in result['suggested_action']

def test_get_pod_logs_no_pods_found(mock_k8s_client):
    """Tests the structured output when no pods are found."""
    # Arrange
    service_name = "non-existent-service"

    mock_k8s_client.read_namespaced_service.side_effect = ApiException(status=404)
    mock_k8s_client.list_namespaced_pod.return_value.items = []

    agent = LogInspectorAgent()
    agent.v1 = mock_k8s_client

    # Act
    result = agent.get_pod_logs(service_name)

    # Assert
    assert result['hypothesis'] == f"Service '{service_name}' has no active pods."
    assert result['evidence'] == []
    assert "Verify the deployment status" in result['suggested_action']

def test_get_pod_logs_api_exception_on_log_read(mock_k8s_client):
    """Tests the structured output when an API exception occurs during log reading."""
    # Arrange
    service_name = "failing-service"
    pod1_name = "failing-service-pod-1"

    mock_pod1 = MagicMock()
    mock_pod1.metadata.name = pod1_name

    mock_service = MagicMock()
    mock_service.spec.selector = {"app": service_name}

    mock_k8s_client.read_namespaced_service.return_value = mock_service
    mock_k8s_client.list_namespaced_pod.return_value.items = [mock_pod1]
    mock_k8s_client.read_namespaced_pod_log.side_effect = ApiException(status=500, reason="Internal Server Error")

    agent = LogInspectorAgent()
    agent.v1 = mock_k8s_client

    # Act
    result = agent.get_pod_logs(service_name)

    # Assert
    assert "Errors detected in 1 of 1 pods" in result['hypothesis']
    assert len(result['evidence']) == 1
    assert result['evidence'][0]['pod_name'] == pod1_name
    assert "Could not retrieve logs" in result['evidence'][0]['errors'][0]

@patch('src.agents.analysis.log_inspector.LogInspectorAgent._find_pods_by_service')
def test_retry_logic_on_api_failure(mock_find_pods, mock_k8s_client):
    """Tests that the retry logic is invoked on API failure."""
    # Arrange
    service_name = "flaky-service"

    # Simulate failure on the first two calls, then success
    mock_find_pods.side_effect = [
        ApiException(status=503, reason="Service Unavailable"),
        ApiException(status=503, reason="Service Unavailable"),
        []  # Success, but no pods found
    ]

    agent = LogInspectorAgent()
    # We are patching the method on the class, so the instance will use the mock

    # Act
    agent.get_pod_logs(service_name)

    # Assert
    assert mock_find_pods.call_count == 3
