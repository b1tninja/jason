"""Living documents: a governing document as amended, section by section, with the instrument that last set each one.

An amendment changes a governing document in its own words: "Section 4.2 is hereby amended and restated as follows",
"is amended to add the following subsection", "is hereby removed". Many print the change itself in type: a legend such
as "(stricken out wording will be removed, and bolded wording will be added)" and then the section with the removed
words struck through and the added words in bold. A plain-text copy loses the marks and reads both versions run
together ("twenty percent (20%) twenty-five (25%)"), so the marks are read from a source that keeps them: a Google
Doc's text runs (``textStyle.strikethrough``, ``bold``, ``underline``) or a text PDF's spans and drawn rules.

``Operation`` is one change: a section, a ``Verb``, and the instrument's words for the section as ``Run``s with their
``Mark``. Its ``before`` (plain and struck words) is the text the instrument says it changes; its ``after`` (plain and
added words) is the text it sets. ``Instrument`` is an amendment's operations with its ``Standing`` (draft, adopted,
recorded) and dates. ``consolidate`` applies the operations of every instrument in effect, in order, to the base
document's outline and returns a ``CurrentDocument``: each ``Provision`` with its caption, its words, and its history.

A reading is evidence: the operations are read from the instrument's text, and whether an instrument has taken effect
is the specification's (a person pins its standing). A miss stays a miss: an operation whose section is not there, or
whose instrument promises marks this copy does not carry, is not applied; it is a finding. A "before" that differs from
the base is applied (the instrument's restated words are what it adopts) and reported, since it means the base copy
and the copy the drafter worked from disagree.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from typing import Any

from jason.community.outlines import DocumentOutline, _paragraphs, normalize_number
from jason.community.symbols import DocumentKind


class Mark(Enum):
    PLAIN = "plain"
    STRUCK = "struck"        # removed by the instrument
    ADDED = "added"          # added by the instrument (bold or underlined, as its legend says)


@dataclass(frozen=True)
class Run:
    text: str
    mark: Mark = Mark.PLAIN


@dataclass(frozen=True)
class StyledRun:
    """A run of text as the source draws it, before the instrument's legend says what the styles mean."""

    text: str
    struck: bool = False
    bold: bool = False
    underlined: bool = False


class Verb(Enum):
    RESTATE = "restate"      # "is hereby amended and restated as follows", "is amended to read"
    ADD = "add"              # "is amended to add the following subsection", "is hereby added"
    REMOVE = "remove"        # "is hereby removed", "deleted", "repealed"


class Standing(Enum):
    DRAFT = "draft"          # unsigned or undated: never applies
    ADOPTED = "adopted"      # approved by the board or the members; not recorded
    RECORDED = "recorded"    # recorded; its number and date are on the county's stamp


class Effect(Enum):
    """When an amendment to a kind of document takes effect."""

    ON_RECORDING = "on recording"     # the declaration: approved, certified, and recorded (Civil Code 4270(a))
    ON_ADOPTION = "on adoption"       # bylaws, operating rules, and policies: when adopted, or on the date they state


_ON_RECORDING = frozenset({DocumentKind.DECLARATION, DocumentKind.ANNEXATION})


def effect_of(kind: DocumentKind | str | None) -> Effect:
    """A declaration (and an annexation, part of it) changes only on recording; any other document on adoption."""
    try:
        kind = DocumentKind(kind) if kind else None
    except ValueError:
        kind = None
    return Effect.ON_RECORDING if kind in _ON_RECORDING else Effect.ON_ADOPTION


def _join(texts: Iterable[str]) -> str:
    """Runs joined, without the doubled space (or the space before a period) a dropped run leaves between its
    neighbours. Only the seams change; the words inside a run stay as the instrument prints them."""
    out = ""
    for text in texts:
        if out[-1:] in (" ", "\t") and text[:1] in (" ", "\t"):
            text = text.lstrip(" \t")
        elif out[-1:] in (" ", "\t") and text[:1] in (".", ",", ";", ":"):
            out = out.rstrip(" \t")
        out += text
    return out.strip()


@dataclass(frozen=True)
class Operation:
    section: str                       # "4.2(b)", as documents cite it
    verb: Verb
    runs: tuple[Run, ...] = ()         # the instrument's words for the section, with their marks
    caption: str = ""                  # the section's caption as the instruction quotes it
    instruction: str = ""              # the instruction's own words
    marks_lost: bool = False           # the legend says marks carry the change, and this copy has none
    struck_by_ocr: bool = False        # the struck words were read by OCR through the strike: their letters are noise

    @property
    def before(self) -> str:
        return _join(r.text for r in self.runs if r.mark is not Mark.ADDED)

    @property
    def after(self) -> str:
        return _join(r.text for r in self.runs if r.mark is not Mark.STRUCK)

    @property
    def marked(self) -> bool:
        return any(r.mark is not Mark.PLAIN for r in self.runs)

    def redline(self) -> str:
        """The words with their marks as text: ``~~struck~~`` and ``**added**``."""
        out = []
        for r in self.runs:
            core = r.text.strip()
            if r.mark is Mark.PLAIN or not core:
                out.append(r.text)
                continue
            lead, trail = r.text[: len(r.text) - len(r.text.lstrip())], r.text[len(r.text.rstrip()):]
            fence = "~~" if r.mark is Mark.STRUCK else "**"
            out.append(f"{lead}{fence}{core}{fence}{trail}")
        return "".join(out)


