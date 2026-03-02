import pytest
from src.agents.evidence_fusion_agent import EvidenceFusionAgent
from src.models.swarm import SwarmResult

@pytest.mark.asyncio
async def test_evidence_fusion_aggregation():
    agent = EvidenceFusionAgent()

    outputs = [
        SwarmResult(
            agent_id="metrics_analysis",
            hypothesis="High CPU",
            confidence=0.8,
            quantitative_metrics={"cpu": 90.0},
            qualitative_findings=["CPU is high"]
        ),
        SwarmResult(
            agent_id="correlator",
            hypothesis="Logs match CPU spike",
            confidence=0.9,
            quantitative_metrics={"correlation": 0.95},
            qualitative_findings=["Log pattern matched"]
        )
    ]

    fusion_output = await agent.execute({"agent_outputs": outputs})

    assert fusion_output.status == "success"
    # Weighted: (0.8 * 0.4 + 0.9 * 0.4) / 0.8 = (0.32 + 0.36) / 0.8 = 0.68 / 0.8 = 0.85
    assert pytest.approx(fusion_output.confidence, 0.01) == 0.85
    assert "metrics_analysis" in fusion_output.result["hypothesis"]
    assert "correlator" in fusion_output.result["hypothesis"]
    assert fusion_output.quantitative_metrics["cpu"] == 90.0
    assert "CPU is high" in fusion_output.qualitative_findings

@pytest.mark.asyncio
async def test_evidence_fusion_conflict():
    agent = EvidenceFusionAgent()

    # Large conflict: 0.9 vs 0.1
    outputs = [
        SwarmResult(agent_id="metrics_analysis", hypothesis="A", confidence=0.9),
        SwarmResult(agent_id="correlator", hypothesis="B", confidence=0.1)
    ]

    fusion_output = await agent.execute({"agent_outputs": outputs})

    # Base weighted average would be 0.5 (if equal weights)
    # With conflict penalty, it should be significantly lower than 0.5
    assert fusion_output.confidence < 0.5
    print(f"Conflicted Score: {fusion_output.confidence}")
