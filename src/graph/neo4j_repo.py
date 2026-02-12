"""
Neo4j Repository - Graph Database Access Layer

Handles persistence of Agents, Alerts, Decisions and their relationships.
"""

import os
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from neo4j import GraphDatabase, Driver

from src.models.alert import Alert

logger = logging.getLogger(__name__)

class Neo4jRepository:
    """Repository for interacting with Neo4j graph database."""

    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "strads123")
        self._driver: Optional[Driver] = None

    def connect(self):
        """Establish connection to Neo4j."""
        if not self._driver:
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                self.verify_connectivity()
                logger.info("Connected to Neo4j at %s", self.uri)
            except Exception as e:
                logger.error("Failed to connect to Neo4j: %s", e)
                raise

    def verify_connectivity(self):
        """Check if connection is alive."""
        if self._driver:
            self._driver.verify_connectivity()

    def close(self):
        """Close the driver."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def create_alert(self, alert_model: Alert):
        """
        Persist an Alert node and link it to a Service.
        RELATIONSHIP: (:Alert)-[:IMPACTS]->(:Service)
        """
        query = """
        MERGE (s:Service {name: $service_name})
        CREATE (a:Alert {
            fingerprint: $fingerprint,
            timestamp: $timestamp,
            severity: $severity,
            description: $description,
            source: $source
        })
        MERGE (a)-[:IMPACTS]->(s)
        RETURN a.fingerprint as fingerprint
        """
        params = {
            "service_name": alert_model.service,
            "fingerprint": alert_model.fingerprint,
            "timestamp": alert_model.timestamp.isoformat(),
            "severity": alert_model.severity,
            "description": alert_model.description,
            "source": alert_model.source.value
        }
        
        with self._driver.session() as session:
            result = session.run(query, params)
            return result.single()["fingerprint"]

    # Placeholder for future methods
    def create_incident_from_alert(self, _alert_fingerprint: str):
        # Intentionally left unimplemented in this prototype.
        # Implement when incident creation workflow is defined.
        return None
        
    def save_swarm_hypothesis(self, _incident_id: str, _swarm_result):
        # Persist swarm hypothesis for an incident (TBD)
        # Returning None indicates not implemented in this stub.
        return None

    def save_decision_candidate(self, candidate: Any) -> Optional[str]:
        """
        Persist a DecisionCandidate node and link to the Alert.
        RELATIONSHIP: (:Alert)-[:HAS_CANDIDATE]->(:DecisionCandidate)
        """
        query = """
        MATCH (a:Alert {fingerprint: $alert_ref})
        CREATE (d:DecisionCandidate {
            decision_id: $did,
            summary: $summary,
            status: $status,
            primary_hypothesis: $hypothesis,
            risk: $risk,
            automation: $automation,
            created_at: $created_at
        })
        MERGE (a)-[:HAS_CANDIDATE]->(d)
        RETURN d.decision_id as id
        """
        
        params = {
            "alert_ref": candidate.alert_reference,
            "did": str(candidate.decision_id),
            "summary": candidate.summary,
            "status": candidate.status.value,
            "hypothesis": candidate.primary_hypothesis,
            "risk": candidate.risk_assessment,
            "automation": candidate.automation_level.value,
            "created_at": candidate.created_at.isoformat()
        }
        
        with self._driver.session() as session:
            result = session.run(query, params)
            if result.peek() is None:
                logger.warning(f"Alert {candidate.alert_reference} not found when saving decision.")
                return None
            return result.single()["id"]

    def record_decision_outcome(self, validation: Any):
        """
        Updates the DecisionCandidate node with the outcome and creates a Review node.
        RELATIONSHIP: (:DecisionCandidate)-[:HAS_REVIEW]->(:Review)
        """
        status = "APPROVED" if validation.is_approved else "REJECTED"
        
        query = """
        MATCH (d:DecisionCandidate {decision_id: $did})
        SET d.status = $status, d.feedback = $feedback, d.validated_at = $validated_at
        CREATE (r:Review {
             validation_id: $vid,
             is_approved: $is_approved,
             feedback: $feedback,
             validated_by: $validated_by,
             timestamp: $validated_at
        })
        MERGE (d)-[:HAS_REVIEW]->(r)

        WITH d, r
        OPTIONAL MATCH (d)-[:SUGGESTS_PROCEDURE]->(p:Procedure)
        FOREACH (_ IN CASE WHEN p IS NULL THEN [] ELSE [1] END |
            SET p.success_count = coalesce(p.success_count, 0) + CASE WHEN $worked THEN 1 ELSE 0 END,
                p.failure_count = coalesce(p.failure_count, 0) + CASE WHEN $worked THEN 0 ELSE 1 END,
                p.confidence = CASE
                    WHEN $worked THEN CASE WHEN coalesce(p.confidence, 0.5) + 0.05 > 0.99 THEN 0.99 ELSE coalesce(p.confidence, 0.5) + 0.05 END
                    ELSE CASE WHEN coalesce(p.confidence, 0.5) - 0.05 < 0.1 THEN 0.1 ELSE coalesce(p.confidence, 0.5) - 0.05 END
                END,
                p.updated_at = datetime()
            CREATE (pf:ProcedureFeedback {
                feedback: $feedback,
                worked: $worked,
                validated_by: $validated_by,
                timestamp: $validated_at
            })
            MERGE (p)-[:HAS_FEEDBACK]->(pf)
            MERGE (d)-[:HAS_FEEDBACK]->(pf)
        )
        """
        
        # Use current time if validation.validated_at is None
        val_time = validation.validated_at or datetime.now(timezone.utc)

        feedback_text = (validation.feedback or "").lower()
        worked = validation.is_approved and any(k in feedback_text for k in ["funcionou", "resolved", "resolvido", "worked", "sucesso", "success"])

        params = {
            "did": str(validation.decision_id),
            "status": status,
            "feedback": validation.feedback or "",
            "validated_at": val_time.isoformat(),
            "vid": validation.validation_id,
            "is_approved": validation.is_approved,
            "validated_by": validation.validated_by,
            "worked": worked,
        }
        
        with self._driver.session() as session:
            session.run(query, params)

    def get_pending_decisions(self) -> list[Dict[str, Any]]:
        """
        Retrieves all DecisionCandidate nodes.
        """
        query = """
        MATCH (d:DecisionCandidate)
        OPTIONAL MATCH (a:Alert)-[:HAS_CANDIDATE]->(d)
        RETURN d, a.service as service, a.severity as severity
        ORDER BY d.created_at DESC
        """
        
        decisions = []
        with self._driver.session() as session:
            result = session.run(query)
            for record in result:
                d = record["d"]
                decisions.append({
                    "decision_id": d["decision_id"],
                    "summary": d["summary"],
                    "primary_hypothesis": d["primary_hypothesis"],
                    "risk_assessment": d["risk"],
                    "automation_level": d["automation"],
                    "created_at": d["created_at"],
                    "status": d["status"],
                    "service": record["service"],
                    "severity": record["severity"]
                })
        return decisions

    def create_agent_execution(self, decision_id: str, agent_name: str, agent_config: dict) -> Optional[str]:
        """
        Create an AgentExecution node and link to DecisionCandidate.
        RELATIONSHIP: (:DecisionCandidate)-[:EXECUTED_BY]->(:AgentExecution)
        """
        query = """
        MATCH (d:DecisionCandidate {decision_id: $decision_id})
        CREATE (e:AgentExecution {
            execution_id: $execution_id,
            agent_name: $agent_name,
            status: $status,
            confidence: $confidence,
            started_at: $started_at,
            completed_at: $completed_at,
            duration_ms: $duration_ms,
            input_params: $input_params,
            output_flags: $output_flags,
            memory_mb: $memory_mb,
            model_version: $model_version
        })
        MERGE (d)-[:EXECUTED_BY]->(e)
        RETURN e.execution_id as execution_id
        """
        
        execution_id = str(uuid.uuid4())
        
        params = {
            "decision_id": decision_id,
            "execution_id": execution_id,
            "agent_name": agent_name,
            "status": agent_config.get("status", "pending"),
            "confidence": agent_config.get("confidence", 0.5),
            "started_at": agent_config.get("started_at", None),
            "completed_at": agent_config.get("completed_at"),
            "duration_ms": agent_config.get("duration_ms", 0),
            "input_params": str(agent_config.get("input_params", {})),
            "output_flags": "|".join(agent_config.get("output_flags", [])),
            "memory_mb": agent_config.get("memory_mb", 128),
            "model_version": agent_config.get("model_version", "v1.0.0")
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, params)
                record = result.single()
                if record is None:
                    logger.warning(f"DecisionCandidate {decision_id} not found when creating agent execution.")
                    return None
                return record["execution_id"]
        except Exception as e:
            logger.error(f"Error creating agent execution: {e}")
            return None

    def get_incident_timeline(self, decision_id: str) -> dict:
        """
        Retrieve timeline of agent executions for a decision.
        Returns timeline events from AgentExecution nodes.
        """
        query = """
        MATCH (d:DecisionCandidate {decision_id: $decision_id})
        OPTIONAL MATCH (d)-[:EXECUTED_BY]->(e:AgentExecution)
        RETURN d, e
        """
        
        timeline = {
            "decision_id": decision_id,
            "executions": [],
            "total_executions": 0
        }
        
        try:
            with self._driver.session() as session:
                result = session.run(query, {"decision_id": decision_id})
                executions = []
                for record in result:
                    if record['e'] is not None:
                        execution = {
                            'execution_id': record['e'].get('execution_id'),
                            'agent_name': record['e'].get('agent_name'),
                            'status': record['e'].get('status'),
                            'confidence': record['e'].get('confidence'),
                            'started_at': record['e'].get('started_at'),
                            'completed_at': record['e'].get('completed_at'),
                            'duration_ms': record['e'].get('duration_ms'),
                            'memory_mb': record['e'].get('memory_mb'),
                            'model_version': record['e'].get('model_version'),
                            'output_flags': record['e'].get('output_flags')
                        }
                        executions.append(execution)
                
                # Sort by started_at in descending order
                executions.sort(key=lambda x: x.get('started_at', ''), reverse=True)
                timeline["executions"] = executions
                timeline["total_executions"] = len(executions)
        except Exception as e:
            logger.error(f"Error fetching timeline for decision {decision_id}: {e}")
        
        return timeline

    def get_all_incidents(self) -> list:
        """
        Retrieve all incidents (DecisionCandidate nodes) with execution count.
        """
        query = """
        MATCH (d:DecisionCandidate)
        OPTIONAL MATCH (a:Alert)-[:HAS_CANDIDATE]->(d)
        OPTIONAL MATCH (d)-[:EXECUTED_BY]->(e:AgentExecution)
        RETURN 
            d.decision_id as decision_id,
            d.summary as summary,
            d.status as status,
            d.created_at as created_at,
            d.risk as risk,
            a.service as service,
            a.severity as severity,
            count(e) as execution_count
        ORDER BY d.created_at DESC
        """
        
        incidents = []
        try:
            with self._driver.session() as session:
                result = session.run(query)
                for record in result:
                    summary = record["summary"] or ""
                    incidents.append({
                        "decision_id": record["decision_id"],
                        "summary": summary[:100] + "..." if len(summary) > 100 else summary,
                        "full_summary": summary,
                        "status": record["status"],
                        "created_at": record["created_at"],
                        "risk": record["risk"],
                        "service": record["service"],
                        "severity": record["severity"],
                        "execution_count": record["execution_count"] or 0
                    })
        except Exception as e:
            logger.error(f"Error fetching all incidents: {e}")
        
        return incidents

