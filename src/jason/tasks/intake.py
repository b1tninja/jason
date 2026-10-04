"""Generate the questions a person answers while documents are taken in, and apply the answers.

``scan`` runs the readers jason already has and turns every uncertainty into an ``intake.Ask``:

- **the library**: a file no rule classified (``CLASSIFY``), with the model's or the phrase rules' best guess;
- **a living document** (``living_docs.build``): an amendment's before words that differ from the document
  (``BEFORE_DIFFERS``: changed silently, or misread?), two readings of one instrument that disagree
  (``READINGS_DIFFER``), a source held out (``HELD_SOURCE``), the working copy differing in an amended section
  (``DRIFT``), an annotation whose words are gone (``ORPHANED_NOTE``);
- **the base text's OCR** against the working copy (``OCR_READING``): where the two differ by a few words, which does
  the page say? The working copy is usually right where the extract's word is not a word at all; such an ask is
  ``likely`` and can be accepted in a batch after a look.

``apply`` turns answered asks into records the next run uses: an OCR reading becomes a transcription (a
``living.Correction`` kept in ``data/living/<key>/transcriptions.json``), a classification a person-chosen kind
(``data/library/classified-by-person.json``), an onboarding fact a private fact, a Keeper note, or a proposed profile
change, and a mapping a proposed profile change (``jason.tasks.onboarding_answers``). An applicability fact
(``jason.community.applicability_asks``) is checked and marked applied: the answer itself is the fact the next
evaluation reads. The other kinds are recorded answers for the board or counsel. A high-stakes answer waits for a
second person's confirmation.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from pathlib import Path
from typing import Any

from jason.community.intake import Ask, AskKind, AskStatus, ask_id

_WORD = re.compile(r"[A-Za-z]+")
CONTEXT = 3                       # words of context either side of a reading in question
MAX_WORDS = 3                     # a difference of more words is structure, not a misread


def vocabulary(texts: list[str]) -> Counter:
    """How often each word appears across the working copies: a word seen twice is a word."""
    words: Counter = Counter()
    for text in texts:
        words.update(w.lower() for w in _WORD.findall(text))
    return words


def _known(tokens: list[str], vocab: Counter) -> bool:
    letters = [w.lower() for t in tokens for w in _WORD.findall(t)]
    return bool(letters) and all(vocab[w] >= 2 for w in letters) and all(re.fullmatch(r"[\w.,;:()'\"%$&/-]+", t) for t in tokens)


def _likely(old: list[str], new: list[str], vocab: Counter) -> bool:
    """Whether the working copy's words are very probably what the page says:
    - the same characters, spaced differently ("(51 %)" and "(51%)");
    - a deletion of nothing but non-words (a garbled running footer), never of a real word (a run-in caption);
    - a replacement of non-words by real words that look alike ("Condommmms" by "Condominiums")."""
    if "".join(old) == "".join(new):
        # Spacing: splitting words OCR ran together is likely ("ofthe" -> "of the"); joining two words is not (the
        # copy's own slip, "of California" -> "ofCalifornia"), unless only punctuation moves ("(51 %)" -> "(51%)").
        words = lambda tokens: sum(bool(re.search(r"[A-Za-z0-9]", t)) for t in tokens)   # noqa: E731
        return len(new) > len(old) or words(new) == words(old)
    if not new:
        # A deletion of junk only: no real word, and no number (a lone "2" may be a paragraph's number).
        return (not any(vocab[w.lower()] >= 2 for t in old for w in _WORD.findall(t))
                and not any(re.fullmatch(r"\W*\d[\d.,]*\W*", t) for t in old))
    alike = difflib.SequenceMatcher(None, " ".join(old).lower(), " ".join(new).lower()).ratio() >= 0.5
    return alike and _known(new, vocab) and not _known(old, vocab)


def _unique_span(body: str, tokens: list[str], left: list[str], right: list[str]) -> tuple[str, str, str] | None:
    """The exact words of ``body`` for ``tokens`` (whitespace as the body has it), widened by context until they occur
    once: (wrong, left words added, right words added)."""
    for lw in range(0, len(left) + 1):
        for rw in range(0, len(right) + 1):
            words = left[len(left) - lw:] + tokens + right[:rw]
            if not words:
                continue
            pattern = r"\s+".join(re.escape(w) for w in words)
            found = list(re.finditer(pattern, body))
            if len(found) == 1:
                return found[0].group(0), " ".join(left[len(left) - lw:]), " ".join(right[:rw])
    return None


def _fix_of(old: list[str], new: list[str]) -> Any:
    from jason.community.ocr_correct import Fix

    if "".join(old) == "".join(new):
        return Fix.SPLIT if len(new) > len(old) else Fix.JOIN
    if not new:
        return Fix.STRAY
    return Fix.CHARACTER


def _readings_in(suggestions: list, i1: int, i2: int, tokens: list[str]) -> dict[Any, str]:
    """Each method's reading of tokens [i1, i2): its suggestions inside the span applied; a method with none there
    has no reading of it."""
    from jason.community.ocr_correct import apply

    by_method: dict[Any, list] = {}
    for s in suggestions:
        if i1 <= s.start and s.end <= i2:
            for m in s.methods:
                by_method.setdefault(m, []).append(s)
    out = {}
    for m, ss in by_method.items():
        shifted = [type(s)(s.start - i1, s.end - i1, s.wrong, s.right, s.fix, s.methods) for s in ss]
        out[m] = " ".join(apply(tokens[i1:i2], shifted))
    return out


def _evidence(context: str, readings: dict[Any, str], guard: str) -> tuple[str, ...]:
    lines = [f"base: ...{context}..."]
    lines += [f"{m.value} reads: \"{r or '(nothing)'}\"" for m, r in readings.items()]
    if guard:
        lines.append(f"a person reads the page: {guard}")
    return tuple(lines)


def ocr_reading_asks(key: str, current: Any, copy: Any, vocab: Counter, *, lexicon: Any = None,
                     extra: dict[str, list] | None = None, held: list | None = None) -> list[Ask]:
    """Where the base text (read by OCR) and the working copy differ by a few words in a section no amendment set.

    With ``lexicon`` (``ocr_correct``), each difference is also read by the text rules, and ``extra`` adds other
    readers' suggestions by section (the local model, the vision model): an ask is ``likely`` only when two independent
    readers agree and the guard passes (``ocr_correct.tier``). Where the working copy keeps the OCR's reading but the
    rules read the page otherwise (the copy's own slip, "ofthe"), or where there is no working copy, the rules'
    suggestion is asked too. Without ``lexicon``, the working copy alone decides, as ``_likely`` says."""
    from jason.community.living import provisions_of
    from jason.community.ocr_correct import Method, Suggestion, Tier, combine, suggest, tier

    theirs = {p.number: p for p in provisions_of(copy) if p.number} if copy is not None else {}
    out = []
    for p in current.provisions:
        if not p.number or p.standing is not None:
            continue
        ours_t = p.body.split()
        subject = f"{key}#{p.number}"
        rules = combine(suggest(ours_t, lexicon), (extra or {}).get(p.number, ())) if lexicon is not None else []
        covered: set[int] = set()
        same: set[int] = set()                                # tokens the working copy reads as the OCR did
        if p.number in theirs:
            their_t = theirs[p.number].body.split()
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ours_t, b=their_t, autojunk=False).get_opcodes():
                if tag == "equal":
                    same.update(range(i1, i2))
                if tag == "equal" or i2 - i1 > MAX_WORDS or j2 - j1 > MAX_WORDS or i2 == i1:
                    continue                                  # an insertion in the copy is structure, not a misread
                old, new = ours_t[i1:i2], their_t[j1:j2]
                span = _unique_span(p.body, old, ours_t[max(0, i1 - CONTEXT):i1], ours_t[i2:i2 + CONTEXT])
                if span is None:
                    continue
                covered.update(range(i1, i2))
                wrong, lw, rw = span
                right = " ".join(x for x in (lw, " ".join(new), rw) if x)
                context = " ".join(ours_t[max(0, i1 - 6):i2 + 6])
                choices: tuple[str, ...] = (right, wrong)
                detail = {"document": key, "section": p.number, "wrong": wrong, "right": right}
                if lexicon is None:
                    likely, evidence = _likely(old, new, vocab), (f"base: ...{context}...",)
                else:
                    readings = _readings_in(rules, i1, i2, ours_t)
                    agree = tuple(m for m, r in readings.items() if r.split() == new)
                    s = Suggestion(i1, i2, " ".join(old), " ".join(new), _fix_of(old, new), (Method.WORKING_COPY, *agree))
                    rivals = sorted({r for r in readings.values() if r.split() != new and r.split() != old})
                    likely = not rivals and tier(s) is Tier.LIKELY
                    for r in rivals:
                        choices += (" ".join(x for x in (lw, r, rw) if x),)
                    evidence = _evidence(context, {Method.WORKING_COPY: " ".join(new), **readings}, s.guard)
                    detail.update(methods=[m.value for m in s.methods], guard=s.guard, fix=s.fix.value)
                out.append(Ask(ask_id(AskKind.OCR_READING, subject, wrong), AskKind.OCR_READING, subject,
                               f'The recorded copy\'s OCR reads "{" ".join(old)}"; the working copy reads '
                               f'"{" ".join(new) or "(nothing)"}". Which does the page say?',
                               choices=(*choices, "something else (type it)"), suggestion=right, likely=likely,
                               evidence=evidence, detail=detail))
        # The rules' readings where the working copy says nothing different: the copy's own slip ("ofthe" kept), a
        # section the copy arranges differently, or no copy at all. Asked when two readers agree, or when the copy
        # keeps the OCR's reading against a confident rule; the rest are held for the record (``held``).
        for s in rules:
            if any(k in covered for k in range(s.start, s.end)):
                continue
            copy_agrees = all(k in same for k in range(s.start, s.end))
            likely = not copy_agrees and tier(s) is Tier.LIKELY
            if not likely and not (copy_agrees and s.confidence >= 0.9):
                if held is not None:
                    held.append((p.number, s))
                continue
            span = _unique_span(p.body, ours_t[s.start:s.end], ours_t[max(0, s.start - CONTEXT):s.start],
                                ours_t[s.end:s.end + CONTEXT])
            if span is None:
                continue
            wrong, lw, rw = span
            right = " ".join(x for x in (lw, s.right, rw) if x)
            context = " ".join(ours_t[max(0, s.start - 6):s.end + 6])
            readings = {m: s.right for m in s.methods}
            if copy_agrees:
                readings[Method.WORKING_COPY] = s.wrong
            who = "the OCR and the working copy read" if copy_agrees else "the OCR reads"
            out.append(Ask(ask_id(AskKind.OCR_READING, subject, wrong + "|" + s.right), AskKind.OCR_READING, subject,
                           f'{who[0].upper()}{who[1:]} "{s.wrong}"; {", ".join(m.value for m in s.methods)} '
                           f'read{"s" if len(s.methods) == 1 else ""} "{s.right or "(nothing)"}". Which does the page say?',
                           choices=(right, wrong, "something else (type it)"), suggestion=right, likely=likely,
                           evidence=_evidence(context, readings, s.guard),
                           detail={"document": key, "section": p.number, "wrong": wrong, "right": right,
                                   "methods": [m.value for m in s.methods], "guard": s.guard, "fix": s.fix.value,
                                   "confidence": s.confidence}))
    return out


def living_asks(built: Any, placed: list | None = None) -> list[Ask]:
    """The findings of a living document's build that a person decides."""
    from jason.community.living import FindingKind, Placement

    key = built.living.key
    out = []
    kinds = {FindingKind.BEFORE_DIFFERS: (AskKind.BEFORE_DIFFERS,
                                          "The amendment's before words differ from the document's. Did the drafter "
                                          "change words without marking them, or is a copy misread?",
                                          ("changed without marks: ask counsel", "a copy is misread: transcribe it",
                                           "noted: no action")),
             FindingKind.READINGS_DIFFER: (AskKind.READINGS_DIFFER,
                                           "Two copies of the instrument give different words. Which does the recorded "
                                           "copy say?", ("the recorded scan", "the other reading", "neither: transcribe")),
             FindingKind.HELD: (AskKind.HELD_SOURCE, "A source was not read. Review the changed file (and pin its new "
                                "digest) or fetch it.", ("reviewed: pin the new digest", "fetch it", "noted"))}
    for f in built.current.findings:
        if f.kind not in kinds:
            continue
        kind, question, choices = kinds[f.kind]
        subject = f"{key}#{f.section}" if f.section else f"{key}@{f.instrument}"
        out.append(Ask(ask_id(kind, subject, f.detail), kind, subject, question, choices=choices,
                       evidence=(f.line(),), detail={"document": key, "section": f.section, "instrument": f.instrument}))
    for f in built.drift:
        if f.kind is not FindingKind.DRIFT:
            continue
        subject = f"{key}#{f.section}"
        out.append(Ask(ask_id(AskKind.DRIFT, subject, f.detail), AskKind.DRIFT, subject,
                       "The working copy differs from the current text in a section an amendment set. Fix the working "
                       "copy, or is the difference a correction to record?",
                       choices=("fix the working copy", "record a correction", "ask counsel"),
                       suggestion="fix the working copy", evidence=(f.detail,),
                       detail={"document": key, "section": f.section}))
    for p, _ in placed or []:
        if p.placement is not Placement.ORPHANED:
            continue
        a = p.annotation
        subject = f"{key}#{a.section or '?'}"
        out.append(Ask(ask_id(AskKind.ORPHANED_NOTE, subject, a.source), AskKind.ORPHANED_NOTE, subject,
                       "A note's words are gone from the text. Re-anchor it to a section, keep it as a general note, "
                       "or resolve it?", choices=("re-anchor (name the section)", "keep as a general note", "resolve it"),
                       evidence=(f'{a.kind.value}: "{a.text[:160]}"' + (f' on "{a.quote[:80]}"' if a.quote else ""),),
                       detail={"document": key, "source": a.source}))
    return out


def library_asks(data_dir: Path) -> list[Ask]:
    """Library files no rule classified, with the evidence a person needs to choose."""
    import sqlite3

    db = Path(data_dir) / "library" / "library.db"
    if not db.is_file():
        return []
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT id, path, kind, method, evidence FROM documents "
                            "WHERE kind IS NULL OR kind = '' OR method = 'NONE'").fetchall()
    out = []
    for doc_id, path, kind, method, evidence in rows:
        text = Path(data_dir) / "library" / "text" / f"{doc_id}.txt"
        head = " ".join(text.read_text(encoding="utf-8", errors="replace").split()[:40]) if text.is_file() else ""
        subject = f"library:{path}"
        out.append(Ask(ask_id(AskKind.CLASSIFY, subject, ""), AskKind.CLASSIFY, subject,
                       "No rule classified this file. Which kind of document is it? (a DocumentKind value, e.g. "
                       "minutes, policy, contract; or 'dismiss')",
                       evidence=tuple(x for x in (f"path: {path}", f"begins: {head}" if head else "no text read",
                                                  evidence or "") if x),
                       detail={"path": path}))
    return out


