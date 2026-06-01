"""Repo scan: git log + artifact dirs + decision-language docs. No LLM."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

# Doc-level signal keywords for status decisions.
_DECISION_KEYWORDS = (
    "優先度を下げ", "優先度下げ", "後回し", "保留", "対象外", "やらない",
    "棄却", "廃止", "次フェーズ", "現時点では着手しない",
    "次回 MTG", "次回MTG", "要件定義打合せでご相談",
    "確定した要件定義の最優先論点",
    "v1 → v2", "に代わって", "に置き換え",
    "実装完了", "完成", "完了済", "✓ resolved",
)
_DECISION_RE = re.compile("|".join(re.escape(k) for k in _DECISION_KEYWORDS))
_DATE_IN_NAME_RE = re.compile(r"(20\d{6})")

# Conventional artifact dir names. If a problem references a path that's
# inside one of these, that's a strong "done" signal (output exists).
_ARTIFACT_DIR_NAMES = (
    "outputs", "output", "dist", "build", "target",
    "成果物", "results", "result", "released",
)


def git_log(repo: str | Path, *, n: int = 50) -> list[dict[str, str]]:
    """Return last N commits as [{hash, date, subject}]. Empty if not a git repo."""
    if shutil.which("git") is None:
        return []
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "log", f"-n{n}",
             "--pretty=format:%h\t%ad\t%s", "--date=short"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if res.returncode != 0:
        return []
    out: list[dict[str, str]] = []
    for line in (res.stdout or "").splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            out.append({"hash": parts[0], "date": parts[1], "subject": parts[2][:200]})
    return out


def scan_artifact_dirs(repo: str | Path) -> list[str]:
    """Find directories that look like build/output artifact stores. Returns
    repo-relative paths (no recursion into them — just existence)."""
    repo_path = Path(repo).resolve()
    found: list[str] = []
    for root in repo_path.rglob("*"):
        if not root.is_dir():
            continue
        try:
            rel_parts = root.relative_to(repo_path).parts
        except ValueError:
            continue
        if any(p.startswith(".") for p in rel_parts):
            continue
        if root.name in _ARTIFACT_DIR_NAMES:
            # Only count if non-empty (has at least one file inside)
            try:
                has_file = any(p.is_file() for p in root.iterdir())
            except OSError:
                continue
            if has_file:
                found.append(root.relative_to(repo_path).as_posix())
    return sorted(found)


def scan_decision_docs(repo: str | Path, *, max_docs: int = 20) -> list[dict[str, str]]:
    """Find .md docs that contain decision-language keywords. Returns
    [{path, date, excerpt}] with the FIRST matching window (±200 chars around hit).

    Used as LLM context to detect dropped/pending_escalation/superseded statuses.
    """
    repo_path = Path(repo).resolve()
    found: list[dict[str, str]] = []
    for path in repo_path.rglob("*.md"):
        try:
            rel_parts = path.relative_to(repo_path).parts
        except ValueError:
            continue
        if any(p.startswith(".") for p in rel_parts):
            continue
        rel = path.relative_to(repo_path).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = _DECISION_RE.search(text)
        if not m:
            continue
        # ±400 char excerpt window around the first hit
        start = max(0, m.start() - 200)
        end = min(len(text), m.end() + 400)
        excerpt = text[start:end].strip()
        date_match = _DATE_IN_NAME_RE.search(path.name)
        date = None
        if date_match:
            try:
                from datetime import datetime as _dt
                date = _dt.strptime(date_match.group(1), "%Y%m%d").strftime("%Y-%m-%d")
            except ValueError:
                date = None
        found.append({
            "path": rel,
            "date": date or "",
            "matched_keyword": m.group(0),
            "excerpt": excerpt,
        })
    # Newest first (by filename date) then cap
    found.sort(key=lambda x: x.get("date") or "0000-00-00", reverse=True)
    return found[:max_docs]


__all__ = ["git_log", "scan_artifact_dirs", "scan_decision_docs"]
