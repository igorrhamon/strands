"""
Confidence Service 2.0 - Governed Confidence Engine
Implements weighted confidence based on alert types, historical accuracy, and risk levels.
Uses external YAML configuration for auditability.
"""

import logging
import os
import yaml
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ConfidenceFactor(BaseModel):
    name: str
    weight: float
    score: float

class ConfidenceResult(BaseModel):
    final_score: float
    factors: List[ConfidenceFactor]
    risk_adjusted_threshold: float
    is_above_threshold: bool
    version: str
    algorithm_hash: str = "sha256:conf_v2_stable"
    metadata: Dict[str, str] = Field(default_factory=dict)

class ConfidenceServiceV2:
    """
    Evolved Confidence Engine for Enterprise Readiness.
    """
    
    def __init__(self, config_path: str = "/home/ubuntu/strands/config/confidence_weights_v2026_02.yaml", historical_provider: Optional[Any] = None):
        self.config_path = config_path
        self.historical_provider = historical_provider
        self.config = self._load_config()
        self.version = self.config.get("version", "unknown")

    def _load_config(self) -> Dict:
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"[CONFIDENCE_V2] Failed to load config from {self.config_path}: {e}")
            # Fallback minimal config
            return {
                "weights": {"agent_base": 0.4, "evidence_quality": 0.3, "historical_accuracy": 0.3},
                "thresholds": {"low": 0.5, "medium": 0.7, "high": 0.85, "critical": 0.95},
                "category_multipliers": {"application": 1.0},
                "models": {"confidence_algorithm": "weighted_v2_fallback"}
            }

    def calculate_confidence(
        self,
        agent_score: float,
        agent_name: str,
        alert_category: str = "application",
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        evidence_quality: float = 1.0,
        historical_accuracy: Optional[float] = None
    ) -> ConfidenceResult:
        """
        Calculates a governed confidence score using the frozen weight matrix.
        """
        weights = self.config.get("weights", {})
        factors = []
        
        # 1. Agent Reported Score
        factors.append(ConfidenceFactor(name="agent_base", weight=weights.get("agent_base", 0.4), score=agent_score))
        
        # 2. Evidence Quality
        factors.append(ConfidenceFactor(name="evidence_quality", weight=weights.get("evidence_quality", 0.3), score=evidence_quality))
        
        # 3. Historical Accuracy
        if historical_accuracy is None and self.historical_provider:
            historical_accuracy = self.historical_provider.get_accuracy(agent_name)
        
        hist_score = historical_accuracy if historical_accuracy is not None else 0.7
        factors.append(ConfidenceFactor(name="historical_accuracy", weight=weights.get("historical_accuracy", 0.3), score=hist_score))
        
        # Calculate Weighted Average
        total_weight = sum(f.weight for f in factors)
        weighted_sum = sum(f.score * f.weight for f in factors)
        final_score = weighted_sum / total_weight
        
        # Apply Category Multiplier (Higher scrutiny for sensitive categories)
        multipliers = self.config.get("category_multipliers", {})
        multiplier = multipliers.get(alert_category.lower(), 1.0)
        if multiplier > 1.0:
            final_score = final_score * (1.0 / multiplier)
            
        # Risk-Adjusted Threshold
        thresholds = self.config.get("thresholds", {})
        threshold = thresholds.get(risk_level.value, 0.70)
        
        # Metadata for Auditability
        metadata = self.config.get("models", {}).copy()
        metadata["weight_matrix_version"] = self.version
        
        result = ConfidenceResult(
            final_score=round(final_score, 4),
            factors=factors,
            risk_adjusted_threshold=threshold,
            is_above_threshold=final_score >= threshold,
            version=self.version,
            metadata=metadata
        )
        
        logger.info(f"[CONFIDENCE_V2] Decision for {agent_name}: {result.final_score} (Threshold: {threshold})")
        return result

    def get_model_metadata(self) -> Dict[str, str]:
        metadata = self.config.get("models", {}).copy()
        metadata["weight_matrix_version"] = self.version
        return metadata
