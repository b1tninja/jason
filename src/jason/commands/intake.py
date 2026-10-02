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

from jason.commands._shared import data_dir as _data_dir


def _second_readers(ld, built, lexicon, data_dir, *, model: bool, vision: bool) -> dict:
    """The local model's and the vision model's readings of a living document's doubtful words, by section."""
    from jason.community.ocr_correct import combine, suggest
    from jason.local_ai import LocalAIUnavailable, preflight, unload
    from jason.tasks import living_docs
    from jason.tasks import ocr_correct as ocr_task

    passages = {p.number: p.body.split() for p in built.current.provisions if p.number and p.standing is None}
    extra: dict = {}
    if model:
        from jason.community.ocr_models import DEFAULT_TEXT_MODEL, OllamaTextCorrector

        try:
            preflight(DEFAULT_TEXT_MODEL)
            extra = ocr_task.model_readings(passages, lexicon, OllamaTextCorrector(model=DEFAULT_TEXT_MODEL))
        except LocalAIUnavailable as exc:
            print(f"{ld.key}: the local model is not read: {exc}", file=sys.stderr)
        finally:
            try:
                unload(DEFAULT_TEXT_MODEL)
            except OSError:
                pass
    if vision and ld.base.kind.value == "scan":
        from jason.community.ocr_models import VisionWordReader

        cache = living_docs.living_dir(data_dir, ld.key) / "sources"
        pdf, why = living_docs.scan_file(ld.base, cache)
        if pdf is None:
            print(f"{ld.key}: no crops: {why}", file=sys.stderr)
            return extra
        import os

        from jason.community.ocr import OLLAMA_OCR_MODEL

        model_name = os.environ.get("JASON_OCR_MODEL") or OLLAMA_OCR_MODEL
        reader = VisionWordReader(model=model_name)
        try:
            preflight(model_name)
        except LocalAIUnavailable as exc:
            print(f"{ld.key}: the vision model is not read: {exc}", file=sys.stderr)
            return extra
        words = ocr_task.page_words(pdf, cache / f"{ld.base.ref}.words.json")
        # Only the guarded suggestions (a number, an operative word) go to the page: the rest have two text readers.
        wanted = {k: [s for s in combine(suggest(t, lexicon), extra.get(k, ())) if s.guard] for k, t in passages.items()}
        try:
            seen = ocr_task.vision_readings(pdf, words, passages, {k: v for k, v in wanted.items() if v}, reader)
        finally:
            try:
                unload(model_name)
            except OSError:
                pass
        for k, v in seen.items():
            extra[k] = list(extra.get(k, [])) + v
    return extra


def _scan(data_dir, *, model: bool = False, vision: bool = False) -> tuple[list, tuple[str, ...]]:
    import json

    from jason.community import community
    from jason.tasks import intake as intake_task
    from jason.tasks import living_docs
    from jason.tasks import ocr_correct as ocr_task

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
        if ld.base.kind.value != "scan" and copy is None:
            continue                                     # a text no OCR read, and nothing to compare it with
        # The language model never learns from the document it reads, nor from its own working copy.
        text = " ".join(p.body for p in built.current.provisions)
        lexicon = ocr_task.lexicon_for(data_dir, text, exclude=(ld.key,))
        extra = _second_readers(ld, built, lexicon, data_dir, model=model, vision=vision) if (model or vision) else {}
        held: list = []
        asks += intake_task.ocr_reading_asks(ld.key, built.current, copy, vocab, lexicon=lexicon, extra=extra,
                                             held=held)
        # One reader's suggestions are kept for the record, not asked: --model (or --vision) adds the second reader.
        path = living_docs.living_dir(data_dir, ld.key) / "ocr-suggestions.json"
        path.write_text(json.dumps([{"section": section, "wrong": s.wrong, "right": s.right, "fix": s.fix.value,
                                     "methods": [m.value for m in s.methods], "confidence": s.confidence,
                                     "guard": s.guard, "evidence": list(s.evidence)} for section, s in held],
                                   indent=1), encoding="utf-8")
        if held:
            print(f"{ld.key}: {len(held)} suggestions with one reader kept in {path} (--model adds a second)")
    return asks, tuple(scope)


def cmd_intake(args: argparse.Namespace) -> int:
    from jason.community import intake
    from jason.tasks import intake as intake_task

    data_dir = _data_dir(args)
    asks = intake.load(data_dir)
    if args.library_ocr:
        from jason.tasks import ocr_correct as ocr_task

        rows = ocr_task.library_suggestions(data_dir, kinds=args.library_kind or (), limit=args.limit if args.limit != 20 else None)
        print(f"{len(rows)} library texts read by OCR; suggestions beside each in data/library/text/<id>.ocr-suggestions.json")
        for r in rows[:15]:
            print(f"  {r['suspects'] / max(1, r['tokens']):.1%} suspect, English {r['english_share']:.0%}, "
                  f"{r['suggestions']} suggestions ({r['guarded']} for a person): {r['path']} [{r['engine']}]")
        if not (args.scan or args.answer or args.accept_likely or args.apply):
            return 0
    if args.scan:
        found, scope = _scan(data_dir, model=args.model, vision=args.vision)
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
    p.add_argument("--model", action="store_true",
                   help="with --scan: the local text model reads the doubtful words too (a second reader)")
    p.add_argument("--vision", action="store_true",
                   help="with --scan: the vision model reads the page's crop of a number or operative word in doubt")
    p.add_argument("--library-ocr", action="store_true",
                   help="write OCR suggestions beside the library's OCR texts and list the worst-read files")
    p.add_argument("--library-kind", action="append", help="with --library-ocr: only this kind (repeatable)")
    p.set_defaults(func=cmd_intake)
