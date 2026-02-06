# 🐳 Docker Guide - Strands Frontend

## 📋 Overview

Este guia explica como usar Docker para executar o frontend refatorado do Strands com todas as dependências.

## 🚀 Quick Start

### Opção 1: Usar docker-compose-frontend.yml (Recomendado para Desenvolvimento)

```bash
# Clonar a branch
git checkout feat/frontend-refactor

# Iniciar todos os serviços
docker-compose -f docker-compose-frontend.yml up -d

# Aguardar ~30 segundos para os serviços iniciarem

# Acessar no navegador
# http://localhost:8000
```

### Opção 2: Usar docker-compose.yaml (Produção)

```bash
# Iniciar stack completa
docker-compose up -d

# Acessar
# http://localhost:8000
```

### Opção 3: Build e Run Manual

```bash
# Build da imagem
docker build -t strands:latest .

# Executar container
docker run -p 8000:8000 \
  -v $(pwd)/templates:/app/templates \
  -v $(pwd)/static:/app/static \
  strands:latest
```

## 🔍 Serviços Disponíveis

### docker-compose-frontend.yml

| Serviço | Porta | URL |
|---------|-------|-----|
| **Strands Dashboard** | 8000 | http://localhost:8000 |
| **Neo4j** | 7474/7687 | http://localhost:7474 |
| **Qdrant** | 6333/6334 | http://localhost:6333 |
| **Prometheus** | 9090 | http://localhost:9090 |
| **Grafana** | 3000 | http://localhost:3000 |
| **Ollama** | 11434 | http://localhost:11434 |

### docker-compose.yaml

Inclui todos os serviços acima + Grafana Proxy (porta 3100)

## 📊 Verificar Status

```bash
# Ver status de todos os containers
docker-compose -f docker-compose-frontend.yml ps

# Ver logs do dashboard
docker-compose -f docker-compose-frontend.yml logs -f strands-dashboard

# Ver logs de um serviço específico
docker-compose -f docker-compose-frontend.yml logs -f neo4j
```

## 🧪 Testar Funcionalidades

### 1. Dashboard Carregando

```bash
# Verificar se o dashboard está respondendo
curl http://localhost:8000

# Deve retornar HTML da página
```

### 2. Simular Alerta

```bash
# Via curl
curl -X POST http://localhost:8000/simulate/alert?active=true

# Ou acessar http://localhost:8000 e clicar no botão
```

### 3. Verificar Métricas

```bash
# Prometheus
curl http://localhost:9090/api/v1/targets

# Grafana
curl http://localhost:3000/api/health
```

## 🔧 Configuração

### Variáveis de Ambiente

```bash
# No docker-compose-frontend.yml, você pode alterar:

environment:
  - NEO4J_URI=bolt://neo4j:7687
  - NEO4J_USER=neo4j
  - NEO4J_PASSWORD=strads123
  - QDRANT_URL=http://qdrant:6333
  - PROMETHEUS_URL=http://prometheus:9090
  - LOG_LEVEL=DEBUG  # ou INFO, WARNING, ERROR
```

### Volumes

```bash
# Templates (hot reload)
- ./templates:/app/templates

# Static files (CSS, JS)
- ./static:/app/static

# Source code
- ./src:/app/src
```

## 🛠️ Desenvolvimento

### Hot Reload Habilitado

O `docker-compose-frontend.yml` usa `--reload` no uvicorn, então:

```bash
# Editar arquivo
vim templates/components/header.html

# Salvar
# O servidor detecta mudança automaticamente
# Recarregar navegador para ver mudanças
```

### Debug Mode

```bash
# Alterar LOG_LEVEL em docker-compose-frontend.yml
- LOG_LEVEL=DEBUG

# Reiniciar
docker-compose -f docker-compose-frontend.yml restart strands-dashboard
```

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs detalhados
docker-compose -f docker-compose-frontend.yml logs strands-dashboard

# Verificar se porta 8000 está em uso
lsof -i :8000

# Se estiver, matar processo
kill -9 <PID>
```

### Arquivos estáticos não carregam

```bash
# Verificar se volumes estão montados
docker-compose -f docker-compose-frontend.yml exec strands-dashboard ls -la /app/static

# Se vazio, copiar arquivos
docker-compose -f docker-compose-frontend.yml exec strands-dashboard cp -r /app/static/* /app/static/
```

### Neo4j não conecta

```bash
# Verificar health
docker-compose -f docker-compose-frontend.yml exec neo4j cypher-shell -u neo4j -p strads123 "RETURN 1"

# Ver logs
docker-compose -f docker-compose-frontend.yml logs neo4j
```

### Qdrant não conecta

```bash
# Verificar health
curl http://localhost:6333/health

# Ver logs
docker-compose -f docker-compose-frontend.yml logs qdrant
```

## 📦 Limpeza

### Parar containers

```bash
docker-compose -f docker-compose-frontend.yml down
```

### Remover volumes (CUIDADO: deleta dados!)

```bash
docker-compose -f docker-compose-frontend.yml down -v
```

### Remover tudo

```bash
docker-compose -f docker-compose-frontend.yml down -v
docker system prune -a
```

## 🚀 Deploy em Produção

### 1. Build da imagem

```bash
docker build -t strands:v1.0 .
```

### 2. Tag para registry

```bash
docker tag strands:v1.0 your-registry/strands:v1.0
```

### 3. Push para registry

```bash
docker push your-registry/strands:v1.0
```

### 4. Deploy com docker-compose.yaml

```bash
# Atualizar imagem em docker-compose.yaml
# strands-dashboard:
#   image: your-registry/strands:v1.0

docker-compose up -d
```

## 📊 Monitoramento

### Prometheus

```bash
# Acessar
http://localhost:9090

# Queries úteis:
# - up (status de targets)
# - rate(http_requests_total[5m]) (taxa de requisições)
# - process_resident_memory_bytes (memória)
```

### Grafana

```bash
# Acessar
http://localhost:3000

# Credenciais padrão:
# Username: admin
# Password: strads_grafana

# Adicionar Prometheus como datasource:
# URL: http://prometheus:9090
```

## 🔗 Networking

Os containers se comunicam através da rede `strads_network`:

```
strands-dashboard
├─ neo4j (bolt://neo4j:7687)
├─ qdrant (http://qdrant:6333)
├─ prometheus (http://prometheus:9090)
└─ ollama (http://ollama:11434)
```

## 📚 Arquivos Relacionados

- `Dockerfile` - Configuração da imagem Docker
- `docker-compose.yaml` - Stack completa (produção)
- `docker-compose-frontend.yml` - Stack frontend (desenvolvimento)
- `FRONTEND_ACCESS_GUIDE.md` - Guia de acesso local
- `FRONTEND_REFACTOR_README.md` - Detalhes da refatoração

## 🎯 Próximos Passos

1. **Testar localmente** com docker-compose-frontend.yml
2. **Validar funcionalidades** (simular alerta, aprovar/rejeitar)
3. **Verificar logs** para erros
4. **Deploy em staging** com docker-compose.yaml
5. **Monitorar com Prometheus/Grafana**

## 📞 Suporte

Para problemas:

1. Verificar logs: `docker-compose logs -f`
2. Verificar health: `docker-compose ps`
3. Verificar conectividade: `docker-compose exec <service> curl <url>`
4. Ler `FRONTEND_ACCESS_GUIDE.md` para mais detalhes

---

**Status**: Pronto para uso  
**Última atualização**: 2026-02-06  
**Branch**: feat/frontend-refactor
