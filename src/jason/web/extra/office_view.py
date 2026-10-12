"""The office views' loader (``GET /api/office-view?office=ROLE``, docs/console/screens/office-views.md): what waits on
one office, what is coming for it, and the workflow runs whose current step it holds, so any board member can read any
office's landing page.

**A lens, not impersonation.** Reading another office's page changes nothing about who the viewer is: the gate and the data
levels are the viewer's own, nothing is written, and the answer carries the office asked for (an ``OfficerRole`` word), the
viewer's own offices as words (``mine``), and no person's name and no session. ``office`` empty reads the viewer's own offices
as a union (a person who holds two offices sees both).

**Who may read it.** A signed-in person whose offices open P2 (``jason.web.access``: the manager and every board office):
401 signed out, 403 with ``access.may_see``'s sentence for a roster person with no office, a reviewer, counsel, or an
administrator who holds no office. Where console sign-in is not set up it answers as the loopback console always has
(``jason.web.gates``). The owner view never reads it (``OWNER_SOURCES`` does not list it). An ``office`` that is not an
``OfficerRole`` word is a 400.

**What is composed, from what exists** (each band stands or fails alone; the reason a band failed is in ``bandErrors``):

- ``waitingOnOffice``: the letters requested of an approver the office stands for (``Officer.approves``, ``the <office>``,
  and ``the board`` for the two offices that record its vote), by kind and count; the engine's plans waiting for a second
  signature that a holder of the office may give (``may_second``: not the first signer, not the one who asked, an office the
  controls allow); the board items the board gave the office
  (or the board) to act on; and, for the secretary, the board's open votes to record.
- ``signedWaiting``: the engine's plans signed and not yet applied (``jason.approvals.engine.waiting_to_apply``;
  docs/console/approval-clarity.md, section 4), by kind title and how long each has waited from the last signature, with
  whether it is older than its kind allows (it is planned again before apply) and whether only a person at a terminal
  applies it, whether the board's reminder is due (``reminderDue``; it only surfaces, nothing is sent) and whether a pause
  the board adopted still holds (``pausing``). The same rows for every office read: the board's rule of 2026-10-11 is that directors and officers (and the
  manager) have the same access, and any of them may apply. Counts, times, and the plan's title; never an item.
- ``personSteps``: the workflows' person steps that are on a legal clock, late, in need of a date, due soon, or open a while
  (``jason.workflows.nudge``; docs/workflows/person-steps.md, section 6), one row a step, most urgent first, with its band as a mark
  (``legal``, ``late``, ``date``, ``soon``, ``stale``) and the office that holds it. **The same rows for every office lens**: escalation
  is visibility, never a message, so a step late for one office is on every board member's page; the lens only puts the steps the
  office it reads holds first (``forOffice``). A held run is its general title (even in the private view), an administrator's own
  definition is listed for an administrator only, and a per-item step is one row with a count. The lead time and the open-a-while
  threshold are proposals (``numbers``), not the law's. Nothing is sent or snoozed; counts, offices, titles, and dates only.
- ``needsAttention`` and ``comingUp``: the schedule's occurrences (``jason.tasks.schedule.agenda``) for the duties the
  profile's assignments give the office, or the board, or name it as the backup: overdue and due soon, then the next weeks;
  and a count of the dock's open tasks the office owns.
- ``work``: the workflow runs that are the office's move, read the way the Work list reads them (``jason.web.extra.work``: one dry
  fold, one pressing step, one rule for whose move it is), so Today and Work show the same step and the same holder. The Work screens' rules hold
  here (``jason.web.extra.work_scope``): a run of an administrator's definition is listed for an administrator only, and a
  held run (a hearing, a delinquent account, a records request) outside the private view is its general title and state
  with no label or step; inside it the run is named in full and the reading is logged in ``access/served.jsonl``.

``notComposed`` says plainly what the page could not build and why. Rows hold offices, counts, kinds, and titles of items
(contact details masked); an owner's name or unit never. Disk only: nothing here calls PayHOA, Google, or a model.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

Args = dict[str, str]

LIMIT = 12                                  # rows a band shows; its total is in ``counts``
PAST_DAYS = 30                              # how far back the schedule looks for what is overdue
AHEAD_DAYS = 45                             # how far ahead "coming up" looks
BANDS = ("waitingOnOffice", "signedWaiting", "personSteps", "needsAttention", "comingUp", "work")
BOARD = "the board"

NOT_AN_OFFICE = ("{word!r} is not an office. The offices are {offices}.")
MINE_EMPTY = "You hold no office on this page; pick an office to read."
NO_OFFICERS = "The profile names no officers, so no office is listed and every office reads as vacant."
CAVEATS = (
    "Reading another office's page is a lens, not that person's session: you stay yourself, your data levels are your "
    "own, and anything you do is recorded under your own name.",
    "Read from the stores on disk. jason decides nothing: a clock is computed, an assignment is a proposal until the board "
    "adopts it, and an act on a row happens on the screen that owns it.",
    "A row shows an office's counts and the titles of its items; the owning screens decide what a name or a unit shows.",
)


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _today() -> date:
    return date.today()


def office_words() -> tuple[str, ...]:
    """The office words, in the order the lens lists them: the board's offices, the directors, the manager."""
    from jason.community.base import OfficerRole

    return tuple(r.value for r in OfficerRole)


