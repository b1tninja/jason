"""The owner view's loaders, and the guard that serves them (docs/console/security-and-privacy.md, the owner view).

The owner view (``?view=owner``) is a view, not a sign-in: anyone at the machine can switch back. What it decides is
what a screen marked for owners is sent, and the server decides that, not the page. Every read the console makes in
the owner view carries ``view=owner``; ``install`` answers such a read only from ``OWNER_SOURCES``, each a loader
that copies what a member is entitled to and nothing else (an allowlist, never a filter of the board's answer):

- open-session meetings and minutes (Civil Code 4925, 4950): the posted notice, the agendas, and the minutes, never
  an executive session's record, a transcript, a recording, or the board's checks;
- the annual disclosures members receive (5300, 5305, 5310, 4041, and those the policy statement carries), with when
  each is due and the day the delivery ledger shows it went out;
- the reserve summary and the insurance summary the budget report carries (5300(b)(9), 5565, 5570);
- the records request form and the record kinds a member may ask for (5200-5215), never another member's request;
- the meeting room's stage for the open session, never the roster, the log, the polls, or executive matters;
- the public owner page and the brand (``community-profile``, ``theme``), which are built for owners already.

A source with no owner loader answers 403 in the owner view. No owner loader sends an owner's name, a unit, a
balance, a lien, a delinquency, a hearing, a discipline, or an executive item.

``owner_digest`` (``GET /api/owner-digest``) is the owner's Overview in place of the board's digest: the next open
meeting, the latest approved open minutes, the annual disclosures, the community's adopted standards and policies, and
how to make a records request. Reads disk only; nothing here writes.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

Args = dict[str, str]
Loaders = dict[str, Callable[[Args], dict[str, Any]]]

VIEW = "view"
OWNER = "owner"
REFUSED = "{name} is the board's: it is not served in the owner view."

# Meeting records a member is entitled to (CIV 4920, 4950), from the places they are posted or sent to members. jason's
# own drafts and the association's email are the board's working copies; a transcript, a recording, a chat, an AI
# summary, and an executive session's agenda are not open-session records a member receives.
MEMBER_KINDS = ("meeting notice", "agenda", "draft minutes", "minutes")
POSTED = ("PayHOA library", "Drive", "PayHOA communication")
OPEN_LEVELS = ("P0", "P1")

# The annual disclosures a member receives (notice_catalog rows with ``annual`` and every member as recipient).
DELIVERED_WORDS = {"delivered": "delivered", "sent, with follow-ups owed": "sent", "sent": "sent"}

CAVEATS = (
    "This is the owner view: what a member receives or may ask for. It is a view of the console, not a sign-in.",
    "Read from the association's records by jason. A record listed is on file; it is not reviewed or certified.",
    "Association records may not be used for a purpose unrelated to a member's interest as a member (CIV 5230).",
)


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _community() -> Any:
    from jason.community import community

    return community()


def _today(args: Args) -> date:
    raw = str(args.get("today", "") or "").strip()
    try:
        return date.fromisoformat(raw) if raw else date.today()
    except ValueError:
        return date.today()


# ------------------------------------------------------------------------------------------------------------------
# Meetings: the open session's posted records


def _member_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The records of one meeting a member is entitled to: a member kind, posted, and not confidential."""
    return [r for r in records or () if isinstance(r, dict) and str(r.get("kind") or "") in MEMBER_KINDS
            and str(r.get("where") or "") in POSTED and not r.get("confidential")]


