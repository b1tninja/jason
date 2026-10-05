"""The community record (``GET /api/community``): the association's standing facts in one answer, each with its source.

Board only, read-only. It answers a signed-in roster person (``jason.web.access.signed_in``: 401 otherwise) and never
the owner view (``owner_view.OWNER_SOURCES`` does not list it, so the owner view's guard refuses it). The public page
reads ``community-profile`` instead.

Each fact is a field ``{value, source, onFile, note}``, read from one ``Community`` method and nothing else:

- **identity** (``Community.identity()``): the names, the signer, the posting location, the designated recipient, the
  official address and email, the website, the time zone, the meeting platform, and management. A signer the profile
  does not name is the general wording every template signs with, said so (``default``).
- **board** (``Community.board()``, a ``BoardRule``): the seats with their provision, the quorum with ``quorum_source``,
  the vote basis with ``vote_source``, and whether an interested director counts toward the quorum with its source.
  A rule not on file says "not on file; ask counsel"; counsel's reading is labeled as one.
- **noticePeriod**: the days ``board_items.notice_period`` gives (the documents' longer period, else the statute's,
  cited), for a meeting and for one held solely in executive session, beside the profile's own provision
  (``board_notice_period()``).
- **openForum** (``open_forum_limit()``): the limit the board adopted, or "No limit on record; the board sets it
  (CIV 4925(b))." Never a default.
- **fiscalYearEnd**, **meetingSchedule** (place, cadence, the annual meeting, the practice, with the resolution),
  **units** (the count of ``units()``), **site** (``site()``), and **theme** (a pointer to ``/api/theme``).

A fact the profile leaves at its empty default is "not on file"; jason fills nothing in. The official email goes out
masked (``[email]``) unless the person's private view is open and their offices open P2, when the answer is logged in
``access/served.jsonl``. Nothing here reads a private fact beyond what ``/api/community-profile`` shows, and nothing
writes.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date
from typing import Any

Args = dict[str, str]

NOT_ON_FILE = "not on file"
ASK_COUNSEL = "not on file; ask counsel"
NO_SOURCE = "no source recorded; ask counsel"
MASKED = "[email]"
EMAILS_MASKED = "The official email is masked. It shows while your private view is open, if your offices open contact details."
EMAILS_SHOWN = "The official email is shown: your private view is open. This answer is logged."
CAVEATS = (
    "Read from the profile by jason. Each fact names the Community method or provision it comes from; a fact not on "
    "file is said so and never filled in.",
    "A provision is cited here, not recited: its words are on disk through jason cite. Counsel's reading is labeled as "
    "a reading, not the provision's words.",
    "This page changes nothing. A profile fact is changed by the profile's maintainer, through onboarding's proposal.",
)

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
ORDINALS = ("first", "second", "third", "fourth", "fifth")


def field(value: Any, source: str, *, note: str = "", **more: Any) -> dict[str, Any]:
    """A fact on file: its ``value`` and the ``source`` it was read from."""
    return {"value": value, "source": source, "onFile": True, "note": note, **more}


def missing(note: str = NOT_ON_FILE, **more: Any) -> dict[str, Any]:
    """A fact not on file: no value, no source, and the ``note`` that says so."""
    return {"value": None, "source": "", "onFile": False, "note": note, **more}


def _call(obj: Any, name: str) -> Any:
    """``obj.name()`` (or the attribute), or None when it is missing or raises: a fact that cannot be read is a miss."""
    value = getattr(obj, name, None)
    if value is None:
        return None
    try:
        return value() if callable(value) else value
    except Exception:  # noqa: BLE001 - a method that cannot answer is not on file
        return None


# -- identity ---------------------------------------------------------------------------------------------------------

# Identity's fields this record shows, by the key it answers them under.
IDENTITY_FIELDS = (
    ("name", "name"), ("corporateName", "corporate_name"), ("signer", "signer"),
    ("postingLocation", "posting_location"), ("designatedRecipient", "designated_recipient"),
    ("officialAddress", "official_address"), ("officialEmail", "official_email"), ("website", "website"),
    ("timeZone", "time_zone"), ("meetingPlatform", "meeting_platform"), ("management", "management"),
)


def _identity(c: Any, unmask: bool) -> dict[str, Any]:
    from jason.community.identity import Identity

    ident = _call(c, "identity")
    defaults = {f.name: f.default for f in fields(Identity)}
    out: dict[str, Any] = {}
    for key, attr in IDENTITY_FIELDS:
        value = str(getattr(ident, attr, "") or "") if ident is not None else ""
        if not value:
            out[key] = missing()
            continue
        source = f"Community.identity().{attr}"
        if attr == "signer" and value == defaults.get("signer"):
            out[key] = field(value, f"{source}: the general wording every template signs with; the profile names no "
                                    "other signer", default=True)
            continue
        if attr == "official_email" and not unmask:
            value = MASKED
        out[key] = field(value, source)
    return out


# -- the board ----------------------------------------------------------------------------------------------------------

def _rule_source(src: Any) -> dict[str, Any]:
    """A ``RuleSource`` as its parts: the provision (``source``), and counsel's reading labeled as one."""
    cite = str(getattr(src, "cite", "") or "")
    counsel = str(getattr(src, "counsel", "") or "")
    reading = str(getattr(src, "reading", "") or "")
    label = str(getattr(src, "label", "") or "") if src is not None else ""
    if counsel:
        label = f"{label}, a reading, not the provision's words"
    return {"source": label if counsel else cite, "cite": cite, "counsel": counsel, "reading": reading,
            "isReading": bool(counsel)}


