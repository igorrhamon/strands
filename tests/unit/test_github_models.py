import asyncio
import os
import sys
import types
import pytest

# Ensure repo root is on sys.path so `import src.*` works when running pytest.
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Ensure a minimal strands.models.Model exists for tests when the real package
# is not installed in the environment.
if "strands" not in sys.modules:
    strands_mod = types.ModuleType("strands")
    models_mod = types.ModuleType("strands.models")

    class Model:
        pass

    models_mod.Model = Model
    strands_mod.models = models_mod
    sys.modules["strands"] = strands_mod
    sys.modules["strands.models"] = models_mod

from src.providers.github_models import GitHubModels, MissingTokenError


class DummyChoice:
    def __init__(self, role=None, message=None, content=None, text=None, finish_reason=None):
        self.role = role
        self.message = message
        self.content = content
        self.text = text
        self.finish_reason = finish_reason


class DummyResponse:
    def __init__(self, choices=None, messages=None, text=None):
        self.choices = choices
        self.messages = messages
        self.text = text


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(MissingTokenError):
        GitHubModels()


def test_chat_shaped_parsing(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    class FakeClient:
        def __init__(self, endpoint, credential):
            pass

        def get_chat_response(self, model, messages, timeout):
            # return a response with choices shaped like SDK
            return DummyResponse(choices=[DummyChoice(role="assistant", message="Hello from assistant")])

    monkeypatch.setitem(__import__("src.providers.github_models", fromlist=["GitHubModels"]).__dict__, "ChatCompletionsClient", FakeClient)

    # monkeypatch _client_cls directly by instantiating and setting attribute
    provider = GitHubModels()
    provider._client_cls = FakeClient

    async def run():
        gen = provider.stream([{"role":"user","content":"Hi"}])
        ev = await gen.__anext__()
        assert "contentBlockDelta" in ev

    asyncio.get_event_loop().run_until_complete(run())


def test_text_fallback_parsing(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    class FakeClient2:
        def __init__(self, endpoint, credential):
            pass

        def get_chat_response(self, model, messages, timeout):
            return DummyResponse(text="Plain text response")

    provider = GitHubModels()
    provider._client_cls = FakeClient2

    async def run2():
        gen = provider.stream([{"role":"user","content":"Hi"}])
        ev = await gen.__anext__()
        assert ev["contentBlockDelta"]["delta"]["text"] == "Plain text response"

    asyncio.get_event_loop().run_until_complete(run2())


def test_permission_error_detection(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    class BadClient:
        def __init__(self, endpoint, credential):
            pass

        def get_chat_response(self, model, messages, timeout):
            raise RuntimeError("403 Forbidden: token lacks permission")

    provider = GitHubModels()
    provider._client_cls = BadClient

    async def run3():
        gen = provider.stream([{"role":"user","content":"Hi"}])
        with pytest.raises(PermissionError):
            await gen.__anext__()

    asyncio.get_event_loop().run_until_complete(run3())
