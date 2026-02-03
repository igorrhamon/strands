from typing import AsyncGenerator, Any, Optional

import httpx

from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent


class HTTPModel(Model):
    """Simple HTTP-backed Model provider for Strands Agents.

    Expects the endpoint to accept JSON {"prompt": "..."} and return
    either JSON {"text": "..."} or a plain-text body.
    """

    def __init__(self, endpoint_url: str, timeout: float = 60.0, **kwargs: Any):
        self.endpoint_url = endpoint_url
        self.timeout = timeout
        super().__init__(**kwargs)

    def update_config(self, **model_config: Any) -> None:
        return

    def get_config(self) -> Any:
        return {"model_id": self.endpoint_url, "max_tokens": 1024}

    async def structured_output(self, output_model: Any, prompt: Messages, system_prompt: Optional[str] = None, **kwargs: Any) -> AsyncGenerator[dict[str, Any], None]:
        chunks: list[str] = []
        async for ev in self.stream(prompt, system_prompt=system_prompt, **kwargs):
            cbd = ev.get("contentBlockDelta")
            if cbd:
                delta = cbd.get("delta", {})
                text = delta.get("text")
                if text:
                    chunks.append(text)
        yield {"output": "".join(chunks)}

    async def stream(self, messages: Messages, tool_specs: Optional[list] = None, system_prompt: Optional[str] = None, **kwargs: Any) -> AsyncGenerator[StreamEvent, None]:
        prompt_parts: list[str] = []
        for m in messages:
            role = m.get("role")
            for block in m.get("content", []):
                text = block.get("text")
                if text:
                    prompt_parts.append(f"[{role}] {text}")

        payload = {"prompt": "\n".join(prompt_parts), "max_tokens": kwargs.get("max_tokens", 1024)}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.endpoint_url, json=payload)
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                data = None

            if isinstance(data, dict) and "text" in data:
                yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": data["text"]}}}
                return

            yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": resp.text}}}
