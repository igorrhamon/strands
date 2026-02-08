/**
 * Tipos para Strands Execution Monitor
 */

export interface Agent {
  id: string
  name: string
  type: 'THREAT_INTEL' | 'LOG_ANALYZER' | 'METRICS_ANALYZER' | 'HUMAN_ANALYST'
  confidence: number
  weight: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  evidence_count: number
  last_updated: string
}

export interface ExecutionStep {
  step_index: number
  agent_id: string
  agent_name: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  confidence: number
  timestamp: string
  duration_ms: number
  result: string
}

export interface Decision {
  decision_type: 'APPROVED' | 'REJECTED' | 'ESCALATED' | 'PENDING_HUMAN_APPROVAL'
  confidence_score: number
  reasoning: string
  timestamp: string
}

export interface Execution {
  execution_id: string
  source_id: string
  event_type: string
  source_system: string
  priority: number
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  agents: Agent[]
  steps: ExecutionStep[]
  decision: Decision | null
  created_at: string
  updated_at: string
  duration_ms: number
  error?: string
}

export interface ExecutionListItem {
  execution_id: string
  source_id: string
  event_type: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  confidence_score: number
  agent_count: number
  created_at: string
  duration_ms: number
}

export interface ConfidenceLevel {
  level: 'VERY_LOW' | 'LOW' | 'MEDIUM' | 'HIGH' | 'VERY_HIGH'
  color: string
  percentage: number
}

export interface AgentStats {
  total_executions: number
  successful_executions: number
  failed_executions: number
  average_confidence: number
  average_duration_ms: number
}
