import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AgentCard } from '../AgentCard'
import type { Agent } from '../../types'

describe('AgentCard', () => {
  const mockAgent: Agent = {
    id: 'agent-1',
    name: 'Threat Intel Agent',
    type: 'THREAT_INTEL',
    confidence: 0.85,
    weight: 2.0,
    status: 'COMPLETED',
    evidence_count: 5,
    last_updated: '2026-02-08T10:30:00Z',
  }

  it('deve renderizar informações do agente', () => {
    render(<AgentCard agent={mockAgent} />)
    
    expect(screen.getByText('Threat Intel Agent')).toBeInTheDocument()
    expect(screen.getByText('THREAT_INTEL')).toBeInTheDocument()
  })

  it('deve exibir confiança corretamente', () => {
    render(<AgentCard agent={mockAgent} />)
    
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('deve exibir peso e contagem de evidências', () => {
    render(<AgentCard agent={mockAgent} />)
    
    expect(screen.getByText('2.0')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('deve exibir status do agente', () => {
    render(<AgentCard agent={mockAgent} />)
    
    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
  })

  it('deve renderizar com cores corretas para diferentes tipos', () => {
    const logAnalyzerAgent: Agent = {
      ...mockAgent,
      type: 'LOG_ANALYZER',
    }

    const { container } = render(<AgentCard agent={logAnalyzerAgent} />)
    expect(container.firstChild).toHaveClass('bg-blue-50')
  })

  it('deve exibir barra de progresso de confiança', () => {
    const { container } = render(<AgentCard agent={mockAgent} />)
    const progressBar = container.querySelector('[style*="width"]')
    expect(progressBar).toBeInTheDocument()
  })

  it('deve lidar com diferentes níveis de confiança', () => {
    const lowConfidenceAgent: Agent = {
      ...mockAgent,
      confidence: 0.3,
    }

    render(<AgentCard agent={lowConfidenceAgent} />)
    expect(screen.getByText('30%')).toBeInTheDocument()
  })

  it('deve exibir timestamp de atualização', () => {
    render(<AgentCard agent={mockAgent} />)
    
    const timeElement = screen.getByText(/Atualizado em/)
    expect(timeElement).toBeInTheDocument()
  })
})
