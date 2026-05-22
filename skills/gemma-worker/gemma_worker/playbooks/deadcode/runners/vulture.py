from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any


async def run_vulture(files: list[Path]) -> list[dict[str, Any]]:
    if not shutil.which("vulture"):
        return []
    py_files = [str(p) for p in files if p.suffix == ".py"]
    if not py_files:
        return []
    proc = await asyncio.create_subprocess_exec(
        "vulture", "--min-confidence", "60", *py_files,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _err = await proc.communicate()
    text = out.decode("utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip() or ":" not in line:
            continue
        try:
            path_part, rest = line.split(":", 1)
            line_no_str, message = rest.split(":", 1)
            line_no = int(line_no_str)
        except ValueError:
            continue
        msg = message.strip()
        severity = "low"
        if "unused function" in msg or "unused class" in msg:
            severity = "medium"
        if "unreachable code" in msg or "unused import" in msg:
            severity = "high"
        findings.append({
            "playbook": "deadcode",
            "axis": "tool:vulture",
            "file": str(Path(path_part).resolve()),
            "line": line_no,
            "symbol": msg.split(" ", 2)[-1] if " " in msg else msg,
            "evidence": msg,
            "severity": severity,
            "why": "vulture detected",
        })
    return findings
