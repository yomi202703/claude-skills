#!/usr/bin/env python3
"""Dispatcher: slash-command → script routing (v5, SPEC §13.2).

Usage:
    python dispatcher.py <command> [command-args...]

Commands (v5):
    ingest <arxiv:ID | path/to.md>
    status
    lint                         — regenerate index.md, return dead_link report
    pillars [--top-n N]
    narratives                   — validate narratives/, regenerate forest index
    narrative-draft <source.md>  — source md → narrative tree
    narrative-split <slug> --section <H2> — split a bloating narrative
    coverage-narrative <slug>    — QuestEval gap report
    note-from-chat <export.md> --study <slug> — chat export → notes/<slug>.md
    note-rewire [--study <slug>] [--apply] — propose/apply anchor wikilinks for orphan notes
    pipeline                     — ingest → lint → narratives (v5)
    card-draft <slug> [--model <m>] — symbol-walk the tree → exhaustive atomic Q-A deck
    card-add --slug <s> --front <q> --back <a> — append one card by hand (rare)
    cards [<slug>]               — dump deck(s) as JSON

v5 paradigm (REQUIREMENTS §14): concepts/ 廃止、ai-digest 独立化。
`enrich`, `project`, `coverage`, `research`, `ingest --from-digest`
はこの版で全削除された。`drill` の自動採点ループも削除。代わりに card-draft が
narrative tree の記号([?][★][⟳]…)を決定論的に walk して網羅的な暗記デッキを生成
(網羅は構造保証、LLMは清書のみ)。card-add は手動の補助。drill 会話は「ミス→その
カードに戻れ」の診断に縮小 (SKILL.md "Recall drill & cards" / hard rule #2 参照)。

All commands accept --vault PATH (default: $AI_WIKI_ROOT or ~/ai-wiki).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_draft as mod_card_draft  # noqa: E402
import cards as mod_cards  # noqa: E402
import coverage_qa as mod_coverage_qa  # noqa: E402
import ingest as mod_ingest  # noqa: E402
import narrative as mod_narrative  # noqa: E402
import narrative_draft as mod_narrative_draft  # noqa: E402
import note_from_chat as mod_note_from_chat  # noqa: E402
import note_rewire as mod_note_rewire  # noqa: E402
import pillars as mod_pillars  # noqa: E402
import pipeline as mod_pipeline  # noqa: E402
import schema as mod_schema  # noqa: E402
from vault import Vault  # noqa: E402


def cmd_ingest(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py ingest")
    p.add_argument("source", help="arxiv:XXX | path/to.md")
    p.add_argument("--vault", default=None)
    p.add_argument("--ingested-from", default="manual", dest="ingested_from")
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_ingest.ingest(vault, args.source, ingested_from=args.ingested_from)


def cmd_status(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py status")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    manifest = vault.read_manifest()
    narratives = [s for s in vault.list_pages("narrative") if not s.startswith("_")]
    return {
        "vault_root": str(vault.root),
        "counts": {
            "narratives": len(narratives),
            "sources": len(vault.list_pages("source")),
            "notes": len(vault.list_pages("note")),
        },
        "manifest_last_ingest": manifest.get("last_ingest"),
        "manifest_sources": len(manifest.get("sources", {})),
    }


def cmd_lint(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py lint")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    mod_schema.update_index(vault)
    return mod_schema.lint(vault)


def cmd_pillars(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py pillars")
    p.add_argument("--top-n", type=int, default=20, dest="top_n")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_pillars.compute_pillars(vault, top_n=args.top_n)


def cmd_narratives(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py narratives")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_narrative.narratives_summary(vault)


def cmd_coverage_narrative(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py coverage-narrative")
    p.add_argument("slug", help="narrative slug to evaluate")
    p.add_argument("--source", default=None,
                   help="path to original md source (required on first run)")
    p.add_argument("--regenerate-qa", action="store_true",
                   help="force regeneration of QA set even if cached")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_coverage_qa.run_coverage(
        vault,
        slug=args.slug,
        source_path=args.source,
        regenerate_qa=args.regenerate_qa,
    )


def cmd_pipeline(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py pipeline")
    p.add_argument("--arxiv", action="append", default=None,
                   help="arxiv:<id> to ingest (repeat for multiple)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_pipeline.run_pipeline(
        vault,
        arxiv_refs=args.arxiv,
        dry_run=args.dry_run,
    )


def cmd_narrative_draft(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py narrative-draft")
    p.add_argument("source", help="path to markdown source file")
    p.add_argument("--slug", default=None, help="base slug (default: from filename)")
    p.add_argument("--title", default=None, help="display title (default: first `#` heading)")
    p.add_argument("--no-cove", action="store_true",
                   help="skip the final CoVe consistency cleanup")
    p.add_argument("--no-coverage", action="store_true",
                   help="skip the QuestEval iterative remediation (no gap check, no fix)")
    p.add_argument("--coverage-threshold", type=float, default=0.95,
                   help="coverage ratio (0.0-1.0) below which QuestEval will iterate (default 0.95)")
    p.add_argument("--max-iterations", type=int, default=3,
                   help="max QuestEval remediation rounds per narrative (default 3)")
    p.add_argument("--dry-run", action="store_true", help="parse + classify, no LLM calls")
    p.add_argument(
        "--force-strategy",
        choices=["single", "chunked", "hierarchical"],
        default=None,
    )
    p.add_argument(
        "--mode",
        choices=["auto", "peer"],
        default="auto",
        help="auto: one tree per source (size-based). peer: one independent "
             "peer tree per major section, no master hub (for multi-section papers)",
    )
    p.add_argument(
        "--faithfulness",
        action="store_true",
        help="after commit, judge each tree's claims against its source "
             "(precision direction); flags unsupported claims + synthesized edges",
    )
    p.add_argument(
        "--judge-model",
        default=None,
        help="model for the faithfulness judge (default: a different model from "
             "the opus generator, to avoid self-preference bias)",
    )
    p.add_argument(
        "--annotate-inferred",
        action="store_true",
        help="mark synthesized spine edges in-tree with [~] (implies "
             "--faithfulness); idempotent, validates before rewriting",
    )
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_narrative_draft.narrative_draft(
        vault,
        source_path=args.source,
        slug=args.slug,
        title=args.title,
        use_cove=not args.no_cove,
        run_coverage=not args.no_coverage,
        coverage_threshold=args.coverage_threshold,
        max_iterations=args.max_iterations,
        dry_run=args.dry_run,
        force_strategy=args.force_strategy,
        mode=args.mode,
        run_faithfulness=args.faithfulness or args.annotate_inferred,
        judge_model=args.judge_model,
        annotate_inferred=args.annotate_inferred,
    )


def cmd_narrative_split(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py narrative-split")
    p.add_argument("slug", help="source narrative slug (the bloating parent)")
    p.add_argument("--section", required=True,
                   help="`## <header>` text to extract (exact match on the H2 header)")
    p.add_argument("--new-slug", default=None,
                   help="slug for the extracted tree (default: <parent>-<section-slug>)")
    p.add_argument("--no-cove", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_narrative_draft.narrative_split(
        vault,
        parent_slug=args.slug,
        section_heading=args.section,
        new_slug=args.new_slug,
        use_cove=not args.no_cove,
        dry_run=args.dry_run,
    )


def cmd_note_from_chat(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py note-from-chat")
    p.add_argument("export", help="path to chat export markdown file")
    p.add_argument("--study", required=True,
                   help="study identifier (typically the related narrative slug)")
    p.add_argument("--slug", default=None, dest="slug_override",
                   help="override slug for the resulting note (default: LLM proposes)")
    p.add_argument("--no-anchor", action="store_true",
                   help="do not propose an anchor wikilink even if narrative exists")
    p.add_argument("--apply-anchor", action="store_true",
                   help="patch the related narrative with the proposed wikilink")
    p.add_argument("--no-detect-check", action="store_true",
                   help="skip chat-export shape detection (allow non-chat input)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_note_from_chat.note_from_chat(
        vault,
        chat_path=args.export,
        study=args.study,
        slug_override=args.slug_override,
        no_anchor=args.no_anchor,
        apply_anchor=args.apply_anchor,
        skip_detect_check=args.no_detect_check,
        dry_run=args.dry_run,
    )


def cmd_note_rewire(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py note-rewire")
    p.add_argument("--study", default=None, dest="study_filter",
                   help="filter to a single study (default: all)")
    p.add_argument("--apply", action="store_true",
                   help="actually patch narratives (default: dry-run, propose only)")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_note_rewire.note_rewire(
        vault,
        study_filter=args.study_filter,
        apply=args.apply,
    )


def cmd_card_add(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py card-add")
    p.add_argument("--slug", required=True, help="narrative slug the card came from (deck file)")
    p.add_argument("--front", required=True, help="cue: the question / description")
    p.add_argument("--back", required=True, help="answer: the term / causal explanation")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_cards.add_card(vault, slug=args.slug, front=args.front, back=args.back)


def cmd_cards(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py cards")
    p.add_argument("slug", nargs="?", default=None, help="deck to dump (default: all decks)")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_cards.list_cards(vault, slug=args.slug)


def cmd_card_draft(argv: list[str]) -> dict:
    p = argparse.ArgumentParser(prog="dispatcher.py card-draft")
    p.add_argument("slug", help="narrative slug to generate a deck for (symbol-walk)")
    p.add_argument("--model", default=None, help="LLM model override (default: opus)")
    p.add_argument("--vault", default=None)
    args = p.parse_args(argv)
    vault = Vault(root=args.vault) if args.vault else Vault()
    return mod_card_draft.draft_cards(vault, args.slug, model=args.model)


COMMANDS = {
    "ingest": cmd_ingest,
    "card-add": cmd_card_add,
    "card-draft": cmd_card_draft,
    "cards": cmd_cards,
    "status": cmd_status,
    "lint": cmd_lint,
    "pillars": cmd_pillars,
    "narratives": cmd_narratives,
    "narrative-draft": cmd_narrative_draft,
    "narrative-split": cmd_narrative_split,
    "note-from-chat": cmd_note_from_chat,
    "note-rewire": cmd_note_rewire,
    "pipeline": cmd_pipeline,
    "coverage-narrative": cmd_coverage_narrative,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        print("\nAvailable commands:")
        for name in COMMANDS:
            print(f"  {name}")
        return
    cmd_name = sys.argv[1]
    rest = sys.argv[2:]
    if cmd_name not in COMMANDS:
        print(f"unknown command: {cmd_name}", file=sys.stderr)
        sys.exit(2)
    result = COMMANDS[cmd_name](rest)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