@dataclass(frozen=True)
class Instrument:
    """An amendment: its operations, its standing, and its dates. ``amends`` is the outline key of the document."""

    key: str
    amends: str
    standing: Standing
    operations: tuple[Operation, ...] = ()
    title: str = ""
    adopted: date | None = None
    recorded: date | None = None
    number: str = ""                   # the recorder's document number
    effective: date | None = None      # a later date the instrument says it takes effect

    @property
    def dated(self) -> date | None:
        return self.effective or self.recorded or self.adopted

    def in_effect(self, effect: Effect, as_of: date | None = None) -> bool:
        if effect is Effect.ON_RECORDING:
            took = self.standing is Standing.RECORDED and self.recorded is not None
        else:
            took = self.standing in (Standing.ADOPTED, Standing.RECORDED)
        if not took:
            return False
        return as_of is None or self.dated is None or self.dated <= as_of

    def describe(self) -> str:
        name = self.title or self.key
        if self.standing is Standing.RECORDED:
            return f"{name}, recorded {self.recorded or '(date unknown)'}" + (f" as No. {self.number}" if self.number else "")
        if self.standing is Standing.ADOPTED:
            return f"{name}, adopted {self.adopted or '(date unknown)'}, not recorded"
        return f"{name} (draft)"


# Reading the operations.

_OPERATIVE = re.compile(r"\bNOW,?\s+THEREFORE\b", re.I)
# OCR drops letters here too ("N. WITNESS WHEREOF").
_WITNESS = re.compile(r"^\W*(?:\S{1,3}\s+)?WITNESS\s+WHEREOF\b", re.I)
# The instrument's own next article ("2. Miscellaneous.") ends the words of the operation before it.
_OWN_ARTICLE = re.compile(r"^\W*\d{1,2}\.\s+[A-Z][A-Za-z ]{2,40}\.(?:\s|$)")
# "(stricken out wording will be removed, and bolded wording will be added)". The legend's own example word is often
# struck through itself, so a scan's OCR garbles it ("st#eker out wording"); "wording will be removed" still reads.
_LEGEND = re.compile(r"(?:stricken|struck|strike-?\s?through|strikeout|\b(?:wording|words|language|text)\s+(?:will\s+be|is)\s+"
                     r"(?:removed|deleted))[^.:]{0,80}?(bold(?:ed|face)?|underlin\w*)", re.I)
_VERB = re.compile(
    r"\b(?:is|are|shall\s+be)\s+(?:hereby\s+)?"
    r"(amended\s+and\s+restated|amended\s+to\s+add|amended\s+to\s+read|restated|amended|added|removed|deleted|repealed)\b",
    re.I)
_SECTION = re.compile(r"\bSections?\s+(\d+(?:\.\d+)+)((?:\s*\(\s*[a-z0-9]{1,5}\s*\))*)", re.I)
_SUBPART = re.compile(r"\b(?:subsection|subpart|paragraph|subparagraph|clause)\s*\(\s*([a-z0-9]{1,5})\s*\)", re.I)
_CAPTION = re.compile(r"[\"“]([^\"“”]{2,90}?)[\"”]")
_LEADING_TOKEN = re.compile(r"^\s*\(\s*([a-z0-9]{1,5})\s*\)\s*", re.I)
_LEADING_LABEL = re.compile(r"^\s*(?:\(\s*[a-z0-9]{1,5}\s*\)|\d+(?:\.\d+)+\.?(?=\s))\s*", re.I)
_INLINE_CAPTION = re.compile(r"^((?:[A-Z][\w'’&/-]*)(?:\s+(?:[A-Z][\w'’&/-]*|of|on|the|and|or|to|for|in|a|an|by|with)){0,12}\.)\s+")


def _verb(word: str) -> Verb:
    word = re.sub(r"\s+", " ", word.lower())
    if word in ("amended to add", "added"):
        return Verb.ADD
    if word in ("removed", "deleted", "repealed"):
        return Verb.REMOVE
    return Verb.RESTATE


def read_instruction(text: str) -> tuple[str, Verb, str] | None:
    """The section, verb, and quoted caption of one instruction ("Section 4.2 (“Use”), subsection (b) is hereby
    removed"), or None when the text gives no section and verb."""
    verb = _VERB.search(text)
    if not verb:
        return None
    head = text[: verb.start()]
    found = list(_SECTION.finditer(head))
    if not found:
        return None
    m = found[-1]
    number = m.group(1) + re.sub(r"\s+", "", m.group(2) or "")
    for sub in _SUBPART.finditer(head[m.end():]):
        number += f"({sub.group(1).lower()})"
    captions = _CAPTION.findall(head[m.end():])
    caption = captions[-1].strip() if captions else ""
    return normalize_number(number), _verb(verb.group(1)), caption


def legend(paragraphs: Sequence[Sequence[StyledRun]]) -> str:
    """What the instrument says marks an addition ("bold" or "underline"); empty when it gives no legend."""
    for runs in paragraphs:
        if m := _LEGEND.search("".join(r.text for r in runs)):
            return "underline" if m.group(1).lower().startswith("underlin") else "bold"
    return ""


