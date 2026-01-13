
import logging
import json
from neo4j import GraphDatabase, Driver
from typing import Dict, Any, List

from swarm_intelligence.core.models import (
    Alert, SwarmPlan, SwarmStep, SwarmResult, Decision,
    HumanDecision, OperationalOutcome, EvidenceType
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

    def run_read_transaction(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        with self._driver.session() as session:
            result = session.execute_read(lambda tx: tx.run(query, parameters).data())
        return result

    def fetch_full_run_context(self, run_id: str) -> Dict[str, Any]:
        """Fetches and reconstructs a complete SwarmRun context for deterministic replay."""
        query = """
        MATCH (run:SwarmRun {id: $run_id})<-[:TRIGGERED]-(alert:Alert)
        MATCH (run)-[:EXECUTED_STEP]->(step)-[:EXECUTED_BY]->(agent:Agent)
        OPTIONAL MATCH (step)-[:PRODUCED]->(result:SwarmResult)
        WITH run, alert, step, agent, collect(result) as results
        ORDER BY result.timestamp
        WITH run, alert, collect({step: step, agent: agent, results: results}) as step_data
        OPTIONAL MATCH (run)-[:EXECUTED_STEP]->(any_step)-[:PRODUCED]->(any_result)-[:CAUSALLY_INFLUENCED]->(decision:Decision)
        RETURN run, alert, step_data, decision
        """
        data = self.run_read_transaction(query, {"run_id": run_id})
        if not data:
            return {}

        raw_run = data[0]

        # Reconstruct SwarmSteps and SwarmResults
        steps = []
        all_results = {}
        for item in raw_run['step_data']:
            raw_step = item['step']
            # Retry policy reconstruction would go here if needed
            steps.append(SwarmStep(agent_id=item['agent']['id'], step_id=raw_step['id'], parameters=json.loads(raw_step['parameters'])))
            for raw_result in item['results']:
                all_results[raw_result['id']] = SwarmResult(
                    agent_id=item['agent']['id'],
                    output=raw_result['output'],
                    confidence=raw_result['confidence'],
                    actionable=raw_result['actionable'],
                    evidence_type=EvidenceType(raw_result['evidence_type']),
                    error=raw_result['error']
                )

        plan = SwarmPlan(
            plan_id=raw_run['run']['id'],
            objective=raw_run['run']['objective'],
            steps=steps
        )

        return {
            "plan": plan,
            "alert": Alert(alert_id=raw_run['alert']['id'], data=json.loads(raw_run['alert']['data'])),
            "results": all_results,
            "decision": raw_run['decision']
        }

    def setup_schema(self):
        """Sets up the unique constraints and indexes for the graph."""
        schema_queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Alert) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:SwarmRun) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:SwarmStep) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (res:SwarmResult) REQUIRE res.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Decision) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (hd:HumanDecision) REQUIRE hd.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:OperationalOutcome) REQUIRE o.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (dc:DecisionContext) REQUIRE dc.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (cs:ConfidenceSnapshot) REQUIRE cs.id IS UNIQUE",
        ]
        for query in schema_queries:
            self.run_transaction(query)
        logging.info("Neo4j schema constraints ensured.")

    def save_swarm_run(self, plan: SwarmPlan, alert: Alert, run_history: Dict[str, List[SwarmResult]], decision: Decision):
        """Saves the entire swarm run in a single atomic transaction."""

        steps_params = []
        for step in plan.steps:
            results_params = []
            for i, result in enumerate(run_history.get(step.step_id, [])):
                results_params.append({
                    "result_id": f"{step.step_id}-{i}",
                    "output": str(result.output), "confidence": result.confidence,
                    "actionable": result.actionable, "evidence_type": result.evidence_type.value,
                    "error": result.error
                })

            steps_params.append({
                "step_id": step.step_id, "agent_id": step.agent_id,
                "params": json.dumps(step.parameters),
                "policy": json.dumps(step.retry_policy.to_dict() if step.retry_policy else {}),
                "results": results_params
            })

        query = """
        // 1. Alert and SwarmRun
        MERGE (alert:Alert {id: $alert_id}) ON CREATE SET alert.data = $alert_data
        MERGE (run:SwarmRun {id: $run_id}) ON CREATE SET run.objective = $objective, run.timestamp = datetime()
        MERGE (alert)-[:TRIGGERED]->(run)

        // 2. Decision and Context
        MERGE (dc:DecisionContext {id: $context_id}) ON CREATE SET dc.aggregation_strategy = $agg_strategy, dc.replayable = $replayable
        MERGE (d:Decision {id: $decision_id}) ON CREATE SET d.summary = $summary, d.action_proposed = $action_proposed, d.confidence = $confidence, d.timestamp = datetime()
        MERGE (d)-[:BASED_ON]->(dc)

        // 3. Steps, Agents, and Results (using UNWIND for batch creation)
        WITH run, d
        UNWIND $steps as step_data
        MERGE (agent:Agent {id: step_data.agent_id})
        MERGE (step:SwarmStep {id: step_data.step_id}) ON CREATE SET step.parameters = step_data.params, step.retry_policy = step_data.policy
        MERGE (run)-[:EXECUTED_STEP]->(step)
        MERGE (step)-[:EXECUTED_BY]->(agent)

        WITH d, step, step_data.results as results_data
        UNWIND results_data as result_data
        MERGE (result:SwarmResult {id: result_data.result_id})
        ON CREATE SET
            result.output = result_data.output,
            result.confidence = result_data.confidence,
            result.actionable = result_data.actionable,
            result.evidence_type = result_data.evidence_type,
            result.error = result_data.error,
            result.timestamp = datetime()
        MERGE (step)-[:PRODUCED]->(result)

        // 4. Causal Links
        WITH d, collect(result) as all_results
        UNWIND $influencing_results as influencing_result_id
        MATCH (res:SwarmResult {id: influencing_result_id})
        MERGE (res)-[rel:CAUSALLY_INFLUENCED]->(d)
        ON CREATE SET
            rel.weight = 1.0,
            rel.confidence_at_time = res.confidence,
            rel.role = 'direct_evidence',
            rel.timestamp = datetime()
        """

        influencing_result_ids = []
        for result in decision.supporting_evidence:
            step_id = next((s.step_id for s in plan.steps if s.agent_id == result.agent_id), None)
            if step_id:
                result_idx = len(run_history.get(step_id, [])) - 1
                if result_idx >= 0:
                    influencing_result_ids.append(f"{step_id}-{result_idx}")

        params = {
            "alert_id": alert.alert_id, "alert_data": json.dumps(alert.data),
            "run_id": plan.plan_id, "objective": plan.objective,
            "context_id": decision.context.context_id, "agg_strategy": decision.context.aggregation_strategy,
            "replayable": decision.context.replayable, "decision_id": decision.decision_id,
            "summary": decision.summary, "action_proposed": decision.action_proposed,
            "confidence": decision.confidence, "steps": steps_params,
            "influencing_results": influencing_result_ids
        }

        self.run_transaction(query, params)

    def save_human_override(self, decision: Decision, human_decision: HumanDecision, outcome: OperationalOutcome, plan: SwarmPlan, run_history: Dict[str, List[SwarmResult]]):
        invalidated_result_ids = []
        for result in decision.supporting_evidence:
            step_id = next((s.step_id for s in plan.steps if s.agent_id == result.agent_id), None)
            if step_id:
                result_idx = len(run_history.get(step_id, [])) - 1
                if result_idx >= 0:
                    invalidated_result_ids.append(f"{step_id}-{result_idx}")

        query = """
        // 1. Match the core Decision node
        MATCH (d:Decision {id: $decision_id})

        // 2. Create the HumanDecision and its outcome
        MERGE (hd:HumanDecision {id: $hd_id})
        ON CREATE SET hd.author = $author, hd.action = $action, hd.override_reason = $reason, hd.timestamp = datetime()
        MERGE (d)-[:OVERRIDDEN_BY]->(hd)
        MERGE (o:OperationalOutcome {id: $outcome_id})
        ON CREATE SET o.status = $status, o.impact_level = $impact, o.resolution_time_seconds = $res_time
        MERGE (hd)-[:RESULTED_IN]->(o)

        // 3. Link invalidated results and penalized agents
        WITH hd
        UNWIND $invalidated_results as invalidated_id
        MATCH (r:SwarmResult {id: invalidated_id})
        MATCH (a:Agent)<-[:EXECUTED_BY]-(:SwarmStep)-[:PRODUCED]->(r)
        MERGE (hd)-[:INVALIDATED]->(r)
        MERGE (hd)-[:PENALIZED]->(a)
        """

        params = {
            "decision_id": decision.decision_id, "hd_id": human_decision.human_decision_id,
            "author": human_decision.author, "action": human_decision.action.value,
            "reason": human_decision.override_reason,
            "outcome_id": outcome.outcome_id, "status": outcome.status,
            "impact": outcome.impact_level, "res_time": outcome.resolution_time_seconds,
            "invalidated_results": invalidated_result_ids
        }

        self.run_transaction(query, params)
        logging.info(f"Human override by {human_decision.author} and its outcome have been saved atomically.")
