"""``jason onboard`` as a session: the checklist, the stage gates, and the intake questions ranked by what each answer
unblocks.

``build`` reads, read-only: the onboarding checklist against the profile and the data on disk
(``jason.tasks.onboarding``), the intake queue (``data/intake/asks.json``), and the citations of each section
(``jason cite``'s shelf: the documents' cross-references, and jason's own records that name a section). It adds the
questions onboarding asks (``generate``):

- a ``FACT`` for each checklist item a person supplies (an item with a ``FactAsk``) that is missing or partial;
- a ``FACT`` for each lead a lookup found in a public source (``jason onboard --lookup``), its found value the
  suggestion, while the item it serves is not present;
- a ``MAP`` for each book a checklist item looks for that no document fills, where the outlines or the library hold a
  candidate; and for each Civil Code 5200 record held in classified files with no folder pinned to hold it.

Each question gets its ``Unblocks`` (``jason.community.intake_rank``), and ``rank`` sorts the open ones. Nothing is
written: ``jason onboard --scan`` (or ``jason intake --scan``) parks the generated questions in the queue so they can
be answered, and the appliers (``jason.tasks.onboarding_answers``) turn answers into records.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from jason.community import intake
from jason.community.intake import Ask, AskKind, AskStatus, ask_id
from jason.community.intake_rank import (
    QUALITY_KINDS, Citing, Ranked, Unblocks, rank, reading_matters, section_weight, subject_section,
)
from jason.community.onboarding import (
    GATES, LEADS, Context, FactRecord, GateResult, InBook, ItemResult, Record, Settled, Stage, Status, check, gates,
    stages_of,
)

# The subjects the onboarding questions use: a scan that covers them marks a question no longer asked stale.
SCOPE = ("fact:", "book:", "record:", "map:")
LEAD_FILES = 20                    # library texts read for a fact's lead pattern, at most
CHOICES = 6                        # candidate documents offered as choices, at most

_RECORD_ANSWER = {
    FactRecord.PRIVATE: "The answer goes in the private facts (data/spec), never the specification.",
    FactRecord.PROFILE: "The answer becomes a proposed change to the profile, for a person to review and apply.",
    FactRecord.KEEPER: "Only the Keeper record's name is kept, never a password or code.",
}


# --- Citations --------------------------------------------------------------------------------------------------------

def citations(community: Any, data_dir: Path) -> dict[str, list[Citing]]:
    """Every citation of a section, by document key: the governing documents' cross-references and jason's own records
    (conflicts, notice provisions and requirements, duties, schedule assignments, ...) that name a section. The same
    reading ``jason cite --most-cited`` counts."""
    from jason.community.cite import Holder, Unit, of_reference
    from jason.tasks.cite import Shelf

    shelf = Shelf(community, Path(data_dir))
    out: dict[str, list[Citing]] = defaultdict(list)

    def add(target: Any, holder: str, key: str) -> None:
        if target is None or target.unit is not Unit.SECTION or not target.key:
            return
        for number in target.siblings or (target.number,):
            if number:
                out[target.key].append(Citing(number, holder, key))

    for row in shelf.rows():
        add(of_reference(row.get("target", ""), row.get("kind", "")), Holder.DOCUMENT.value, "")
    for m in shelf.mentions():
        add(m.target, m.holder.value, m.key)
    return dict(out)


# --- The questions onboarding asks -----------------------------------------------------------------------------------

def _leads(ask: Any, library: Iterable[dict[str, Any]], data_dir: Path) -> tuple[list[str], str]:
    """The library files of the fact's lead kinds (as evidence), and the most common match of its lead pattern in
    their text (the suggestion)."""
    kinds = {k.value for k in ask.lead_kinds}
    rows = [r for r in library if str(r.get("kind") or "") in kinds]
    if not rows:
        return [], ""
    rows.sort(key=lambda r: str(r.get("period") or ""), reverse=True)
    names = [str(r.get("path") or r.get("name") or "") for r in rows[:3]]
    lines = [f"lead: the library holds {len(rows)} {'/'.join(sorted(kinds))} file{'' if len(rows) == 1 else 's'}: "
             + "; ".join(names) + (" ..." if len(rows) > 3 else "")]
    suggestion = ""
    if ask.lead_pattern:
        found: Counter = Counter()
        pattern = re.compile(ask.lead_pattern)
        for r in rows[:LEAD_FILES]:
            path = Path(data_dir) / "library" / "text" / f"{r.get('id')}.txt"
            if path.is_file():
                found.update(set(pattern.findall(path.read_text(encoding="utf-8", errors="replace"))))
        if found:
            suggestion, seen = found.most_common(1)[0]
            lines.append(f"lead: read in {seen} of those files' text")
    return lines, suggestion


def fact_asks(results: Iterable[ItemResult], ctx: Context, data_dir: Path) -> list[Ask]:
    """A ``FACT`` for each item a person supplies that is missing or partial."""
    out = []
    for r in results:
        spec = r.item.ask
        if spec is None or r.status is Status.PRESENT:
            continue
        subject = f"fact:{r.item.key}"
        leads, suggestion = _leads(spec, ctx.library, data_dir)
        evidence = (f"checklist {r.item.key} is {r.status.value}: {r.evidence}", f"why: {r.item.why}",
                    "from: " + ", ".join(s.value for s in r.item.sources), *leads)
        out.append(Ask(ask_id(AskKind.FACT, subject, ""), AskKind.FACT, subject,
                       f"{spec.question} {_RECORD_ANSWER[spec.record]}", choices=spec.choices, suggestion=suggestion,
                       evidence=evidence, serves=r.item.key, stakes=spec.stakes,
                       detail={"item": r.item.key, "record": spec.record.value, "group": r.item.group.value,
                               "clock": spec.clock, "method": spec.method, "private": r.item.private}))
    return out


def lead_asks(results: Iterable[ItemResult], ctx: Context) -> list[Ask]:
    """A ``FACT`` for each lead a lookup found in a public source (``jason.tasks.onboarding_lookup``), kept under
    ``leads`` in the profile's private facts, while the item it serves is not present. The found value is the
    suggestion; the answer becomes a proposed change to the profile, never a row written straight in."""
    found = ctx.private(ctx.profile) if ctx.profile else {}
    leads = found.get(LEADS) if isinstance(found, dict) else None
    by_key = {r.item.key: r for r in results}
    record = FactRecord.PROFILE
    out = []
    for lead in leads or ():
        if not isinstance(lead, dict) or not lead.get("key") or not lead.get("question"):
            continue
        r = by_key.get(str(lead.get("item") or ""))
        if r is not None and r.status is Status.PRESENT:
            continue
        subject = f"fact:lookup:{lead['key']}"
        evidence = ([f"checklist {r.item.key} is {r.status.value}: {r.evidence}"] if r is not None else []) + [
            f"lead: {lead.get('source') or 'a public source'}, read {lead.get('found') or '?'}",
            *(str(e) for e in lead.get("evidence") or ())]
        out.append(Ask(ask_id(AskKind.FACT, subject, ""), AskKind.FACT, subject,
                       f"{lead['question']} {_RECORD_ANSWER[record]}", choices=tuple(lead.get("choices") or ()),
                       suggestion=str(lead.get("suggestion") or ""), evidence=tuple(evidence),
                       serves=r.item.key if r is not None else "", stakes=bool(lead.get("stakes")),
                       detail={"item": r.item.key if r is not None else str(lead.get("item") or ""),
                               "record": record.value, "group": r.item.group.value if r is not None else "",
                               "clock": "", "method": str(lead.get("method") or ""), "private": False,
                               "lead": lead["key"], "source": str(lead.get("source") or "")}))
    return out


def _outlines(data_dir: Path) -> list[dict[str, str]]:
    """The outlined documents on disk: key, title, kind."""
    folder = Path(data_dir) / "outlines"
    out = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        if path.name == "references.json":
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(raw, dict) and raw.get("key"):
            out.append({"key": str(raw["key"]), "title": str(raw.get("title") or ""), "kind": str(raw.get("kind") or "")})
    return out


def _item_for(check_type: type, value: Any) -> str:
    """The checklist item whose check of this type names ``value`` (a book, a 5200 record)."""
    from jason.community.onboarding import ITEMS

    attr = "book" if check_type is InBook else "kind"
    for i in ITEMS:
        if any(isinstance(c, check_type) and getattr(c, attr) is value for c in i.checks):
            return i.key
    return ""


def map_asks(results: Iterable[ItemResult], ctx: Context, data_dir: Path) -> list[Ask]:
    """``MAP`` questions: a book a checklist item looks for that no document fills, with the candidates the outlines and
    the library hold; and a 5200 record held in classified files that no folder is pinned to hold."""
    from jason.community.books import Book, Shape, default_book, entries_of

    status = {r.item.key: r.status for r in results}
    mapped = {e.book for e in entries_of(ctx.community)}
    entered = {e.document for e in entries_of(ctx.community)}
    outlines = _outlines(data_dir)
    out: list[Ask] = []
    for book in Book:
        key = _item_for(InBook, book)
        if not key or book in mapped:
            continue
        kinds = set(book.info.kinds)
        docs = [o for o in outlines if o["key"] not in entered and o["kind"] and default_book(o["kind"]) is book]
        files = [str(r.get("path") or r.get("name") or "") for r in ctx.library
                 if kinds and str(r.get("kind") or "") in {k.value for k in kinds}]
        if not docs and not files:
            continue
        series = book.info.shape is Shape.SERIES
        kind_words = "/".join(sorted({o["kind"] for o in docs} | {k.value for k in kinds})) or "its"
        choices: list[str] = []
        if series and len(docs) > 1:
            choices.append(f"all {len(docs)} outlined {kind_words} documents")
        choices += [o["key"] for o in docs[:CHOICES]]
        choices += [f"library:{f}" for f in files[:max(0, CHOICES - len(choices))]]
        choices.append("none of these: it is kept elsewhere (say where)")
        suggestion = choices[0] if (series and len(docs) > 1) or len(docs) == 1 or (not docs and len(files) == 1) else ""
        subject = f"book:{book.value}"
        evidence = [f"checklist {key} is {status.get(key, Status.MISSING).value}: book {book.value} has no document mapped",
                    f"{book.info.title} ({book.info.statute}); {'a series, one record per item' if series else 'cited by section'}"]
        if docs:
            evidence.append(f"outlined and not mapped: {', '.join(o['key'] for o in docs[:CHOICES])}"
                            + (f" and {len(docs) - CHOICES} more" if len(docs) > CHOICES else ""))
        if files:
            evidence.append(f"the library holds {len(files)} {kind_words} file{'' if len(files) == 1 else 's'}")
        out.append(Ask(ask_id(AskKind.MAP, subject, ""), AskKind.MAP, subject,
                       f"No document is mapped to {book.info.title} (book {book.value}), so its record address and the "
                       f"checklist cannot find it. Which document fills it? The answer becomes a proposed change to the "
                       f"profile's book entries, for a person to apply.",
                       choices=tuple(choices), suggestion=suggestion, evidence=tuple(evidence), serves=key,
                       detail={"map": "book", "book": book.value, "item": key, "outlines": [o["key"] for o in docs],
                               "files": files[:CHOICES]}))
    folders = tuple(getattr(ctx.community, "library_folders", lambda: ())())
    for h in ctx.holdings:
        kind = getattr(h, "kind", None)
        if kind is None or getattr(h, "pinned", True) or not getattr(h, "classified", 0):
            continue
        parents = Counter(str(r.get("path") or "").rsplit("/", 1)[0] + "/" for r in ctx.library
                          if kind.value in (r.get("records") or ()) and "/" in str(r.get("path") or ""))
        candidates: Counter = Counter()
        for parent, n in parents.items():
            row = max((f for f in folders if parent.startswith(f.path)), key=lambda f: len(f.path), default=None)
            candidates[row.path if row is not None else parent] += n
        if not candidates:
            continue
        key = _item_for(Record, kind)
        subject = f"record:{kind.value}"
        choices = tuple(p for p, _ in candidates.most_common(CHOICES)) + ("not a 5200 record here: dismiss",)
        out.append(Ask(ask_id(AskKind.MAP, subject, ""), AskKind.MAP, subject,
                       f"{h.classified} classified files are the {kind.value.replace('_', ' ')} record "
                       f"({getattr(h, 'citation', 'CIV 5200')}), but no folder is pinned to hold it. Which library "
                       f"folder holds it? The answer becomes a proposed pin in the profile, for a person to apply.",
                       choices=choices, suggestion=choices[0], serves=key,
                       evidence=tuple([f"held in: " + "; ".join(f"{p} ({n})" for p, n in parents.most_common(4))]
                                      + ([f"checklist {key} is {status.get(key, Status.MISSING).value}"] if key else [])),
                       detail={"map": "record", "record": kind.value, "item": key, "folders": list(candidates)}))
    return out


def generate(results: Iterable[ItemResult], ctx: Context, data_dir: Path) -> list[Ask]:
    results = tuple(results)
    return fact_asks(results, ctx, data_dir) + lead_asks(results, ctx) + map_asks(results, ctx, data_dir)


def generate_for(community: Any, data_dir: Path, *, settings: Any = None) -> list[Ask]:
    """The onboarding questions for the active profile (``jason intake --scan`` adds them to the queue)."""
    from jason.tasks.onboarding import load_context

    ctx = load_context(community, data_dir, settings=settings, asks=tuple(intake.load(data_dir)))
    return generate(check(ctx), ctx, data_dir)


# --- What each question unblocks -------------------------------------------------------------------------------------

def unblocks_for(a: Ask, *, status: dict[str, Status], groups: dict[str, str], gate_results: Iterable[GateResult],
                 cited: dict[str, list[Citing]], books: Any = None) -> Unblocks:
    """What answering ``a`` unblocks: its checklist item and the gates waiting on it (a FACT or MAP); the clocks and
    weighted citations of its section; the gates an open question of its kind holds closed; or its text's quality."""
    items: list[tuple[str, str]] = []
    gate_names: list[str] = []
    records: list[str] = []
    clocks: list[str] = []
    sections: list[str] = []
    item_groups: list[str] = []
    weight = 0.0
    served = a.serves or str(a.detail.get("item") or "")
    if served:
        now = status.get(served)
        if now is not None and now is not Status.PRESENT:
            items.append((served, now.value))
            gate_names += [s.value for s in stages_of(served)]
        if served in groups:
            item_groups.append(groups[served])
    if a.kind is AskKind.FACT and a.detail.get("clock"):
        clocks.append(str(a.detail["clock"]))
    if a.kind is AskKind.MAP:
        if a.detail.get("book"):
            records.append(f"book {a.detail['book']}")
        if a.detail.get("record"):
            records.append(f"record {a.detail['record']}")
    document, number = subject_section(a.subject)
    if not document and "@" in a.subject and ":" not in a.subject.split("@", 1)[0]:
        document = a.subject.split("@", 1)[0]
    if number:
        weight, found = section_weight(number, cited.get(document, ()))
        # Only a question that decides the section's words can move its clocks: which text is in force, or an OCR
        # reading that could change the meaning (not a respacing, nor a likely real word for a non-word). An orphaned
        # note, a section's kind, or a held source keeps its citations and gives up the clock.
        if a.kind in intake.HIGH_STAKES or (a.kind is AskKind.OCR_READING and reading_matters(a.detail, a.likely)):
            clocks += list(found)
        sections.append(a.subject)
    if document and books is not None:
        book = books.book(document)
        key = _item_for(InBook, book) if book is not None else ""
        if key and key in groups:
            item_groups.append(groups[key])
    if a.kind is AskKind.CLASSIFY:
        item_groups.append("records")
    for g in gate_results:
        if any(isinstance(c, Settled) and c.counts(a, books) for c in g.gate.checks):
            gate_names.append(g.gate.stage.value)
    return Unblocks(items=tuple(items), gates=tuple(dict.fromkeys(gate_names)), records=tuple(records),
                    clocks=tuple(dict.fromkeys(clocks)), sections=tuple(sections), weight=weight,
                    quality=a.kind.value in QUALITY_KINDS, groups=tuple(dict.fromkeys(item_groups)))


