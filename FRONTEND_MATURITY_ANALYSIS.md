# 🎨 Frontend Maturity Analysis & Improvement Plan

## 📊 Análise Atual do Frontend

### **Estado Atual**

O Strands possui um **frontend básico** servido via **Jinja2 Templates** no FastAPI:

```
Frontend Stack:
├─ Framework: FastAPI + Jinja2 Templates
├─ Styling: Tailwind CSS (CDN)
├─ JavaScript: Vanilla JS (inline)
├─ Files: 1 arquivo HTML (templates/index.html)
└─ Maturity: ⭐⭐ (Muito Básico)
```

### **Estrutura Atual**

```
strands/
├─ server_fastapi.py          (Serve o frontend)
├─ templates/
│  └─ index.html              (Única página)
└─ (sem pasta frontend/client/web)
```

### **Funcionalidades Atuais**

```html
<!-- templates/index.html -->
<!DOCTYPE html>
<html>
  <head>
    <title>Strands Governance</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body>
    <!-- Componentes: -->
    ✅ Header com título
    ✅ Botão "Simulate Alert"
    ✅ Lista de decisões pendentes
    ✅ Botões Approve/Reject
    ✅ Timestamp de criação
    ❌ Sem responsividade avançada
    ❌ Sem componentes reutilizáveis
    ❌ Sem estado de aplicação
    ❌ Sem routing
    ❌ Sem testes
  </body>
</html>
```

---

## 🔍 Análise de Maturidade

### **Pontos Positivos ✅**

| Aspecto | Status | Detalhes |
|---------|--------|----------|
| **Styling** | ✅ Bom | Tailwind CSS via CDN |
| **Acessibilidade** | ✅ Básica | aria-labels presentes |
| **Responsividade** | ✅ Básica | Tailwind breakpoints (md:) |
| **Interatividade** | ✅ Funcional | Botões Approve/Reject funcionam |
| **Performance** | ✅ Rápido | Sem dependências pesadas |

### **Pontos Negativos ❌**

| Aspecto | Status | Problema |
|---------|--------|----------|
| **Arquitetura** | ❌ Monolítica | Tudo em 1 arquivo |
| **Componentização** | ❌ Inexistente | Sem componentes reutilizáveis |
| **Estado** | ❌ Nenhum | Sem gerenciamento de estado |
| **Routing** | ❌ Nenhum | Apenas 1 página |
| **Testes** | ❌ Nenhum | Sem testes unitários/E2E |
| **TypeScript** | ❌ Não | Apenas JavaScript vanilla |
| **Build Process** | ❌ Nenhum | Sem bundler (Webpack, Vite) |
| **Documentação** | ❌ Nenhuma | Sem docs de componentes |
| **CI/CD** | ❌ Nenhum | Sem pipeline de frontend |
| **Monitoramento** | ❌ Nenhum | Sem analytics/error tracking |

---

## 📈 Matriz de Maturidade

```
MATURIDADE DO FRONTEND STRANDS

Nível 1: Inicial (Atual)
├─ Arquivo HTML único
├─ JavaScript inline
├─ Sem build process
└─ Score: 2/10

Nível 2: Básico (Proposto - Curto Prazo)
├─ Componentes reutilizáveis
├─ Gerenciamento de estado
├─ Testes básicos
└─ Score: 5/10

Nível 3: Intermediário (Médio Prazo)
├─ React/Vue com TypeScript
├─ Routing completo
├─ Testes E2E
├─ CI/CD pipeline
└─ Score: 7/10

Nível 4: Avançado (Longo Prazo)
├─ Design system completo
├─ Performance otimizada
├─ Acessibilidade WCAG AA
├─ Analytics e monitoring
└─ Score: 9/10

Nível 5: Excelente (Ideal)
├─ Tudo acima +
├─ PWA capabilities
├─ Offline support
├─ Real-time updates
└─ Score: 10/10
```

---

## 🚀 Plano de Melhoria

### **Fase 1: Refatoração (1-2 semanas)**

**Objetivo**: Melhorar a estrutura atual sem mudar o stack

