from typing import Optional, Any, Dict, AsyncIterable, AsyncGenerator, Type, TypeVar, TypeAlias, TYPE_CHECKING
import os

from strands.models import Model

# Keep module import-safe in environments/tests that stub only `strands.models.Model`.
# Only import Strands typing helpers during type-checking.
if TYPE_CHECKING:  # pragma: no cover
    from strands.types.streaming import StreamEvent as StreamEvent
    from strands.types.content import Messages as Messages
else:  # pragma: no cover
    StreamEvent: TypeAlias = Dict[str, Any]
    Messages: TypeAlias = Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MissingTokenError(RuntimeError):
    pass


class GitHubModels(Model):
    def __init__(self, endpoint: str = "https://models.github.ai/inference", model_name: str = "openai/gpt-5-mini", timeout: int = 30):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise MissingTokenError("GITHUB_TOKEN not found in environment")
        self._token = token
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout = timeout

        # Lazy import to keep file import-safe when SDK isn't installed
        try:
            from azure.ai.inference import ChatCompletionsClient  # type: ignore
            self._client_cls: Any = ChatCompletionsClient  # type: ignore[assignment]
        except Exception:
            self._client_cls: Any = None  # type: ignore[assignment]

    def get_config(self) -> Dict[str, Any]:
        return {"endpoint": self.endpoint, "model_name": self.model_name}

    def update_config(self, **model_config) -> None:
        if "model_name" in model_config:
            self.model_name = model_config["model_name"]

    async def structured_output(
        self, output_model: Type[T], prompt: Messages, system_prompt: Optional[str] = None, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # For synchronous use-case we delegate to stream and collect final message
        async for ev in self.stream(prompt, system_prompt=system_prompt, **kwargs):
            yield ev  # type: ignore

    def _get_client(self):
        if self._client_cls is None:
            raise RuntimeError("azure-ai-inference SDK not available; ensure azure-ai-inference is installed")

        # azure-ai-inference typically expects an AzureKeyCredential; keep a string fallback
        # for compatibility with older SDKs and unit tests using fake clients.
        try:
            from azure.core.credentials import AzureKeyCredential  # type: ignore

            credential: Any = AzureKeyCredential(self._token)
        except Exception:
            credential = self._token

        return self._client_cls(self.endpoint, credential=credential)

    def _make_request(self, client, chat_messages):
        try:
            # azure-ai-inference (>=1.0.0b*) - timeout passed via kwargs
            if hasattr(client, "complete"):
                return client.complete(
                    model=self.model_name,
                    messages=chat_messages,
                    timeout=self.timeout
                )

            # Back-compat for earlier SDKs or for unit-test fake clients
            if hasattr(client, "get_chat_response"):
                return client.get_chat_response(model=self.model_name, messages=chat_messages, timeout=self.timeout)
            if hasattr(client, "create_chat_completion"):
                return client.create_chat_completion(model=self.model_name, messages=chat_messages, timeout=self.timeout)

            raise AttributeError(
                "GitHubModels client does not expose any supported chat completion method. "
                "Tried: complete, get_chat_response, create_chat_completion"
            )
        except Exception as e:
            msg = str(e)
            if "401" in msg or "403" in msg or "permission" in msg.lower():
                raise PermissionError(
                    "Permission error when calling GitHub Models. Ensure GITHUB_TOKEN has the required scope (e.g. 'models:use') and is valid. Original: "
                    + msg
                ) from e
            raise

    def _build_chat_messages(self, messages: Messages, system_prompt: Optional[str]) -> list:
        """Small helper to assemble chat messages payload (reduces complexity in stream)."""
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            chat_messages.append(m)
        return chat_messages

    def _parse_response(self, response) -> Optional[str]:
        # azure-ai-inference returns ChatCompletions with choices[*].message.content
        # but be defensive about multiple shapes.
        for parser in (self._parse_from_choices, self._parse_from_messages, self._parse_from_text):
            text = parser(response)
            if text is not None:
                return text
        return None

    def _parse_from_choices(self, response) -> Optional[str]:
        choices = getattr(response, "choices", None)
        if not choices:
            return None

        for choice in choices:
            if not self._is_assistant_choice(choice):
                continue

            msg = getattr(choice, "message", None)
            content = self._extract_message_content(msg)
            if content is not None:
                return content

            # Last-resort fallback for unusual SDK/test shapes.
            for attr in ("content", "text"):
                val = getattr(choice, attr, None)
                if isinstance(val, str):
                    return val

            if isinstance(msg, str):
                return msg

        return None

    def _is_assistant_choice(self, choice) -> bool:
        role = getattr(choice, "role", None)
        if role == "assistant":
            return True
        return getattr(choice, "finish_reason", None) is not None

    def _normalize_value(self, c) -> Optional[str]:
        """Normalize various types into string. Helper for content extraction."""
        if c is None:
            return None
        if isinstance(c, str):
            return c
        if isinstance(c, dict):
            return self._normalize_dict(c)
        if isinstance(c, (list, tuple)):
            return self._normalize_list(c)
        return self._normalize_object(c)

    def _normalize_dict(self, c: dict) -> Optional[str]:
        """Extract text from dict structure."""
        for key in ("text", "content", "value"):
            v = c.get(key)
            if isinstance(v, str):
                return v
            if isinstance(v, (list, dict)):
                nested = self._normalize_value(v)
                if nested:
                    return nested
        return None

    def _extract_item_text(self, item) -> Optional[str]:
        """Extract text from a single list item."""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return self._normalize_value(item)
        # try attribute access on objects
        text = getattr(item, "text", None)
        if isinstance(text, str):
            return text
        cont = getattr(item, "content", None)
        if isinstance(cont, str):
            return cont
        return None

    def _normalize_list(self, c) -> Optional[str]:
        """Extract and concatenate text from list structure."""
        parts = []
        for item in c:
            text = self._extract_item_text(item)
            if text:
                parts.append(text)
        return "".join(parts) if parts else None

    def _normalize_object(self, c) -> Optional[str]:
        """Extract text from object attributes."""
        for attr in ("text", "content"):
            val = getattr(c, attr, None)
            if isinstance(val, str):
                return val
        return None

    def _extract_message_content(self, msg) -> Optional[str]:
        """Extract text content from message in various formats."""
        if msg is None:
            return None

        # dict-like message
        if isinstance(msg, dict):
            return self._normalize_value(msg.get("content") or msg.get("text") or msg)

        # object-like message: try attributes first, then attempt normalization
        content = getattr(msg, "content", None)
        if content is not None:
            return self._normalize_value(content)

        text = getattr(msg, "text", None)
        if isinstance(text, str):
            return text

        # final attempt: try to normalize the message object itself
        return self._normalize_value(msg)

    def _parse_from_messages(self, response) -> Optional[str]:
        msgs = getattr(response, "messages", None)
        if not msgs:
            return None

        for m in msgs:
            if getattr(m, "role", None) != "assistant":
                continue
            # Use the generic extractor which normalizes dicts, lists, and
            # object-like message shapes into strings when possible.
            content = self._extract_message_content(m)
            if content is not None:
                return content

        return None

    def _parse_from_text(self, response) -> Optional[str]:
        text = getattr(response, "text", None)
        return text if isinstance(text, str) else None

    async def stream(self, messages: Messages, tool_specs=None, system_prompt: Optional[str] = None, **kwargs) -> AsyncIterable[StreamEvent]:
        # Synchronous provider: call the SDK synchronously via thread or simple blocking call

        client = self._get_client()
        chat_messages = self._build_chat_messages(messages, system_prompt)
        response = self._make_request(client, chat_messages)
        assistant_text = self._parse_response(response)

        if assistant_text is None:
            raise RuntimeError("Could not parse assistant text from GitHub Models response")
        # Log truncated assistant text for debugging (avoid extremely large logs)
        # Log truncated assistant text for debugging (avoid extremely large logs)
        self._log_preview(assistant_text)

        # Yield a StreamEvent with contentBlockDelta
        yield {
            "contentBlockDelta": {
                "contentBlockIndex": 0,
                "delta": {"text": assistant_text}
            }
        }

    def _log_preview(self, assistant_text: str) -> None:
        try:
            import logging
            _log = logging.getLogger(__name__)
            preview = assistant_text if len(assistant_text) < 1000 else assistant_text[:1000] + "...[truncated]"
            _log.info(f"GitHubModels assistant_text preview: {preview}")
        except Exception:
            # best-effort logging only
            pass
