import asyncio
import itertools
import sys
from typing import AsyncGenerator, Any, Optional

import httpx

from strands.models import Model
from strands.types.content import Messages
from strands.types.streaming import StreamEvent


async def spinner_task(stop_event: asyncio.Event):
    spinner = itertools.cycle(["-", "/", "|", "\\"])
    last_line_length = 0
    while not stop_event.is_set():
        try:
            line = f" {next(spinner)} Thinking..."
            last_line_length = len(line)
            sys.stdout.write(line)
            sys.stdout.flush()
            await asyncio.sleep(0.1)
            sys.stdout.write("\\r")
        except asyncio.CancelledError:
            break
    # Clear the line
    sys.stdout.write("\r" + " " * last_line_length + "\r")
    sys.stdout.flush()


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

        stop_spinner_event = asyncio.Event()
        spinner = asyncio.create_task(spinner_task(stop_spinner_event))
        try:
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
        finally:
            stop_spinner_event.set()
            await spinner
