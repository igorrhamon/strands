
import logging
import json
from enum import Enum
from neo4j import GraphDatabase, Driver
from typing import Dict, Any, List

from swarm_intelligence.core.models import (
    Alert, SwarmPlan, SwarmStep, AgentExecution, Evidence, Decision,
    HumanDecision, OperationalOutcome, EvidenceType, RetryAttempt, ReplayReport,
    Domain, SwarmRun, RetryDecision
)
from swarm_intelligence.core.enums import RiskLevel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _convert_enums_to_values(obj: Any) -> Any:
    """
    Recursively converts Enum instances, Exception objects, and complex types to primitive values for Neo4j serialization.
    Neo4j driver only supports primitive types and arrays thereof.
    Also converts non-string dictionary keys to strings.
    """
    if obj is None:
        return None
    elif isinstance(obj, bool):  # Must be before int (bool is subclass of int)
        return obj
    elif isinstance(obj, (int, float, str)):
        return obj
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, Exception):
        return str(obj)
    elif isinstance(obj, dict):
        return {str(k): _convert_enums_to_values(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_enums_to_values(item) for item in obj]
    else:
        # For any other custom object, try to convert using __dict__
        try:
            if hasattr(obj, '__dict__'):
                return _convert_enums_to_values(obj.__dict__)
            else:
                return str(obj)
        except Exception:
            return str(obj)



class Neo4jAdapter:
    """
    A production-grade adapter for interacting with a Neo4j database,
    focusing on creating a causal graph for traceability and learning.
    """
    def __init__(self, uri, user, password):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))
        logging.info("Neo4jAdapter initialized and connected.")

    def close(self):
        self._driver.close()
        logging.info("Neo4jAdapter connection closed.")

    def run_transaction(self, query: str, parameters: Dict[str, Any] = None):
        if parameters:
            parameters = _convert_enums_to_values(parameters)
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, parameters))

    def run_write_transaction(self, query: str, parameters: Dict[str, Any] = None) -> Any:
        if parameters:
            parameters = _convert_enums_to_values(parameters)
        with self._driver.session() as session:
            result = session.execute_write(lambda tx: tx.run(query, parameters).single())
        return result

    def run_read_transaction(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if parameters:
            parameters = _convert_enums_to_values(parameters)
        with self._driver.session() as session:
            result = session.execute_read(lambda tx: tx.run(query, parameters).data())
        return result

    def fetch_full_run_context(self, run_id: str) -> Dict[str, Any]:
        """Fetches and reconstructs a complete SwarmRun context for deterministic replay."""
        # Fetch core run data
        run_query = "MATCH (run:SwarmRun {id: $run_id}) RETURN run LIMIT 1"
        run_data = self.run_read_transaction(run_query, {"run_id": run_id})
        
        if not run_data:
            logging.warning(f"No SwarmRun found with id: {run_id}")
            return {}
        
        run_node = run_data[0]['run']
        
        # Fetch alert if it exists
        alert_query = "MATCH (alert:Alert)-[:TRIGGERED]->(run:SwarmRun {id: $run_id}) RETURN alert LIMIT 1"
        alert_data = self.run_read_transaction(alert_query, {"run_id": run_id})
        alert_node = alert_data[0]['alert'] if alert_data else None
        
        # Fetch domain if it exists
        domain_query = "MATCH (run:SwarmRun {id: $run_id})-[:BELONGS_TO]->(domain:Domain) RETURN domain LIMIT 1"
        domain_data = self.run_read_transaction(domain_query, {"run_id": run_id})
        domain_node = domain_data[0]['domain'] if domain_data else None
        
        # Fetch all executions for this run
        exec_query = """
        MATCH (run:SwarmRun {id: $run_id})-[:EXECUTED_STEP]->(step:SwarmStep)-[:HAD_EXECUTION]->(exec:AgentExecution)
        OPTIONAL MATCH (agent:Agent)-[:EXECUTED]->(exec)
        OPTIONAL MATCH (exec)-[:PRODUCED]->(ev:Evidence)
        RETURN step, agent, exec, collect(ev) as evidences
        ORDER BY step.id
        """
        exec_data = self.run_read_transaction(exec_query, {"run_id": run_id})
        
        if not exec_data:
            logging.warning(f"No executions found for run_id: {run_id}")
            return {}
        
        # Reconstruct plan and executions
        seen_steps = set()
        reconstructed_steps = []
        reconstructed_results = {}
        
        for row in exec_data:
            step_node = row['step']
            agent_node = row['agent']
            exec_node = row['exec']
            evidences = row['evidences'] or []
            
            # Add unique steps to plan
            if step_node['id'] not in seen_steps:
                reconstructed_steps.append(SwarmStep(
                    agent_id=agent_node['id'] if agent_node else step_node['id'],
                    step_id=step_node['id']
                ))
                seen_steps.add(step_node['id'])
            
            # Store execution results
            reconstructed_results[exec_node['id']] = AgentExecution(
                execution_id=exec_node['id'],
                agent_id=agent_node['id'] if agent_node else "unknown",
                agent_version=exec_node.get('agent_version', '1.0'),
                logic_hash=exec_node.get('logic_hash', ''),
                step_id=step_node['id'],
                input_parameters={},
                output_evidence=[
                    Evidence(
                        evidence_id=ev.get('id') or ev.get('evidence_id'),
                        source_agent_execution_id=ev.get('source_agent_execution_id'),
                        agent_id=ev.get('agent_id'),
                        content=ev.get('content'),
                        confidence=ev.get('confidence', 0.0),
                        evidence_type=EvidenceType(ev.get('evidence_type', 'hypothesis'))
                    )
                    for ev in evidences if isinstance(ev, dict)
                ],
                error=exec_node.get('error')
            )
        
        reconstructed_plan = SwarmPlan(
            plan_id=run_node['id'],
            objective=run_node.get('objective', 'Replayed execution'),
            steps=reconstructed_steps
        )
        
        return {
            'run_id': run_node['id'],
            'plan': reconstructed_plan,
            'domain': domain_node,
            'alert': alert_node,
            'master_seed': run_node.get('master_seed'),
            'results': reconstructed_results,
            'evidence': [],
            'decision': None
        }


    def setup_schema(self):
        """Sets up the unique constraints and indexes for the graph."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Alert) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SwarmRun) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:SwarmStep) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Agent) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:AgentExecution) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Evidence) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Decision) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:HumanDecision) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:OperationalOutcome) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:RetryAttempt) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:RetryDecision) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:RetryPolicy) REQUIRE n.logic_hash IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ReplayReport) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ConfidenceSnapshot) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Domain) REQUIRE n.id IS UNIQUE",
        ]
        for query in constraints:
            self.run_transaction(query)
        logging.info("Neo4j schema constraints ensured.")

    def save_swarm_run(self, swarm_run: SwarmRun, alert: Alert, retry_attempts: List[RetryAttempt], retry_decisions: List[RetryDecision]):
        # This complex query performs the entire save in one atomic transaction.
        query = """
        MERGE (alert:Alert {id: $alert_id}) ON CREATE SET alert.data = $alert_data
        MERGE (run:SwarmRun {id: $run_id}) ON CREATE SET run.objective = $objective, run.timestamp = datetime(), run.master_seed = $master_seed
        MERGE (alert)-[:TRIGGERED]->(run)

        WITH run, alert
        MATCH (domain:Domain {id: $domain_id})
        MERGE (run)-[:BELONGS_TO]->(domain)

        MERGE (dec:Decision {id: $decision_id})
        ON CREATE SET dec.summary = $summary, dec.action_proposed = $action_proposed, dec.confidence = $confidence, dec.timestamp = datetime()

        MATCH (run:SwarmRun), (dec:Decision)
        WHERE run.id = $run_id AND dec.id = $decision_id
        MERGE (run)-[:HAS_FINAL_DECISION]->(dec)

        // Compatibility legacy dashboard (src/graph/neo4j_repo.py)
        WITH run, alert, dec
        MERGE (s:Service {name: coalesce($service_name, "unknown-service")})
        SET alert.fingerprint = alert.id,
            alert.timestamp = datetime(),
            alert.severity = coalesce($severity, "warning"),
            alert.description = coalesce($description, "Alert from Strands"),
            alert.source = "ORCHESTRATOR"
        MERGE (alert)-[:IMPACTS]->(s)
        
        MERGE (dc:DecisionCandidate {decision_id: dec.id})
        ON CREATE SET 
            dc.summary = dec.summary,
            dc.status = "PROPOSED",
            dc.primary_hypothesis = "Swarm Analysis Result",
            dc.risk = "MEDIUM",
            dc.automation = "PARTIAL",
            dc.created_at = datetime()
        MERGE (alert)-[:HAS_CANDIDATE]->(dc)

        WITH run, dec
        UNWIND $steps as step_param
        MERGE (step:SwarmStep {id: step_param.step_id})
        ON CREATE SET step.parameters = step_param.params
        MERGE (run)-[:EXECUTED_STEP]->(step)

        MERGE (agent:Agent {id: step_param.agent_id})

        WITH run, dec, step, agent, step_param.executions as executions_param
        UNWIND executions_param as exec_param
        CREATE (exec:AgentExecution {
            id: exec_param.execution_id,
            agent_version: exec_param.agent_version,
            logic_hash: exec_param.logic_hash,
            error: exec_param.error,
            timestamp: datetime()
        })
        MERGE (step)-[:HAD_EXECUTION]->(exec)
        MERGE (agent)-[:EXECUTED]->(exec)

        WITH run, dec, exec, exec_param.evidence as evidences_param
        UNWIND evidences_param as ev_param
        CREATE (ev:Evidence {
            id: ev_param.evidence_id,
            content: ev_param.content,
            confidence: ev_param.confidence,
            evidence_type: ev_param.evidence_type
        })
        MERGE (exec)-[:PRODUCED]->(ev)

        WITH run, dec
        UNWIND $influencing_evidence as ev_id
        MATCH (evidence:Evidence {id: ev_id})
        MERGE (evidence)-[:INFLUENCED {weight: 1.0}]->(dec)

        WITH run
        UNWIND $retries as retry_param
        MATCH (step:SwarmStep {id: retry_param.step_id})
        MATCH (failed_exec:AgentExecution {id: retry_param.failed_execution_id})
        MERGE (ra:RetryAttempt {id: retry_param.attempt_id})
        ON CREATE SET 
            ra.attempt_number = retry_param.attempt_number,
            ra.delay_seconds = retry_param.delay_seconds,
            ra.reason = retry_param.reason,
            ra.timestamp = datetime()
        MERGE (step)-[:RETRIED_WITH]->(ra)
        MERGE (ra)-[:FAILED_EXECUTION]->(failed_exec)

        WITH run
        UNWIND $retry_decisions as rd_param
        MATCH (attempt:RetryAttempt {id: rd_param.attempt_id})
        MATCH (failed_exec:AgentExecution {id: attempt.failed_execution_id})
        MATCH (step:SwarmStep {id: rd_param.step_id})
        CREATE (rd:RetryDecision {
            id: rd_param.decision_id,
            reason: rd_param.reason,
            timestamp: datetime()
        })
        CREATE (failed_exec)-[:TRIGGERED]->(rd)
        CREATE (rd)-[:RESULTED_IN]->(attempt)
        CREATE (attempt)-[:REEXECUTED]->(step)
        """

        steps_params = [{
            "step_id": s.step_id,
            "agent_id": s.agent_id,
            "params": json.dumps(s.parameters),
            "executions": [{
                "execution_id": ex.execution_id,
                "agent_version": ex.agent_version,
                "logic_hash": ex.logic_hash,
                "error": ex.error,
                "evidence": [{
                    "evidence_id": e.evidence_id,
                    "content": json.dumps(_convert_enums_to_values(e.content)) if isinstance(e.content, dict) else str(e.content),
                    "confidence": e.confidence,
                    "evidence_type": e.evidence_type.value if isinstance(e.evidence_type, Enum) else e.evidence_type
                } for e in ex.output_evidence]
            } for ex in swarm_run.executions if ex.step_id == s.step_id]
        } for s in swarm_run.plan.steps]

        # Extract metadata for legacy dashboard
        alert_dict = alert.data if isinstance(alert.data, dict) else {}
        if isinstance(alert.data, str):
            try:
                alert_dict = json.loads(alert.data)
            except:
                alert_dict = {}
        
        # Determine service name and severity from AlertManager format if present
        first_alert = alert_dict.get("alerts", [{}])[0] if "alerts" in alert_dict else {}
        service_name = first_alert.get("labels", {}).get("instance") or first_alert.get("labels", {}).get("alertname")
        severity = first_alert.get("labels", {}).get("severity")
        description = first_alert.get("annotations", {}).get("description") or alert_dict.get("alertname")

        params = {
            "alert_id": alert.alert_id, "alert_data": json.dumps(alert.data),
            "run_id": swarm_run.run_id, "objective": swarm_run.plan.objective,
            "master_seed": swarm_run.master_seed,
            "domain_id": swarm_run.domain.id,
            "decision_id": swarm_run.final_decision.decision_id, "summary": swarm_run.final_decision.summary,
            "action_proposed": swarm_run.final_decision.action_proposed, "confidence": swarm_run.final_decision.confidence,
            "service_name": service_name, "severity": severity, "description": description,
            "steps": steps_params,
            "influencing_evidence": [ev.evidence_id for ev in swarm_run.final_decision.supporting_evidence],
            "retries": [r.__dict__ for r in retry_attempts],
            "retry_decisions": [rd.__dict__ for rd in retry_decisions]
        }
        self.run_transaction(query, params)

    def save_human_override(self, decision: Decision, human_decision: HumanDecision, outcome: OperationalOutcome):
        """Saves the human override and its causal impact in a single atomic transaction."""
        query = """
        MATCH (d:Decision {id: $decision_id})
        CREATE (hd:HumanDecision {id: $hd_id, author: $author, reason: $reason, timestamp: datetime()})
        CREATE (d)-[:OVERRULED]->(hd)

        // Compatibility legacy dashboard (src/graph/neo4j_repo.py)
        WITH d, hd
        OPTIONAL MATCH (dc:DecisionCandidate {decision_id: $decision_id})
        SET dc.status = CASE WHEN $status = 'success' THEN 'APPROVED' ELSE 'REJECTED' END,
            dc.validated_at = datetime(),
            dc.feedback = $reason
        
        CREATE (o:OperationalOutcome {id: $outcome_id, status: $status, timestamp: datetime()})
        CREATE (hd)-[:LED_TO]->(o)

        WITH hd
        UNWIND $evidence_ids as ev_id
        MATCH (ev:Evidence {id: ev_id})
        MATCH (a:Agent)<-[:EXECUTED]-(:AgentExecution)-[:PRODUCED]->(ev)
        CREATE (hd)-[:INVALIDATED]->(ev)
        CREATE (hd)-[:PENALIZED]->(a)
        """
        params = {
            "decision_id": decision.decision_id,
            "hd_id": human_decision.human_decision_id,
            "author": human_decision.author,
            "reason": human_decision.override_reason,
            "outcome_id": outcome.outcome_id,
            "status": outcome.status,
            "evidence_ids": [ev.evidence_id for ev in decision.supporting_evidence]
        }
        self.run_transaction(query, params)
        logging.info(f"Human override by {human_decision.author} saved atomically.")

    def save_replay_report(self, report: ReplayReport):
        """Saves a replay report to the graph, linking it to the involved decisions."""
        query = """
        MATCH (orig_d:Decision {id: $original_id})
        MATCH (replay_d:Decision {id: $replayed_id})
        CREATE (rr:ReplayReport {
            id: $report_id,
            confidence_delta: $delta,
            divergences: $divergences,
            timestamp: datetime()
        })
        CREATE (rr)-[:REPLAYED]->(orig_d)
        CREATE (replay_d)-[:GENERATED_BY]->(rr)
        """
        params = {
            "original_id": report.original_decision_id,
            "replayed_id": report.replayed_decision_id,
            "report_id": report.report_id,
            "delta": report.confidence_delta,
            "divergences": report.causal_divergences
        }
        self.run_transaction(query, params)
        logging.info(f"Replay report {report.report_id} saved.")

    def save_domain(self, domain: Domain):
        """Saves a cognitive domain to the graph."""
        query = """
        MERGE (d:Domain {id: $id})
        ON CREATE SET d.name = $name, d.description = $description, d.risk_level = $risk_level
        ON MATCH SET d.name = $name, d.description = $description, d.risk_level = $risk_level
        """
        params = {
            "id": domain.id,
            "name": domain.name,
            "description": domain.description,
            "risk_level": domain.risk_level.value
        }
        self.run_transaction(query, params)
        logging.info(f"Domain '{domain.name}' saved.")

    def link_agent_to_domain(self, agent_id: str, domain_id: str, weight: float):
        """Creates a weighted APPLICABLE_TO relationship from an agent to a domain."""
        query = """
        MATCH (a:Agent {id: $agent_id})
        MATCH (d:Domain {id: $domain_id})
        MERGE (a)-[r:APPLICABLE_TO]->(d)
        SET r.weight = $weight
        """
        self.run_transaction(query, {"agent_id": agent_id, "domain_id": domain_id, "weight": weight})

    def link_policy_to_domain(self, policy_name: str, domain_id: str):
        """Creates a VALID_IN relationship from a policy to a domain."""
        query = """
        MERGE (p:RetryPolicy {name: $policy_name})
        MATCH (d:Domain {id: $domain_id})
        MERGE (p)-[:VALID_IN]->(d)
        """
        self.run_transaction(query, {"policy_name": policy_name, "domain_id": domain_id})

    def link_metric_to_domain(self, metric_name: str, domain_id: str):
        """Creates a RELEVANT_FOR relationship from a metric to a domain."""
        query = """
        MERGE (m:Metric {name: $metric_name})
        MATCH (d:Domain {id: $domain_id})
        MERGE (m)-[:RELEVANT_FOR]->(d)
        """
        self.run_transaction(query, {"metric_name": metric_name, "domain_id": domain_id})

    def get_policies_for_domain(self, domain_id: str) -> List[str]:
        """Fetches the names of retry policies valid for a given domain."""
        query = """
        MATCH (:Domain {id: $domain_id})<-[:VALID_IN]-(p:RetryPolicy)
        RETURN p.name as policy_name
        """
        results = self.run_read_transaction(query, {"domain_id": domain_id})
        return [result["policy_name"] for result in results]

    def create_confidence_snapshot(self, agent_id: str, value: float, source_event: str, sequence_id: int) -> str:
        """Creates a ConfidenceSnapshot node and returns its ID."""
        query = """
        MATCH (a:Agent {id: $agent_id})
        CREATE (s:ConfidenceSnapshot {
            id: randomUUID(),
            value: $value,
            source_event: $source_event,
            sequence_id: $sequence_id,
            timestamp: datetime()
        })
        CREATE (a)-[:HAS_CONFIDENCE]->(s)
        RETURN s.id as snapshot_id
        """
        result = self.run_write_transaction(query, {
            "agent_id": agent_id,
            "value": value,
            "source_event": source_event,
            "sequence_id": sequence_id
        })
        if result is None:
            logging.error(f"Failed to create confidence snapshot for agent {agent_id}")
            return None
        return result["snapshot_id"]

    def link_snapshot_to_cause(self, snapshot_id: str, cause_id: str, cause_type: str):
        """Creates a [:CAUSED_BY] relationship from a snapshot to its cause."""
        query = f"""
        MATCH (s:ConfidenceSnapshot {{id: $snapshot_id}})
        MATCH (c:{cause_type} {{id: $cause_id}})
        CREATE (s)-[:CAUSED_BY]->(c)
        """
        self.run_transaction(query, {"snapshot_id": snapshot_id, "cause_id": cause_id})
