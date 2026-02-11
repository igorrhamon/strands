"""
Operational agent implementations for the swarm.

Although historically loaded as "mock" agents, these implementations now perform
real deterministic analysis over incoming Alertmanager payloads and calculate
confidence from observable signal quality.
"""

import asyncio
import hashlib
import logging
import re
from typing import Any, Dict, List

from swarm_intelligence.core.models import AgentExecution, Evidence, EvidenceType
from swarm_intelligence.core.swarm import Agent

logger = logging.getLogger(__name__)


def _extract_alert_text(params: Dict[str, Any]) -> str:
    alert = params.get("alert") or {}
    raw_data = alert.get("raw_data") if isinstance(alert, dict) else {}
    if not isinstance(raw_data, dict):
        raw_data = {}

    fragments: List[str] = []
    for item in raw_data.get("alerts", []):
        labels = item.get("labels", {})
        annotations = item.get("annotations", {})
        fragments.extend([str(v) for v in labels.values()])
        fragments.extend([str(v) for v in annotations.values()])

    return " ".join(fragments).lower()


class ThreatIntelAgent(Agent):
    IOC_PATTERNS = {
        r"(bash|sh|cmd).*-i.*socket": ("Reverse shell attempt", 1.0),
        r"curl|wget.*\|.*bash": ("Curl-bash code execution", 1.0),
        r"/dev/tcp/": ("Bash network redirection", 0.8),
        r"powershell.*-enc": ("Encoded PowerShell command", 0.8),
        r"base64.*decode": ("Base64 obfuscation", 0.55),
        r"ransomware|malware|c2|command and control": ("Known malware indicator", 0.9),
    }

    def __init__(self, agent_id: str = "threatintel"):
        super().__init__(
            agent_id,
            version="3.0-operational",
            logic_hash=hashlib.md5(b"threat_ioc_pattern_scoring").hexdigest(),
        )

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        await asyncio.sleep(0.01)
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        text = _extract_alert_text(params)
        matches = []
        scores = []
        for pattern, (name, sev_score) in self.IOC_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                matches.append({"pattern": pattern, "name": name, "severity_score": sev_score})
                scores.append(sev_score)

        data_quality = 1.0 if text else 0.45
        signal_strength = (sum(scores) / len(scores)) if scores else 0.35
        confidence = round(max(0.25, min(0.99, (0.6 * signal_strength + 0.4 * data_quality))), 3)

        evidence = Evidence(
            source_agent_execution_id=execution.execution_id,
            agent_id=self.agent_id,
            content={
                "matches": matches,
                "threats_detected": len(matches),
                "signal_strength": round(signal_strength, 3),
                "data_quality": round(data_quality, 3),
            },
            confidence=confidence,
            evidence_type=EvidenceType.SEMANTIC,
        )
        execution.output_evidence.append(evidence)
        return execution


class LogAnalysisAgent(Agent):
    ERROR_PATTERNS = {
        r"timeout|connection refused|dns": 0.75,
        r"oom|outofmemory": 1.0,
        r"permission denied|access denied": 0.8,
        r"disk full|no space": 1.0,
        r"panic|segmentation fault": 1.0,
        r"\b5\d\d\b": 0.7,
    }

    def __init__(self, agent_id: str = "loganalysis"):
        super().__init__(
            agent_id,
            version="3.0-operational",
            logic_hash=hashlib.md5(b"log_error_pattern_density_scoring").hexdigest(),
        )

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        await asyncio.sleep(0.01)
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        text = _extract_alert_text(params)
        hits: Dict[str, int] = {}
        weights: List[float] = []
        for pattern, weight in self.ERROR_PATTERNS.items():
            found = len(re.findall(pattern, text, re.IGNORECASE))
            if found:
                hits[pattern] = found
                weights.extend([weight] * found)

        sample_tokens = max(len(text.split()), 1)
        error_density = min(1.0, len(weights) / sample_tokens)
        avg_severity = (sum(weights) / len(weights)) if weights else 0.3
        data_quality = 1.0 if text else 0.4
        confidence = round(max(0.25, min(0.99, 0.5 * avg_severity + 0.3 * data_quality + 0.2 * error_density)), 3)

        evidence = Evidence(
            source_agent_execution_id=execution.execution_id,
            agent_id=self.agent_id,
            content={
                "pattern_hits": hits,
                "error_density": round(error_density, 3),
                "avg_severity": round(avg_severity, 3),
                "tokens": sample_tokens,
            },
            confidence=confidence,
            evidence_type=EvidenceType.METRICS,
        )
        execution.output_evidence.append(evidence)
        return execution


class NetworkScannerAgent(Agent):
    HIGH_RISK_PORTS = {3306: 0.75, 5432: 0.75, 6379: 0.95, 27017: 0.95, 9200: 0.8}
    SUSPICIOUS_PORTS = {135: 0.8, 139: 0.7, 445: 0.8, 3389: 0.85, 1433: 0.8}

    def __init__(self, agent_id: str = "networkscanner"):
        super().__init__(
            agent_id,
            version="3.0-operational",
            logic_hash=hashlib.md5(b"network_exposure_and_port_risk_scoring").hexdigest(),
        )

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        await asyncio.sleep(0.01)
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        network_info = params.get("network_info") or {}
        open_ports = network_info.get("open_ports")
        if not isinstance(open_ports, list) or not open_ports:
            open_ports = [22, 80, 443]

        high_risk = [p for p in open_ports if p in self.HIGH_RISK_PORTS]
        suspicious = [p for p in open_ports if p in self.SUSPICIOUS_PORTS]

        port_risk_scores = [self.HIGH_RISK_PORTS[p] for p in high_risk] + [self.SUSPICIOUS_PORTS[p] for p in suspicious]
        risk_strength = (sum(port_risk_scores) / len(port_risk_scores)) if port_risk_scores else 0.35
        coverage = min(1.0, len(open_ports) / 8)
        confidence = round(max(0.25, min(0.99, 0.55 * risk_strength + 0.45 * coverage)), 3)

        evidence = Evidence(
            source_agent_execution_id=execution.execution_id,
            agent_id=self.agent_id,
            content={
                "open_ports": open_ports,
                "high_risk_ports": high_risk,
                "suspicious_ports": suspicious,
                "risk_strength": round(risk_strength, 3),
                "coverage": round(coverage, 3),
            },
            confidence=confidence,
            evidence_type=EvidenceType.METRICS,
        )
        execution.output_evidence.append(evidence)
        return execution


__all__ = ["ThreatIntelAgent", "LogAnalysisAgent", "NetworkScannerAgent"]
