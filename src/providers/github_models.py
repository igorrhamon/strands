from typing import Optional, Any, Dict
import os

from strands.models import Model


class MissingTokenError(RuntimeError):
    pass


class GitHubModels(Model):
    def __init__(self, endpoint: str = "https://models.github.ai/inference", model_name: str = "openai/gpt-5", timeout: int = 30):
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise MissingTokenError("GITHUB_TOKEN not found in environment")
        self._token = token
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout = timeout

        # Lazy import to keep file import-safe when SDK isn't installed
        try:
            from azure.ai.inference import ChatCompletionsClient
            self._client_cls = ChatCompletionsClient
        except Exception:
            self._client_cls = None

    def get_config(self) -> Dict[str, Any]:
        return {"endpoint": self.endpoint, "model_name": self.model_name}

    def update_config(self, **model_config) -> None:
        if "model_name" in model_config:
            self.model_name = model_config["model_name"]

    async def structured_output(self, output_model, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        # For synchronous use-case we delegate to stream and collect final message
        events = []
        async for ev in self.stream([{"role": "user", "content": prompt}], system_prompt=system_prompt, **kwargs):
            events.append(ev)
        # Map events to structured output if required by strands SDK
        return events

    async def stream(self, messages, system_prompt: Optional[str] = None, **kwargs):
        # Synchronous provider: call the SDK synchronously via thread or simple blocking call
        if self._client_cls is None:
            raise RuntimeError("azure-ai-inference SDK not available; ensure azure-ai-inference is installed")

        # Build chat messages payload
        chat_messages = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        for m in messages:
            chat_messages.append(m)

        # Instantiate client and call complete
        client = self._client_cls(self.endpoint, credential=self._token)

        # The exact client call may vary by SDK; attempt common method names
        try:
            response = client.get_chat_response(model=self.model_name, messages=chat_messages, timeout=self.timeout)
        except AttributeError:
            response = client.create_chat_completion(model=self.model_name, messages=chat_messages, timeout=self.timeout)
        except Exception as e:
            # Detect common permission errors surfaced by SDK or HTTP layer
            msg = str(e)
            if "401" in msg or "403" in msg or "permission" in msg.lower():
                raise PermissionError(
                    "Permission error when calling GitHub Models. Ensure GITHUB_TOKEN has the required scope (e.g. 'models:use') and is valid. Original: "
                    + msg
                ) from e
            raise

        # Parse response: prefer messages/choices with role=assistant, fallback to text
        assistant_text = None
        try:
            # Try chat-shaped response (choices preferred)
            choices = getattr(response, "choices", None)
            if choices:
                for c in choices:
                    role = getattr(c, "role", None)
                    if role == "assistant" or getattr(c, "finish_reason", None) is not None:
                        assistant_text = getattr(c, "message", None) or getattr(c, "content", None) or getattr(c, "text", None)
                        break

            # Next try messages array
            if assistant_text is None:
                msgs = getattr(response, "messages", None)
                if msgs:
                    for m in msgs:
                        if getattr(m, "role", None) == "assistant":
                            assistant_text = getattr(m, "content", None) or getattr(m, "text", None)
                            break

            # Fallback to top-level text
            if assistant_text is None:
                assistant_text = getattr(response, "text", None)
        except Exception:
            # Let parsing errors surface as SDK/HTTP errors
            raise

        if assistant_text is None:
            raise RuntimeError("Could not parse assistant text from GitHub Models response")

        # Yield a single StreamEvent shaped dict expected by strands (contentBlockDelta)
        yield {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": assistant_text}}}