#### 1.1 Separar HTML em Componentes

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>{% block title %}Strands{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body>
    {% include "components/header.html" %}
    <main>
      {% block content %}{% endblock %}
    </main>
    {% include "components/footer.html" %}
  </body>
</html>

<!-- templates/index.html -->
{% extends "base.html" %}

{% block title %}Governance Dashboard{% endblock %}

{% block content %}
  {% include "components/decision-list.html" %}
{% endblock %}

<!-- templates/components/header.html -->
<header class="...">
  <h1>🎨 Strands Governance</h1>
  <button onclick="simulateAlert()">Simulate Alert</button>
</header>

<!-- templates/components/decision-card.html -->
<section class="...">
  <div class="decision-header">
    <span class="service-badge">{{ d.service }}</span>
    <h2>{{ d.summary }}</h2>
    <time>{{ d.created_at[:16] }}</time>
  </div>
  <div class="hypothesis">{{ d.primary_hypothesis }}</div>
  <div class="actions">
    <button onclick="approve('{{ d.decision_id }}')">Approve</button>
    <button onclick="reject('{{ d.decision_id }}')">Reject</button>
  </div>
</section>
```

#### 1.2 Organizar JavaScript

```javascript
// static/js/api.js
class StrandsAPI {
  static async simulateAlert() {
    const response = await fetch('/simulate/alert?active=true', {
      method: 'POST'
    });
    return response.json();
  }

  static async submitReview(decisionId, isApproved) {
    const response = await fetch(`/decisions/${decisionId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        decision_id: decisionId,
        is_approved: isApproved,
        validated_by: 'Human Operator'
      })
    });
    return response.json();
  }
}

// static/js/ui.js
class UI {
  static async handleApprove(decisionId, button) {
    button.disabled = true;
    button.innerText = 'Processing...';
    try {
      const result = await StrandsAPI.submitReview(decisionId, true);
      if (result.status === 'success') {
        button.innerText = '✅ Confirmed';
        setTimeout(() => location.reload(), 1000);
      }
    } catch (error) {
      console.error('Error:', error);
      button.disabled = false;
      button.innerText = 'Approve';
      alert('Network Error');
    }
  }
}
```

#### 1.3 Adicionar CSS Modular

```css
/* static/css/components.css */
.decision-card {
  @apply bg-white p-6 rounded-2xl shadow-sm border border-slate-200;
  @apply hover:border-blue-300 transition-all duration-300;
}

.service-badge {
  @apply inline-block px-2.5 py-1 rounded-md text-xs font-bold uppercase;
}

.service-badge.critical {
  @apply bg-red-100 text-red-700;
}

.service-badge.warning {
  @apply bg-amber-100 text-amber-700;
}

.action-button {
  @apply flex-1 font-bold py-3 rounded-xl transition focus:ring-4;
}

.action-button.approve {
  @apply bg-emerald-600 text-white hover:bg-emerald-700;
}

.action-button.reject {
  @apply bg-rose-600 text-white hover:bg-rose-700;
}
```

#### 1.4 Estrutura de Pastas

```
strands/
├─ server_fastapi.py
├─ templates/
│  ├─ base.html
│  ├─ index.html
│  ├─ decisions.html
│  └─ components/
│     ├─ header.html
│     ├─ footer.html
│     ├─ decision-card.html
│     ├─ decision-list.html
│     └─ alert-simulator.html
├─ static/
│  ├─ css/
│  │  ├─ main.css
│  │  ├─ components.css
│  │  └─ utilities.css
│  ├─ js/
│  │  ├─ api.js
│  │  ├─ ui.js
│  │  └─ main.js
│  └─ images/
│     └─ logo.svg
└─ tests/
   └─ frontend/
      ├─ test_api.js
      └─ test_ui.js
```

---

### **Fase 2: Modernização (2-4 semanas)**

**Objetivo**: Migrar para React com TypeScript

#### 2.1 Setup React + Vite

```bash
# Criar novo projeto React
npm create vite@latest strands-ui -- --template react-ts

# Estrutura
strands-ui/
├─ src/
│  ├─ components/
│  │  ├─ Header.tsx
│  │  ├─ DecisionCard.tsx
│  │  ├─ DecisionList.tsx
│  │  └─ AlertSimulator.tsx
│  ├─ pages/
│  │  ├─ Dashboard.tsx
│  │  ├─ Decisions.tsx
│  │  └─ Analytics.tsx
│  ├─ hooks/
│  │  ├─ useDecisions.ts
│  │  ├─ useAPI.ts
│  │  └─ useAuth.ts
│  ├─ types/
│  │  ├─ decision.ts
│  │  ├─ alert.ts
│  │  └─ api.ts
│  ├─ services/
│  │  ├─ api.ts
│  │  ├─ storage.ts
│  │  └─ analytics.ts
│  ├─ App.tsx
│  └─ main.tsx
├─ tests/
│  ├─ components/
│  ├─ hooks/
│  └─ services/
├─ package.json
└─ vite.config.ts
```

#### 2.2 Componentes React

```typescript
// src/types/decision.ts
export interface Decision {
  decision_id: string;
  service: string;
  severity: 'critical' | 'warning' | 'info';
  summary: string;
  primary_hypothesis: string;
  created_at: string;
}

// src/components/DecisionCard.tsx
import React, { useState } from 'react';
import { Decision } from '../types/decision';
import { api } from '../services/api';

interface Props {
  decision: Decision;
  onReview: (id: string, approved: boolean) => void;
}

export const DecisionCard: React.FC<Props> = ({ decision, onReview }) => {
  const [loading, setLoading] = useState(false);

  const handleReview = async (approved: boolean) => {
    setLoading(true);
    try {
      await api.submitReview(decision.decision_id, approved);
      onReview(decision.decision_id, approved);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
      <div className="flex justify-between items-start gap-4 mb-4">
        <div>
          <span className={`service-badge ${decision.severity}`}>
            {decision.service}
          </span>
          <h2 className="text-xl font-bold mt-2">{decision.summary}</h2>
        </div>
        <time className="text-xs text-slate-400">
          {new Date(decision.created_at).toLocaleString()}
        </time>
      </div>

      <div className="bg-slate-50 p-4 rounded-xl mb-6 border-l-4 border-blue-500">
        <p className="text-slate-700 font-medium">
          {decision.primary_hypothesis}
        </p>
      </div>

      <div className="flex gap-4">
        <button
          onClick={() => handleReview(true)}
          disabled={loading}
          className="flex-1 bg-emerald-600 text-white font-bold py-3 rounded-xl hover:bg-emerald-700 disabled:opacity-50"
        >
          {loading ? 'Processing...' : 'Approve'}
        </button>
        <button
          onClick={() => handleReview(false)}
          disabled={loading}
          className="flex-1 bg-rose-600 text-white font-bold py-3 rounded-xl hover:bg-rose-700 disabled:opacity-50"
        >
          {loading ? 'Processing...' : 'Reject'}
        </button>
      </div>
    </section>
  );
};

// src/hooks/useDecisions.ts
import { useState, useEffect } from 'react';
import { Decision } from '../types/decision';
import { api } from '../services/api';

export const useDecisions = () => {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDecisions = async () => {
      try {
        const data = await api.getDecisions();
        setDecisions(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchDecisions();
    const interval = setInterval(fetchDecisions, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  return { decisions, loading, error };
};
```

#### 2.3 Roteamento

```typescript
// src/App.tsx
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Header } from './components/Header';
import { Dashboard } from './pages/Dashboard';
import { Decisions } from './pages/Decisions';
import { Analytics } from './pages/Analytics';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Header />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/decisions" element={<Decisions />} />
        <Route path="/analytics" element={<Analytics />} />
      </Routes>
    </BrowserRouter>
  );
};
```

---

### **Fase 3: Funcionalidades Avançadas (4-8 semanas)**

#### 3.1 Design System

```typescript
// src/components/ui/Button.tsx
import React from 'react';

interface ButtonProps {
  variant: 'primary' | 'secondary' | 'danger' | 'success';
  size: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  variant,
  size,
  children,
  onClick,
  disabled
}) => {
  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white',
    secondary: 'bg-slate-200 hover:bg-slate-300 text-slate-900',
    danger: 'bg-rose-600 hover:bg-rose-700 text-white',
    success: 'bg-emerald-600 hover:bg-emerald-700 text-white'
  };

  const sizeClasses = {
    sm: 'px-3 py-1 text-sm',
    md: 'px-4 py-2 text-base',
    lg: 'px-6 py-3 text-lg'
  };

  return (
    <button
      className={`
        font-medium rounded-lg transition
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
};
```

#### 3.2 State Management (Zustand)

```typescript
// src/store/decisionsStore.ts
import { create } from 'zustand';
import { Decision } from '../types/decision';

interface DecisionsStore {
  decisions: Decision[];
  loading: boolean;
  error: string | null;
  fetchDecisions: () => Promise<void>;
  submitReview: (id: string, approved: boolean) => Promise<void>;
}

export const useDecisionsStore = create<DecisionsStore>((set) => ({
  decisions: [],
  loading: false,
  error: null,

  fetchDecisions: async () => {
    set({ loading: true });
    try {
      const response = await fetch('/api/decisions');
      const data = await response.json();
      set({ decisions: data, error: null });
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Unknown error' });
    } finally {
      set({ loading: false });
    }
  },

  submitReview: async (id: string, approved: boolean) => {
    try {
      await fetch(`/api/decisions/${id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision_id: id, is_approved: approved })
      });
      // Refetch decisions
      const store = useDecisionsStore.getState();
      await store.fetchDecisions();
    } catch (error) {
      set({ error: error instanceof Error ? error.message : 'Unknown error' });
    }
  }
}));
```

#### 3.3 Testes

```typescript
// tests/components/DecisionCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { DecisionCard } from '../../src/components/DecisionCard';
import { Decision } from '../../src/types/decision';

describe('DecisionCard', () => {
  const mockDecision: Decision = {
    decision_id: 'dec-123',
    service: 'payment-api',
    severity: 'critical',
    summary: 'Database connection timeout',
    primary_hypothesis: 'Connection pool exhausted',
    created_at: '2026-02-06T12:00:00Z'
  };

  it('renders decision details', () => {
    render(
      <DecisionCard decision={mockDecision} onReview={() => {}} />
    );
    
    expect(screen.getByText('Database connection timeout')).toBeInTheDocument();
    expect(screen.getByText('Connection pool exhausted')).toBeInTheDocument();
  });

  it('calls onReview when Approve is clicked', () => {
    const onReview = jest.fn();
    render(
      <DecisionCard decision={mockDecision} onReview={onReview} />
    );
    
    fireEvent.click(screen.getByText('Approve'));
    expect(onReview).toHaveBeenCalledWith('dec-123', true);
  });
});
```

---

## 📋 Checklist de Melhoria

### **Fase 1: Refatoração**
- [ ] Separar HTML em componentes Jinja2
- [ ] Organizar JavaScript em módulos
- [ ] Criar CSS modular
- [ ] Adicionar testes básicos
- [ ] Documentar componentes

### **Fase 2: Modernização**
- [ ] Setup React + Vite + TypeScript
- [ ] Migrar componentes
- [ ] Implementar roteamento
- [ ] Adicionar gerenciamento de estado
- [ ] Configurar CI/CD para frontend

### **Fase 3: Funcionalidades Avançadas**
- [ ] Design system completo
- [ ] Testes E2E (Playwright/Cypress)
- [ ] Analytics (Sentry/LogRocket)
- [ ] PWA capabilities
- [ ] Dark mode support

---

## 🎯 Métricas de Sucesso

| Métrica | Atual | Alvo (Fase 1) | Alvo (Fase 2) | Alvo (Fase 3) |
|---------|-------|---------------|---------------|---------------|
| **Lighthouse Score** | 60 | 75 | 85 | 95 |
| **Bundle Size** | 50KB | 45KB | 150KB | 180KB |
| **Time to Interactive** | 2.5s | 2.0s | 1.5s | 1.0s |
| **Test Coverage** | 0% | 30% | 60% | 80% |
| **Accessibility (WCAG)** | A | A | AA | AAA |
| **Componentes** | 1 | 8 | 20 | 40+ |
| **Páginas** | 1 | 1 | 3 | 5+ |

---

## 💰 Estimativa de Esforço

| Fase | Duração | Esforço | Prioridade |
|------|---------|---------|-----------|
| **Fase 1** | 1-2 semanas | 40 horas | 🔴 ALTA |
| **Fase 2** | 2-4 semanas | 80 horas | 🟡 MÉDIA |
| **Fase 3** | 4-8 semanas | 160 horas | 🟢 BAIXA |

---

## 🚀 Recomendação

**Comece pela Fase 1 (Refatoração)** porque:

✅ Melhora imediata sem mudar stack  
✅ Baixo risco de breaking changes  
✅ Prepara base para Fase 2  
✅ Rápido ROI (1-2 semanas)  

Depois migre para **Fase 2 (React)** quando:
- Fase 1 estiver completa
- Requisitos de funcionalidades crescerem
- Necessidade de melhor performance
- Mais desenvolvedores no time

---

## 📚 Recursos Recomendados

- **React**: https://react.dev
- **TypeScript**: https://www.typescriptlang.org
- **Vite**: https://vitejs.dev
- **Tailwind CSS**: https://tailwindcss.com
- **Testing Library**: https://testing-library.com
- **Zustand**: https://github.com/pmndrs/zustand
- **React Router**: https://reactrouter.com

---

**Última atualização**: 2026-02-06  
**Status**: Recomendação para Implementação