def _mark(run: StyledRun, added_by: str) -> Mark:
    if not added_by:
        return Mark.PLAIN
    if run.struck:
        return Mark.STRUCK
    if (added_by == "bold" and run.bold) or (added_by == "underline" and run.underlined):
        return Mark.ADDED
    return Mark.PLAIN


def _tidy(runs: list[Run]) -> tuple[Run, ...]:
    """Merge neighbours with the same mark, and trim the whitespace around the whole."""
    merged: list[Run] = []
    for r in runs:
        if not r.text:
            continue
        # Whitespace alone between two runs reads as plain, so "~~a~~ **b**" keeps its space in both versions.
        mark = Mark.PLAIN if not r.text.strip() else r.mark
        if merged and merged[-1].mark is mark:
            merged[-1] = Run(merged[-1].text + r.text, mark)
        else:
            merged.append(Run(r.text, mark))
    while merged and not merged[0].text.strip():
        merged.pop(0)
    while merged and not merged[-1].text.strip():
        merged.pop()
    if merged:
        merged[0] = Run(merged[0].text.lstrip(), merged[0].mark)
        merged[-1] = Run(merged[-1].text.rstrip(), merged[-1].mark)
    return tuple(merged)


def read_operations(paragraphs: Iterable[Sequence[StyledRun]], *, styled: bool = True) -> tuple[Operation, ...]:
    """The operations in an instrument's operative part (from "NOW, THEREFORE" to "IN WITNESS WHEREOF").

    Each instruction paragraph opens an operation; the paragraphs after it, up to the next instruction, are its words.
    ``styled`` says whether the source keeps type styles (a Doc, a text PDF) or not (plain text, OCR). An instruction
    with no words (an umbrella "Section 4.15 is amended as follows") is dropped unless it removes."""
    paragraphs = [list(p) for p in paragraphs]
    added_by = legend(paragraphs) if styled else ""
    has_legend = bool(legend(paragraphs))
    ops: list[Operation] = []
    pending: tuple[str, Verb, str, str] | None = None
    body: list[Run] = []
    started = False

    def flush() -> None:
        if pending is None:
            return
        section, verb, caption, instruction = pending
        runs = _tidy(body)
        if verb is Verb.ADD and runs and not caption:
            # "is amended to add the following subsection: (o) Caption. Words": the number and caption lead the words.
            text = runs[0].text
            if m := _LEADING_TOKEN.match(text):
                # No subsection is numbered zero: "(0)" is OCR's "(o)".
                token = "o" if m.group(1) == "0" else m.group(1).lower()
                section = normalize_number(f"{section}({token})")
                text = text[m.end():]
            if c := _INLINE_CAPTION.match(text):
                caption, text = c.group(1), text[c.end():]
            runs = _tidy([Run(text, runs[0].mark), *runs[1:]])
        if not runs and verb is not Verb.REMOVE:
            return
        lost = has_legend and not added_by and verb is Verb.RESTATE
        ops.append(Operation(section, verb, runs, caption, instruction, lost))

    for runs in paragraphs:
        text = "".join(r.text for r in runs).strip()
        if not text:
            continue
        if not started:
            if not _OPERATIVE.search(text):
                continue
            started = True
        if _WITNESS.match(text):
            break
        if found := read_instruction(text):
            flush()
            pending, body = (*found, text), []
            continue
        if _OWN_ARTICLE.match(text):
            flush()
            pending, body = None, []
            continue
        if pending is not None:
            if body:
                body.append(Run("\n"))
            first = True
            for r in runs:
                t = r.text.lstrip("\t") if first else r.text
                first = False
                body.append(Run(t.replace("\n", ""), _mark(r, added_by)))
    flush()
    return tuple(ops)


def doc_paragraphs(doc: dict[str, Any]) -> Iterator[list[StyledRun]]:
    """A Google Doc's paragraphs (the Docs API's document) as styled runs."""
    tab = ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc
    for p in _paragraphs(tab.get("body", {}).get("content", [])):
        runs = []
        for e in p.get("elements", []):
            run = e.get("textRun")
            if not run:
                continue
            style = run.get("textStyle", {})
            runs.append(StyledRun(run.get("content", ""), bool(style.get("strikethrough")), bool(style.get("bold")),
                                  bool(style.get("underline"))))
        yield runs


def text_paragraphs(text: str) -> Iterator[list[StyledRun]]:
    """Plain text (an extract, OCR) as paragraphs split on blank lines, one unstyled run each."""
    for block in re.split(r"\n\s*\n", text):
        joined = re.sub(r"-\s*\n\s*(?=[a-z])", "", block)
        joined = re.sub(r"\s*\n\s*", " ", joined).strip()
        if joined:
            yield [StyledRun(joined)]


def operations_from_doc(doc: dict[str, Any]) -> tuple[Operation, ...]:
    return read_operations(doc_paragraphs(doc), styled=True)


def operations_from_text(text: str) -> tuple[Operation, ...]:
    return read_operations(text_paragraphs(text), styled=False)


# Applying them.


