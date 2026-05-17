---
name: code-consistency
description: AI 生成コードの事後監査。Detect only — never modifies code. 実装区切り/PR 前/レビュー時/simplify 前に呼ぶ。
---

# Code Consistency Audit (orchestrator)

## Rules

- Detect, report, user decides. The skill never modifies code on its own. Pair with `simplify` skill for fix mode.
- Silent on CLEAN: do not emit per-axis results when every axis is empty.
- False positives are acceptable. Subagents err on the side of flagging; the user filters.
- Idempotent: same input produces the same report.
- The orchestrator does not re-judge subagent findings, does not narrate, does not summarize axes. Pure routing + aggregation.
- Cross-axis duplicates are preserved: when the same `file:line` is flagged by multiple axes, keep one entry per axis. Do not merge.

## Workflow

1. Confirm audit targets with user via AskUserQuestion if not specified. Accept a file, a directory, or a glob. If the user does not respond or supplies an unreadable path, return the request unfulfilled and stop.
2. Enumerate the files in the target (recursively if a directory, single entry if a file). Filter to `*.py` for v1. Exclude `*/.venv/*`, `*/_archive/*`, `*/node_modules/*`, `*/__pycache__/*`. This is the file queue.
3. Process the file queue one file at a time. For each file:
   a. Spawn 5 audit subagents in parallel via the Agent tool with `model: opus`. Each subagent's input is the content of the corresponding `~/.claude/skills/code-consistency/prompts/axis-NN-*.md` plus the single file path as `$TARGET` and the repo root as `$REPO_ROOT`, with the explicit constraint: "Return ONLY the JSON array — no narration, no markdown fences, no preamble." Each subagent receives only its own axis content, one anchor file, and the repo root for cross-reference.
   b. Collect the 5 JSON arrays for this file.
   c. If a subagent returns non-JSON, errors, or times out, retry once. On second failure, record `{file, axis: N, status: "error", detail: <short>}` and continue with the other axes for this file.
4. After all files are processed, aggregate every JSON list. Preserve cross-axis duplicates per the rule above.
5. Report violations as `file:line | axis# | severity | evidence | why`. If every list is empty: `✓ all 5 axes clean across <N> files`. Report any axis-level errors from step 3c alongside the violations.

## Self-tune (single pass, post-audit)

The skill improves its own axis prompts based on real audit output. There is no fixture, no re-run loop, no convergence check. Each real audit is both a detector run and the data source for the next round of refinement. Edits ship "untested" and are validated implicitly by the next real audit; git history is the only safety net.

Run only when the audit produced ≥ 1 finding that the orchestrator can confidently classify as a false positive (axis prompt over-reach). Skip when findings are sparse, all true-positive, or ambiguous.

1. `cd ~/.claude/skills/code-consistency`. If not a git repo, `git init && git add -A && git commit -m "init: code-consistency skill baseline"`. Otherwise, `git status` — if dirty, `git add -A && git commit -m "wip: pre-tune snapshot of code-consistency"`.
2. Read the findings from step 5. For each finding, self-classify as TP / FP / ambiguous. Group FPs by `axis` field — that's the axis whose prompt over-reached.
3. For each FP cluster, identify the specific clause in `prompts/axis-NN-*.md` that produced it. Add a narrowing rule — an exclusion under "What constitutes acceptable design" or "Exclusions", or a tighter phrasing under "What constitutes the failure". Do not rewrite the prompt wholesale.
4. Commit: `git add -A && git commit -m "tune axis-NN: drop FP on <short pattern>"`. One commit per axis touched.
5. Stop. Do not re-run the audit in the same invocation. Report the tune commits to the user as part of the audit summary.

If the next real audit reveals the tune overshot (now misses obvious TPs), `git revert <tune-commit>` is the recovery path. Do not chain tune commits to "fix" a previous tune — revert and start fresh on a different finding set.

## Axes

| # | Axis | Scope | Prompt file |
|---|---|---|---|
| 1 | Robustness theater | file-local | `prompts/axis-01-robustness-theater.md` |
| 2 | Phantom flexibility | file-local + repo grep | `prompts/axis-02-phantom-flexibility.md` |
| 3 | Drift across files | cross-file | `prompts/axis-03-drift.md` |
| 4 | Re-implementation / duplication | cross-file + stdlib | `prompts/axis-04-duplication.md` |
| 5 | Placeholder & residue debt | file-local | `prompts/axis-05-residue.md` |

Axes are self-contained in their prompt files. The orchestrator does not need to understand them — it only routes targets and collects JSON.

## Evidence basis for the 5 axes

- Axis 1: Columbia "9 Critical Failure Patterns" #9 Exception silently suppressed (2026-01-08); Anthropic Claude Code system prompt anti-pattern clauses.
- Axis 2: Simon Willison "vibe coding / agentic engineering" over-engineering observation (2026-05-06); Anthropic system prompt "Don't add features... Don't design for hypothetical future".
- Axis 3: Columbia #4 Data Management Errors + #8 Codebase Awareness (2026-01-08); codewithrigor #8 Architecture Drift (2026).
- Axis 4: Columbia #7 Repeated Code (2026-01-08); GitClear 2025 — copy/paste rate 8.3% (2021) → 12.3% (2024) across 211M changed lines from Google/MS/Meta repos.
- Axis 5: Columbia #5 Hardcoded placeholder values (2026-01-08); Anthropic system prompt residue clauses.