# --- The session ------------------------------------------------------------------------------------------------------

@dataclass
class Session:
    title: str
    results: tuple[ItemResult, ...]
    gates: tuple[GateResult, ...]
    queue: list[Ask]                                  # the stored questions merged with the generated ones
    stored: set[str] = field(default_factory=set)     # ids already in data/intake/asks.json
    ranked: list[Ranked] = field(default_factory=list)
    ingest: dict[str, Any] | None = None              # the last ``jason ingest`` (``jason.tasks.ingest.gate``)
    ingest_lines: list[str] = field(default_factory=list)

    @property
    def stage(self) -> Stage | None:
        """The first stage whose gate is closed; None when every gate is open."""
        return next((g.gate.stage for g in self.gates if not g.open), None)

    def waiting(self) -> list[Ask]:
        """Answered questions not yet applied: those still needing a second person first."""
        return [a for a in self.queue if a.status is AskStatus.ANSWERED]

    def questions(self, *, group: str = "", stage: str = "", limit: int = 0) -> list[Ranked]:
        rows = [r for r in self.ranked if (not group or group in r.unblocks.groups)
                and (not stage or stage in r.unblocks.gates
                     or any(stage in {s.value for s in stages_of(k)} for k, _ in r.unblocks.items))]
        return rows[:limit] if limit else rows