class FindingKind(Enum):
    NOT_IN_EFFECT = "not in effect"          # a draft, or not yet recorded: listed, not applied
    MARKS_LOST = "marks lost"                # the legend says marks carry the change; this copy has none
    TARGET_MISSING = "target missing"        # restates or removes a section the document does not have
    BEFORE_DIFFERS = "before differs"        # the words the instrument shows as before are not the base's
    QUOTED_ELSEWHERE = "quoted elsewhere"    # its before words are another section's
    ALREADY_PRESENT = "already present"      # adds a section the document already has, with other words
    ALREADY_APPLIED = "already applied"      # the base reads closer to the after words: a copy amended by hand
    NO_CHANGE = "no change"                  # the restated words are the section's words already
    SUBSECTIONS_REPLACED = "subsections replaced"   # a restated section's subsections give way to its new words
    DRIFT = "drift"                          # a copy of the document differs from the consolidated text
    EDITORIAL = "editorial note"             # a copy carries an editor's bracketed note among the words
    CORRECTION_REFUSED = "correction refused"   # an editorial fix that would change meaning
    CORRECTION_STALE = "correction stale"    # its wrong words are no longer in the section
    READINGS_DIFFER = "readings differ"      # two copies of one instrument give different words for a section
    HELD = "held"                            # a source not read (changed since review, or not fetched)


@dataclass(frozen=True)
class AmendmentFinding:
    kind: FindingKind
    section: str
    instrument: str
    detail: str = ""

    def line(self) -> str:
        where = f"{self.section}: " if self.section else ""
        return f"{self.kind.value}: {where}{self.instrument}" + (f"; {self.detail}" if self.detail else "")


@dataclass
class Provision:
    """One section of the current document: its own words (not its subsections'), and who set them."""

    number: str
    caption: str
    body: str
    depth: int
    set_by: str                         # the base document's key, or the instrument's
    dated: date | None = None
    standing: Standing | None = None    # None for the base
    history: list[str] = field(default_factory=list)   # "base", then "<instrument>: restate", in order
    removed: bool = False


@dataclass
class CurrentDocument:
    key: str
    title: str
    base: str                           # where the base text came from (a Doc's revision, a recorded copy)
    provisions: list[Provision]
    applied: list[Instrument] = field(default_factory=list)
    pending: list[Instrument] = field(default_factory=list)
    findings: list[AmendmentFinding] = field(default_factory=list)

    @property
    def through(self) -> Instrument | None:
        return self.applied[-1] if self.applied else None

    def provision(self, number: str) -> Provision | None:
        wanted = normalize_number(number)
        return next((p for p in self.provisions if p.number == wanted), None)

    def text_of(self, number: str) -> str:
        """A section's words with its subsections', as one text."""
        at = _index(self.provisions, normalize_number(number))
        if at is None:
            return ""
        parts = []
        for p in self.provisions[at: _subtree_end(self.provisions, at)]:
            if not p.removed:
                parts.append("\n".join(x for x in (p.caption, p.body) if x))
        return "\n".join(parts)

    def markdown(self) -> str:
        """The document as amended, each section set by an amendment marked with that amendment."""
        lines = [f"# {self.title}", ""]
        through = self.through
        lines.append(f"As amended through the {through.describe()}." if through else "As written; no amendment in effect.")
        lines += ["", f"Base text: {self.base}. Consolidated by jason from the instruments' own words; it is not an "
                  "official restatement, and the recorded instruments control.", ""]
        for p in self.provisions:
            if not p.number and not p.body.strip():
                continue
            head = " ".join(x for x in (p.number, p.caption) if x)
            if p.removed:
                lines += [f"**{head}** _(removed by {p.set_by})_", ""]
                continue
            if head:
                lines.append(f"**{head}**")
            if p.body.strip():
                lines.append(p.body.strip())
            if p.standing is not None:
                lines.append(f"> _{p.number}: {p.history[-1]}{f', {p.dated}' if p.dated else ''}._")
            lines.append("")
        if self.pending:
            lines += ["## Not in effect", ""] + [f"- {i.describe()}: {', '.join(o.section for o in i.operations)}"
                                                 for i in self.pending] + [""]
        return "\n".join(lines)


