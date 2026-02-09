/**
 * Componente ConfidenceChart
 * Visualiza a confiança de cada agente em um gráfico de barras
 */

import React from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import type { Agent } from '../types'

interface ConfidenceChartProps {
  agents: Agent[]
}

export function ConfidenceChart({ agents }: ConfidenceChartProps) {
  const data = agents.map((agent) => ({
    name: agent.name,
    confidence: Math.round(agent.confidence * 100),
    weight: agent.weight,
  }))

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 60 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="name"
          angle={-45}
          textAnchor="end"
          height={100}
          interval={0}
          tick={{ fontSize: 12 }}
        />
        <YAxis label={{ value: 'Confiança (%)', angle: -90, position: 'insideLeft' }} />
        <Tooltip
          formatter={(value) => `${value}%`}
          contentStyle={{ backgroundColor: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: '8px' }}
        />
        <Legend />
        <Bar dataKey="confidence" fill="#3b82f6" name="Confiança (%)" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
