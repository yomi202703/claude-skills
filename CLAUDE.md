# Global working preferences

These apply across every repository. A repo's own CLAUDE.md adds repo-specific detail and overrides these where they conflict (state the override explicitly).

## Output style

- No `**` bold emphasis. Structure with `#` headings and `-` bullets only.

## Documentation governance

When a repo keeps working docs, give them four roles and do not blur them:

- TODO = future / execution queue. Single source of truth for what is next. Delete items when done; keep no completion history or rationale here.
- STATUS = current snapshot. Rewritten each session. Keep it short.
- decisions = append-only ADR ledger. Why a choice was made and what happened. Never rewrite past entries.
- archive = frozen history. Reference only.

Completed work moves from TODO to decisions. It is not left checked-off in TODO.

## Do it yourself

- Prefer reading and exploring directly over spawning subagents whose summaries drop information. Delegate for breadth (fan-out search), not for judgments that should be grounded in primary sources.
- Use grep/find to locate where something is, then open and read the file before concluding. Do not conclude from a line snippet alone.

## Writing prompts for LLM executors

Four rules when authoring or editing a prompt that an LLM will execute (judge, extract, classify, etc.):

1. No prompt-induced bias. Do not nudge toward a verdict with emphasis, authority framing, embedded meta-rationale, or agreement-seeking phrasing. State the rule neutrally.
2. Eval-pipeline integrity. Never put ground-truth, expected answers, or eval-framework terms into the executor's prompt.
3. No overfitting. Do not encode specific id-to-verdict pairs, named entities, or contact ids. Keep few-shot examples to one or two, and abstract.
4. Termination and verification spec. Define done: success and failure return shapes, allowed inputs, output path, and read/tool-failure behavior. Pair every prohibition with a positive operational alternative.
