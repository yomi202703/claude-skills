# Global working preferences

These apply across every repository. A repo's own CLAUDE.md adds repo-specific detail and overrides these where they conflict (state the override explicitly).

## Output style

- No `**` bold emphasis. Structure with `#` headings and `-` bullets only.

## Documentation governance

When a repo keeps working docs, give them four roles and do not blur them:

- TODO = future / execution queue. Single source of truth for what is next. Two states only — Active (actionable now, ranked P0–P2) and Deferred (blocked; each item MUST name the concrete trigger that unblocks it, e.g. "[data X arrives]", "[owner decides]"). One line per item; rationale lives in decisions (linked by date), never here. Delete when done.
- STATUS = current snapshot. Rewritten each session. Keep it short.
- decisions = append-only ADR ledger. Why a choice was made and what happened. Never rewrite past entries. May be split into one append-only file per topic (mirroring the repo's modules) once a single ledger grows large enough to bloat context on read — the point of the split is that you open only the relevant topic file, not the whole history. When split, freeze the pre-split monolith in archive and route new entries to the topic files; pointers name the topic (e.g. "decisions/<topic> <date>"). Routing a new entry to its topic is the writer's (the AI's) judgment call — do not ask the user which file; default to the cross-cutting bucket when unsure.
- archive = frozen history. Reference only.

Completed work moves from TODO to decisions. It is not left checked-off in TODO. State (Active/Deferred) is orthogonal to priority: an item can be important yet Deferred because it is blocked. A Deferred item with no concrete trigger is not deferred — it is either Active or a "won't do". A "won't do" is recorded in decisions only (the dated call, with rationale) and removed from TODO — do NOT keep a "won't-do" index in TODO (it duplicates decisions and bloats the queue). When you need the list of rejected items to avoid re-proposing one, grep decisions (and archive) for the dated "won't do" calls before proposing.

## Do it yourself

- Prefer reading and exploring directly over spawning subagents whose summaries drop information. Delegate for breadth (fan-out search), not for judgments that should be grounded in primary sources.
- Use grep/find to locate where something is, then open and read the file before concluding. Do not conclude from a line snippet alone.

## Writing prompts for LLM executors

Four rules when authoring or editing a prompt that an LLM will execute (judge, extract, classify, etc.):

1. No prompt-induced bias. Do not nudge toward a verdict with emphasis, authority framing, embedded meta-rationale, or agreement-seeking phrasing. State the rule neutrally.
2. Eval-pipeline integrity. Never put ground-truth, expected answers, or eval-framework terms into the executor's prompt.
3. No overfitting. Do not encode specific id-to-verdict pairs, named entities, or contact ids. Keep few-shot examples to one or two, and abstract.
4. Termination and verification spec. Define done: success and failure return shapes, allowed inputs, output path, and read/tool-failure behavior. Pair every prohibition with a positive operational alternative.
