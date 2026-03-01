"""
Evidence Fusion Agent - Consolidates findings from multiple agents.

This agent is responsible for:
1. Aggregating confidence scores from multiple agents using weighted averages.
2. Applying hysteresis and smoothing to avoid jitter in decisions.
3. Consolidating quantitative and qualitative evidence into a single hypothesis.
"""

import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

from src.agents.base_agent import BaseAgent, AgentOutput, AgentStatus, Evidence, EvidenceType
from src.models.swarm import SwarmResult, EvidenceItem

logger = logging.getLogger(__name__)

class EvidenceFusionAgent(BaseAgent):
    """
    Agent that fuses evidence from multiple agents into a unified hypothesis.
    """

    def __init__(self, name: str = "EvidenceFusionAgent", config: Dict = None):
        super().__init__(name, config)
        self.agent_id = "evidence_fusion"

        # Priority for environment variables in weights
        import os
        self.weights = {
            "metrics_analysis": float(os.getenv("FUSION_WEIGHT_METRICS", 0.4)),
            "correlator": float(os.getenv("FUSION_WEIGHT_CORRELATOR", 0.4)),
            "log_inspector": float(os.getenv("FUSION_WEIGHT_LOGS", 0.2))
        }

        # Override with explicit config if provided
        if self.config and "weights" in self.config:
            self.weights.update(self.config["weights"])

        self._history = []

    async def execute(self, input_data: Dict[str, Any]) -> AgentOutput:
        """
        Consolidates multiple agent outputs into a single fused output.

        Args:
            input_data: Should contain 'agent_outputs' (List[SwarmResult])
        """
        try:
            agent_outputs = input_data.get("agent_outputs", [])
            if not agent_outputs:
                return self._failed_output("No agent outputs provided for fusion")

            # 1. Aggregation
            fused_confidence, fused_metrics = self._fuse_quantitative(agent_outputs)
            fused_hypothesis, fused_findings = self._fuse_qualitative(agent_outputs)

            # 2. Hysteresis/Smoothing (Simple version)
            smoothed_confidence = self._apply_smoothing(fused_confidence)

            # 3. Generate Evidence
            evidence = await self.generate_evidence(agent_outputs, smoothed_confidence)

            # 4. Return Output
            return AgentOutput(
                agent_id=self.agent_id,
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                result={"hypothesis": fused_hypothesis},
                confidence=smoothed_confidence,
                evidence=evidence,
                quantitative_metrics=fused_metrics,
                qualitative_findings=fused_findings
            )

        except Exception as e:
            self.logger.error(f"Fusion failed: {e}")
            return self._failed_output(str(e))

    def _fuse_quantitative(self, outputs: List[SwarmResult]) -> (float, Dict[str, float]):
        total_weight = 0.0
        weighted_confidence = 0.0
        all_metrics = {}

        for out in outputs:
            weight = self.weights.get(out.agent_id, 0.1)
            weighted_confidence += out.confidence * weight
            total_weight += weight

            # Merge metrics
            all_metrics.update(out.quantitative_metrics)

        final_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0
        return final_confidence, all_metrics

    def _fuse_qualitative(self, outputs: List[SwarmResult]) -> (str, List[str]):
        findings = []
        hypotheses = []

        for out in outputs:
            findings.extend(out.qualitative_findings)
            hypotheses.append(f"[{out.agent_id}] {out.hypothesis}")

        fused_hypothesis = " | ".join(hypotheses)
        return fused_hypothesis, findings

    def _apply_smoothing(self, current_confidence: float) -> float:
        self._history.append(current_confidence)
        if len(self._history) > 5:
            self._history.pop(0)

        return sum(self._history) / len(self._history)

    async def collect_data(self, input_data: Dict[str, Any]) -> Any:
        return input_data.get("agent_outputs")

    def analyze(self, data: Any) -> Any:
        return data

    def validate_output(self, result: Any) -> bool:
        return True

    async def generate_evidence(self, data: Any, result: Any) -> List[Evidence]:
        # Evidence for fusion is the aggregate itself
        return [
            Evidence(
                type=EvidenceType.INFERENCE,
                source=self.name,
                value=result,
                confidence=result,
                qualitative_summary="Fused confidence from multiple agents"
            )
        ]

    def _failed_output(self, message: str) -> AgentOutput:
        return AgentOutput(
            agent_id=self.agent_id,
            agent_name=self.name,
            status=AgentStatus.FAILED,
            result=None,
            confidence=0.0,
            error_message=message
        )
