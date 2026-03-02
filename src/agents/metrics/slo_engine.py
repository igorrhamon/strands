"""
SLO Engine - Computes SLIs, Error Budgets, and Burn Rates.
"""

import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class SLODefinition(BaseModel):
    service: str
    target: float = 0.999 # 99.9%
    window_days: int = 30

class SLOEngine:
    """
    Computes SRE metrics based on incoming telemetry.
    """
    def __init__(self, definitions: Optional[List[SLODefinition]] = None):
        self.definitions = {d.service: d for d in (definitions or [])}

    def compute_burn_rate(self, service: str, current_error_rate: float) -> float:
        """
        Calculates the error budget burn rate.
        Burn Rate = Current Error Rate / (1 - SLO Target)
        A burn rate of 1.0 means the budget is being consumed at a rate that will
        exhaust it exactly at the end of the window.
        """
        slo = self.definitions.get(service)
        if not slo:
            # Default to 99.9% if not defined
            slo = SLODefinition(service=service, target=0.999)

        allowed_error_rate = 1.0 - slo.target
        if allowed_error_rate == 0:
            return 0.0

        burn_rate = current_error_rate / allowed_error_rate
        return burn_rate

    def compute_sli(self, success_count: int, total_count: int) -> float:
        if total_count == 0:
            return 1.0
        return success_count / total_count

    def compute_remaining_budget(self, service: str, accumulated_errors: int, total_budget_events: int) -> float:
        slo = self.definitions.get(service)
        if not slo:
            return 1.0

        used_budget = accumulated_errors / (total_budget_events * (1.0 - slo.target))
        return max(0.0, 1.0 - used_budget)
