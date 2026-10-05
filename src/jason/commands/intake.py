"""``jason intake``: the questions jason could not decide while taking documents in, for a person to answer.

``jason intake --scan`` runs the readers (the library, each living document against its sources and working copy)
and parks each uncertainty as a question in ``data/intake/asks.json``; an answered question stays answered.
``jason intake`` lists the open ones (``--kind``, ``--subject``, ``--limit``). ``--answer ID TEXT --by NAME`` answers
one (a choice's number or words; ``dismiss`` closes it; an answer that looks like a secret is refused and not stored).
``--confirm ID --by NAME`` is a second person's confirmation of a high-stakes answer. ``--accept-likely --by NAME``
answers every open ``likely`` OCR reading with its suggestion, after a person has looked at the list. ``--apply``
turns the answers into the records the next run uses (transcriptions, person-chosen kinds, private facts, proposed
profile changes). The scan also parks the onboarding questions (``jason onboard``). Read-only everywhere but ``data/``.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Any, Callable

from jason.commands._shared import data_dir as _data_dir


def _second_readers(ld, built, lexicon, data_dir, *, model: bool, vision: bool, route: str = "suspects",
                    opts: Any = None) -> dict:
    """The local model's and the vision model's readings of a living document's doubtful words, by section. ``route``
    says which tokens the vision model reads: the guarded suggestions (a number, an operative word: today's), and with
    ``doubts`` or ``suspects`` the words the text rules cannot settle, or every word the English prior doubts."""
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
        rules = {"opts": opts} if opts is not None else {}
        wanted = {k: [s for s in combine(suggest(t, lexicon, **rules), extra.get(k, ())) if s.guard]
                  for k, t in passages.items()}
        try:
            seen = ocr_task.vision_readings(pdf, words, passages, {k: v for k, v in wanted.items() if v}, reader)
            if route != "guarded":
                found = ocr_task.routed(passages, lexicon, route, opts)
                for k, v in ocr_task.vision_readings(pdf, words, passages, found, reader, lexicon=lexicon).items():
                    seen[k] = seen.get(k, []) + v
        finally:
            try:
                unload(model_name)
            except OSError:
                pass
        for k, v in seen.items():
            extra[k] = list(extra.get(k, [])) + v
    return extra


def _scan(data_dir, *, model: bool = False, vision: bool = False, route: str = "suspects",
          options: tuple[str, ...] = ("search", "case", "terms")) -> tuple[list, tuple[str, ...]]:
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
        opts = ocr_task.options_for(options, ocr_task.load_channel(data_dir)) if (options or ocr_task.load_channel(data_dir)) else None
        extra = (_second_readers(ld, built, lexicon, data_dir, model=model, vision=vision, route=route, opts=opts)
                 if (model or vision) else {})
        held: list = []
        asks += intake_task.ocr_reading_asks(ld.key, built.current, copy, vocab, lexicon=lexicon, extra=extra,
                                             held=held, opts=opts)
        # One reader's suggestions are kept for the record, not asked: --model (or --vision) adds the second reader.
        path = living_docs.living_dir(data_dir, ld.key) / "ocr-suggestions.json"
        path.write_text(json.dumps([{"section": section, "wrong": s.wrong, "right": s.right, "fix": s.fix.value,
                                     "methods": [m.value for m in s.methods], "confidence": s.confidence,
                                     "guard": s.guard, "evidence": list(s.evidence)} for section, s in held],
                                   indent=1), encoding="utf-8")
        if held:
            print(f"{ld.key}: {len(held)} suggestions with one reader kept in {path} (--model adds a second)")
    # The onboarding questions: facts a person supplies, and documents or records with no book or folder.
    from jason.tasks import onboarding_session

    try:
        asks += onboarding_session.generate_for(community(), data_dir)
        scope += list(onboarding_session.SCOPE)
    except Exception as exc:  # noqa: BLE001 - the checklist failing must not lose the document questions
        print(f"onboarding questions not read: {type(exc).__name__}: {exc}", file=sys.stderr)
    return asks, tuple(scope)


def _learn_channel(data_dir) -> str:
    """``--learn-channel``: count the letters a recognizer misread in each scanned living document's base, against its
    working copy, and save the rule table (letters only) to ``data/ocr/channel.json``. The reading is the raw one: no
    transcription is applied, and the lexicon's own corpus is not read."""
    from jason.community import community, ocr_channel
    from jason.community.living import provisions_of
    from jason.tasks import living_docs, ocr_reread
    from jason.tasks import ocr_correct as ocr_task

    pairs: list = []
    printed: list = []
    for ld in community().living_documents():
        if ld.base.kind.value != "scan" or not ld.working_doc:
            continue
        copy = living_docs.working_copy(ld, data_dir)
        if copy is None:
            continue
        try:
            built = living_docs.build(ld, data_dir, transcribed=())
        except ValueError as exc:
            print(f"{ld.key}: {exc}", file=sys.stderr)
            continue
        hyp, _ = ocr_reread.page_tokens(built.current.provisions)
        ref, _ = ocr_reread.page_tokens(provisions_of(copy))
        pairs += ocr_channel.aligned_pairs(hyp, ref)
        printed += ref
    from pathlib import Path

    from jason.community.ocr import TesseractCli
    from jason.tasks import ocr_synth

    real = len(pairs)
    synthetic = 0
    if TesseractCli.available():
        # Clean public text, rendered, degraded, and read back by the Tesseract tool: more misreads than a copy gives.
        texts = [p.read_text(encoding="utf-8", errors="replace") for p in sorted((Path(data_dir) / "authorities").rglob("*.md"))]
        if texts:
            fake, spoken = ocr_synth.synthetic_pairs(texts)
            pairs, printed, synthetic = pairs + fake, printed + spoken, len(fake)
    if not pairs:
        return "no scanned living document with a working copy, and no rendered text: nothing to learn the channel from"
    channel = ocr_task.learn_channel(pairs, printed, data_dir)
    top = ", ".join(f"{r}>{p}" for r, p, _ in channel.table(8))
    return (f"learned {len(channel.rules)} rules from {real} words a working copy shows were misread and {synthetic} read "
            f"back from rendered statutes into {ocr_task.channel_path(data_dir)}: {top} (as read > as printed); "
            f"jason intake --scan reads it from now on")


def print_applied(done: list, refused: list, shown: list) -> None:
    """What ``--apply`` did: each record, each diff or proposal, and each answer it refused, with why."""
    print(f"applied {len(done)}: " + "; ".join(f"{a.id} -> {a.applied_to}" for a in done[:10])
          + (" ..." if len(done) > 10 else ""))
    for a, text in shown:
        print(f"\n{a.id} ({a.kind.value} {a.subject}):\n{text.rstrip()}")
    for a, why in refused:
        print(f"not applied {a.id} ({a.kind.value} {a.subject}): {why}", file=sys.stderr)


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
        if not (args.scan or args.answer or args.confirm or args.accept_likely or args.apply):
            return 0
    if args.learn_channel:
        print(_learn_channel(data_dir))
        if not (args.scan or args.answer or args.confirm or args.accept_likely or args.apply):
            return 0
    if args.scan:
        found, scope = _scan(data_dir, model=args.model, vision=args.vision, route=args.vision_route,
                             options=tuple(o for o in (args.ocr_options or "").split(",") if o))
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
        print(f"{a.id}: {a.status.value}: {a.answer!r} (by {a.answered_by})"
              + ("; high stakes: a second person confirms it (--confirm ID --by NAME) before --apply"
                 if intake.high_stakes(a) and a.status is intake.AskStatus.ANSWERED else ""))
    if args.confirm:
        try:
            a = intake.confirm(asks, args.confirm, args.by or "")
        except (KeyError, ValueError) as exc:
            print(f"cannot confirm {args.confirm}: {exc}", file=sys.stderr)
            return 2
        intake.save(data_dir, asks)
        print(f"{a.id}: confirmed by {a.confirmed_by} (answered by {a.answered_by})")
    if args.accept_likely:
        try:
            done = intake_task.accept_likely(asks, args.by or "")
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        intake.save(data_dir, asks)
        print(f"accepted {len(done)} likely OCR readings in the name of {args.by}")
    if args.apply:
        refused: list = []
        shown: list = []
        done = intake_task.apply(asks, data_dir, refused=refused, shown=shown)
        intake.save(data_dir, asks)
        print_applied(done, refused, shown)
    if args.scan or args.answer or args.confirm or args.accept_likely or args.apply:
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
    p.add_argument("--confirm", metavar="ID",
                   help="a second person confirms an answered high-stakes question (with --by; not who answered)")
    p.add_argument("--by", help="the person answering or confirming (required)")
    p.add_argument("--apply", action="store_true", help="turn answers into the records the next run uses")
    p.add_argument("--model", action="store_true",
                   help="with --scan: the local text model reads the doubtful words too (a second reader)")
    p.add_argument("--vision", action="store_true",
                   help="with --scan: the vision model reads the page's crop of the words in doubt (--vision-route says which)")
    p.add_argument("--vision-route", choices=("guarded", "doubts", "suspects"), default="suspects",
                   help="with --scan --vision: which tokens the page's crop is read for: every word the English prior doubts "
                        "(default), the words the text rules cannot settle, or only the guarded suggestions (a number, an "
                        "operative word; the first version's)")
    p.add_argument("--ocr-options", metavar="LIST", default="search,case,terms",
                   help="with --scan: the text rules' extra readings, comma separated (default search,case,terms; an empty "
                        "string is the first version's rules): search (words within three edits), case (capitals from the "
                        "sentence and the document's terms), terms (a defined term ranks up), real-words (a real word read "
                        "as another the context makes likelier; sends those words to the page too)")
    p.add_argument("--learn-channel", action="store_true",
                   help="count the letters OCR misreads (against each working copy, and in rendered statutes read back by "
                        "the Tesseract tool) into data/ocr/channel.json; --scan reads it (letters only, no word of any "
                        "document)")
    p.add_argument("--library-ocr", action="store_true",
                   help="write OCR suggestions beside the library's OCR texts and list the worst-read files")
    p.add_argument("--library-kind", action="append", help="with --library-ocr: only this kind (repeatable)")
    p.set_defaults(func=cmd_intake)