def _sourced(value: Any, src: Any) -> dict[str, Any]:
    """A rule's value with its ``RuleSource``; a value with no source recorded says to ask counsel."""
    parts = _rule_source(src)
    if not parts["source"]:
        return {"value": value, "source": "", "onFile": True, "note": NO_SOURCE, **parts}
    return field(value, parts.pop("source"), **parts)


def _board(c: Any) -> dict[str, Any]:
    rule = _call(c, "board")
    if rule is None:
        return {"seats": missing(), "quorum": missing(ASK_COUNSEL), "voteBasis": missing(ASK_COUNSEL),
                "interestedInQuorum": missing(ASK_COUNSEL)}
    source = str(getattr(rule, "source", "") or "")
    seats = (field(int(rule.seats), source, minimum=int(rule.minimum), maximum=int(rule.maximum)) if source else
             {**missing(NO_SOURCE), "value": int(rule.seats), "onFile": True})
    quorum_source = str(getattr(rule, "quorum_source", "") or "")
    try:
        needed = int(rule.quorum())
    except Exception:  # noqa: BLE001 - a quorum that cannot be computed is not on file
        needed = None
    if needed is None:
        quorum = missing(ASK_COUNSEL)
    elif quorum_source:
        quorum = field(needed, quorum_source, floor=int(rule.quorum_floor), whenSeats=int(rule.seats))
    else:
        quorum = {**missing(f"the provision that sets the quorum is {ASK_COUNSEL}"), "value": needed, "onFile": True,
                  "floor": int(rule.quorum_floor), "whenSeats": int(rule.seats)}
    basis = getattr(rule, "vote_basis", None)
    vote = (_sourced(basis.value, getattr(rule, "vote_source", None)) | {"key": basis.name.lower().replace("_", "-")}
            if basis is not None else missing(ASK_COUNSEL))
    counts = getattr(rule, "interested_in_quorum", None)
    interested = _sourced(counts, getattr(rule, "interested_source", None)) if counts is not None else missing(ASK_COUNSEL)
    return {"seats": seats, "quorum": quorum, "voteBasis": vote, "interestedInQuorum": interested}


# -- notice, forum, year, schedule --------------------------------------------------------------------------------------

def _notice(c: Any) -> dict[str, Any]:
    from jason.tasks.board_items import notice_period

    days, source = notice_period(community=c)
    exec_days, exec_source = notice_period(executive_only=True, community=c)
    period = _call(c, "board_notice_period")
    if period is None:
        provision = missing(f"{NOT_ON_FILE}; the statute's period applies (CIV 4920(a), (b))")
    else:
        provision = field(int(period.days), str(period.source),
                          executiveDays=int(period.executive_days) if period.executive_days is not None else None)
    return {"meeting": field(days, source), "executiveOnly": field(exec_days, exec_source), "provision": provision}


def _forum(c: Any) -> dict[str, Any]:
    from jason.tasks.meeting_room import NO_FORUM_LIMIT

    limit = _call(c, "open_forum_limit")
    if limit is None:
        return missing(NO_FORUM_LIMIT)
    return field(int(limit.minutes), str(limit.source), note="minutes for each member (CIV 4925(b))")


def _fiscal(c: Any) -> dict[str, Any]:
    end = _call(c, "fiscal_year_end")
    if not end:
        return missing()
    month, day = int(end[0]), int(end[1])
    return field({"month": month, "day": day}, "Community.fiscal_year_end()", label=f"{MONTHS[month - 1]} {day}")