def _docs(records: list[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    """The member's records as document references grouped by kind, each at an open level only (a reference the
    server places at P2 or above is the board's, whatever its kind)."""
    from jason.web.extra.meeting_docs import record_refs

    try:
        groups = record_refs(records, root)
    except Exception:  # noqa: BLE001 - a reference that cannot be built is left out, never guessed
        return []
    out = []
    for g in groups:
        docs = [d for d in g.get("docs") or [] if str(d.get("level") or "") in OPEN_LEVELS]
        if docs:
            out.append({"kind": g["kind"], "docs": docs})
    return out


def _has(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r in records:
        where = out.setdefault(str(r["kind"]), {})
        where[str(r["where"])] = where.get(str(r["where"]), 0) + 1
    return out


def _catalog(root: Path) -> list[dict[str, Any]]:
    from jason.tasks.meeting_catalog import load

    try:
        return [m for m in (load(root).get("meetings") or []) if isinstance(m, dict) and m.get("date")]
    except Exception:  # noqa: BLE001 - no catalog is no meetings, said in the note
        return []


def owner_meetings(args: Args) -> dict[str, Any]:
    """Each meeting's open-session records on file (the notice, the agendas, the minutes), newest first; with
    ``date``, that meeting's records as references. No titles (a call's topic can name a hearing), no checks, no
    schedule gaps, and no meeting that has no member record."""
    root = _root()
    catalog = _catalog(root)
    day = str(args.get("date", "") or "").strip()
    if day:
        found = next((m for m in catalog if m["date"] == day), None)
        records = _member_records(found.get("records") or []) if found else []
        if not records:
            return {"found": False, "date": day, "note": f"No open-session record of {day} is on file."}
        return {"found": True, "date": day, "docs": _docs(records, root)}
    rows = []
    for m in catalog:
        records = _member_records(m.get("records") or [])
        if records:
            rows.append({"date": m["date"], "titles": [], "has": _has(records), "checks": []})
    rows.sort(key=lambda r: r["date"], reverse=True)
    note = "" if catalog else "No meeting records are on file yet."
    return {"found": bool(rows), "count": len(rows), "meetings": rows, "scheduleGaps": [], "note": note,
            "caveats": list(CAVEATS) + ["Members receive the minutes of open board meetings, or a draft or summary, "
                                        "within 30 days (CIV 4950). Executive session is noted only generally."]}


def _next_meeting(community: Any, root: Path, today: date, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The next open meeting: the earlier of the schedule's next regular meeting and a meeting on file with a posted
    notice or agenda, with the agenda when it is posted."""
    schedule = None
    try:
        schedule = community.meeting_schedule()
    except Exception:  # noqa: BLE001 - a profile with no schedule has none
        schedule = None
    regular = None
    if schedule is not None:
        try:
            regular = schedule.next_meeting(today - timedelta(days=1))
        except Exception:  # noqa: BLE001
            regular = None
    posted = sorted(m["date"] for m in catalog if m["date"] >= today.isoformat()
                    and any(r["kind"] in ("meeting notice", "agenda") for r in _member_records(m.get("records") or [])))
    days = [d for d in ([regular.isoformat()] if regular else []) + posted[:1]]
    if not days:
        return None
    day = min(days)
    entry = next((m for m in catalog if m["date"] == day), None)
    records = [r for r in _member_records((entry or {}).get("records") or []) if r["kind"] in ("meeting notice", "agenda")]
    out: dict[str, Any] = {"date": day, "regular": bool(regular and day == regular.isoformat()),
                           "agendaPosted": any(r["kind"] == "agenda" for r in records), "docs": _docs(records, root)}
    if schedule is not None and out["regular"]:
        out.update(time=str(getattr(schedule, "time", "") or ""), place=str(getattr(schedule, "place", "") or ""))
    return out


def _latest_minutes(root: Path, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The newest meeting whose approved minutes (not a draft) are posted, with them as references."""
    for m in sorted(catalog, key=lambda m: m["date"], reverse=True):
        records = [r for r in _member_records(m.get("records") or []) if r["kind"] == "minutes"]
        if records:
            return {"date": m["date"], "docs": _docs(records, root)}
    return None


# ------------------------------------------------------------------------------------------------------------------
# The annual disclosures


def _fiscal_ends(community: Any, today: date) -> list[date]:
    try:
        end = community.fiscal_year_end()
    except Exception:  # noqa: BLE001
        end = None
    if not end:
        return []
    month, day = end
    out = []
    for year in (today.year - 1, today.year, today.year + 1):
        try:
            out.append(date(year, month, day))
        except ValueError:
            continue
    return out


def _window(req: Any, ends: list[date], today: date) -> tuple[date | None, date | None, str]:
    """The window a fiscal-year disclosure goes out in: the first whose last day is not past, and the clock in
    words. Other clocks give their words alone."""
    from jason.community.notices import Anchor

    words = "; ".join(t.describe() for t in req.timing)
    for t in req.timing:
        if t.anchor is not Anchor.FISCAL_YEAR_END:
            continue
        for end in ends:
            first, last = t.window(end)
            if last is None or last >= today:
                return first, last, words
    return None, None, words


def _ledger(root: Path) -> dict[str, tuple[date, str]]:
    """The latest delivery the ledger shows for each notice catalog requirement: (day, "delivered" or "sent"). Counts
    of members reached or owed stay on the board's screens."""
    try:
        from jason.tasks.notice_evidence import ledger

        records = ledger(root)
    except Exception:  # noqa: BLE001 - no ledger is no delivery shown
        return {}
    out: dict[str, tuple[date, str]] = {}
    for rec in records.values():
        word = DELIVERED_WORDS.get(getattr(rec.strength, "value", ""), "")
        if not rec.requirement or rec.on is None or not word:
            continue
        if rec.requirement not in out or rec.on > out[rec.requirement][0]:
            out[rec.requirement] = (rec.on, word)
    return out


def disclosures(community: Any, root: Path, today: date) -> list[dict[str, Any]]:
    """The annual disclosures every member receives, each with its statute, its window when the fiscal year is known,
    the day the ledger shows it went out, and the disclosures it carries."""
    from jason.community.notice_catalog import REQUIREMENTS
    from jason.community.notices import Recipients

    annual = [r for r in REQUIREMENTS if r.annual and r.recipients is Recipients.ALL_MEMBERS]
    ends = _fiscal_ends(community, today)
    shown = _ledger(root)
    rows = []
    for req in annual:
        if req.carried_by:
            continue
        first, last, words = _window(req, ends, today)
        went = shown.get(req.key)
        rows.append({"key": req.key, "name": req.title, "authority": req.statute, "rule": words,
                     "windowOpens": first.isoformat() if first else None, "next": last.isoformat() if last else None,
                     "delivered": went[0].isoformat() if went else None, "deliveredAs": went[1] if went else "",
                     "carries": [{"key": c.key, "name": c.title, "authority": c.statute} for c in annual if c.carried_by == req.key]})
    rows.sort(key=lambda r: (r["next"] or "9999", r["name"]))
    return rows


def owner_disclosures(args: Args) -> dict[str, Any]:
    """The annual disclosures members receive: due when, and the day the delivery ledger shows each went out."""
    today = _today(args)
    community = _community()
    rows = disclosures(community, _root(), today)
    note = "" if _fiscal_ends(community, today) else "The association's fiscal year is not set here, so the windows are not dated."
    return {"found": True, "asOf": today.isoformat(), "disclosures": rows, "note": note,
            "caveats": list(CAVEATS) + ["A delivery shown is what the association's delivery ledger records; a "
                                        "member who did not receive one may ask the association for a copy."]}


# ------------------------------------------------------------------------------------------------------------------
# Standards and policies, and how to ask for records


def standards(community: Any) -> dict[str, Any]:
    """The community's published standards: the response clocks its governing documents set. A proposed policy is
    never member-facing; until the board adopts one, there is none here."""
    rows = []
    try:
        from jason.community.responses import ClockSource, rules_for

        _, by_kind = rules_for(community)
        for rule in by_kind.values():
            if rule.source is ClockSource.DOCUMENTS and rule.days:
                rows.append({"kind": rule.kind.value, "days": rule.days, "businessDays": bool(rule.business_days),
                             "authority": rule.authority, "source": rule.source.value})
    except Exception:  # noqa: BLE001 - no rules read is none shown
        rows = []
    rows.sort(key=lambda r: r["kind"])
    return {"adopted": [], "standards": rows,
            "note": "No board policy is recorded as adopted yet. A proposed policy is not shown to members until the "
                    "board adopts it."}


def records_request() -> dict[str, Any]:
    """How a member asks for association records, with the clocks the statute sets (CIV 5205, 5210, 5215)."""
    from jason.community.notice_catalog import requirement

    clocks = []
    for key in ("records-current-year", "records-prior-years"):
        try:
            req = requirement(key)
        except KeyError:
            continue
        clocks.append({"key": req.key, "records": req.title, "authority": req.statute,
                       "clock": "; ".join(t.describe() for t in req.timing)})
    return {"screen": "records-requests", "clocks": clocks,
            "steps": ["Pick the records you want and how you'd like them (inspection or copies) on the Records screen.",
                      "Give your unit, and a purpose when you ask for the membership list.",
                      "The association answers within the time Civil Code 5210 sets, counted from when it receives the request.",
                      "A record withheld or redacted comes with its basis in writing, on request (Civil Code 5215)."],
            "produced": "What the board produced for you will show here once owners have accounts. Until then the "
                        "association sends it to you directly."}


def owner_digest(args: Args) -> dict[str, Any]:
    """The owner's Overview: the next open meeting (with its agenda when posted), the latest approved open minutes,
    the annual disclosures due or delivered, the community's adopted standards and policies, and how to make a
    records request. Nothing about any owner, unit, balance, lien, hearing, or executive session."""
    today = _today(args)
    community = _community()
    root = _root()
    catalog = _catalog(root)
    return {"found": True, "asOf": today.isoformat(),
            "nextMeeting": _next_meeting(community, root, today, catalog),
            "latestMinutes": _latest_minutes(root, catalog),
            "disclosures": disclosures(community, root, today),
            "policies": standards(community),
            "recordsRequest": records_request(),
            "caveats": list(CAVEATS)}


# ------------------------------------------------------------------------------------------------------------------
# Records: the request form's kinds


def owner_records(args: Args) -> dict[str, Any]:
    """The record kinds a member may ask for (CIV 5200), each with its citation, meaning, and retention, for the
    request form. No request of any member, and no count of what is on the shelf."""
    from jason.web.extra.records_requests import record_kinds

    kinds, note = record_kinds()
    rows = [{"record": k["record"], "label": k["label"], "citation": k["citation"], "meaning": k.get("meaning", ""),
             "retention": k.get("retention", "")} for k in kinds]
    return {"found": True, "count": 0, "counts": {}, "requests": [], "kinds": rows, "vias": [], "note": note,
            "produced": records_request()["produced"],
            "caveats": ["The membership list is shared only for purposes related to membership (CIV 5230).",
                        "A request recorded here is received by the association; a person answers it. jason produces nothing on its own."]}


# ------------------------------------------------------------------------------------------------------------------
# The summaries the budget report carries: reserves and insurance

_STUDIES: dict[str, tuple[tuple[tuple[str, int], ...], list[Any]]] = {}


def _studies(root: Path) -> list[Any]:
    from jason.tasks.reserves import load_studies, study_files

    files = study_files(root)
    stamp = tuple((str(p), p.stat().st_mtime_ns) for p in files)
    key = str(root.resolve())
    cached = _STUDIES.get(key)
    if cached is None or cached[0] != stamp:
        cached = _STUDIES[key] = (stamp, load_studies(root))
    return cached[1]


SUMMARY_KEYS = ("fiscalYear", "preparer", "prepared", "level", "beginningBalanceCents", "annualContributionCents",
                "requiredEndOfYearCents", "projectedEndOfYearCents", "percentFunded", "sufficientFor30Years", "components")


def owner_reserves(args: Args, loaders: Loaders | None = None) -> dict[str, Any]:
    """The reserve funding summary members receive with the budget report (CIV 5565, 5570), from the latest reserve
    study: its figures, and the percent funded over the studies on file. Not the ledger's transfers or memos."""
    try:
        from jason.tasks.reserves import history, latest_study

        studies = _studies(_root())
        latest = latest_study(studies)
    except Exception as exc:  # noqa: BLE001 - no study read is no summary, said
        return {"found": False, "summary": None, "years": [], "note": f"No reserve study could be read ({type(exc).__name__}).",
                "caveats": list(CAVEATS)}
    if latest is None:
        return {"found": False, "summary": None, "years": [], "note": "No reserve study is on file.", "caveats": list(CAVEATS)}
    rows = history(studies)
    summary = {k: v for k, v in history([latest])[0].items() if k in SUMMARY_KEYS}
    years = [{k: r.get(k) for k in ("fiscalYear", "percentFunded", "projectedEndOfYearCents", "requiredEndOfYearCents")} for r in rows]
    return {"found": True, "summary": summary, "years": years, "note": "",
            "caveats": list(CAVEATS) + ["The figures are the reserve study preparer's estimates; the board adopts the "
                                        "funding plan. The full reserve summary and the Assessment and Reserve Funding "
                                        "Disclosure Summary go to members with the annual budget report (CIV 5300, 5565, 5570)."]}


def _deductibles(community: Any) -> dict[str, int]:
    try:
        return {p.number: int(p.deductible_cents) for p in community.insurance().policies
                if p.number and p.deductible_cents is not None}
    except Exception:  # noqa: BLE001 - a profile with no insurance facts gives none
        return {}


def owner_insurance(args: Args, loaders: Loaders) -> dict[str, Any]:
    """The insurance summary (CIV 5300(b)(9)): each policy's kind, carrier, term, and deductible when the profile
    records it. Not the policy numbers, premiums, standings, letters, notices, findings, or claims."""
    board = loaders["insurance"]({})
    deductibles = _deductibles(_community())
    policies = []
    for p in board.get("policies") or []:
        if not isinstance(p, dict):
            continue
        terms = [{"start": t.get("start"), "end": t.get("end")} for t in p.get("terms") or [] if isinstance(t, dict)]
        policies.append({"kind": str(p.get("kind") or ""), "building": p.get("building"), "carrier": str(p.get("carrier") or ""),
                         "termEnd": p.get("termEnd"), "terms": terms, "deductibleCents": deductibles.get(str(p.get("number") or ""))})
    return {"found": bool(board.get("found", True)) and bool(policies), "asOf": str(board.get("asOf") or ""), "policies": policies,
            "claims": [], "note": "" if policies else "No policy is on file.",
            "caveats": list(CAVEATS) + ["The insurance summary goes to members with the annual budget report (CIV 5300(b)(9)); "
                                        "the policies themselves govern."]}


# ------------------------------------------------------------------------------------------------------------------
# The meeting room's stage, and the calendar


ITEM_KEYS = ("id", "kind", "label", "title", "facts", "motion", "threshold", "recused", "allot", "session")
MOTION_KEYS = ("id", "itemId", "title", "text", "mover", "second", "recused", "threshold", "votes", "result", "decidedAt",
               "movedAt", "tally")
ROOM_KEYS = ("date", "directors", "current", "presenter", "view", "mode", "attendance", "calledToOrder", "openForum",
             "adjournedAt", "present", "quorum")


def owner_meeting_room(args: Args, loaders: Loaders) -> dict[str, Any]:
    """The open session's stage as the shared screen shows it: the open items, the current one, the directors present,
    and the motions on open items. No roster of owners, no log, no polls, no admitted names, no executive matters,
    no packet or brief, and no commands."""
    day = str(args.get("date", "") or "").strip()
    if not day:  # the next open meeting, as the member digest reads it
        try:
            root = _root()
            found = _next_meeting(_community(), root, _today(args), _catalog(root))
            day = found["date"] if found else ""
        except Exception:  # noqa: BLE001 - the room's own default stands
            day = ""
    board = loaders["meeting-room"]({"date": day} if day else {})
    if board.get("found") is False:
        return {"found": False, "note": str(board.get("note") or "No meeting is set up.")}
    items = []
    for it in board.get("items") or []:
        if not isinstance(it, dict):
            continue
        if it.get("kind") == "exec":
            # Built from nothing of the board's item: its title, label, facts, and matters can name the matter.
            items.append({"id": "exec", "kind": "exec", "label": "Executive session", "title": "Executive session", "facts": [],
                          "motion": "Move to adjourn to executive session (CIV 4935).", "threshold": "majority", "recused": [],
                          "allot": it.get("allot") or 0, "session": "executive session", "packet": [], "brief": None, "matters": []})
            continue
        row = {k: it.get(k) for k in ITEM_KEYS}
        row.update(packet=[], brief=None, matters=[], facts=[str(f) for f in it.get("facts") or []])
        items.append(row)
    open_ids = {str(i["id"]) for i in items if i.get("kind") != "exec"}
    raw = board.get("room") or {}
    room = {k: raw.get(k) for k in ROOM_KEYS}
    ex = raw.get("executive") or {}
    room.update(executive={"active": bool(ex.get("active")), "startedAt": str(ex.get("startedAt") or ""),
                           "endedAt": str(ex.get("endedAt") or ""), "note": ""},
                motions=[{k: m.get(k) for k in MOTION_KEYS} for m in raw.get("motions") or []
                         if isinstance(m, dict) and str(m.get("itemId") or "") in open_ids],
                log=[], polls=[], admitted=[], transcriptSuggestions=[], history=[])
    for key, empty in (("directors", []), ("present", []), ("attendance", {}), ("openForum", {"count": 0, "limitMinutes": 0})):
        if room.get(key) is None:
            room[key] = empty
    return {"found": True, "date": str(board.get("date") or ""), "today": str(board.get("today") or ""),
            "directors": [str(d) for d in board.get("directors") or []], "quorum": board.get("quorum") or 0,
            "items": items, "room": room, "decisions": [], "plan": {"found": False, "count": 0},
            "roster": {"synced": "", "count": 0, "rows": [], "note": ""}, "offAgendaPaths": [],
            "zoom": {"commands": {}, "admitCommand": "", "note": ""}, "commands": {}, "minutesKey": "", "notes": [],
            "caveats": ["You are watching the open session. Executive session is closed to members (CIV 4935)."]}


def _passed(name: str) -> Callable[[Args, Loaders], dict[str, Any]]:
    """A source built for owners already (the public owner page, the brand): served as the board's loader answers it."""
    def serve(args: Args, loaders: Loaders) -> dict[str, Any]:
        return loaders[name](args)
    serve.__name__ = f"passed_{name.replace('-', '_')}"
    return serve


# Each source the owner view reads, and the loader that answers it there. A source not here is refused in the owner
# view. ``ui/src/ownerScreens.json`` names, for each screen the owner view shows, the sources it reads.
OWNER_SOURCES: dict[str, Callable[[Args, Loaders], dict[str, Any]]] = {
    "owner-digest": lambda args, loaders: owner_digest(args),
    "meetings": lambda args, loaders: owner_meetings(args),
    "calendar": lambda args, loaders: owner_disclosures(args),
    "records-requests": lambda args, loaders: owner_records(args),
    "reserves": owner_reserves,
    "insurance": owner_insurance,
    "meeting-room": owner_meeting_room,
    "community-profile": _passed("community-profile"),
    "theme": _passed("theme"),
}


def owner_read(name: str, args: Args, loaders: Loaders) -> dict[str, Any]:
    """What the owner view is sent for ``name``: its owner loader's answer, or ``PermissionError`` for a source the
    owner view does not read."""
    serve = OWNER_SOURCES.get(name)
    if serve is None:
        raise PermissionError(REFUSED.format(name=name))
    return serve({k: v for k, v in args.items() if k != VIEW}, loaders)


# Reads the owner view may make that are not sources: the session, and a document's bytes or thumbnail, which carry
# their own sign-in and data-level checks (``jason.web.access``).
PASSED_ENDPOINTS = frozenset({"session", "local_file", "drive.drive_thumb", "previews.pdf_thumb"})


def install(app: Any, loaders: Loaders) -> None:
    """Answer every ``GET /api/<source>?view=owner`` from ``OWNER_SOURCES``, before any other hook: an owner loader's
    answer, or 403 for a source the owner view does not read. Any other read under ``/api/`` in the owner view (an
    approval, the evidence) is refused too, except ``PASSED_ENDPOINTS``. Installed ahead of the private view's
    hold-back, so a confidential listing is never asked for in the owner view."""
    from flask import jsonify, request

    @app.before_request
    def _owner_view():
        if request.method != "GET" or request.args.get(VIEW) != OWNER or not request.path.startswith("/api/"):
            return None
        if request.endpoint in PASSED_ENDPOINTS:
            return None
        if request.endpoint != "source":
            resp = jsonify(error=REFUSED.format(name=request.path), ownerView=True)
            resp.status_code = 403
            resp.headers["Cache-Control"] = "no-store"
            return resp
        name = str((request.view_args or {}).get("name") or "")
        try:
            out = owner_read(name, request.args.to_dict(), loaders)
        except PermissionError as exc:
            resp = jsonify(error=str(exc), ownerView=True)
            resp.status_code = 403
        except ValueError as exc:
            resp = jsonify(error=str(exc))
            resp.status_code = 400
        except Exception as exc:  # noqa: BLE001 - a missing store is a miss to show, as the source route says it
            resp = jsonify(error=f"{type(exc).__name__}: {exc}")
            resp.status_code = 500
        else:
            resp = jsonify(out)
        resp.headers["Cache-Control"] = "no-store"
        return resp


__all__ = ["CAVEATS", "MEMBER_KINDS", "OWNER_SOURCES", "disclosures", "install", "owner_digest", "owner_disclosures",
           "owner_insurance", "owner_meeting_room", "owner_meetings", "owner_read", "owner_records",
           "owner_reserves", "records_request", "standards"]
