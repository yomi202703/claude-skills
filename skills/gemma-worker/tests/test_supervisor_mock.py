from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from gemma_worker.client.base import WorkerConfig
from gemma_worker.supervisor import run_supervisor


@pytest.mark.asyncio
async def test_supervisor_end_to_end_mock(mock_env, monkeypatch, tmp_path):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    monkeypatch.setenv("GEMMA_WORKER_STATE_DIR", str(tmp_path))

    classify_payload = {
        "id": "c1", "object": "chat.completion", "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant",
                    "content": '{"playbook":"deadcode"}'}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    deadcode_payload = {
        "id": "d1", "object": "chat.completion", "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant",
                    "content": json.dumps([{
                        "file": "x.py", "line": 5, "symbol": "unused_xyz",
                        "evidence": "no callers", "severity": "high",
                        "why": "exported but unreferenced",
                    }])}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    fixture = Path(__file__).parent / "fixtures" / "sample_repo"
    call_n = {"i": 0}

    def side_effect(request):
        call_n["i"] += 1
        body = request.content.decode("utf-8")
        if "Classify the following" in body:
            return httpx.Response(200, json=classify_payload)
        if "audit a single source file" in body or "dead code" in body.lower():
            return httpx.Response(200, json=deadcode_payload)
        return httpx.Response(200, json={
            "id": "f", "object": "chat.completion", "model": "m",
            "choices": [{"index": 0, "message": {"role": "assistant",
                        "content": '{"adjustment":"none"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(side_effect=side_effect)
        result = await run_supervisor(
            task=f"find dead code in {fixture}",
            playbook="auto",
            max_iterations=1,
        )

    assert result["verdict"] in ("PROMOTE", "HOLD", "ROLLBACK")
    assert result["playbook"] == "deadcode"
    assert any(a.get("symbol") == "unused_xyz" for a in result["artifacts"])
    assert result["trace_id"]
