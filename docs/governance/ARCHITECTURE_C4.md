# Arquitetura Strands (C4 Model)

## 1. Contexto do Sistema
O Strands é uma Plataforma de Inteligência Operacional que atua entre o monitoramento (Grafana/Prometheus) e a resposta a incidentes, sugerindo ações baseadas em grafos de conhecimento e RAG.

## 2. Containers
- **Swarm Coordinator**: Orquestrador de agentes especializados.
- **Confidence Engine 2.0**: Motor de decisão governado por pesos e riscos.
- **Semantic Recovery (RAG)**: Recuperação de runbooks e decisões históricas via embeddings.
- **Distributed Deduplicator**: Gestão de estado global via Redis.
- **Graph Database (Neo4j)**: Armazenamento de relações causais e histórico.

## 3. Fluxo de Dados
1. Alerta chega via Webhook.
2. Deduplicador verifica existência no Redis.
3. Swarm inicia análise paralela.
4. Confidence Engine avalia evidências.
5. Decisão é registrada com metadados de versão para auditoria.
