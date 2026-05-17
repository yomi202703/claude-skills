# P5 — Over-large sheet → metadata summary only

The sheet exceeds 50,000 cells. Do not attempt full processing.

## Output

- Structured summary: sheet dimensions, merge counts, sample headers
- Explicit recommendation:
  - If shape is db-like → run P2 (SQLite materialize)
  - If shape is structured → run P4 (script generation)
- Ask the user once whether to proceed with materialization or script generation

This is the only path where asking is permitted, because the next step is high-cost.
