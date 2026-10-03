"""The console dock: deadlines from the calendar, the action register, scratchpad notes, Ask, and translation drafts.

``dock`` reads disk only: the association calendar (``association_calendar``), the dock store, and, for Ask's common
questions, the meeting page, the decisions store, the records inventory, and the library. Each common answer names
the tool it read (``sources``); an answer with no source is no answer. ``write`` records a person's acts in the dock
store: a task added, changed, or done; a note; a question asked; a translation draft and its review state. Nothing
here sends, posts, or decides. A free question with no library hit is routed to the manager as a task; jason never
guesses. There is no translator in this build: a translation draft is a person's text marked ``needs review``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

Args = dict[str, str]

PARTS = ("counts", "deadlines", "tasks", "notes", "ask", "all")
SOON_DAYS = 14
CLOCK_DAYS = 45

# Words in a deadline's name or authority, to the screen that works it. First match wins; otherwise the calendar.
SCREEN_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("liens", ("lien", "collection", "delinquen", "5685", "5705", "5855")),
    ("disclosures", ("election", "notice", "disclosure", "policy statement", "5310", "4040", "5305")),
    ("insurance", ("insurance", "policy", "premium", "fidelity", "bond", "flood", "umbrella", "d&o")),
    ("reserves", ("reserve", "budget", "5300", "5550", "5515", "5500")),
    ("meetings", ("minutes", "meeting", "4950", "4920")),
    ("records", ("record", "5210", "5200", "inspection")),
)

ASK_CAVEATS = (
    "Answers come from the association's records and jason's stores, and cite where each was read. They are not legal advice.",
    "A question with no sourced answer goes to the action register for the manager. jason never guesses.",
)


def _today() -> date:
    return date.today()


def _days(iso: str, today: date) -> int | None:
    try:
        return (date.fromisoformat(str(iso)[:10]) - today).days
    except (TypeError, ValueError):
        return None


def screen_for(text: str) -> str:
    """The console screen a deadline belongs to, by the words it carries; the calendar when none match."""
    hay = str(text or "").lower()
    for screen, words in SCREEN_RULES:
        if any(w in hay for w in words):
            return screen
    return "calendar"


def _root():
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _calendar() -> dict[str, Any]:
    from jason.mcp.county import association_calendar

    return association_calendar()


def deadlines(today: date | None = None) -> dict[str, Any]:
    """The calendar's dated obligations as rows grouped Overdue / Next 14 days / Later, each with a screen hint, and the
    rows within 45 days either way for the clock."""
    day = today or _today()
    try:
        cal = _calendar()
    except Exception as exc:  # the calendar needs the profile and PayHOA's payments; the dock stands without it
        return {"found": False, "note": f"calendar not read: {type(exc).__name__}: {exc}", "asOf": day.isoformat(),
                "groups": [{"key": k, "label": l, "rows": []} for k, l in _GROUPS], "clock": [], "counts": {"overdue": 0, "soon": 0, "later": 0}}
    rows: list[dict[str, Any]] = []
    for i, ob in enumerate(cal.get("obligations", [])):
        nxt = ob.get("next")
        if not nxt or ob.get("standing") == "done":
            continue
        n = _days(nxt, day)
        if n is None:
            continue
        rows.append({"id": f"d{i + 1}", "title": ob.get("name", ""), "date": str(nxt)[:10], "days": n, "authority": ob.get("authority", ""),
                     "standing": ob.get("standing", ""), "note": ob.get("note", ""), "screen": screen_for(f"{ob.get('name', '')} {ob.get('authority', '')}")})
    rows.sort(key=lambda r: (r["date"], r["title"]))
    over = [r for r in rows if r["days"] < 0]
    soon = [r for r in rows if 0 <= r["days"] <= SOON_DAYS]
    later = [r for r in rows if r["days"] > SOON_DAYS]
    return {"found": True, "asOf": cal.get("asOf", day.isoformat()), "today": day.isoformat(),
            "groups": [{"key": "overdue", "label": "Overdue", "rows": over}, {"key": "soon", "label": f"Next {SOON_DAYS} days", "rows": soon},
                       {"key": "later", "label": "Later", "rows": later}],
            "clock": [{"key": r["id"], "label": r["title"], "date": r["date"], "authority": r["authority"]} for r in rows if -CLOCK_DAYS <= r["days"] <= CLOCK_DAYS],
            "counts": {"overdue": len(over), "soon": len(soon), "later": len(later)}, "caveats": list(cal.get("caveats", []))}


_GROUPS = (("overdue", "Overdue"), ("soon", f"Next {SOON_DAYS} days"), ("later", "Later"))


def _tasks(today: date) -> dict[str, Any]:
    from jason.tasks import dock as store

    rows = store.load(_root())["tasks"]
    overdue = sum(1 for t in rows if not t.get("done") and t.get("due") and (_days(t["due"], today) or 0) < 0)
    return {"found": True, "today": today.isoformat(), "count": len(rows), "overdue": overdue, "open": sum(1 for t in rows if not t.get("done")),
            "tasks": sorted(rows, key=lambda t: (t.get("done", False), t.get("due") or "9999", t.get("created", ""))),
            "editable": list(store.TASK_EDITABLE), "caveats": ["The register is what people said needs doing; jason assigns nothing and marks nothing done."]}


def _notes() -> dict[str, Any]:
    from jason.tasks import dock as store

    rows = store.load(_root())["notes"]
    return {"found": True, "count": len(rows), "notes": sorted(rows, key=lambda n: n.get("updated", ""), reverse=True),
            "statuses": list(store.NOTE_STATUSES), "caveat": store.NOTE_CAVEAT}


# -- Ask: the common questions, each answered from a store and cited -------------------------------------------------


def _q_next_meeting() -> dict[str, Any]:
    from jason.web.sources import meeting

    m = meeting({})
    if not m.get("found"):
        return {"answer": "", "sources": []}
    return {"answer": f"The next board meeting is {m['date']}. The agenda notice is due by {m['noticeBy']} (CIV 4920); an executive-only meeting's by {m['executiveNoticeBy']}. "
                      f"{m.get('openCount', 0)} open-session and {m.get('executiveCount', 0)} executive items are proposed or on the agenda.",
            "sources": ["meeting()", "CIV 4920"]}


def _q_due_this_month(today: date) -> dict[str, Any]:
    d = deadlines(today)
    if not d.get("found"):
        return {"answer": "", "sources": []}
    month = today.isoformat()[:7]
    rows = [r for g in d["groups"] for r in g["rows"] if r["date"].startswith(month)]
    if not rows:
        return {"answer": f"The calendar shows nothing due in {month}.", "sources": ["association_calendar()"]}
    lines = "; ".join(f"{r['title']} by {r['date']}" + (f" ({r['authority']})" if r["authority"] else "") for r in rows)
    return {"answer": f"Due in {month}: {lines}.", "sources": ["association_calendar()"] + sorted({r["authority"] for r in rows if r["authority"]})}


def _q_overdue(today: date) -> dict[str, Any]:
    d = deadlines(today)
    if not d.get("found"):
        return {"answer": "", "sources": []}
    rows = d["groups"][0]["rows"]
    if not rows:
        return {"answer": "The calendar shows nothing overdue.", "sources": ["association_calendar()"]}
    return {"answer": "Overdue: " + "; ".join(f"{r['title']} ({r['date']}, {-r['days']}d)" for r in rows) + ".", "sources": ["association_calendar()"]}


def _q_last_decisions() -> dict[str, Any]:
    from jason.tasks import decisions as store

    rows = store.load(_root())
    if not rows:
        return {"answer": "", "sources": []}
    last = max(d.meeting for d in rows)
    picked = [d for d in rows if d.meeting == last]
    said = "; ".join(f"{d.title}: {d.outcome or 'vote open'}" for d in picked)
    return {"answer": f"At the {last} meeting the board recorded {len(picked)} decision(s): {said}. The outcome is the board's word as recorded.",
            "sources": [f"decisions(meeting={last})"] + [f"decision {d.id}" for d in picked]}


def _q_minutes() -> dict[str, Any]:
    from jason.mcp.county import library_search, records_inventory

    sources: list[str] = []
    parts: list[str] = []
    try:
        for rec in records_inventory().get("records", []):
            if rec.get("record") == "minutes":
                where = ", ".join(str(f) for f in (rec.get("folders") or [])) or "nowhere pinned"
                parts.append(f"The minutes are kept at {where} ({rec.get('files', 0)} files; newest {rec.get('newest') or 'none'}).")
                if rec.get("gap"):
                    parts.append(f"Gap: {rec['gap']}.")
                sources += ["records_inventory()", str(rec.get("citation") or "CIV 5200(a)(8)")]
    except Exception:
        pass
    try:
        hits = library_search(kind="minutes", limit=3)
        if hits.get("found"):
            parts.append("Newest in the library: " + "; ".join(f"{r['path']} ({r.get('period') or '?'})" for r in hits["rows"]) + ".")
            sources.append("library_search(kind=minutes)")
    except Exception:
        pass
    return {"answer": " ".join(parts), "sources": sources if parts else []}


def common_questions(today: date | None = None) -> list[dict[str, Any]]:
    """The questions jason answers from its stores, each with the answer it found now and the tools it read."""
    day = today or _today()
    plan = (
        ("When is the next board meeting?", "meetings", _q_next_meeting),
        ("What is due this month?", "calendar", lambda: _q_due_this_month(day)),
        ("What is overdue?", "calendar", lambda: _q_overdue(day)),
        ("What did the board decide last meeting?", "decisions", _q_last_decisions),
        ("Where are the minutes?", "records", _q_minutes),
    )
    out = []
    for question, screen, fn in plan:
        try:
            got = fn()
        except Exception as exc:  # a store not on disk is no answer, never a guess
            got = {"answer": "", "sources": [], "note": f"{type(exc).__name__}: {exc}"}
        sourced = bool(got.get("sources")) and bool(got.get("answer"))
        out.append({"question": question, "screen": screen, "answer": got["answer"] if sourced else "", "sources": got.get("sources", []) if sourced else [],
                    "routed": not sourced, "note": got.get("note", "")})
    return out


def _ask(today: date) -> dict[str, Any]:
    from jason.tasks import dock as store

    data = store.load(_root())
    return {"found": True, "common": common_questions(today), "asks": sorted(data["asks"], key=lambda a: a.get("at", ""), reverse=True)[:20],
            "translations": sorted(data["translations"], key=lambda t: t.get("at", ""), reverse=True), "translationStates": list(store.TRANSLATION_STATES),
            "translateCommand": "", "routedAnswer": store.ROUTED_ANSWER, "caveats": list(ASK_CAVEATS) + [store.TRANSLATION_CAVEAT]}


def dock(args: Args) -> dict[str, Any]:
    """``part`` is one of ``counts, deadlines, tasks, notes, ask, all`` (default all). ``counts`` is the overdue
    deadlines and the overdue open tasks, for the dock's red badges."""
    part = args.get("part", "all").strip() or "all"
    if part not in PARTS:
        return {"found": False, "note": f"part is one of {', '.join(PARTS)}"}
    today = _today()
    if part == "counts":
        d = deadlines(today)
        return {"found": True, "deadlines": d["counts"]["overdue"], "tasks": _tasks(today)["overdue"]}
    if part == "deadlines":
        return deadlines(today)
    if part == "tasks":
        return _tasks(today)
    if part == "notes":
        return _notes()
    if part == "ask":
        return _ask(today)
    d = deadlines(today)
    t = _tasks(today)
    return {"found": True, "counts": {"deadlines": d["counts"]["overdue"], "tasks": t["overdue"]}, "deadlines": d, "tasks": t, "notes": _notes(), "ask": _ask(today)}


