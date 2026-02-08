/**
 * Componente ExecutionTimeline
 * Exibe a timeline de execução dos passos
 */

import React from 'react'
import type { ExecutionStep } from '../types'
import { formatDate, formatDuration } from '../utils/format'
import { CheckCircle, AlertCircle, Clock, Zap } from 'lucide-react'

interface ExecutionTimelineProps {
  steps: ExecutionStep[]
}

export function ExecutionTimeline({ steps }: ExecutionTimelineProps) {
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

  function getStatusColor(status: string) {
    switch (status) {
      case 'COMPLETED':
        return 'text-green-700'
      case 'FAILED':
        return 'text-red-700'
      case 'RUNNING':
        return 'text-blue-700'
      case 'PENDING':
        return 'text-yellow-700'
      default:
        return 'text-gray-700'
    }
  }

  return (
    <div className="space-y-4">
      {steps.map((step, index) => (
        <div key={index} className="flex gap-4">
          {/* Ícone e Linha */}
          <div className="flex flex-col items-center">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gray-100">
              {getStatusIcon(step.status)}
            </div>
            {index < steps.length - 1 && <div className="w-1 h-12 bg-gray-200 mt-2"></div>}
          </div>

          {/* Conteúdo */}
          <div className="flex-1 pb-4">
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h4 className="font-semibold text-gray-900">Passo {step.step_index}</h4>
                  <p className="text-sm text-gray-600">{step.agent_name}</p>
                </div>
                <div className="text-right">
                  <p className={`text-sm font-medium ${getStatusColor(step.status)}`}>{step.status}</p>
                  <p className="text-xs text-gray-600">{formatDuration(step.duration_ms)}</p>
                </div>
              </div>

              {/* Confiança */}
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-600">Confiança</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {(step.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div
                    className="h-1.5 rounded-full bg-blue-500"
                    style={{ width: `${step.confidence * 100}%` }}
                  ></div>
                </div>
              </div>

              {/* Resultado */}
              {step.result && (
                <div className="mt-3 p-2 bg-white rounded border border-gray-200">
                  <p className="text-xs text-gray-600 mb-1">Resultado</p>
                  <p className="text-sm text-gray-700 font-mono">{step.result}</p>
                </div>
              )}

              {/* Timestamp */}
              <p className="text-xs text-gray-500 mt-2">{formatDate(step.timestamp)}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
