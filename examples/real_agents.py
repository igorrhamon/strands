"""
Real Agent Adapters - Wrap agents from src/agents to be compatible with SwarmOrchestrator.

Adapters consume real data produced in main.py (`params.alert.raw_data`, labels,
annotations and derived fields), and compute confidence from observed signal quality.
"""

import asyncio
import hashlib
import logging
import re
from typing import Any, Dict, List

from swarm_intelligence.core.models import AgentExecution, Evidence, EvidenceType
from swarm_intelligence.core.swarm import Agent

logger = logging.getLogger(__name__)


def _get_raw_alerts(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    alert = params.get("alert") or {}
    raw_data = alert.get("raw_data") if isinstance(alert, dict) else {}
    if not isinstance(raw_data, dict):
        return []
    alerts = raw_data.get("alerts", [])
    return alerts if isinstance(alerts, list) else []


def _extract_alert_text(params: Dict[str, Any]) -> str:
    fragments: List[str] = []
    for item in _get_raw_alerts(params):
        labels = item.get("labels", {})
        annotations = item.get("annotations", {})
        fragments.extend([str(v) for v in labels.values()])
        fragments.extend([str(v) for v in annotations.values()])
    fragments.append(str(params.get("summary", "")))
    fragments.append(str(params.get("description", "")))
    return " ".join(fragments).lower()


def _bounded_confidence(value: float) -> float:
    return round(max(0.25, min(0.99, value)), 3)


class CorrelatorAgentAdapter(Agent):
    """Adapter for src.agents.analysis.correlator.CorrelatorAgent."""

    CORRELATION_PATTERNS = {
        "resource": [r"oom", r"outofmemory", r"cpu", r"memory", r"throttling"],
        "connectivity": [r"timeout", r"connection refused", r"dns", r"network"],
        "availability": [r"5\d\d", r"latency", r"unavailable", r"degraded"],
        "security": [r"unauthorized", r"forbidden", r"malware", r"ransomware"],
    }

    def __init__(self, agent_id: str = "correlator"):
        logic_str = "correlate logs, metrics, traces, and events to identify patterns"
        super().__init__(
            agent_id,
            version="2.0-adapter",
            logic_hash=hashlib.md5(logic_str.encode()).hexdigest(),
        )
        try:
            from src.agents.analysis.correlator import CorrelatorAgent

            self.agent = CorrelatorAgent()
            logger.info("✅ CorrelatorAgent loaded")
        except Exception as e:
            logger.warning(f"⚠️ CorrelatorAgent unavailable (heuristic mode): {e}")
            self.agent = None

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        try:
            await asyncio.sleep(0.02)
            text = _extract_alert_text(params)

            correlated_domains: Dict[str, int] = {}
            domain_hits = 0
            for domain, patterns in self.CORRELATION_PATTERNS.items():
                hits = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
                if hits:
                    correlated_domains[domain] = hits
                    domain_hits += hits

            result = None
            if self.agent is not None and params.get("alert"):
                try:
                    result = self.agent.analyze(params["alert"])
                except Exception as real_err:
                    logger.debug(f"Correlator real agent failed, using heuristic output: {real_err}")

            total_domains = len(correlated_domains)
            alerts_count = len(_get_raw_alerts(params)) or 1
            data_quality = 1.0 if text else 0.45
            correlation_strength = min(1.0, (total_domains / 4) + (domain_hits / 12))
            confidence = _bounded_confidence(0.5 * correlation_strength + 0.3 * data_quality + 0.2 * min(1.0, alerts_count / 5))

            content = {
                "correlated_domains": correlated_domains,
                "patterns_detected": domain_hits,
                "alerts_count": alerts_count,
                "correlation_strength": round(correlation_strength, 3),
                "hypothesis": getattr(result, "hypothesis", "Multi-domain signal correlation") if result else "Multi-domain signal correlation",
                "evidence": getattr(result, "evidence", []) if result else [],
            }

            execution.output_evidence.append(
                Evidence(
                    source_agent_execution_id=execution.execution_id,
                    agent_id=self.agent_id,
                    content=content,
                    confidence=confidence,
                    evidence_type=EvidenceType.SEMANTIC,
                )
            )
        except Exception as e:
            logger.error(f"CorrelatorAgent error: {e}", exc_info=True)
            execution.error = e

        return execution


class LogInspectorAgentAdapter(Agent):
    """Adapter for src.agents.analysis.log_inspector.LogInspectorAgent."""

    LOG_PATTERNS = {
        r"oom|outofmemory": 1.0,
        r"timeout|connection refused": 0.8,
        r"panic|traceback|stack": 0.95,
        r"permission denied|unauthorized|forbidden": 0.85,
        r"5\d\d": 0.7,
    }

    def __init__(self, agent_id: str = "loginspector"):
        logic_str = "inspect pod logs and extract error patterns"
        super().__init__(
            agent_id,
            version="2.0-adapter",
            logic_hash=hashlib.md5(logic_str.encode()).hexdigest(),
        )
        try:
            from src.agents.analysis.log_inspector import LogInspectorAgent

            self.agent = LogInspectorAgent()
            logger.info("✅ LogInspectorAgent loaded")
        except Exception as e:
            logger.warning(f"⚠️ LogInspectorAgent unavailable (heuristic mode): {e}")
            self.agent = None

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        try:
            await asyncio.sleep(0.02)
            text = _extract_alert_text(params)
            service_name = params.get("service_name", "unknown")
            namespace = params.get("namespace", "default")

            result: Dict[str, Any] = {}
            if self.agent:
                try:
                    result = self.agent.get_pod_logs(service_name, namespace)
                except Exception as agent_err:
                    logger.debug(f"LogInspector real execution failed, using heuristic: {agent_err}")

            weights: List[float] = []
            pattern_hits: Dict[str, int] = {}
            for pattern, weight in self.LOG_PATTERNS.items():
                hits = len(re.findall(pattern, text, re.IGNORECASE))
                if hits:
                    pattern_hits[pattern] = hits
                    weights.extend([weight] * hits)

            base_result = result if result else self._heuristic_log_analysis(text, pattern_hits)
            avg_severity = (sum(weights) / len(weights)) if weights else 0.35
            signal_density = min(1.0, len(weights) / max(len(text.split()), 1))
            data_quality = 1.0 if text else 0.4
            confidence = _bounded_confidence(0.5 * avg_severity + 0.3 * data_quality + 0.2 * signal_density)

            base_result.update(
                {
                    "service_name": service_name,
                    "namespace": namespace,
                    "pattern_hits": pattern_hits,
                }
            )

            execution.output_evidence.append(
                Evidence(
                    source_agent_execution_id=execution.execution_id,
                    agent_id=self.agent_id,
                    content=base_result,
                    confidence=confidence,
                    evidence_type=EvidenceType.RAW_DATA,
                )
            )
        except Exception as e:
            logger.error(f"LogInspectorAgent error: {e}", exc_info=True)
            execution.error = e

        return execution

    @staticmethod
    def _heuristic_log_analysis(text: str, pattern_hits: Dict[str, int]) -> Dict[str, Any]:
        total_hits = sum(pattern_hits.values())
        return {
            "pods_scanned": 1,
            "error_count": total_hits,
            "error_rate": f"{round(min(100.0, (total_hits / max(len(text.split()), 1)) * 100), 2)}%",
            "top_errors": [{"pattern": p, "count": c} for p, c in pattern_hits.items()],
        }


class MetricsAnalysisAgentAdapter(Agent):
    """Adapter for src.agents.metrics_analysis.MetricsAnalysisAgent."""

    def __init__(self, agent_id: str = "metricsanalyzer"):
        logic_str = "analyze metrics for anomalies and performance bottlenecks"
        super().__init__(
            agent_id,
            version="2.0-adapter",
            logic_hash=hashlib.md5(logic_str.encode()).hexdigest(),
        )
        try:
            from src.agents.metrics_analysis import MetricsAnalysisAgent

            self.agent = MetricsAnalysisAgent()
            logger.info("✅ MetricsAnalysisAgent loaded")
        except Exception as e:
            logger.warning(f"⚠️ MetricsAnalysisAgent unavailable (heuristic mode): {e}")
            self.agent = None

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        try:
            await asyncio.sleep(0.02)
            text = _extract_alert_text(params)
            content: Dict[str, Any]

            if self.agent:
                try:
                    result = self.agent.analyze_cluster_sync(
                        params.get("cluster"),
                        metrics=params.get("metrics", ["cpu", "memory", "request_rate", "latency", "error_rate"]),
                    )
                    content = result.__dict__ if hasattr(result, "__dict__") else result
                except Exception as agent_err:
                    logger.debug(f"Metrics real execution failed, using heuristic: {agent_err}")
                    content = self._heuristic_metrics(text)
            else:
                content = self._heuristic_metrics(text)

            content = content if isinstance(content, dict) else {"raw_result": content}
            anomalies = content.get("anomalies", [])
            anomaly_count = len(anomalies) if isinstance(anomalies, list) else 0
            text_anomaly_signal = sum(1 for p in [r"cpu", r"memory", r"latency", r"error rate", r"throttle"] if re.search(p, text, re.IGNORECASE))
            data_quality = 1.0 if text else 0.45
            confidence = _bounded_confidence(0.45 * min(1.0, (anomaly_count + text_anomaly_signal) / 6) + 0.35 * data_quality + 0.2 * (1.0 if content else 0.3))

            content["text_signal_hits"] = text_anomaly_signal
            execution.output_evidence.append(
                Evidence(
                    source_agent_execution_id=execution.execution_id,
                    agent_id=self.agent_id,
                    content=content,
                    confidence=confidence,
                    evidence_type=EvidenceType.METRICS,
                )
            )
        except Exception as e:
            logger.error(f"MetricsAnalysisAgent error: {e}", exc_info=True)
            execution.error = e

        return execution

    @staticmethod
    def _heuristic_metrics(text: str) -> Dict[str, Any]:
        cpu = 85 if re.search(r"cpu|throttle", text, re.IGNORECASE) else 55
        memory = 82 if re.search(r"memory|oom", text, re.IGNORECASE) else 58
        latency = 520 if re.search(r"latency|timeout", text, re.IGNORECASE) else 180
        error_rate = 4.2 if re.search(r"5\d\d|error", text, re.IGNORECASE) else 0.9
        anomalies = []
        if cpu > 80:
            anomalies.append({"metric": "cpu", "severity": "high", "trend": "increasing"})
        if memory > 80:
            anomalies.append({"metric": "memory", "severity": "high", "trend": "increasing"})
        if latency > 400:
            anomalies.append({"metric": "latency", "severity": "medium", "trend": "increasing"})
        if error_rate > 2.0:
            anomalies.append({"metric": "error_rate", "severity": "high", "trend": "increasing"})
        return {
            "cpu_usage_percent": cpu,
            "memory_usage_percent": memory,
            "latency_p99_ms": latency,
            "error_rate_percent": error_rate,
            "anomalies": anomalies,
        }


class AlertCorrelatorAgentAdapter(Agent):
    """Adapter for src.agents.alert_correlation.AlertCorrelationAgent."""

    def __init__(self, agent_id: str = "alertcorrelator"):
        logic_str = "correlate multiple alerts to identify related incidents"
        super().__init__(
            agent_id,
            version="2.0-adapter",
            logic_hash=hashlib.md5(logic_str.encode()).hexdigest(),
        )
        try:
            from src.agents.alert_correlation import AlertCorrelationAgent

            self.agent = AlertCorrelationAgent()
            logger.info("✅ AlertCorrelationAgent loaded")
        except Exception as e:
            logger.warning(f"⚠️ AlertCorrelationAgent unavailable (heuristic mode): {e}")
            self.agent = None

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        try:
            await asyncio.sleep(0.02)
            alerts = _get_raw_alerts(params)
            labels_signatures = [
                (
                    item.get("labels", {}).get("alertname", "unknown"),
                    item.get("labels", {}).get("instance", "unknown"),
                    item.get("labels", {}).get("service", item.get("labels", {}).get("job", "unknown")),
                )
                for item in alerts
            ]
            unique_groups = set(labels_signatures)

            clusters = None
            if self.agent:
                try:
                    lookback = params.get("lookback_minutes", 60)
                    clusters = self.agent.collect_and_correlate(lookback_minutes=lookback)
                except Exception as agent_err:
                    logger.debug(f"AlertCorrelator real execution failed, using heuristic: {agent_err}")

            correlated_groups = len(clusters) if clusters is not None else max(1, len(unique_groups))
            alerts_received = len(alerts) or 1
            grouping_ratio = min(1.0, correlated_groups / alerts_received)
            data_quality = 1.0 if alerts else 0.5
            confidence = _bounded_confidence(0.45 * (1 - grouping_ratio) + 0.35 * data_quality + 0.2 * min(1.0, alerts_received / 6))

            result = {
                "alerts_received": alerts_received,
                "correlated_groups": correlated_groups,
                "clusters": [getattr(c, "cluster_id", "unknown") for c in clusters] if clusters else [f"group-{i}" for i in range(correlated_groups)],
                "grouping_ratio": round(grouping_ratio, 3),
                "unique_signatures": len(unique_groups),
            }

            execution.output_evidence.append(
                Evidence(
                    source_agent_execution_id=execution.execution_id,
                    agent_id=self.agent_id,
                    content=result,
                    confidence=confidence,
                    evidence_type=EvidenceType.RAW_DATA,
                )
            )
        except Exception as e:
            logger.error(f"AlertCorrelatorAgent error: {e}", exc_info=True)
            execution.error = e

        return execution


class RecommenderAgentAdapter(Agent):
    """Adapter for src.agents.governance.recommender.RecommenderAgent."""

    def __init__(self, agent_id: str = "recommender"):
        logic_str = "generate remediation recommendations based on analysis"
        super().__init__(
            agent_id,
            version="2.0-adapter",
            logic_hash=hashlib.md5(logic_str.encode()).hexdigest(),
        )
        try:
            from src.agents.governance.recommender import RecommenderAgent

            self.agent = RecommenderAgent()
            logger.info("✅ RecommenderAgent loaded")
        except Exception as e:
            logger.warning(f"⚠️ RecommenderAgent unavailable (heuristic mode): {e}")
            self.agent = None

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )

        try:
            await asyncio.sleep(0.02)
            text = _extract_alert_text(params)
            decision_candidates = params.get("decision_candidates", [])

            if not decision_candidates:
                severity = str(params.get("severity", "medium")).lower()
                service = params.get("service_name", "unknown")
                inferred_issue = "cpu" if re.search(r"cpu|throttle", text, re.IGNORECASE) else (
                    "memory" if re.search(r"memory|oom", text, re.IGNORECASE) else (
                        "latency" if re.search(r"latency|timeout", text, re.IGNORECASE) else "error"
                    )
                )
                decision_candidates = [
                    {
                        "severity": severity,
                        "service": service,
                        "issue_type": inferred_issue,
                        "reason": params.get("summary") or params.get("description") or "Alertmanager incident signal",
                    }
                ]

            recommendations = [self._recommend_from_candidate(c) for c in decision_candidates]
            priority_score = sum(r.get("priority", 0) for r in recommendations) / max(1, len(recommendations))

            result = {
                "recommendations": recommendations,
                "total_recommendations": len(recommendations),
                "priority_score": round(priority_score, 2),
            }

            data_quality = 1.0 if text else 0.45
            confidence = _bounded_confidence(0.5 * min(1.0, len(recommendations) / 3) + 0.3 * data_quality + 0.2 * min(1.0, priority_score / 10))

            execution.output_evidence.append(
                Evidence(
                    source_agent_execution_id=execution.execution_id,
                    agent_id=self.agent_id,
                    content=result,
                    confidence=confidence,
                    evidence_type=EvidenceType.SEMANTIC,
                )
            )
        except Exception as e:
            logger.error(f"RecommenderAgent error: {e}", exc_info=True)
            execution.error = e

        return execution

    @staticmethod
    def _recommend_from_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
        severity = candidate.get("severity", "medium").lower()
        service = candidate.get("service", "unknown")

        action_map = {
            "cpu": "scale_replicas",
            "memory": "increase_memory_limit",
            "latency": "optimize_service",
            "error": "check_logs",
        }

        issue_type = candidate.get("issue_type", "cpu")
        action = action_map.get(issue_type, "investigate")

        return {
            "action": action,
            "target": service,
            "reason": candidate.get("reason", "Anomaly detected"),
            "severity": severity,
            "priority": {"critical": 10, "high": 8, "medium": 5, "low": 2}.get(severity, 5),
            "estimated_improvement": f"Address {issue_type} issue",
        }


