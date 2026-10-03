"""The meeting room page: the meeting as the board sees it, the agenda plan's items, and the live room record.

The loader merges three things that already exist: ``jason.web.sources.meeting`` (the date, directors, items, the
decisions recorded, and the commands), the agenda plan's candidates (``jason.web.extra.agenda_plan``, tolerated when
it is not there), and the room record ``jason.tasks.meeting_room`` keeps. It adds the quorum, each motion's tally, the
owner roster for the waiting room when the PayHOA catalog is on disk, and the caveats. The write applies one named
action to the room; it is a person's act, recorded as theirs. jason calls neither Zoom nor Google from here: it does not
admit anyone it cannot match, remove anyone, end the meeting, start or pause a recording, or record a vote on its own.
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


def agenda(base: dict[str, Any], candidates: list[dict[str, Any]], room: dict[str, Any]) -> list[dict[str, Any]]:
    """The stage's items in order: call to order, open forum, the open-session items (the plan's included candidates in
    their order, else the meeting's open items), executive session when there are executive matters, adjournment."""
    def row(id_: str, kind: str, title: str, **more: Any) -> dict[str, Any]:
        return {"id": id_, "kind": kind, "label": KIND_LABELS.get(kind, kind.capitalize()), "title": title, "facts": [], "motion": "",
                "threshold": "majority", "recused": [], "allot": 0, "packet": [], "brief": None, "session": "open session", **more}

    items = [row("call", "call", "Call to order and roll call", allot=3),
             row("forum", "forum", "Open forum", allot=int(room.get("openForum", {}).get("limitMinutes", 3) or 3) * 5)]
    executive: list[str] = []
    if candidates:
        picked = [c for c in candidates if c.get("include", True)]
        picked.sort(key=lambda c: (int(_first(c, "order", default=10**6) or 10**6), str(_first(c, "title"))))
        for n, c in enumerate(picked, 1):
            session = str(_first(c, "session", "agendaSession", default="open")).lower()
            title = str(_first(c, "title", default=f"Item {n}"))
            if "exec" in session:
                executive.append(str(_first(c, "general", default=title)))
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
                executive.append(title)
                continue
            items.append(row(str(it.get("id", f"item-{n}")), "action", title, label=f"Item {len(items) - 1} · Action",
                             facts=[s for s in (str(it.get("ask", "")), str(it.get("authority", ""))) if s], allot=int(it.get("allot", 0) or 0)))
    if executive:
        items.append(row("exec", "exec", "Adjourn to executive session", allot=2, matters=executive,
                         motion=f"Move to adjourn to executive session to discuss {' and '.join(executive)} (CIV 4935)."))
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


def meeting_room(args: Args) -> dict[str, Any]:
    """The meeting (``meeting`` loader), the plan's items, the room record with tallies, the quorum, the roster, and the caveats."""
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
    items = agenda(base, candidates, room)
    notes = list(base.get("notes") or []) + ([plan_note] if plan_note else [])
    roster = _roster(root)
    if roster.get("note"):
        notes.append(roster["note"])
    return {
        "found": True, "date": day, "today": base.get("today", ""), "directors": directors, "quorum": store.quorum(directors),
        "items": items, "room": store.with_tallies(room), "decisions": base.get("decisions", []), "plan": {"found": bool(candidates), "count": len(candidates)},
        "roster": roster, "offAgendaPaths": [{"path": k, "text": v} for k, v in store.OFF_AGENDA_PATHS.items()],
        "zoom": _zoom(root, day),
        "commands": {**(base.get("commands") or {}), "minutesDraft": f"jason board --minutes {day}"},
        "minutesKey": f"minutes/{day}", "notes": notes, "caveats": list(CAVEATS),
    }


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Apply one action (``body.action``) to the room for the meeting ``key`` (an ISO date) as ``body.by``. The directors come
    from the board roster on disk unless the body carries them. Returns the room with tallies."""
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
    room = store.update(root, key, {k: v for k, v in body.items() if k not in ("by", "directors")}, by=str(body.get("by", "") or ""),
                        directors=[str(d) for d in directors or []])
    return store.with_tallies(room)
