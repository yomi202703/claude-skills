from __future__ import annotations

from pathlib import Path

from gemma_worker.playbooks._common import (
    extract_targets_from_task,
    iter_target_files,
)

FIXTURE_REPO = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def test_extract_absolute_path():
    targets = extract_targets_from_task(f"scan {FIXTURE_REPO}")
    assert any(str(FIXTURE_REPO) in t for t in targets)


def test_extract_relative_path_from_cwd(monkeypatch):
    monkeypatch.chdir(FIXTURE_REPO.parent.parent.parent)
    targets = extract_targets_from_task("scan tests/fixtures/sample_repo")
    assert targets, "relative path with / should be picked up"
    assert any("sample_repo" in t for t in targets)


def test_extract_no_match_returns_empty():
    targets = extract_targets_from_task("just words with no path")
    assert targets == []


def test_extract_path_with_extension():
    p = FIXTURE_REPO / "unused_module.py"
    targets = extract_targets_from_task(f"look at {p.name} relative to {FIXTURE_REPO}")
    assert any("unused_module.py" in t for t in targets) or any(
        "sample_repo" in t for t in targets
    )


def test_iter_target_files_empty_for_nonexistent():
    files = iter_target_files(["/nonexistent/path/xyz"])
    assert files == []


def test_iter_target_files_includes_python():
    files = iter_target_files([str(FIXTURE_REPO)])
    assert any(p.suffix == ".py" for p in files)
