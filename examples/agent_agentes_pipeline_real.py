#!/usr/bin/env python3
"""
Agent that calls the real LLM agents pipeline endpoint (no mock).

Usage:
    python examples/agent_agentes_pipeline_real.py

Note: The real endpoint does not require authentication (running in desenv/hml environment).
"""

import os
import sys
import asyncio
import json
from typing import Any
from pathlib import Path

# Add parent directory to path to import src module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.agentes_pipeline import AgentesPipelineProvider, InvalidPipelineConfiguration

try:
    from strands.agent import Agent
except Exception:
    Agent = None


def run_example():
    print("✅ Using real endpoint (no token required)")

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

        print("✅ Provider initialized (real endpoint)")
        config = provider.get_config()
        print(f"   Endpoint: {config['endpoint']}{config['path']}")
        print(f"   Pipeline: {config['pipeline']}")

    except InvalidPipelineConfiguration as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Example security alert to analyze
    alert_text = """
    Relato de Segurança:
    - Tentativa de acesso à API de transferência
    - IP origem: 192.168.1.100 (conhecida)
    - Hora: 2026-01-07 10:30:00 UTC
    - Bloqueada após 3 tentativas
    - Cliente: João Silva (PJ - CNPJ: 12.345.678/0001-90)
    """

    async def demo_real_pipeline():
        print("\n📤 Calling real agents pipeline:\n")
        print(f"Input:\n{alert_text}\n")
        print("Processing through pipeline: unif → json → parecer\n")
        print("=" * 80)

        try:
            messages: Any = [{"role": "user", "content": alert_text}]
            async for ev in provider.stream(
                messages,
                system_prompt="Você é um analista de segurança experiente.",
            ):
                if not isinstance(ev, dict):
                    continue
                content_block = ev.get("contentBlockDelta", {})
                if not isinstance(content_block, dict):
                    continue
                delta = content_block.get("delta", {})
                if not isinstance(delta, dict):
                    continue
                result_text = delta.get("text", "")
                if not result_text:
                    continue

                # Parse and pretty-print
                try:
                    result_json = json.loads(result_text)
                    print("Result (parsed JSON):\n")
                    print(json.dumps(result_json, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    print("Result (raw text):\n")
                    print(result_text)

        except Exception as e:
            print(f"❌ Error calling pipeline: {type(e).__name__}: {e}")
            sys.exit(1)

        print("\n" + "=" * 80)

    def demo_via_agent():
        if Agent is None:
            return

        print("\n🤖 Using provider via Strands Agent:\n")

        try:
            agent = Agent(
                system_prompt="Você é um analista de segurança experiente.",
                model=provider,
            )

            result = agent(alert_text)
            print(result)

        except Exception as e:
            print(f"❌ Error with Agent: {type(e).__name__}: {e}")

    async def main():
        await demo_real_pipeline()
        demo_via_agent()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_example()
