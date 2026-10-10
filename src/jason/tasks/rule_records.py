"""Rule records on disk, read only (docs/rule-records.md, phase 1).

``load`` reads what the views need: the rule records (the file a person keeps in ``data/rule-records/<document>.json``, or
derived from the manual's classification: ``records`` is ``auto``, ``stored`` or ``derived``), the adoption events, the
stored grants of rule-making power and the subject rows (``jason rules``), and the working Doc's reading of each rule for
the comparison. ``links`` finds the uses: a stored hearing or board decision whose own record cites the rule by its
address (``jason://rules/<id>``). Where no link exists, there is none to show; the link write is a later phase.

Nothing is written: not to ``data/`` (no draft, no store, no folder), not to Drive, PayHOA, or the mail. A source that cannot
be read leaves a note and a miss, never a guess.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community import rule_authority as ra
from jason.community import rule_records as rr
from jason.community.manual import AdoptionEvent, ManualError
from jason.community.rules_document import RuleBook, RuleRecord

MODES = ("auto", "derived", "stored")
ADDRESS = re.compile(re.escape(rr.ADDRESS) + r"([^\s\"'<>)\]},;]+)")


@dataclass
class Loaded:
    data_dir: Path
    book: RuleBook
    events: list[AdoptionEvent]
    authorities: list[ra.RuleAuthority] | None = None       # None: no grants stored
    rows: list[ra.SubjectRow] | None = None                 # None: the subject rows were not read
    docs: dict[str, rr.DocReading] = field(default_factory=dict)
    doc_read: bool = False
    notes: list[str] = field(default_factory=list)

    def record(self, id_: str) -> RuleRecord | None:
        """A record by its id, or by the number it prints as when only one record has it."""
        got = self.book.get(id_)
        if got is not None:
            return got
        same = [r for r in self.book.records if id_ and (r.number == id_ or r.id.split("#", 1)[-1] == id_)]
        return same[0] if len(same) == 1 else None


def _stored_path(data_dir: Path, document: str) -> Path:
    from jason.tasks.rules_documents import records_path

    return records_path(data_dir, document)


def _grants(data_dir: Path, notes: list[str]) -> list[ra.RuleAuthority] | None:
    """The stored grants, if the file is there. ``ra.stored`` would make the folder; reading must not."""
    if not (Path(data_dir) / "rules" / "authority.json").is_file():
        notes.append("no grants are stored: jason rules --find reads them")
        return None
    try:
        return [a for a in ra.stored(data_dir) if a.review is not ra.Review.REJECTED]
    except Exception as exc:                                       # noqa: BLE001 - a miss stays a miss
        notes.append(f"the stored grants could not be read ({type(exc).__name__}: {exc})")
        return None


def _subject_rows(data_dir: Path, community: Any, authorities: list[ra.RuleAuthority] | None,
                  notes: list[str]) -> list[ra.SubjectRow] | None:
    if authorities is None:
        return None
    try:
        from jason.tasks import rule_authority as task

        return task.subjects(data_dir, community, authorities=authorities)
    except Exception as exc:                                       # noqa: BLE001
        notes.append(f"the rules on file could not be read for the subject rows ({type(exc).__name__}: {exc}); "
                     "the grants are shown without them")
        return None


def doc_readings(book: RuleBook, read: dict[str, Any]) -> dict[str, rr.DocReading]:
    """The working Doc's reading of each rule: its words as the Doc has them now (pending suggestions left out), and what
    the revision history says of them (``manual_rule_change.partition``): a change with no adoption found, or one an adoption
    on record covers. A rule tied to no section of the Doc's outline is ``in_doc`` false."""
    part, result, clean = read["part"], read["result"], read["clean"]
    segments = {s.id: s for s in result.segments}
    changed = {u.number: u for u in (part.official if part is not None else [])}
    cured = {u.number: why for u, why in (part.cured if part is not None else [])}
    pending = len(part.suggestions) if part is not None else 0
    revision = part.revision if part is not None else ""
    out: dict[str, rr.DocReading] = {}
    for rec in book.records:
        seg = segments.get(rec.segment) if rec.segment else None
        if seg is None:
            out[rec.id] = rr.DocReading(in_doc=False)
            continue
        try:
            words = clean.words(seg)[0]
        except Exception:                                          # noqa: BLE001 - the section's source is not on disk
            continue
        u = changed.get(rec.number)
        out[rec.id] = rr.DocReading(words=words, revision=revision, later_adoption=cured.get(rec.number, ""),
                                    suggested=bool(u and u.suggested), pending=pending,
                                    changed_between=(u.from_on, u.to_on) if u else ("", ""))
    return out


