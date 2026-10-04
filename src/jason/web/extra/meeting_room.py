"""The meeting room page: the meeting as the board sees it, the agenda plan's items, and the live room record.

The loader merges three things that already exist: ``jason.web.sources.meeting`` (the date, directors, items, the
decisions recorded, and the commands), the agenda plan's candidates (``jason.web.extra.agenda_plan``, tolerated when
it is not there), and the room record ``jason.tasks.meeting_room`` keeps. It adds the quorum, each motion's tally, the
owner roster for the waiting room when the PayHOA catalog is on disk, and the caveats. The write applies one named
action to the room; it is a person's act, recorded as theirs. jason calls neither Zoom nor Google from here: it does not
admit anyone it cannot match, remove anyone, end the meeting, start or pause a recording, or record a vote on its own.

The executive session is kept apart. Civil Code 4935(e): "Any matter discussed in executive session shall be generally
noted in the minutes of the immediately following meeting that is open to the entire membership." The loader's answer
reaches anyone who opens the room, members included, so outside the private view it carries an executive matter only
by its ``ExecutiveSubject`` in the statute's words (never the item's title or id, which can name the member or the
matter) and never the executive record. The executive record (``meetings/room-<date>-executive.json``, P3) and the
matters' titles are added only for a viewer whose private view is open and whose offices open P3 in it
(``jason.web.access.check``), and each such answer is logged in ``access/served.jsonl``.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

CAVEATS = (
    "The chair runs the meeting and the board decides; jason keeps the agenda on screen and the record.",
    "Director votes are a roll call by name (CIV 4926(a)(3)). Polls are members' input, never a board vote.",
    "A recused director counts toward the quorum and not toward the vote (Corp. Code 7233; CIV 5350).",
    "A topic not on the posted agenda takes only a CIV 4930 path, and each choice is logged.",
    "Executive session stays out of the open minutes, recording, and transcript (CIV 4935, 5215); the host pauses and resumes them, not jason.",
    "In executive session the record is kept apart (P3, the private view): the open log notes only the 4935 subject in general terms, the times, and the return (CIV 4935(e)).",
    "jason does not admit anyone it cannot match to the owner roster, remove anyone, end the meeting, or record a vote on its own.",
    "Draft minutes go through Approvals (the secretary) before members see them; they are due within 30 days (CIV 4950).",
)

KIND_LABELS = {"call": "Call to order", "forum": "Open forum", "consent": "Consent", "report": "Report", "action": "Action",
               "discussion": "Discussion", "exec": "Executive session", "adjourn": "Adjournment"}


def _candidates(date: str) -> tuple[list[dict[str, Any]], str]:
    """The agenda plan's candidates for ``date``, or none with the reason."""
    try:
        from jason.web.extra.agenda_plan import agenda_plan

        plan = agenda_plan({"date": date})
    except Exception as exc:  # the plan is another store; the room stands without it
        return [], f"agenda plan: {type(exc).__name__}: {exc}"
    if not isinstance(plan, dict) or plan.get("found") is False:
        return [], str((plan or {}).get("note", "") or "no agenda plan for this meeting") if isinstance(plan, dict) else "no agenda plan"
    rows = plan.get("candidates") or []
    return [c for c in rows if isinstance(c, dict)], ""


