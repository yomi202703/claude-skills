"""Repo scan: enumerate escalation packages + response candidates (no LLM)."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any  # noqa: F401  (used in type hints below)

# `_<name>版_` or `_<name>版.md` filename pattern. The presence of a
# "<人名>版" doc IS itself an escalation signal (it's a package prepared for an
# external party to review/decide).
_VERSION_DOC_RE = re.compile(r"_([^_/]{1,12})版[_.]")

# Directory name heuristic for meeting transcripts (substring match, case-insensitive).
_MTG_DIR_KEYWORDS = ("mtg", "meeting", "議事録", "wecom", "transcript", "minutes")


def _dir_looks_like_mtg(part: str) -> bool:
    low = part.lower()
    return any(kw in low for kw in _MTG_DIR_KEYWORDS)

# Date in filename heuristic (YYYYMMDD).
_DATE_IN_NAME_RE = re.compile(r"(20\d{6})")


def _parse_yyyymmdd(token: str) -> str | None:
    """Convert YYYYMMDD → YYYY-MM-DD if plausible date."""
    try:
        dt = datetime.strptime(token, "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def scan_escalation_packages(repo: str | Path) -> list[dict[str, Any]]:
    """Walk repo for files that look like escalation packages or MTG transcripts.

    Returns list of {path, kind, owner, date}.
    No LLM call. Pure filename / directory pattern.
    """
    repo_path = Path(repo).resolve()
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    for path in repo_path.rglob("*.md"):
        # Skip hidden dirs (.git, .loop, .claude…)
        try:
            rel_parts = path.relative_to(repo_path).parts
        except ValueError:
            continue
        if any(p.startswith(".") for p in rel_parts):
            continue

        rel = path.relative_to(repo_path).as_posix()
        if rel in seen:
            continue
        seen.add(rel)

        name = path.name
        date_match = _DATE_IN_NAME_RE.search(name)
        date_iso = _parse_yyyymmdd(date_match.group(1)) if date_match else None

        # version doc: explicit escalation package
        m = _VERSION_DOC_RE.search(name)
        if m:
            found.append({
                "path": rel,
                "kind": "version_doc",
                "owner": m.group(1).strip(),
                "date": date_iso,
            })
            continue

        # MTG transcript: ditto for meeting decisions/escalations
        if any(_dir_looks_like_mtg(part) for part in rel_parts[:-1]):
            found.append({
                "path": rel,
                "kind": "mtg_transcript",
                "owner": None,
                "date": date_iso,
            })

    # Sort newest first by date (None goes last)
    found.sort(key=lambda x: (x["date"] or "0000-00-00"), reverse=True)
    return found


def read_package_excerpt(repo: str | Path, package_path: str, *, max_chars: int = 8000) -> str:
    """Read first N chars of an escalation package. Used as LLM context."""
    p = Path(repo).resolve() / package_path
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return text[:max_chars]


_RESPONSE_KEYWORDS_RE = re.compile(
    "|".join(re.escape(k) for k in (
        "決定しました", "合意しました", "ご回答", "ご承認", "承認しました",
        "回答済", "返答済", "確認しました", "了承しました", "OKです",
        "approved", "decided", "agreed", "confirmed",
    ))
)


def scan_response_candidates(
    repo: str | Path,
    packages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find docs that may be RESPONSES to escalation packages.

    A response candidate is any .md that:
      - is dated AFTER any escalation package date
      - contains 'response language' (合意/承認/決定/ご回答/etc)

    Returns [{path, date, matched_keyword, excerpt}].
    Pure scan, no LLM.
    """
    if not packages:
        return []
    # Earliest pkg date — anything earlier can't be a response
    pkg_dates = [p["date"] for p in packages if p.get("date")]
    if not pkg_dates:
        return []
    min_pkg_date = min(pkg_dates)

    repo_path = Path(repo).resolve()
    pkg_paths = {p["path"] for p in packages}
    found: list[dict[str, Any]] = []

    for path in repo_path.rglob("*.md"):
        try:
            rel_parts = path.relative_to(repo_path).parts
        except ValueError:
            continue
        if any(p.startswith(".") for p in rel_parts):
            continue
        rel = path.relative_to(repo_path).as_posix()
        if rel in pkg_paths:
            continue  # the package itself isn't its own response

        name = path.name
        m_date = _DATE_IN_NAME_RE.search(name)
        date_iso = _parse_yyyymmdd(m_date.group(1)) if m_date else None
        if not date_iso or date_iso < min_pkg_date:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = _RESPONSE_KEYWORDS_RE.search(text)
        if not m:
            continue
        start = max(0, m.start() - 150)
        end = min(len(text), m.end() + 250)
        found.append({
            "path": rel,
            "date": date_iso,
            "matched_keyword": m.group(0),
            "excerpt": text[start:end].strip(),
        })

    found.sort(key=lambda x: x["date"], reverse=True)
    return found


__all__ = ["scan_escalation_packages", "read_package_excerpt", "scan_response_candidates"]
