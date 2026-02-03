from __future__ import annotations

from typing import Optional, Any, Dict, AsyncIterable, AsyncGenerator, Type, TypeVar, TypeAlias, TYPE_CHECKING, Callable, Iterable
import json
import os

import httpx
from pydantic import BaseModel

from strands.models import Model

# Keep module import-safe in environments/tests that stub only `strands.models.Model`.
# Only import Strands typing helpers during type-checking.
if TYPE_CHECKING:  # pragma: no cover
    from strands.types.streaming import StreamEvent as StreamEvent
    from strands.types.content import Messages as Messages
else:  # pragma: no cover
    StreamEvent: TypeAlias = Dict[str, Any]
    Messages: TypeAlias = Any

T = TypeVar("T", bound=BaseModel)


class MissingTokenError(RuntimeError):
    pass


class InvalidPipelineConfiguration(RuntimeError):
    pass


class AgentesPipelineProvider(Model):
    """Provider que executa um pipeline sequencial de agentes via HTTP.

    - Endpoint default: `http://acs-assist-inov-4047.nia.desenv.bb.com.br/acs/llms/agent`
    - Auth: `Authorization: Bearer <AGENTES_ROI2_TOKEN>`
    - Execução: bulk (yield único StreamEvent)

    O pipeline recebe um input inicial (primeira mensagem do usuário) e executa cada
    agente em sequência, passando a saída como entrada do próximo.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        pipeline: Optional[Iterable[str]] = None,
        timeout: Optional[int] = None,
        validate_json_steps: Optional[Iterable[str]] = None,
        include_history: bool = True,
        post_fn: Optional[Callable[[str, Dict[str, Any], Dict[str, str], int], Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        self.endpoint = endpoint or os.environ.get(
            "AGENTES_ROI2_ENDPOINT", "http://acs-assist-inov-4047.nia.desenv.bb.com.br"
        ).rstrip("/")
        self.path = "/acs/llms/agent"
        self.timeout = int(timeout or os.environ.get("AGENTES_ROI2_TIMEOUT", "30"))

        self.pipeline = list(pipeline) if pipeline is not None else []
        if not self.pipeline:
            raise InvalidPipelineConfiguration("pipeline must contain at least one agent name")

        self.validate_json_steps = set(validate_json_steps or [])
        self.include_history = include_history
        self.context = context or {}

        # Injection seam for unit tests.
        # Signature: (url, json_payload, headers, timeout_seconds) -> response-like
        self._post_fn = post_fn

    def get_config(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "path": self.path,
            "pipeline": list(self.pipeline),
            "timeout": self.timeout,
            "include_history": self.include_history,
            "validate_json_steps": sorted(self.validate_json_steps),
        }

    def update_config(self, **model_config) -> None:
        if "endpoint" in model_config and model_config["endpoint"]:
            self.endpoint = str(model_config["endpoint"]).rstrip("/")
        if "timeout" in model_config and model_config["timeout"] is not None:
            self.timeout = int(model_config["timeout"])
        if "pipeline" in model_config and model_config["pipeline"] is not None:
            pipeline = list(model_config["pipeline"])
            if not pipeline:
                raise InvalidPipelineConfiguration("pipeline must contain at least one agent name")
            self.pipeline = pipeline
        if "include_history" in model_config:
            self.include_history = bool(model_config["include_history"])
        if "validate_json_steps" in model_config and model_config["validate_json_steps"] is not None:
            self.validate_json_steps = set(model_config["validate_json_steps"])

    async def structured_output(
        self, output_model: Type[T], prompt: Messages, system_prompt: Optional[str] = None, **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Delegate to stream for this repo's provider pattern.
        async for ev in self.stream(prompt, system_prompt=system_prompt, **kwargs):
            yield ev  # type: ignore

    def _build_url(self) -> str:
        return f"{self.endpoint}{self.path}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _extract_initial_input(self, messages: Messages) -> str:
        if messages is None:
            raise ValueError("messages is required")

        # Typical Strands shape: list[{'role': 'user', 'content': '...'}]
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, dict) and "content" in first:
                return str(first.get("content") or "")
            return str(first)

        # Fallback: treat as string
        return str(messages)

    def _strip_code_fences(self, text: str) -> str:
        s = text.strip()
        if s.startswith("```json"):
            s = s[len("```json") :].strip()
        elif s.startswith("```"):
            s = s[len("```") :].strip()
        if s.endswith("```"):
            s = s[:-3].strip()
        return s

    def _validate_json_text(self, raw: str) -> Dict[str, Any]:
        try:
            cleaned = self._strip_code_fences(raw)
            parsed = json.loads(cleaned)
            if isinstance(parsed, (dict, list)):
                return {"valido": True, "json": parsed, "erro": None}
            return {"valido": False, "json": None, "erro": "JSON válido, mas não é objeto/lista"}
        except Exception as e:
            return {"valido": False, "json": None, "erro": str(e)}

    def _post(self, payload: Dict[str, Any]) -> Any:
        url = self._build_url()
        headers = self._headers()

        if self._post_fn is not None:
            return self._post_fn(url, payload, headers, self.timeout)

        with httpx.Client(timeout=self.timeout) as client:
            return client.post(url, json=payload, headers=headers)

    def _raise_for_status(self, resp: Any) -> None:
        status_code = getattr(resp, "status_code", None)
        if status_code is None:
            return

        if status_code in (401, 403):
            raise PermissionError(
                f"Permission error calling agentes pipeline service (HTTP {status_code}). "
                "Verify AGENTES_ROI2_TOKEN is valid and has required permissions."
            )

        if status_code >= 400:
            body = getattr(resp, "text", "")
            raise RuntimeError(f"HTTP error calling agentes pipeline service: {status_code}. Body: {body}")

    def _parse_response_text(self, resp: Any) -> str:
        """
        Parse response from the real API.
        
        Real contract (from examples):
        response['data']['context']['prompt_response']['acs_llm_prompt_execution']['response']['data']['messages'][-1]['content']
        """
        try:
            data = resp.json() if hasattr(resp, "json") else None
        except Exception:
            data = None

        if not isinstance(data, dict):
            raise RuntimeError("API returned non-JSON response")

        # Navigate the nested structure from the real API
        try:
            content = (
                data.get("data", {})
                .get("context", {})
                .get("prompt_response", {})
                .get("acs_llm_prompt_execution", {})
                .get("response", {})
                .get("data", {})
                .get("messages", [])
            )
            
            if isinstance(content, list) and len(content) > 0:
                last_message = content[-1]
                if isinstance(last_message, dict):
                    text = last_message.get("content", "")
                    if isinstance(text, str) and text.strip():
                        return text
        except (KeyError, TypeError, IndexError):
            pass

        # Fallback: look for resultado/output at top level
        for key in ("resultado", "output", "text", "content", "message"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v

        # Last resort: raw text
        text = getattr(resp, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        raise RuntimeError("Could not parse response text from agentes service")

    def _call_agent(self, agent_name: str, agent_input: Any, system_prompt: Optional[str] = None) -> str:
        if isinstance(agent_input, (dict, list)):
            agent_input_str = json.dumps(agent_input, ensure_ascii=False)
        else:
            agent_input_str = str(agent_input)

        # Real API Contract (from examples):
        # POST /acs/llms/agent
        # {"data": {"input": "...", "intents": [...], "entities": [...], "context": {...}}}
        # Prepend agent_name as system instruction (like the examples do)
        full_input = f"[AGENTE: {agent_name}] {agent_input_str}"
        if system_prompt:
            full_input = f"{system_prompt}\n{full_input}"

        payload = {
            "data": {
                "input": full_input,
                "intents": [{}],
                "entities": [{}],
                "context": self.context.copy() if self.context else {},
            }
        }

        resp = self._post(payload)
        self._raise_for_status(resp)
        return self._parse_response_text(resp)

    def _execute_pipeline(self, initial_input: str, system_prompt: Optional[str]) -> Dict[str, Any]:
        historico: list[Dict[str, Any]] = []
        current: Any = initial_input

        for agent_name in self.pipeline:
            out_text = self._call_agent(agent_name, current, system_prompt=system_prompt)

            step: Dict[str, Any] = {"agente": agent_name, "entrada": current, "saida": out_text}

            if agent_name in self.validate_json_steps:
                validacao = self._validate_json_text(out_text)
                step["validacao"] = validacao
                historico.append(step)
                if not validacao["valido"]:
                    return {
                        "status": "falha",
                        "etapa": agent_name,
                        "erro": validacao["erro"],
                        "resultado": None,
                        "historico": historico,
                    }
                current = validacao["json"]
            else:
                historico.append(step)
                current = out_text

        return {
            "status": "sucesso",
            "etapa": self.pipeline[-1],
            "erro": None,
            "resultado": current,
            "historico": historico,
        }

    async def stream(
        self, messages: Messages, tool_specs=None, system_prompt: Optional[str] = None, **kwargs
    ) -> AsyncIterable[StreamEvent]:
        initial_input = self._extract_initial_input(messages)

        # Bulk execution. (Sync HTTP via httpx.Client)
        result = self._execute_pipeline(initial_input, system_prompt=system_prompt)

        if self.include_history:
            assistant_text = json.dumps(result, ensure_ascii=False)
        else:
            # If pipeline succeeded and last output is str, return it. Otherwise dump.
            if result.get("status") == "sucesso" and isinstance(result.get("resultado"), str):
                assistant_text = result["resultado"]
            else:
                assistant_text = json.dumps(result, ensure_ascii=False)

        yield {
            "contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": assistant_text}}
        }
