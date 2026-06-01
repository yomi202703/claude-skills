from __future__ import annotations

import json
import re
import time
import uuid
from contextvars import ContextVar
from typing import Any

# ContextVars so that concurrent supervisor.run() calls in the same process
# do not stomp on each other's trace_id / task_id. Previously these lived in a
# module-global dict which is not safe under asyncio task interleaving.
_trace_id_var: ContextVar[str | None] = ContextVar("gemma_worker_trace_id", default=None)
_task_id_var: ContextVar[str | None] = ContextVar("gemma_worker_task_id", default=None)


def set_worker_context(*, trace_id: str | None, task_id: str | None) -> None:
    _trace_id_var.set(trace_id)
    _task_id_var.set(task_id)

from openai import AsyncOpenAI
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from opentelemetry import trace
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from gemma_worker.client.base import CallResult, WorkerConfig
from gemma_worker.tracer.otel_tracer import gen_ai_span

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?|\n?```\s*$", re.IGNORECASE)


def strip_code_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = _CODE_FENCE_RE.sub("", s)
    return s.strip()


def try_parse_json(text: str) -> Any | None:
    s = strip_code_fence(text)
    if not s:
        return None
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def make_client(cfg: WorkerConfig) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        timeout=cfg.timeout_s,
        max_retries=0,
    )


_RETRYABLE = (APITimeoutError, APIConnectionError, RateLimitError, APIError)


def _flatten_messages_for_span(messages: list[dict[str, str]]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


async def call_chat(
    *,
    client: AsyncOpenAI,
    model: str,
    messages: list[dict[str, str]],
    max_retries: int,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    want_json: bool = False,
    system_name: str = "unknown",
    worker_trace_id: str | None = None,
    worker_task_id: str | None = None,
) -> CallResult:
    trace_id = uuid.uuid4().hex
    started = time.perf_counter()
    last_exc: BaseException | None = None
    raw: dict[str, Any] = {}
    text = ""
    tracer = trace.get_tracer("gemma-worker", "0.1.0")
    span_prompt = _flatten_messages_for_span(messages)
    effective_worker_trace = worker_trace_id or _trace_id_var.get()
    effective_worker_task = worker_task_id or _task_id_var.get()
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(max_retries + 1),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=False,
    ):
        with attempt:
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            with gen_ai_span(
                tracer,
                operation="chat",
                system=system_name,
                model=model,
                prompt=span_prompt,
            ) as span:
                if effective_worker_trace:
                    span.set_attribute("gemma_worker.trace_id", effective_worker_trace)
                if effective_worker_task:
                    span.set_attribute("gemma_worker.task_id", effective_worker_task)
                try:
                    resp = await client.chat.completions.create(**kwargs)
                except Exception as e:
                    last_exc = e
                    span.set_attribute("gen_ai.response.finish_reasons",
                                       json.dumps(["error"], ensure_ascii=False))
                    span.set_attribute("error", str(e)[:1024])
                    raise
                # Defensive: some providers can return empty choices on
                # content filtering or upstream errors. Treat as a retryable
                # error rather than IndexError.
                choices = getattr(resp, "choices", None) or []
                if not choices:
                    last_exc = APIError(
                        message="empty choices in response",
                        request=None,  # type: ignore[arg-type]
                        body=None,
                    )
                    span.set_attribute("error", "empty_choices")
                    raise last_exc
                text = (choices[0].message.content or "").strip()
                finish_reason = choices[0].finish_reason or "stop"
                raw = {
                    "finish_reason": finish_reason,
                    "model": resp.model,
                }
                usage = getattr(resp, "usage", None)
                tin = getattr(usage, "prompt_tokens", 0) if usage else 0
                tout = getattr(usage, "completion_tokens", 0) if usage else 0
                span.set_attribute("gen_ai.output.messages",
                                   json.dumps(
                                       [{"role": "assistant",
                                         "parts": [{"type": "text",
                                                    "content": text[:64000]}]}],
                                       ensure_ascii=False,
                                   ))
                span.set_attribute("gen_ai.response.finish_reasons",
                                   json.dumps([finish_reason], ensure_ascii=False))
                span.set_attribute("gen_ai.usage.input_tokens", int(tin))
                span.set_attribute("gen_ai.usage.output_tokens", int(tout))
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            parsed = try_parse_json(text) if want_json else None
            if want_json and parsed is None:
                return CallResult(
                    text=text,
                    json=None,
                    status="error",
                    error="json_parse_failed",
                    latency_ms=elapsed_ms,
                    tokens_in=tin,
                    tokens_out=tout,
                    trace_id=trace_id,
                    raw=raw,
                )
            return CallResult(
                text=strip_code_fence(text) if not want_json else text,
                json=parsed,
                status="ok",
                error=None,
                latency_ms=elapsed_ms,
                tokens_in=tin,
                tokens_out=tout,
                trace_id=trace_id,
                raw=raw,
            )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return CallResult(
        text="",
        json=None,
        status="error",
        error=str(last_exc) if last_exc else "unknown",
        latency_ms=elapsed_ms,
        trace_id=trace_id,
    )