def _first(c: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for k in keys:
        if c.get(k) not in (None, ""):
            return c[k]
    return default


HELD = "Executive session: the record is kept apart (open the private view to see it)."
SUBJECT_MISSING = "name the 4935 subject first"


def executive_matters(base: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    """The executive matters on the agenda, in order: ``{id, title, subject}``. The subject is the matter's
    ``ExecutiveSubject`` value (the plan's ``subject``, else the item's own), or "" when none is named; it is never
    guessed from the title. The id and title are for the private view and the write only."""
    from jason.community.models.meetings import executive_subject

    def subject(c: dict[str, Any]) -> str:
        s = executive_subject(_first(c, "subject", "executiveSubject", "executive_subject"))
        return s.value if s is not None else ""

    out: list[dict[str, str]] = []
    if candidates:
        picked = [c for c in candidates if c.get("include", True)]
        picked.sort(key=lambda c: (int(_first(c, "order", default=10**6) or 10**6), str(_first(c, "title"))))
        for n, c in enumerate(picked, 1):
            if "exec" in str(_first(c, "session", "agendaSession", default="open")).lower():
                out.append({"id": str(_first(c, "id", default=f"item-{n}")), "title": str(_first(c, "title", default=f"Item {n}")), "subject": subject(c)})
    else:
        for n, it in enumerate(base.get("items") or [], 1):
            if it.get("agendaSession", "open session") != "open session":
                out.append({"id": str(it.get("id", f"item-{n}")), "title": str(it.get("title", f"Item {n}")), "subject": subject(it)})
    return out


def agenda(base: dict[str, Any], candidates: list[dict[str, Any]], room: dict[str, Any], *, private: bool = False) -> list[dict[str, Any]]:
    """The stage's items in order: call to order, open forum, the open-session items (the plan's included candidates in
    their order, else the meeting's open items), executive session when there are executive matters, adjournment.

    The executive item names its matters only by their 4935 subjects in general terms (``matters``; 4935(e)); each row
    of ``executiveMatters`` is ``{ref, subject, general, named}``, plus ``id`` and ``title`` only when ``private``.
    A matter with no subject is counted as unnamed: it cannot be taken into executive session until it is named."""
    from jason.community.models.meetings import EXECUTIVE_GENERAL_TERMS, executive_general_note, executive_subject

    def row(id_: str, kind: str, title: str, **more: Any) -> dict[str, Any]:
        return {"id": id_, "kind": kind, "label": KIND_LABELS.get(kind, kind.capitalize()), "title": title, "facts": [], "motion": "",
                "threshold": "majority", "recused": [], "allot": 0, "packet": [], "brief": None, "session": "open session", **more}

    items = [row("call", "call", "Call to order and roll call", allot=3),
             row("forum", "forum", "Open forum", allot=int(room.get("openForum", {}).get("limitMinutes", 3) or 3) * 5)]
    executive = executive_matters(base, candidates)
    if candidates:
        picked = [c for c in candidates if c.get("include", True)]
        picked.sort(key=lambda c: (int(_first(c, "order", default=10**6) or 10**6), str(_first(c, "title"))))
        for n, c in enumerate(picked, 1):
            session = str(_first(c, "session", "agendaSession", default="open")).lower()
            title = str(_first(c, "title", default=f"Item {n}"))
            if "exec" in session:
                continue
            kind = str(_first(c, "kind", default="action")).lower()
            items.append(row(str(_first(c, "id", default=f"item-{n}")), kind, title, label=f"Item {len(items) - 1} · {KIND_LABELS.get(kind, kind.capitalize())}",
                             facts=[str(f) for f in (c.get("facts") or [])], motion=str(_first(c, "motion")),
                             threshold=str(_first(c, "threshold", default="majority")), recused=[str(r) for r in (c.get("recused") or c.get("conflicts") or [])],
                             allot=int(_first(c, "allot", default=0) or 0), packet=[p for p in (c.get("packet") or []) if isinstance(p, dict)],
                             brief=c.get("brief") if isinstance(c.get("brief"), dict) else None, suggestion=str(_first(c, "suggestion"))))
    else:
        for n, it in enumerate(base.get("items") or [], 1):
            title = str(it.get("title", f"Item {n}"))
            if it.get("agendaSession", "open session") != "open session":
                continue
            items.append(row(str(it.get("id", f"item-{n}")), "action", title, label=f"Item {len(items) - 1} · Action",
                             facts=[s for s in (str(it.get("ask", "")), str(it.get("authority", ""))) if s], allot=int(it.get("allot", 0) or 0)))
    if executive:
        rows: list[dict[str, Any]] = []
        for n, m in enumerate(executive, 1):
            s = executive_subject(m["subject"])
            r: dict[str, Any] = {"ref": str(n), "subject": m["subject"], "general": EXECUTIVE_GENERAL_TERMS[s][0] if s else "", "named": s is not None}
            if private:
                r.update(id=m["id"], title=m["title"])
            rows.append(r)
        named = [m["subject"] for m in executive if m["subject"]]
        note = executive_general_note(named)
        unnamed = sum(1 for r in rows if not r["named"])
        items.append(row("exec", "exec", "Adjourn to executive session", allot=2,
                         matters=list(dict.fromkeys(r["general"] for r in rows if r["named"])), executiveMatters=rows, unnamed=unnamed,
                         subjectNote=(f"{SUBJECT_MISSING}: {unnamed} executive matter{'s' if unnamed != 1 else ''} without a Civil Code 4935 "
                                      "subject (litigation, contracts, member discipline, personnel, a member's payment of assessments, "
                                      "or a foreclosure decision)") if unnamed else "",
                         motion=f"Move to adjourn to executive session to discuss {note}." if note else ""))
    items.append(row("adjourn", "adjourn", "Adjourn", allot=1))
    return items


def _roster(root) -> dict[str, Any]:
    """The owner roster from the PayHOA catalog on disk (``jason sync-catalog``), for matching the waiting room; or not synced."""
    try:
        from jason.tasks.broadcast import catalog_rows

        units, people, synced = catalog_rows(root / "payhoa.db")
    except Exception as exc:
        return {"synced": "", "count": 0, "rows": [], "note": f"roster not synced: {type(exc).__name__}"}
    if not units and not people:
        return {"synced": "", "count": 0, "rows": [], "note": "roster not synced; run jason sync-catalog"}
    by_id = {int(p["id"]): p for p in people if p.get("id") is not None and not p.get("deletedAt")}

    def name(p: dict[str, Any]) -> str:
        return str(p.get("name") or " ".join(str(p.get(k) or "") for k in ("firstName", "lastName")).strip() or p.get("email") or "").strip()

    rows: list[dict[str, str]] = []
    for u in units:
        if u.get("deletedAt"):
            continue
        label = str(u.get("title") or u.get("address") or u.get("id") or "")
        for o in u.get("owners") or []:
            if o.get("deletedAt"):
                continue
            p = by_id.get(int(o["membershipId"])) if o.get("membershipId") is not None else None
            n = name(p) if p else name(o)
            if n:
                rows.append({"name": n, "unit": label})
    return {"synced": synced, "count": len(rows), "rows": rows, "note": ""}


def _zoom(root: Any, day: str) -> dict[str, Any]:
    """The Zoom commands for the day's meeting: the sync, and when `jason zoom --create-board-meeting` scheduled it,
    the recording controls and the caption line a person may run as the host."""
    from jason.tasks.zoom import board_meeting

    created = board_meeting(root, day) or {}
    meeting_id = (created.get("zoom") or {}).get("id")
    commands = {"sync": "jason zoom", "meeting": f"jason zoom --meeting {day}"}
    if meeting_id:
        commands.update({"recordingPause": f"jason zoom --recording pause --meeting-id {meeting_id} --yes",
                         "recordingResume": f"jason zoom --recording resume --meeting-id {meeting_id} --yes",
                         "caption": f"jason zoom --caption \"<the answer>\" --meeting-id {meeting_id} --yes"})
    note = ("jason reads the Zoom account's history to disk (jason zoom). Admitting, muting, polls, and breakout rooms are the host's acts in Zoom; the room logs them."
            + (" The recording controls and the caption line run as the host from a terminal, each logged under the meeting id; a caption is seen by everyone."
               if meeting_id else " Schedule the meeting with jason zoom --create-board-meeting to get the recording and caption commands here."))
    return {"commands": commands, "meetingId": meeting_id, "admitCommand": "", "note": note}


def private_view(day: str, path: str = "") -> bool:
    """Whether this request may see the executive record for ``day``: a signed-in viewer whose private view is open and
    whose offices open P3 in it (``jason.web.access.check``). When so, the answer is logged in ``access/served.jsonl``
    under ``path`` (the executive file's, by default) before it goes out; a log that cannot be written shows nothing.
    False outside a request, with no sign-in, or on any failure: the record stays held."""
    try:
        from flask import has_request_context

        from jason.web import access

        if not has_request_context():
            return False
        viewer, refused = access.check(access.Level.P3)
        if refused is not None or viewer is None:
            return False
        access.served(viewer, access.Level.P3, path=path or f"meetings/room-{day}-executive.json")
        return True
    except Exception:  # noqa: BLE001 - anything unclear keeps the executive record held
        return False


def meeting_room(args: Args) -> dict[str, Any]:
    """The meeting (``meeting`` loader), the plan's items, the open room record with tallies, the quorum, the roster, and
    the caveats. ``executive`` is ``{shown, active, note, record}``: the executive record (``record``) only in the
    private view (``private_view``), else ``record`` is None and ``note`` says it is kept apart (CIV 4935(e))."""
    from jason.mcp.county import _data_dir
    from jason.tasks import meeting_room as store
    from jason.web.sources import meeting as meeting_loader

    base = meeting_loader(args)
    if base.get("found") is False:
        return base
    root = _data_dir(None)
    day = base["date"]
    candidates, plan_note = _candidates(day)
    room = store.load(root, day)
    directors = [str(d) for d in (base.get("directors") or room.get("directors") or [])]
    room["directors"] = directors
    private = private_view(day)
    items = agenda(base, candidates, room, private=private)
    notes = list(base.get("notes") or []) + ([plan_note] if plan_note else [])
    roster = _roster(root)
    if roster.get("note"):
        notes.append(roster["note"])
    record = store.executive_view(room, store.load_executive(root, day)) if private else None
    executive = {"shown": private, "active": bool(room["executive"].get("active")), "note": "" if private else HELD, "record": record}
    return {
        "found": True, "date": day, "today": base.get("today", ""), "directors": directors, "quorum": store.quorum(directors),
        "items": items, "room": store.with_tallies(room), "executive": executive, "decisions": base.get("decisions", []),
        "plan": {"found": bool(candidates), "count": len(candidates)},
        "roster": roster, "offAgendaPaths": [{"path": k, "text": v} for k, v in store.OFF_AGENDA_PATHS.items()],
        "zoom": _zoom(root, day),
        "commands": {**(base.get("commands") or {}), "minutesDraft": f"jason board --minutes {day}"},
        "minutesKey": f"minutes/{day}", "notes": notes, "caveats": list(CAVEATS),
    }


def _agenda_matters(day: str) -> list[dict[str, str]] | None:
    """The day's executive matters as the loader orders them, or None when the meeting or the plan cannot be read."""
    try:
        from jason.web.sources import meeting as meeting_loader

        base = meeting_loader({"date": day})
        if base.get("found") is False:
            return None
        candidates, _ = _candidates(day)
        return executive_matters(base, candidates)
    except Exception:  # noqa: BLE001 - the chair's named subjects still go to the store, which checks each one
        return None


def resolve_matters(day: str, body: dict[str, Any]) -> list[dict[str, Any]]:
    """The matters an ``executive_start`` takes in, each ``{id, title, subject}``. A matter is given by ``ref`` (its
    place among the agenda's executive matters, as the loader numbers them) or ``id``, with the ``subject`` the chair
    names when the agenda names none; the agenda's own subject wins over the body's. With no matters in the body, every
    executive matter on the agenda. The store refuses any matter left without a subject (``NAME_SUBJECT``)."""
    rows = _agenda_matters(day)
    given = body.get("matters")
    if given is None and body.get("subjects"):
        return [{"subject": s} for s in body["subjects"]]
    if given is None:
        given = [{"ref": str(n)} for n in range(1, len(rows or []) + 1)]
    if not isinstance(given, list):
        raise ValueError("matters is a list of {ref, subject}")
    out: list[dict[str, Any]] = []
    for n, g in enumerate(given, 1):
        g = g if isinstance(g, dict) else {"subject": g}
        ref, ident = str(g.get("ref", "") or "").strip(), str(g.get("id", "") or "").strip()
        found = None
        if rows:
            if ref.isdigit() and 1 <= int(ref) <= len(rows):
                found = rows[int(ref) - 1]
            elif ident:
                found = next((r for r in rows if r["id"] == ident), None)
        out.append({"id": (found or {}).get("id") or ident or f"matter-{ref or n}", "title": (found or {}).get("title", ""),
                    "subject": (found or {}).get("subject") or g.get("subject") or ""})
    return out


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Apply one action (``body.action``) to the room for the meeting ``key`` (an ISO date) as ``body.by``. The directors come
    from the board roster on disk unless the body carries them. Returns the open room with tallies, never the executive
    record: a write's answer is not the private view. ``executive_start`` takes the agenda's executive matters by
    ``ref`` (``resolve_matters``); one with no 4935 subject is refused ("name the 4935 subject first")."""
    from jason.mcp.county import _data_dir
    from jason.tasks import meeting_room as store

    root = _data_dir(None)
    directors = body.get("directors")
    if not directors:
        try:
            from jason.tasks.board_members import current_names

            directors = current_names(root)
        except Exception:
            directors = []
    clean = {k: v for k, v in body.items() if k not in ("by", "directors")}
    if clean.get("action") == "executive_start":
        clean["matters"] = resolve_matters(key, clean)
        clean.pop("subjects", None)
    room = store.update(root, key, clean, by=str(body.get("by", "") or ""), directors=[str(d) for d in directors or []])
    return store.with_tallies(room)
