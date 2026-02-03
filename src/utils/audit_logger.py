"""
Audit Logger - Append-Only Decision Logging

Implements immutable audit trail for all decision recommendations.
Every decision, including intermediate steps, is logged.

Constitution Principle IV: Rastreabilidade - TUDO é logado, decisões são replay-able.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from src.models.audit_log import AuditLog
from src.models.decision import Decision

logger = logging.getLogger(__name__)


class AuditLoggerError(Exception):
    """Raised when audit logging fails."""
    pass


class AuditLogger:
    """
    Append-only audit logger for decision trail.
    
    Writes JSON Lines (JSONL) format for easy parsing and replay.
    Each line is a complete AuditLog entry.
    """
    
    DEFAULT_LOG_FILE = "audit_decisions.jsonl"
    
    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_filename: str = DEFAULT_LOG_FILE,
    ):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs. Defaults to ./logs.
            log_filename: Name of the log file.
        """
        self._log_dir = log_dir or Path("./logs")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = self._log_dir / log_filename
        
        logger.info(f"[AuditLogger] Initialized at {self._log_path}")
    
    def log_decision(
        self,
        decision: Decision,
        cluster_id: str,
        alert_fingerprints: list[str],
        agent_version: str = "1.0.0",
    ) -> AuditLog:
        """
        Log a decision to the audit trail.
        
        Args:
            decision: The decision to log.
            cluster_id: ID of the alert cluster.
            alert_fingerprints: Fingerprints of alerts in cluster.
            agent_version: Version of the decision agent.
        
        Returns:
            The AuditLog entry that was written.
        """
        # Extract semantic evidence IDs as strings
        semantic_evidence_ids = [
            str(e.decision_id) for e in getattr(decision, "semantic_evidence", [])
        ]

        # Build a minimal decision_output payload (keep the full object for replay)
        decision_output = decision

        # Agent identity - try env var then fallback
        import os
        agent_id = os.getenv("AGENT_ID", "agent-unknown")

        # Execution duration: decision may provide it, otherwise default to 0
        execution_duration_ms = getattr(decision, "execution_duration_ms", 0) or 0

        # Build audit log
        audit_log = AuditLog(
            timestamp=datetime.now(timezone.utc),
            agent_version=agent_version,
            decision_id=decision.decision_id,
            alert_ids=alert_fingerprints,
            cluster_id=str(cluster_id) if cluster_id is not None else None,
            metric_context=getattr(decision, "metric_context", {}),
            semantic_evidence_ids=semantic_evidence_ids,
            decision_output=decision_output,
            agent_id=agent_id,
            execution_duration_ms=int(execution_duration_ms),
            human_validation_status=getattr(decision, "human_validation_status", None) or decision.human_validation_status,
        )
        
        # Write to log file
        self._append_log(audit_log)
        
        logger.info(
            f"[AuditLogger] Logged decision {audit_log.decision_id} "
            f"(state={audit_log.decision_state}, confidence={audit_log.confidence:.2f})"
        )
        
        return audit_log
    
    def log_validation(
        self,
        decision_id: UUID,
        validated_by: str,
        approved: bool,
    ) -> None:
        """
        Log a human validation event.
        
        Args:
            decision_id: ID of the decision being validated.
            validated_by: ID of the human validator.
            approved: Whether the decision was approved.
        """
        event = {
            "event_type": "validation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": str(decision_id),
            "validated_by": validated_by,
            "approved": approved,
        }
        
        self._append_raw(event)
        
        logger.info(
            f"[AuditLogger] Validation logged: {decision_id} "
            f"({'approved' if approved else 'rejected'} by {validated_by})"
        )
    
    def log_embedding_created(
        self,
        decision_id: UUID,
        point_id: str,
    ) -> None:
        """
        Log embedding creation event (post-confirmation).
        
        Constitution Principle III: Only log embedding AFTER confirmation.
        
        Args:
            decision_id: ID of the confirmed decision.
            point_id: Qdrant point ID for the embedding.
        """
        event = {
            "event_type": "embedding_created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": str(decision_id),
            "point_id": point_id,
        }
        
        self._append_raw(event)
        
        logger.info(
            f"[AuditLogger] Embedding logged: decision={decision_id}, point={point_id}"
        )
    
    def _append_log(self, audit_log: AuditLog) -> None:
        """
        Append an AuditLog to the log file.
        
        Args:
            audit_log: Log entry to append.
        """
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                # Use getattr to tolerate variations in AuditLog shape
                decision_out = getattr(audit_log, "decision_output", None)
                # Flatten some fields for JSONL
                log_dict = {
                    "event_type": "decision",
                    "log_id": str(getattr(audit_log, "log_id", "")),
                    "timestamp": getattr(audit_log, "timestamp", datetime.now(timezone.utc)).isoformat(),
                    "agent_version": getattr(audit_log, "agent_version", None),
                    "decision_id": str(getattr(audit_log, "decision_id", getattr(decision_out, "decision_id", ""))),
                    "cluster_id": getattr(audit_log, "cluster_id", None),
                    "alert_fingerprints": getattr(audit_log, "alert_ids", getattr(audit_log, "alert_fingerprints", [])),
                    "decision_state": getattr(decision_out, "decision_state", None) if decision_out else None,
                    "confidence": getattr(decision_out, "confidence", None) if decision_out else None,
                    "rules_applied": getattr(decision_out, "rules_applied", [] ) if decision_out else [],
                    "semantic_evidence_ids": getattr(audit_log, "semantic_evidence_ids", []),
                    "llm_contribution": getattr(decision_out, "llm_contribution", None) if decision_out else None,
                    "llm_reason": getattr(decision_out, "llm_reason", None) if decision_out else None,
                    "human_validation_status": getattr(audit_log, "human_validation_status", None),
                    "validated_by": getattr(decision_out, "validated_by", None) if decision_out else None,
                    "validated_at": (
                        getattr(decision_out, "validated_at", None).isoformat()
                        if getattr(decision_out, "validated_at", None) else None
                    ),
                    "justification": getattr(decision_out, "justification", None) if decision_out else None,
                }
                f.write(json.dumps(log_dict) + "\n")
        
        except Exception as e:
            raise AuditLoggerError(f"Failed to append audit log: {e}") from e
    
    def _append_raw(self, event: dict) -> None:
        """
        Append a raw event dict to the log file.
        
        Args:
            event: Event dict to append.
        """
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            raise AuditLoggerError(f"Failed to append raw event: {e}") from e
    
    def read_all_logs(self) -> list[dict]:
        """
        Read all log entries from the audit file.
        
        Returns:
            List of log entries as dicts.
        """
        if not self._log_path.exists():
            return []
        
        logs = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        return logs
    
    def find_decision_logs(self, decision_id: UUID) -> list[dict]:
        """
        Find all log entries for a specific decision.
        
        Args:
            decision_id: ID of the decision.
        
        Returns:
            List of related log entries.
        """
        decision_str = str(decision_id)
        return [
            log for log in self.read_all_logs()
            if log.get("decision_id") == decision_str
        ]
    
    def get_replay_context(self, decision_id: UUID) -> Optional[dict]:
        """
        Get replay context for a decision.
        
        Constitution Principle IV: Decisions must be replay-able.
        
        Args:
            decision_id: ID of the decision to replay.
        
        Returns:
            Dict with all context needed for replay, or None.
        """
        logs = self.find_decision_logs(decision_id)
        
        if not logs:
            return None
        
        # Find the main decision log
        decision_log = next(
            (l for l in logs if l.get("event_type") == "decision"),
            None
        )
        
        if not decision_log:
            return None
        
        # Find validation event if any
        validation_log = next(
            (l for l in logs if l.get("event_type") == "validation"),
            None
        )
        
        # Find embedding event if any
        embedding_log = next(
            (l for l in logs if l.get("event_type") == "embedding_created"),
            None
        )
        
        return {
            "decision": decision_log,
            "validation": validation_log,
            "embedding": embedding_log,
            "can_replay": True,
            "rules_applied": decision_log.get("rules_applied", []),
            "semantic_evidence_ids": decision_log.get("semantic_evidence_ids", []),
        }
    
    def clear_logs(self) -> None:
        """
        Clear all logs. USE WITH CAUTION - for testing only.
        """
        if self._log_path.exists():
            self._log_path.unlink()
        logger.warning("[AuditLogger] Logs cleared")
