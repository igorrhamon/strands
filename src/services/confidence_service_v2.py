"""
Confidence Service 2.0 - Governed Confidence Engine
Implements weighted confidence based on alert types, historical accuracy, and risk levels.
"""

import logging
import numpy as np
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
    version: str = "2.0.0"
    algorithm_hash: str = "sha256:conf_v2_stable"

class ConfidenceServiceV2:
    """
    Evolved Confidence Engine for Enterprise Readiness.
    Features:
    1. Weighted base scores by alert type.
    2. Risk-adjusted thresholds.
    3. Historical accuracy integration.
    4. Formal versioning for auditability.
    """
    
    # Default thresholds based on Risk Level
    THRESHOLDS = {
        RiskLevel.LOW: 0.50,
        RiskLevel.MEDIUM: 0.70,
        RiskLevel.HIGH: 0.85,
        RiskLevel.CRITICAL: 0.95
    }
    
    # Weights for different alert categories
    CATEGORY_WEIGHTS = {
        "security": 1.2,   # Security alerts need higher scrutiny
        "database": 1.1,
        "network": 1.0,
        "application": 0.9,
        "infrastructure": 0.8
    }

    def __init__(self, historical_provider: Optional[Any] = None):
        self.historical_provider = historical_provider
        self.version = "2.0.0"

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
        Calculates a governed confidence score.
        """
        factors = []
        
        # 1. Agent Reported Score (Base)
        factors.append(ConfidenceFactor(name="agent_base", weight=0.4, score=agent_score))
        
        # 2. Evidence Quality
        factors.append(ConfidenceFactor(name="evidence_quality", weight=0.3, score=evidence_quality))
        
        # 3. Historical Accuracy (if available)
        if historical_accuracy is None and self.historical_provider:
            # Fallback to provider if not passed directly
            historical_accuracy = self.historical_provider.get_accuracy(agent_name)
        
        hist_score = historical_accuracy if historical_accuracy is not None else 0.7 # Default 70%
        factors.append(ConfidenceFactor(name="historical_accuracy", weight=0.3, score=hist_score))
        
        # Calculate Weighted Average
        total_weight = sum(f.weight for f in factors)
        weighted_sum = sum(f.score * f.weight for f in factors)
        final_score = weighted_sum / total_weight
        
        # Apply Category Multiplier (Normalization)
        multiplier = self.CATEGORY_WEIGHTS.get(alert_category.lower(), 1.0)
        # We don't just multiply the score (could exceed 1.0), we adjust the strictness
        # or slightly dampen/boost the final score
        if multiplier > 1.0:
            final_score = final_score * (1.0 / multiplier) # Higher scrutiny = lower final score for same inputs
            
        # Risk-Adjusted Threshold
        threshold = self.THRESHOLDS.get(risk_level, 0.70)
        
        result = ConfidenceResult(
            final_score=round(final_score, 4),
            factors=factors,
            risk_adjusted_threshold=threshold,
            is_above_threshold=final_score >= threshold,
            version=self.version
        )
        
        logger.info(
            f"[CONFIDENCE_V2] Agent: {agent_name} | Score: {result.final_score} | "
            f"Threshold: {threshold} ({risk_level}) | Pass: {result.is_above_threshold}"
        )
        
        return result

    def get_model_metadata(self) -> Dict[str, str]:
        """Returns metadata for audit logs."""
        return {
            "confidence_engine_version": self.version,
            "algorithm": "weighted_risk_adjusted_v2",
            "threshold_policy": "enterprise_standard_v1"
        }
