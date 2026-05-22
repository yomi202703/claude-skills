from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any


async def run_ts_prune(files: list[Path]) -> list[dict[str, Any]]:
    if not shutil.which("ts-prune"):
        return []
    ts_files = [p for p in files if p.suffix in {".ts", ".tsx", ".js", ".jsx"}]
    if not ts_files:
        return []
    root = ts_files[0].parents[0]
    while root != root.parent and not (root / "tsconfig.json").exists() and not (root / "package.json").exists():
        root = root.parent
    proc = await asyncio.create_subprocess_exec(
        "ts-prune",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        cwd=str(root),
    )
    out, _err = await proc.communicate()
    text = out.decode("utf-8", errors="replace")
    target_paths = {str(p.resolve()) for p in ts_files}
    findings: list[dict[str, Any]] = []
    for line in text.splitlines():
        if " - " not in line or ":" not in line:
            continue
        path_with_line, symbol = line.rsplit(" - ", 1)
        try:
            path_str, line_no_str = path_with_line.rsplit(":", 1)
            line_no = int(line_no_str)
        except ValueError:
            continue
        abs_path = str((root / path_str).resolve())
        if abs_path not in target_paths:
            continue
        findings.append({
            "playbook": "deadcode",
            "axis": "tool:ts-prune",
            "file": abs_path,
            "line": line_no,
            "symbol": symbol.strip(),
            "evidence": line.strip(),
            "severity": "medium",
            "why": "ts-prune detected unused export",
        })
    return findings
