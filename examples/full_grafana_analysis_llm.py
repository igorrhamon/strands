from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.providers.github_models import GitHubModels

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
    # Expected shape from our provider: {"contentBlockDelta": {"delta": {"text": "..."}}}
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


async def _run_model(model: GitHubModels, user_prompt: str, system_prompt: str) -> str:
    """Stream model response and concatenate text deltas."""
    parts: List[str] = []
    async for ev in model.stream([{"role": "user", "content": user_prompt}], system_prompt=system_prompt):  # type: ignore[arg-type]
        parts.append(_extract_text_delta(ev))
    return "".join(parts)


def main() -> None:
    """Main entry point for Grafana analysis with LLM."""
    # Fail fast if GITHUB_TOKEN is missing (follows provider error handling pattern)
    if not os.environ.get("GITHUB_TOKEN"):
        raise EnvironmentError(
            "GITHUB_TOKEN not found in environment. "
            "Set it before running: export GITHUB_TOKEN='ghp_...'"
        )

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

    # Model configuration
    model_name = os.environ.get("GITHUB_MODELS_MODEL", os.environ.get("GITHUB_MODEL_NAME", "openai/gpt-5"))
    endpoint = os.environ.get("GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference")
    timeout = _get_int_env("GITHUB_MODELS_TIMEOUT", 120)  # Increased default to 120s for LLM analysis

    print(f"🤖 Inicializando modelo {model_name}...", file=sys.stderr)
    model = GitHubModels(endpoint=endpoint, model_name=model_name, timeout=timeout)

    # Prompts in Portuguese (SRE observability analysis)
    system_prompt = (
        "Você é um analista SRE/observabilidade. Sua tarefa é analisar um relatório JSON do Grafana (datasources, alert rules e dashboard/queries). "
        "Responda em português com uma análise completa e acionável, mas read-only (não proponha ações destrutivas). "
        "Estruture a resposta em: Resumo executivo; Sinais de saúde; Riscos/alertas; Hipóteses; Próximos passos de investigação (somente leitura)."
    )

    user_prompt = (
        "Analise o relatório a seguir. Se algum campo estiver vazio, explique o que isso significa e quais validações (read-only) fariam sentido.\n\n"
        f"RELATÓRIO_JSON=\n{json.dumps(report, ensure_ascii=False, indent=2)}"
    )

    print(f"⏳ Enviando para análise (timeout: {timeout}s)...", file=sys.stderr)
    
    # Execute async model call (correct usage of asyncio.run)
    text = asyncio.run(_run_model(model, user_prompt=user_prompt, system_prompt=system_prompt))
    
    print("✓ Análise concluída\n", file=sys.stderr)
    
    # Output analysis
    print(text.strip())


if __name__ == "__main__":
    main()
