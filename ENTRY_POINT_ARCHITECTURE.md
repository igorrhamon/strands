# 🚀 Strands - Entry Point Architecture

## 📍 Ponto de Entrada Principal

O ponto de entrada da aplicação Strands é o arquivo **`server_fastapi.py`**, que inicializa a aplicação FastAPI e orquestra todos os componentes.

## 🎯 Fluxo de Inicialização

```mermaid
graph TD
    A["🖥️ Host Machine<br/>localhost:8000"] -->|HTTP Request| B["🐳 Docker Container<br/>strands-dashboard"]
    
    B -->|Startup| C["📄 server_fastapi.py<br/>Entry Point"]
    
    C -->|Initialize| D["🔧 FastAPI App<br/>Setup Routes"]
    C -->|Connect| E["🗄️ Neo4j<br/>Graph DB"]
    C -->|Connect| F["🔍 Qdrant<br/>Vector Store"]
    C -->|Connect| G["📊 Prometheus<br/>Metrics"]
    C -->|Connect| H["🤖 Ollama<br/>LLM"]
    
    D -->|Route: GET /| I["📱 Frontend<br/>index.html"]
    D -->|Route: POST /api/alerts| J["🚨 Alert Collector"]
    D -->|Route: POST /api/analyze| K["🧠 Analysis Engine"]
    D -->|Route: GET /metrics| L["📈 Metrics Endpoint"]
    D -->|Route: GET /health| M["❤️ Health Check"]
    
    I -->|Load| N["🎨 Templates<br/>Jinja2"]
    I -->|Load| O["🎯 Static Files<br/>CSS/JS"]
    
    J -->|Process| P["🔄 Alert Pipeline"]
    K -->|Process| Q["⚙️ Decision Engine"]
    
    P -->|Store| E
    P -->|Embed| F
    Q -->|Query| E
    Q -->|Search| F
    Q -->|Analyze| H
    
    L -->|Expose| G
    
    style A fill:#e1f5ff
    style B fill:#fff3e0
    style C fill:#f3e5f5
    style D fill:#e8f5e9
    style E fill:#fce4ec
    style F fill:#f1f8e9
    style G fill:#ede7f6
    style H fill:#e0f2f1
    style I fill:#fff9c4
    style J fill:#ffccbc
    style K fill:#c8e6c9
    style L fill:#b3e5fc
    style M fill:#ffccbc
    style N fill:#fff9c4
    style O fill:#fff9c4
    style P fill:#ffccbc
    style Q fill:#c8e6c9
```

## 📋 Detalhes do Entry Point

### 1. **server_fastapi.py** - Arquivo Principal

```python
# Localização: /home/ubuntu/strands/server_fastapi.py

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Inicializar FastAPI
app = FastAPI(title="Strands Governance")

# Configurar templates Jinja2
templates = Jinja2Templates(directory="templates")

# Servir arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Inicializar conexões
@app.on_event("startup")
async def startup():
    # Conectar Neo4j
    # Conectar Qdrant
    # Conectar Prometheus
    # Conectar Ollama
    pass

# Rotas principais
@app.get("/")
async def home():
    return templates.TemplateResponse("index.html", {})

@app.post("/api/alerts")
async def receive_alert(alert: Alert):
    # Processar alerta
    pass

@app.post("/api/analyze")
async def analyze():
    # Executar análise
    pass

@app.get("/metrics")
async def metrics():
    # Expor métricas Prometheus
    pass

@app.get("/health")
async def health():
    # Health check
    pass
```

## 🔄 Fluxo de Requisição HTTP

```mermaid
sequenceDiagram
    participant Client as 🖥️ Client<br/>Browser
    participant FastAPI as ⚡ FastAPI<br/>server_fastapi.py
    participant Templates as 📄 Templates<br/>Jinja2
    participant Static as 🎨 Static Files<br/>CSS/JS
    participant API as 🔌 API Routes<br/>Handlers
    participant Neo4j as 🗄️ Neo4j<br/>Graph DB
    participant Qdrant as 🔍 Qdrant<br/>Vector Store
    participant Ollama as 🤖 Ollama<br/>LLM
    
    Client->>FastAPI: GET /
    FastAPI->>Templates: Render index.html
    Templates->>Client: HTML Page
    
    Client->>Static: Load CSS/JS
    Static->>Client: static/css/main.css
    Static->>Client: static/js/api.js
    
    Client->>API: POST /api/alerts
    API->>Neo4j: Store Alert
    API->>Qdrant: Embed Alert
    API->>Ollama: Analyze
    API->>Client: Response
    
    Client->>API: GET /metrics
    API->>Client: Prometheus Metrics
```

