"""progress CLI — scan + classify."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _stages_dir(repo: str | Path) -> Path:
    d = Path(repo).resolve() / ".loop" / "_stages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(repo: str) -> Path:
    return _stages_dir(repo) / "progress.json"


def _read_cache(repo: str) -> dict[str, Any] | None:
    p = _cache_path(repo)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def _write_cache(repo: str, data: dict[str, Any]) -> None:
    _cache_path(repo).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def _run(repo: str, *, no_cache: bool) -> dict[str, Any]:
    from improver.env_loader import load_env
    load_env(repo)

    if not no_cache:
        cached = _read_cache(repo)
        if cached:
            logger.info("progress: using cached %s entries", len(cached.get("progress") or []))
            _write_outputs(repo, cached)
            return cached

    # Load problems.json (required)
    problems_path = Path(repo).resolve() / ".loop" / "problems.json"
    if not problems_path.is_file():
        raise FileNotFoundError(
            f"{problems_path} not found. Run `problems run --repo {repo}` first."
        )
    problems_data = json.loads(problems_path.read_text(encoding="utf-8"))
    problems = problems_data.get("problems") or []

    # Load constraints.json (optional)
    constraints_path = Path(repo).resolve() / ".loop" / "constraints.json"
    constraints: list[dict[str, Any]] | None = None
    if constraints_path.is_file():
        try:
            cd = json.loads(constraints_path.read_text(encoding="utf-8"))
            constraints = cd.get("constraints") or []
        except json.JSONDecodeError:
            logger.warning("constraints.json invalid, ignoring")

    # Scan git log + artifact dirs + decision docs
    from progress.scan import git_log, scan_artifact_dirs, scan_decision_docs
    commits = git_log(repo, n=50)
    artifacts = scan_artifact_dirs(repo)
    decision_docs = scan_decision_docs(repo)
    logger.info("progress: scanned %s commits + %s artifact dirs + %s decision docs",
                len(commits), len(artifacts), len(decision_docs))

    # One gemma call
    from progress.classify import classify_progress
    out = await classify_progress(problems, commits, artifacts, constraints, decision_docs)
    from collections import Counter
    status_counts = Counter(p["status"] for p in out["progress"])
    logger.info("progress: %s", dict(status_counts))

    _write_cache(repo, out)
    _write_outputs(repo, out)
    return out


def _write_outputs(repo: str, data: dict[str, Any]) -> Path:
    out_path = Path(repo).resolve() / ".loop" / "progress.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _render_text(data: dict[str, Any]) -> str:
    from collections import Counter
    ps = data.get("progress") or []
    counts = Counter(p["status"] for p in ps)
    lines = [f"progress: {len(ps)} problems classified — {dict(counts)}"]
    for status in ("dropped", "deferred", "pending_escalation", "superseded", "done", "undone"):
        items = [p for p in ps if p["status"] == status]
        if not items:
            continue
        lines.append(f"\n[{status}] ({len(items)})")
        for p in items[:20]:
            pid = p["problem_id"][:8]
            reason = p.get("reason", "")[:80]
            lines.append(f"  {pid} — {reason}")
        if len(items) > 20:
            lines.append(f"  ... ({len(items)-20} more)")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        prog="progress",
        description="Granular progress classifier (per-problem)",
    )
    sub = parser.add_subparsers(dest="cmd")

    rn = sub.add_parser("run", help="Scan + classify (default)")
    rn.add_argument("--repo", default=".")
    rn.add_argument("--no-cache", action="store_true",
                    help="Ignore .loop/_stages/progress.json cache")
    rn.add_argument("--output", choices=("json", "text"), default="text")

    ns = parser.parse_args(argv)
    cmd = ns.cmd or "run"

    try:
        if cmd == "run":
            try:
                data = asyncio.run(_run(ns.repo, no_cache=ns.no_cache))
            except FileNotFoundError as e:
                sys.stderr.write(f"error: {e}\n")
                return 2
            if ns.output == "json":
                json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
            else:
                sys.stdout.write(_render_text(data))
            return 0
        parser.error(f"unknown command: {cmd}")
        return 2
    except KeyboardInterrupt:
        return 130


__all__ = ["main"]
