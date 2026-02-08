/**
 * Componente Principal da Aplicação
 */

import React from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { ExecutionsList } from './pages/ExecutionsList'
import { ExecutionDetail } from './pages/ExecutionDetail'
import { Activity } from 'lucide-react'

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Activity className="w-8 h-8 text-blue-500" />
            <span className="text-2xl font-bold text-gray-900">Strands Monitor</span>
          </Link>
          <nav className="flex items-center gap-6">
            <Link to="/" className="text-gray-700 hover:text-gray-900 font-medium">
              Execuções
            </Link>
            <a
              href="https://github.com/igorrhamon/strands"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-700 hover:text-gray-900 font-medium"
            >
              GitHub
            </a>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <p className="text-center text-gray-600">
            © 2026 Strands Execution Monitor - Frontend para acompanhar execuções do sistema
          </p>
        </div>
      </footer>
    </div>
  )
}

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <Layout>
              <ExecutionsList />
            </Layout>
          }
        />
        <Route
          path="/executions/:executionId"
          element={
            <Layout>
              <ExecutionDetail />
            </Layout>
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App
