from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from gemma_worker.client.base import build_client
from gemma_worker.playbooks.gap import run as run_gap
from gemma_worker.playbooks.inconsistency import run as run_inconsistency
from gemma_worker.playbooks.optimization import run as run_optimization
from gemma_worker.playbooks.research import run as run_research
from gemma_worker.playbooks.synthesis import run as run_synthesis
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store


def _mk_payload(content: str) -> dict:
    return {
        "id": "x", "object": "chat.completion", "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


@pytest.fixture
def fixture_dir():
    return Path(__file__).parent.parent / "fixtures" / "sample_repo"


@pytest.fixture
async def env(monkeypatch, tmp_db):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    monkeypatch.setenv("WORKER_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("WORKER_LLM_MODEL", "gemma-test")
    store = Store(tmp_db)
    await store.init()
    pool = WorkerPool(max_concurrency=2)
    await pool.start()
    yield build_client(), pool, store
    await pool.close()


@pytest.mark.asyncio
async def test_inconsistency(env, fixture_dir):
    client, pool, store = env
    arr = json.dumps([{
        "file": "x.py", "line": 3,
        "evidence": "docstring says A but code does B",
        "severity": "medium", "why": "mismatch",
    }])
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(return_value=httpx.Response(200, json=_mk_payload(arr)))
        out = await run_inconsistency(
            task=f"check {fixture_dir}",
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out and out[0]["playbook"] == "inconsistency"


@pytest.mark.asyncio
async def test_gap(env, fixture_dir):
    client, pool, store = env
    enum_payload = _mk_payload('{"expected": ["error handling", "tests"]}')
    audit_payload = _mk_payload(json.dumps([{
        "file": "x.py", "line": 1,
        "evidence": "no error handling", "severity": "high",
        "why": "missing",
    }]))
    call_n = {"i": 0}

    def side_effect(req):
        call_n["i"] += 1
        if call_n["i"] == 1:
            return httpx.Response(200, json=enum_payload)
        return httpx.Response(200, json=audit_payload)

    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(side_effect=side_effect)
        out = await run_gap(
            task=f"audit {fixture_dir}",
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out and out[0]["playbook"] == "gap"


@pytest.mark.asyncio
async def test_research_escalates(env):
    client, pool, store = env
    payload = _mk_payload('{"queries": ["q1", "q2"], "escalate_to_ceo": true}')
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(return_value=httpx.Response(200, json=payload))
        out = await run_research(
            task="find latest LangGraph release notes",
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out
    assert out[0]["playbook"] == "research"
    assert out[0]["file"] == "ceo_escalation"


@pytest.mark.asyncio
async def test_optimization(env, fixture_dir):
    client, pool, store = env
    arr = json.dumps([{
        "file": "x.py", "line": 5,
        "evidence": "for i in range(n): for j in range(n):",
        "severity": "medium", "why": "O(n^2)",
        "suggestion": "use set lookup",
    }])
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(return_value=httpx.Response(200, json=_mk_payload(arr)))
        out = await run_optimization(
            task=f"optimize {fixture_dir}",
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out and out[0]["suggestion"] == "use set lookup"


@pytest.mark.asyncio
async def test_synthesis(env, fixture_dir):
    client, pool, store = env
    per_file = _mk_payload('{"file": "x.py", "summary": "computes things.", "standout": ["pure"]}')
    global_payload = _mk_payload(json.dumps([{
        "file": "(global)", "line": 0,
        "evidence": "everything is pure functions",
        "severity": "low", "why": "refactor opportunity",
    }]))
    call_n = {"i": 0}

    def side_effect(req):
        call_n["i"] += 1
        body = req.content.decode("utf-8")
        if "Per-file summaries" in body:
            return httpx.Response(200, json=global_payload)
        return httpx.Response(200, json=per_file)

    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(side_effect=side_effect)
        out = await run_synthesis(
            task=f"overview of {fixture_dir}",
            client=client, pool=pool, store=store, reflexion=[],
        )
    kinds = {a.get("kind") for a in out}
    assert "file_summary" in kinds
    assert "global_theme" in kinds
