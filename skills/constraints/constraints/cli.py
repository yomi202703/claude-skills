"""constraints CLI — scan + classify."""
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
    return _stages_dir(repo) / "constraints.json"


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
            logger.info("constraints: using cached %s entries", len(cached.get("constraints") or []))
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

    # Scan repo for escalation packages + response candidates
    from constraints.scan import scan_escalation_packages, scan_response_candidates
    packages = scan_escalation_packages(repo)
    responses = scan_response_candidates(repo, packages)
    logger.info("constraints: scanned %s escalation packages + %s response candidates",
                len(packages), len(responses))

    # One gemma call for classification
    from constraints.classify import classify_constraints
    out = await classify_constraints(repo, problems, packages, responses)
    blocked = sum(1 for c in out["constraints"] if c.get("kind"))
    logger.info("constraints: %s blocked / %s evaluated",
                blocked, len(out["constraints"]))

    _write_cache(repo, out)
    _write_outputs(repo, out)
    return out


def _write_outputs(repo: str, data: dict[str, Any]) -> Path:
    """Write .loop/constraints.json (top-level, alongside problems.json)."""
    out_path = Path(repo).resolve() / ".loop" / "constraints.json"
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _render_text(data: dict[str, Any]) -> str:
    lines = []
    cs = data.get("constraints") or []
    blocked = [c for c in cs if c.get("kind")]
    pkgs = data.get("escalation_packages_found") or []
    lines.append(f"constraints: {len(blocked)} blocked / {len(cs)} evaluated, {len(pkgs)} packages found")
    for c in blocked:
        pid = c["problem_id"][:8]
        kind = c["kind"]
        owner = c.get("owner", "?")
        since = c.get("since", "?")
        days = c.get("last_sent_days_ago")
        days_str = f" ({days}d ago)" if days is not None else ""
        doc = c.get("escalation_doc", "")
        ack = c.get("ack")
        ack_str = ("  ✓ acked" if ack is True else "  ⏳ no ack" if ack is False else "")
        lines.append(f"  [{kind}] {pid} owner={owner} since={since}{days_str}{ack_str}")
        lines.append(f"          via {doc}")
        if ack is True and c.get("ack_doc"):
            lines.append(f"          ack via {c['ack_doc']}")
        if c.get("evidence_quote"):
            lines.append(f"          quote: {c['evidence_quote'][:140]}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        prog="constraints",
        description="Escalation/blocking-constraint detector (per-problem)",
    )
    sub = parser.add_subparsers(dest="cmd")

    rn = sub.add_parser("run", help="Scan + classify (default)")
    rn.add_argument("--repo", default=".")
    rn.add_argument("--no-cache", action="store_true",
                    help="Ignore .loop/_stages/constraints.json cache")
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
