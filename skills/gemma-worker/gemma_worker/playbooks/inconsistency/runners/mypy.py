from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any

_LINE_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*(?P<severity>error|note|warning):\s*(?P<msg>.+)$")


async def run_mypy(files: list[Path]) -> list[dict[str, Any]]:
    if not shutil.which("mypy"):
        return []
    py_files = [str(p) for p in files if p.suffix == ".py"]
    if not py_files:
        return []
    proc = await asyncio.create_subprocess_exec(
        "mypy",
        "--no-error-summary",
        "--no-color-output",
        "--show-error-codes",
        "--follow-imports=silent",
        *py_files,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, _err = await proc.communicate()
    text = out.decode("utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    for raw in text.splitlines():
        m = _LINE_RE.match(raw.strip())
        if not m:
            continue
        if m.group("severity") == "note":
            continue
        msg = m.group("msg").strip()
        severity = "low"
        if "incompatible" in msg.lower() or "has no attribute" in msg.lower():
            severity = "high"
        elif "type" in msg.lower():
            severity = "medium"
        findings.append({
            "playbook": "inconsistency",
            "axis": "tool:mypy",
            "file": str(Path(m.group("file")).resolve()),
            "line": int(m.group("line")),
            "evidence": msg,
            "severity": severity,
            "why": "mypy detected type-vs-usage inconsistency",
        })
    return findings