## 🎯 Estrutura de Rotas

```mermaid
graph LR
    A["FastAPI<br/>server_fastapi.py"]
    
    A -->|GET /| B["🏠 Home<br/>index.html"]
    A -->|GET /health| C["❤️ Health Check"]
    A -->|GET /metrics| D["📊 Prometheus Metrics"]
    A -->|POST /api/alerts| E["🚨 Alert Collector"]
    A -->|POST /api/analyze| F["🧠 Analysis Engine"]
    A -->|GET /api/decisions| G["📋 Get Decisions"]
    A -->|POST /api/decisions/:id/approve| H["✅ Approve Decision"]
    A -->|POST /api/decisions/:id/reject| I["❌ Reject Decision"]
    
    E -->|Normaliza| J["Alert Pipeline"]
    F -->|Analisa| K["Decision Engine"]
    
    style A fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    style B fill:#fff9c4
    style C fill:#ffccbc
    style D fill:#b3e5fc
    style E fill:#ffccbc
    style F fill:#c8e6c9
    style G fill:#fff9c4
    style H fill:#c8e6c9
    style I fill:#ffccbc
    style J fill:#ffccbc
    style K fill:#c8e6c9
```

## 🚀 Processo de Startup

```mermaid
graph TD
    A["🐳 Docker Container<br/>Inicia"] -->|Executa| B["python server_fastapi.py"]
    
    B -->|Carrega| C["Variáveis de Ambiente"]
    C -->|NEO4J_URI| D["🗄️ Conecta Neo4j"]
    C -->|QDRANT_URL| E["🔍 Conecta Qdrant"]
    C -->|PROMETHEUS_URL| F["📊 Conecta Prometheus"]
    C -->|OLLAMA_URL| G["🤖 Conecta Ollama"]
    
    D -->|Status| H{Conexões<br/>OK?}
    E -->|Status| H
    F -->|Status| H
    G -->|Status| H
    
    H -->|✅ Sim| I["🟢 FastAPI Startup"]
    H -->|❌ Não| J["🔴 Erro de Inicialização"]
    
    I -->|Registra| K["Rotas HTTP"]
    I -->|Monta| L["Arquivos Estáticos"]
    I -->|Inicia| M["Uvicorn Server"]
    
    M -->|Escuta| N["0.0.0.0:8000"]
    
    N -->|Pronto para| O["🚀 Requisições HTTP"]
    
    style A fill:#e3f2fd
    style B fill:#f3e5f5
    style C fill:#fff3e0
    style D fill:#fce4ec
    style E fill:#f1f8e9
    style F fill:#ede7f6
    style G fill:#e0f2f1
    style H fill:#fff9c4
    style I fill:#c8e6c9
    style J fill:#ffccbc
    style K fill:#c8e6c9
    style L fill:#fff9c4
    style M fill:#b3e5fc
    style N fill:#c8e6c9
    style O fill:#a5d6a7
```

## 📊 Arquitetura em Camadas

```mermaid
graph TB
    subgraph Presentation["🎨 Presentation Layer"]
        A["Frontend<br/>HTML/CSS/JS<br/>templates/"]
        B["Static Files<br/>CSS/JS<br/>static/"]
    end
    
    subgraph API["🔌 API Layer"]
        C["FastAPI<br/>server_fastapi.py<br/>Routes & Handlers"]
    end
    
    subgraph Business["⚙️ Business Logic Layer"]
        D["Alert Pipeline<br/>src/pipeline/"]
        E["Decision Engine<br/>src/agents/"]
        F["Orchestrator<br/>src/agents/"]
    end
    
    subgraph Data["💾 Data Layer"]
        G["Neo4j<br/>Graph Database<br/>Relationships"]
        H["Qdrant<br/>Vector Store<br/>Embeddings"]
        I["Prometheus<br/>Time Series<br/>Metrics"]
    end
    
    subgraph AI["🤖 AI Layer"]
        J["Ollama<br/>LLM Models<br/>Analysis"]
    end
    
    A -->|HTTP| C
    B -->|HTTP| C
    C -->|Process| D
    C -->|Analyze| E
    D -->|Orchestrate| F
    E -->|Query| G
    E -->|Search| H
    F -->|Metrics| I
    E -->|Analyze| J
    
    style Presentation fill:#fff9c4
    style API fill:#b3e5fc
    style Business fill:#c8e6c9
    style Data fill:#ffccbc
    style AI fill:#e0f2f1
```

## 🔌 Conectores Principais

### 1. **Frontend → FastAPI**
```
GET http://localhost:8000/
↓
server_fastapi.py @app.get("/")
↓
Renderiza templates/index.html
↓
Retorna HTML ao navegador
```

