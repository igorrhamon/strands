# Matriz de Risco e Automação

| Tipo de Decisão | Nível de Risco | Automação Permitida | Requisito de Confiança |
| :--- | :--- | :--- | :--- |
| Reinício de Pod | LOW | ASSISTED | > 0.70 |
| Escalonamento de Recursos | MEDIUM | ASSISTED | > 0.80 |
| Mudança de Rota de Rede | HIGH | MANUAL | > 0.85 |
| Flush de Banco de Dados | CRITICAL | MANUAL | > 0.95 |

**Nota**: O Strands opera sob o princípio de "Human-in-the-loop". Nenhuma ação crítica é executada sem confirmação explícita.
