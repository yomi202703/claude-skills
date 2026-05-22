from __future__ import annotations

import pytest

from gemma_worker.store.sqlite_store import Store


@pytest.mark.asyncio
async def test_init_creates_tables(tmp_db):
    store = Store(tmp_db)
    await store.init()
    assert tmp_db.exists()


@pytest.mark.asyncio
async def test_trace_roundtrip(tmp_db):
    store = Store(tmp_db)
    await store.init()
    await store.start_trace(
        trace_id="t1", task_id="task-a", playbook="deadcode",
        payload={"task": "find unused"},
    )
    rec = await store.get_trace("t1")
    assert rec is not None
    assert rec.task_id == "task-a"
    assert rec.playbook == "deadcode"
    assert rec.verdict is None

    await store.finish_trace(
        trace_id="t1", verdict="PROMOTE",
        payload={"task": "find unused", "result": "ok"},
    )
    rec2 = await store.get_trace("t1")
    assert rec2 is not None
    assert rec2.verdict == "PROMOTE"
    assert rec2.payload["result"] == "ok"
    assert rec2.finished_at is not None


@pytest.mark.asyncio
async def test_span_insert_and_list(tmp_db):
    store = Store(tmp_db)
    await store.init()
    await store.insert_span(
        span_id="s1", trace_id="t1", parent_span_id=None,
        name="root", started_at=1.0, ended_at=2.0,
        attributes={"gen_ai.system": "gemma"}, status="OK",
    )
    await store.insert_span(
        span_id="s2", trace_id="t1", parent_span_id="s1",
        name="gemma.chat", started_at=1.1, ended_at=1.9,
        attributes={"gen_ai.request.model": "gemma-test"}, status="OK",
    )
    spans = await store.list_spans("t1")
    assert [s["span_id"] for s in spans] == ["s1", "s2"]
    assert spans[1]["attributes"]["gen_ai.request.model"] == "gemma-test"


@pytest.mark.asyncio
async def test_retry_increments(tmp_db):
    store = Store(tmp_db)
    await store.init()
    a1 = await store.bump_retry("task-x", "boom", delay_s=1.0)
    a2 = await store.bump_retry("task-x", "boom", delay_s=2.0)
    a3 = await store.bump_retry("task-x", "boom2", delay_s=4.0)
    assert (a1, a2, a3) == (1, 2, 3)


@pytest.mark.asyncio
async def test_log_disagreement(tmp_db):
    store = Store(tmp_db)
    await store.init()
    await store.log_disagreement(
        trace_id="t1", axis=5,
        finding={"file": "x.py", "line": 1, "evidence": "...", "severity": "high", "why": "..."},
        cheap_verdict="valid", expensive_verdict="invalid",
        tiebreaker_verdict="valid", final="valid",
    )
