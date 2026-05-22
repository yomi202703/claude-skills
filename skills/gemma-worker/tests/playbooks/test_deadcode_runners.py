from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gemma_worker.playbooks.deadcode.runners.ts_prune import run_ts_prune
from gemma_worker.playbooks.deadcode.runners.vulture import run_vulture


FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "sample_repo"


@pytest.mark.asyncio
async def test_vulture_skips_when_no_python_files():
    out = await run_vulture([])
    assert out == []


@pytest.mark.asyncio
async def test_ts_prune_skips_when_no_ts_files():
    out = await run_ts_prune([])
    assert out == []


@pytest.mark.skipif(not shutil.which("vulture"), reason="vulture not installed")
@pytest.mark.asyncio
async def test_vulture_finds_unused_in_fixture():
    files = list(FIXTURE_REPO.rglob("*.py"))
    assert files
    out = await run_vulture(files)
    symbols = [item.get("symbol", "") for item in out]
    assert any("unused_orphan_xyz" in s for s in symbols), (
        f"expected vulture to flag unused_orphan_xyz, got: {symbols}"
    )
    for item in out:
        assert item["playbook"] == "deadcode"
        assert item["axis"] == "tool:vulture"
        assert item["severity"] in {"high", "medium", "low"}