# -- writes ----------------------------------------------------------------------------------------------------------

ACTIONS = ("task_add", "task_update", "task_done", "note_add", "note_update", "ask", "translate", "translation_state")


def _norm_words(text: str) -> set[str]:
    import re

    return {w for w in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split() if len(w) > 3}


def _answer_free(question: str, by: str, screen: str) -> dict[str, Any]:
    """A free question: a common question when it is one, else the library; no hit means routed."""
    from jason.mcp.county import library_search
    from jason.tasks import dock as store

    words = _norm_words(question)
    for c in common_questions():
        if c["sources"] and len(words & _norm_words(c["question"])) >= max(2, len(_norm_words(c["question"])) - 1):
            return store.record_ask(_root(), question, by=by, answer=c["answer"], sources=c["sources"], screen=c["screen"])
    try:
        hits = library_search(words=question, limit=5)
    except Exception:
        hits = {"found": False}
    if hits.get("found") and hits.get("rows"):
        rows = hits["rows"]
        answer = f"The phrase appears in {hits.get('count', len(rows))} library file(s): " + "; ".join(
            f"{r['path']} ({r.get('kind') or 'unclassified'}" + (f", {r['period']}" if r.get("period") else "") + ")" for r in rows) + ". Read the file; this is where the words were found, not a finding."
        return store.record_ask(_root(), question, by=by, answer=answer, sources=[f"library_search(words={question!r})"] + [r["path"] for r in rows], screen="records")
    return store.record_ask(_root(), question, by=by, answer="", sources=[], screen=screen)


