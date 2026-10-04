"""The console dock: deadlines from the calendar, the action register, scratchpad notes, Ask, and translation drafts.

``dock`` reads disk only: the association calendar (``association_calendar``), the dock store, and, for Ask's common
questions, the meeting page, the decisions store, the records inventory, and the library. Each common answer names
the tool it read (``sources``); an answer with no source is no answer. ``write`` records a person's acts in the dock
store: a task added, changed, or done; a note; a question asked; a translation draft and its review state. Nothing
here sends, posts, or decides. A free question with no library hit becomes a task owned by the office that owns the
duty the person said it is about (``route``, from ``Community.assignments``), else unassigned and waiting for a person
to take it; jason never guesses and picks no one. The counts are the signed-in person's (``counts``): what they or
their offices may act on, or everyone's, said so, when nobody is signed in. There is no translator in this build: a
translation draft is a person's text marked ``needs review``.
"""

from __future__ import annotations

import re
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
    "A question with no sourced answer goes to the action register: to the office that owns the duty it is about, when "
    "the asker names one, else unassigned until a person takes it. jason never guesses and picks no one.",
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


# -- whose: the duties' owners (the profile's assignments) and the signed-in person (the roster) ----------------------


def _viewer() -> Any:
    """The request's viewer (``jason.web.access.current_viewer``), or None: nobody signed in, or no request."""
    try:
        from jason.web.access import current_viewer

        return current_viewer()
    except Exception:  # noqa: BLE001 - a sign-in that cannot be read is nobody signed in; the counts say everyone's
        return None


def _assignments() -> tuple[Any, ...]:
    """Who owns each duty (``Community.assignments``); empty when the profile keeps none or cannot be read."""
    try:
        from jason.community import community

        return tuple(community().assignments())
    except Exception:  # noqa: BLE001 - a profile that cannot be read owns nothing: every duty is a miss, unassigned
        return ()


def _duty_owners() -> tuple[Any, ...]:
    """The assignments that own a duty: less the ones the board declined or found not applicable."""
    from jason.community.schedule import Adoption

    return tuple(a for a in _assignments() if a.adoption not in (Adoption.DECLINED, Adoption.NOT_APPLICABLE))


def _officers() -> tuple[Any, ...]:
    """The roster's officers and portfolio managers (``jason.access.community_officers``); empty when unread."""
    try:
        from jason.access import community_officers

        return tuple(community_officers())
    except Exception:  # noqa: BLE001
        return ()


_NOT_OFFICES = ("jason", "owners")


def role_words(role: str) -> str:
    """An assignment's role as an owner reads: "the treasurer", "the board"; jason and owners as themselves."""
    return role if role in _NOT_OFFICES else f"the {role}"


def _word(text: Any) -> str:
    said = " ".join(str(text or "").lower().split())
    return said[4:] if said.startswith("the ") else said


def _board_offices() -> frozenset[str]:
    from jason.community.base import OfficerRole

    return frozenset(r.value for r in OfficerRole if r is not OfficerRole.MANAGER)


def holds(owner: Any, name: str, offices: frozenset[str]) -> bool:
    """Whether an owner ("the treasurer", "the board", a person's name) is this person or one of their offices. The
    board is every director's; a name is the person's own."""
    word = _word(owner)
    if not word:
        return False
    if name and word == _word(name):
        return True
    if word in offices:
        return True
    return word == "board" and bool(offices & _board_offices())


def _owners(title: str, rows: tuple[Any, ...]) -> list[dict[str, str]]:
    """The offices the assignments name as the owner of a calendar obligation (``obligation:<name>``), one a role."""
    from jason.community.schedule import covering

    out: dict[str, dict[str, str]] = {}
    for a in covering(f"obligation:{title}", rows):
        out.setdefault(a.role.value, {"role": a.role.value, "owner": role_words(a.role.value), "assignment": a.key, "adoption": a.adoption.value})
    return list(out.values())


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
    duties = _duty_owners()
    for i, ob in enumerate(cal.get("obligations", [])):
        nxt = ob.get("next")
        if not nxt or ob.get("standing") == "done":
            continue
        n = _days(nxt, day)
        if n is None:
            continue
        owners = _owners(ob.get("name", ""), duties)    # no assignment covers it: unassigned, a miss, never a guess
        rows.append({"id": f"d{i + 1}", "title": ob.get("name", ""), "date": str(nxt)[:10], "days": n, "authority": ob.get("authority", ""),
                     "standing": ob.get("standing", ""), "note": ob.get("note", ""), "screen": screen_for(f"{ob.get('name', '')} {ob.get('authority', '')}"),
                     "owners": owners, "owner": ", ".join(o["owner"] for o in owners)})
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