def load(data_dir: Path | None = None, community: Any = None, *, records: str = "auto", doc: bool = True,
         grants: bool = True) -> Loaded:
    """The records and what the views set beside them. ``doc`` False skips the working Doc (a stored book then has no
    comparison); ``grants`` False skips ``jason rules``' subject rows (a heavy read)."""
    from jason.tasks import manual as task
    from jason.tasks.rules_documents import build_book, load_book

    if records not in MODES:
        raise ValueError(f"records is one of {', '.join(MODES)}")
    data_dir = Path(data_dir) if data_dir is not None else task.default_data_dir()
    if community is None:
        from jason.community import community as active

        community = active()
    spec = task.spec_of(community)
    notes: list[str] = []
    events = task.adoption_history(data_dir, community, spec)
    stored = load_book(_stored_path(data_dir, spec.document)) if records != "derived" else None
    if records == "stored" and stored is None:
        raise ManualError(f"no stored rule records at {_stored_path(data_dir, spec.document)} "
                          "(jason document-template rules-and-regulations --export-records writes the first ones)")
    read: dict[str, Any] | None = None
    if stored is None or doc:
        try:
            read = task.read_rules(data_dir, community)
        except Exception as exc:                                   # noqa: BLE001 - no manual rows, no outline on disk
            if stored is None:
                raise ManualError(f"the records can be derived only from the manual's classification: {exc}") from exc
            notes.append(f"the working Doc was not read ({type(exc).__name__}: {exc})")
    if stored is not None:
        book = stored
    else:
        assert read is not None
        book = build_book(data_dir, {"rules_source": read["clean"], "passages": read["passages"]}, read["result"],
                          read["outline"], read["spec"], events, "derived")
        notes.append("Derived from the classification: no record is stored. "
                     "jason document-template rules-and-regulations --export-records keeps them as data.")
    out = Loaded(Path(data_dir), book, events, notes=notes)
    if read is not None and doc:
        out.docs = doc_readings(book, read)
        out.doc_read = True
        if read["part"] is None:
            notes.append(f"no revision history for the Doc, so a change with no adoption found cannot be told: {read['why']}")
    if grants:
        out.authorities = _grants(data_dir, notes)
        out.rows = _subject_rows(data_dir, community, out.authorities, notes)
    return out


def comparisons(loaded: Loaded, day: date | None) -> dict[str, rr.Compare]:
    """Each record's comparison with the Doc; empty when the Doc was not read."""
    if not loaded.doc_read:
        return {}
    return {r.id: rr.compare(r, day, loaded.docs.get(r.id)) for r in loaded.book.records}


# ---------------------------------------------------------------------------------------------------------------------
# Uses


def _scan(text: str) -> set[str]:
    return {m.group(1).rstrip(".") for m in ADDRESS.finditer(text)}


def links(data_dir: Path) -> tuple[dict[str, list[rr.Use]], list[str]]:
    """Uses by rule id: each stored hearing or open-session board decision whose own record cites ``jason://rules/<id>``.
    An executive-session decision is not read (it is held by its nature); names are never carried, only a route."""
    from jason.tasks.decisions import is_executive, load as load_decisions
    from jason.tasks.hearing_decisions import key_of, load as load_hearings

    out: dict[str, list[rr.Use]] = {}
    notes: list[str] = []
    try:
        for h in load_hearings(data_dir):
            ids = _scan(json.dumps(h, default=str))
            if not ids:
                continue
            decided = h.get("decision") or {}
            on = str(h.get("start", ""))[:10]
            use = rr.Use("hearing", date.fromisoformat(on) if on else None,
                         "decision recorded" if decided else "hearing planned", {"route": f"#/hearings?id={key_of(h)}"})
            for i in ids:
                out.setdefault(i, []).append(use)
    except Exception as exc:                                       # noqa: BLE001
        notes.append(f"the hearings could not be read ({type(exc).__name__}: {exc})")
    held = 0
    try:
        for d in load_decisions(data_dir):
            ids = _scan(" ".join((d.title, d.motion, d.notes)))
            if not ids:
                continue
            if is_executive(d):
                held += 1
                continue
            use = rr.Use("decision", date.fromisoformat(d.meeting), d.outcome or "not yet decided",
                         {"route": f"#/decisions?id={d.id}"}, d.by)
            for i in ids:
                out.setdefault(i, []).append(use)
    except Exception as exc:                                       # noqa: BLE001
        notes.append(f"the board decisions could not be read ({type(exc).__name__}: {exc})")
    if held:
        notes.append(f"{held} executive-session decision(s) cite a rule and are not listed")
    return out, notes


def uses_of(loaded: Loaded, record: RuleRecord) -> list[rr.Use]:
    found, _ = links(loaded.data_dir)
    return found.get(record.id, [])


def use_counts(loaded: Loaded) -> dict[str, int]:
    found, _ = links(loaded.data_dir)
    return {r.id: len(found.get(r.id, [])) for r in loaded.book.records}


# ---------------------------------------------------------------------------------------------------------------------
# The views the MCP tools and the console loaders serve (JSON-ready; one shape for all of them)


def _parse_day(text: str) -> tuple[date | None, str]:
    if not text:
        return None, ""
    try:
        return date.fromisoformat(text), ""
    except ValueError:
        return None, f"as_of takes a day, YYYY-MM-DD, not {text!r}"