def _norm(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = re.sub(r"-\s*\n\s*(?=[a-z])", "", text)
    return re.sub(r"\s+", " ", text).strip()


def word_changes(base: str, other: str, *, context: int = 2, limit: int = 4) -> list[str]:
    """How ``other`` differs from ``base``, word by word: ``"leased or [rented or] occupied" -> "leased or occupied"``."""
    a, b = _norm(base).split(" "), _norm(other).split(" ")
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        before = " ".join(a[max(0, i1 - context): i1])
        after = " ".join(a[i2: i2 + context])
        old, new = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        out.append(f'"{before} [{old}] {after}" -> "{before} [{new}] {after}"'.replace("  ", " "))
        if len(out) >= limit:
            break
    return out


def _depth(number: str) -> int:
    return 1 + number.count(".") + number.count("(")


def _descends(number: str, ancestor: str) -> bool:
    return bool(number) and number != ancestor and (number.startswith(ancestor + "(") or number.startswith(ancestor + "."))


def _index(provisions: list[Provision], number: str) -> int | None:
    return next((k for k, p in enumerate(provisions) if p.number == number), None)


def _subtree_end(provisions: list[Provision], at: int) -> int:
    number = provisions[at].number
    end = at + 1
    while end < len(provisions) and _descends(provisions[end].number, number):
        end += 1
    return end


def _split_caption(own: str, title: str) -> tuple[str, str]:
    """A section's caption and its words. A Doc puts the caption on its own line; an extract runs it into the words."""
    own = _LEADING_LABEL.sub("", own.lstrip(), count=1)
    first, newline, rest = own.partition("\n")
    # A caption line is the heading alone: no sentence runs on after its period.
    lone = not re.search(r"\.\s+\S", first.strip())
    if newline and lone and title and first.strip() == title.strip() and rest.strip():
        return first.strip(), rest.strip()
    if m := _INLINE_CAPTION.match(own):
        return m.group(1), own[m.end():].strip()
    return "", own.strip()


def provisions_of(outline: DocumentOutline) -> list[Provision]:
    """The outline as provisions: the preamble, then each section's own words up to the next section."""
    sections = sorted(outline.sections, key=lambda s: s.start)
    out = []
    if sections and sections[0].start > 0:
        out.append(Provision("", "", outline.text[: sections[0].start].strip(), 0, outline.key, history=["base"]))
    for k, s in enumerate(sections):
        end = sections[k + 1].start if k + 1 < len(sections) else len(outline.text)
        own = outline.text[s.start:end]
        # A Doc's leaf list item is its own title (truncated to 90); only a heading line is a caption.
        caption, body = _split_caption(own, s.title)
        out.append(Provision(s.number, caption, body, s.depth, outline.key, history=["base"]))
    return out


def consolidate(base: DocumentOutline, instruments: Sequence[Instrument], *, as_of: date | None = None,
                effect: Effect | None = None, base_from: str = "",
                corrections: Sequence[Correction] = ()) -> CurrentDocument:
    """Apply the operations of every instrument in effect, in the order of their dates (then as given), with the
    editorial corrections around them (``correct``)."""
    effect = effect or effect_of(base.kind)
    provisions = provisions_of(base)
    current = CurrentDocument(base.key, base.title, base_from or (f"revision {base.revision}" if base.revision else base.key),
                              provisions)
    left = correct(current, corrections, final=False)
    ordered = sorted(enumerate(instruments), key=lambda pair: (pair[1].dated or date.max, pair[0]))
    for _, instrument in ordered:
        if instrument.amends and instrument.amends != base.key:
            continue
        if not instrument.in_effect(effect, as_of):
            current.pending.append(instrument)
            current.findings.append(AmendmentFinding(FindingKind.NOT_IN_EFFECT, "", instrument.key,
                                                     f"{instrument.standing.value}; takes effect {effect.value}"))
            continue
        for op in instrument.operations:
            _apply(current, instrument, op)
        current.applied.append(instrument)
    correct(current, left, final=True)
    return current


def _apply(current: CurrentDocument, instrument: Instrument, op: Operation) -> None:
    provisions, key = current.provisions, instrument.key

    def find(kind: FindingKind, detail: str = "") -> None:
        current.findings.append(AmendmentFinding(kind, op.section, key, detail))

    if op.marks_lost:
        find(FindingKind.MARKS_LOST, "read the marks from a copy that keeps them (the Doc, or a text PDF)")
        return
    at = _index(provisions, op.section)
    stamp = dict(set_by=key, dated=instrument.dated, standing=instrument.standing)
    if op.verb is Verb.ADD:
        if at is not None:
            if _norm(provisions[at].body) != _norm(op.after):
                find(FindingKind.ALREADY_PRESENT, "; ".join(word_changes(provisions[at].body, op.after)))
            end = _subtree_end(provisions, at)
            del provisions[at + 1: end]
            provisions[at] = replace(provisions[at], body=op.after, caption=op.caption or provisions[at].caption,
                                     history=[*provisions[at].history, f"{key}: add"], removed=False, **stamp)
            _split_lines(provisions, at)
            return
        parent = op.section[: op.section.rfind("(")] if "(" in op.section else op.section.rsplit(".", 1)[0]
        p_at = _index(provisions, parent)
        if p_at is None:
            find(FindingKind.TARGET_MISSING, f"no section {parent} to add it to")
            return
        insert = _subtree_end(provisions, p_at)
        provisions.insert(insert, Provision(op.section, op.caption, op.after, _depth(op.section),
                                            history=[f"{key}: add"], **stamp))
        _split_lines(provisions, insert)
        return
    if at is None and _split_inline(provisions, op.section):
        at = _index(provisions, op.section)
    if at is None:
        where = _quoted_at(provisions, op.before) if op.marked else ""
        find(FindingKind.TARGET_MISSING, f"its before words are {where}'s" if where else "")
        return
    target = provisions[at]
    if op.marked and _norm(op.before) != _norm(target.body):
        where = _quoted_at(provisions, op.before)
        if where and where != op.section:
            find(FindingKind.QUOTED_ELSEWHERE, f"its before words are {where}'s")
        if _ratio(target.body, op.after) > _ratio(target.body, op.before):
            find(FindingKind.ALREADY_APPLIED, "the base reads closer to the instrument's after words than its before "
                 "words: a copy amended by hand")
        changes = _before_changes(target.body, op)
        if changes:
            find(FindingKind.BEFORE_DIFFERS, "; ".join(changes))
    if op.verb is Verb.RESTATE and _norm(op.after) == _norm(target.body):
        find(FindingKind.NO_CHANGE)
    end = _subtree_end(provisions, at)
    if op.verb is Verb.REMOVE:
        removed = not op.after.strip()
        provisions[at] = replace(target, body=op.after, removed=removed, history=[*target.history, f"{key}: remove"], **stamp)
        del provisions[at + 1: end]
        return
    if end > at + 1:
        find(FindingKind.SUBSECTIONS_REPLACED, ", ".join(p.number for p in provisions[at + 1: end]))
        del provisions[at + 1: end]
    provisions[at] = replace(target, body=op.after, caption=target.caption or op.caption,
                             history=[*target.history, f"{key}: {op.verb.value}"], **stamp)
    _split_lines(provisions, at)


_STRUCK = "\x00struck"


def _before_changes(body: str, op: Operation, *, limit: int = 4) -> list[str]:
    """How the instrument's before words differ from the section's. When the struck words were read by OCR through the
    strike, they stand in for whatever the section says there: only a difference in the plain words is reported."""
    if not op.struck_by_ocr:
        return word_changes(body, op.before)
    ours = _norm(body).split(" ")
    theirs: list[str] = []
    for r in op.runs:
        if r.mark is Mark.ADDED:
            continue
        words = _norm(r.text).split(" ") if _norm(r.text) else []
        theirs += [_STRUCK] * len(words) if r.mark is Mark.STRUCK else words
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=ours, b=theirs, autojunk=False).get_opcodes():
        if tag == "equal" or (j2 > j1 and all(w == _STRUCK for w in theirs[j1:j2])):
            continue
        before, after = " ".join(ours[max(0, i1 - 2): i1]), " ".join(ours[i2: i2 + 2])
        new = " ".join("~struck~" if w == _STRUCK else w for w in theirs[j1:j2])
        out.append(f'"{before} [{" ".join(ours[i1:i2])}] {after}" -> "{before} [{new}] {after}"'.replace("  ", " "))
        if len(out) >= limit:
            break
    return out


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(a=_norm(a).split(" "), b=_norm(b).split(" "), autojunk=False).ratio()


