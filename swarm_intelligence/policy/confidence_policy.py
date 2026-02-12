from pydantic import BaseModel, Field


class ConfidencePolicy(BaseModel):
    """Pydantic model for confidence policy used across the system.

    Provides default values and helper accessors so it is compatible with
    `ConfidenceService` which expects `get_penalty_for_override()` and
    `get_reinforcement_for_success()` methods.
    """
    penalty_override: float = Field(0.1, ge=0.0, le=1.0)
    reinforcement_success: float = Field(0.05, ge=0.0, le=1.0)

    def get_penalty_for_override(self) -> float:
        return float(self.penalty_override)

    def get_reinforcement_for_success(self) -> float:
        return float(self.reinforcement_success)


class DefaultConfidencePolicy(ConfidencePolicy):
    """Default policy with sensible defaults for overrides and reinforcements."""
    penalty_override: float = Field(0.1, ge=0.0, le=1.0)
    reinforcement_success: float = Field(0.05, ge=0.0, le=1.0)
