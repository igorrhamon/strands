# 🚀 Como Acessar o Frontend Refatorado

## 📋 Pré-requisitos

- Python 3.10+
- FastAPI instalado
- Dependências do Strands instaladas

## 🏃 Passo 1: Clonar a Branch

```bash
# Se ainda não tem o repositório
git clone https://github.com/igorrhamon/strands.git
cd strands

# Ou, se já tem, fazer checkout da branch
git checkout feat/frontend-refactor
```

## 🔧 Passo 2: Instalar Dependências

```bash
# Criar ambiente virtual (opcional mas recomendado)
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Se requirements.txt não tem tudo:
pip install fastapi uvicorn jinja2 prometheus-client
```

## 📁 Passo 3: Verificar Estrutura

```bash
# Verificar que os arquivos estão no lugar certo
ls -la templates/
ls -la static/

# Deve mostrar:
# templates/
#   ├── base.html
#   ├── index.html
#   └── components/
#       ├── header.html
#       ├── footer.html
#       ├── decision-card.html
#       └── decision-list.html
#
# static/
#   ├── css/
#   │   └── main.css
#   └── js/
#       ├── api.js
#       └── ui.js
```

## 🚀 Passo 4: Iniciar o Servidor

### Opção A: Usando server_fastapi.py

```bash
# Iniciar o servidor
python server_fastapi.py

# Ou com uvicorn diretamente
uvicorn server_fastapi:app --reload --host 0.0.0.0 --port 8000
```

### Opção B: Usando main.py (se disponível)

```bash
python main.py
```

### Opção C: Usando Docker (se preferir)

```bash
# Build da imagem
docker build -t strands:latest .

# Executar container
docker run -p 8000:8000 strands:latest
```

## 🌐 Passo 5: Acessar no Navegador

Abra seu navegador e visite:

```
http://localhost:8000
```

Você deve ver:
- ✅ Header com logo "🎨 Strands Governance"
- ✅ Botão "Simulate Alert"
- ✅ Lista de decisões (vazia inicialmente)
- ✅ Footer com links

## 🧪 Passo 6: Testar Funcionalidades

### 1. Simular um Alerta

```
1. Clique no botão "Simulate Alert"
2. Aguarde 1-2 segundos
3. A página deve recarregar com uma nova decisão
```

### 2. Aprovar/Rejeitar Decisão

```
1. Clique em "Approve" ou "Reject"
2. O botão deve mostrar "Processing..."
3. Após sucesso, a página recarrega
```

### 3. Atalho de Teclado

```
1. Pressione Alt+S
2. Deve simular um alerta (mesmo que clicar no botão)
```

### 4. Responsividade

```
1. Abra DevTools (F12)
2. Ative modo mobile (Ctrl+Shift+M)
3. Redimensione o navegador
4. A interface deve se adaptar
```

### 5. Dark Mode

```
1. Abra DevTools (F12)
2. Vá para Settings > Rendering
3. Ative "Emulate CSS media feature prefers-color-scheme"
4. Selecione "dark"
5. A interface deve mudar para dark mode
```

## 🔍 Troubleshooting

### Erro: "Static files not found"

```bash
# Verificar se pasta static existe
ls -la static/

# Se não existir, criar:
mkdir -p static/css
mkdir -p static/js

# Copiar arquivos (se estiverem em outro lugar):
cp -r static/* ./static/
```

### Erro: "Templates not found"

```bash
# Verificar se pasta templates existe
ls -la templates/

# Se não existir, criar:
mkdir -p templates/components
```

### Erro: "Module not found"

```bash
# Reinstalar dependências
pip install --upgrade -r requirements.txt

# Ou instalar manualmente:
pip install fastapi uvicorn jinja2 prometheus-client
```

### Botões não funcionam

```
1. Abra DevTools (F12)
2. Vá para Console
3. Verifique se há erros de JavaScript
4. Verifique se os arquivos CSS/JS estão sendo carregados:
   - Vá para Network tab
   - Recarregue a página
   - Procure por static/css/main.css e static/js/*.js
```

### Estilos não aparecem

```
1. Verificar se Tailwind CSS CDN está carregando:
   - Abra DevTools (F12)
   - Vá para Network tab
   - Procure por "cdn.tailwindcss.com"
   - Se não estiver, a internet pode estar desconectada

2. Verificar se main.css está carregando:
   - Procure por "static/css/main.css" na Network tab
   - Se retornar 404, verificar se arquivo existe
```

## 📊 Endpoints Disponíveis

```
GET  /                      → Dashboard (página principal)
POST /simulate/alert        → Simular novo alerta
GET  /decisions             → Listar decisões
POST /decisions/{id}/review → Submeter revisão
GET  /metrics               → Métricas Prometheus
```

## 🎯 Verificação Completa

Use este checklist para verificar se tudo está funcionando:

- [ ] Página carrega sem erros (F12 → Console)
- [ ] Header aparece com logo e botão
- [ ] Footer aparece no final da página
- [ ] Estilos CSS estão aplicados
- [ ] Botão "Simulate Alert" funciona
- [ ] Novo alerta aparece após simular
- [ ] Botões "Approve" e "Reject" funcionam
- [ ] Atalho Alt+S funciona
- [ ] Página é responsiva (mobile)
- [ ] Dark mode funciona
- [ ] Não há erros no console

## 📚 Arquivos Importantes

| Arquivo | Descrição |
|---------|-----------|
| `server_fastapi.py` | Servidor FastAPI |
| `templates/base.html` | Template base |
| `templates/index.html` | Página principal |
| `templates/components/` | Componentes reutilizáveis |
| `static/css/main.css` | Estilos CSS |
| `static/js/api.js` | Cliente de API |
| `static/js/ui.js` | Controlador de UI |

## 🔗 URLs Úteis

| URL | Descrição |
|-----|-----------|
| `http://localhost:8000` | Dashboard principal |
| `http://localhost:8000/docs` | Documentação Swagger |
| `http://localhost:8000/redoc` | Documentação ReDoc |
| `http://localhost:8000/metrics` | Métricas Prometheus |

## 🐛 Debug Mode

Para debug mais detalhado:

```python
# Adicionar ao server_fastapi.py
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Ou via linha de comando:
# PYTHONPATH=. python -m uvicorn server_fastapi:app --reload --log-level debug
```

## 📞 Suporte

Se encontrar problemas:

1. Verifique o console do navegador (F12)
2. Verifique os logs do servidor
3. Leia `FRONTEND_REFACTOR_README.md` para mais detalhes
4. Verifique `FRONTEND_MATURITY_ANALYSIS.md` para arquitetura

## 🎓 Próximos Passos

Após testar o frontend refatorado:

1. **Revisar o código** nos arquivos criados
2. **Testar em diferentes navegadores** (Chrome, Firefox, Safari)
3. **Testar em dispositivos móveis** (smartphone, tablet)
4. **Fornecer feedback** sobre UX/UI
5. **Preparar para Phase 2** (React migration)

---

**Status**: Pronto para teste  
**Última atualização**: 2026-02-06  
**Branch**: feat/frontend-refactor
