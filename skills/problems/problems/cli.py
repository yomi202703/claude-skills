from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("problems")


STAGES = ("extract", "consolidate", "verify", "analyze")
# Map stage to its cache filename
_STAGE_CACHE = {
    "extract": "extract.json",
    "consolidate": "consolidate.json",
    "verify": "verify.json",
    "analyze": "analyze.json",
}


def _stages_dir(repo: str | Path) -> Path:
    d = Path(repo).resolve() / ".loop" / "_stages"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_cache(repo: str, stage: str) -> dict[str, Any] | None:
    p = _stages_dir(repo) / _STAGE_CACHE[stage]
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(repo: str, stage: str, data: dict[str, Any]) -> Path:
    p = _stages_dir(repo) / _STAGE_CACHE[stage]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


async def _ensure_extract(repo: str, *, no_cache: bool) -> dict[str, Any]:
    if not no_cache:
        cached = _read_cache(repo, "extract")
        if cached:
            logger.info("extract: using cached %s events", len((cached.get('events') or [])))
            return cached
    from problems.extract import extract_all, serialize
    res = await extract_all(repo)
    out = serialize(res)
    _write_cache(repo, "extract", out)
    return out


async def _ensure_consolidate(repo: str, *, no_cache: bool) -> dict[str, Any]:
    if not no_cache:
        cached = _read_cache(repo, "consolidate")
        if cached:
            logger.info("consolidate: using cached %s problems",
                        len(cached.get("problems") or []))
            return cached
    extract_data = await _ensure_extract(repo, no_cache=no_cache)
    from problems.consolidate import consolidate
    out = await consolidate(extract_data.get("events") or [])
    _write_cache(repo, "consolidate", out)
    return out


async def _ensure_verify(repo: str, *, no_cache: bool) -> dict[str, Any]:
    if not no_cache:
        cached = _read_cache(repo, "verify")
        if cached:
            return cached
    b_out = await _ensure_consolidate(repo, no_cache=no_cache)
    from problems.verify import verify
    out = await verify(repo, b_out)
    _write_cache(repo, "verify", out)
    return out


async def _ensure_analyze(repo: str, *, no_cache: bool) -> dict[str, Any]:
    if not no_cache:
        cached = _read_cache(repo, "analyze")
        if cached:
            return cached
    c_out = await _ensure_verify(repo, no_cache=no_cache)
    from problems.analyze import analyze
    out = await analyze(c_out)
    _write_cache(repo, "analyze", out)
    return out


_STAGE_RUNNERS = {
    "extract": _ensure_extract,
    "consolidate": _ensure_consolidate,
    "verify": _ensure_verify,
    "analyze": _ensure_analyze,
}


async def _run(repo: str, *, stage: str, no_cache: bool) -> dict[str, Any]:
    # Auto-load .env so WORKER_LLM_* propagates
    from improver.env_loader import load_env
    load_env(repo)

    runner = _STAGE_RUNNERS[stage]
    result = await runner(repo, no_cache=no_cache)
    return result


def _write_outputs(repo: str, data: dict[str, Any]) -> tuple[Path, Path]:
    """Write .loop/problems.json + problems.md (only when full pipeline)."""
    from problems.render import render_markdown
    out_dir = Path(repo).resolve() / ".loop"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "problems.json"
    md_path = out_dir / "problems.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(data), encoding="utf-8")
    return md_path, json_path


def _bootstrap(repo: str) -> dict[str, Any]:
    """Minimal bootstrap: reuse loop's pattern (.loop/ dir + .env + .gitignore)."""
    from loop.bootstrap import bootstrap_project  # type: ignore
    return bootstrap_project(repo)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="problems", description="Per-problem timeline extractor (4-gemma pipeline)")
    sub = parser.add_subparsers(dest="cmd")

    bs = sub.add_parser("bootstrap", help="Initialize <repo>/.loop/ (via loop bootstrap)")
    bs.add_argument("--repo", default=".")

    rn = sub.add_parser("run", help="Run pipeline (default: full = analyze stage)")
    rn.add_argument("--repo", default=".")
    rn.add_argument("--stage", choices=STAGES, default="analyze",
                    help="Stop after this stage. default=analyze (full pipeline)")
    rn.add_argument("--no-cache", action="store_true", help="Ignore .loop/_stages/ cache")
    rn.add_argument("--output", choices=("json", "text"), default="text")

    ns = parser.parse_args(argv)
    cmd = ns.cmd or "run"

    try:
        if cmd == "bootstrap":
            try:
                result = _bootstrap(ns.repo)
            except ImportError:
                # loop skill not installed; do a minimal bootstrap inline
                from pathlib import Path as _P
                d = _P(ns.repo).resolve() / ".loop"
                d.mkdir(exist_ok=True)
                result = {"status": "ok", "dir": str(d), "note": "minimal bootstrap (loop skill not available)"}
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if cmd != "run":
            parser.error(f"unknown command: {cmd}")
            return 2

        data = asyncio.run(_run(ns.repo, stage=ns.stage, no_cache=ns.no_cache))

        # Write final outputs only after full pipeline (analyze stage)
        if ns.stage == "analyze":
            md_path, json_path = _write_outputs(ns.repo, data)
            wrote = f"\n--- written: {md_path} / {json_path}"
        else:
            wrote = f"\n--- stage cache: .loop/_stages/{_STAGE_CACHE[ns.stage]}"

        if ns.output == "json":
            json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        else:
            # Brief text summary
            if ns.stage == "extract":
                ev = data.get("events") or []
                errs = data.get("errors") or []
                sys.stdout.write(f"extract: {len(ev)} events ({sum(1 for e in ev if e.get('lens')=='progress')} progress, "
                                 f"{sum(1 for e in ev if e.get('lens')=='problem')} problem) "
                                 f"from {data.get('docs_scanned', 0)} docs, {len(errs)} errors\n")
            elif ns.stage in ("consolidate", "verify", "analyze"):
                problems = data.get("problems") or []
                stats = data.get("stats") or {}
                open_n = sum(1 for p in problems if p.get("latest_state") == "open")
                res_n = sum(1 for p in problems if p.get("latest_state") == "resolved")
                disc_n = sum(1 for p in problems if p.get("latest_state") == "discrepancy")
                sys.stdout.write(f"{ns.stage}: {len(problems)} problems "
                                 f"({open_n} open, {res_n} resolved, {disc_n} discrepancy), "
                                 f"{stats.get('unclassified', 0)} unclassified events\n")
                # show top 5 titles
                for p in problems[:5]:
                    state = p.get("latest_state", "?")
                    sys.stdout.write(f"  [{state}] {p.get('problem_id','?')} {p.get('title','')[:80]}\n")
                if len(problems) > 5:
                    sys.stdout.write(f"  ... ({len(problems)-5} more)\n")
            sys.stdout.write(wrote + "\n")
        return 0
    except KeyboardInterrupt:
        return 130