def _letters_waiting(name: str, offices: frozenset[str]) -> int | None:
    """Letters requested of an approver this person's offices may act for (``Officer.can_approve``); with no ``name``
    and no ``offices``, every requested letter. None when the letters store cannot be read."""
    from jason.tasks import approvals as letters

    try:
        rows = [l for l in letters.load(_root()).values() if l.get("stage") == "requested"]
    except Exception:  # noqa: BLE001 - the dock stands without the approvals store
        return None
    if not name and not offices:
        return len(rows)
    from jason.community.base import Officer, OfficerRole

    mine = [o for o in _officers() if (o.name == name if name else o.role.value in offices)]
    if not mine and not name:                         # viewing as an office nobody holds: the office's own rule
        mine = [Officer(OfficerRole(o), "") for o in sorted(offices)]
    return sum(1 for l in rows if any(o.can_approve(str(l.get("approver") or "")) for o in mine))


def counts(today: date) -> dict[str, Any]:
    """The dock's red counts: the overdue deadlines and overdue open tasks, and the letters waiting on an approval.
    Signed in, they are what this person may act on: tasks owned by them or their offices, deadlines whose duty's
    owner is one of their offices (``Community.assignments``), letters whose approver their office may act for. An
    admin viewing as an office or a person gets that one's. With nobody signed in, or an admin who holds no office,
    they are everyone's, and ``scope`` says so."""
    d = deadlines(today)
    t = _tasks(today)
    over = d["groups"][0]["rows"]
    late = [x for x in t["tasks"] if not x.get("done") and x.get("due") and (_days(x["due"], today) or 0) < 0]
    viewer = _viewer()
    everyone = viewer is None or (not viewer.offices and (viewer.admin or not viewer.name))
    if everyone:
        why = ("nobody is signed in" if viewer is None else "an admin who holds no office sees what waits on anyone")
        return {"found": True, "scope": "everyone", "who": "", "deadlines": len(over), "tasks": len(late),
                "approvals": _letters_waiting("", frozenset()), "note": f"Everyone's: {why}."}
    name, offices = viewer.name, frozenset(viewer.offices)
    mine_over = [r for r in over if any(holds(o["owner"], name, offices) for o in r.get("owners", []))]
    mine_late = [x for x in late if holds(x.get("owner"), name, offices)]
    who = viewer.label
    return {"found": True, "scope": "mine", "who": who, "deadlines": len(mine_over), "tasks": len(mine_late),
            "approvals": _letters_waiting(name, offices),
            "note": f"{who}'s: deadlines whose duty an office of theirs owns, tasks owned by them or their offices, and letters waiting on their approval."
                    + (" Viewing as them (admin view)." if viewer.acting else "")}


_TOOL_CALL = re.compile(r"^[a-z_]+\(.*\)$", re.S)


def source_ref(text: str, root: Any = None) -> dict[str, Any]:
    """One source an answer or a note names, as the console's ``Doc`` takes it (docs/console/doc-component.md): a tool
    call jason read (``meeting()``) is ``{command}``; a citation, a library document, a Drive file, or a file under data/
    is a ``DocRef`` (``jason.approvals.docref``); a bare library path is looked up as one exactly; anything else stays
    ``{text}``, never a guess."""
    from jason.approvals.docref import ref_from_string
    from jason.approvals.evidence import mask_text

    said = " ".join(str(text or "").split())
    if _TOOL_CALL.match(said):
        return {"command": mask_text(said)[0]}
    try:
        got = ref_from_string(said, data_dir=root)
        if "text" in got and "/" in said and not said.lower().startswith(("data/", "library", "drive")):
            lib = ref_from_string(f"library: {said}", data_dir=root)
            if "address" in lib:
                return lib
        return got
    except (OSError, ValueError):
        return {"text": mask_text(said)[0]}


