---
name: deadcode
description: Detect dead code, verify it, delete it, and confirm with tests — end to end. Trigger on "find dead code", "unused code", "unreferenced", "clean up", "remove unused", "dead functions".
---

# deadcode (router)

The user does not read code. The skill completes end to end.
Never escalate "needs review" items to the user. Never treat tool output as the final verdict.

## Rules

R1. Passing tests is the minimum gate for deletion — necessary, not sufficient.
R2. Make a safety commit before any deletion.
R3. Tool output is a candidate list. Final judgment is by the skill's own grep + code reading.
R4. "Zero dead reports" does not mean "no dead code exists".
R5. Test-green ≠ safe. Dead code can revive through feature flags, config, serialization, or reflection, none of which a passing suite exercises. `safety: 3` candidates (functions / methods / classes) are not deleted on the test gate alone — they pass through the Phase 2.5 runtime-evidence gate first; where runtime evidence is unobtainable they are deferred, not deleted.
R6. Dynamic-dispatch indicators in a file — `getattr` / `setattr`, `importlib` / `__import__`, `__getattr__` / `__getattribute__`, `eval` / `exec`, or other reflection — make every finding in that file low-confidence. Low-confidence findings are excluded from auto-delete and routed to Phase 2.5.

## Phase 0 — Stack detection & route

| manifest | language | framework file |
|----------|----------|----------------|
| `package.json` | JS/TS | `frameworks/js-ts.md` |
| `pyproject.toml` / `requirements.txt` | Python | `frameworks/python.md` |

Multi-language repo: ask via AskUserQuestion to pick one.

Load `LENSES`, `TEST_CMD`, `FRAMEWORK_HOOKS`, `ENTRYPOINTS` from the framework file.

## Phase 1 — Baseline & safety commit

1. Run `TEST_CMD`
   - exit 0 → continue
   - no tests configured → AskUserQuestion: "No tests found. Proceed conservatively with grep + typecheck only?". yes → replace R1 with "grep + typecheck green" (`status: no_tests_conservative`)
   - exit ≠ 0 → exit with `status: tests_red_before_start`
2. Capture the **typecheck baseline**: run the typechecker now and record the pre-existing error set. The deletion gate (Phase 3a) is "no *new* errors versus this baseline", not "absolute green" — a repo that already has unrelated typecheck errors must not make every deletion look unsafe.
3. `git add -A && git commit -m "wip: pre-deadcode-scan snapshot" --allow-empty`
4. Run **all `LENSES` in parallel**, UNION the outputs, dedup by `(file, line, name)`. Each lens has `name` and `safety` (1 = safest, 3 = riskiest). Carry `lens` and `safety` on every finding.
   - A lens that is `command not found` → AskUserQuestion to run `bash ~/.claude/skills/deadcode/setup.sh --<lang>`. no → `status: aborted_no_tool`.
   - A lens that times out, crashes, or returns malformed/non-JSON output → record `{lens, status: "error", detail}`, drop only that lens's findings, and continue with the others. Never treat a crashed lens as "zero findings = clean".

Output schema: `[{file, line, name, kind, lens, safety}]`.

## Phase 2 — Per-finding verification

For each finding, decide silently (do not surface to user):

1. Read the definition site (±20 lines)
2. `rg -n '\b<name>\b'` repo-wide
3. Filter grep output: drop the definition line; drop comment lines; keep string-literal hits. ≥1 line remaining → keep alive, skip
4. Match against `FRAMEWORK_HOOKS` → skip
5. `rg -n "['\"]<name>['\"]"` for dispatcher patterns. ≥1 hit → skip
6. None matched → add to candidate list
7. Tag confidence (R6): if the finding's file contains any dynamic-dispatch indicator (`getattr`/`setattr`, `importlib`/`__import__`, `__getattr__`/`__getattribute__`, `eval`/`exec`), mark the candidate `low_confidence`. low_confidence candidates and every `safety: 3` candidate go to Phase 2.5 instead of straight to deletion; `safety: 1–2` non-low-confidence candidates form the deletion list directly.

