"""
Incident State Machine - Manages the lifecycle of an incident.
"""

import logging
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class IncidentState(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    STABLE = "STABLE"
    CLOSED = "CLOSED"

class IncidentStateMachine:
    """
    Manages transitions between incident states.
    Prevents duplicate actions and ensures logical flow.
    """
    def __init__(self):
        self._incident_states: Dict[str, IncidentState] = {}
        self._last_update: Dict[str, datetime] = {}

    def get_state(self, incident_id: str) -> IncidentState:
        return self._incident_states.get(incident_id, IncidentState.OPEN)

    def transition_to(self, incident_id: str, new_state: IncidentState) -> bool:
        current_state = self.get_state(incident_id)

        if current_state == new_state:
            return True

        # Define valid transitions
        valid_transitions = {
            IncidentState.OPEN: [IncidentState.INVESTIGATING, IncidentState.CLOSED],
            IncidentState.INVESTIGATING: [IncidentState.MITIGATING, IncidentState.STABLE, IncidentState.CLOSED],
            IncidentState.MITIGATING: [IncidentState.STABLE, IncidentState.INVESTIGATING],
            IncidentState.STABLE: [IncidentState.CLOSED, IncidentState.INVESTIGATING],
            IncidentState.CLOSED: [IncidentState.OPEN] # Re-opening
        }

        if new_state in valid_transitions.get(current_state, []):
            logger.info(f"Incident {incident_id} transitioning: {current_state} -> {new_state}")
            self._incident_states[incident_id] = new_state
            self._last_update[incident_id] = datetime.now(timezone.utc)
            return True
        else:
            logger.warning(f"Invalid transition for {incident_id}: {current_state} -> {new_state}")
            return False

    def can_mitigate(self, incident_id: str) -> bool:
        return self.get_state(incident_id) == IncidentState.INVESTIGATING