def build(community: Any, data_dir: Path, *, settings: Any = None) -> Session:
    """The session for the active profile, read-only."""
    from jason.community.books import Books
    from jason.tasks.onboarding import load_context

    data_dir = Path(data_dir)
    stored = intake.load(data_dir)
    ctx = load_context(community, data_dir, settings=settings, asks=tuple(stored))
    results = check(ctx)
    queue = intake.merge(stored, generate(results, ctx, data_dir), scope=SCOPE)
    gate_results = gates(results, ctx)
    try:
        cited = citations(community, data_dir)
    except Exception:  # noqa: BLE001 - no outlines yet: no section is cited, and the ranking says so
        cited = {}
    books = Books.of(community)
    status = {r.item.key: r.status for r in results}
    groups = {r.item.key: r.item.group.value for r in results}
    open_asks = [a for a in queue if a.status is AskStatus.OPEN]
    unblocks = {a.id: unblocks_for(a, status=status, groups=groups, gate_results=gate_results, cited=cited, books=books)
                for a in open_asks}
    ingest, ingest_lines = _ingest(data_dir)
    return Session(f"Onboarding: {getattr(community, 'name', '')}", results, gate_results, queue,
                   {a.id for a in stored}, rank(open_asks, unblocks), ingest, ingest_lines)


