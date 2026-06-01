# gemma-worker

Provider-agnostic LLM worker orchestrator. Claude Code (CEO) delegates heavy enumeration / analysis / synthesis tasks here. The skill routes the request to one of six playbooks, runs them via LangGraph + an async queue against any OpenAI-compatible endpoint, traces every call with OpenTelemetry, measures five quality dimensions, integrates `ai-pipeline-audit`, and returns a `PROMOTE` / `HOLD` / `ROLLBACK` verdict.

## Quick start

```
export WORKER_LLM_BASE_URL=https://your-endpoint.example.com/v1
export WORKER_LLM_API_KEY=sk-...
export WORKER_LLM_MODEL=gemma-4-31B-it
export WORKER_LLM_PROVIDER=gemma

uv run --project ~/.claude/skills/gemma-worker \
  python -m gemma_worker.run \
  "find unused exports in /path/to/repo" \
  --playbook auto --output json
```

`WORKER_LLM_PROVIDER` selects an adapter under `gemma_worker/client/providers/`:

| provider    | endpoints                          | system role handling          |
|-------------|------------------------------------|-------------------------------|
| `gemma`     | any OpenAI-compatible host serving Gemma | merged into the user message  |
| `openai`    | api.openai.com, Azure OpenAI       | native                        |
| `anthropic` | Anthropic via OpenAI-compat proxy  | native (with max_tokens=4096) |
| `ollama`    | `http://localhost:11434/v1`        | native                        |
| `vllm`      | self-hosted vLLM                   | native                        |

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

`--playbook auto` lets the supervisor classify the task.

## Output schema

See `SKILL.md`. Important: PROMOTE is a quality signal, not authority. The CEO is the final decision-maker.

## Quality gate

The runtime gate uses thresholds from arXiv 2603.15676 (Automated Self-Testing as a Quality Gate):

| metric                   | PROMOTE                  | HOLD band   | ROLLBACK |
|--------------------------|--------------------------|-------------|----------|
| Task Success             | ≥ 0.80                   | 0.56–0.80   | < 0.56   |
| Context Preservation     | ≥ 0.90                   | 0.63–0.90   | < 0.63   |
| P95 Latency (per iter)   | ≤ 15 000 ms              | 15–21 s     | > 21 s   |
| Safety Pass Rate         | ≥ 0.95                   | 0.67–0.95   | < 0.67   |
| Evidence Coverage        | ≥ 0.80                   | 0.56–0.80   | < 0.56   |
| axis-05 violations       | 0                        | 1–2         | ≥ 3      |
| axis-06 violations       | 0                        | 1–2         | ≥ 3      |

PROMOTE requires every dimension to be in the PROMOTE band; any dimension in ROLLBACK forces a global ROLLBACK.

After ~100 real runs, recalibrate by inspecting the `trace_log` and `spans` tables in `~/.local/share/gemma-worker/store.db`.

## Audit integration

* Layer 0 (design-time, axes 1–4): a `PostToolUse` hook on `Edit|Write` renders the relevant `axis-*-prompt.md` against the edited file and logs to `/tmp/gemma-worker-audit.log`.
* Layer 2 (runtime, axes 5–6): the supervisor stores per-call spans in SQLite; pass that span list (or the raw store) to axis-05 / axis-06 prompts after a worker run.

`ai-pipeline-audit` keeps its "Detect, report, user decides" contract. Nothing is auto-modified.

## Storage

The worker keeps state in a single SQLite DB:

```
~/.local/share/gemma-worker/store.db
  - trace_log            (one row per worker run)
  - spans                (every LLM/tool call as an OTel span)
  - retry_state          (idempotent retry counters)
  - audit_disagreements  (meta-judge tie-break log)
```

Override the directory with `GEMMA_WORKER_STATE_DIR`.

## Monthly review (operate the skill, not just run it)

The architecture is pinned to specific library versions and threshold values. They will drift. Run a `/deep` review on a monthly cadence:

1. First Monday — framework freshness
   - "LangGraph 0.7" / "Pydantic 3" / "OpenAI SDK breaking changes" — anything that would invalidate the pins in `pyproject.toml`.
2. Third Monday — model freshness
   - Re-evaluate SWE-bench-Verified scores for Gemma-class workers, and any new OpenAI-compatible endpoints.
3. Ad hoc — security advisories
   - `langchain` GHSA, `openai` CVE, `aiosqlite` releases.

Workflow:

1. `/deep "<topic>"` → save plan under `~/.claude/plans/<short-name>.md`.
2. Tag each finding with `Adopt` / `Reject` / `Defer`.
3. `Adopt` → patch this skill (`pyproject.toml`, `supervisor.py`, or a specific playbook).
4. `Reject` / `Defer` → archive the plan under `~/.claude/plans/archive/`.
5. Append a one-liner to `~/.claude/plans/_index.md` so future months can see the decision history.

## Tests

```
cd ~/.claude/skills/gemma-worker
uv run pytest                       # full suite, ~1s
uv run pytest -m live               # live smoke against $WORKER_LLM_BASE_URL (only when set)
```

## File map

```
gemma_worker/
  __main__.py / run.py              CLI entrypoint
  supervisor.py                     LangGraph StateGraph (route → execute → audit → measure → reflect)
  client/
    base.py                         WorkerConfig + Provider protocol
    _shared.py                      AsyncOpenAI helper, JSON parsing, retry
    providers/
      gemma.py / openai_.py /
      anthropic_.py / ollama.py /
      vllm.py
  queue/worker_pool.py              asyncio priority queue + adaptive rate
  store/
    schema.sql
    sqlite_store.py                 trace_log, spans, retry_state, disagreements
  tracer/otel_tracer.py             gen_ai.* spans, SQLite exporter
  gate/
    audit_gate.py                   Layer 0 prompt rendering for ai-pipeline-audit
    runtime_gate.py                 5-dimension metrics + PROMOTE/HOLD/ROLLBACK
  playbooks/
    _common.py
    deadcode.py / inconsistency.py /
    gap.py / research.py /
    optimization.py / synthesis.py
  prompts/                          (reserved for future externalized templates)
tests/                              69 passing tests across all modules
_dev/hook_check.sh                  PostToolUse hook (Edit|Write → Layer 0 audit)
```

## Limitations

* `research` playbook does not perform web fetches. It escalates to the CEO with structured queries.
* Worker LLMs at the Gemma-31B class are mediocre at deep multi-step reasoning. The supervisor compensates with the reflexion loop, not the model.
* The runtime gate's metric formulas are intentionally simple — replace with calibrated ones after running enough real workloads to fit a regression.
