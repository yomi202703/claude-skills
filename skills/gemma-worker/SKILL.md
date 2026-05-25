---
name: gemma-worker
description: Heavy enumeration / analysis / synthesis を OpenAI 互換エンドポイントの OSS LLM に委譲。9 playbook (deadcode / inconsistency / gap / research / optimization / synthesis / critique / devils_advocate / steelman) を LangGraph で並列実行し、5 次元品質を測って PROMOTE / HOLD / ROLLBACK verdict を返す。リポジトリ全体スキャンや大量並列調査向け。単発の判断・対話には呼ばない。対象はコード中心 — prose/markdown 対応は `synthesis` と `critique`、cross-file 比較は `synthesis`、prior-artifact 入力は `devils_advocate` / `steelman`。
---

# gemma-worker

## When to invoke

- Repository-wide search / analysis / synthesis tasks
- Anything you'd otherwise loop on yourself with many similar LLM calls
- Tasks where a quality verdict (PROMOTE / HOLD / ROLLBACK) is desired

## When NOT to invoke

- Single-shot decisions you can answer yourself
- Tasks requiring browsing or interactive user dialogue
- Anything where the worker LLM (mid-size OSS) is clearly insufficient — that
  should stay on Claude Code itself

## Playbooks

Most file-based playbooks scan **one source file at a time** with code-oriented
axes — they do not detect cross-file drift. `synthesis` crosses files;
`critique` accepts both code and prose; `devils_advocate` / `steelman`
consume prior-run JSON artifacts.

| playbook        | scope       | content target  | finding kind                                       |
|-----------------|-------------|-----------------|----------------------------------------------------|
| `deadcode`      | intra-file  | code only       | unused exports, unreferenced helpers, dead branches |
| `inconsistency` | intra-file  | code only       | docstring↔code, type↔usage, name↔behavior          |
| `gap`           | intra-file  | code only       | missing error handling / tests / edge cases        |
| `optimization`  | intra-file  | code only       | quadratic loops, redundant I/O, wasted allocations |
| `research`      | task-only   | n/a             | escalation hand-off (worker can't browse the web)  |
| `synthesis`     | cross-file  | any (incl .md)  | per-file summaries + top-5 global themes (2-tier if >10 files) |
| `critique`      | intra-file  | any (code+prose) | unstated assumptions, reasoning leaps, alt framings, tradeoff blindspots, scope mismatches |
| `devils_advocate` | derived (prior `.json` artifacts) | n/a | asymmetric counter-evidence against existing findings |
| `steelman`      | derived (prior `.json` artifacts) | n/a | strongest case for the opposite verdict (~2x cost vs DA) |

**Picking a playbook**:
- Cross-file consistency of prompt docs, configs, or other `.md` → `synthesis`
  (read its `global_theme` artifacts).
- Per-file code audit → match by finding kind above.
- Abstract / reference-level critique of either code or prose → `critique`.
- Layered review (after Layer A runs): `devils_advocate` rebuts findings,
  `steelman` argues the opposite verdict. Both consume the prior run's JSON.
- Mismatched scope/content (e.g. `inconsistency` on `.md`) returns 0 findings
  and forces `ROLLBACK`. Pick again rather than retrying.

## Configuration

The skill reads the following environment variables. Set them once in your
shell (or in `.env` sourced by your invocation context).

```
WORKER_LLM_BASE_URL    OpenAI-compatible endpoint URL
WORKER_LLM_API_KEY     API key (use 'sk-noop' for local Ollama)
WORKER_LLM_MODEL       Model id (e.g. gemma-4-31B-it, qwen2.5-coder:32b)
WORKER_LLM_PROVIDER    gemma | openai | anthropic | ollama | vllm
```

The provider name selects an adapter under `gemma_worker/client/providers/`
that handles model-specific quirks (system-role merge for Gemma, JSON
continuation prefix, etc.).

## Entrypoint

```
uv run --project ~/.claude/skills/gemma-worker \
  python -m gemma_worker.run "<task>" \
  --playbook <deadcode|inconsistency|gap|research|optimization|synthesis|critique|devils_advocate|steelman|auto> \
  --output json
```

`--playbook auto` lets the supervisor classify and pick the playbook.

### Scan scope

The task string can name explicit paths (anything that looks like a path
and exists on disk is picked up — relative or absolute). If the task names
no paths, the worker falls back to an implicit scan root, in order:

1. `$GEMMA_WORKER_PROJECT_ROOT` (if set and exists)
2. `git rev-parse --show-toplevel` (from `cwd`)
3. `cwd`

This means a bare task like `"audit refactor consistency"` invoked from
inside a project is enough — there is no need to enumerate paths in the
task string. To override, either pass paths inline or set
`GEMMA_WORKER_PROJECT_ROOT` in the environment.

### Excluding directories (PII / legacy / generated)

The built-in excludes cover dependency / build / cache / VCS dirs
(`.venv`, `node_modules`, `__pycache__`, `dist`, `build`, `.git`, ...).
**Project-specific dirs that hold PII, legacy archives, or generated
artifacts must be passed explicitly** — the worker has no way to infer
project conventions on its own. Two equivalent surfaces:

- `--exclude-dirs _data,_archive,outputs` (CLI flag)
- `GEMMA_WORKER_EXCLUDE_DIRS=_data:_archive:outputs` (env var)

Caller responsibility: before invoking the worker, read the project's
`CLAUDE.md` / `.gitignore` for the "do not touch" list and pass those
names. Customer data and personal information in particular must be
excluded by name; the worker has no PII detector.

## Output schema

```json
{
  "verdict": "PROMOTE" | "HOLD" | "ROLLBACK",
  "metrics": {
    "task_success": 0.0-1.0,
    "context_preservation": 0.0-1.0,
    "p95_latency_ms": int,
    "safety_pass_rate": 0.0-1.0,
    "evidence_coverage": 0.0-1.0,
    "axis_05_violations": int,
    "axis_06_violations": int
  },
  "artifacts": [ ... playbook-specific findings ... ],
  "trace_id": "...",
  "audit": {
    "axes_1_to_4": [ {file, line, axis, severity, evidence, why}, ... ],
    "axes_5_to_6": [ ... ]
  }
}
```

## What you (Claude Code) should NOT do

- Re-invoke the skill on the same task to "retry" — retries happen internally
- Pass already-processed results back in
- Skip reviewing `artifacts` — you are still the final judge
- Treat PROMOTE as "automatically merge" — it's a quality signal, not authority
