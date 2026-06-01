from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from gemma_worker.client.base import build_client
from gemma_worker.playbooks.critique import run as run_critique
from gemma_worker.playbooks.devils_advocate import run as run_devils_advocate
from gemma_worker.playbooks.steelman import run as run_steelman
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
def fixture_dir() -> Path:
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


def test_critique_axes_are_content_agnostic() -> None:
    """Regression: critique axes must NOT inherit the deadcode-template wording.

    The previous failure mode was that every axis-based playbook copy-pasted
    "You audit a single source file..." from deadcode, making them code-only.
    The critique playbook is the antidote — content-agnostic from day one.
    """
    axes_dir = (
        Path(__file__).parent.parent.parent
        / "gemma_worker"
        / "playbooks"
        / "critique"
        / "axes"
    )
    md_files = sorted(axes_dir.glob("axis-*.md"))
    assert len(md_files) == 5, f"expected 5 critique axes, got {len(md_files)}"
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        assert "a single source file" not in text, (
            f"{md.name} inherits deadcode-template phrasing 'a single source file' — "
            "this is the lock-in we are guarding against"
        )
        assert "a single artifact" in text, (
            f"{md.name} must open with the content-agnostic phrasing"
        )


def test_critique_axes_use_hedged_tone() -> None:
    axes_dir = (
        Path(__file__).parent.parent.parent
        / "gemma_worker"
        / "playbooks"
        / "critique"
        / "axes"
    )
    forbidden_in_instructions = ("must be wrong", "always wrong", "definitely incorrect")
    for md in sorted(axes_dir.glob("axis-*.md")):
        text = md.read_text(encoding="utf-8")
        for phrase in forbidden_in_instructions:
            assert phrase not in text.lower(), f"{md.name}: forbidden phrase '{phrase}'"


@pytest.mark.asyncio
async def test_critique_smoke(env, fixture_dir) -> None:
    client, pool, store = env
    arr = json.dumps([{
        "file": "x.py", "line": 1,
        "evidence": "the artifact assumes input is non-empty without checking",
        "severity": "medium", "why": "load-bearing precondition",
    }])
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=_mk_payload(arr))
        )
        out = await run_critique(
            task=f"critique {fixture_dir}",
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out and out[0]["playbook"] == "critique"


@pytest.mark.asyncio
async def test_devils_advocate_rebuts_prior_artifacts(env, tmp_path) -> None:
    client, pool, store = env
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({
        "artifacts": [{
            "playbook": "inconsistency",
            "axis": "docstring-vs-code",
            "file": "x.py", "line": 5,
            "evidence": "docstring says returns int, returns str",
            "severity": "medium",
            "why": "mismatch",
        }]
    }))
    rebut_payload = _mk_payload(json.dumps({
        "original_axis": "docstring-vs-code",
        "rebuttal": "the docstring is a stub; the implementation is the contract",
        "counter_strength": "moderate",
        "counter_evidence": "callers use the str return value",
    }))
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=rebut_payload)
        )
        out = await run_devils_advocate(
            task=str(prior),
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out, "devils_advocate should produce one rebuttal per finding"
    assert out[0]["playbook"] == "devils_advocate"
    assert out[0]["kind"] == "rebuttal"
    assert out[0]["rebuts_axis"] == "docstring-vs-code"
    assert "counter_strength" in out[0]


@pytest.mark.asyncio
async def test_devils_advocate_returns_empty_when_no_json(env) -> None:
    client, pool, store = env
    out = await run_devils_advocate(
        task="no .json paths here",
        client=client, pool=pool, store=store, reflexion=[],
    )
    assert out == []


@pytest.mark.asyncio
async def test_steelman_constructs_opposite_case(env, tmp_path) -> None:
    client, pool, store = env
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps([{
        "playbook": "critique",
        "axis": "axis-01-unstated-assumption",
        "file": "x.md", "line": 0,
        "evidence": "the design assumes single-tenant",
        "severity": "high",
        "why": "load-bearing",
    }]))
    steelman_payload = _mk_payload(json.dumps({
        "original_axis": "axis-01-unstated-assumption",
        "opposite_verdict": "single-tenant assumption is explicit and justified",
        "argument": (
            "The product spec defines tenant=org. Multi-tenancy is out of scope by "
            "decision. The assumption is not unstated — it is encoded in the type. "
            "Treating it as a finding misreads the scope of the artifact."
        ),
        "supporting_basis": "product spec section 2.1",
        "argument_strength": "strong",
    }))
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=steelman_payload)
        )
        out = await run_steelman(
            task=str(prior),
            client=client, pool=pool, store=store, reflexion=[],
        )
    assert out
    assert out[0]["playbook"] == "steelman"
    assert out[0]["kind"] == "steelman"
    assert out[0]["opposes_axis"] == "axis-01-unstated-assumption"
    assert out[0]["argument_strength"] == "strong"


def test_extract_artifact_paths_preserves_leading_dot(tmp_path, monkeypatch) -> None:
    """Relative paths starting with '.' (e.g. .gemma_runs/foo.json) must not
    have the leading dot stripped — str.strip is bidirectional, so the old
    `token.strip(",.;:'\"`")` ate the leading '.' and the file no longer
    resolved. See devils_advocate.run._extract_artifact_paths /
    steelman.run._extract_artifact_paths.
    """
    from gemma_worker.playbooks.devils_advocate.run import (
        _extract_artifact_paths as _ext_da,
    )
    from gemma_worker.playbooks.steelman.run import (
        _extract_artifact_paths as _ext_sm,
    )

    runs_dir = tmp_path / ".gemma_runs"
    runs_dir.mkdir()
    artifact = runs_dir / "foo.json"
    artifact.write_text("{}", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    rel = ".gemma_runs/foo.json"
    task = f"rebut findings from {rel}."  # trailing '.' must still be stripped

    for fn in (_ext_da, _ext_sm):
        paths = fn(task)
        assert paths == [artifact.resolve()], (
            f"{fn.__module__} dropped a leading-dot relative path: {paths}"
        )


def test_known_playbooks_includes_new() -> None:
    from gemma_worker.supervisor import KNOWN_PLAYBOOKS

    for name in ("critique", "devils_advocate", "steelman"):
        assert name in KNOWN_PLAYBOOKS


def test_cli_choices_includes_new() -> None:
    from gemma_worker.run import PLAYBOOKS

    for name in ("critique", "devils_advocate", "steelman"):
        assert name in PLAYBOOKS