def normalize(value: Any) -> str:
    """An ``office`` argument as an ``OfficerRole`` word: trimmed, lower case, ``-``/``_``/``+`` read as a space (so a
    hash can say ``vice-president``). ValueError for a word that is not an office; empty stays empty (my offices)."""
    word = " ".join(str(value or "").replace("-", " ").replace("_", " ").replace("+", " ").lower().split())
    if word and word not in office_words():
        raise ValueError(NOT_AN_OFFICE.format(word=str(value), offices=", ".join(office_words())))
    return word


def _gate() -> Any:
    """The request's viewer, or None (nobody signed in, sign-in not set up, or no request). 401 signed out and 403 where
    the viewer's offices do not open P2, by the loader gate (``jason.web.gates``)."""
    from jason.web import access, gates

    gates.check(gates.P2)
    return access.current_viewer()


# -- the profile's offices ---------------------------------------------------------------------------------------------


def _officers() -> tuple[Any, ...]:
    """The profile's officers and the portfolio manager (``jason.access.community_officers``); empty when unread."""
    try:
        from jason.access import community_officers

        return tuple(community_officers())
    except Exception:  # noqa: BLE001 - a profile that names no one makes every office vacant, said so
        return ()


def lens(officers: tuple[Any, ...]) -> list[dict[str, Any]]:
    """Every office the profile names, with whether anyone holds it: ``[{office, vacant, holders}]`` (a count, never a
    name). Empty when the profile names no officers (the page is Today as it is)."""
    if not officers:
        return []
    out = []
    for word in office_words():
        held = sum(1 for o in officers if o.role.value == word)
        out.append({"office": word, "vacant": held == 0, "holders": held})
    return out


def _mine(viewer: Any) -> list[str]:
    held = set(getattr(viewer, "offices", ()) or ())
    return [w for w in office_words() if w in held]


def _title(reading: list[str]) -> str:
    if not reading:
        return "my offices"
    words = [f"the {w}" for w in reading]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


# -- matching an owner to an office ------------------------------------------------------------------------------------


def _names_of(officers: tuple[Any, ...], office: str) -> list[str]:
    """The names holding ``office``, used only to match an owner a board item names; they never leave this module."""
    return [o.name for o in officers if o.role.value == office and o.name]


def _owned_by(owner: Any, office: str, officers: tuple[Any, ...]) -> str:
    """"" if ``owner`` (free text on a board item or a task) is not the office's; ``office`` when it names the office or
    one of its holders; ``BOARD`` when it names the board and the office is one of the board's."""
    from jason.web.extra.dock import holds

    names = _names_of(officers, office) or [""]
    if any(holds(owner, n, frozenset({office})) for n in names):
        word = " ".join(str(owner or "").lower().split())
        return BOARD if word.removeprefix("the ") == "board" else office
    return ""


