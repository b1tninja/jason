"""MCP tools, and the programmatic interface, for the governance systems: the living documents, the conflicts, the
intake questions, the schedule, members' requests, the notice catalog, and the documents' duties; and
``governance_digest``, what needs attention across all of them.

Each tool is a plain function that returns a JSON-ready dict, so ``jason-mcp`` serves it and Python code imports it
(``jason.api``). They read the stores on disk; three write a person's record to ``data/`` and never anything else:
``answer_intake_question``, ``record_completion``, and nothing that reaches PayHOA, Google, or the mail. A write names
the person (``by``) and is refused without one. None decides for the board: a conflict is noted, a duty is a reading, a
request's clock is computed, and approving, denying, or assigning stays a person's.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def _root(data_dir: Path | None) -> Path:
    from jason.config import Settings

    return Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent


def _community() -> Any:
    from jason.community import community

    return community()


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


# --- The living documents ---------------------------------------------------------------------------------------------

def living_document(key: str = "", section: str = "", as_of: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """A governing document as amended. With no ``key``, the documents kept living. With ``key`` (``ccrs``): the
    instruments applied and not in effect, the findings (an amendment's silent changes, readings that differ), and
    the rule rows' checks; with ``section`` (``4.15(a)``) also that section's current words, who set them, and its
    history. ``as_of`` (YYYY-MM-DD) gives the text in force on a date. Built from the sources saved on disk (run
    ``jason living KEY --fetch`` for the latest); it is not an official restatement, and the recorded instruments
    control."""
    from jason.tasks import living_docs

    rows = _community().living_documents()
    if not key:
        return {"documents": [{"key": d.key, "title": d.title, "base": d.base_from,
                               "instruments": [i.key for i in d.instruments]} for d in rows]}
    ld = next((d for d in rows if d.key == key), None)
    if ld is None:
        return {"error": f"no living document {key}", "documents": [d.key for d in rows]}
    try:
        built = living_docs.build(ld, _root(data_dir), as_of=date.fromisoformat(as_of) if as_of else None)
    except ValueError as exc:
        return {"error": str(exc)}
    cur = built.current
    out: dict[str, Any] = {
        "key": key, "title": ld.title, "base": cur.base,
        "applied": [i.describe() for i in cur.applied], "notInEffect": [i.describe() for i in cur.pending],
        "held": built.held, "findings": [f.line() for f in cur.findings],
        "checks": [{"rule": c.rule, "section": c.section, "expect": c.expect, "found": ok} for c, ok in built.checks],
        "amended": [{"section": p.number, "setBy": p.set_by, "dated": _day(p.dated)} for p in cur.provisions
                    if p.standing is not None],
        "caveat": "Consolidated by jason from the instruments' own words; the recorded instruments control.",
    }
    if section:
        p = cur.provision(section)
        if p is None:
            out["section"] = {"error": f"no section {section}"}
        else:
            out["section"] = {"number": p.number, "caption": p.caption, "words": cur.text_of(p.number),
                              "setBy": p.set_by, "dated": _day(p.dated), "history": p.history, "removed": p.removed}
    return out


# --- Conflicts --------------------------------------------------------------------------------------------------------

def document_conflicts(area: str = "", include_resolved: bool = False, leads: bool = False, document: str = "",
                       since: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Written provisions a higher authority displaces (Civil Code 4205: followed only as far as the law allows): each
    with what still governs, the part that yields, since when, plain or for counsel, and the board item. ``area``
    narrows (rentals, enforcement, governing, ...). ``leads`` adds the candidates: each change in the Act since a
    document was written with the section that cites it or speaks to its subject (``document``, ``since`` narrow
    them); a lead is to read beside the statute, not a conflict."""
    from jason.community.authority_order import conflicts
    from jason.community.lessons import Area

    c = _community()
    try:
        wanted = Area(area) if area else None
    except ValueError:
        return {"error": f"areas: {', '.join(a.value for a in Area)}"}
    rows = conflicts(c, wanted, open_only=not include_resolved)
    out: dict[str, Any] = {"conflicts": [{
        "key": r.key, "provision": r.provision, "says": r.says, "authority": r.authority,
        "since": _day(r.since), "extent": r.extent, "meanwhile": r.apply, "clarity": r.clarity.value,
        "status": r.status.value, "boardItem": r.board_item, "resolvedBy": r.resolved_by} for r in rows],
        "caveat": "jason notes a conflict; only the board, counsel, or an amendment resolves one."}
    if leads:
        from jason.tasks import conflict_leads

        found = conflict_leads.leads(_root(data_dir), c, document=document, since=since)
        out["leads"] = [{"document": l.document, "section": l.section, "statute": l.change.citation,
                         "bill": l.change.bill, "operative": l.change.when, "route": l.route, "recorded": l.recorded,
                         "quote": l.quote} for l in found[:200]]
        out["leadCount"] = len(found)
    return out


# --- Intake questions -------------------------------------------------------------------------------------------------

def intake_questions(kind: str = "", subject: str = "", likely_only: bool = False, status: str = "open",
                     limit: int = 50, data_dir: Path | None = None) -> dict[str, Any]:
    """The questions jason parked while taking documents in (``jason intake --scan``): which kind a file is, what an
    OCR'd word says, an amendment's silent change, drift in the working copy, an orphaned note. Each with its
    evidence, choices, and jason's suggestion; ``likely`` means two independent readers agree. ``status`` is open,
    answered, applied, dismissed, stale, or "" for all."""
    from jason.community import intake

    asks = [a for a in intake.load(_root(data_dir))
            if (not status or a.status.value == status) and (not kind or a.kind.value == kind)
            and (not subject or a.subject.startswith(subject)) and (not likely_only or a.likely)]
    return {"count": len(asks), "questions": [{
        "id": a.id, "kind": a.kind.value, "subject": a.subject, "question": a.question, "choices": list(a.choices),
        "suggestion": a.suggestion, "likely": a.likely, "evidence": list(a.evidence), "status": a.status.value,
        "answer": a.answer, "answeredBy": a.answered_by} for a in asks[: max(1, int(limit))]]}


def answer_intake_question(question_id: str, answer: str, by: str, data_dir: Path | None = None) -> dict[str, Any]:
    """Record a person's answer to one intake question (a choice's number, or words; "dismiss" closes it). It writes
    only ``data/intake/asks.json``; ``jason intake --apply`` turns answers into the records later runs use. ``by``
    names the person answering and is required: jason never answers in its own name."""
    from jason.community import intake

    root = _root(data_dir)
    asks = intake.load(root)
    try:
        a = intake.answer(asks, question_id, answer, by)
    except (KeyError, ValueError) as exc:
        return {"error": f"cannot answer {question_id}: {exc}"}
    intake.save(root, asks)
    return {"id": a.id, "status": a.status.value, "answer": a.answer, "answeredBy": a.answered_by,
            "next": "jason intake --apply"}


# --- The schedule -----------------------------------------------------------------------------------------------------

def schedule_agenda(days: int = 60, past: int = 30, role: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """What falls due: each assignment's occurrences from ``past`` days back to ``days`` ahead, with its role and
    standing (done, overdue, due soon, upcoming). ``role`` narrows (treasurer, secretary, board, ...). Assignments are
    jason's proposals until the board adopts them; a completion is recorded by a person (``record_completion``)."""
    from datetime import timedelta

    from jason.community.schedule import Role
    from jason.tasks import schedule as task

    c = _community()
    found = task.agenda(c, _root(data_dir), start=date.today() - timedelta(days=past),
                        end=date.today() + timedelta(days=days))
    if role:
        try:
            r = Role(role)
        except ValueError:
            return {"error": f"roles: {', '.join(x.value for x in Role)}"}
        found = [o for o in found if o.assignment.role is r or o.assignment.backup is r]
    return {"items": [{"due": _day(o.due), "standing": o.standing, "key": o.assignment.key, "title": o.assignment.title,
                       "role": o.assignment.role.value, "adoption": o.assignment.adoption.value,
                       "evidence": o.assignment.evidence, "done": o.done} for o in found]}


def schedule_assignments(data_dir: Path | None = None) -> dict[str, Any]:
    """Who does each duty and when: every assignment with its role, backup, clock, evidence, the jason command, and its
    adoption; and the coverage check: duties nobody owns, and duties on a clock that only a standing assignment owns
    (both should be empty)."""
    from jason.community.schedule import assignments
    from jason.tasks import schedule as task

    c, root = _community(), _root(data_dir)
    covered, uncovered = task.coverage(c, root)
    loose = task.unscheduled(c, root)
    return {"assignments": [{"key": a.key, "title": a.title, "role": a.role.value,
                             "backup": a.backup.value if a.backup else None, "clock": a.cadence(),
                             "covers": list(a.covers), "evidence": a.evidence, "jason": a.jason,
                             "adoption": a.adoption.value, "adopted": a.adopted, "note": a.note}
                            for a in assignments(c)],
            "coverage": {"assigned": len(covered), "unassigned": [r for r, _ in uncovered],
                         "assignedNotScheduled": [r for r, _, _ in loose]}}


def record_completion(key: str, due: str, by: str, evidence: str, done_on: str = "",
                      data_dir: Path | None = None) -> dict[str, Any]:
    """Record that an assignment's occurrence due on ``due`` (YYYY-MM-DD) was done: who did it (``by``) and the
    evidence (the minutes' date and item, a payment, a notice proof). Writes only ``data/schedule/done.jsonl``; refused
    without a person and evidence."""
    from jason.community.schedule import assignments
    from jason.tasks import schedule as task

    if not any(a.key == key for a in assignments(_community())):
        return {"error": f"no assignment {key}"}
    try:
        row = task.record_done(_root(data_dir), key, date.fromisoformat(due),
                               date.fromisoformat(done_on) if done_on else date.today(), by, evidence)
    except ValueError as exc:
        return {"error": str(exc)}
    return {"recorded": row}


# --- Members' requests ------------------------------------------------------------------------------------------------

def member_requests(open_only: bool = True, kind: str = "", include_email: bool = True, limit: int = 60,
                    sources: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    """Each member's request (PayHOA, and the owners' email threads): its kind, the day received, the clock (the
    statute's, the documents', or a proposed policy's), the due day, the owner's role, whether it was acknowledged and
    answered, its standing, and the next step. ``sources`` adds leads to where each answer is written: the governing
    documents' passages, library files by name, and precedent violations for a complaint. It never approves, denies,
    or assigns a request."""
    from jason.community.responses import ResponseKind
    from jason.tasks import responses as task

    c, root = _community(), _root(data_dir)
    found = task.handle(c, root) + (task.email_requests(c, root) if include_email else [])
    if kind:
        try:
            k = ResponseKind(kind)
        except ValueError:
            return {"error": f"kinds: {', '.join(x.value for x in ResponseKind)}"}
        found = [h for h in found if h.kind is k]
    if open_only:
        found = [h for h in found if h.closed is None]
    found.sort(key=lambda h: (h.closed is not None, h.due or date.max))
    shown = found[: max(1, int(limit))]
    leads: dict[str, Any] = {}
    if sources:
        from jason.tasks.response_sources import SourceContext, sources_for

        ctx = SourceContext(root, c)
        leads = {str(h.request["id"]): sources_for(h, c, ctx) for h in shown}
    rows = []
    for h in shown:
        row = {"id": h.request["id"], "kind": h.kind.value, "unit": h.request.get("unit"), "title": h.request.get("title"),
               "received": _day(h.received), "due": _day(h.due), "clock": h.clock,
               "clockSource": h.rule.source.value if h.rule else None, "owner": h.rule.assignment if h.rule else None,
               "acknowledged": _day(h.acknowledged), "answered": _day(h.answered), "closed": _day(h.closed),
               "standing": h.standing, "next": h.rule.first_step if h.rule else "", "classifiedBy": h.why}
        if sources:
            row["sources"] = leads.get(str(h.request["id"]), {})
        rows.append(row)
    caveat = "Email kinds come from subjects; a proposed clock is a target until the board adopts it."
    if sources:
        caveat += " Each source is a lead to read, not a ruling; a precedent shows past handling, not this matter's facts."
    return {"summary": task.summary(found), "requests": rows, "caveat": caveat}


def request_kinds_measure(misses: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    """How well requests' kinds are read: precision and recall per kind against the hand-labelled gold set
    (``data/responses/kind-gold.json``, private), for PayHOA requests, email threads, and both. ``misses`` adds each
    request read wrongly with the rule that decided it."""
    from jason.tasks import request_kinds

    try:
        result = request_kinds.measure(_root(data_dir), _community())
    except FileNotFoundError:
        return {"error": "no gold set: label requests in data/responses/kind-gold.json (docs/responses.md)"}
    if not misses:
        result = {k: v for k, v in result.items() if k != "misses"}
    result["caveat"] = "The rules were tuned on this set, so the scores are an upper bound until new requests are labelled."
    return result


def acknowledgment_draft(request_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    """A first comment to the owner for an open, unacknowledged request, for a person to read and send: what was
    received and when, and a response date only where the law or the documents set one. It sends nothing; the
    result names how a person sends it."""
    from jason.tasks import responses as task

    c, root = _community(), _root(data_dir)
    for h in task.handle(c, root) + task.email_requests(c, root):
        if str(h.request["id"]) == str(request_id):
            send = (f'jason request-comment {h.request["id"]} "<the text>"' if str(h.request["id"]).isdigit()
                    else f"jason respond --draft {h.request['id']} --gmail (a dry run; --yes saves a Gmail draft in "
                         f"the thread for a person to send): {h.request.get('link', '')}")
            return {"id": h.request["id"], "draft": task.acknowledgment(h, c), "send": send,
                    "acknowledged": _day(h.acknowledged)}
    return {"error": f"no request {request_id}"}


# --- The notice catalog and delivery ----------------------------------------------------------------------------------

def notice_requirements(key: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The notices the law requires, from the notice catalog: with no ``key``, every requirement's key, statute,
    recipients, and clock; with ``key`` (``board-meeting``, ``discipline-hearing``), one in full: methods, clock,
    content, the evidence that proves it, and what the governing documents add (the stricter clock governs)."""
    from jason.community.notice_catalog import REQUIREMENTS, requirement

    if not key:
        return {"requirements": [{"key": r.key, "title": r.title, "statute": r.statute, "verified": r.verified,
                                  "clock": "; ".join(t.describe() for t in r.timing)} for r in REQUIREMENTS]}
    try:
        r = requirement(key)
    except KeyError:
        return {"error": f"no requirement {key}", "keys": [x.key for x in REQUIREMENTS]}
    provisions = [p for p in getattr(_community(), "notice_provisions", lambda: ())()
                  if getattr(p, "requirement", "") == key]
    return {"key": r.key, "title": r.title, "statute": r.statute, "verified": r.verified,
            "recipients": str(getattr(r.recipients, "value", r.recipients)),
            "methods": [str(getattr(m, "value", m)) for m in r.methods],
            "clock": [t.describe() for t in r.timing], "content": list(r.content),
            "proof": [str(getattr(e, "value", e)) for e in r.evidence], "note": r.note, "caveat": r.caveat,
            "documents": [{"document": p.document, "section": p.section, "comparison": p.comparison.value,
                           "says": p.says} for p in provisions]}


def notice_delivery(key: str, general: bool = False, data_dir: Path | None = None) -> dict[str, Any]:
    """One notice's delivery to every member, from the ledger ``jason notices KEY --sync`` keeps: who was reached, who
    bounced or was skipped, and the follow-ups the law asks for (a bounce resent by mail, Civil Code 4041(e)).
    ``general`` treats a posted general notice under 4045. Reads disk only; sync first for the latest."""
    import json

    from jason.tasks import notice_ledger

    attempts = notice_ledger.load(_root(data_dir), key)
    general = general or notice_ledger.is_general(_root(data_dir), key)
    if not attempts:
        return {"error": f"no attempts for {key} in the ledger (jason notices {key} --sync)"}
    return {"key": key, "standing": json.loads(notice_ledger.as_json(notice_ledger.standing(attempts, general=general))),
            "summary": notice_ledger.lines(notice_ledger.standing(attempts, general=general))[0]}


# --- The documents' duties --------------------------------------------------------------------------------------------

def document_duties(key: str, kind: str = "", timed: bool = False, limit: int = 80,
                    data_dir: Path | None = None) -> dict[str, Any]:
    """The norms a governing document states (``jason duties --documents KEY``): each duty, prohibition, permission,
    right, or condition with its section, quote, bearer, deadline or recurrence, trigger, whether it is a duty to give
    notice, and its review. ``timed`` keeps those with a deadline or recurrence. A reading is a lead for a person to
    review; about one in five across the corpus is the wrong kind."""
    from jason.tasks.document_duties import stored

    found = stored(_root(data_dir), key)
    if not found:
        return {"error": f"no readings for {key} (jason duties --documents {key})"}
    found = [d for d in found if (not kind or d.kind.value == kind)
             and (not timed or (d.timed and d.kind.value != "definition"))]
    return {"count": len(found), "duties": [{
        "id": d.id, "section": d.section, "kind": d.kind.value, "bearer": d.bearer.value, "quote": d.quote,
        "action": d.action, "trigger": d.trigger, "deadline": str(d.deadline) if d.deadline else None,
        "recurrence": d.recurrence, "notice": d.notice, "review": d.review.value} for d in found[: max(1, int(limit))]]}


# --- What needs attention ---------------------------------------------------------------------------------------------

def governance_digest(section: str = "", limit: int = 8, past: int = 30, private: bool = False,
                      data_dir: Path | None = None) -> dict[str, Any]:
    """Start here for "what needs attention" in the governance systems: each board meeting's notice (CIV 4920) and
    minutes (4950(a)) deadlines read against the record (a deadline passed with none on record, a record late, one
    near; none on record is not none given; the section's counts carry every meeting watched); schedule items overdue
    or due soon by role; people's own Google Tasks and calendar events read beside what jason tracks (open tasks past
    their due day, tasks a rule says to close, untracked recurring items as proposed clocks; nothing in Google is
    marked or closed); members' requests past or near their clocks (a statute's clock first); open intake questions
    by kind, the likely ones apart; open conflicts by status (counsel, board, noted); notices with follow-ups owed;
    living documents with failed rule checks, held sources, or drift; and the documents' timed duties nothing tracks.
    Most urgent first: a passed clock the law or the documents set (LEGAL), then overdue, due soon, open, noted. Each
    section is capped at ``limit`` with its total, and each line names the command that gives the detail (the tools:
    schedule_agenda, member_requests, intake_questions, document_conflicts, notice_delivery, living_document,
    document_duties). ``section`` narrows to one (meetings, schedule, people, requests, intake, conflicts, notices,
    living, duties); ``private`` leaves units out and replaces each person's task title with its rule's label (a title
    can name an owner or a unit). A section whose store is missing is reported unavailable, not raised. Reads disk
    only; decides nothing."""
    from jason.tasks import attention

    try:
        found = attention.digest(_community(), _root(data_dir), limit=max(1, int(limit)), past=max(0, int(past)),
                                 sections=(section,) if section else attention.SECTIONS, private=private)
    except ValueError as exc:
        return {"error": str(exc)}
    return found.as_dict()


# --- Citations --------------------------------------------------------------------------------------------------------

def cite_document(expression: str, as_of: str = "", text: bool = True, data_dir: Path | None = None) -> dict[str, Any]:
    """Cite and recite one of the association's documents or records, the way a person or a document writes it:
    "Declaration § 6.2(a)", "Section 6.2(a) of the Declaration", "Bylaws Art. 6", "Rules R-3(e)",
    "Resolution 20990101-1", "Doc. No. 209901010001", "minutes 2099-01-01", "CIV 4920(a)", or a canonical
    ``decl#6.2(a)``; ``as_of`` (YYYY-MM-DD) gives the words in force on a day. Returns ``kind`` (section, outline,
    record, statute, miss), ``found``, the ``citation``, the stored words whole (``text``), the version in force
    (``inForce``), and ``history`` (the instruments that changed it; one not in force is flagged, never merged). A
    document, an article, a span, or siblings is an ``outline``, never concatenated words; a miss has its ``reason``.
    Recite the words first, with the citation and the caveat; any reading of them is yours, labeled as one. The
    consolidated text is not an official restatement; the recorded instruments control."""
    from jason.tasks.cite import resolve

    return resolve(expression, as_of=as_of or None, text=bool(text), data_dir=_root(data_dir))


def section_refs(expression: str, hops: int = 1, direction: str = "out", data_dir: Path | None = None) -> dict[str, Any]:
    """The references around one section or record (same expressions as ``cite_document``). ``direction`` "out"
    follows what its words cite (other documents' sections, statutes on disk, resolutions, instruments) for ``hops``
    hops (0 follows until a target repeats), each node found or missing with a reason; "in" lists what names it: the
    governing documents' sections and jason's own records (Conflict rows, notice provisions and requirements, document
    duties, schedule assignments, response rules, templates, procedures, lessons, embedded references and their
    renderings), each with its scope (exact, within, enclosing) and how the cited words stand now (current, amended,
    words changed since read, removed, missing). "both" gives both. A record's own summary is ``jasonsReading``,
    shown beside ``recitedWords``: a reading, never the provision. References are read from the documents' current
    outlines (``jason outlines``); a reference the grammar missed stays missed."""
    from jason.tasks.cite import Shelf

    if direction not in ("out", "in", "both"):
        return {"error": "direction is out, in, or both"}
    shelf = Shelf(None, _root(data_dir))
    c = shelf(expression).hops(None if int(hops) <= 0 else int(hops))
    try:
        return c.as_dict(text=False, refs=direction in ("out", "both"), cited_by=direction in ("in", "both"))
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"kind": "miss", "found": False, "reason": "unreadable", "detail": str(exc), "expression": expression}


def embedded_copies(key: str = "", host: str = "", stale_only: bool = False, owner: str = "",
                    data_dir: Path | None = None) -> dict[str, Any]:
    """The last scan's copies of governing-document sections in other documents (``jason section-refs --scan``):
    each host with who owns it and what may be done (a token for jason's own sources; report only for adopted
    documents and vendor templates; never rewritten for what was sent or recorded), and each copy's section, kind,
    coverage, and whether it reads as the current words, superseded ones, or a draft's. ``key`` narrows to a document,
    ``host`` to hosts whose name contains it, ``owner`` to one owner, ``stale_only`` to stale copies. A copy is found
    by shared words: a lead to read beside the section, not a finding. The consolidated text is not an official
    restatement."""
    from jason.tasks import section_refs as sr

    return sr.embedded_copies(_root(data_dir), key=key, host=host, stale_only=bool(stale_only), owner=owner)


TOOLS = (living_document, document_conflicts, intake_questions, answer_intake_question, schedule_agenda,
         schedule_assignments, record_completion, member_requests, request_kinds_measure, acknowledgment_draft,
         notice_requirements, notice_delivery, document_duties, governance_digest, cite_document, section_refs,
         embedded_copies)

__all__ = [t.__name__ for t in TOOLS] + ["TOOLS"]
