from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from gemma_worker.client.base import build_client
from gemma_worker.playbooks.deadcode import run as run_deadcode
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store


@pytest.mark.asyncio
async def test_deadcode_returns_findings(mock_env, monkeypatch, tmp_db):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    client = build_client()

    payload = {
        "id": "x",
        "object": "chat.completion",
        "model": "m",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps([
                        {
                            "file": "x.py", "line": 5,
                            "symbol": "unused_orphan_xyz",
                            "evidence": "no callers", "severity": "medium",
                            "why": "exported but not referenced",
                        }
                    ]),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    store = Store(tmp_db)
    await store.init()
    pool = WorkerPool(max_concurrency=2)
    await pool.start()
    fixture = Path(__file__).parent.parent / "fixtures" / "sample_repo"
    try:
        with respx.mock(base_url="https://mock.invalid/v1") as router:
            router.post("/chat/completions").mock(
                return_value=httpx.Response(200, json=payload)
            )
            artifacts = await run_deadcode(
                task=f"find unused exports in {fixture}",
                client=client,
                pool=pool,
                store=store,
                reflexion=[],
            )
    finally:
        await pool.close()

    assert artifacts
    deadcode_artifacts = [a for a in artifacts if a.get("axis") != "escalation"]
    assert deadcode_artifacts
    assert any(a.get("symbol") == "unused_orphan_xyz" for a in deadcode_artifacts)
    assert all(a["playbook"] == "deadcode" for a in artifacts)
    assert any(a.get("axis") == "escalation" for a in artifacts)


@pytest.mark.asyncio
async def test_deadcode_empty_target(mock_env, monkeypatch, tmp_db):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    client = build_client()
    store = Store(tmp_db)
    await store.init()
    pool = WorkerPool(max_concurrency=2)
    await pool.start()
    try:
        artifacts = await run_deadcode(
            task="find unused in /nonexistent/path/xyz",
            client=client,
            pool=pool,
            store=store,
            reflexion=[],
        )
    finally:
        await pool.close()
    assert artifacts == []
