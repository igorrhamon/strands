/**
 * Página de Detalhes de Execução
 * Exibe informações completas de uma execução específica
 */

import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getExecution } from '../api/client'
import type { Execution } from '../types'
import { formatDate, formatDuration, getStatusColor, getConfidenceColor } from '../utils/format'
import { ArrowLeft, AlertCircle, CheckCircle, Clock, Zap, BarChart3 } from 'lucide-react'
import { AgentCard } from '../components/AgentCard'
import { ExecutionTimeline } from '../components/ExecutionTimeline'
import { ConfidenceChart } from '../components/ConfidenceChart'

export function ExecutionDetail() {
  const { executionId } = useParams<{ executionId: string }>()
  const navigate = useNavigate()
  const [execution, setExecution] = useState<Execution | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadExecution()
  }, [executionId])

  async function loadExecution() {
    if (!executionId) return

    try {
      setLoading(true)
      setError(null)
      const data = await getExecution(executionId)
      setExecution(data)
    } catch (err) {
      setError('Erro ao carregar detalhes da execução')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Zap className="w-12 h-12 text-blue-500 animate-pulse mx-auto mb-4" />
          <p className="text-gray-600">Carregando detalhes da execução...</p>
        </div>
      </div>
    )
  }

  if (error || !execution) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate('/executions')}
          className="flex items-center gap-2 text-blue-500 hover:text-blue-700"
        >
          <ArrowLeft className="w-5 h-5" />
          Voltar
        </button>
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
          <AlertCircle className="w-6 h-6 inline mr-2" />
          {error || 'Execução não encontrada'}
        </div>
      </div>
    )
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-6 h-6 text-green-500" />
      case 'FAILED':
        return <AlertCircle className="w-6 h-6 text-red-500" />
      case 'RUNNING':
        return <Zap className="w-6 h-6 text-blue-500 animate-pulse" />
      case 'PENDING':
        return <Clock className="w-6 h-6 text-yellow-500" />
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/executions')}
          className="flex items-center gap-2 text-blue-500 hover:text-blue-700"
        >
          <ArrowLeft className="w-5 h-5" />
          Voltar
        </button>
      </div>

      {/* Status Card */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-4">
              {getStatusIcon(execution.status)}
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {execution.execution_id.substring(0, 20)}...
                </h1>
                <p className={`text-lg font-semibold ${getStatusColor(execution.status)}`}>
                  {execution.status}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
              <div>
                <p className="text-sm text-gray-600">Fonte</p>
                <p className="text-lg font-semibold text-gray-900">{execution.source_id}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Tipo de Evento</p>
                <p className="text-lg font-semibold text-gray-900">{execution.event_type}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Sistema</p>
                <p className="text-lg font-semibold text-gray-900">{execution.source_system}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Prioridade</p>
                <p className="text-lg font-semibold text-gray-900">{execution.priority}/10</p>
              </div>
            </div>
          </div>

          {/* Confiança */}
          <div className="text-right">
            <p className="text-sm text-gray-600 mb-2">Confiança Final</p>
            <div className="flex items-center justify-end gap-3">
              <div className="text-right">
                <p className={`text-4xl font-bold ${getConfidenceColor(execution.decision?.confidence_score || 0)}`}>
                  {((execution.decision?.confidence_score || 0) * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Informações Gerais */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-600 mb-2">Criado em</p>
          <p className="text-lg font-semibold text-gray-900">{formatDate(execution.created_at)}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-600 mb-2">Atualizado em</p>
          <p className="text-lg font-semibold text-gray-900">{formatDate(execution.updated_at)}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-600 mb-2">Duração Total</p>
          <p className="text-lg font-semibold text-gray-900">{formatDuration(execution.duration_ms)}</p>
        </div>
      </div>

      {/* Gráfico de Confiança */}
      {execution.agents.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-5 h-5 text-blue-500" />
            <h2 className="text-xl font-bold text-gray-900">Confiança dos Agentes</h2>
          </div>
          <ConfidenceChart agents={execution.agents} />
        </div>
      )}

      {/* Agentes */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-gray-900">Agentes Executados ({execution.agents.length})</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {execution.agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </div>

      {/* Timeline */}
      {execution.steps.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Timeline de Execução</h2>
          <ExecutionTimeline steps={execution.steps} />
        </div>
      )}

      {/* Decisão */}
      {execution.decision && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Decisão Final</h2>
          <div className="space-y-4">
            <div>
              <p className="text-sm text-gray-600">Tipo de Decisão</p>
              <p className="text-lg font-semibold text-gray-900">{execution.decision.decision_type}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Raciocínio</p>
              <p className="text-gray-700 mt-2">{execution.decision.reasoning}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Timestamp</p>
              <p className="text-gray-700">{formatDate(execution.decision.timestamp)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Erro */}
      {execution.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <p className="text-sm text-gray-600 mb-2">Erro</p>
          <p className="text-red-700 font-mono text-sm">{execution.error}</p>
        </div>
      )}
    </div>
  )
}
