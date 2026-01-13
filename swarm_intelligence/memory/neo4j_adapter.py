
import logging
import json
from neo4j import GraphDatabase, Driver
from typing import Dict, Any, List

from swarm_intelligence.core.models import (
    Alert, SwarmPlan, SwarmStep, AgentExecution, Evidence, Decision,
    HumanDecision, OperationalOutcome, EvidenceType, RetryAttempt, ReplayReport
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, parameters))

    def run_write_transaction(self, query: str, parameters: Dict[str, Any] = None) -> Any:
        with self._driver.session() as session:
            result = session.execute_write(lambda tx: tx.run(query, parameters).single())
        return result

    def run_read_transaction(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.execute_read(lambda tx: tx.run(query, parameters).data())
        return result

    def fetch_full_run_context(self, run_id: str) -> Dict[str, Any]:
        """Fetches and reconstructs a complete SwarmRun context for deterministic replay."""
        # This implementation is simplified for clarity. A production version would
        # need more robust reconstruction of complex objects like policies.
        query = """
        MATCH (run:SwarmRun {id: $run_id})<-[:TRIGGERED]-(alert:Alert)
        MATCH (run)-[:EXECUTED_STEP]->(step)-[:HAD_EXECUTION]->(exec:AgentExecution)-[:EXECUTED_BY]->(agent:Agent)
        OPTIONAL MATCH (exec)-[:PRODUCED]->(ev:Evidence)
        WITH run, alert, step, agent, exec, collect(ev) as evidences
        WITH run, alert, step, agent, collect({execution: exec, evidences: evidences}) as executions_data
        WITH run, alert, collect({step: step, agent: agent, executions: executions_data}) as step_data
        OPTIONAL MATCH (decision:Decision)<-[:INFLUENCED]-(:Evidence)<-[:PRODUCED]-(:AgentExecution)<-[:HAD_EXECUTION]-(:SwarmStep)<-[:EXECUTED_STEP]-(run)
        RETURN run, alert, step_data, decision LIMIT 1
        """
        data = self.run_read_transaction(query, {"run_id": run_id})
        if not data: return {}

        raw_run = data[0]
        reconstructed_steps = []
        reconstructed_results = {}
        for step_info in raw_run['step_data']:
            step_node = step_info['step']
            reconstructed_steps.append(SwarmStep(agent_id=step_info['agent']['id'], step_id=step_node['id']))
            for exec_info in step_info['executions']:
                execution_node = exec_info['execution']
                evidence_list = [Evidence(**ev) for ev in exec_info['evidences']]
                reconstructed_results[execution_node['id']] = AgentExecution(
                    execution_id=execution_node['id'],
                    agent_id=step_info['agent']['id'],
                    agent_version=execution_node['agent_version'],
                    logic_hash=execution_node['logic_hash'],
                    step_id=step_node['id'],
                    input_parameters={}, # Simplified for this example
                    output_evidence=evidence_list,
                    error=execution_node['error']
                )

        reconstructed_plan = SwarmPlan(
            plan_id=raw_run['run']['id'],
            objective=raw_run['run']['objective'],
            steps=reconstructed_steps
        )

        return {
            "plan": reconstructed_plan,
            "alert": Alert(alert_id=raw_run['alert']['id'], data=json.loads(raw_run['alert']['data'])),
            "results": reconstructed_results,
            "decision": raw_run['decision'],
            "master_seed": raw_run['run']['master_seed']
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
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ReplayReport) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ConfidenceSnapshot) REQUIRE n.id IS UNIQUE",
        ]
        for query in constraints:
            self.run_transaction(query)
        logging.info("Neo4j schema constraints ensured.")

    def save_swarm_run(self, plan: SwarmPlan, alert: Alert, executions: List[AgentExecution], decision: Decision, retry_attempts: List[RetryAttempt], master_seed: int):
        # This complex query performs the entire save in one atomic transaction.
        query = """
        MERGE (alert:Alert {id: $alert_id}) ON CREATE SET alert.data = $alert_data
        MERGE (run:SwarmRun {id: $run_id}) ON CREATE SET run.objective = $objective, run.timestamp = datetime(), run.master_seed = $master_seed
        MERGE (alert)-[:TRIGGERED]->(run)

        MERGE (dec:Decision {id: $decision_id})
        ON CREATE SET dec.summary = $summary, dec.action_proposed = $action_proposed, dec.confidence = $confidence, dec.timestamp = datetime()

        WITH run, dec
        UNWIND $steps as step_param
        MERGE (step:SwarmStep {id: step_param.step_id})
        ON CREATE SET step.parameters = step_param.params, step.retry_policy = step_param.policy
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

        WITH dec, exec, exec_param.evidence as evidences_param
        UNWIND evidences_param as ev_param
        CREATE (ev:Evidence {
            id: ev_param.evidence_id,
            content: ev_param.content,
            confidence: ev_param.confidence,
            evidence_type: ev_param.evidence_type
        })
        MERGE (exec)-[:PRODUCED]->(ev)

        WITH dec
        UNWIND $influencing_evidence as ev_id
        MATCH (evidence:Evidence {id: ev_id})
        MERGE (evidence)-[:INFLUENCED {weight: 1.0}]->(dec)

        WITH dec
        UNWIND $retries as retry_param
        MATCH (failed_exec:AgentExecution {id: retry_param.failed_execution_id})
        CREATE (ra:RetryAttempt {
            id: retry_param.attempt_id,
            attempt_number: retry_param.attempt_number,
            delay_seconds: retry_param.delay_seconds,
            reason: retry_param.reason,
            timestamp: datetime()
        })
        CREATE (failed_exec)-[:RETRIED_WITH]->(ra)
        """

        steps_params = [{
            "step_id": s.step_id,
            "agent_id": s.agent_id,
            "params": json.dumps(s.parameters),
            "policy": json.dumps(s.retry_policy.to_dict() if s.retry_policy else {}),
            "executions": [{
                "execution_id": ex.execution_id,
                "agent_version": ex.agent_version,
                "logic_hash": ex.logic_hash,
                "error": ex.error,
                "evidence": [e.__dict__ for e in ex.output_evidence]
            } for ex in executions if ex.step_id == s.step_id]
        } for s in plan.steps]

        params = {
            "alert_id": alert.alert_id, "alert_data": json.dumps(alert.data),
            "run_id": plan.plan_id, "objective": plan.objective,
            "master_seed": master_seed,
            "decision_id": decision.decision_id, "summary": decision.summary,
            "action_proposed": decision.action_proposed, "confidence": decision.confidence,
            "steps": steps_params,
            "influencing_evidence": [ev.evidence_id for ev in decision.supporting_evidence],
            "retries": [r.__dict__ for r in retry_attempts]
        }
        self.run_transaction(query, params)

    def save_human_override(self, decision: Decision, human_decision: HumanDecision, outcome: OperationalOutcome):
        """Saves the human override and its causal impact in a single atomic transaction."""
        query = """
        MATCH (d:Decision {id: $decision_id})
        CREATE (hd:HumanDecision {id: $hd_id, author: $author, reason: $reason, timestamp: datetime()})
        CREATE (d)-[:OVERRULED]->(hd)

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
        return result["snapshot_id"]

    def link_snapshot_to_cause(self, snapshot_id: str, cause_id: str, cause_type: str):
        """Creates a [:CAUSED_BY] relationship from a snapshot to its cause."""
        query = f"""
        MATCH (s:ConfidenceSnapshot {{id: $snapshot_id}})
        MATCH (c:{cause_type} {{id: $cause_id}})
        CREATE (s)-[:CAUSED_BY]->(c)
        """
        self.run_transaction(query, {"snapshot_id": snapshot_id, "cause_id": cause_id})