def _letter_waits(office: str, approver: str, officers: tuple[Any, ...]) -> bool:
    """Whether a letter requested of ``approver`` waits on ``office``: the approver is "the <office>", or a holder of the
    office approves for it (``Officer.approves``), or it is the board and the office records the board's vote
    (``Officer.can_approve``)."""
    from jason.community.base import Officer, OfficerRole

    role = OfficerRole(office)
    if approver == f"the {office}":
        return True
    if approver == BOARD:
        return Officer(role, "").can_approve(BOARD)
    return any(o.role is role and approver in o.approves for o in officers)


# -- the bands ---------------------------------------------------------------------------------------------------------


def _band(name: str, build: Callable[[], list[dict[str, Any]]], errors: dict[str, str]) -> list[dict[str, Any]]:
    try:
        return build()
    except Exception as exc:  # noqa: BLE001 - one band failing says so with its reason; the others stand
        errors.setdefault(name, f"{type(exc).__name__}: {exc}")
        return []


def _letters(root: Path, reading: list[str], officers: tuple[Any, ...]) -> list[dict[str, Any]]:
    from jason.tasks import approvals as store

    out: dict[tuple[str, str, str], int] = {}
    for letter in store.load(root).values():
        if letter.get("stage") != "requested":
            continue
        approver = str(letter.get("approver") or BOARD)
        for office in reading:
            if _letter_waits(office, approver, officers):
                key = (office, str(letter.get("kind") or "Letter"), approver)
                out[key] = out.get(key, 0) + 1
    return [{"type": "letter", "office": office, "kind": kind, "approver": approver, "count": n, "screen": "approvals",
             "text": f"{n} {kind} waiting for {approver}"} for (office, kind, approver), n in sorted(out.items())]


def _board_items(root: Path, reading: list[str], officers: tuple[Any, ...]) -> list[dict[str, Any]]:
    from jason.approvals.evidence import mask_text
    from jason.mcp.county import board_items

    out = []
    for item in board_items(include_closed=False, include_confidential=False, data_dir=root).get("items") or []:
        for office in reading:
            via = _owned_by(item.get("owner"), office, officers)
            if via:
                out.append({"type": "board-item", "office": office, "id": str(item.get("id") or ""),
                            "title": mask_text(str(item.get("title") or ""))[0], "priority": str(item.get("priority") or ""),
                            "status": str(item.get("status") or ""), "due": str(item.get("due") or "") or None,
                            "shared": via == BOARD, "screen": "actions",
                            "text": f"Board item: {mask_text(str(item.get('title') or ''))[0]}"})
                break
    return out


def _decisions(root: Path, reading: list[str]) -> list[dict[str, Any]]:
    """The board's open votes: the secretary records the outcome (and the minutes)."""
    if "secretary" not in reading:
        return []
    from jason.approvals.evidence import mask_text
    from jason.tasks import decisions as store

    out = []
    for d in store.open_only(store.load(root)):
        if not d.outcome:
            title = mask_text(d.title)[0]
            out.append({"type": "decision", "office": "secretary", "id": d.id, "title": title, "meeting": d.meeting,
                        "screen": "decisions", "text": f"Decision to record: {title} ({d.meeting})"})
    return out


def may_second(root: Path, a: Any, office: str, officers: tuple[Any, ...]) -> bool:
    """Whether a holder of ``office`` may give the second signature a plan waits for: the engine's own rule
    (``jason.approvals.engine.confirm``), asked of each holder the profile names. The second person is not the one who signed first,
    not the one who asked for the plan, and holds an office the controls the board adopted allow (``signer_refusals``). An office with
    no named holder is unknown, not eligible."""
    from jason.approvals.engine import signer_refusals
    from jason.approvals.model import same_person

    for name in _names_of(officers, office):
        if same_person(name, a.first.name) or same_person(name, a.requested_by):
            continue
        if not signer_refusals(a, [a.first.name, name], final=True, data_dir=root):
            return True
    return False


