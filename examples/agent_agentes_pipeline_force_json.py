#!/usr/bin/env python3
"""
Agent example that calls the real agentes pipeline but forces the `json` step
to emit only a JSON object by using a restrictive `system_prompt`.

Usage:
    python examples/agent_agentes_pipeline_force_json.py
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# Make repo importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.agentes_pipeline import AgentesPipelineProvider, InvalidPipelineConfiguration


def run_example():
    pipeline = ["unif", "json", "parecer"]
    endpoint = os.environ.get(
        "AGENTES_ROI2_ENDPOINT",
        "http://acs-assist-inov-4047.nia.desenv.bb.com.br"
    )

    try:
        provider = AgentesPipelineProvider(
            endpoint=endpoint,
            pipeline=pipeline,
            validate_json_steps=["json"],
            include_history=True,
        )

    except InvalidPipelineConfiguration as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Construct a restrictive system prompt that instructs the json step
    # to output a single JSON object and nothing else.
    system_prompt = (
        "You are a sequence of agents executed in order: unif, json, parecer.\n"
        "When the pipeline reaches the agent named 'json', DO NOT output prose.\n"
        "Output only a single valid JSON object (no surrounding text, no explanation).\n"
        "The JSON object must contain at least the keys: 'valido' (boolean), 'texto_unificado' (string), 'tags' (list of strings).\n"
        "If you cannot produce the JSON, output '{\"valido\": false, \"json\": null, \"erro\": \"unable to produce json\"}'.\n"
        "Respond in Portuguese."
    )

    input_text = (
        "Relato de Segurança:\n- Tentativa de acesso à API de transferência\n- IP origem: 192.168.1.100\n"
        "- Hora: 2026-01-07 10:30:00 UTC\n- Bloqueada após 3 tentativas\n- Cliente: João Silva"
    )

    async def call_provider():
        try:
            messages = [{"role": "user", "content": input_text}]
            async for ev in provider.stream(messages, system_prompt=system_prompt):
                content_block = ev.get("contentBlockDelta", {})
                delta = content_block.get("delta", {})
                text = delta.get("text", "")
                print("--- RAW RESPONSE ---")
                print(text)

                # attempt to parse
                try:
                    parsed = json.loads(text)
                    print("--- PARSED JSON ---")
                    print(json.dumps(parsed, indent=2, ensure_ascii=False))
                except Exception as e:
                    print("--- JSON PARSE ERROR ---")
                    print(type(e).__name__, e)

        except Exception as e:
            print(f"❌ Error calling provider: {type(e).__name__}: {e}")

    asyncio.run(call_provider())


if __name__ == "__main__":
    run_example()
