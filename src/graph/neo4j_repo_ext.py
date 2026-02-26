"""
Extension methods for Neo4jRepository to support AgentExecution nodes.
This file contains new methods that should be added to the Neo4jRepository class.
"""

# Add these methods to the Neo4jRepository class in neo4j_repo.py

def create_agent_execution(self, decision_id: str, agent_name: str, agent_config: dict) -> str or None:
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
    
    import uuid
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
            if result.peek() is None:
                logger.warning(f"DecisionCandidate {decision_id} not found when creating agent execution.")
                return None
            return result.single()["execution_id"]
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
    RETURN d, collect(e {
        execution_id: e.execution_id,
        agent_name: e.agent_name,
        status: e.status,
        confidence: e.confidence,
        started_at: e.started_at,
        completed_at: e.completed_at,
        duration_ms: e.duration_ms,
        memory_mb: e.memory_mb,
        model_version: e.model_version,
        output_flags: e.output_flags
    }) as executions
    ORDER BY e.started_at DESC
    """
    
    timeline = {
        "decision_id": decision_id,
        "executions": [],
        "total_executions": 0
    }
    
    try:
        with self._driver.session() as session:
            result = session.run(query, {"decision_id": decision_id})
            record = result.single()
            
            if record:
                executions = [e for e in record["executions"] if e is not None]
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
