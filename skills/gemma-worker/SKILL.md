---
name: gemma-worker
description: Heavy enumeration / analysis / synthesis を OpenAI 互換エンドポイントの OSS LLM に委譲。6 playbook (deadcode / inconsistency / gap / research / optimization / synthesis) を LangGraph で並列実行し、5 次元品質を測って PROMOTE / HOLD / ROLLBACK verdict を返す。リポジトリ全体スキャンや大量並列調査向け。単発の判断・対話には呼ばない。
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
  --playbook <deadcode|inconsistency|gap|research|optimization|synthesis|auto> \
  --output json
```

`--playbook auto` lets the supervisor classify and pick the playbook.

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
