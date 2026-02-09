/**
 * Página de Listagem de Execuções
 * Exibe todas as execuções do sistema com filtros e paginação
 */

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listExecutions } from '../api/client'
import type { ExecutionListItem } from '../types'
import { formatDate, formatDuration, getStatusColor, getConfidenceColor } from '../utils/format'
import { Search, ChevronRight, AlertCircle, CheckCircle, Clock, Zap } from 'lucide-react'

export function ExecutionsList() {
  const navigate = useNavigate()
  const [executions, setExecutions] = useState<ExecutionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')

  const LIMIT = 20

  useEffect(() => {
    loadExecutions()
  }, [page, statusFilter])

  async function loadExecutions() {
    try {
      setLoading(true)
      setError(null)
      const data = await listExecutions(page, LIMIT, statusFilter || undefined)
      setExecutions(data.items)
      setTotal(data.total)
    } catch (err) {
      setError('Erro ao carregar execuções')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  function handleExecutionClick(executionId: string) {
    navigate(`/executions/${executionId}`)
  }

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

  const totalPages = Math.ceil(total / LIMIT)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Execuções</h1>
          <p className="text-gray-600 mt-1">Acompanhe todas as execuções do sistema Strands</p>
        </div>
      </div>

      {/* Filtros */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Busca */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Buscar por ID ou fonte..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Filtro de Status */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos os Status</option>
            <option value="PENDING">Pendente</option>
            <option value="RUNNING">Executando</option>
            <option value="COMPLETED">Completo</option>
            <option value="FAILED">Falha</option>
          </select>
        </div>
      </div>

      {/* Erro */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
          {error}
        </div>
      )}

      {/* Listagem */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Carregando execuções...</div>
        ) : executions.length === 0 ? (
          <div className="p-8 text-center text-gray-500">Nenhuma execução encontrada</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">ID</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Fonte</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Tipo</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Status</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Confiança</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Agentes</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Duração</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700">Data</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-gray-700"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {executions.map((execution) => (
                    <tr
                      key={execution.execution_id}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => handleExecutionClick(execution.execution_id)}
                    >
                      <td className="px-6 py-4 text-sm font-mono text-gray-900">
                        {execution.execution_id.substring(0, 12)}...
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-700">{execution.source_id}</td>
                      <td className="px-6 py-4 text-sm text-gray-600">{execution.event_type}</td>
                      <td className="px-6 py-4 text-sm">
                        <div className="flex items-center gap-2">
                          {getStatusIcon(execution.status)}
                          <span className={`font-medium ${getStatusColor(execution.status)}`}>
                            {execution.status}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm">
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-gray-200 rounded-full h-2">
                            <div
                              className={`h-2 rounded-full ${getConfidenceColor(execution.confidence_score)}`}
                              style={{ width: `${execution.confidence_score * 100}%` }}
                            ></div>
                          </div>
                          <span className="font-medium text-gray-900">
                            {(execution.confidence_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-700">
                        <span className="bg-blue-50 text-blue-700 px-2 py-1 rounded text-xs font-medium">
                          {execution.agent_count}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {formatDuration(execution.duration_ms)}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">
                        {formatDate(execution.created_at)}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <ChevronRight className="w-5 h-5 text-gray-400" />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Paginação */}
            <div className="bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-between items-center">
              <div className="text-sm text-gray-600">
                Mostrando {(page - 1) * LIMIT + 1} a {Math.min(page * LIMIT, total)} de {total}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                >
                  Anterior
                </button>
                <div className="flex items-center gap-2">
                  {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
                    const pageNum = i + 1
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setPage(pageNum)}
                        className={`px-3 py-2 rounded-lg ${
                          page === pageNum
                            ? 'bg-blue-500 text-white'
                            : 'border border-gray-300 hover:bg-gray-100'
                        }`}
                      >
                        {pageNum}
                      </button>
                    )
                  })}
                </div>
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                >
                  Próximo
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
