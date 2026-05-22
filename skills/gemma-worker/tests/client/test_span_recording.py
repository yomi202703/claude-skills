from __future__ import annotations

import asyncio
import httpx
import pytest
import respx

from gemma_worker.client.base import build_client
from gemma_worker.store.sqlite_store import Store
from gemma_worker.tracer.otel_tracer import install_tracer


@pytest.mark.asyncio
async def test_span_recorded_after_llm_call(mock_env, monkeypatch, tmp_db):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    store = Store(tmp_db)
    await store.init()
    install_tracer(store)
    client = build_client()

    payload = {
        "id": "x", "object": "chat.completion", "model": "gemma-test",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 7, "total_tokens": 49},
    }
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        await client.call(system="be brief", user="hi", want_json=False)

    from opentelemetry import trace
    provider = trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush(timeout_millis=2000)
    await asyncio.sleep(0.2)

    import json as _json
    import aiosqlite
    async with aiosqlite.connect(tmp_db) as db:
        cur = await db.execute(
            "SELECT name, attributes_json FROM spans WHERE name = 'gen_ai.chat'"
        )
        rows = await cur.fetchall()
    assert rows, "expected at least one gen_ai.chat span"
    name, attrs_json = rows[-1]
    attrs = _json.loads(attrs_json)
    assert attrs.get("gen_ai.system") == "gemma"
    assert attrs.get("gen_ai.request.model") == "gemma-test"
    assert attrs.get("gen_ai.usage.input_tokens") == 42
    assert attrs.get("gen_ai.usage.output_tokens") == 7
    assert "gen_ai.input.messages" in attrs
    assert "gen_ai.output.messages" in attrs
