import os
import pytest
from src.state.incident_state_machine import IncidentStateMachine, IncidentState

def test_incident_state_transitions(tmp_path):
    # Use a temporary state file for the test
    test_file = tmp_path / "test_states.json"

    # Patch the STATE_FILE at instance level or class level for the test
    class TestStateMachine(IncidentStateMachine):
        STATE_FILE = str(test_file)

    sm = TestStateMachine()
    incident_id = f"inc-{os.urandom(4).hex()}"

    assert sm.get_state(incident_id) == IncidentState.OPEN

    # Valid transition
    assert sm.transition_to(incident_id, IncidentState.INVESTIGATING) is True
    assert sm.get_state(incident_id) == IncidentState.INVESTIGATING

    # Valid transition
    assert sm.transition_to(incident_id, IncidentState.MITIGATING) is True
    assert sm.get_state(incident_id) == IncidentState.MITIGATING

    # Invalid transition (MITIGATING -> CLOSED is not allowed in my simple machine)
    assert sm.transition_to(incident_id, IncidentState.CLOSED) is False
    assert sm.get_state(incident_id) == IncidentState.MITIGATING

    # Valid transition MITIGATING -> STABLE -> CLOSED
    assert sm.transition_to(incident_id, IncidentState.STABLE) is True
    assert sm.transition_to(incident_id, IncidentState.CLOSED) is True
    assert sm.get_state(incident_id) == IncidentState.CLOSED
