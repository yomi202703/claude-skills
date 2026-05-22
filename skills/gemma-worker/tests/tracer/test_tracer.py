from __future__ import annotations

import pytest

from gemma_worker.store.sqlite_store import Store
from gemma_worker.tracer.otel_tracer import gen_ai_span, install_tracer


@pytest.mark.asyncio
async def test_install_returns_tracer(tmp_db):
    store = Store(tmp_db)
    await store.init()
    tracer = install_tracer(store)
    assert tracer is not None


@pytest.mark.asyncio
async def test_gen_ai_span_sets_attributes(tmp_db):
    store = Store(tmp_db)
    await store.init()
    tracer = install_tracer(store)
    with gen_ai_span(
        tracer,
        operation="chat",
        system="gemma",
        model="gemma-test",
        prompt="hi",
        completion="hello",
        finish_reason="stop",
        usage={"prompt_tokens": 1, "completion_tokens": 1},
    ) as span:
        assert span.is_recording()
        attrs = dict(span.attributes or {})
        assert "gen_ai.input.messages" in attrs
        assert "gen_ai.output.messages" in attrs
        assert "gen_ai.usage.input_tokens" in attrs
        assert "gen_ai.usage.output_tokens" in attrs
        assert "gen_ai.response.finish_reasons" in attrs
        assert "gen_ai.prompt" not in attrs
        assert "gen_ai.completion" not in attrs


@pytest.mark.asyncio
async def test_gen_ai_span_legacy_dup_mode(tmp_db, monkeypatch):
    monkeypatch.setenv("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_dup")
    store = Store(tmp_db)
    await store.init()
    tracer = install_tracer(store)
    with gen_ai_span(
        tracer,
        operation="chat",
        system="gemma",
        model="gemma-test",
        prompt="hi",
        completion="hello",
        finish_reason="stop",
    ) as span:
        attrs = dict(span.attributes or {})
        assert "gen_ai.input.messages" in attrs
        assert "gen_ai.prompt" in attrs
        assert "gen_ai.completion" in attrs
