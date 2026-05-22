# gemma-worker evals

This directory contains evaluation prompts for the `gemma-worker` skill. The format aligns with the Anthropic `skill-creator` 2.0 schema so the `Eval` and `Benchmark` modes can drive it.

## Files

| File | Purpose |
|---|---|
| `evals.json` | 10 eval cases covering all 6 playbooks plus 3 supervisor-routing tests |
| `fixtures/clean_module/` | A small file with no dead code (for the clean-codebase case) |
| `fixtures/docstring_mismatch/` | Docstring contradicts implementation |
| `fixtures/incomplete_module/` | Missing error handling / safety nets |
| `fixtures/quadratic_loop/` | O(n^2) patterns that should be flagged |
| `fixtures/multi_file_repo/` | Three small files for the synthesis playbook |

## Running evals

### Option A — `anthropic-skills:skill-creator` (recommended)

From a Claude Code session:

```
/anthropic-skills:skill-creator
```

Then choose **Eval** mode and point it at `~/.claude/skills/gemma-worker/evals/evals.json`. skill-creator will spawn its four sub-agents (Skill Tester, Grader, Comparator, Analyzer) and produce:

- `iteration-<N>/eval-<ID>/with_skill/outputs/`
- `iteration-<N>/eval-<ID>/with_skill/timing.json`
- `iteration-<N>/grading.json`
- `iteration-<N>/benchmark.json`

A blind A/B comparator can also run `with_skill` vs `without_skill` to quantify the skill's contribution.

### Option B — manual smoke

For a quick local check without skill-creator, run a single eval by invoking the worker directly:

```
export WORKER_LLM_BASE_URL=...
export WORKER_LLM_API_KEY=...
export WORKER_LLM_MODEL=...
export WORKER_LLM_PROVIDER=gemma

cd ~/.claude/skills/gemma-worker
uv run python -m gemma_worker.run \
  "find unused exports in tests/fixtures/sample_repo" \
  --playbook deadcode --output json | tee /tmp/eval-1.json
```

Then check the JSON against `evals.json` assertions for eval id 1 by eye.

## Assertion format

Each eval has a flat list of `assertions`. They are written as plain prose that a human (or `Grader` sub-agent) can evaluate against the worker's output. We intentionally avoid programmable assertion expressions to keep the schema portable.

Example:

```json
{"name": "finds_unused_orphan",
 "text": "artifacts contain symbol 'unused_orphan_xyz'"}
```

The grader is expected to inspect the JSON output produced by `gemma_worker.run` and decide pass/fail per assertion. It writes `passed: true|false` and `evidence: "..."` back into a per-eval `eval_metadata.json`.

## Thresholds

`evals.json` also records the verdict thresholds the runtime gate uses (arXiv 2603.15676):

- PROMOTE band: `pass_rate >= 0.80`, `p95_latency_ms <= 15000`, `evidence_coverage >= 0.80`
- ROLLBACK floor: `pass_rate < 0.56`, `p95_latency_ms > 21000`, `evidence_coverage < 0.56`
- HOLD between

These mirror `~/.claude/skills/ai-pipeline-audit/scripts/verdict_mapper.py` so the eval benchmark and the live runtime gate stay calibrated to the same numbers.

## Adding new evals

1. Bump the next free `id`.
2. Choose `playbook`: one of `deadcode / inconsistency / gap / research / optimization / synthesis / auto`.
3. Write a realistic `prompt` — not a polished textbook query. Skills 2.0 guidance explicitly warns that polished prompts fail real-world validation; use messy phrasing, typos, abbreviations.
4. Set `expected_output` as a short prose description.
5. Add 1-5 `assertions` that a grader can check from the JSON output.
6. If you need new fixture files, add them under `fixtures/` and reference them in `files`.
7. Re-run skill-creator's Eval mode to update the benchmark.
