"""
Incident State Machine - Manages the lifecycle of an incident.
"""

import logging
import json
import os
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

    Persistence Interface:
    In production, this class should interact with a persistent store (e.g. Redis, Neo4j, or PG).
    Baseline: Simple JSON file persistence.
    """
    STATE_FILE = "run/incident_states.json"

    def __init__(self, persistence_adapter: Optional[Any] = None):
        self._incident_states: Dict[str, IncidentState] = {}
        self._last_update: Dict[str, datetime] = {}
        self._persistence = persistence_adapter
        self._load_all_states()

    def _load_all_states(self):
        """Loads states from persistence."""
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self._incident_states = {k: IncidentState(v) for k, v in data.items()}
                logger.info(f"Loaded {len(self._incident_states)} incident states from {self.STATE_FILE}")
            except Exception as e:
                logger.error(f"Failed to load state file: {e}")

    def _save_state(self, incident_id: str, state: IncidentState):
        """Saves state to persistence."""
        try:
            os.makedirs(os.path.dirname(self.STATE_FILE), exist_ok=True)
            # Reload to avoid overwriting concurrent changes in multi-agent setup
            current_data = {}
            if os.path.exists(self.STATE_FILE):
                with open(self.STATE_FILE, 'r') as f:
                    current_data = json.load(f)

            current_data[incident_id] = state.value
            with open(self.STATE_FILE, 'w') as f:
                json.dump(current_data, f)
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")

    def get_state(self, incident_id: str) -> IncidentState:
        # Check cache/memory first, then persistence if needed
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
            self._save_state(incident_id, new_state)
            return True
        else:
            logger.warning(f"Invalid transition for {incident_id}: {current_state} -> {new_state}")
            return False

    def can_mitigate(self, incident_id: str) -> bool:
        return self.get_state(incident_id) == IncidentState.INVESTIGATING
