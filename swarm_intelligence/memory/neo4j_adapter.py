
import logging
from neo4j import GraphDatabase, Driver
from typing import Dict, Any, List

from swarm_intelligence.core.models import (
    Alert, SwarmPlan, SwarmStep, SwarmResult, Decision,
    HumanDecision, OperationalOutcome
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
        ]
        for query in schema_queries:
            self.run_transaction(query)
        logging.info("Neo4j schema constraints ensured.")

    def save_swarm_run(self, plan: SwarmPlan, alert: Alert, run_history: Dict[str, List[SwarmResult]], decision: Decision):
        # 1. Create Alert and SwarmRun
        self.run_transaction(
            """
            MERGE (alert:Alert {id: $alert_id})
            ON CREATE SET alert.data = $alert_data
            MERGE (run:SwarmRun {id: $run_id})
            ON CREATE SET run.objective = $objective, run.timestamp = datetime()
            MERGE (alert)-[:TRIGGERED]->(run)
            """, {
                "alert_id": alert.alert_id, "alert_data": str(alert.data),
                "run_id": plan.plan_id, "objective": plan.objective
            }
        )

        # 2. Create Agents, Steps, and Results
        for step in plan.steps:
            self.run_transaction(
                """
                MERGE (agent:Agent {id: $agent_id})
                MERGE (step:SwarmStep {id: $step_id})
                ON CREATE SET step.parameters = $params
                MERGE (run:SwarmRun {id: $run_id})
                MERGE (run)-[:EXECUTED_STEP]->(step)
                MERGE (step)-[:EXECUTED_BY]->(agent)
                """, {
                    "agent_id": step.agent_id, "step_id": step.step_id,
                    "params": str(step.parameters), "run_id": plan.plan_id
                }
            )

            for i, result in enumerate(run_history.get(step.step_id, [])):
                result_id = f"{step.step_id}-{i}"
                self.run_transaction(
                    """
                    MATCH (step:SwarmStep {id: $step_id})
                    MERGE (result:SwarmResult {id: $result_id})
                    ON CREATE SET
                        result.output = $output,
                        result.confidence = $confidence,
                        result.actionable = $actionable,
                        result.evidence_type = $evidence_type,
                        result.error = $error,
                        result.timestamp = datetime()
                    MERGE (step)-[:PRODUCED]->(result)
                    """, {
                        "step_id": step.step_id, "result_id": result_id,
                        "output": str(result.output), "confidence": result.confidence,
                        "actionable": result.actionable, "evidence_type": result.evidence_type.value,
                        "error": result.error
                    }
                )

        # 3. Create Decision and link influencing results
        self.run_transaction(
            """
            MERGE (d:Decision {id: $decision_id})
            ON CREATE SET
                d.summary = $summary,
                d.action_proposed = $action_proposed,
                d.confidence = $confidence,
                d.timestamp = datetime()
            """, {
                "decision_id": decision.decision_id, "summary": decision.summary,
                "action_proposed": decision.action_proposed, "confidence": decision.confidence
            }
        )
        for result in decision.supporting_evidence:
            # This requires a way to map SwarmResult back to a unique ID
            # For now, we assume the last result of a step is the one that influenced the decision
            step_id = next(s.step_id for s in plan.steps if s.agent_id == result.agent_id)
            result_idx = len(run_history.get(step_id, [])) - 1
            if result_idx >= 0:
                result_id = f"{step_id}-{result_idx}"
                self.run_transaction(
                    "MATCH (r:SwarmResult {id: $result_id}), (d:Decision {id: $decision_id}) MERGE (r)-[:INFLUENCED]->(d)",
                    {"result_id": result_id, "decision_id": decision.decision_id}
                )

    def save_human_override(self, decision: Decision, human_decision: HumanDecision, outcome: OperationalOutcome):
        self.run_transaction(
            """
            MATCH (d:Decision {id: $decision_id})
            MERGE (hd:HumanDecision {id: $hd_id})
            ON CREATE SET
                hd.author = $author,
                hd.action = $action,
                hd.override_reason = $reason,
                hd.timestamp = datetime()
            MERGE (d)-[:OVERRIDDEN_BY]->(hd)
            MERGE (o:OperationalOutcome {id: $outcome_id})
            ON CREATE SET
                o.status = $status,
                o.impact_level = $impact,
                o.resolution_time_seconds = $res_time
            MERGE (hd)-[:RESULTED_IN]->(o)
            """, {
                "decision_id": decision.decision_id, "hd_id": human_decision.human_decision_id,
                "author": human_decision.author, "action": human_decision.action.value,
                "reason": human_decision.override_reason,
                "outcome_id": outcome.outcome_id, "status": outcome.status,
                "impact": outcome.impact_level, "res_time": outcome.resolution_time_seconds
            }
        )
        logging.info(f"Human override by {human_decision.author} and its outcome have been saved.")
