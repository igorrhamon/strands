/**
 * Utilitários de Formatação
 */

export function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleString('pt-BR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${ms}ms`
  }
  if (ms < 60000) {
    return `${(ms / 1000).toFixed(2)}s`
  }
  const minutes = Math.floor(ms / 60000)
  const seconds = ((ms % 60000) / 1000).toFixed(0)
  return `${minutes}m ${seconds}s`
}

export function getStatusColor(status: string): string {
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

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) {
    return 'bg-green-500 text-green-700'
  }
  if (confidence >= 0.6) {
    return 'bg-blue-500 text-blue-700'
  }
  if (confidence >= 0.4) {
    return 'bg-yellow-500 text-yellow-700'
  }
  return 'bg-red-500 text-red-700'
}

export function getConfidenceLevel(confidence: number): string {
  if (confidence >= 0.9) {
    return 'MUITO ALTA'
  }
  if (confidence >= 0.7) {
    return 'ALTA'
  }
  if (confidence >= 0.5) {
    return 'MÉDIA'
  }
  if (confidence >= 0.3) {
    return 'BAIXA'
  }
  return 'MUITO BAIXA'
}
