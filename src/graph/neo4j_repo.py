"""
Neo4j Repository - Graph Database Access Layer

Handles persistence of Agents, Alerts, Decisions and their relationships.
"""

import os
import logging
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
        """
        
        # Use current time if validation.validated_at is None
        val_time = validation.validated_at or datetime.now(timezone.utc)

        params = {
            "did": str(validation.decision_id),
            "status": status,
            "feedback": validation.feedback or "",
            "validated_at": val_time.isoformat(),
            "vid": validation.validation_id,
            "is_approved": validation.is_approved,
            "validated_by": validation.validated_by
        }
        
        with self._driver.session() as session:
            session.run(query, params)

    def get_pending_decisions(self) -> list[Dict[str, Any]]:
        """
        Retrieves all DecisionCandidate nodes with status 'PROPOSED'.
        """
        query = """
        MATCH (d:DecisionCandidate {status: 'PROPOSED'})
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

