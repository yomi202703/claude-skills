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
async def test_exporter_honors_worker_trace_id_attribute(tmp_db):
    """Regression: SQLiteSpanExporter must store the supervisor-supplied
    `gemma_worker.trace_id` attribute as the row's trace_id column, so that
    Store.list_spans(supervisor_trace_id) returns the spans.

    Before the fix the exporter stored OTel's auto-generated 128-bit
    trace_id; runtime_gate / observability could not look up spans by the
    UUID hex that the supervisor uses to identify a run.

    This is a unit test against SQLiteSpanExporter directly, deliberately
    bypassing the install_tracer singleton (which makes per-test stores
    impossible to attach in the suite).
    """
    from gemma_worker.tracer.otel_tracer import SQLiteSpanExporter

    store = Store(tmp_db)
    await store.init()

    worker_trace_id = "deadbeef" * 4  # 32 hex chars to mimic uuid.hex
    otel_trace_id = 0x11112222333344445555666677778888
    otel_span_id = 0x9999AAAABBBBCCCC

    class _SpanCtx:
        def __init__(self, t, s):
            self.trace_id = t
            self.span_id = s

    class _Status:
        status_code = "OK"

    class _FakeSpan:
        def __init__(self, attrs):
            self.context = _SpanCtx(otel_trace_id, otel_span_id)
            self.parent = None
            self.name = "gen_ai.chat"
            self.start_time = 1_700_000_000_000_000_000
            self.end_time = 1_700_000_001_000_000_000
            self.attributes = attrs
            self.status = _Status()

    # Case 1: worker trace_id attribute present — row.trace_id must equal it
    SQLiteSpanExporter(store).export([
        _FakeSpan({"gemma_worker.trace_id": worker_trace_id, "gen_ai.system": "gemma"})
    ])
    spans = await store.list_spans(worker_trace_id)
    assert len(spans) == 1, (
        "exporter must store gemma_worker.trace_id attribute as the row's "
        "trace_id column"
    )
    assert spans[0]["trace_id"] == worker_trace_id

    # OTel trace_id must NOT be the row key when worker context exists
    otel_hex = format(otel_trace_id, "032x")
    fallback = await store.list_spans(otel_hex)
    assert fallback == [], "OTel trace_id must not shadow the worker trace_id"

    # Case 2: no worker trace_id attribute — fall back to OTel trace_id
    class _FakeSpan2(_FakeSpan):
        def __init__(self, attrs):
            super().__init__(attrs)
            self.context = _SpanCtx(0xAAAABBBBCCCCDDDDEEEEFFFF00001111, 0xDEADBEEF)

    SQLiteSpanExporter(store).export([_FakeSpan2({"gen_ai.system": "gemma"})])
    fallback_hex = format(0xAAAABBBBCCCCDDDDEEEEFFFF00001111, "032x")
    fb_spans = await store.list_spans(fallback_hex)
    assert len(fb_spans) == 1, "exporter must fall back to OTel trace_id when no worker context"


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