def _missing(id_: str, loaded: Loaded | None = None) -> dict[str, Any]:
    return {"found": False, "id": id_, "note": f"no rule record {id_!r}; the list names them (jason rule-records)"}


def _open(data_dir: Path | None, records: str, **flags: bool) -> tuple[Loaded | None, dict[str, Any] | None]:
    try:
        return load(data_dir, records=records, **flags), None
    except (ManualError, ValueError, OSError) as exc:
        return None, {"found": False, "note": str(exc),
                      "command": "jason document-template rules-and-regulations --export-records"}


def list_view(data_dir: Path | None = None, *, as_of: str = "", status: str = "", subject: str = "", records: str = "auto",
              doc: bool = True, grants: bool = True) -> dict[str, Any]:
    day, bad = _parse_day(as_of)
    if bad:
        return {"found": False, "note": bad}
    loaded, err = _open(data_dir, records, doc=doc, grants=grants)
    if err or loaded is None:
        return err or {"found": False}
    when = day or date.today()
    out = rr.book_view(loaded.book, when, loaded.events, rows=loaded.rows, authorities=loaded.authorities or (),
                       comparisons=comparisons(loaded, when), uses=use_counts(loaded), status=status, subject=subject)
    out["notes"] = loaded.notes
    return out


def record_detail(id_: str, data_dir: Path | None = None, *, as_of: str = "", records: str = "auto") -> dict[str, Any]:
    day, bad = _parse_day(as_of)
    if bad:
        return {"found": False, "note": bad}
    loaded, err = _open(data_dir, records, doc=True, grants=True)
    if err or loaded is None:
        return err or {"found": False}
    rec = loaded.record(id_)
    if rec is None:
        return _missing(id_)
    when = day or date.today()
    cmp_ = rr.compare(rec, when, loaded.docs.get(rec.id) if loaded.doc_read else None)
    out = rr.record_view(rec, when, loaded.events, rows=loaded.rows, authorities=loaded.authorities or (), comparison=cmp_,
                         uses=len(links(loaded.data_dir)[0].get(rec.id, [])))
    out["notes"] = loaded.notes
    return out


def history_detail(id_: str, data_dir: Path | None = None, *, as_of: str = "", records: str = "auto") -> dict[str, Any]:
    day, bad = _parse_day(as_of)
    if bad:
        return {"found": False, "note": bad}
    loaded, err = _open(data_dir, records, doc=False, grants=False)
    if err or loaded is None:
        return err or {"found": False}
    rec = loaded.record(id_)
    if rec is None:
        return _missing(id_)
    return {"found": True, "id": rec.id, "number": rec.number, "title": rec.title, **rr.history(rec, loaded.events, day or date.today()),
            "caveats": [rr.CAVEAT]}


def compare_detail(id_: str, data_dir: Path | None = None, *, as_of: str = "", records: str = "auto") -> dict[str, Any]:
    day, bad = _parse_day(as_of)
    if bad:
        return {"found": False, "note": bad}
    loaded, err = _open(data_dir, records, doc=True, grants=False)
    if err or loaded is None:
        return err or {"found": False}
    rec = loaded.record(id_)
    if rec is None:
        return _missing(id_)
    cmp_ = rr.compare(rec, day or date.today(), loaded.docs.get(rec.id) if loaded.doc_read else None)
    return {"found": True, "id": rec.id, "address": rr.citation(rec), **cmp_.to_dict(), "notes": loaded.notes}


def uses_detail(id_: str, data_dir: Path | None = None, *, as_of: str = "", records: str = "auto") -> dict[str, Any]:
    day, bad = _parse_day(as_of)
    if bad:
        return {"found": False, "note": bad}
    loaded, err = _open(data_dir, records, doc=False, grants=False)
    if err or loaded is None:
        return err or {"found": False}
    rec = loaded.record(id_)
    if rec is None:
        return _missing(id_)
    found, notes = links(loaded.data_dir)
    return {**rr.uses_view(rec, found.get(rec.id, []), day or date.today()), "notes": notes}


def events_detail(id_: str = "", key: str = "", data_dir: Path | None = None, records: str = "auto") -> dict[str, Any]:
    """The acts on record for a rule: the adoption events that name it, and the suspensions and repeals a person recorded.
    The proposal event log is a later phase, so a proposal ``key`` is not found."""
    if key and not id_:
        return {"found": False, "key": key, "note": "no proposal store yet: proposals and their event log are the next phase"}
    loaded, err = _open(data_dir, records, doc=False, grants=False)
    if err or loaded is None:
        return err or {"found": False}
    rec = loaded.record(id_)
    if rec is None:
        return _missing(id_)
    h = rr.history(rec, loaded.events)
    return {"found": True, "id": rec.id, "events": h["events"], "acts": h["acts"],
            "note": "" if (h["events"] or h["acts"]) else "nothing recorded since jason first read it"}


__all__ = ["Loaded", "MODES", "compare_detail", "comparisons", "doc_readings", "events_detail", "history_detail", "links",
           "list_view", "load", "record_detail", "use_counts", "uses_detail", "uses_of"]
