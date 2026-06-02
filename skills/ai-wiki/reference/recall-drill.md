# Recall drill (chat-time behavior)

Read this when the user asks to be drilled / quizzed on a narrative. The drill is conducted by you (the main assistant) in chat — there is no `dispatcher.py` command for it.

## Cards vs drill — keep them separate

- **Cards = the durable memorization asset.** Built *from the tree*, up front, exhaustively, by `card-draft`. Lives in `cards/<slug>.tsv`, Anki-importable. This is where memory actually forms (via the SRS scheduler).
- **The drill (this chat) = a check + a pointer.** It surfaces what the user can't yet retrieve and points them back to the relevant card. It is **not** where cards are born, and **not** the memorization engine.

Why the split: one retrieval doesn't consolidate a memory — only repeated, spaced retrieval does (Karpicke & Roediger). A single chat can't deliver the Nth pass on a whole course, and cramming once manufactures an illusion of knowing. So memorization lives in the SRS; the chat's value is diagnosis.

## Drill loop — strictly one question, then stop

1. Ask **one** question and halt. Never fabricate or pre-fill the user's answer — the entire value is them retrieving unaided. Wait for real input.
2. When they answer, compare it against the narrative and supply what they missed. A miss means *that card isn't yet memorized* → tell them to keep drilling it in the SRS. **Do not mint a new card for the miss** — the card already exists in the deck (that's the redundancy `card-draft` eliminates). Then next question.
3. Sweep nodes in source order so the check has no blind spots; mix term recall and causal prompts.

`card-add` stays only for genuinely-novel synthesis the tree doesn't contain — not for routine miss-carding. Append-only, no node bookkeeping; `--ref` is provenance, never a coverage key.

## Hand-off to spaced repetition

`cards/<slug>.tsv` is a 2-column (Front, Back) Anki text file with header directives (`#notetype:Basic`, `#deck:<slug>`) so it imports with no field-mapping and auto-routes into a per-narrative deck. Tell the user to import it and drill via SRS — **not** to "study" by reading the cards as a list (Q and A both visible = passive rereading, not retrieval); the hidden-back drill in the SRS is where memory forms. The one real failure mode at scale is review backlog / burnout, so advise pacing new cards (~10–20/day) rather than dumping a whole course at once.