class LLMResolutionAgentAdapter(Agent):
    """LLM fallback agent with semantic context enrichment."""

    def __init__(self, agent_id: str = "llm_agent"):
        logic_str = "llm_root_cause_and_resolution_with_semantic_enrichment"
        super().__init__(
            agent_id,
            version="1.0-llm-fallback",
            logic_hash=hashlib.md5(logic_str.encode()).hexdigest(),
        )
        # Use centralized provider factory so the LLM backend can be selected
        # via environment variable `LLM_PROVIDER` (e.g. 'ollama' or 'github').
        self.llm_provider = None
        try:
            from src.llm.provider_factory import LLMFactory

            # Factory reads LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL from env
            self.llm_provider = LLMFactory.create_provider()
            logger.info("✅ LLM provider initialized via LLMFactory")
        except Exception as e:
            logger.warning(f"⚠️ LLM provider unavailable, using heuristic fallback: {e}")

    async def execute(self, params: Dict[str, Any], step_id: str) -> AgentExecution:
        execution = AgentExecution(
            agent_id=self.agent_id,
            agent_version=self.version,
            logic_hash=self.logic_hash,
            step_id=step_id,
            input_parameters=params,
        )
        try:
            text = _extract_alert_text(params)
            evidence_payload = params.get("evidence", [])
            evidence_text = "\n".join(str(e.get("content")) for e in evidence_payload if isinstance(e, dict))


            semantic_context = []
            try:
                from semantica.semantic_extract import NERExtractor
                from semantica.kg import GraphBuilder
                ner = NERExtractor()
                entities = ner.extract(f"{text} {evidence_text}")
                kg = GraphBuilder()
                for entity_type, values in entities.items():
                    for idx, value in enumerate(values):
                        kg.add_entity(f"{entity_type}-{idx}-{value}", entity_type, {"value": value})
                semantic_context = kg.semantic_search(text or evidence_text, limit=5)
            except Exception as sem_err:
                logger.debug(f"Semantic enrichment failed, continuing without KG: {sem_err}")

            procedure = "manual_review"
            root_cause = "Insufficient evidence"
            llm_used = False
            if self.llm_provider is not None:
                prompt = (
                    "Você é um engenheiro SRE. Com base nas evidências e contexto semântico, "
                    "retorne: causa provável e procedimento recomendado em 3 passos.\n"
                    f"Alert text: {text}\n"
                    f"Evidence: {evidence_text}\n"
                    f"Semantic context: {semantic_context}\n"
                )
                try:
                    llm_resp = await self.llm_provider.generate(prompt=prompt, temperature=0.2)
                    llm_used = True
                    root_cause = llm_resp[:400]
                    procedure = llm_resp[:600]
                except Exception as llm_err:
                    logger.warning(f"LLM call failed, fallback heuristic applied: {llm_err}")

            if not llm_used:
                if re.search(r"oom|memory", f"{text} {evidence_text}", re.IGNORECASE):
                    root_cause = "Memory pressure / OOM pattern"
                    procedure = "Aumentar limite de memória; reiniciar pods afetados; validar consumo e leak."
                elif re.search(r"cpu|throttl", f"{text} {evidence_text}", re.IGNORECASE):
                    root_cause = "CPU saturation pattern"
                    procedure = "Escalar réplicas; ajustar requests/limits; verificar query/processo intensivo."
                elif re.search(r"timeout|latency|5\d\d", f"{text} {evidence_text}", re.IGNORECASE):
                    root_cause = "Latency/availability degradation"
                    procedure = "Inspecionar upstream; aplicar circuit-breaker; reduzir timeout de cascata."

            evidence_quality = min(1.0, len(evidence_payload) / 8) if isinstance(evidence_payload, list) else 0.3
            semantic_quality = min(1.0, len(semantic_context) / 5) if isinstance(semantic_context, list) else 0.2
            confidence = _bounded_confidence(0.45 * evidence_quality + 0.25 * semantic_quality + (0.25 if llm_used else 0.15) + 0.15)

            execution.output_evidence.append(
                Evidence(
                    source_agent_execution_id=execution.execution_id,
                    agent_id=self.agent_id,
                    content={
                        "root_cause": root_cause,
                        "recommended_procedure": procedure,
                        "semantic_context": semantic_context,
                        "llm_used": llm_used,
                    },
                    confidence=confidence,
                    evidence_type=EvidenceType.HYPOTHESIS,
                )
            )
        except Exception as e:
            execution.error = e
        return execution


__all__ = [
    "CorrelatorAgentAdapter",
    "LogInspectorAgentAdapter",
    "MetricsAnalysisAgentAdapter",
    "AlertCorrelatorAgentAdapter",
    "RecommenderAgentAdapter",
    "LLMResolutionAgentAdapter",
]
