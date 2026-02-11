# Documento do Confidence Engine 2.0

## Visão Geral
O motor de confiança do Strands não é heurístico, mas sim governado por uma matriz de pesos formalizada em `config/confidence_weights_v2026_02.yaml`.

## Componentes do Score
- **Base do Agente (40%)**: Confiança reportada pelo modelo/agente.
- **Qualidade da Evidência (30%)**: Verificabilidade dos dados coletados.
- **Acurácia Histórica (30%)**: Performance passada do agente em cenários similares.

## Thresholds por Nível de Risco
- **LOW**: 0.50 (Informativo)
- **MEDIUM**: 0.70 (Recomendação padrão)
- **HIGH**: 0.85 (Requer evidências fortes)
- **CRITICAL**: 0.95 (Exige consenso e histórico impecável)