def _send_for_review(row: dict[str, Any], by: str) -> str:
    """The approvals draft for a fluent reviewer; a missing approvals store is tolerated and said."""
    try:
        from jason.web.extra import approvals

        key = f"translations/{row['id']}"
        letter = {"key": key, "kind": "Translation", "title": f"{row.get('englishKey') or 'Notice'} ({row['language']})", "date": datetime.now().date().isoformat(),
                  "to": f"Members who asked for {row['language']}", "via": "With the English notice, which controls", "body": [row["english"], row["draft"]],
                  "signoff": "", "approver": "a fluent reviewer"}
        approvals.write("", {"action": "draft", "by": by, "letter": letter, "note": "translation draft for a fluent reviewer"})
        try:
            approvals.write(key, {"action": "save", "by": by})
            approvals.write(key, {"action": "request", "by": by, "note": "a fluent reviewer checks the draft; the English notice controls"})
        except Exception:
            pass
        return f"approvals {key}"
    except Exception as exc:
        return f"approvals draft not made: {type(exc).__name__}"


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``body.action`` is one of ``ACTIONS``; ``key`` is the row id for the updates. Every action carries ``by``."""
    from jason.tasks import dock as store

    root = _root()
    action = str(body.get("action", "")).strip()
    by = str(body.get("by", "") or "")
    key = (key or "").strip()
    if key in ("-", "new"):   # the route needs a key; a create has none
        key = ""
    if action not in ACTIONS:
        raise ValueError(f"action is one of {', '.join(ACTIONS)}")
    if action == "task_add":
        return store.add_task(root, str(body.get("text", "")), by=by, owner=str(body.get("owner", "") or ""), due=str(body.get("due", "") or ""),
                              source=str(body.get("source", "manual") or "manual"), screen=str(body.get("screen", "") or ""))
    if action == "task_update":
        changes = {k: v for k, v in body.items() if k in store.TASK_EDITABLE}
        return store.update_task(root, key, by=by, **changes)
    if action == "task_done":
        return store.complete_task(root, key, by=by, done=bool(body.get("done", True)))
    if action == "note_add":
        return store.add_note(root, str(body.get("title", "")), by=by, body=str(body.get("body", "") or ""), status=str(body.get("status", "researching") or "researching"),
                              sources=body.get("sources") if isinstance(body.get("sources"), list) else None)
    if action == "note_update":
        changes = {k: v for k, v in body.items() if k in store.NOTE_EDITABLE}
        return store.update_note(root, key, by=by, **changes)
    if action == "ask":
        return _answer_free(str(body.get("question", "")), by, str(body.get("screen", "") or ""))
    if action == "translate":
        return store.add_translation(root, english_key=str(body.get("englishKey", "") or ""), english=str(body.get("english", "") or ""),
                                     language=str(body.get("language", "") or ""), draft=str(body.get("draft", "") or ""), by=by)
    state = str(body.get("state", "") or "")
    note = str(body.get("note", "") or "")
    if state == "sent for review":
        row = next((t for t in store.load(root)["translations"] if str(t.get("id")) == key), None)
        if row is None:
            raise KeyError(key)
        note = (note + "; " if note else "") + _send_for_review(row, by)
    return store.translation_state(root, key, state, by=by, note=note)


__all__ = ["ACTIONS", "ASK_CAVEATS", "PARTS", "SCREEN_RULES", "common_questions", "deadlines", "dock", "screen_for", "write"]
