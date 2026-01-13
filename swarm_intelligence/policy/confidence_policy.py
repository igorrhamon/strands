
from abc import ABC, abstractmethod
from typing import Dict, Any

class ConfidencePolicy(ABC):
    """
    Abstract base class for policies governing confidence adjustments.
    """
    version: str = "1.0"

    @abstractmethod
    def get_penalty_for_override(self) -> float:
        pass

    @abstractmethod
    def get_reinforcement_for_success(self) -> float:
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {"policy_name": self.__class__.__name__, "version": self.version}

class DefaultConfidencePolicy(ConfidencePolicy):
    """
    A default, simple confidence policy.
    """
    version = "1.0"

    def get_penalty_for_override(self) -> float:
        return 0.1

    def get_reinforcement_for_success(self) -> float:
        return 0.05
