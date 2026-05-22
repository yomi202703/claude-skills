#!/usr/bin/env python3
"""convo-md entry point.

Auto-detects the current Claude Code session's JSONL from cwd, runs Stage 1
(deterministic) then Stage 2 (chunked parallel Haiku compression), writes a
single md.

Default output: <cwd>/claude_sessions/log_<end-time>.md. The folder is
auto-created (with a stub README) if missing. End time is the last message's
timestamp in JST (YYYY-MM-DD_HH-MM-SS), sortable in descending order = newest.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Local imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage1  # noqa: E402
import stage2  # noqa: E402
import stage3  # noqa: E402


def _candidate_dirs(cwd: Path) -> list[Path]:
    """Project-dir candidates. Claude Code replaces /, _, . with - in paths."""
    s = str(cwd.resolve())
    naive = s.replace("/", "-")
    full = naive
    for ch in ("_", "."):
        full = full.replace(ch, "-")
    names = [naive] if naive == full else [naive, full]
    return [Path.home() / ".claude" / "projects" / n for n in names]


JST = timezone(timedelta(hours=9))


def jsonl_end_label(jsonl: Path) -> str:
    """Return the JSONL's last message timestamp as `YYYY-MM-DD_HH-MM-SS` (JST).

    Falls back to the file's mtime if no timestamps are found.
    """
    last_ts: str | None = None
    try:
        with jsonl.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = rec.get("timestamp")
                if ts:
                    last_ts = ts
    except OSError:
        pass

    if last_ts:
        try:
            dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00")).astimezone(JST)
            return dt.strftime("%Y-%m-%d_%H-%M-%S")
        except ValueError:
            pass
    # Fallback to mtime.
    return datetime.fromtimestamp(jsonl.stat().st_mtime, tz=JST).strftime("%Y-%m-%d_%H-%M-%S")


def default_out_path(jsonl: Path, cwd: Path | None = None) -> Path:
    """Pick output path: always `<cwd>/claude_sessions/log_<end>.md`.

    Auto-creates `claude_sessions/` (and its README) if missing.
    """
    cwd = (cwd or Path.cwd()).resolve()
    label = jsonl_end_label(jsonl)
    sessions_dir = cwd / "claude_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    readme = sessions_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# claude_sessions/\n\n"
            "Claude Code との会話セッションのログ (要約済)。`convo-md` skill が自動生成。\n\n"
            "ファイル名: `log_<会話終了時刻 JST: YYYY-MM-DD_HH-MM-SS>.md` (降順 = 新しい順)。\n",
            encoding="utf-8",
        )
    return sessions_dir / f"log_{label}.md"


def find_current_jsonl(cwd: Path | None = None) -> Path:
    cwd = (cwd or Path.cwd()).resolve()

    # Direct hits via candidate-dir naming.
    for d in _candidate_dirs(cwd):
        if d.exists():
            jsonls = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            if jsonls:
                return jsonls[0]

    # Fallback: scan recently-modified JSONLs across all project dirs and
    # match by the `cwd` field embedded in each session's first record.
    projects_root = Path.home() / ".claude" / "projects"
    if not projects_root.exists():
        raise FileNotFoundError(f"Claude projects root not found: {projects_root}")

    target = str(cwd)
    all_jsonls: list[Path] = []
    for d in projects_root.iterdir():
        if d.is_dir():
            all_jsonls.extend(d.glob("*.jsonl"))
    all_jsonls.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for jsonl in all_jsonls[:50]:
        try:
            with jsonl.open(encoding="utf-8") as f:
                first = f.readline()
            rec = json.loads(first)
            if rec.get("cwd") == target:
                return jsonl
        except (json.JSONDecodeError, OSError):
            continue

    raise FileNotFoundError(
        f"No JSONL matches cwd={target}. Pass --jsonl <path> to override."
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Distill current Claude Code session into a handoff md.")
    ap.add_argument("--jsonl", type=Path, default=None,
                    help="path to source JSONL (default: auto-detect from cwd)")
    ap.add_argument("--out", type=Path, default=None,
                    help="output md path (default: <cwd>/claude_sessions/log_<end-time>.md, auto-created)")
    ap.add_argument("--no-stage2", action="store_true",
                    help="skip LLM compression (Stage 1 only)")
    ap.add_argument("--chunk-size", type=int, default=20)
    ap.add_argument("--overlap", type=int, default=2)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--parallelism", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--level", choices=["light", "medium", "aggressive"], default="medium",
                    help="Stage 2 圧縮レベル (default: medium)")
    ap.add_argument("--no-stage3", action="store_true",
                    help="Stage 3 (全体サマリ) を実行しない")
    args = ap.parse_args()

    # Resolve source JSONL.
    if args.jsonl:
        jsonl = args.jsonl
        if not jsonl.exists():
            print(f"error: --jsonl path does not exist: {jsonl}", file=sys.stderr)
            return 1
    else:
        try:
            jsonl = find_current_jsonl()
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1

    session_id = jsonl.stem

    # Resolve output path.
    if args.out:
        out_path = args.out
    else:
        out_path = default_out_path(jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Stage 1: write to a temp file (or directly to out_path if --no-stage2).
    if args.no_stage2:
        n_turns = stage1.write_cleaned_md(jsonl, out_path, session_id)
        result = {
            "jsonl": str(jsonl),
            "out_path": str(out_path),
            "stage": "1",
            "turns": n_turns,
            "size_bytes": out_path.stat().st_size,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        n_turns = stage1.write_cleaned_md(jsonl, tmp_path, session_id)
        stage1_size = tmp_path.stat().st_size

        s2 = stage2.run_stage2(
            tmp_path,
            out_path,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            model=args.model,
            parallelism=args.parallelism,
            timeout=args.timeout,
            level=args.level,
        )
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass

    stage2_size = out_path.stat().st_size

    # Stage 3: hierarchical overview
    s3: dict = {}
    if not args.no_stage3 and not s2.get("errors"):
        s3 = stage3.run_stage3(
            out_path,
            out_path,
            model=args.model,
            timeout=args.timeout,
        )

    result = {
        "jsonl": str(jsonl),
        "out_path": str(out_path),
        "stage": "1+2+3" if (not args.no_stage3 and s3.get("stage3") == "ok") else "1+2",
        "level": args.level,
        "turns": n_turns,
        "stage1_size_bytes": stage1_size,
        "stage2_size_bytes": stage2_size,
        "final_size_bytes": out_path.stat().st_size,
        "compression_ratio": (
            round(stage2_size / stage1_size, 3) if stage1_size else None
        ),
        "stage2": s2,
        "stage3": s3 if s3 else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if s2.get("errors") or s3.get("stage3") == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
