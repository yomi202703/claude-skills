from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import time
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
    SpanExportResult,
)

from gemma_worker.store.sqlite_store import Store


_provider_installed = False


class SQLiteSpanExporter(SpanExporter):
    def __init__(self, store: Store):
        self._db_path = str(store.db_path)

    def export(self, spans):
        try:
            with sqlite3.connect(self._db_path, timeout=5.0) as db:
                db.execute("PRAGMA journal_mode=WAL")
                for sp in spans:
                    attrs = dict(sp.attributes or {})
                    db.execute(
                        "INSERT OR REPLACE INTO spans"
                        "(span_id, trace_id, parent_span_id, name, started_at, ended_at, attributes_json, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            format(sp.context.span_id, "016x"),
                            format(sp.context.trace_id, "032x"),
                            format(sp.parent.span_id, "016x") if sp.parent else None,
                            sp.name,
                            sp.start_time / 1e9 if sp.start_time else 0.0,
                            sp.end_time / 1e9 if sp.end_time else None,
                            json.dumps(attrs, ensure_ascii=False, default=str),
                            str(sp.status.status_code) if sp.status else None,
                        ),
                    )
                db.commit()
        except Exception:
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self):
        return None

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def install_tracer(store: Store | None = None) -> trace.Tracer:
    global _provider_installed
    if not _provider_installed:
        resource = Resource.create({"service.name": "gemma-worker"})
        provider = TracerProvider(resource=resource)
        otlp = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            except Exception:
                pass
        if os.environ.get("GEMMA_WORKER_CONSOLE_TRACE"):
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        if store is not None:
            provider.add_span_processor(BatchSpanProcessor(SQLiteSpanExporter(store)))
        trace.set_tracer_provider(provider)
        _provider_installed = True
    return trace.get_tracer("gemma-worker", "0.1.0")


def _stability_mode() -> str:
    return os.environ.get("OTEL_SEMCONV_STABILITY_OPT_IN", "gen_ai_latest").lower()


def _set_input_messages(span: trace.Span, prompt: str) -> None:
    messages = [{"role": "user", "content": [{"type": "text", "content": prompt[:64000]}]}]
    span.set_attribute("gen_ai.input.messages", json.dumps(messages, ensure_ascii=False))


def _set_output_messages(span: trace.Span, completion: str) -> None:
    messages = [{"role": "assistant", "parts": [{"type": "text", "content": completion[:64000]}]}]
    span.set_attribute("gen_ai.output.messages", json.dumps(messages, ensure_ascii=False))


@contextlib.contextmanager
def gen_ai_span(
    tracer: trace.Tracer,
    *,
    operation: str,
    system: str,
    model: str,
    prompt: str,
    completion: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    finish_reason: str | None = None,
    usage: dict[str, int] | None = None,
) -> Iterator[trace.Span]:
    name = f"gen_ai.{operation}"
    mode = _stability_mode()
    emit_legacy = mode in ("gen_ai_dup", "gen_ai/dup")
    emit_legacy_only = mode == "gen_ai_legacy"
    emit_new = not emit_legacy_only
    with tracer.start_as_current_span(name) as span:
        span.set_attribute("gen_ai.system", system)
        span.set_attribute("gen_ai.operation.name", operation)
        span.set_attribute("gen_ai.request.model", model)
        if emit_new:
            _set_input_messages(span, prompt)
            if completion is not None:
                _set_output_messages(span, completion)
        if emit_legacy or emit_legacy_only:
            span.set_attribute("gen_ai.prompt", prompt[:64000])
            if completion is not None:
                span.set_attribute("gen_ai.completion", completion[:64000])
        if tool_calls:
            span.set_attribute("gen_ai.response.tool_calls",
                               json.dumps(tool_calls, ensure_ascii=False))
        if finish_reason is not None:
            span.set_attribute("gen_ai.response.finish_reasons",
                               json.dumps([finish_reason], ensure_ascii=False))
            if emit_legacy or emit_legacy_only:
                span.set_attribute("gen_ai.response.finish_reason", finish_reason)
        if usage:
            for k, v in usage.items():
                if k == "prompt_tokens":
                    span.set_attribute("gen_ai.usage.input_tokens", int(v))
                elif k == "completion_tokens":
                    span.set_attribute("gen_ai.usage.output_tokens", int(v))
                else:
                    span.set_attribute(f"gen_ai.usage.{k}", int(v))
                if emit_legacy or emit_legacy_only:
                    span.set_attribute(f"gen_ai.usage.{k}", int(v))
        yield span
