import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExecutionTimeline } from '../ExecutionTimeline'
import type { ExecutionStep } from '../../types'

describe('ExecutionTimeline', () => {
  const mockSteps: ExecutionStep[] = [
    {
      step_index: 1,
      agent_name: 'Threat Intel Agent',
      status: 'COMPLETED',
      duration_ms: 1500,
      confidence: 0.85,
      result: 'Threat detected: Suspicious login attempt',
      timestamp: '2026-02-08T10:30:00Z',
    },
    {
      step_index: 2,
      agent_name: 'Log Analyzer',
      status: 'COMPLETED',
      duration_ms: 2000,
      confidence: 0.75,
      result: 'Log analysis complete',
      timestamp: '2026-02-08T10:30:02Z',
    },
  ]

  it('deve renderizar todos os passos', () => {
    render(<ExecutionTimeline steps={mockSteps} />)
    
    expect(screen.getByText('Passo 1')).toBeInTheDocument()
    expect(screen.getByText('Passo 2')).toBeInTheDocument()
  })

  it('deve exibir nomes dos agentes', () => {
    render(<ExecutionTimeline steps={mockSteps} />)
    
    expect(screen.getByText('Threat Intel Agent')).toBeInTheDocument()
    expect(screen.getByText('Log Analyzer')).toBeInTheDocument()
  })

  it('deve exibir status de cada passo', () => {
    render(<ExecutionTimeline steps={mockSteps} />)
    
    const completedElements = screen.getAllByText('COMPLETED')
    expect(completedElements.length).toBeGreaterThanOrEqual(2)
  })

  it('deve exibir confiança de cada passo', () => {
    render(<ExecutionTimeline steps={mockSteps} />)
    
    expect(screen.getByText('85%')).toBeInTheDocument()
    expect(screen.getByText('75%')).toBeInTheDocument()
  })

  it('deve exibir duração de cada passo', () => {
    render(<ExecutionTimeline steps={mockSteps} />)
    
    expect(screen.getByText('1.50s')).toBeInTheDocument()
    expect(screen.getByText('2.00s')).toBeInTheDocument()
  })

  it('deve exibir resultados dos passos', () => {
    render(<ExecutionTimeline steps={mockSteps} />)
    
    expect(screen.getByText(/Threat detected/)).toBeInTheDocument()
    expect(screen.getByText(/Log analysis complete/)).toBeInTheDocument()
  })

  it('deve renderizar com lista vazia', () => {
    const { container } = render(<ExecutionTimeline steps={[]} />)
    expect(container.firstChild?.childNodes.length).toBe(0)
  })

  it('deve exibir ícones de status diferentes', () => {
    const failedStep: ExecutionStep = {
      ...mockSteps[0],
      status: 'FAILED',
    }

    render(<ExecutionTimeline steps={[failedStep]} />)
    expect(screen.getByText('FAILED')).toBeInTheDocument()
  })

  it('deve exibir linhas conectando passos', () => {
    const { container } = render(<ExecutionTimeline steps={mockSteps} />)
    
    const lines = container.querySelectorAll('[class*="bg-gray-200"]')
    expect(lines.length).toBeGreaterThan(0)
  })
})
