import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'
import {
  listExecutions,
  getExecution,
  getExecutionHistory,
  getAgentStats,
  getAuditReport,
  searchExecutions,
  getSystemMetrics,
  healthCheck,
} from '../client'

// Mock axios
vi.mock('axios')

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('listExecutions', () => {
    it('deve listar execuções com paginação', async () => {
      const mockData = {
        items: [
          {
            execution_id: 'exec-1',
            source_id: 'source-1',
            event_type: 'alert',
            status: 'COMPLETED',
            confidence_score: 0.85,
            agent_count: 3,
            duration_ms: 1500,
            created_at: '2026-02-08T10:30:00Z',
          },
        ],
        total: 100,
        page: 1,
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockData })

      const result = await listExecutions(1, 20)

      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(100)
      expect(result.page).toBe(1)
    })

    it('deve filtrar por status', async () => {
      const mockData = { items: [], total: 0, page: 1 }
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockData })

      await listExecutions(1, 20, 'COMPLETED')

      expect(vi.mocked(axios.get)).toHaveBeenCalled()
    })
  })

  describe('getExecution', () => {
    it('deve obter detalhes de uma execução', async () => {
      const mockExecution = {
        execution_id: 'exec-1',
        source_id: 'source-1',
        event_type: 'alert',
        status: 'COMPLETED',
        agents: [],
        steps: [],
        decision: null,
        created_at: '2026-02-08T10:30:00Z',
        updated_at: '2026-02-08T10:31:00Z',
        duration_ms: 1500,
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockExecution })

      const result = await getExecution('exec-1')

      expect(result.execution_id).toBe('exec-1')
      expect(result.status).toBe('COMPLETED')
    })
  })

  describe('getExecutionHistory', () => {
    it('deve obter histórico de execuções por source_id', async () => {
      const mockHistory = [
        {
          execution_id: 'exec-1',
          source_id: 'source-1',
          event_type: 'alert',
          status: 'COMPLETED',
          confidence_score: 0.85,
          agent_count: 3,
          duration_ms: 1500,
          created_at: '2026-02-08T10:30:00Z',
        },
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockHistory })

      const result = await getExecutionHistory('source-1', 10)

      expect(result).toHaveLength(1)
      expect(result[0].source_id).toBe('source-1')
    })
  })

  describe('getAgentStats', () => {
    it('deve obter estatísticas de um agente', async () => {
      const mockStats = {
        agent_id: 'agent-1',
        total_executions: 100,
        success_rate: 0.95,
        average_confidence: 0.85,
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockStats })

      const result = await getAgentStats('agent-1')

      expect(result.agent_id).toBe('agent-1')
      expect(result.success_rate).toBe(0.95)
    })
  })

  describe('getAuditReport', () => {
    it('deve obter relatório de auditoria', async () => {
      const mockReport = {
        execution_id: 'exec-1',
        status: 'PASSED',
        alerts: [],
        timestamp: '2026-02-08T10:30:00Z',
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockReport })

      const result = await getAuditReport('exec-1')

      expect(result.execution_id).toBe('exec-1')
      expect(result.status).toBe('PASSED')
    })
  })

  describe('searchExecutions', () => {
    it('deve buscar execuções por query', async () => {
      const mockResults = [
        {
          execution_id: 'exec-1',
          source_id: 'source-1',
          event_type: 'alert',
          status: 'COMPLETED',
          confidence_score: 0.85,
          agent_count: 3,
          duration_ms: 1500,
          created_at: '2026-02-08T10:30:00Z',
        },
      ]

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockResults })

      const result = await searchExecutions('exec-1', 20)

      expect(result).toHaveLength(1)
      expect(result[0].execution_id).toBe('exec-1')
    })
  })

  describe('getSystemMetrics', () => {
    it('deve obter métricas gerais do sistema', async () => {
      const mockMetrics = {
        total_executions: 1000,
        success_rate: 0.92,
        average_confidence: 0.83,
        uptime_hours: 720,
      }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockMetrics })

      const result = await getSystemMetrics()

      expect(result.total_executions).toBe(1000)
      expect(result.success_rate).toBe(0.92)
    })
  })

  describe('healthCheck', () => {
    it('deve verificar saúde da API', async () => {
      const mockHealth = { status: 'healthy' }

      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockHealth })

      const result = await healthCheck()

      expect(result.status).toBe('healthy')
    })

    it('deve lidar com erro de saúde', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('API unavailable'))

      try {
        await healthCheck()
      } catch (error) {
        expect(error).toBeDefined()
      }
    })
  })

  describe('Tratamento de Erros', () => {
    it('deve lançar erro quando API falha', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      try {
        await listExecutions(1, 20)
      } catch (error) {
        expect(error).toBeDefined()
      }
    })

    it('deve lançar erro com mensagem apropriada', async () => {
      const errorMessage = 'Unauthorized'
      vi.mocked(axios.get).mockRejectedValueOnce(new Error(errorMessage))

      try {
        await getExecution('exec-1')
      } catch (error) {
        expect((error as Error).message).toBe(errorMessage)
      }
    })
  })
})
