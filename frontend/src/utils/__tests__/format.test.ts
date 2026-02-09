import { describe, it, expect } from 'vitest'
import {
  formatDate,
  formatDuration,
  getStatusColor,
  getConfidenceColor,
  getConfidenceLevel,
} from '../format'

describe('Utilitários de Formatação', () => {
  describe('formatDate', () => {
    it('deve formatar data corretamente', () => {
      const date = '2026-02-08T10:30:00Z'
      const result = formatDate(date)
      expect(result).toContain('08')
      expect(result).toContain('02')
      expect(result).toContain('2026')
    })

    it('deve incluir hora no formato', () => {
      const date = '2026-02-08T14:30:45Z'
      const result = formatDate(date)
      expect(result).toMatch(/\d{2}:\d{2}:\d{2}/)
    })
  })

  describe('formatDuration', () => {
    it('deve formatar milissegundos corretamente', () => {
      expect(formatDuration(500)).toBe('500ms')
      expect(formatDuration(999)).toBe('999ms')
    })

    it('deve formatar segundos corretamente', () => {
      expect(formatDuration(1000)).toBe('1.00s')
      expect(formatDuration(5500)).toBe('5.50s')
    })

    it('deve formatar minutos e segundos corretamente', () => {
      expect(formatDuration(60000)).toBe('1m 0s')
      expect(formatDuration(90000)).toBe('1m 30s')
      expect(formatDuration(120000)).toBe('2m 0s')
    })
  })

  describe('getStatusColor', () => {
    it('deve retornar cor verde para COMPLETED', () => {
      expect(getStatusColor('COMPLETED')).toBe('text-green-700')
    })

    it('deve retornar cor vermelha para FAILED', () => {
      expect(getStatusColor('FAILED')).toBe('text-red-700')
    })

    it('deve retornar cor azul para RUNNING', () => {
      expect(getStatusColor('RUNNING')).toBe('text-blue-700')
    })

    it('deve retornar cor amarela para PENDING', () => {
      expect(getStatusColor('PENDING')).toBe('text-yellow-700')
    })

    it('deve retornar cor padrão para status desconhecido', () => {
      expect(getStatusColor('UNKNOWN')).toBe('text-gray-700')
    })
  })

  describe('getConfidenceColor', () => {
    it('deve retornar verde para confiança muito alta (>= 0.8)', () => {
      expect(getConfidenceColor(0.8)).toContain('green')
      expect(getConfidenceColor(0.95)).toContain('green')
    })

    it('deve retornar azul para confiança alta (0.6-0.8)', () => {
      expect(getConfidenceColor(0.6)).toContain('blue')
      expect(getConfidenceColor(0.75)).toContain('blue')
    })

    it('deve retornar amarelo para confiança média (0.4-0.6)', () => {
      expect(getConfidenceColor(0.4)).toContain('yellow')
      expect(getConfidenceColor(0.5)).toContain('yellow')
    })

    it('deve retornar vermelho para confiança baixa (< 0.4)', () => {
      expect(getConfidenceColor(0.3)).toContain('red')
      expect(getConfidenceColor(0.1)).toContain('red')
    })
  })

  describe('getConfidenceLevel', () => {
    it('deve retornar MUITO ALTA para >= 0.9', () => {
      expect(getConfidenceLevel(0.9)).toBe('MUITO ALTA')
      expect(getConfidenceLevel(1.0)).toBe('MUITO ALTA')
    })

    it('deve retornar ALTA para 0.7-0.9', () => {
      expect(getConfidenceLevel(0.7)).toBe('ALTA')
      expect(getConfidenceLevel(0.85)).toBe('ALTA')
    })

    it('deve retornar MÉDIA para 0.5-0.7', () => {
      expect(getConfidenceLevel(0.5)).toBe('MÉDIA')
      expect(getConfidenceLevel(0.65)).toBe('MÉDIA')
    })

    it('deve retornar BAIXA para 0.3-0.5', () => {
      expect(getConfidenceLevel(0.3)).toBe('BAIXA')
      expect(getConfidenceLevel(0.45)).toBe('BAIXA')
    })

    it('deve retornar MUITO BAIXA para < 0.3', () => {
      expect(getConfidenceLevel(0.2)).toBe('MUITO BAIXA')
      expect(getConfidenceLevel(0.0)).toBe('MUITO BAIXA')
    })
  })
})
