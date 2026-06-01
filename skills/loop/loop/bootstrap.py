"""Initialize <repo>/.loop/ with .env + .gitignore entries.

Mirrors improver/bootstrap.py but writes to .loop/ instead of .improver/.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from improver.bootstrap import _parse_env, SKILL_ENV as IMPROVER_SKILL_ENV

GITIGNORE_LINE = ".loop/"
ENV_REQUIRED_KEYS = ("WORKER_LLM_BASE_URL", "WORKER_LLM_API_KEY", "WORKER_LLM_MODEL", "WORKER_LLM_PROVIDER")


def _ensure_env(target: Path) -> dict[str, Any]:
    # Reuse improver's skill .env as the source of truth for keys.
    if not IMPROVER_SKILL_ENV.exists():
        return {"env": "skipped", "reason": f"skill .env not found at {IMPROVER_SKILL_ENV}"}
    src = _parse_env(IMPROVER_SKILL_ENV.read_text())
    missing_in_src = [k for k in ENV_REQUIRED_KEYS if not src.get(k)]
    if missing_in_src:
        return {"env": "skipped", "reason": f"skill .env missing: {missing_in_src}"}

    # Write ONLY required keys (don't copy the entire skill .env — it may contain
    # unrelated secrets). Use plain KEY=VALUE format (no `export`) so .env-style
    # parsers that don't understand shell syntax still work.
    env_path = target / ".env"
    if not env_path.exists():
        lines = ["# Created by loop bootstrap"]
        for k in ENV_REQUIRED_KEYS:
            lines.append(f"{k}={src[k]}")
        env_path.write_text("\n".join(lines) + "\n")
        env_path.chmod(0o600)
        return {"env": {"action": "created", "path": str(env_path), "keys_added": list(ENV_REQUIRED_KEYS)}}

    existing = _parse_env(env_path.read_text())
    missing = [k for k in ENV_REQUIRED_KEYS if not existing.get(k)]
    if not missing:
        return {"env": {"action": "ok", "path": str(env_path), "keys_added": []}}

    appendix = ["", "# Added by loop bootstrap"]
    for k in missing:
        appendix.append(f"{k}={src[k]}")
    with env_path.open("a") as f:
        f.write("\n".join(appendix) + "\n")
    return {"env": {"action": "appended", "path": str(env_path), "keys_added": missing}}


def _ensure_gitignore(target: Path) -> dict[str, Any]:
    gi = target / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    if GITIGNORE_LINE in {l.strip() for l in lines}:
        return {"gitignore": {"action": "ok", "added": []}}
    new = "\n".join(lines).rstrip() + ("\n\n# loop\n" + GITIGNORE_LINE + "\n") if lines else ("# loop\n" + GITIGNORE_LINE + "\n")
    gi.write_text(new)
    return {"gitignore": {"action": "updated", "added": [GITIGNORE_LINE]}}


def _ensure_dir(target: Path) -> dict[str, Any]:
    d = target / ".loop"
    d.mkdir(exist_ok=True)
    return {"dir": str(d)}


def bootstrap_project(target: str | Path) -> dict[str, Any]:
    target = Path(target).resolve()
    if not target.is_dir():
        return {"status": "error", "error": f"not a directory: {target}"}
    out: dict[str, Any] = {"status": "ok", "target": str(target)}
    out.update(_ensure_env(target))
    out.update(_ensure_gitignore(target))
    out.update(_ensure_dir(target))
    return out