_ROMANS = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv")


def _series(token: str) -> tuple[str, ...]:
    """The labels of the series a subsection token belongs to: (i), (ii), ...; (a), (b), ...; (1), (2), ..."""
    if token.isdigit():
        return tuple(str(n) for n in range(1, 41))
    if token in _ROMANS and token not in ("v", "x"):
        return _ROMANS
    return tuple(chr(c) for c in range(ord("a"), ord("z") + 1))


def _split_inline(provisions: list[Provision], number: str) -> bool:
    """Split a section whose subsections run inline ("... expressly provide (i) that ..., (ii) that ..., and (iii)
    that ...") into its subsections, when the one wanted is among them. A section already split stays as it is."""
    if "(" not in number:
        return False
    parent, token = number[: number.rfind("(")], number[number.rfind("(") + 1: -1]
    p_at = _index(provisions, parent)
    if p_at is None or _subtree_end(provisions, p_at) > p_at + 1:
        return False
    return _split(provisions, p_at, _series(token), wanted=token, line_start=False)


def _split_lines(provisions: list[Provision], at: int) -> None:
    """Split the subsections an instrument's new words list a line each ("...that is:\\n(i) encumbered...")."""
    for series in (_ROMANS, tuple(chr(c) for c in range(ord("a"), ord("z") + 1)), tuple(str(n) for n in range(1, 41))):
        if _split(provisions, at, series, wanted=series[0], line_start=True):
            return


def _split(provisions: list[Provision], p_at: int, series: tuple[str, ...], *, wanted: str, line_start: bool) -> bool:
    parent = provisions[p_at].number
    body = provisions[p_at].body
    lead = r"(?:(?<=\n)|^)[ \t]*" if line_start else r"(?:(?<=\s)|^)"
    starts: list[tuple[str, int, int]] = []
    pos = 0
    for label in series:
        m = re.compile(lead + r"\(\s*" + re.escape(label) + r"\s*\)\s+").search(body, pos)
        if not m:
            break
        starts.append((label, m.start(), m.end()))
        pos = m.end()
    if wanted not in {label for label, _, _ in starts}:
        return False
    head = body[: starts[0][1]].strip()
    parent_row = provisions[p_at]
    children = []
    for k, (label, _, end) in enumerate(starts):
        stop = starts[k + 1][1] if k + 1 < len(starts) else len(body)
        children.append(Provision(f"{parent}({label})", "", body[end:stop].strip().rstrip(",").strip(),
                                  parent_row.depth + 1, parent_row.set_by, parent_row.dated, parent_row.standing,
                                  [*parent_row.history, "split inline"]))
    provisions[p_at] = replace(parent_row, body=head)
    provisions[p_at + 1: p_at + 1] = children
    return True


def _quoted_at(provisions: list[Provision], words: str) -> str:
    """The section whose words are closest to ``words``, when close (a ratio of 0.9 or more)."""
    wanted = _norm(words)
    best, score = "", 0.0
    for p in provisions:
        if not p.number or not p.body:
            continue
        ratio = difflib.SequenceMatcher(a=_norm(p.body), b=wanted, autojunk=False).ratio()
        if ratio > score:
            best, score = p.number, ratio
    return best if score >= 0.9 else ""


_EDITORIAL = re.compile(r"\[\s*([^\]\n]{1,200}?)\s*\]")


