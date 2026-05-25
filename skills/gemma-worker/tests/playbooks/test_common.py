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


def test_extract_no_match_falls_back_to_scan_root(tmp_path, monkeypatch):
    """When the task names no paths, fall back to an implicit scan root
    (env override → git toplevel → cwd) so a bare task like
    "audit refactor" still has somewhere to scan — mirroring how
    Claude Code treats the open repo as the implicit scope.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMMA_WORKER_PROJECT_ROOT", str(tmp_path))
    targets = extract_targets_from_task("just words with no path")
    assert targets == [str(tmp_path.resolve())]


def test_extract_no_match_uses_cwd_when_no_env_or_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GEMMA_WORKER_PROJECT_ROOT", raising=False)
    # tmp_path is not a git repo, so git lookup fails → cwd fallback
    targets = extract_targets_from_task("audit something")
    assert targets == [str(tmp_path.resolve())]


def test_extract_path_with_extension():
    p = FIXTURE_REPO / "unused_module.py"
    targets = extract_targets_from_task(f"look at {p.name} relative to {FIXTURE_REPO}")
    assert any("unused_module.py" in t for t in targets) or any(
        "sample_repo" in t for t in targets
    )


def test_extract_preserves_leading_dot_in_relative_path(tmp_path, monkeypatch):
    """Regression: `./file.py` and `../file.py` must NOT have their leading
    `.` stripped. Previously `strip(",.;:'\"\\`")` ate leading dots, so
    `./SKILL.md` became `/SKILL.md` (non-existent absolute path)."""
    (tmp_path / "file.py").write_text("pass")
    monkeypatch.chdir(tmp_path)
    targets = extract_targets_from_task("audit ./file.py")
    assert any(t.endswith("./file.py") or t.endswith("file.py") for t in targets), (
        f"expected ./file.py to be preserved, got: {targets}"
    )
    files = iter_target_files(targets)
    assert files, "iter_target_files must resolve the relative path to a real file"


def test_iter_target_files_empty_for_nonexistent():
    files = iter_target_files(["/nonexistent/path/xyz"])
    assert files == []


def test_iter_target_files_includes_python():
    files = iter_target_files([str(FIXTURE_REPO)])
    assert any(p.suffix == ".py" for p in files)


def test_iter_target_files_honors_env_exclude(tmp_path, monkeypatch):
    """`GEMMA_WORKER_EXCLUDE_DIRS` lets the caller (Claude / CLI) keep
    project-specific PII / legacy dirs out of the scan stream without
    threading the value through every playbook signature.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ok.py").write_text("x = 1")
    (tmp_path / "_data").mkdir()
    (tmp_path / "_data" / "secret.py").write_text("pii = 'leak'")
    (tmp_path / "_archive").mkdir()
    (tmp_path / "_archive" / "old.py").write_text("legacy = True")

    # Without env override: archive + data are walked.
    monkeypatch.delenv("GEMMA_WORKER_EXCLUDE_DIRS", raising=False)
    files = iter_target_files([str(tmp_path)])
    names = {p.name for p in files}
    assert {"ok.py", "secret.py", "old.py"} <= names

    # With env override (comma- or colon-separated): both are excluded.
    monkeypatch.setenv("GEMMA_WORKER_EXCLUDE_DIRS", "_data,_archive")
    files = iter_target_files([str(tmp_path)])
    names = {p.name for p in files}
    assert "ok.py" in names
    assert "secret.py" not in names
    assert "old.py" not in names

    # Colon separator also works (PATH-style).
    monkeypatch.setenv("GEMMA_WORKER_EXCLUDE_DIRS", "_data:_archive")
    files = iter_target_files([str(tmp_path)])
    names = {p.name for p in files}
    assert "secret.py" not in names
