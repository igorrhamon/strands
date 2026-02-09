/**
 * Cliente API para Strands Backend
 * Comunicação com endpoints de execução e auditoria
 */

import axios from 'axios'
import type { Execution, ExecutionListItem } from '../types'

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1'

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Listar todas as execuções com paginação
 */
export async function listExecutions(
  page: number = 1,
  limit: number = 20,
  status?: string
): Promise<{ items: ExecutionListItem[]; total: number; page: number }> {
  const params = new URLSearchParams({
    page: page.toString(),
    limit: limit.toString(),
  })

  if (status) {
    params.append('status', status)
  }

  const response = await client.get(`/executions?${params.toString()}`)
  return response.data
}

/**
 * Obter detalhes de uma execução específica
 */
export async function getExecution(executionId: string): Promise<Execution> {
  const response = await client.get(`/executions/${executionId}`)
  return response.data
}

/**
 * Obter histórico de execuções por source_id
 */
export async function getExecutionHistory(
  sourceId: string,
  limit: number = 10
): Promise<ExecutionListItem[]> {
  const response = await client.get(`/executions/source/${sourceId}/history`, {
    params: { limit },
  })
  return response.data
}

/**
 * Obter estatísticas de um agente
 */
export async function getAgentStats(agentId: string) {
  const response = await client.get(`/agents/${agentId}/stats`)
  return response.data
}

/**
 * Obter relatório de auditoria de uma execução
 */
export async function getAuditReport(executionId: string) {
  const response = await client.get(`/audit/execute`, {
    params: { execution_id: executionId },
  })
  return response.data
}

/**
 * Buscar execuções por critério
 */
export async function searchExecutions(
  query: string,
  limit: number = 20
): Promise<ExecutionListItem[]> {
  const response = await client.get('/executions/search', {
    params: { q: query, limit },
  })
  return response.data
}

/**
 * Obter métricas gerais do sistema
 */
export async function getSystemMetrics() {
  const response = await client.get('/metrics/summary')
  return response.data
}

/**
 * Verificar saúde da API
 */
export async function healthCheck(): Promise<{ status: string }> {
  const response = await client.get('/health')
  return response.data
}

export default client
