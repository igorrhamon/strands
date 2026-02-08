/**
 * Componente AgentCard
 * Exibe informações de um agente com confiança e status
 */

import React from 'react'
import type { Agent } from '../types'
import { getConfidenceColor } from '../utils/format'
import { CheckCircle, AlertCircle, Clock, Zap } from 'lucide-react'

interface AgentCardProps {
  agent: Agent
}

export function AgentCard({ agent }: AgentCardProps) {
  function getStatusIcon(status: string) {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'FAILED':
        return <AlertCircle className="w-5 h-5 text-red-500" />
      case 'RUNNING':
        return <Zap className="w-5 h-5 text-blue-500 animate-pulse" />
      case 'PENDING':
        return <Clock className="w-5 h-5 text-yellow-500" />
      default:
        return null
    }
  }

  function getAgentColor(type: string) {
    switch (type) {
      case 'THREAT_INTEL':
        return 'bg-purple-50 border-purple-200'
      case 'LOG_ANALYZER':
        return 'bg-blue-50 border-blue-200'
      case 'METRICS_ANALYZER':
        return 'bg-green-50 border-green-200'
      case 'HUMAN_ANALYST':
        return 'bg-orange-50 border-orange-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  return (
    <div className={`rounded-lg border p-4 ${getAgentColor(agent.type)}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900">{agent.name}</h3>
          <p className="text-sm text-gray-600 mt-1">{agent.type}</p>
        </div>
        <div className="flex items-center gap-2">
          {getStatusIcon(agent.status)}
          <span className="text-xs font-medium text-gray-600">{agent.status}</span>
        </div>
      </div>

      {/* Confiança */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-sm font-medium text-gray-700">Confiança</p>
          <p className={`text-lg font-bold ${getConfidenceColor(agent.confidence)}`}>
            {(agent.confidence * 100).toFixed(0)}%
          </p>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full ${getConfidenceColor(agent.confidence)}`}
            style={{ width: `${agent.confidence * 100}%` }}
          ></div>
        </div>
      </div>

      {/* Peso e Evidência */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-600">Peso</p>
          <p className="text-lg font-semibold text-gray-900">{agent.weight.toFixed(1)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-600">Evidências</p>
          <p className="text-lg font-semibold text-gray-900">{agent.evidence_count}</p>
        </div>
      </div>

      {/* Última Atualização */}
      <div className="mt-4 pt-4 border-t border-gray-300">
        <p className="text-xs text-gray-600">
          Atualizado em {new Date(agent.last_updated).toLocaleTimeString('pt-BR')}
        </p>
      </div>
    </div>
  )
}
