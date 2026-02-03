from typing import Optional, Any, Dict, AsyncIterable, AsyncGenerator, Type, TypeVar, TypeAlias, TYPE_CHECKING
import os

try:
    from strands.models import Model
except Exception:  # pragma: no cover - provide fallback for test environments
    class Model:  # type: ignore
        pass

# Keep module import-safe in environments/tests that stub only `strands.models.Model`.
if TYPE_CHECKING:  # pragma: no cover
    from strands.types.streaming import StreamEvent as StreamEvent
    from strands.types.content import Messages as Messages
else:  # pragma: no cover
    StreamEvent: TypeAlias = Dict[str, Any]
    Messages: TypeAlias = Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OllamaModels(Model):
    """Provider that talks to a local Ollama server (http API).

    This implementation favors a simple, synchronous HTTP call to the local
    Ollama server. By default it collects the full response and yields a
    single event compatible with the project's `GitHubModels` shape. Streaming
    is supported via `streaming=True` which will attempt to parse chunked/NDJSON
    responses and yield incremental text deltas.
    """

    def __init__(self, host: str = "http://localhost:11434", model_id: str = "llama3.1", timeout: int = 30, streaming: bool = False):
        self.host = host.rstrip("/")
        self.model_id = model_id
        self.timeout = timeout
        self.streaming = streaming

        # lazy import httpx to keep module import-safe in test environments
        try:
            import httpx  # type: ignore

            self._httpx = httpx
        except Exception:
            self._httpx = None

    def get_config(self) -> Dict[str, Any]:
        return {"host": self.host, "model_id": self.model_id, "streaming": self.streaming}

    def update_config(self, **model_config) -> None:
        if "model_id" in model_config:
            self.model_id = model_config["model_id"]
        if "host" in model_config:
            self.host = model_config["host"].rstrip("/")
        if "streaming" in model_config:
            self.streaming = bool(model_config["streaming"])

    async def structured_output(self, output_model: Type[T], prompt: Messages, system_prompt: Optional[str] = None, **kwargs) -> AsyncGenerator[Dict[str, Any], None]:
        async for ev in self.stream(prompt, system_prompt=system_prompt, **kwargs):
            yield ev

    def _make_prompt_from_messages(self, messages: Messages, system_prompt: Optional[str]) -> str:
        parts = []
        if system_prompt:
            parts.append(f"System: {system_prompt}\n\n")
        for m in messages:
            role = m.get("role") if isinstance(m, dict) else getattr(m, "role", "user")
            content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
            if role == "system":
                parts.append(f"System: {content}\n\n")
            elif role == "assistant":
                parts.append(f"Assistant: {content}\n")
            else:
                parts.append(f"User: {content}\n")
        parts.append("Assistant:")
        return "\n".join(parts)

    def _call_generate_http(self, prompt: str, stream: bool = False) -> Any:
        if self._httpx is None:
            raise RuntimeError("httpx not available; please install httpx in your environment")

        url = f"{self.host}/api/generate"
        payload = {"model": self.model_id, "prompt": prompt}
        if stream:
            payload["stream"] = True

        client = self._httpx.Client(timeout=self.timeout)
        try:
            resp = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            return resp
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _parse_response_text(self, resp) -> Optional[str]:
        """Try to extract assistant text from a standard response object."""
        # Ollama typical response contains 'output' or 'text' fields in JSON
        try:
            data = resp.json()
        except Exception:
            text = getattr(resp, "text", None)
            return text if isinstance(text, str) else None

        # Common shapes: {'output': '...'}, {'text': '...'}, {'results': [{'content': '...'}]}
        for key in ("output", "text", "result", "results"):
            if key in data:
                val = data[key]
                if isinstance(val, str):
                    return val
                if isinstance(val, list) and len(val) > 0:
                    first = val[0]
                    if isinstance(first, dict):
                        for fk in ("content", "text", "output"):
                            v2 = first.get(fk)
                            if isinstance(v2, str):
                                return v2
        # final fallback: attempt to stringify
        return None

    async def stream(self, messages: Messages, tool_specs=None, system_prompt: Optional[str] = None, **kwargs) -> AsyncIterable[StreamEvent]:
        # Build prompt
        prompt = self._make_prompt_from_messages(messages, system_prompt)

        # If streaming mode requested in method call, respect it
        stream_flag = kwargs.get("streaming", self.streaming)

        if stream_flag:
            # Attempt streaming request and aggregate chunks into a single final string
            resp = self._call_generate_http(prompt, stream=True)

            collected_parts = []
            try:
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    text = chunk.decode("utf-8", errors="ignore")
                    # Some streaming payloads contain JSON per-line; try to extract 'response' field
                    stripped = text.strip()
                    # attempt to parse NDJSON pieces
                    try:
                        import json as _json

                        parsed = _json.loads(stripped)
                        if isinstance(parsed, dict) and "response" in parsed:
                            collected_parts.append(parsed["response"])
                            continue
                        # fallback: use raw text
                    except Exception:
                        pass

                    collected_parts.append(text)

                assistant_text = "".join(collected_parts)
                if not assistant_text:
                    # nothing collected; fallback to non-stream parse
                    assistant_text = self._parse_response_text(resp) or ""

                yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": assistant_text}}}
                return
            except Exception:
                # Fallthrough to non-stream parsing on error
                pass

        # Non-streaming: get response and parse full text
        resp = self._call_generate_http(prompt, stream=False)
        assistant_text = self._parse_response_text(resp)

        if assistant_text is None:
            raise RuntimeError("Could not parse assistant text from Ollama response")

        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": assistant_text}}}