## Phase 2.5 — Runtime-evidence gate (safety:3 and low_confidence)

`safety: 1–2` candidates skip this gate by design: unused imports / variables, compiler-proven unreachable branches, and orphan files are *statically* decidable, so a passing typecheck is sufficient proof for them. `safety: 3` (functions / methods / classes) and any `low_confidence` candidate are not statically decidable — liveness for dynamic code is undecidable in general — so they need evidence they are actually unexecuted before deletion.

1. Instrument each candidate's definition site with a lightweight execution marker: a single log line (or counter increment) emitted on entry, tagged with the candidate's `file:name`.
2. Run `TEST_CMD` plus any other exercising workload the repo provides (a `make`/script target that runs the app, a seed/CLI invocation). "Exercising workload" means something that drives production code paths, not just imports modules.
3. A candidate whose marker fired → it is live → drop it (record in `kept_by_runtime_evidence`).
4. A candidate with zero marker hits → it graduates to the deletion list.
5. "No runtime observation feasible" = there is no test or workload that drives the candidate's module at all (importing the module does not count). In that case do NOT delete these candidates: move them to `deferred_needs_runtime_evidence`. `safety: 1–2` deletions still proceed regardless.

Remove the instrumentation before Phase 3 (it is not part of the deletion).

## Phase 3 — Batch delete + bisect

### 3a — Stack N commits (sorted safest first)

Sort `deletion_list` by `safety` ascending (1 → 3). This puts unreachable-code and unused-import deletions first; aggressive function/class removals last. If bisect later finds a bad commit, the earlier (safer) ones are more likely to stay.

```
for c in sorted(deletion_list, by safety):
    delete(c)             # imports/vars via Edit, functions/methods/classes via ast-grep
    typecheck             # pyright / tsc
    no NEW errors vs Phase 1 baseline → git commit -m "deadcode: try remove <file>:<name> [lens=<lens>]"
    new error(s) introduced → git reset --hard HEAD, record in rejected_by_typecheck
```

### 3b — Single test pass + bisect

```
TEST_CMD
```

green → accept all, go to Phase 4.
red → `git bisect start HEAD <safety_commit> && git bisect run TEST_CMD` to find bad commit → `git revert --no-edit <bad>` → rerun TEST_CMD → repeat until green. Record in `rejected_by_test`.

### 3c — AST delete (functions/methods/classes)

```
ast-grep run --pattern '<pattern>' --rewrite '' --lang <lang> <file>
```

## Phase 4 — Final commit & report

If ≥1 deletion:

```
git add -A && git commit -m "deadcode: remove N unused <kind>"
```

Report:

```
status: completed | aborted_no_tool | tests_red_before_start | no_tests_conservative | no_runtime_evidence
safety_commit: <SHA>
deletion_commit: <SHA> or null
removed: [{file, name, kind}]
rejected_by_test: [{file, name, kind}]
rejected_by_typecheck: [{file, name, kind}]
kept_by_runtime_evidence: [{file, name, kind}]          # observed executing in Phase 2.5
deferred_needs_runtime_evidence: [{file, name, kind}]   # safety:3 / low_confidence, no way to observe — NOT deleted
limitations: <free text>
revert_cmd: "git reset --hard <safety_commit>"
```

`status` reflects the run as a whole, and `deferred_needs_runtime_evidence` is independent of it: a deferred list may be non-empty under any status. Use `completed` whenever the pipeline finished and ≥1 deletion landed (even if some candidates were deferred). Use `no_runtime_evidence` only when nothing was deleted *because* every candidate that reached the deletion stage was a safety:3 / low_confidence one that had to be deferred. The deferred list is reported in every case so it is never silently dropped.

`limitations` must always state what this skill structurally cannot see, so a clean report is not misread as proof of no dead code: cross-language reachability (e.g. a Python symbol called only from TS/JS, or via an API/RPC boundary), dead CSS / unused static assets, code behind permanently-off (or permanently-on) feature flags, and any call made through reflection. None of these are detected here.
