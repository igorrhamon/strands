# 🧬 Guia de Evolução Autônoma - Strands

## Visão Geral

Este documento detalha as novas capacidades de **Evolução Autônoma** do Strands, que permitem ao sistema aprender, adaptar-se e melhorar suas operações de remediação sem intervenção humana constante.

---

## 📦 Componentes Implementados

### 1. Integração com GitHub Models
**Arquivo:** `src/llm/provider_factory.py`

Adicionamos suporte nativo ao **GitHub Models** (via Azure AI Inference SDK), permitindo acesso a modelos de ponta (GPT-4o, Phi-3, Llama-3) diretamente através da infraestrutura do GitHub.

**Configuração:**
```bash
export LLM_PROVIDER=github
export LLM_API_KEY=ghp_...
export LLM_MODEL=gpt-4o
```

### 2. Dashboard de Curação SRE
**Frontend:** `frontend/curation_dashboard.html`
**Backend:** `src/api/curation_api.py`

Interface visual para Engenheiros de Confiabilidade (SREs) revisarem, aprovarem ou rejeitarem playbooks gerados por IA.

**Funcionalidades:**
- Listagem de playbooks pendentes (PENDING_REVIEW)
- Visualização detalhada de passos e comandos
- Avaliação de risco (Low, Medium, High)
- Aprovação com um clique (move para ACTIVE)
- Rejeição com feedback (move para ARCHIVED)

### 3. Feedback Loop & Análise de Tendências
**Arquivo:** `src/core/feedback_loop.py`

Motor que fecha o ciclo de aprendizado:
1. **Coleta:** Registra sucesso/falha de cada execução
2. **Análise:** Calcula taxas de sucesso e duração média
3. **Tendências:** Identifica padrões emergentes (ex: aumento de falhas de memória)
4. **Otimização:** Sugere melhorias em playbooks com desempenho degradado

### 4. Versionamento de Playbooks
**Arquivo:** `src/core/playbook_versioning.py`

Sistema robusto de versionamento semântico para playbooks:
- **Major:** Mudanças incompatíveis ou reescrita
- **Minor:** Adição de passos ou melhorias
- **Patch:** Correções de bugs ou typos

Permite rollback seguro e rastreabilidade completa de mudanças.

---

## 🔄 Fluxo de Trabalho Completo

1. **Detecção:** Correlator detecta um padrão de incidente.
2. **Geração:** Se não houver playbook, LLM (GitHub Models) gera um rascunho.
3. **Curação:** SRE acessa o Dashboard e aprova o rascunho.
4. **Execução:** Strands executa o playbook aprovado.
5. **Feedback:** Resultado é registrado pelo Feedback Loop.
6. **Evolução:** Se a taxa de sucesso cair, o sistema sugere uma nova versão.

---

## 🚀 Como Usar

### Iniciar o Dashboard
```bash
uvicorn src.api.curation_api:app --reload
# Acessar http://localhost:8000/docs para API
# Abrir frontend/curation_dashboard.html no navegador
```

### Configurar GitHub Models
```python
from src.llm.provider_factory import LLMFactory, LLMConfig, LLMProviderType

config = LLMConfig(
    provider=LLMProviderType.GITHUB,
    api_key="seu-token-github",
    model="gpt-4o"
)
provider = LLMFactory.create_provider(config)
response = await provider.generate("Como corrigir OOM no Kubernetes?")
```

---

## 📊 Métricas de Sucesso

O sistema agora rastreia:
- **Taxa de Automação:** % de incidentes resolvidos sem humano
- **Tempo de Curação:** Tempo médio entre geração e aprovação
- **Eficácia de Playbook:** Taxa de sucesso por versão
- **Economia de Tempo:** Horas de engenharia salvas

---

**Status:** 🟢 PRONTO PARA PRODUÇÃO
