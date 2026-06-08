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

## Procedural mode — faded derivation drill

Read this branch when the user asks to be drilled on a **derivation** (a
`derivations/<slug>.md` spine), not a narrative. Declarative recall ("can you
say X?") and procedural recall ("can you *derive* X?") are different skills;
flashcards train the former, this drill trains the latter. The proven shape is
**worked → faded → independent** (faded worked examples) over a subgoal-labeled
spine. The spine (`## SPINE`, the `[⇣n]` chain) is the single source of truth.

Loop — same one-step-at-a-time discipline as above, plus a fade ladder:

1. Show the **GOAL** and the **subgoal map** (the `[⇣n]` labels only, not their
   content). The labels are the scaffold — subgoal labeling is what transfers.
2. Reveal steps already established; ask for **one** next step's actual math.
   Tell them to do it on paper first. Halt. Never pre-fill their work.
3. Compare their step against that `[⇣n]`'s content in the spine. If it reaches
   the spine, reveal it and advance. If it doesn't, that is **not** a verdict on
   them (hard rule #2) — it is only the trigger to **drop that step's fade one
   notch** next round (show more scaffold), and to note it for re-drilling. Say
   "the spine's ⇣k is …, your step didn't reach it yet — let's fade less here,"
   never "wrong."
4. Fade ladder across repetitions of the same derivation: **F0** all steps shown
   (read it) → **F1** last step hidden → **F2** back half hidden → **F3** only
   the GOAL given, reproduce the whole chain. Raise the fade as they succeed,
   lower it on a miss.

A step marked `[~]` in the spine is **unverified** (the source skipped it and the
judge couldn't confirm). Flag that when you reach it — drill it, but tell the
user to check it against the source/instructor; don't present it as settled.

No script and no `.tsv` for this — the durable artifact is the spine itself; the
drill is the chat-time check (a verified spine can still be Anki-carded later via
the normal `card-draft` path once transfer has happened).

## Hand-off to spaced repetition

`cards/<slug>.tsv` is a 2-column (Front, Back) Anki text file with header directives (`#notetype:Basic`, `#deck:<slug>`) so it imports with no field-mapping and auto-routes into a per-narrative deck. Tell the user to import it and drill via SRS — **not** to "study" by reading the cards as a list (Q and A both visible = passive rereading, not retrieval); the hidden-back drill in the SRS is where memory forms. The one real failure mode at scale is review backlog / burnout, so advise pacing new cards (~10–20/day) rather than dumping a whole course at once.
