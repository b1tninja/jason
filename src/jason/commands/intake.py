"""``jason intake``: the questions jason could not decide while taking documents in, for a person to answer.

``jason intake --scan`` runs the readers (the library, each living document against its sources and working copy)
and parks each uncertainty as a question in ``data/intake/asks.json``; an answered question stays answered.
``jason intake`` lists the open ones (``--kind``, ``--subject``, ``--limit``). ``--answer ID TEXT --by NAME`` answers
one (a choice's number or words; ``dismiss`` closes it). ``--accept-likely --by NAME`` answers every open ``likely``
OCR reading with its suggestion, after a person has looked at the list. ``--apply`` turns the answers into the records
the next run uses (transcriptions, person-chosen kinds). Read-only everywhere but ``data/``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def _scan(data_dir) -> tuple[list, tuple[str, ...]]:
    import json

    from jason.community import community
    from jason.tasks import intake as intake_task
    from jason.tasks import living_docs

    asks = intake_task.library_asks(data_dir)
    scope = ["library:"]
    texts = [json.loads(p.read_text(encoding="utf-8")).get("text", "")
             for p in (data_dir / "outlines").glob("*.json") if p.name != "references.json"]
    vocab = intake_task.vocabulary(texts)
    for ld in community().living_documents():
        scope.append(f"{ld.key}#")
        scope.append(f"{ld.key}@")
        try:
            built = living_docs.build(ld, data_dir, working=True)
        except ValueError as exc:
            print(f"{ld.key}: {exc}", file=sys.stderr)
            continue
        copy = living_docs.working_copy(ld, data_dir)
        placed = living_docs.place_annotations(built.current, copy, living_docs.load_annotations(data_dir, ld.key))
        asks += intake_task.living_asks(built, placed)
        if copy is not None:
            asks += intake_task.ocr_reading_asks(ld.key, built.current, copy, vocab)
    return asks, tuple(scope)


def cmd_intake(args: argparse.Namespace) -> int:
    from jason.community import intake
    from jason.tasks import intake as intake_task

    data_dir = _data_dir(args)
    asks = intake.load(data_dir)
    if args.scan:
        found, scope = _scan(data_dir)
        asks = intake.merge(asks, found, scope=scope)
        intake.save(data_dir, asks)
        counts = Counter((a.kind.value, a.status.value) for a in asks)
        print("questions: " + "; ".join(f"{k} {s}: {n}" for (k, s), n in sorted(counts.items())))
    if args.answer:
        ident, text = args.answer
        try:
            a = intake.answer(asks, ident, text, args.by or "")
        except (KeyError, ValueError) as exc:
            print(f"cannot answer {ident}: {exc}", file=sys.stderr)
            return 2
        intake.save(data_dir, asks)
        print(f"{a.id}: {a.status.value}: {a.answer!r} (by {a.answered_by})")
    if args.accept_likely:
        try:
            done = intake_task.accept_likely(asks, args.by or "")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        intake.save(data_dir, asks)
        print(f"accepted {len(done)} likely OCR readings in the name of {args.by}")
    if args.apply:
        done = intake_task.apply(asks, data_dir)
        intake.save(data_dir, asks)
        print(f"applied {len(done)}: " + "; ".join(f"{a.id} -> {a.applied_to}" for a in done[:10])
              + (" ..." if len(done) > 10 else ""))
    if args.scan or args.answer or args.accept_likely or args.apply:
        return 0
    wanted = [a for a in asks if a.status is intake.AskStatus.OPEN
              and (not args.kind or a.kind.value == args.kind) and (not args.subject or a.subject.startswith(args.subject))]
    if args.likely:
        wanted = [a for a in wanted if a.likely]
    print(f"{len(wanted)} open questions" + (f" ({sum(a.likely for a in wanted)} likely)" if wanted else "")
          + (": jason intake --scan finds them" if not asks else ""))
    for a in wanted[: args.limit]:
        print(f"\n[{a.id}] {a.kind.value} {a.subject}{' (likely)' if a.likely else ''}\n  {a.question}")
        for e in a.evidence:
            print(f"  evidence: {e[:300]}")
        for n, c in enumerate(a.choices, 1):
            print(f"  {n}. {c[:200]}" + ("   <- suggested" if c == a.suggestion else ""))
    if len(wanted) > args.limit:
        print(f"\n... {len(wanted) - args.limit} more (--limit N, --kind, --subject)")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("intake", help="Questions jason could not decide while taking documents in: classify, OCR "
                                      "readings, amendments, drift, orphaned notes")
    add_common(p)
    p.add_argument("--scan", action="store_true", help="run the readers and park each uncertainty as a question")
    p.add_argument("--kind", help="list one kind (classify, ocr reading, drift, before differs, ...)")
    p.add_argument("--subject", help="list one subject's questions (a prefix: ccrs#4.15, library:)")
    p.add_argument("--likely", action="store_true", help="list only the likely ones")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--answer", nargs=2, metavar=("ID", "TEXT"), help="answer one (a choice's number or words; dismiss)")
    p.add_argument("--accept-likely", action="store_true",
                   help="answer every open likely OCR reading with its suggestion (after looking at --likely)")
    p.add_argument("--by", help="the person answering (required to answer)")
    p.add_argument("--apply", action="store_true", help="turn answers into the records the next run uses")
    p.set_defaults(func=cmd_intake)
