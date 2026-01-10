from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Ensure the repo `src` is importable when running pytest from the project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.providers.ollama_models import OllamaModels
import types


class DummyResp:
    def __init__(self, json_data=None, text_data=None, chunks=None):
        self._json = json_data
        self.text = text_data
        self._chunks = chunks

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        return None

    def iter_bytes(self):
        for c in self._chunks or []:
            yield c


class FakeClient:
    def __init__(self, resp: DummyResp):
        self.resp = resp

    def post(self, url, json=None, headers=None):
        return self.resp


def test_non_streaming_parses_text(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://localhost:11434")

    # Prepare a fake response shape
    data = {"output": "hello from model"}
    resp = DummyResp(json_data=data)

    def fake_httpx_Client(timeout):
        return FakeClient(resp)

    # Patch httpx in the provider
    provider = OllamaModels(host="http://localhost:11434", model_id="small-model")
    provider._httpx = types.SimpleNamespace(Client=lambda timeout=None: FakeClient(resp))

    async def run():
        msgs = [{"role": "user", "content": "Say hello"}]
        out = []
        async for ev in provider.stream(msgs):
            out.append(ev)
        assert len(out) == 1
        assert "hello from model" in out[0]["contentBlockDelta"]["delta"]["text"]

    asyncio.run(run())


def test_streaming_yields_chunks(monkeypatch):
    chunks = [b"hello ", b"world"]
    resp = DummyResp(chunks=chunks)
    provider = OllamaModels(host="http://localhost:11434", model_id="small-model", streaming=True)
    provider._httpx = types.SimpleNamespace(Client=lambda timeout=None: FakeClient(resp))

    async def run():
        msgs = [{"role": "user", "content": "Say hello"}]
        out = []
        async for ev in provider.stream(msgs):
            out.append(ev["contentBlockDelta"]["delta"]["text"])
        # aggregated into single event
        assert len(out) == 1
        assert out[0] == "hello world"

    asyncio.run(run())