def _plans_to_second(root: Path, reading: list[str], officers: tuple[Any, ...]) -> list[dict[str, Any]]:
    """The engine's plans that are submitted and wait for a second, distinct signature, for each office in ``reading`` with a holder who
    may give it (see ``may_second``). Kind and title only: the first signer's name is not shown, and the office is told only that it is
    not the person who signed first."""
    from jason.approvals import store
    from jason.approvals.engine import needs_second
    from jason.approvals.evidence import mask_text
    from jason.approvals.model import ApprovalStatus as S

    out = []
    for a in store.load_all(root):
        if a.status not in (S.APPROVED, S.PARTIALLY_APPROVED) or a.first is None or a.second is not None:
            continue
        try:
            if not needs_second(a, data_dir=root):
                continue
        except KeyError:                                   # a kind this checkout no longer has: Approvals shows it
            continue
        title = mask_text(str(a.title))[0]
        for office in reading:
            if may_second(root, a, office, officers):
                out.append({"type": "plan-to-second", "office": office, "id": a.id, "kind": a.kind, "title": title,
                            "screen": "approvals",
                            "text": f"{title}: waiting for a second signature, from someone other than the first signer"})
    return out


def waiting_on_office(root: Path, reading: list[str], officers: tuple[Any, ...]) -> list[dict[str, Any]]:
    """What waits on the office: letters, plans waiting for a second signature, board items, and open votes."""
    return (_letters(root, reading, officers) + _plans_to_second(root, reading, officers) + _board_items(root, reading, officers)
            + _decisions(root, reading))


def _occurrences(root: Path, today: date) -> list[Any]:
    from jason.community import community
    from jason.tasks import schedule as task

    return task.agenda(community(), root, start=today - timedelta(days=PAST_DAYS), end=today + timedelta(days=AHEAD_DAYS),
                       today=today)