def _months(months: tuple[int, ...]) -> str:
    names = [MONTHS[m - 1] for m in months]
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _day(s: Any) -> str:
    """The schedule's day in words: "the third Tuesday"."""
    nth = ORDINALS[s.nth - 1] if 1 <= s.nth <= len(ORDINALS) else f"number {s.nth}"
    return f"the {nth} {WEEKDAYS[s.weekday]}"


def cadence(s: Any) -> str:
    """The schedule's own terms in words: "the third Tuesday at 7:00 pm, in January and April"."""
    when = _day(s) + (f" at {s.time}" if s.time else "")
    return when + (f", in {_months(tuple(s.regular_months))}" if s.regular_months else ", every month")


def _schedule(c: Any) -> dict[str, Any]:
    s = _call(c, "meeting_schedule")
    if s is None:
        return {"place": missing(), "cadence": missing(), "annual": missing(), "practice": missing()}
    source = str(getattr(s, "resolution", "") or "")
    src = source or "Community.meeting_schedule()"
    note = "" if source else "no resolution recorded"
    place = field(s.place, src, note=note) if s.place else missing()
    # The annual meeting of members falls on the schedule's day in its month (``MeetingSchedule.day_in``).
    annual = (field(f"{_day(s)} of {MONTHS[s.annual_month - 1]}", src, note=note, month=int(s.annual_month))
              if s.annual_month else missing())
    practice = (field(s.practice, "Community.meeting_schedule().practice", note="a practice that differs from the schedule")
                if s.practice else missing())
    return {"place": place, "cadence": field(cadence(s), src, note=note), "annual": annual, "practice": practice}


def _units(c: Any) -> dict[str, Any]:
    found = _call(c, "units")
    return field(len(found), "Community.units()") if found else missing()


def _site(c: Any) -> dict[str, Any]:
    site = str(_call(c, "site") or "")
    return field(site, "Community.site()") if site else missing()


def _theme(c: Any) -> dict[str, Any]:
    t = _call(c, "theme")
    out = {"href": "/api/theme", "source": "Community.theme()", "onFile": t is not None}
    return {**out, "wordmark": str(getattr(t, "wordmark", "") or ""), "note": ""} if t is not None else {
        **out, "wordmark": "", "note": f"{NOT_ON_FILE}; the console keeps jason's neutral look"}


def _not_on_file(out: dict[str, Any], prefix: str = "") -> list[str]:
    """Every field's path whose fact is not on file, so a screen can list what to ask for."""
    found = []
    for key, value in out.items():
        if not isinstance(value, dict):
            continue
        path = f"{prefix}{key}"
        if "onFile" in value and "value" in value:
            if not value["onFile"]:
                found.append(path)
        else:
            found += _not_on_file(value, f"{path}.")
    return found


def community_of(c: Any, *, unmask: bool = False, today: date | None = None) -> dict[str, Any]:
    """The community record from the profile ``c`` alone (any object with ``Community``'s methods; a missing one is a
    miss). ``unmask`` shows the official email."""
    facts = {
        "identity": _identity(c, unmask),
        "board": _board(c),
        "noticePeriod": _notice(c),
        "openForum": _forum(c),
        "fiscalYearEnd": _fiscal(c),
        "meetingSchedule": _schedule(c),
        "units": _units(c),
        "site": _site(c),
    }
    return {"found": True, "asOf": (today or date.today()).isoformat(), "slug": str(getattr(c, "slug", "") or ""),
            **facts, "theme": _theme(c), "notOnFile": _not_on_file(facts),
            "emailsShown": unmask, "emailsNote": EMAILS_SHOWN if unmask else EMAILS_MASKED, "caveats": list(CAVEATS)}


def _unmask(viewer: Any) -> bool:
    """Whether this request shows the official email: the private view open and the viewer's offices open P2; logged."""
    from jason.web.access import Level, may_see, private_window, served

    if private_window() is None or not may_see(viewer, Level.P2, private=True)[0]:
        return False
    try:
        served(viewer, Level.P2, address="api/community")
    except OSError:
        return False                       # an answer that cannot be logged goes out masked
    return True


def community_record(args: Args) -> dict[str, Any]:
    """``GET /api/community``: the community record for the signed-in roster person (401 otherwise)."""
    from jason.community import community
    from jason.web.access import signed_in

    viewer = signed_in()
    return community_of(community(), unmask=_unmask(viewer))


__all__ = ["ASK_COUNSEL", "CAVEATS", "MASKED", "NOT_ON_FILE", "NO_SOURCE", "cadence", "community_of", "community_record",
           "field", "missing"]
