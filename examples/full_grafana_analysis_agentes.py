from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.providers.agentes_pipeline import AgentesPipelineProvider

# Reuse the same data collection pipeline
from examples.full_grafana_analysis import build_report


def _get_int_env(name: str, default: int) -> int:
    """Parse integer from environment variable with fallback."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _extract_text_delta(ev: Any) -> str:
    """Extract text from streaming event using defensive parsing pattern."""
    # Expected shape from AgentesPipelineProvider: {"contentBlockDelta": {"delta": {"text": "..."}}}
    if not isinstance(ev, dict):
        return ""
    cbd = ev.get("contentBlockDelta")
    if not isinstance(cbd, dict):
        return ""
    delta = cbd.get("delta")  # type: ignore[union-attr]
    if not isinstance(delta, dict):
        return ""
    text = delta.get("text")  # type: ignore[union-attr]
    return text if isinstance(text, str) else ""


async def _run_model(
    model: AgentesPipelineProvider, user_prompt: str, system_prompt: str
) -> str:
    """Stream model response and concatenate text deltas."""
    parts: List[str] = []
    messages: Any = [{"role": "user", "content": user_prompt}]
    async for ev in model.stream(messages, system_prompt=system_prompt):
        parts.append(_extract_text_delta(ev))
    return "".join(parts)


def main() -> None:
    """Main entry point for Grafana analysis with Agentes Pipeline."""
    # Environment configuration
    start = os.environ.get("GRAFANA_FROM", "now-6h")
    end = os.environ.get("GRAFANA_TO", "now")
    environment = os.environ.get("ENVIRONMENT", "local")

    # Build Grafana report
    print("📊 Coletando dados do Grafana...", file=sys.stderr)
    report = build_report(start=start, end=end, environment=environment)

    # Validate report is not empty
    if not report or not isinstance(report, dict):
        raise ValueError(
            f"build_report() returned invalid data: {type(report)}. "
            "Check Grafana configuration and connectivity."
        )

    report_size = len(json.dumps(report))
    print(f"✓ Relatório coletado ({report_size} bytes)", file=sys.stderr)

    # Pipeline configuration (multi-stage analysis)
    # Stage 1: unif - Unified analysis
    # Stage 2: json - Structure into JSON
    # Stage 3: parecer - Final assessment with recommendations
    pipeline = ["unif", "json", "parecer"]
    endpoint = os.environ.get(
        "AGENTES_ROI2_ENDPOINT",
        "http://acs-assist-inov-4047.nia.desenv.bb.com.br"
    )
    timeout = _get_int_env("AGENTES_ROI2_TIMEOUT", 120)

    print(f"🤖 Inicializando pipeline de agentes: {' → '.join(pipeline)}...", file=sys.stderr)
    model = AgentesPipelineProvider(
        endpoint=endpoint,
        pipeline=pipeline,
        validate_json_steps=["json"],  # Validate JSON output from 'json' stage
        include_history=False,  # Return only final 'parecer' output
        timeout=timeout,
    )

    # Prompts in Portuguese (SRE observability analysis)
    system_prompt = (
        "Você é um analista SRE/observabilidade. Sua tarefa é analisar um relatório JSON do Grafana "
        "(datasources, alert rules e dashboard/queries). Responda em português com análise completa e acionável, "
        "mas read-only (não proponha ações destrutivas). "
        "Cada agente tem um papel específico:\n"
        "- unif: Análise unificada e resumida do relatório\n"
        "- json: Estruture a análise anterior em JSON bem formado\n"
        "- parecer: Gere parecer final com sinais críticos, riscos, hipóteses e próximos passos de investigação"
    )

    user_prompt = (
        "Analise o relatório a seguir. Se algum campo estiver vazio, explique o que isso significa e quais validações "
        "(read-only) fariam sentido.\n\n"
        f"RELATÓRIO_GRAFANA=\n{json.dumps(report, ensure_ascii=False, indent=2)}"
    )

    print(f"⏳ Enviando para análise em pipeline (timeout: {timeout}s)...", file=sys.stderr)

    # Execute async model call
    text = asyncio.run(_run_model(model, user_prompt=user_prompt, system_prompt=system_prompt))

    print("✓ Análise concluída\n", file=sys.stderr)

    # Output analysis
    print(text.strip())


if __name__ == "__main__":
    main()
