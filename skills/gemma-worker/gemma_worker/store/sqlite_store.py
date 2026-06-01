from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def default_db_path() -> Path:
    base = os.environ.get("GEMMA_WORKER_STATE_DIR")
    if base:
        d = Path(base).expanduser()
    else:
        d = Path("~/.local/share/gemma-worker").expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d / "store.db"


@dataclass
class TraceRecord:
    trace_id: str
    task_id: str
    playbook: str
    started_at: float
    finished_at: float | None
    verdict: str | None
    payload: dict[str, Any]


class Store:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()

    async def init(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA wal_autocheckpoint=100")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.executescript(schema)
            # Migration: add otel_trace_id to existing spans tables that
            # predate the column. CREATE TABLE IF NOT EXISTS won't add it.
            cur = await db.execute("PRAGMA table_info(spans)")
            cols = {row[1] for row in await cur.fetchall()}
            if "otel_trace_id" not in cols:
                await db.execute("ALTER TABLE spans ADD COLUMN otel_trace_id TEXT")
            await db.commit()

    async def start_trace(self, *, trace_id: str, task_id: str, playbook: str,
                          payload: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO trace_log(trace_id, task_id, playbook, started_at, payload_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (trace_id, task_id, playbook, time.time(), json.dumps(payload, ensure_ascii=False)),
            )
            await db.commit()

    async def finish_trace(self, *, trace_id: str, verdict: str, payload: dict[str, Any]) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE trace_log SET finished_at=?, verdict=?, payload_json=? WHERE trace_id=?",
                (time.time(), verdict, json.dumps(payload, ensure_ascii=False), trace_id),
            )
            await db.commit()

    async def insert_span(self, *, span_id: str, trace_id: str, parent_span_id: str | None,
                          name: str, started_at: float, ended_at: float | None,
                          attributes: dict[str, Any], status: str | None) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO spans"
                "(span_id, trace_id, parent_span_id, name, started_at, ended_at, attributes_json, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    span_id, trace_id, parent_span_id, name, started_at, ended_at,
                    json.dumps(attributes, ensure_ascii=False), status,
                ),
            )
            await db.commit()

    async def list_spans(self, trace_id: str) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT span_id, trace_id, parent_span_id, name, started_at, ended_at, "
                "attributes_json, status FROM spans WHERE trace_id=? ORDER BY started_at",
                (trace_id,),
            )
            rows = await cur.fetchall()
        return [
            {
                "span_id": r[0],
                "trace_id": r[1],
                "parent_span_id": r[2],
                "name": r[3],
                "started_at": r[4],
                "ended_at": r[5],
                "attributes": json.loads(r[6] or "{}"),
                "status": r[7],
            }
            for r in rows
        ]

    async def get_trace(self, trace_id: str) -> TraceRecord | None:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT trace_id, task_id, playbook, started_at, finished_at, verdict, payload_json "
                "FROM trace_log WHERE trace_id=?",
                (trace_id,),
            )
            row = await cur.fetchone()
        if not row:
            return None
        return TraceRecord(
            trace_id=row[0], task_id=row[1], playbook=row[2],
            started_at=row[3], finished_at=row[4], verdict=row[5],
            payload=json.loads(row[6] or "{}"),
        )

    async def bump_retry(self, task_id: str, error: str | None, delay_s: float) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO retry_state(task_id, attempts, last_error, next_retry_at) "
                "VALUES (?, 1, ?, ?) "
                "ON CONFLICT(task_id) DO UPDATE SET "
                "  attempts = attempts + 1, "
                "  last_error = excluded.last_error, "
                "  next_retry_at = excluded.next_retry_at",
                (task_id, error, time.time() + delay_s),
            )
            await db.commit()
            cur = await db.execute(
                "SELECT attempts FROM retry_state WHERE task_id=?", (task_id,)
            )
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def log_disagreement(self, *, trace_id: str, axis: int, finding: dict[str, Any],
                               cheap_verdict: str | None, expensive_verdict: str | None,
                               tiebreaker_verdict: str | None, final: str) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO audit_disagreements"
                "(trace_id, axis, cheap_verdict, expensive_verdict, tiebreaker_verdict, "
                " final, finding_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trace_id, axis, cheap_verdict, expensive_verdict, tiebreaker_verdict,
                    final, json.dumps(finding, ensure_ascii=False), time.time(),
                ),
            )
            await db.commit()