def drift(current: CurrentDocument, copy: DocumentOutline, *, label: str = "", amended_only: bool = False
          ) -> list[AmendmentFinding]:
    """Where a copy of the document (a working Doc kept by hand) differs from the consolidated text, section by
    section. A section only one side has is drift too. ``amended_only`` compares only the sections an amendment set."""
    found = []
    theirs = {p.number: p for p in provisions_of(copy) if p.number}
    ours = {p.number: p for p in current.provisions if p.number and (p.standing is not None or not amended_only)}
    if amended_only:
        theirs = {n: p for n, p in theirs.items() if n in ours}
    who = label or copy.key
    for number, other in theirs.items():
        # An editor's bracketed note ("[ Absent from the recorded text. ]") is not the instrument's words: it is
        # reported as such and left out of the comparison, so it never passes as operative text.
        for note in _EDITORIAL.findall(other.body):
            found.append(AmendmentFinding(FindingKind.EDITORIAL, number, who, note.strip()))
        if _EDITORIAL.search(other.body):
            other.body = _EDITORIAL.sub("", other.body).strip()
    for number, p in ours.items():
        other = theirs.get(number)
        if other is None:
            if not p.removed:
                found.append(AmendmentFinding(FindingKind.DRIFT, number, who, "missing from the copy"))
            continue
        if _norm(p.body) != _norm(other.body):
            found.append(AmendmentFinding(FindingKind.DRIFT, number, who, "; ".join(word_changes(p.body, other.body))))
    for number in sorted(theirs.keys() - ours.keys()):
        found.append(AmendmentFinding(FindingKind.DRIFT, number, who, "only in the copy"))
    return found


# Corrections: an editor's fix to the text as read (an OCR slip, a typo), never a change of meaning.


class CorrectionKind(Enum):
    OCR = "ocr"                      # the extract misread the page ("tenn" for "term")
    TYPO = "typo"                    # the instrument's own slip, fixed in the reading copy
    PUNCTUATION = "punctuation"
    SPACING = "spacing"


@dataclass(frozen=True)
class Correction:
    """One editorial fix to a section's words: ``wrong`` (as the text reads) becomes ``right``. It cites what was
    wrong and how it knows (``source``: the page, the recorded copy). A correction that would change a number or an
    operative word, or more than two words, is refused: that is an amendment's work, or a question for counsel."""

    section: str
    wrong: str
    right: str
    kind: CorrectionKind
    source: str = ""
    note: str = ""


# Words whose change changes what a provision requires.
_OPERATIVE_WORDS = frozenset({"not", "no", "nor", "shall", "may", "must", "will", "and", "or", "any", "all", "each",
                              "except", "unless", "only", "without", "before", "after", "more", "less", "than"})


def changes_meaning(wrong: str, right: str) -> str:
    """Why a correction from ``wrong`` to ``right`` is more than editorial; empty when it is not."""
    if re.sub(r"\s+", "", wrong) == re.sub(r"\s+", "", right):
        return ""                                    # spacing alone ("ofanyprovisions")
    if re.findall(r"\d+", wrong) != re.findall(r"\d+", right):
        return "a number changes"
    a, b = _norm(wrong).lower().split(" "), _norm(right).lower().split(" ")
    changed: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag != "equal":
            changed += a[i1:i2] + b[j1:j2]
    words = {re.sub(r"\W", "", w) for w in changed}
    if words & _OPERATIVE_WORDS:
        return f"an operative word changes ({', '.join(sorted(words & _OPERATIVE_WORDS))})"
    if len(changed) > 4:
        return "more than two words change"
    return ""


def correct(current: CurrentDocument, corrections: Sequence[Correction], *, final: bool = True) -> list[Correction]:
    """Apply editorial corrections. Each must find its ``wrong`` words exactly once in its section. ``consolidate``
    applies them to the base first (so an amendment's before words meet a clean base), then once more after the
    amendments for the rest; a correction that finds its words neither time is stale (an amendment has since
    restated the section) and reported. Returns the corrections left unapplied."""
    left = []
    for c in corrections:
        p = current.provision(c.section)
        why = changes_meaning(c.wrong, c.right)
        if why:
            current.findings.append(AmendmentFinding(FindingKind.CORRECTION_REFUSED, c.section, "correction", why))
            continue
        if p is None or p.body.count(c.wrong) != 1:
            if final:
                found = "not found" if p is None or c.wrong not in p.body else "found more than once"
                current.findings.append(AmendmentFinding(FindingKind.CORRECTION_STALE, c.section, "correction",
                                                         f'"{c.wrong}" {found}'))
            else:
                left.append(c)
            continue
        p.body = p.body.replace(c.wrong, c.right)
        p.history.append(f"correction ({c.kind.value})")
    return left


# Annotations: notes on a passage (a question, an interpretation, context) that survive regenerating the text.


class AnnotationKind(Enum):
    QUESTION = "question"
    VAGUE = "vague"                          # the provision is unclear; a candidate for a rule or a reading
    INTERPRETATION = "interpretation"        # how the board reads and applies it now
    CONTEXT = "context"                      # facts that help a reader (which streets, which district)
    DEFINITION = "definition"                # an abbreviation or term spelled out
    OUTDATED_CITATION = "outdated citation"  # cites a statute since renumbered or repealed
    POLICY_CANDIDATE = "policy candidate"    # "should be made a rule": a lead for the board
    ACTION_ITEM = "action item"              # something to do about the provision
    PROVENANCE = "provenance"                # which instrument set the words (jason computes this; a note is checked)