def apply(asks: list[Ask], data_dir: Path, *, refused: list | None = None, shown: list | None = None,
          replace: bool = False, community: Any = None, profile: str = "", spec_dir: Path | None = None) -> list[Ask]:
    """Turn answered asks into the records runs use. Returns the asks applied.

    A high-stakes answer (``intake.high_stakes``) is refused until a second person has confirmed it. A ``FACT`` or
    ``MAP`` answer goes through ``jason.tasks.onboarding_answers``: private facts merged (with a backup; ``replace``
    lets a different answer replace one already there), a Keeper record named, or a proposed profile change written.
    ``refused`` collects (ask, why) for those not applied, ``shown`` (ask, text) for the diffs and proposals."""
    from jason.community.intake import high_stakes
    from jason.community.symbols import DocumentKind
    from jason.tasks import library as library_task
    from jason.tasks import living_docs

    done = []
    for a in asks:
        if a.status is not AskStatus.ANSWERED:
            continue
        if high_stakes(a) and not a.confirmed_by:
            if refused is not None:
                refused.append((a, "high stakes: a second person confirms it first (--confirm ID --by NAME)"))
            continue
        if a.kind in (AskKind.FACT, AskKind.MAP):
            from jason.tasks.onboarding_answers import apply_answer

            out = apply_answer(a, data_dir=data_dir, community=community, profile=profile, spec_dir=spec_dir,
                               replace=replace)
            if not out.applied:
                if refused is not None:
                    refused.append((a, out.reason))
                continue
            a.status, a.applied_to = AskStatus.APPLIED, out.record
            if shown is not None and out.shown:
                shown.append((a, out.shown))
            done.append(a)
        elif a.kind is AskKind.OCR_READING:
            d = a.detail
            right = a.answer
            if right == d["wrong"]:
                a.status, a.applied_to = AskStatus.APPLIED, "kept as read"
            else:
                living_docs.add_transcription(data_dir, d["document"], d["section"], d["wrong"], right,
                                              source=f"the recorded page, read by {a.answered_by} ({a.answered_at[:10]})")
                a.status, a.applied_to = AskStatus.APPLIED, f"transcription in {d['document']} {d['section']}"
            done.append(a)
        elif a.kind is AskKind.CLASSIFY:
            try:
                kind = DocumentKind(a.answer.strip().lower())
            except ValueError:
                continue                              # not a kind's value: left answered for a person to fix
            library_task.set_person_kind(data_dir, a.detail["path"], kind.value, a.answered_by)
            a.status, a.applied_to = AskStatus.APPLIED, f"library kind {kind.value} (re-run jason library)"
            done.append(a)
        elif a.kind is AskKind.APPLICABILITY:
            # The answer is the record: the next evaluation reads it as a fact (source ANSWER). Applying checks that
            # it reads as the fact, and writes nothing else.
            from jason.community.applicability_asks import applied_note

            ok, note = applied_note(a)
            if not ok:
                if refused is not None:
                    refused.append((a, note))
                continue
            a.status, a.applied_to = AskStatus.APPLIED, note
            done.append(a)
    return done


def accept_likely(asks: list[Ask], by: str, *, kind: AskKind = AskKind.OCR_READING) -> list[Ask]:
    """Answer every open ``likely`` ask of a kind with its suggestion, in the name of the person who looked."""
    from jason.community.intake import answer

    if not by:
        raise ValueError("a batch answer names the person who accepted it")
    return [answer(asks, a.id, a.suggestion, by) for a in asks
            if a.status is AskStatus.OPEN and a.likely and a.kind is kind and a.suggestion]


__all__ = ["accept_likely", "apply", "library_asks", "living_asks", "ocr_reading_asks", "vocabulary"]
