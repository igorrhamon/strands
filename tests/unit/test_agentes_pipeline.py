import asyncio
import os
import sys
import types
import json
import pytest

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Ensure a minimal strands.models.Model exists for tests when the real package
# is not installed in the environment.
if "strands" not in sys.modules:
    strands_mod = types.ModuleType("strands")
    models_mod = types.ModuleType("strands.models")

    class Model:
        pass

    models_mod.Model = Model  # type: ignore[attr-defined]
    strands_mod.models = models_mod  # type: ignore[attr-defined]
    sys.modules["strands"] = strands_mod
    sys.modules["strands.models"] = models_mod

from src.providers.agentes_pipeline import (
    AgentesPipelineProvider,
    MissingTokenError,
    InvalidPipelineConfiguration,
)


class FakeResponse:
    def __init__(self, status_code: int = 200, data=None, text: str = ""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        if isinstance(self._data, Exception):
            raise self._data
        return self._data


def test_missing_token_raises(monkeypatch):
    # Token is no longer required; removed this test
    pass


def test_empty_pipeline_raises(monkeypatch):
    with pytest.raises(InvalidPipelineConfiguration):
        AgentesPipelineProvider(pipeline=[], endpoint="http://example")


def test_pipeline_calls_agents_in_order(monkeypatch):
    calls = []

    def post_fn(url, payload, headers, timeout):
        calls.append({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
        # Extract full input which contains [AGENTE: name] prefix
        full_input = payload.get("data", {}).get("input", "")
        
        # Return nested response structure (real API contract)
        # Check for agent name at start of [AGENTE: ...] pattern
        if full_input.startswith("[AGENTE: unif]"):
            return FakeResponse(200, {
                "data": {
                    "context": {
                        "prompt_response": {
                            "acs_llm_prompt_execution": {
                                "response": {
                                    "data": {
                                        "messages": [
                                            {"content": "saida_unif"}
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            })
        elif full_input.startswith("[AGENTE: parecer]"):
            return FakeResponse(200, {
                "data": {
                    "context": {
                        "prompt_response": {
                            "acs_llm_prompt_execution": {
                                "response": {
                                    "data": {
                                        "messages": [
                                            {"content": "saida_parecer"}
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            })
        return FakeResponse(200, {
            "data": {
                "context": {
                    "prompt_response": {
                        "acs_llm_prompt_execution": {
                            "response": {
                                "data": {
                                    "messages": [
                                        {"content": "unknown"}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        })

    provider = AgentesPipelineProvider(
        endpoint="http://acs-assist-inov-4047.nia.desenv.bb.com.br",
        pipeline=["unif", "parecer"],
        include_history=False,
        post_fn=post_fn,
    )

    async def run():
        gen = provider.stream([{"role": "user", "content": "entrada"}])
        ev = await gen.__anext__()
        assert ev["contentBlockDelta"]["delta"]["text"] == "saida_parecer"

    asyncio.run(run())

    # Verify calls were made in order
    assert len(calls) == 2
    assert "[AGENTE: unif]" in calls[0]["payload"]["data"]["input"]
    assert "[AGENTE: parecer]" in calls[1]["payload"]["data"]["input"]


def test_validate_json_step_success(monkeypatch):
    def post_fn(url, payload, headers, timeout):
        full_input = payload.get("data", {}).get("input", "")
        if full_input.startswith("[AGENTE: json]"):
            return FakeResponse(200, {
                "data": {
                    "context": {
                        "prompt_response": {
                            "acs_llm_prompt_execution": {
                                "response": {
                                    "data": {
                                        "messages": [
                                            {"content": '{"a": 1}'}
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            })
        if full_input.startswith("[AGENTE: parecer]"):
            # ensure json from previous step is passed as stringified json
            assert json.dumps({"a": 1}, ensure_ascii=False) in full_input
            return FakeResponse(200, {
                "data": {
                    "context": {
                        "prompt_response": {
                            "acs_llm_prompt_execution": {
                                "response": {
                                    "data": {
                                        "messages": [
                                            {"content": "ok"}
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            })
        return FakeResponse(200, {
            "data": {
                "context": {
                    "prompt_response": {
                        "acs_llm_prompt_execution": {
                            "response": {
                                "data": {
                                    "messages": [
                                        {"content": "noop"}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        })

    provider = AgentesPipelineProvider(
        endpoint="http://example",
        pipeline=["json", "parecer"],
        validate_json_steps=["json"],
        include_history=True,
        post_fn=post_fn,
    )

    async def run():
        gen = provider.stream([{"role": "user", "content": "entrada"}])
        ev = await gen.__anext__()
        data = json.loads(ev["contentBlockDelta"]["delta"]["text"])
        assert data["status"] == "sucesso"
        assert data["resultado"] == "ok"
        assert data["historico"][0]["agente"] == "json"
        assert data["historico"][0]["validacao"]["valido"] is True

    asyncio.run(run())


def test_validate_json_step_failure(monkeypatch):
    def post_fn(url, payload, headers, timeout):
        full_input = payload.get("data", {}).get("input", "")
        if full_input.startswith("[AGENTE: json]"):
            return FakeResponse(200, {
                "data": {
                    "context": {
                        "prompt_response": {
                            "acs_llm_prompt_execution": {
                                "response": {
                                    "data": {
                                        "messages": [
                                            {"content": "{invalid json"}
                                        ]
                                    }
                                }
                            }
                        }
                    }
                }
            })
        return FakeResponse(200, {
            "data": {
                "context": {
                    "prompt_response": {
                        "acs_llm_prompt_execution": {
                            "response": {
                                "data": {
                                    "messages": [
                                        {"content": "should_not_run"}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        })

    provider = AgentesPipelineProvider(
        endpoint="http://example",
        pipeline=["json", "parecer"],
        validate_json_steps=["json"],
        include_history=True,
        post_fn=post_fn,
    )

    async def run():
        gen = provider.stream([{"role": "user", "content": "entrada"}])
        ev = await gen.__anext__()
        data = json.loads(ev["contentBlockDelta"]["delta"]["text"])
        assert data["status"] == "falha"
        assert data["etapa"] == "json"
        assert data["resultado"] is None
        assert data["erro"]

    asyncio.run(run())


def test_permission_error_detection(monkeypatch):
    monkeypatch.setenv("AGENTES_ROI2_TOKEN", "fake")

    def post_fn(url, payload, headers, timeout):
        return FakeResponse(403, {"error": "forbidden"}, text="403 Forbidden")

    provider = AgentesPipelineProvider(
        endpoint="http://example",
        pipeline=["unif"],
        include_history=False,
        post_fn=post_fn,
    )

    async def run():
        gen = provider.stream([{"role": "user", "content": "entrada"}])
        with pytest.raises(PermissionError):
            await gen.__anext__()

    asyncio.run(run())
