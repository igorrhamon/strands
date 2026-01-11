import os
import sys
import asyncio
import json
from pathlib import Path

# Add parent directory to path to import src module
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.providers.agentes_pipeline import AgentesPipelineProvider

try:
    from strands.agent import Agent
except Exception:
    Agent = None


def run_example():
    # If token isn't present, default to a mock call function.
    token = os.environ.get("AGENTES_ROI2_TOKEN")
    using_mock = not bool(token)

    pipeline = ["unif", "json", "parecer"]

    def mock_post_fn(url, payload, headers, timeout):
        # API Contract: {"data": {"agent_name": "...", "input": "..."}}
        agent_name = payload.get("data", {}).get("agent_name")
        agent_input = payload.get("data", {}).get("input", "")

        if agent_name == "unif":
            return _FakeResponse(200, {"data": {"resultado": f"[UNIF] {agent_input}"}, "message": [], "status": 200})

        if agent_name == "json":
            # Return a JSON object as text (like many LLMs/services do)
            out = {
                "valido": True,
                "texto_unificado": agent_input,
                "tags": ["demo"],
            }
            return _FakeResponse(200, {"data": {"resultado": json.dumps(out, ensure_ascii=False)}, "message": [], "status": 200})

        if agent_name == "parecer":
            return _FakeResponse(200, {"data": {"resultado": f"[PARECER] OK para: {agent_input}"}, "message": [], "status": 200})

        return _FakeResponse(200, {"data": {"resultado": f"[UNKNOWN:{agent_name}] {agent_input}"}, "message": [], "status": 200})

    provider = AgentesPipelineProvider(
        # Uses your required base URL by default (can be overridden by env AGENTES_ROI2_ENDPOINT)
        endpoint=os.environ.get("AGENTES_ROI2_ENDPOINT", "http://acs-assist-inov-4047.nia.desenv.bb.com.br"),
        pipeline=pipeline,
        validate_json_steps=["json"],
        include_history=True,
        post_fn=mock_post_fn if using_mock else None,
    )

    print("✅ AgentesPipelineProvider initialized")
    print(f"   Using mock: {using_mock}")
    print(f"   Endpoint: {provider.get_config()['endpoint']}{provider.get_config()['path']}")
    print(f"   Pipeline: {provider.get_config()['pipeline']}")

    prompt = "Relato: cliente reporta tentativa de fraude via PIX."

    async def demo_provider_direct():
        print("\n📤 Example: Calling provider directly\n")
        async for ev in provider.stream(
            [{"role": "user", "content": prompt}],
            system_prompt="Você é um analista de segurança.",
        ):
            text = ev["contentBlockDelta"]["delta"]["text"]
            print(text)

    def demo_via_strands_agent():
        if Agent is None:
            print("\n⚠️  strands.agent.Agent not available in this environment")
            return

        print("\n🤖 Example: Using provider via Strands Agent\n")
        agent = Agent(
            system_prompt="Você é um analista de segurança.",
            model=provider,
        )
        result = agent(prompt)
        print(result)

    async def main():
        await demo_provider_direct()
        await demo_via_strands_agent()

    asyncio.run(main())


class _FakeResponse:
    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data, ensure_ascii=False)

    def json(self):
        return self._data


if __name__ == "__main__":
    run_example()
