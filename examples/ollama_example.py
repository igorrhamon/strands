from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.providers.ollama_models import OllamaModels


async def main():
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
    timeout = int(os.environ.get("OLLAMA_TIMEOUT", "120"))

    print(f"Using host={host} model={model} timeout={timeout}s")
    m = OllamaModels(host=host, model_id=model, timeout=timeout)
    msgs = [{"role": "user", "content": "Diga olá em português."}]

    try:
        async for ev in m.stream(msgs):
            print(ev["contentBlockDelta"]["delta"]["text"])
    except Exception as e:
        print("Error while calling Ollama:", type(e).__name__, str(e))


if __name__ == "__main__":
    asyncio.run(main())
