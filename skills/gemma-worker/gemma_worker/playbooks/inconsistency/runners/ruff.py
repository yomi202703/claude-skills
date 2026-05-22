from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any


async def run_ruff(files: list[Path]) -> list[dict[str, Any]]:
    if not shutil.which("ruff"):
        return []
    py_files = [str(p) for p in files if p.suffix == ".py"]
    if not py_files:
        return []
    proc = await asyncio.create_subprocess_exec(
        "ruff", "check", "--output-format", "json",
        "--select", "D,N,RET,RUF",
        *py_files,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _err = await proc.communicate()
    text = out.decode("utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    findings: list[dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        code = item.get("code", "")
        message = item.get("message", "")
        loc = (item.get("location") or {})
        findings.append({
            "playbook": "inconsistency",
            "axis": f"tool:ruff:{code}",
            "file": item.get("filename", ""),
            "line": int(loc.get("row", 0) or 0),
            "evidence": f"{code}: {message}",
            "severity": "low",
            "why": "ruff detected style/doc/naming inconsistency",
        })
    return findings