def duty_rows(found: list[Any], reading: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The schedule's occurrences for ``reading`` as (needs attention, coming up): a duty whose role is the office or the
    board (the board's is every board office's to see), or that names the office as the backup. Overdue and due soon
    first; the urgency words are the digest's (``jason.tasks.attention``)."""
    from jason.community.schedule import Adoption
    from jason.tasks.attention import DOCUMENTS, STATUTE, Urgency, cover_rank

    board_offices = {w for w in reading if w != "manager"}
    basis_word = {STATUTE: "law", DOCUMENTS: "documents"}
    needs, coming = [], []
    for o in found:
        a = o.assignment
        owner = a.role.value
        backup = a.backup.value if a.backup else ""
        if owner in reading:
            via = owner
        elif owner == "board" and board_offices:
            via = "board"
        elif backup in reading:
            via = backup
        else:
            continue
        if o.standing == "done":
            continue
        rank = cover_rank(a.covers)
        row = {"type": "duty", "key": a.key, "title": a.title, "due": o.due.isoformat(), "standing": o.standing,
               "owner": owner, "office": via,
               "backup": via == backup and via != owner, "shared": owner == "board",
               "adoption": a.adoption.value, "basis": basis_word.get(rank, "proposed policy" if a.adoption is Adoption.PROPOSED else "policy"),
               "applies_if": a.applies_if, "screen": "people"}
        if o.standing in ("overdue", "due soon"):
            urgency = (Urgency.SOON if o.standing == "due soon"
                       else Urgency.LEGAL if rank <= DOCUMENTS and not a.applies_if else Urgency.OVERDUE)
            row.update(urgency=urgency.label, rank=int(urgency), text=f"{a.title}, due {row['due']}")
            needs.append(row)
        else:
            row.update(urgency="coming up", rank=int(Urgency.NOTED), text=f"{a.title}, due {row['due']}")
            coming.append(row)
    needs.sort(key=lambda r: (r["rank"], r["due"], r["title"]))
    coming.sort(key=lambda r: (r["due"], r["title"]))
    return needs, coming


def _tasks(root: Path, reading: list[str], officers: tuple[Any, ...], today: date) -> list[dict[str, Any]]:
    """A count of the dock's open tasks the office owns (the titles can name a person, so none is shown)."""
    from jason.tasks import dock as store
    from jason.web.extra.dock import _days

    rows = [t for t in store.load(root).get("tasks", []) if not t.get("done")]
    out = []
    for office in reading:
        mine = [t for t in rows if _owned_by(t.get("owner"), office, officers)]
        if mine:
            late = sum(1 for t in mine if t.get("due") and (_days(t["due"], today) or 0) < 0)
            out.append({"type": "tasks", "office": office, "count": len(mine), "overdue": late, "urgency": "open",
                        "rank": 3, "screen": "", "text": f"{len(mine)} open task(s) owned by the {office}"
                        + (f", {late} overdue" if late else "")})
    return out


def runs_for(root: Path, reading: list[str], scope: Any = None, *, account: str = "", day: date | None = None,
             readers: Any = None) -> list[dict[str, Any]]:
    """The open workflow runs that are the move of one of ``reading``. Whose move a run is, the step it is at, and its date are the
    Work list's own (``jason.web.extra.work``: the same dry fold, ``_pressing`` step, and ``_group``), so Today and Work cannot
    disagree: a run is here when Work lists it under *Yours* for the offices read, or under *The board* with its decision step
    held by one of them (the secretary records it). A run waiting on jason's check, a clock, an arrival, a child run, or another
    office is not. ``account`` names the signed-in person whose offices these are (their own draft run is theirs, and a step
    anyone may do is theirs); empty for another office's lens. A run is its id, definition, label, step, state, and next date; the
    label is the run's own words (never an owner's name). With a ``scope`` (``jason.web.extra.work_scope``): a run of a definition
    the viewer may not know of (``Visibility.ADMIN`` for a non-administrator) is not here, and a held run outside the private view
    is its general title, its state, and its date, with no label, no step id, and a step title only where the definition marks it
    public (``held`` is true)."""
    from jason.web.extra import work
    from jason.workflows import api

    work._register(root, [])
    day = day or _today()
    who = work.Who(account, frozenset(reading), office_lens=True)
    out = []
    for r in work._rows(root, who, day, readers or work._readers(root, day), [], scope):
        if r["state"] not in api.OPEN_STATES or not (r["group"] == "yours" or (r["group"] == "board" and r["mine"])):
            continue
        cur = r["current"]
        office = next((w for w in r["roles"] if w in reading), reading[0])
        label = r["label"] or r["id"]
        title = cur["title"] or ("not opened yet" if r["state"] == "draft" else "")
        out.append({"type": "run", "office": office, "id": r["id"], "definition": r["definition"], "title": r["definitionTitle"],
                    "label": r["label"], "step": cur["id"], "stepTitle": title, "state": r["state"],
                    "due": r["due"]["date"] if r["due"] else None, "screen": "", "text": f"{label}: {title}",
                    "visibility": r["visibility"], "held": r["held"], "group": r["group"], "n": cur["n"]})
    out.sort(key=lambda row: (row["due"] or "9999", row["id"]))
    return out


def _plans_waiting() -> int | None:
    """The engine's plans waiting on a person to decide or sign (None when the store cannot be read). A plan signed and
    waiting to be applied is the ``signedWaiting`` band, not counted here."""
    try:
        from jason.approvals import store
        from jason.web.approvals import _waits_on_a_person

        return sum(1 for a in store.load_all(_root()) if _waits_on_a_person(a))
    except Exception:  # noqa: BLE001
        return None


def signed_waiting(root: Path, now: Any = None) -> list[dict[str, Any]]:
    """The plans signed and waiting to be applied, longest first, as rows of the ``signedWaiting`` band. The text says
    "Signed, waiting to be applied" with how long; a plan older than its kind's limit says it will be planned again before
    it is applied; a terminal-only kind says it is applied at the terminal. Titles are masked like every band's."""
    from jason.approvals.engine import waiting_to_apply, waiting_words
    from jason.approvals.evidence import mask_text

    out = []
    for p in waiting_to_apply(root, now):
        title = mask_text(str(p["title"]))[0]
        text = f"{title}: {waiting_words(p)}"
        note = ("Applied only at a terminal: " + p["applyCommand"]) if p["terminalOnly"] else ""
        out.append({"type": "plan-to-apply", "id": p["id"], "kind": p["kind"], "title": title, "office": "",
                    "waitingHours": p["waitingHours"], "signedAt": p["signedAt"], "stale": p["stale"],
                    "terminalOnly": p["terminalOnly"], "needsSecond": p["needsSecond"], "note": note,
                    "reminderDue": p["reminderDue"], "pausing": p["pausing"],
                    "screen": "approvals", "text": text})
    return out


def person_steps(root: Path, reading: list[str], today: date, scope: Any = None) -> list[dict[str, Any]]:
    """The ``personSteps`` band: every person step of an open run that is on a legal clock, late, in need of a date, due soon, or open
    a while, or escalated because no one holds its office, most urgent first. The same rows whatever office is read (escalation is
    visibility); a step the read office holds comes first among equals (``forOffice``). A held run is its general title (the step is
    "a step" unless the definition marks it public), an administrator's own definition only for an administrator; a per-item step is
    one row with its count (``items``), never an item. Nothing is sent, snoozed, or stored."""
    from jason.tasks import step_guide
    from jason.web.extra import work, work_guide
    from jason.workflows import nudge

    work._register(root, [])
    found = step_guide.step_rows(root, today, holders=work_guide.holders_now(), readers=work._readers(root, today),
                                 reads=scope.reads if scope is not None else None)
    out = []
    for sd, n, r, _owner in found:
        if n.band is nudge.Band.QUIET and not n.escalated_to:
            continue
        held = r["held"]
        offices = [x.value for x in sd.acting_roles if x.value not in ("anyone", "jason", "scheduler")]
        word = n.word or ("no one holds it" if n.escalated_to else "open")
        label = r["runLabel"] if held else work._mask(r["runLabel"])
        out.append({
            "type": "person-step", "band": n.band.value, "urgency": word, "office": offices[0] if offices else "",
            "holder": r["holder"], "forOffice": bool(set(offices) & set(reading)), "id": r["run"], "definition": r["definition"],
            "title": r["title"], "label": label, "step": "" if held else r["step"], "n": 0 if held else r["n"], "held": held,
            "due": n.due or None, "days": n.days, "basis": n.basis_label, "legal": n.legal, "proposed": n.proposed,
            "escalatedTo": n.escalated_to or None,
            "items": {"total": n.items["total"], "notDone": n.items["notDone"]} if n.items else None,
            "screen": "",
            "text": f"{label}: a step is {word}" if held else f"{label}: {r['title']}"
                    + (f" ({n.items['notDone']} of {n.items['total']} not done)" if n.items else ""),
            "_key": (0 if set(offices) & set(reading) else 1, nudge.order_key(n), r["run"], r["n"]),
        })
    out.sort(key=lambda row: row["_key"])
    for row in out:
        del row["_key"]
    return out


def step_numbers() -> dict[str, Any]:
    """The three numbers behind the person-step bands (lead time, open-a-while, escalation delay), labeled as the proposals they are."""
    from jason.workflows import nudge

    p = nudge.DEFAULTS
    return {"leadDays": p.lead_days, "afterHours": p.after_hours, "escalateAfterHours": p.escalate_after_hours, "adopted": p.adopted,
            "note": "" if p.adopted else nudge.PROPOSED_NOTE}


def not_composed(errors: dict[str, str], reading: list[str]) -> list[dict[str, str]]:
    """What this page could not build, and why: the pieces of Today no office owns, and any band that failed."""
    out = []
    waiting = _plans_waiting()
    out.append({"band": "waitingOnOffice", "what": "Plans in the approvals engine still to be decided or signed"
                + (f" ({waiting} waiting on a person)" if waiting else ""),
                "why": "A plan waiting for a second signature is listed for each office with a holder who may give it (not the "
                       "person who signed first or asked for it, and an office the controls allow). A plan waiting for a first "
                       "decision names no office. Read them all in Approvals. A plan already signed and waiting to be applied "
                       "is in the signed-waiting band."})
    out.append({"band": "needsAttention", "what": "The digest's requests, intake, notices, living documents, conflicts, and "
                                                 "people's tasks",
                "why": "The governance digest attaches no office to those lines; only the schedule's duties carry a role. "
                       "They stay on the Board digest."})
    out.append({"band": "nextQuestions", "what": "Next questions (onboarding)",
                "why": "An onboarding question is the board's, not an office's."})
    if "secretary" not in reading and reading:
        out.append({"band": "waitingOnOffice", "what": "The board's open votes to record",
                    "why": "Recording a decision is the secretary's act; only the secretary's page lists them."})
    for band, why in sorted(errors.items()):
        out.append({"band": band, "what": f"The {band} band", "why": why})
    return out


def compose(reading: list[str], *, root: Path, officers: tuple[Any, ...], today: date, scope: Any = None,
            account: str = "") -> dict[str, Any]:
    """The bands for the offices in ``reading``, each built alone, with what could not be built. ``scope`` is the viewer's
    (``jason.web.extra.work_scope``): what the Work band may name of a held or administrator run."""
    errors: dict[str, str] = {}
    coming: list[dict[str, Any]] = []

    def schedule() -> list[dict[str, Any]]:
        found = _occurrences(root, today)
        needs_, coming_ = duty_rows(found, reading)
        coming.extend(coming_)
        return needs_

    waiting = _band("waitingOnOffice", lambda: waiting_on_office(root, reading, officers), errors)
    needs = _band("needsAttention", schedule, errors)
    if "needsAttention" in errors:
        errors["comingUp"] = errors["needsAttention"]
    needs = needs + _band("needsAttention", lambda: _tasks(root, reading, officers, today), errors)
    needs.sort(key=lambda r: (r["rank"], r.get("due") or "9999", r.get("title") or r["text"]))
    work = _band("work", lambda: runs_for(root, reading, scope, account=account, day=today), errors)
    signed = _band("signedWaiting", lambda: signed_waiting(root), errors)
    steps = _band("personSteps", lambda: person_steps(root, reading, today, scope), errors)
    counts = {"waitingOnOffice": len(waiting), "signedWaiting": len(signed), "personSteps": len(steps),
              "needsAttention": len(needs), "comingUp": len(coming), "work": len(work)}
    by_band = {b: sum(1 for r in steps if r["band"] == b) for b in ("legal", "late", "date", "soon", "stale")}
    return {"bands": {"waitingOnOffice": waiting[:LIMIT], "signedWaiting": signed[:LIMIT], "personSteps": steps[:LIMIT],
                      "needsAttention": needs[:LIMIT], "comingUp": coming[:LIMIT], "work": work[:LIMIT]},
            "counts": counts, "stepBands": by_band, "stepNumbers": step_numbers(), "bandErrors": errors,
            "notComposed": not_composed(errors, reading)}


def office_view(args: Args) -> dict[str, Any]:
    """``GET /api/office-view?office=ROLE``: the landing page's bands for one office (``office`` an ``OfficerRole`` word;
    empty reads the viewer's own offices as a union). 401 signed out; 403 for a viewer whose offices do not open P2; 400 for
    a word that is not an office."""
    viewer = _gate()
    asked = normalize(args.get("office"))
    officers = _officers()
    mine = _mine(viewer) if viewer is not None else []
    reading = [asked] if asked else mine
    held = {o.role.value for o in officers}
    out: dict[str, Any] = {
        "found": True, "asOf": _today().isoformat(), "office": asked, "reading": reading, "title": _title(reading),
        "ownOffice": bool(asked) and asked in mine, "vacant": bool(asked) and bool(officers) and asked not in held,
        "offices": lens(officers), "mine": mine, "caveats": list(CAVEATS) + ([] if officers else [NO_OFFICERS]),
    }
    if not reading:
        out.update(bands={b: [] for b in BANDS}, counts={b: 0 for b in BANDS}, bandErrors={}, notComposed=[],
                   stepBands={}, stepNumbers=step_numbers(), note=MINE_EMPTY)
        return out
    from jason.web.extra import work_scope

    scope = work_scope.scope_of(viewer)
    own = viewer is not None and (not asked or asked in mine)       # another office's lens names no person: no draft or anyone-step is its
    account = str(getattr(viewer, "account", "") or "") if own else ""
    out.update(compose(reading, root=_root(), officers=officers, today=_today(), scope=scope, account=account))
    opened_held = sum(1 for r in out["bands"]["work"] if r.get("visibility") == "held" and not r.get("held"))
    if opened_held:                      # held runs named in full (the private view): the reading is logged
        work_scope.log_opening(scope, "api/office-view", runs=opened_held)
    return out


__all__ = ["BANDS", "CAVEATS", "LIMIT", "NOT_AN_OFFICE", "compose", "duty_rows", "lens", "normalize", "office_view",
           "office_words", "person_steps", "runs_for", "signed_waiting", "step_numbers", "waiting_on_office"]