def _ingest(data_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """What the last ``jason ingest`` read, filed, and left open, for the ingest stage beside its checklist condition;
    nothing when it cannot be read."""
    try:
        from jason.tasks import ingest as ingest_task

        return ingest_task.gate(data_dir), list(ingest_task.gate_lines(data_dir))
    except Exception:  # noqa: BLE001 - an ingest report that cannot be read leaves the gate's own checks
        return None, []


def status_dict(session: Session) -> dict[str, Any]:
    """Progress by group, the gates, and the queue's size: JSON-ready, with counts and keys only."""
    from jason.community.onboarding import by_group, counts

    open_asks = [a for a in session.queue if a.status is AskStatus.OPEN]
    return {
        "title": session.title, "progress": counts(session.results),
        "groups": [{"group": g.value, "title": g.title, **counts(rows)} for g, rows in by_group(session.results).items()],
        "stage": session.stage.value if session.stage else "operating",
        "gates": [{"stage": g.gate.stage.value, "title": g.gate.title, "open": g.open, "opensWhen": g.gate.opens,
                   "waiting": [{"key": r.item.key, "status": r.status.value} for r in g.waiting],
                   "checks": [{"passed": f.passed, "evidence": f.evidence} for f in g.findings],
                   **({"ingest": session.ingest} if g.gate.stage is Stage.INGEST else {})} for g in session.gates],
        "questions": {"open": len(open_asks), "byKind": dict(Counter(a.kind.value for a in open_asks).most_common()),
                      "answeredNotApplied": len(session.waiting()),
                      "notYetInQueue": sum(1 for a in open_asks if a.id not in session.stored)},
    }


def question_dict(r: Ranked, stored: set[str]) -> dict[str, Any]:
    a = r.ask
    return {"id": a.id, "kind": a.kind.value, "subject": a.subject, "question": a.question, "choices": list(a.choices),
            "suggestion": a.suggestion, "likely": a.likely, "evidence": list(a.evidence), "priority": r.score,
            "unblocks": r.unblocks.as_dict(), "serves": a.serves, "highStakes": intake.high_stakes(a),
            "inQueue": a.id in stored}


def lines(session: Session, *, limit: int = 5) -> list[str]:
    """The default view: progress by group, the stage gates, and the next questions."""
    from jason.community.onboarding import by_group, counts

    total = counts(session.results)
    out = [session.title, "",
           f"Progress: {len(session.results)} items: {total['present']} present, {total['partial']} partial, "
           f"{total['missing']} missing"]
    for g, rows in by_group(session.results).items():
        c = counts(rows)
        out.append(f"  {g.value:14} {c['present']:3} present {c['partial']:3} partial {c['missing']:3} missing")
    out += ["", "Stages:"]
    for g in session.gates:
        out.append(f"  {g.gate.stage.value:10} {'open' if g.open else 'closed'}: {g.gate.title}")
        if not g.open:
            out.append(f"             waiting on: {g.evidence}")
        if g.gate.stage is Stage.INGEST:
            out += [f"             {line.strip()}" for line in session.ingest_lines]
    waiting = session.waiting()
    if waiting:
        out += ["", f"Answered, not yet applied: {len(waiting)} (jason onboard --apply; a high-stakes answer needs "
                    f"--confirm ID --by NAME from a second person)"]
    shown = session.questions(limit=limit)
    out += ["", f"Next {len(shown)} of {len(session.ranked)} open questions:"]
    for r in shown:
        out += question_lines(r, session.stored)
    if any(r.ask.id not in session.stored for r in shown):
        out += ["", "A question marked (new) is not in the queue yet: jason onboard --scan parks it so it can be answered."]
    return out


def question_lines(r: Ranked, stored: set[str]) -> list[str]:
    a = r.ask
    flags = [x for x in ("likely" if a.likely else "", "high stakes" if intake.high_stakes(a) else "",
                         "new" if a.id not in stored else "") if x]
    out = ["", f"[{a.id}] {a.kind.value} {a.subject}" + (f" ({', '.join(flags)})" if flags else "")
           + f"  priority {r.score:g}", f"  {a.question}"]
    out += [f"  unblocks {line}" for line in r.unblocks.lines()]
    out += [f"  evidence: {e[:240]}" for e in a.evidence[:3]]
    for n, c in enumerate(a.choices, 1):
        out.append(f"  {n}. {c[:160]}" + ("   <- suggested" if c == a.suggestion else ""))
    if a.suggestion and a.suggestion not in a.choices:
        out.append(f"  suggested: {a.suggestion[:160]}")
    return out


__all__ = ["SCOPE", "Session", "build", "citations", "fact_asks", "generate", "generate_for", "lead_asks", "lines",
           "map_asks",
           "question_dict", "question_lines", "status_dict", "unblocks_for"]
