"""The Rules document, and the owner's manual template that refers to it (docs/document-templates.md, section 11).

The rules are one document, kept as **rule records** and rendered by reference. A record is one operating rule (or one of
its subdivisions) with a stable id, the number it prints now, its heading, and its **versions**: the words, the day the
board adopted that version and the board item, or ``proposed`` when no board has adopted it. The version in force on a day
is the newest adopted version on or before that day; a proposed version is in force on no day. A change to a rule is one
record's edit, and every document that includes the rule picks it up the next time it is rendered.

Three definitions use the records (``document_templates`` supplies the blocks and the renderers):

- ``rules_definition``: the Rules document itself. A title, a status line that is the token ``{ADOPTION_STATUS}``, the
  adoption history, one ``RuleBlock`` per record, and an appendix that names the policies bound in apart (``PolicyReferencesBlock``)
  by their book keys instead of copying them.
- ``manual_template_definition``: the owner's manual template. The guide, the directory, the forms, the statutory notices,
  and a ``RulesReferenceBlock`` where the rules go. The block renders the rules from the same records (``full``: the
  Markdown and HTML outputs) or a link and an index of numbers and titles (``index``: the Google Doc template form). The
  words are never typed twice.
- the existing ``owners-manual`` definition can read its rule text from the records too (``RulesDocumentSource``); that is
  an option, and with it off nothing changes.

**The status line is the record's, never this code's.** ``adoption_status`` prints the draft banner unless an adoption
event for the whole document is on record on or before the document's day (an ``AdoptionEvent`` whose ``sections`` name
``RULES_KEY``). jason proposes; the board adopts (Civil Code 4350, 4355, 4360), and a person records the adoption.

The records start as the manual's classification (``derive_book``: the official rules' own pieces, grouped by the section
each stands for, so the words are the official rules' words). A person may keep them as data instead (``save_book``,
``load_book``): then a record edited there is the rule's words, and the manual that reads from the Rules document shows a
labeled difference from the working Doc rather than a silent one. Pure: the disk is in ``jason.tasks.rules_documents``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Sequence

from jason.community.document_templates import (BOOK, Block, BlockResult, Context, DirectoryBlock, DocumentDefinition,
                                                DocumentError, FormBlock, ManualBlock, ProseBlock, shift_headings)
from jason.community.manual import (EDITORIAL, AdoptionAction, AdoptionEvent, Chunk, Classification, SectionKind, Segment,
                                    concordance, fill_token, words)

RULES_KEY = "rules-and-regulations"                 # the Rules document's key, and what an adoption event names
MANUAL_TEMPLATE_KEY = "owners-manual-template"
STATUS_ID = "adoption-status"
FORMAT = 1
DRAFT_BANNER = ("**DRAFT FOR BOARD ADOPTION: not an adopted rule until the board adopts it "
                "(Civil Code 4350, 4355, 4360).**")
APART = "a part published apart"
LEFT_OUT = "left out of the official rules"
HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class ManualDocument:
    """One of the profile's generated documents (``Community.manual_documents()``): which definition, the name its Drive
    file bears, the folder it is filed in (empty: the Templates folder), and the Doc the profile already has, if any."""

    key: str
    name: str
    folder_id: str = ""
    drive_id: str = ""


# ---------------------------------------------------------------------------------------------------------------------
# The records


@dataclass(frozen=True)
class RuleVersion:
    """One version of a rule's words. ``adopted`` is the day the board adopted it (None: the day is not on record, so the
    version is the words as the source document has them); ``proposed`` is a version no board has adopted."""

    text: str                                 # the Markdown the rule prints as
    words: str = ""                           # the words of the source (what a manual reading from the records compares)
    adopted: date | None = None
    board_item: str = ""
    proposed: bool = False
    note: str = ""
    # Fields rule records add (docs/rule-records.md, section 3). Each is empty until a person fills it; a miss stays a miss.
    version: str = ""                         # the version's id ("v2"); empty: its place in the record names it
    source: str = ""                          # which words these are (see ``jason.community.rule_records``); empty: read from the other fields
    source_file: str = ""                     # the stored file the words were entered from (minutes, instrument)
    decision: str = ""                        # the board's decision id, read from the Decisions tab
    recorded_by: str = ""                     # who recorded the adoption
    recorded_at: str = ""
    effective: date | None = None             # the day it takes effect, when not the adoption day
    expires: date | None = None               # an emergency version's end day, from the catalog row
    notice: tuple[str, ...] = ()              # the notice ledger keys
    supersedes: str = ""                      # the version id this one replaced
    proposed_by: str = ""

    def in_force(self, day: date | None) -> bool:
        if self.proposed:
            return False
        return self.adopted is None or day is None or self.adopted <= day

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {"text": self.text, "words": self.words}
        if self.adopted:
            raw["adopted"] = self.adopted.isoformat()
        for key, value in (("boardItem", self.board_item), ("note", self.note)):
            if value:
                raw[key] = value
        if self.proposed:
            raw["proposed"] = True
        for key, value in (("version", self.version), ("source", self.source), ("sourceFile", self.source_file),
                           ("decision", self.decision), ("recordedBy", self.recorded_by), ("recordedAt", self.recorded_at),
                           ("supersedes", self.supersedes), ("proposedBy", self.proposed_by)):
            if value:
                raw[key] = value
        for key, day in (("effective", self.effective), ("expires", self.expires)):
            if day:
                raw[key] = day.isoformat()
        if self.notice:
            raw["notice"] = list(self.notice)
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuleVersion:
        def day(key: str) -> date | None:
            return date.fromisoformat(raw[key]) if raw.get(key) else None

        return cls(raw.get("text", ""), raw.get("words", ""), day("adopted"), raw.get("boardItem", ""),
                   bool(raw.get("proposed")), raw.get("note", ""), raw.get("version", ""), raw.get("source", ""),
                   raw.get("sourceFile", ""), raw.get("decision", ""), raw.get("recordedBy", ""), raw.get("recordedAt", ""),
                   day("effective"), day("expires"), tuple(raw.get("notice") or ()), raw.get("supersedes", ""),
                   raw.get("proposedBy", ""))


@dataclass(frozen=True)
class RuleAct:
    """A suspension or a repeal on record: what a person recorded, from ``on`` (a suspension to ``until``). The event log
    that writes these is a later phase; a stored record may already carry them."""

    kind: str                                 # "suspension" or "repeal"
    on: date
    until: date | None = None
    by: str = ""
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {"kind": self.kind, "on": self.on.isoformat()}
        if self.until:
            raw["until"] = self.until.isoformat()
        for key, value in (("by", self.by), ("evidence", self.evidence)):
            if value:
                raw[key] = value
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuleAct:
        return cls(raw["kind"], date.fromisoformat(raw["on"]), date.fromisoformat(raw["until"]) if raw.get("until") else None,
                   raw.get("by", ""), raw.get("evidence", ""))


@dataclass(frozen=True)
class RuleRecord:
    """One rule: ``id`` (permanent; it does not change when the rule is renumbered or reworded), ``number`` as it prints now,
    ``title`` (its heading text, empty for a plain paragraph) and ``level`` (the Markdown heading level, 0 for none),
    ``segment`` (the address in the manual's outline, kept as an alias), ``kind`` (rule or copy), the editorial ``notes``
    that follow it, and its ``versions`` oldest first."""

    id: str
    number: str = ""
    title: str = ""
    level: int = 0
    book: str = "rules"
    segment: str = ""
    kind: str = "rule"
    copies: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    versions: tuple[RuleVersion, ...] = ()
    subjects: tuple[str, ...] = ()            # ``rule_authority.Subject`` words a person confirmed; empty: read by the rule reader
    authority: tuple[str, ...] = ()           # grant ids (``jason rules``) a person tied the rule to; empty: found by subject
    confidentiality: str = ""                 # "open" or "board"; empty: an adopted version is open
    acts: tuple[RuleAct, ...] = ()            # suspensions and repeals on record

    def version_on(self, day: date | None) -> RuleVersion | None:
        live = [(v.adopted or date.min, i, v) for i, v in enumerate(self.versions) if v.in_force(day)]
        return max(live, key=lambda t: (t[0], t[1]))[2] if live else None

    @property
    def label(self) -> str:
        return self.title or self.number or self.id

    def to_dict(self) -> dict[str, Any]:
        raw: dict[str, Any] = {
            "id": self.id, "number": self.number, "title": self.title, "level": self.level, "book": self.book,
            "segment": self.segment, "kind": self.kind, "copies": list(self.copies), "notes": list(self.notes),
            "versions": [v.to_dict() for v in self.versions]}
        if self.subjects:
            raw["subjects"] = list(self.subjects)
        if self.authority:
            raw["authority"] = list(self.authority)
        if self.confidentiality:
            raw["confidentiality"] = self.confidentiality
        if self.acts:
            raw["acts"] = [a.to_dict() for a in self.acts]
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RuleRecord:
        return cls(raw["id"], raw.get("number", ""), raw.get("title", ""), int(raw.get("level", 0)), raw.get("book", "rules"),
                   raw.get("segment", ""), raw.get("kind", "rule"), tuple(raw.get("copies") or ()),
                   tuple(raw.get("notes") or ()), tuple(RuleVersion.from_dict(v) for v in raw.get("versions") or ()),
                   tuple(raw.get("subjects") or ()), tuple(raw.get("authority") or ()), raw.get("confidentiality", ""),
                   tuple(RuleAct.from_dict(a) for a in raw.get("acts") or ()))


@dataclass
class RuleBook:
    """The rule records in print order, the policies published apart (book key and title), and notes with no rule to follow."""

    records: list[RuleRecord] = field(default_factory=list)
    appendix: list[tuple[str, str]] = field(default_factory=list)
    loose: list[str] = field(default_factory=list)
    document: str = ""                        # the manual's outline key the records were read from
    source: str = ""                          # "derived from the classification", or the file they were stored in

    def get(self, id_: str) -> RuleRecord | None:
        return next((r for r in self.records if r.id == id_), None)

    def by_segment(self, address: str) -> RuleRecord | None:
        return next((r for r in self.records if r.segment and r.segment == address), None)

    def index(self, depth: int = 3) -> list[RuleRecord]:
        """The records that head a part or a rule (a heading of level 2 to ``depth``): numbers and titles only."""
        return [r for r in self.records if 2 <= r.level <= depth and r.title]

    def to_dict(self) -> dict[str, Any]:
        return {"format": FORMAT, "document": self.document, "appendix": [list(a) for a in self.appendix],
                "loose": list(self.loose), "records": [r.to_dict() for r in self.records]}

    @classmethod
    def from_dict(cls, raw: dict[str, Any], source: str = "") -> RuleBook:
        return cls([RuleRecord.from_dict(r) for r in raw.get("records") or ()],
                   [(a[0], a[1]) for a in raw.get("appendix") or ()], list(raw.get("loose") or ()),
                   raw.get("document", ""), source)


@dataclass
class RulesContext:
    """What the rule blocks read: the book, how a reference prints (``full`` the rules' words, ``index`` a link and an index
    of numbers and titles), and whether jason's bracketed notes print beside the rules."""

    book: RuleBook
    mode: str = "full"
    notes: bool = True
    document: str = RULES_KEY


# ---------------------------------------------------------------------------------------------------------------------
# Deriving the records from the manual's classification


def _covers(section: str, number: str) -> bool:
    return bool(section) and bool(number) and (number == section or number.startswith(section + "(")
                                               or number.startswith(section + "-"))


def event_covers(event: AdoptionEvent, *numbers: str) -> bool:
    """Whether an adoption event names any of ``numbers`` (a section covers its subdivisions)."""
    return any(_covers(sec, n) for sec in event.sections for n in numbers)


def adopted_day(events: Iterable[AdoptionEvent], *numbers: str) -> date | None:
    """The latest day an ``adopted`` event on record covers any of ``numbers`` (a section covers its subdivisions)."""
    days = [e.on for e in events if e.action is AdoptionAction.ADOPTED and e.on
            and any(_covers(sec, n) for sec in e.sections for n in numbers)]
    return max(days) if days else None


def _heading(markdown: str) -> tuple[int, str]:
    first = markdown.strip().split("\n", 1)[0] if markdown.strip() else ""
    m = HEADING.match(first)
    return (len(m.group(1)), m.group(2).strip()) if m else (0, "")


def _unique(base: str, seen: set[str]) -> str:
    out, n = base, 1
    while out in seen:
        n += 1
        out = f"{base}~{n}"
    seen.add(out)
    return out


def _segment_id(s: Segment, ids: Any) -> str:
    """A rule's permanent id: the section's permanent id when the document has an id table, else its address."""
    pid = None
    if ids is not None and s.number:
        number = s.number + (f"~{s.locator.nth}" if s.locator.nth > 1 else "")
        try:
            pid = ids.permanent_id(number)
        except Exception:                                           # noqa: BLE001 - a miss stays a miss
            pid = None
    base = pid or f"{s.target.book}#{s.new_number or s.old}"
    return base + (f"/{s.piece}" if s.piece else "")


def derive_book(classification: Classification, spec: Any, source: Any, text: str, *, passages: Sequence[Any] = (),
                current: bool = False, ids: Any = None, events: Sequence[AdoptionEvent] = ()) -> RuleBook:
    """The rule records from the manual's classification. The official rules' own pieces are grouped by the section each
    stands for: a piece that reads from the source's words starts a record, and the notes after it (a copy's source, an open
    question, a passage's change) are its notes. The words are therefore exactly the official rules' words."""
    rows = concordance(classification, text)
    chunks = fill_token("{INCLUDE:rules official}", "INCLUDE", "rules", {"official"}, classification, spec, source, text,
                        rows, list(passages), current)
    by_id = {s.id: s for s in classification.segments}
    book = RuleBook(document=getattr(spec, "document", ""), source="derived from the classification")
    seen: set[str] = set()
    pending: list[dict[str, Any]] = []
    for c in chunks:
        if c.label == APART or c.label == LEFT_OUT:
            continue
        if c.start >= 0 or c.kind == "adopted":
            s = by_id.get(c.segment)
            if s is not None:
                level, title = _heading(c.markdown)
                numbers = tuple(n for n in (s.number, s.new_number) if n)
                rec = {"id": _unique(_segment_id(s, ids), seen), "number": s.new_number or s.number, "title": title,
                       "level": level, "segment": s.id, "kind": s.kind.value, "copies": tuple(s.copies),
                       "adopted": adopted_day(events, *numbers)}
            else:                                                    # a passage's last adopted words, placed by address
                level, title = _heading(c.markdown)
                address = c.segment or "rules"
                rec = {"id": _unique(address, seen), "number": address.split("#", 1)[-1], "title": title, "level": level,
                       "segment": "", "kind": "rule", "copies": (), "adopted": None}
            rec.update(text=c.markdown, words=c.words, notes=[])
            pending.append(rec)
        elif pending:
            pending[-1]["notes"].append(c.markdown)
        else:
            book.loose.append(c.markdown)
    book.records = [RuleRecord(r["id"], r["number"], r["title"], r["level"], "rules", r["segment"], r["kind"], r["copies"],
                               tuple(r["notes"]), (RuleVersion(r["text"], r["words"], r["adopted"]),)) for r in pending]
    firsts: dict[str, int] = {}
    for s in classification.segments:
        if s.target.top not in ("rules", "manual"):
            firsts.setdefault(s.target.top, s.start)
    book.appendix = [(k, spec.title_of(k)) for k in sorted(firsts, key=firsts.__getitem__)]
    return book


def adoption_status(events: Iterable[AdoptionEvent], as_of: date | None, key: str = RULES_KEY) -> str:
    """The words of the ``{ADOPTION_STATUS}`` token. The draft banner stays until an adoption event naming the whole
    document is on record on or before ``as_of``; this function reads the record and decides nothing. With the event, the
    banner is replaced by a line that says when the board adopted it and the evidence."""
    adopted = [e for e in events if e.action is AdoptionAction.ADOPTED and e.on and key in e.sections
               and (as_of is None or e.on <= as_of)]
    if not adopted:
        return DRAFT_BANNER
    latest = max(adopted, key=lambda e: e.on)
    return f"_Adopted by the board of directors on {latest.on.isoformat()} ({latest.evidence})._"


# ---------------------------------------------------------------------------------------------------------------------
# Blocks


@dataclass(frozen=True)
class StatusBlock(ProseBlock):
    """The status line: prose whose words are the token ``{ADOPTION_STATUS}``, filled from the adoption record."""

    kind = "status"


@dataclass(frozen=True)
class RuleBlock(Block):
    """One rule, by its record's id: the version in force on the block's day (or the document's), with the record's notes.
    A rule with no version in force that day prints a visible line saying so, never a silent skip."""

    record: str = ""
    kind = "rule"

    def render(self, ctx: Context) -> BlockResult:
        rc = ctx.rules
        rec = rc.book.get(self.record) if rc is not None else None
        if rec is None:
            raise DocumentError(f"{self.id}: no rule record {self.record!r}")
        day = self.as_of or ctx.as_of
        ver = rec.version_on(day)
        if ver is None:
            when = day.isoformat() if day else "the day of the run"
            adopted = [v.adopted.isoformat() for v in rec.versions if v.adopted and not v.proposed]
            why = (f"the version on file was adopted {', '.join(adopted)}" if adopted else
                   "only a proposed version is on file")
            gap = f"{rec.label}: no version of this rule on file is in force on {when} ({why})."
            line = f"_[{gap}]_"
            return self._result(line, [Chunk(line, kind=EDITORIAL, label="a gap")], gaps=[gap], title=rec.label,
                                source=f"rule:{rec.id}")
        notes = list(rec.notes) if (rc.notes if rc is not None else True) else []
        md = "\n\n".join([ver.text, *notes])
        chunks = [Chunk(ver.text, ver.words, label=f"rule {rec.id}, the version in force on "
                        f"{day.isoformat() if day else 'the day of the run'}", kind="rule", segment=rec.segment)]
        chunks += [Chunk(n, kind=EDITORIAL, label="jason's note beside the rule", segment=rec.segment) for n in notes]
        return self._result(md, chunks, title=rec.label, source=f"rule:{rec.id}")


@dataclass(frozen=True)
class LooseNotesBlock(Block):
    """Notes that follow no rule: a note on a change that no rule piece could be tied to. Printed where the rules begin."""

    kind = "notes"

    def render(self, ctx: Context) -> BlockResult:
        notes = list(ctx.rules.book.loose) if ctx.rules is not None and ctx.rules.notes else []
        text = "\n\n".join(notes)
        return self._result(text, [Chunk(n, kind=EDITORIAL, label="jason's note, tied to no rule") for n in notes],
                            title="Notes", source="the revision history")


@dataclass(frozen=True)
class PolicyReferencesBlock(Block):
    """The policies bound in apart, named by their book keys. They are separate documents, read from their own sources:
    this block lists them and copies none."""

    heading: str = "Appendix: policies published apart"
    kind = "policy-references"

    def render(self, ctx: Context) -> BlockResult:
        apart = ctx.rules.book.appendix if ctx.rules is not None else []
        if not apart:
            return self._result("", [], title=self.heading)
        lines = [f"## {self.heading}", "",
                 "These policies are separate documents. This document does not reproduce them: each is kept, "
                 "adopted, and changed in its own document.", ""]
        lines += [f"- {title} (document key `{key}`)" for key, title in apart]
        text = "\n".join(lines)
        return self._result(text, [Chunk(text, kind=EDITORIAL, label="references to the policies published apart")],
                            title=self.heading, source="the manual's books")


@dataclass(frozen=True)
class RulesReferenceBlock(Block):
    """Where the rules go in a document that does not contain them: a reference to the Rules document. ``full`` renders the
    rules from the Rules document's records, by reference, one level down; ``index`` renders a line that links the Rules
    document and the numbers and titles of its parts and rules. Either way the words are the records', never retyped."""

    document: str = RULES_KEY
    kind = "rules-reference"

    def render(self, ctx: Context) -> BlockResult:
        rc = ctx.rules
        title = ctx.values.get("RULES_TITLE", "Rules and Regulations")
        if rc is None or not rc.book.records:
            gap = f"The {self.document} document has no rule records to refer to."
            line = f"_[Missing: {gap}]_"
            return self._result(line, [Chunk(line, kind=EDITORIAL, label="a gap")], gaps=[gap], title=title,
                                address=self.document)
        url = ctx.values.get("RULES_DOC_URL") or f"{self.document}.md"
        head = f"## {title}\n\n[{title}]({url}) is its own document, kept in one place. This guide refers to it and does not repeat it."
        chunks = [Chunk(head, kind=EDITORIAL, label="a reference to the Rules document")]
        gaps: list[str] = []
        if rc.mode == "index":
            lines = [f"- {r.title}" for r in rc.book.index()]
            body = "\n".join(lines)
            chunks.append(Chunk(body, kind=EDITORIAL, label="an index of the Rules document: numbers and titles only"))
            md = head + "\n\n" + body
        else:
            parts = []
            for r in rc.book.records:
                got = RuleBlock(f"rule:{r.id}", record=r.id, as_of=self.as_of).render(ctx)
                if got.markdown:
                    parts.append(got.markdown)
                chunks += got.chunks
                gaps += got.gaps
            md = head + "\n\n" + shift_headings("\n\n".join(parts), 1)
        return self._result(md, chunks, gaps=gaps, title=title, source=f"document:{self.document}", address=self.document)


# ---------------------------------------------------------------------------------------------------------------------
# The definitions


def rules_definition(book: RuleBook, layout: Any = BOOK) -> DocumentDefinition:
    """The Rules document: title, status line, adoption history, each rule as its own block, the appendix of policies
    published apart. The profile supplies the name and the title (``{ASSOCIATION_NAME}``, ``{RULES_TITLE}``)."""
    items: list[Block] = [
        ProseBlock("title", text="# {RULES_TITLE}\n\n{ASSOCIATION_NAME}\n\n"),
        StatusBlock(STATUS_ID, text="{ADOPTION_STATUS}\n\n"),
        ProseBlock("history-title", text="## Adoption history\n\n"),
        ManualBlock("adoption-history", verb="ADOPTION_HISTORY"),
        ProseBlock("rules-heading", text="## The rules\n\n"),
    ]
    if book.loose:
        items.append(LooseNotesBlock("notes"))
    items += [RuleBlock(f"rule:{r.id}", record=r.id) for r in book.records]
    items.append(PolicyReferencesBlock("policies-apart"))
    return DocumentDefinition(RULES_KEY, "Rules and Regulations", tuple(items), layout, kind="rules",
                              authority="CIV 4340, CIV 4350, CIV 4355, CIV 4360")


def manual_template_definition(layout: Any = BOOK, *, form: str = "architectural-application") -> DocumentDefinition:
    """The owner's manual template: the guide, the directory, the governing documents' excerpts, a reference to the Rules
    document where the rules go, the policies and statutory notices, and the forms. It holds no rule. ``form`` is the key of
    the application's ``FormTemplate``; empty (the profile has no such form), the application's words are the manual's own
    (the ``arch`` book), so the template does not lose it."""
    application: Block = (FormBlock("form-application", form=form, authority="CIV 4765") if form else
                          ManualBlock("form-application", verb="INCLUDE", arg="arch", flags=("optional",),
                                      authority="CIV 4765"))
    items: tuple[Block, ...] = (
        ProseBlock("title", text="# {MANUAL_TITLE}\n\n{ASSOCIATION_NAME}\n\n"),
        ProseBlock("as-of", text="_As of {AS_OF}._\n\n"),
        ManualBlock("guide-welcome", verb="PART", arg="welcome", flags=("optional",)),
        ManualBlock("guide-contacts", verb="PART", arg="contacts", flags=("optional",)),
        ProseBlock("directory-title", text="## The board and the association's contacts\n\n"),
        DirectoryBlock("directory", source="the association's directory (private facts)"),
        ManualBlock("excerpts", verb="EXCERPTS"),
        RulesReferenceBlock("rules-reference", document=RULES_KEY, required=True,
                            authority="CIV 4340, CIV 4350, CIV 4360"),
        ManualBlock("policy-discipline", verb="INCLUDE", arg="disc", flags=("optional",), authority="CIV 5850"),
        ManualBlock("policy-collection", verb="INCLUDE", arg="coll", flags=("optional",), authority="CIV 5310, CIV 5730"),
        ProseBlock("forms-title", text="## Forms\n\n"),
        application,
        ManualBlock("guide-guidance", verb="PART", arg="guidance", flags=("optional",)),
    )
    return DocumentDefinition(MANUAL_TEMPLATE_KEY, "Owner's Manual", items, layout, kind="guide",
                              authority="CIV 4340, CIV 4350, CIV 4360, CIV 4765, CIV 5730, CIV 5850")


# ---------------------------------------------------------------------------------------------------------------------
# Reading the rules from the Rules document: the option on the existing manual


class RulesDocumentSource:
    """A manual ``Source`` whose rule and copy words are the Rules document's records' (the version in force on ``as_of``),
    and everything else the wrapped source's. A rule with no record is read from the wrapped source. Where a record's
    words differ from the manual's, the piece's label says it was read from the Rules document, so the comparison shows a
    labeled difference and never a silent one."""

    def __init__(self, source: Any, book: RuleBook, as_of: date | None = None):
        self.source, self.book, self.as_of = source, book, as_of
        self.used: list[str] = []

    def words(self, s: Segment) -> tuple[str, str]:
        rec = self.book.by_segment(s.id) if s.target.top == "rules" and s.kind in (SectionKind.RULE, SectionKind.COPY) else None
        if rec is None:
            return self.source.words(s)
        ver = rec.version_on(self.as_of)
        if ver is None:
            return "", f"the Rules document has no version of {rec.label} in force on {self.as_of}"
        self.used.append(rec.id)
        return ver.words, f"read from the Rules document (rule {rec.id})"

    def __getattr__(self, name: str) -> Any:
        return getattr(self.source, name)


@dataclass
class RulesSectionCheck:
    """The manual's rules section beside the Rules document's words: the pieces whose words equal their record's, the ones
    that differ (each labeled), and records in the Rules document that the manual does not place."""

    same: int = 0
    different: list[str] = field(default_factory=list)
    unplaced: list[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return not self.different and not self.unplaced


def rules_section_check(chunks: Iterable[Chunk], book: RuleBook, as_of: date | None = None) -> RulesSectionCheck:
    out = RulesSectionCheck()
    placed: set[str] = set()
    for c in chunks:
        rec = book.by_segment(c.segment) if c.segment and (c.start >= 0 or c.kind == "rule") else None
        if rec is None:
            continue
        placed.add(rec.id)
        ver = rec.version_on(as_of)
        if ver is not None and words(c.words) == words(ver.words):
            out.same += 1
        else:
            out.different.append(f"{rec.label}: {c.label or 'unlabeled'}")
    out.unplaced = [r.id for r in book.records if r.segment and r.id not in placed]
    return out


def book_values(values: dict[str, str], rules_url: str = "") -> dict[str, str]:
    """The values a document that refers to the Rules document needs: the link to it (a relative file until a Drive id is
    known)."""
    out = dict(values)
    if rules_url:
        out["RULES_DOC_URL"] = rules_url
    return out


__all__ = ["DRAFT_BANNER", "LooseNotesBlock", "MANUAL_TEMPLATE_KEY", "ManualDocument", "PolicyReferencesBlock", "RULES_KEY", "RuleBlock",
           "RuleAct", "RuleBook", "RuleRecord", "RuleVersion", "RulesContext", "RulesDocumentSource", "RulesReferenceBlock",
           "RulesSectionCheck", "STATUS_ID", "StatusBlock", "adopted_day", "adoption_status", "book_values",
           "derive_book", "event_covers", "manual_template_definition", "rules_definition", "rules_section_check"]