def source_refs(sources: Any, root: Any = None, known: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """``source_ref`` for each source, in order, one for one; ``known`` gives the reference already built for a source
    (a library hit by its id)."""
    known = known or {}
    return [known.get(str(s)) or source_ref(str(s), root) for s in sources or ()]


def _library_refs(rows: list[dict[str, Any]], root: Any) -> dict[str, dict[str, Any]]:
    """Each library hit's reference by its path, from the hit's id."""
    from jason.approvals.docref import library_ref

    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        try:
            out[str(r["path"])] = library_ref(str(r["id"]), data_dir=root)
        except (KeyError, OSError, ValueError):
            continue
    return out


def _notes() -> dict[str, Any]:
    from jason.tasks import dock as store

    root = _root()
    rows = store.load(root)["notes"]
    notes = [{**n, "sourceRefs": source_refs(n.get("sources"), root)} for n in rows]
    return {"found": True, "count": len(rows), "notes": sorted(notes, key=lambda n: n.get("updated", ""), reverse=True),
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

    rows = store.open_only(store.load(_root()))     # an executive-session decision is the private view's (CIV 4935(e))
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
    refs: dict[str, dict[str, Any]] = {}
    try:
        hits = library_search(kind="minutes", limit=3)
        if hits.get("found"):
            parts.append("Newest in the library: " + "; ".join(f"{r['path']} ({r.get('period') or '?'})" for r in hits["rows"]) + ".")
            sources.append("library_search(kind=minutes)")
            refs = _library_refs(hits["rows"], _root())
            sources += [p for p in refs if p not in sources]
    except Exception:
        pass
    return {"answer": " ".join(parts), "sources": sources if parts else [], "refs": refs}


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
        sources = got.get("sources", []) if sourced else []
        out.append({"question": question, "screen": screen, "answer": got["answer"] if sourced else "", "sources": sources,
                    "sourceRefs": source_refs(sources, _root(), got.get("refs")) if sources else [],
                    "routed": not sourced, "note": got.get("note", "")})
    return out


def _ask(today: date) -> dict[str, Any]:
    from jason.tasks import dock as store

    root = _root()
    data = store.load(root)
    asks = sorted(data["asks"], key=lambda a: a.get("at", ""), reverse=True)[:20]
    return {"found": True, "common": common_questions(today), "asks": [{**a, "sourceRefs": source_refs(a.get("sources"), root)} for a in asks],
            "translations": sorted(data["translations"], key=lambda t: t.get("at", ""), reverse=True), "translationStates": list(store.TRANSLATION_STATES),
            "translateCommand": "", "routedAnswer": store.ROUTED_ANSWER, "unassigned": store.UNASSIGNED, "duties": ask_duties(),
            "caveats": list(ASK_CAVEATS) + [store.TRANSLATION_CAVEAT]}


# Owners a routed question may go to: the roster's offices and the board. jason, owners, counsel, a committee, or the
# inspector of elections own duties, but a question on the register waits for an office.
def _routable() -> frozenset[str]:
    from jason.community.base import OfficerRole

    return frozenset({r.value for r in OfficerRole} | {"board"})


def ask_duties() -> list[dict[str, str]]:
    """The duties a person may say a question is about (``Community.assignments``), each with the office that owns it
    and whether the board adopted the assignment. Empty until the profile keeps assignments."""
    return sorted(({"key": a.key, "title": a.title, "owner": role_words(a.role.value), "adoption": a.adoption.value} for a in _duty_owners()),
                  key=lambda r: (r["title"].lower(), r["key"]))


def route(duty: str) -> dict[str, str]:
    """Where a question with no sourced answer goes: the office an assignment names as the owner of the duty the asker
    said it is about (``duty``: an assignment's key, or a reference one covers, "obligation:<name>", "CIV 5500"). No
    duty named, no assignment covering it, more than one office, or an owner who is not an office: unassigned, waiting
    for a person to take it. The owner comes from the profile, never from the question's words; jason picks no one."""
    from jason.community.schedule import Adoption, covering
    from jason.tasks import dock as store

    duty = " ".join(str(duty or "").split())
    if not duty:
        return {"owner": "", "duty": "", "routing": f"{store.UNASSIGNED} (no duty named)"}
    rows = _duty_owners()
    hit = [a for a in rows if a.key == duty] or covering(duty, rows)
    roles = sorted({a.role.value for a in hit})
    if not roles:
        return {"owner": "", "duty": duty, "routing": f"{store.UNASSIGNED} (no assignment covers {duty})"}
    if len(roles) > 1:
        return {"owner": "", "duty": duty, "routing": f"{store.UNASSIGNED} ({duty} is owned by {', '.join(role_words(r) for r in roles)}; a person decides)"}
    a = hit[0]
    owner = role_words(a.role.value)
    if a.role.value not in _routable():
        return {"owner": "", "duty": a.key, "routing": f"{store.UNASSIGNED} ({a.title} is {owner}'s, not an office's)"}
    adopted = "adopted" if a.adoption is Adoption.ADOPTED else "proposed, not yet adopted"
    return {"owner": owner, "duty": a.key, "routing": f"routed to {owner}, who owns {a.title} (assignment {a.key}, {adopted})"}


def dock(args: Args) -> dict[str, Any]:
    """``part`` is one of ``counts, deadlines, tasks, notes, ask, all`` (default all). ``counts`` is the overdue
    deadlines, the overdue open tasks, and the letters waiting on an approval, the signed-in person's (``counts``),
    for the dock's red badges."""
    part = args.get("part", "all").strip() or "all"
    if part not in PARTS:
        return {"found": False, "note": f"part is one of {', '.join(PARTS)}"}
    today = _today()
    if part == "counts":
        return counts(today)
    if part == "deadlines":
        return deadlines(today)
    if part == "tasks":
        return _tasks(today)
    if part == "notes":
        return _notes()
    if part == "ask":
        return _ask(today)
    c = counts(today)
    return {"found": True, "counts": {k: c[k] for k in ("scope", "who", "deadlines", "tasks", "approvals", "note")}, "deadlines": deadlines(today),
            "tasks": _tasks(today), "notes": _notes(), "ask": _ask(today)}


# -- writes ----------------------------------------------------------------------------------------------------------

ACTIONS = ("task_add", "task_update", "task_done", "note_add", "note_update", "ask", "translate", "translation_state")


def _norm_words(text: str) -> set[str]:
    import re

    return {w for w in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split() if len(w) > 3}


def _answer_free(question: str, by: str, screen: str, duty: str = "") -> dict[str, Any]:
    """A free question: a common question when it is one, else the library; no hit means routed (``route``)."""
    from jason.mcp.county import library_search
    from jason.tasks import dock as store

    root = _root()
    words = _norm_words(question)
    for c in common_questions():
        if c["sources"] and len(words & _norm_words(c["question"])) >= max(2, len(_norm_words(c["question"])) - 1):
            row = store.record_ask(root, question, by=by, answer=c["answer"], sources=c["sources"], screen=c["screen"])
            return {**row, "sourceRefs": list(c.get("sourceRefs") or [])}
    try:
        hits = library_search(words=question, limit=5)
    except Exception:
        hits = {"found": False}
    if hits.get("found") and hits.get("rows"):
        rows = hits["rows"]
        answer = f"The phrase appears in {hits.get('count', len(rows))} library file(s): " + "; ".join(
            f"{r['path']} ({r.get('kind') or 'unclassified'}" + (f", {r['period']}" if r.get("period") else "") + ")" for r in rows) + ". Read the file; this is where the words were found, not a finding."
        sources = [f"library_search(words={question!r})"] + [r["path"] for r in rows]
        row = store.record_ask(root, question, by=by, answer=answer, sources=sources, screen="records")
        return {**row, "sourceRefs": source_refs(row.get("sources"), root, _library_refs(rows, root))}
    to = route(duty)
    return {**store.record_ask(root, question, by=by, answer="", sources=[], screen=screen, owner=to["owner"], routing=to["routing"]), "sourceRefs": []}


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
        note = store.add_note(root, str(body.get("title", "")), by=by, body=str(body.get("body", "") or ""), status=str(body.get("status", "researching") or "researching"),
                              sources=body.get("sources") if isinstance(body.get("sources"), list) else None)
        return {**note, "sourceRefs": source_refs(note.get("sources"), root)}
    if action == "note_update":
        changes = {k: v for k, v in body.items() if k in store.NOTE_EDITABLE}
        note = store.update_note(root, key, by=by, **changes)
        return {**note, "sourceRefs": source_refs(note.get("sources"), root)}
    if action == "ask":
        return _answer_free(str(body.get("question", "")), by, str(body.get("screen", "") or ""), str(body.get("duty", "") or ""))
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


__all__ = ["ACTIONS", "ASK_CAVEATS", "PARTS", "SCREEN_RULES", "ask_duties", "common_questions", "counts", "deadlines", "dock",
           "holds", "role_words", "route", "screen_for", "source_ref", "source_refs", "write"]