class Placement(Enum):
    ANCHORED = "anchored"            # the quoted words are in the section the note names
    MOVED = "moved"                  # they are in another section now
    SECTION = "section"              # a note on the whole section (no quote); the section is there
    ORPHANED = "orphaned"            # the words are gone: a finding, never silently dropped


@dataclass(frozen=True)
class Annotation:
    """A note anchored by section and quoted words, not by offset, so it survives a regenerated text. ``source`` is
    where it lives (a Doc comment's id) so a sync can update it rather than duplicate it."""

    section: str
    quote: str
    kind: AnnotationKind
    text: str
    author: str = ""
    written: date | None = None
    source: str = ""
    resolved: bool = False


@dataclass(frozen=True)
class Placed:
    annotation: Annotation
    placement: Placement
    section: str = ""                # where it sits now


def place(current: CurrentDocument, annotations: Sequence[Annotation]) -> list[Placed]:
    """Re-anchor each annotation in the current text: in its section, else wherever its quote now is, else orphaned."""
    out = []
    for a in annotations:
        quote = _norm(a.quote)
        own = current.provision(a.section) if a.section else None
        if not quote:
            out.append(Placed(a, Placement.SECTION if own else Placement.ORPHANED, a.section if own else ""))
            continue
        if own is not None and quote in _norm(current.text_of(own.number)):
            out.append(Placed(a, Placement.ANCHORED, own.number))
            continue
        moved = next((p.number for p in current.provisions if p.number and not p.removed and quote in _norm(p.body)), "")
        out.append(Placed(a, Placement.MOVED if moved else Placement.ORPHANED, moved))
    return out


# The specification's rows: which document is kept living, from which sources, with which corrections and checks.


class SourceKind(Enum):
    DOC = "doc"                      # a Google Doc, read with its text runs (bold, strikethrough)
    LIBRARY_TEXT = "library-text"    # the library's text extract of a PDF (a recorded copy's OCR), by library path
    SCAN = "scan"                    # an image-only PDF in Drive (a recorded copy), read for its marks (scan_marks)


@dataclass(frozen=True)
class SourceRef:
    """Where an instrument's words are read. ``sha256`` pins the library file a person reviewed: a file whose digest
    has changed is held out until it is reviewed again. A Doc is read at its current revision, which is reported."""

    kind: SourceKind
    ref: str                         # a Drive id (DOC, SCAN) or a library path (LIBRARY_TEXT)
    sha256: str = ""
    note: str = ""                   # why this copy ("the draft's runs; its after words match the recorded scan")


@dataclass(frozen=True)
class TextCheck:
    """A rule row that copies a term of the document, checked against the current text: ``expect`` must appear in the
    section's words. A miss means the rule row and the document disagree, and a person decides which is wrong."""

    section: str
    expect: str
    rule: str                        # the row it guards ("LeasingRules.cap_percent = 25")


@dataclass(frozen=True)
class LivingInstrument:
    key: str                         # the instrument's outline key ("ccrs-2nd-amendment")
    document: Any                    # the specification's Document: its title, adoption and recording
    source: SourceRef
    check: SourceRef | None = None   # a second reading whose words must agree (the draft Doc against the recorded scan)


@dataclass(frozen=True)
class LivingDocument:
    """A document kept as amended: the base text, the instruments (applied only once in effect), the editorial
    corrections, the checks of the rule rows that copy its terms, and the working copy a person keeps by hand."""

    key: str                         # the outline key ("ccrs")
    title: str
    kind: DocumentKind
    base: SourceRef
    base_from: str                   # how the generated text names its base ("the recorded 2007 copy")
    instruments: tuple[LivingInstrument, ...] = ()
    corrections: tuple[Correction, ...] = ()
    checks: tuple[TextCheck, ...] = ()
    working_doc: str = ""            # the Drive id of the reading copy kept by hand, checked for drift


def standing_of(document: Any) -> Standing:
    """An instrument's standing from the specification's dates: recorded, adopted, or a draft."""
    if getattr(document, "recorded", None):
        return Standing.RECORDED
    return Standing.ADOPTED if getattr(document, "adopted", None) else Standing.DRAFT


def check_text(current: CurrentDocument, checks: Sequence[TextCheck]) -> list[tuple[TextCheck, bool]]:
    """Each check with whether its words are in the section's current text."""
    return [(c, _norm(c.expect) in _norm(current.text_of(c.section))) for c in checks]


__all__ = ["Mark", "Run", "StyledRun", "Verb", "Standing", "Effect", "effect_of", "Operation", "Instrument",
           "SourceKind", "SourceRef", "TextCheck", "LivingInstrument", "LivingDocument", "standing_of", "check_text",
           "read_instruction", "legend", "read_operations", "doc_paragraphs", "text_paragraphs", "operations_from_doc",
           "operations_from_text", "FindingKind", "AmendmentFinding", "Provision", "CurrentDocument", "word_changes",
           "provisions_of", "consolidate", "drift", "CorrectionKind", "Correction", "changes_meaning", "correct",
           "AnnotationKind", "Placement", "Annotation", "Placed", "place"]
