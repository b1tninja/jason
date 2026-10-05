"""The People and offices screen's loader (``GET /api/people``): who holds each office, read-only.

Answers only a signed-in person on the roster (``jason.web.access.signed_in``: 401 otherwise), and never the owner view
(``owner_view.OWNER_SOURCES`` does not list it, so the owner view's guard refuses it). It reads the profile and the
roster; nothing here writes, and there is no writer: a change of office is the board's act, recorded in the minutes,
then recorded by a person through onboarding's board-roster item, which a second person confirms.

- **Offices** are the board's officer roles (``OfficerRole``: president, vice president, secretary, treasurer), each
  with who holds it (``Community.officers``), what it approves (``Officer.approves``), whether it records the board's
  vote (``Officer.can_approve("the board")``), and the duties the profile's assignments give it
  (``Community.assignments``, as the dock reads them). One person may hold two offices: the answer is grouped both by
  office and by person.
- **A vacant office** says "No one holds the office of OFFICE." with the profile's vacancy provision
  (``Community.vacancy_provision``) recited when it keeps one. Its duties are unassigned: nothing routes to another
  office, and jason picks no one.
- **Directors** without an office are listed by name; a seat is never "vacant" here (the seats are ``BoardRule``'s).
- **Management** (the profile's manager row and the portfolio managers, ``jason.access.officers_with_managers``) is not
  an office of the board; it approves what ``Officer.approves`` says.
- **jason's admins** are not an office and approve nothing; an admin who also holds an office is listed under it.
- **Terms** are the profile's (``Community.terms``: private facts, each with its election record and the provision that
  sets it); none on file says "Terms: not on file." A term whose recorded end is past says "term ended; election due";
  jason computes no other date. The election-status question records a term.
- **A change** points to the board-roster question (its id, words, and the commands that answer, confirm, and apply).

Names are P1 (anyone on the roster); an email address is P2 and goes out masked (``[email]``) unless the person's private
view is open and their offices open P2, when the answer is logged in ``access/served.jsonl``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

Args = dict[str, str]

VACANT = "No one holds the office of {office}."
NO_PROVISION = "The governing documents' vacancy provision is not on file."
NOT_AN_OFFICE = "Not an office; approves nothing."
MANAGEMENT = "Management, not an office of the board."
TERMS = "Terms: not on file."
ENDED = "term ended; election due"
NO_END = "no end date on record"
CHANGE = ("A change of office is the board's act, recorded in the minutes; then the board-roster question records it "
          "(a second person confirms).")
TERMS_NOTE = ("Each term as its election record gives it. A term is recorded by the election-status question (a second "
              "person confirms).")
MASKED = "Email addresses are masked. They show while your private view is open, if your offices open contact details."
SHOWN = "Email addresses are shown: your private view is open. This answer is logged."
CAVEATS = (
    CHANGE,
    "Read from the profile and the sign-in roster by jason. This page changes nothing: no office is added, ended, or "
    "moved from the browser.",
    "A vacant office's duties are unassigned. Who acts meanwhile is only what the governing documents say; jason routes "
    "nothing to another office.",
    "The board approves by a vote at a meeting (CIV 4910), never one person's approval; the president or the secretary "
    "records it.",
)


def _offices() -> tuple[Any, ...]:
    from jason.community.base import OfficerRole

    return (OfficerRole.PRESIDENT, OfficerRole.VICE_PRESIDENT, OfficerRole.SECRETARY, OfficerRole.TREASURER)


def _mask(email: str, unmask: bool) -> str:
    if not email:
        return ""
    return email if unmask else "[email]"


def _duties(role: str, rows: Iterable[Any], holders: list[dict[str, Any]], office_words: str) -> list[dict[str, Any]]:
    """The duties an assignment gives ``role``: routed to the office when someone holds it, else unassigned."""
    from jason.tasks import dock as store
    from jason.web.extra.dock import role_words

    out = []
    for a in rows:
        if a.role.value != role:
            continue
        backup = getattr(a, "backup", None)
        held = bool(holders)
        out.append({"key": a.key, "title": a.title, "adoption": a.adoption.value,
                    "owners": [{"role": role, "name": h["name"], "adoption": a.adoption.value} for h in holders],
                    "assigned": held,
                    "routing": (f"routed to {role_words(role)} (assignment {a.key}, {a.adoption.value})" if held else
                                f"{store.UNASSIGNED} (no one holds the office of {office_words})"),
                    "backup": role_words(backup.value) if backup is not None else ""})
    out.sort(key=lambda d: (d["title"].lower(), d["key"]))
    return out


def question(item_key: str, form: str) -> dict[str, Any]:
    """An onboarding item's standing question: its id in the intake queue, its words, and the commands that answer it,
    confirm it (a second person), and apply it."""
    from jason.community.intake import AskKind, ask_id
    from jason.community.onboarding import item

    ident = ask_id(AskKind.FACT, f"fact:{item_key}", "")
    found = item(item_key)
    return {"item": item_key, "id": ident, "words": found.ask.question if found and found.ask else "", "form": form,
            "commands": [f'jason onboard --answer {ident} "{form}" --by "YOUR NAME"',
                         f'jason onboard --confirm {ident} --by "SECOND PERSON"', "jason onboard --apply"]}


def _term(t: Any, today: date) -> dict[str, Any]:
    from jason.community.base import SeatKind
    from jason.community.roster import PLEASURE

    officer = t.seat is SeatKind.OFFICER
    ended = t.ended(today)
    return {"person": t.person, "seat": t.seat.value, "office": t.office.value if t.office else "",
            "start": t.start.isoformat(), "end": t.end.isoformat() if t.end else None,
            "endNote": t.end.isoformat() if t.end else (PLEASURE if officer else NO_END),
            "source": t.source, "provision": t.provision, "ended": ended, "status": ENDED if ended else ""}


def people_of(officers: Iterable[Any], *, roster: Iterable[Any] = (), admins: Iterable[Any] = (),
              managers: Iterable[Any] = (), community: str = "", duties: Iterable[Any] = (), board: Any = None,
              vacancy: Any = None, unmask: bool = False, today: date | None = None,
              terms: Iterable[Any] = ()) -> dict[str, Any]:
    """The People and offices answer from the records themselves: the profile's ``officers``, the sign-in ``roster``
    (``jason.web.signin.Person``: who can sign in), jason's ``admins`` and portfolio ``managers``, the ``community``'s
    profile key, the duty-owning ``duties`` (``Assignment``), the ``board`` rule, ``vacancy`` (an office ->
    ``VacancyProvision`` or None), and the ``terms`` on file (``Term``). ``unmask`` shows email addresses."""
    from jason.community.roster import CHANGE_FORM, TERM_FORM

    from jason.access import officers_with_managers
    from jason.community.base import OfficerRole

    rows = tuple(officers)
    duty_rows = tuple(duties)
    every = officers_with_managers(rows, community, given=tuple(managers))
    own_names = {o.name for o in rows}
    people = {p.name: p for p in roster}

    def signs_in(name: str) -> bool:
        p = people.get(name)
        return bool(p and p.email)

    def holder(o: Any) -> dict[str, Any]:
        return {"name": o.name, "approves": list(o.approves), "recordsBoard": o.can_approve("the board"),
                "canSignIn": signs_in(o.name)}

    offices = []
    for role in _offices():
        held = [holder(o) for o in every if o.role is role]
        provision = None
        if not held and vacancy is not None:
            try:
                found = vacancy(role)
            except Exception:  # noqa: BLE001 - a provision that cannot be read is not on file
                found = None
            if found is not None:
                provision = {"source": str(found.source), "words": str(found.words or "")}
        offices.append({"office": role.value, "holders": held, "vacant": not held,
                        "vacancy": VACANT.format(office=role.value) if not held else "",
                        "provision": provision, "provisionNote": "" if held or provision else NO_PROVISION,
                        "duties": _duties(role.value, duty_rows, held, role.value)})

    directors = [holder(o) for o in every if o.role is OfficerRole.DIRECTOR]
    seats = None
    if board is not None and getattr(board, "seats", None):
        seats = {"seats": int(board.seats), "source": str(getattr(board, "source", "") or "")}

    managing = [{**holder(o), "portfolio": o.name not in own_names} for o in every if o.role is OfficerRole.MANAGER]
    management = {"holders": managing, "note": MANAGEMENT, "vacant": not managing,
                  "vacancy": "No one holds the manager's role." if not managing else "",
                  "duties": _duties(OfficerRole.MANAGER.value, duty_rows, managing, "manager")}

    by_person: dict[str, dict[str, Any]] = {}
    for o in every:
        p = by_person.setdefault(o.name, {"name": o.name, "offices": [], "approves": [], "recordsBoard": False,
                                          "canSignIn": signs_in(o.name), "admin": False,
                                          "email": _mask(getattr(people.get(o.name), "email", "") or o.email, unmask)})
        if o.role.value not in p["offices"]:
            p["offices"].append(o.role.value)
        p["approves"] += [a for a in o.approves if a not in p["approves"]]
        p["recordsBoard"] = p["recordsBoard"] or o.can_approve("the board")

    admin_rows = []
    for a in admins:
        hit = next((p for p in by_person.values() if p["name"] == a.name), None)
        if hit is None:
            hit = next((by_person[o.name] for o in every if o.email and o.email.lower() == a.email.lower()), None)
        if hit is not None:
            hit["admin"] = True
        admin_rows.append({"name": hit["name"] if hit else a.name, "holds": list(hit["offices"]) if hit else [],
                           "canSignIn": bool(a.email), "note": NOT_AN_OFFICE})
        if hit is None:
            by_person[a.name] = {"name": a.name, "offices": [], "approves": [], "recordsBoard": False,
                                 "canSignIn": bool(a.email), "admin": True, "email": _mask(a.email, unmask)}

    vacant = [o["office"] for o in offices if o["vacant"]]
    day = today or date.today()
    term_rows = [_term(t, day) for t in terms]
    asked = question("board-roster", CHANGE_FORM)
    return {"found": True, "asOf": day.isoformat(),
            "offices": offices, "directors": {"holders": directors, "seats": seats},
            "management": management, "admins": admin_rows,
            "people": sorted(by_person.values(), key=lambda p: p["name"].lower()),
            "vacant": vacant,
            "terms": {"onFile": bool(term_rows), "note": TERMS_NOTE if term_rows else TERMS, "rows": term_rows,
                      "ended": sum(1 for t in term_rows if t["ended"]), "question": question("election-status", TERM_FORM)},
            "change": {"note": CHANGE, "onboardingItem": "board-roster", "screen": "onboarding", "built": True,
                       "question": asked, "commands": asked["commands"], "gap": ""},
            "emailsShown": unmask, "emailsNote": SHOWN if unmask else MASKED,
            "caveats": list(CAVEATS)}


def _unmask(viewer: Any) -> bool:
    """Whether this request shows email addresses: the private view open and the viewer's offices open P2; logged."""
    from jason.web.access import Level, may_see, private_window, served

    if private_window() is None or not may_see(viewer, Level.P2, private=True)[0]:
        return False
    try:
        served(viewer, Level.P2, address="api/people")
    except OSError:
        return False                       # an answer that cannot be logged goes out masked
    return True


def people(args: Args) -> dict[str, Any]:
    """``GET /api/people``: the People and offices answer for the signed-in roster person (401 otherwise)."""
    from flask import current_app

    from jason.access import admins, managers
    from jason.community import community
    from jason.community.profile import profile_name
    from jason.web.access import signed_in
    from jason.web.extra.dock import _duty_owners

    viewer = signed_in()
    sign_in = current_app.extensions.get("jason_sign_in")
    c = community()
    try:
        board = c.board()
    except Exception:  # noqa: BLE001 - no board rule is no seats shown
        board = None
    try:
        terms = c.terms()
    except Exception:  # noqa: BLE001 - terms that cannot be read are not on file
        terms = ()
    return people_of(c.officers(), roster=tuple(sign_in.roster()) if sign_in else (), admins=admins(),
                     managers=managers(), community=profile_name(), duties=_duty_owners(), board=board,
                     vacancy=c.vacancy_provision, unmask=_unmask(viewer), terms=terms)


__all__ = ["CAVEATS", "CHANGE", "ENDED", "NOT_AN_OFFICE", "NO_END", "NO_PROVISION", "TERMS", "TERMS_NOTE", "VACANT",
           "people", "people_of", "question"]
