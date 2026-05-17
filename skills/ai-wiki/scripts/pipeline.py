#!/usr/bin/env python3
"""Pipeline orchestrator (v5, REQUIREMENTS §14 / SPEC §13.3).

Chains the 3 deterministic stages in a fixed order:
  1. ingest (optional, only if arxiv_refs provided)
  2. lint + update_index
  3. narratives (forest index regeneration)

v5 paradigm (2026-04-24) removed: enrich stage (concepts/ 廃止), project
stage (projection 消滅). User triggers explicitly — no scheduler / auto-run
(REQUIREMENTS §13.4, ALT I7).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import ingest as mod_ingest
import narrative as mod_narrative
import schema as mod_schema
from vault import Vault


def run_pipeline(
    vault: Vault,
    *,
    arxiv_refs: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the v5 pipeline and return an aggregated report."""
    started_at = datetime.now(timezone.utc).isoformat()
    stages: list[dict[str, Any]] = []
    fatal_error: str | None = None

    # --- Stage 1: ingest (optional, single arxiv refs) ---
    if arxiv_refs:
        try:
            results = []
            for ref in arxiv_refs:
                r = mod_ingest.ingest_arxiv(vault, ref, dry_run=dry_run)
                results.append(r)
            stages.append({"stage": "ingest", "ok": True, "result": {"ingested": results}})
        except Exception as e:  # noqa: BLE001
            fatal_error = f"ingest failed: {e}"
            stages.append({"stage": "ingest", "ok": False, "error": str(e)})
    else:
        stages.append({"stage": "ingest", "ok": True, "skipped": True})

    # --- Stage 2: lint + update_index (deterministic) ---
    if fatal_error is None:
        try:
            lint_result = mod_schema.lint(vault)
            mod_schema.update_index(vault)
            stages.append({"stage": "lint", "ok": True, "result": lint_result})
        except Exception as e:  # noqa: BLE001
            stages.append({"stage": "lint", "ok": False, "error": str(e)})

    # --- Stage 3: narratives (deterministic, forest index) ---
    if fatal_error is None:
        try:
            result = mod_narrative.narratives_summary(vault)
            stages.append({"stage": "narratives", "ok": True, "result": result})
        except Exception as e:  # noqa: BLE001
            stages.append({"stage": "narratives", "ok": False, "error": str(e)})

    completed_at = datetime.now(timezone.utc).isoformat()

    summary = {
        "vault_root": str(vault.root),
        "started_at": started_at,
        "completed_at": completed_at,
        "fatal_error": fatal_error,
        "stages_run": len(stages),
        "stages_ok": sum(1 for s in stages if s.get("ok", False)),
    }

    vault.append_log(
        "pipeline",
        {
            "stages_run": summary["stages_run"],
            "stages_ok": summary["stages_ok"],
            "fatal": "yes" if fatal_error else "no",
            "arxiv_refs": ",".join(arxiv_refs) if arxiv_refs else "-",
            "dry_run": dry_run,
        },
    )

    return {**summary, "stages": stages}