### 2. **Frontend → API**
```
POST http://localhost:8000/api/alerts
↓
server_fastapi.py @app.post("/api/alerts")
↓
Processa alerta
↓
Retorna JSON response
```

### 3. **FastAPI → Neo4j**
```
from neo4j import GraphDatabase
driver = GraphDatabase.driver(NEO4J_URI)
↓
Executa queries Cypher
↓
Armazena/recupera dados
```

### 4. **FastAPI → Qdrant**
```
from qdrant_client import QdrantClient
client = QdrantClient(QDRANT_URL)
↓
Busca vetorial
↓
Encontra similares
```

### 5. **FastAPI → Ollama**
```
import httpx
async with httpx.AsyncClient() as client:
    response = await client.post(f"{OLLAMA_URL}/api/generate")
↓
Análise com LLM
↓
Retorna insights
```

## 🎯 Fluxo Completo de Uma Requisição

```mermaid
graph LR
    A["1️⃣ Usuário clica<br/>Simulate Alert"] -->|GET /| B["2️⃣ FastAPI recebe"]
    B -->|Renderiza| C["3️⃣ index.html carrega"]
    C -->|Carrega| D["4️⃣ static/js/api.js"]
    D -->|Clica botão| E["5️⃣ POST /api/alerts"]
    E -->|Processa| F["6️⃣ Alert Pipeline"]
    F -->|Armazena| G["7️⃣ Neo4j"]
    F -->|Embeds| H["8️⃣ Qdrant"]
    F -->|Analisa| I["9️⃣ Ollama"]
    I -->|Retorna| J["🔟 Response JSON"]
    J -->|Atualiza| K["1️⃣1️⃣ Frontend UI"]
    
    style A fill:#fff9c4
    style B fill:#b3e5fc
    style C fill:#fff9c4
    style D fill:#fff9c4
    style E fill:#b3e5fc
    style F fill:#c8e6c9
    style G fill:#ffccbc
    style H fill:#f1f8e9
    style I fill:#e0f2f1
    style J fill:#b3e5fc
    style K fill:#fff9c4
```

## 📈 Monitoramento do Entry Point

```mermaid
graph TD
    A["🚀 server_fastapi.py<br/>Running on 0.0.0.0:8000"]
    
    A -->|Expõe| B["GET /health<br/>Health Check"]
    A -->|Expõe| C["GET /metrics<br/>Prometheus Metrics"]
    
    B -->|Verifica| D["✅ Neo4j Connection"]
    B -->|Verifica| E["✅ Qdrant Connection"]
    B -->|Verifica| F["✅ Ollama Connection"]
    
    C -->|Coleta| G["📊 Request Count"]
    C -->|Coleta| H["⏱️ Response Time"]
    C -->|Coleta| I["❌ Error Rate"]
    
    D -->|Status| J["🟢 Healthy"]
    E -->|Status| J
    F -->|Status| J
    
    G -->|Envia para| K["Prometheus<br/>localhost:9090"]
    H -->|Envia para| K
    I -->|Envia para| K
    
    K -->|Visualiza| L["Grafana<br/>localhost:3000"]
    
    style A fill:#f3e5f5,stroke:#7b1fa2,stroke-width:3px
    style B fill:#ffccbc
    style C fill:#b3e5fc
    style D fill:#c8e6c9
    style E fill:#c8e6c9
    style F fill:#c8e6c9
    style G fill:#b3e5fc
    style H fill:#b3e5fc
    style I fill:#b3e5fc
    style J fill:#a5d6a7
    style K fill:#fff9c4
    style L fill:#fff9c4
```

## 🔑 Variáveis de Ambiente Necessárias

```bash
# Banco de dados
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=strads123

# Vector store
QDRANT_URL=http://qdrant:6333

# Observabilidade
PROMETHEUS_URL=http://prometheus:9090

# LLM
OLLAMA_URL=http://ollama:11434

# Servidor
LOG_LEVEL=INFO
```

## 🎓 Como Começar

### 1. **Iniciar Docker Compose**
```bash
docker-compose -f docker-compose-frontend.yml up -d
```

### 2. **Acessar Frontend**
```
http://localhost:8000
```

### 3. **Verificar Health**
```bash
curl http://localhost:8000/health
```

### 4. **Ver Métricas**
```bash
curl http://localhost:8000/metrics
```

### 5. **Testar API**
```bash
curl -X POST http://localhost:8000/api/alerts \
  -H "Content-Type: application/json" \
  -d '{"service": "payment-api", "severity": "critical"}'
```

---

**Arquivo**: ENTRY_POINT_ARCHITECTURE.md  
**Versão**: 1.0  
**Última atualização**: 2026-02-06
