"""loop CLI — bootstrap + synthesize only.

Orchestration of `problems` and `gemma-worker` is now Claude Code's job
(see SKILL.md). This CLI just:
  - bootstrap: initialize <repo>/.loop/ + .env + .gitignore
  - synthesize: read .loop/problems.json + .loop/code_audit.json (optional)
    and produce briefing.{md,json}
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


async def _run_synthesize(repo: str) -> dict[str, Any]:
    from improver.env_loader import load_env
    load_env(repo)
    from loop.synthesize import synthesize_from_files
    return await synthesize_from_files(repo)


def _render_markdown(briefing: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(f"# Project Briefing")
    parts.append(f"_generated {briefing.get('generated_at','?')}_")
    parts.append("")
    if briefing.get("headline"):
        parts.append(f"**Headline**: {briefing['headline']}")
        parts.append("")
    parts.append("## 現状ナラティブ")
    parts.append(briefing.get("narrative", "_(empty)_"))
    parts.append("")

    drill = briefing.get("drill_notes")
    if drill:
        parts.append("## Drill-down findings (Claude Code, 一次資料 verbatim)")
        parts.append(drill)
        parts.append("")

    ps = briefing.get("progress") or []
    if ps:
        from collections import Counter
        counts = Counter(p["status"] for p in ps)
        parts.append(f"## 📊 Progress breakdown ({len(ps)} problems)")
        parts.append("_From `/progress` skill — granular over open/resolved._")
        parts.append("| status | count |")
        parts.append("|---|---:|")
        for status in ("done", "undone", "deferred", "dropped", "superseded", "pending_escalation"):
            n = counts.get(status, 0)
            if n:
                parts.append(f"| {status} | {n} |")
        for status in ("dropped", "deferred", "pending_escalation", "superseded"):
            items = [p for p in ps if p["status"] == status]
            if not items:
                continue
            parts.append(f"\n**{status}** ({len(items)}):")
            for p in items[:10]:
                pid = p["problem_id"][:8]
                reason = (p.get("reason") or "")[:120]
                parts.append(f"- `[{pid}]` {reason}")
            if len(items) > 10:
                parts.append(f"  _(... {len(items)-10} more)_")
        parts.append("")

    cs = briefing.get("constraints") or []
    blocked = [c for c in cs if c.get("kind")]
    if blocked:
        parts.append(f"## 🚧 Blocking constraints ({len(blocked)})")
        parts.append("_From `/constraints` skill — escalations awaiting external response._")
        for c in blocked:
            pid = c.get("problem_id", "?")[:8]
            kind = c.get("kind", "?")
            owner = c.get("owner", "?")
            since = c.get("since", "?")
            days = c.get("last_sent_days_ago")
            days_str = f" — **{days}d ago**" if days is not None else ""
            ack = c.get("ack")
            ack_badge = "  ✓ ack" if ack is True else ("  ⏳ no ack" if ack is False else "")
            doc = c.get("escalation_doc", "")
            parts.append(f"- `[{pid}]` **{kind}** (owner={owner}, since={since}){days_str}{ack_badge}")
            parts.append(f"  - via `{doc}`")
            if ack is True and c.get("ack_doc"):
                parts.append(f"  - **acked via** `{c['ack_doc']}`")
            if c.get("evidence_quote"):
                parts.append(f"  - > {c['evidence_quote'][:160]}")
        parts.append("")

    problems = briefing.get("problems") or []
    open_p = [p for p in problems if p.get("latest_state") == "open"]
    disc_p = [p for p in problems if p.get("latest_state") == "discrepancy"]
    res_p = [p for p in problems if p.get("latest_state") == "resolved"]

    parts.append(
        f"## Problems ({len(problems)} total: {len(open_p)} open, "
        f"{len(disc_p)} discrepancy, {len(res_p)} resolved)"
    )
    parts.append("_For full timelines and code evidence, see `.loop/problems.md`._")
    parts.append("")

    def _section(label: str, items: list[dict[str, Any]], badge: str) -> None:
        if not items:
            return
        parts.append(f"### {badge} {label} ({len(items)})")
        for p in items[:20]:
            pid = p.get("problem_id", "?")
            title = p.get("title", "")
            summary = (p.get("latest_summary") or "").strip()
            tl = p.get("timeline") or []
            last_date = (tl[-1].get("date") or "?")[:10] if tl else "?"
            parts.append(f"- `[{pid}]` **{title}** — latest {last_date}")
            if summary:
                parts.append(f"  - {summary}")
        if len(items) > 20:
            parts.append(f"  _(... {len(items)-20} more, see problems.md)_")
        parts.append("")

    _section("Discrepancy", disc_p, "⚠️")
    _section("Open", open_p, "🔴")
    _section("Recently resolved", res_p, "✅")

    audit_findings = briefing.get("code_audit_findings") or []
    if audit_findings:
        parts.append(f"## Code audit findings ({len(audit_findings)})")
        for f in audit_findings[:15]:
            file_ = f.get("file") or f.get("path") or ""
            line_ = f.get("line")
            loc = f"{file_}:{line_}" if (file_ and line_) else file_
            why = (f.get("why") or f.get("evidence") or f.get("message") or "").strip()[:200]
            kind = f.get("kind") or f.get("playbook") or "audit"
            parts.append(f"- `{loc}` [{kind}] {why}")
        if len(audit_findings) > 15:
            parts.append(f"  _(... {len(audit_findings)-15} more)_")
        parts.append("")

    ev = briefing.get("evidence_table") or []
    if ev:
        parts.append(f"## Evidence table ({len(ev)})")
        for e in ev[:30]:
            parts.append(f"- `{e['id']}` {e.get('snippet','')}")
        if len(ev) > 30:
            parts.append(f"_(... {len(ev)-30} more)_")
    return "\n".join(parts) + "\n"


def _write_outputs(repo: str, briefing: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = Path(repo).resolve() / ".loop"
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / "briefing.json"
    md_path = out_dir / "briefing.md"
    json_path.write_text(json.dumps(briefing, ensure_ascii=False, indent=2))
    md_path.write_text(_render_markdown(briefing))
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="loop",
        description="loop — bootstrap + synthesize. Orchestration of problems / gemma-worker is Claude Code's job (see SKILL.md).",
    )
    sub = parser.add_subparsers(dest="cmd")

    bs = sub.add_parser("bootstrap", help="Initialize <repo>/.loop/ + .env + .gitignore")
    bs.add_argument("--repo", default=".")

    syn = sub.add_parser(
        "synthesize",
        help="Read .loop/problems.json (+ optional .loop/code_audit.json) and write briefing.{md,json}",
    )
    syn.add_argument("--repo", default=".")
    syn.add_argument("--output", choices=("json", "text"), default="text")

    ns = parser.parse_args(argv)
    cmd = ns.cmd
    if cmd is None:
        parser.print_help()
        return 2

    try:
        if cmd == "bootstrap":
            from loop.bootstrap import bootstrap_project
            result = bootstrap_project(ns.repo)
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if cmd == "synthesize":
            try:
                briefing = asyncio.run(_run_synthesize(ns.repo))
            except FileNotFoundError as e:
                sys.stderr.write(f"error: {e}\n")
                return 2
            md_path, json_path = _write_outputs(ns.repo, briefing)
            if ns.output == "json":
                json.dump(briefing, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
            else:
                sys.stdout.write(_render_markdown(briefing))
                sys.stdout.write(f"\n--- written: {md_path} / {json_path}\n")
            return 0

        parser.error(f"unknown command: {cmd}")
        return 2
    except KeyboardInterrupt:
        return 130
