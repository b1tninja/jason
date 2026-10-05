"""The meeting room: the live record of one board meeting as the chair runs it and jason keeps the minutes' trail.

One meeting is one file, ``data/meetings/room-<date>.json``: which item is on the stage, who presents and in which
view and Zoom mode, each director's attendance, the call to order, open forum, each motion with its mover, second,
recusals, threshold, roll-call votes and result, the timestamped log the minutes draft reads, the executive session's
general note and times, polls (member input, never a vote), who was admitted, and the transcript lines suggested for
the minutes.

The executive session is kept apart, in ``data/meetings/room-<date>-executive.json`` (P3, ``jason.web.access``). The
minutes of a board meeting "other than an executive session" go to members (Civil Code 4950(a)), and 4935(e) reads:
"Any matter discussed in executive session shall be generally noted in the minutes of the immediately following
meeting that is open to the entire membership." So while the room is in executive session every log entry, motion,
roll call, decision, and admission is written to the executive record, and the open log gets only the general note
(the matters' ``ExecutiveSubject`` in the statute's words with their 4935 subdivisions, never an item's title), the
start and end times, and "The board returned to open session". A matter whose 4935 subject is not named is not taken
into executive session.

jason records; it decides nothing. A motion needs two different directors and a quorum of those present. The quorum,
what carries a motion, and whether a recused director counts toward the quorum come from the profile's ``BoardRule``
(the bylaws' provision, recited from disk, or counsel's reading, labeled; ``board_rules``), never from jason. Where one
is not on file the room says "not on file; ask counsel" and labels what it counts: a majority of the directors listed
for the quorum and a majority of those present for the vote, each a reading, not the rule. A recusal is a director's
disclosure the secretary records on the motion; jason never applies one. CIV 5350(b) lists matters on which an
interested director "shall not vote", and 5350(a) applies Corporations Code 7233 and 7234 to a contract or other
transaction the board approves; whether the recused director still counts toward the quorum is the bylaws' or
counsel's to say. Until it is on file, the tally is worked both ways (counted among the directors present, and not),
and a vote the two readings decide differently is held, not recorded. An off-agenda emergency item needs two-thirds of
the directors present, or every one of them when fewer than two-thirds of the board is present (CIV 4930(d)(2)). A
topic not on the agenda may take only the CIV 4930 paths. The members' speaking limit is the board's to establish (CIV
4925(b)): the profile's ``open_forum_limit()``, or one a person enters in the room; with neither, the room says no
limit is on record and never assumes one. A decided motion is also written to ``jason.tasks.decisions`` (with its
recusals) so the minutes draft quotes it; one decided in executive session is marked so there, and the open views
leave it out.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.models.meetings import executive_general_note, executive_subject

STORE = "meetings"
EXECUTIVE_SUFFIX = "-executive"

PRESENTERS = ("jason", "chair")
VIEWS = ("host", "shared")
MODES = ("co-host", "host", "portal")
ATTENDANCE = ("present", "absent", "remote")
THRESHOLDS = ("majority", "two-thirds")
VOTES = ("aye", "no", "abstain")
RESULTS = ("carried", "failed", "")
SUGGESTION_STATES = ("suggested", "added", "dismissed")
OPEN_SESSION = "open session"
EXECUTIVE_SESSION = "executive session"

# What the room says where the bylaws' rule and counsel's reading are both missing, and where the board has adopted no
# speaking limit. Neither is ever filled in with a default.
NOT_ON_FILE = "not on file; ask counsel"
NO_FORUM_LIMIT = "No limit on record; the board sets it (CIV 4925(b))."

# The refusal for a matter without its 4935 subject: the open minutes note a matter by its subject's general words
# (4935(e)), so a matter that has none named cannot be taken into executive session.
NAME_SUBJECT = "name the 4935 subject first"
# What the open record says when the board comes back (and the only words besides the general note and the times).
RETURNED = "The board returned to open session."
ADJOURNED_TO = "The board adjourned to executive session"

# The only ways a board may take up a topic that is not on the posted agenda (Civil Code 4930). Anything else is refused.
OFF_AGENDA_PATHS: dict[str, str] = {
    "b": "The board responded briefly, asked a clarifying question, made an announcement, or reported on its own activities (CIV 4930(b)).",
    "c": "The board gave staff a factual reference, asked staff to report back, or directed that the topic be placed on a future agenda (CIV 4930(c)).",
    "d1": "A majority of the board found an emergency and took up the item (CIV 4930(d)(1)).",
    "d2": "The board found, by two-thirds of the directors present (or all of them, fewer than two-thirds of the board being present), that immediate action was needed on a matter that arose after the agenda was posted (CIV 4930(d)(2)).",
    "d3": "The item was on an agenda posted within the last 30 days and was continued to this meeting (CIV 4930(d)(3)).",
}
IDENTIFY_FIRST = "The board identified the item to the members before acting (CIV 4930(e))."

ACTIONS = ("call_to_order", "go_to", "set_presenter", "set_view", "set_mode", "attendance", "open_forum", "motion_draft", "vote", "decide",
           "off_agenda", "executive_start", "executive_end", "poll", "admit", "suggest", "suggestion_state", "adjourn")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _day(day: str) -> str:
    iso = str(day or "").strip()
    try:
        return date.fromisoformat(iso).isoformat()
    except ValueError as exc:
        raise KeyError(iso or "(no date)") from exc


def _path(data_dir: Path, day: str) -> Path:
    return Path(data_dir) / STORE / f"room-{_day(day)}.json"


def executive_path(data_dir: Path, day: str) -> Path:
    """The executive record's file for ``day``: ``meetings/room-<date>-executive.json``, P3 (``jason.web.access``)."""
    return Path(data_dir) / STORE / f"room-{_day(day)}{EXECUTIVE_SUFFIX}.json"


def empty(day: str) -> dict[str, Any]:
    return {"date": _day(day), "directors": [], "current": 0, "presenter": "jason", "view": "host", "mode": "co-host",
            "attendance": {}, "calledToOrder": "", "openForum": {"count": 0, "limitMinutes": 0, "limitBy": ""}, "motions": [], "log": [],
            "executive": {"active": False, "startedAt": "", "endedAt": "", "note": "", "subjects": [], "sessions": []}, "polls": [],
            "admitted": [], "transcriptSuggestions": [], "adjournedAt": "", "created": "", "updated": "", "history": []}


def empty_executive(day: str) -> dict[str, Any]:
    """The executive record: each session's matters (id, subject, title), its log, motions, and admissions."""
    return {"date": _day(day), "sessions": [], "log": [], "motions": [], "admitted": [], "created": "", "updated": "", "history": []}


def load(data_dir: Path, day: str) -> dict[str, Any]:
    """The room record for ``day``, or an empty one when the meeting has not started."""
    path = _path(data_dir, day)
    if not path.is_file():
        return empty(day)
    room = {**empty(day), **json.loads(path.read_text(encoding="utf-8"))}
    room["executive"] = {**empty(day)["executive"], **(room.get("executive") or {})}
    forum = {**empty(day)["openForum"], **(room.get("openForum") or {})}
    if not forum.get("limitBy"):   # a limit no person entered (an earlier default) is not a limit on record
        forum["limitMinutes"] = 0
    room["openForum"] = forum
    return room


def load_executive(data_dir: Path, day: str) -> dict[str, Any]:
    """The executive record for ``day``, or an empty one. P3: only the private view shows it."""
    path = executive_path(data_dir, day)
    if not path.is_file():
        return empty_executive(day)
    return {**empty_executive(day), **json.loads(path.read_text(encoding="utf-8"))}


def save(data_dir: Path, room: dict[str, Any]) -> Path:
    path = _path(data_dir, room["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(room, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def save_executive(data_dir: Path, record: dict[str, Any]) -> Path:
    path = executive_path(data_dir, record["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


# -- rules ------------------------------------------------------------------------------------------------------------

def present(room: dict[str, Any]) -> list[str]:
    """The directors in the meeting, in the room or remote, in roster order."""
    att = room.get("attendance", {})
    names = list(room.get("directors", [])) + [n for n in att if n not in room.get("directors", [])]
    return [n for n in names if att.get(n) in ("present", "remote")]


_UNSET: Any = object()


def _board() -> Any:
    """The active profile's ``BoardRule``, or None (no profile, or none on file)."""
    try:
        from jason.community import community

        return community().board()
    except Exception:  # noqa: BLE001 - no rule on file is a miss the room shows
        return None


def quorum(directors: list[str], board: Any = _UNSET) -> int:
    """Directors needed for a quorum: the profile's board rule when it has one, else a majority of the directors listed
    (a reading the room labels, ``board_rules``: the bylaws' rule is not on file)."""
    rule = _board() if board is _UNSET else board
    count = len(directors)
    if rule is not None and count:
        try:
            return int(rule.quorum(count))
        except Exception:  # noqa: BLE001
            pass
    return count // 2 + 1 if count else 0


def needed(present_count: int, threshold: str, seats: int, basis: Any = None) -> int:
    """Ayes a motion needs. For two-thirds (CIV 4930(d)(2)): two-thirds of the directors present, or every one of them
    when fewer than two-thirds of the board is present. Otherwise the vote rule on file (``VoteBasis``): a majority of the
    directors in office, or of those present; with none on file, a majority of those present (a reading the room labels).
    ``present_count`` is whom the reading counts as present: a recused director is in it under one reading and not the
    other (``tally``)."""
    if present_count <= 0:
        return 0
    if threshold == "two-thirds":
        enough_of_board = seats <= 0 or present_count >= math.ceil(2 * seats / 3)
        return math.ceil(2 * present_count / 3) if enough_of_board else present_count
    if getattr(basis, "name", "") == "MAJORITY_IN_OFFICE" and seats > 0:
        return seats // 2 + 1
    return present_count // 2 + 1


def _recite(cite: str, data_dir: Path | None) -> str:
    """The words of ``cite`` ("Bylaws 1.2", "CORP 7211(a)(8)") from jason's copy on disk, or "" when they are not there.
    A cite naming several sections ("Bylaws 1.1, 1.2") is recited one section at a time."""
    if not cite or data_dir is None:
        return ""
    try:
        from jason.community import community
        from jason.tasks.cite import Shelf

        shelf = Shelf(community(), Path(data_dir))
        text = (shelf(cite).state.text or "").strip()
        if text or "," not in cite:
            return text
        head, *rest = [p.strip() for p in cite.split(",")]
        book = head.rsplit(" ", 1)[0]
        parts = [head] + [p if " " in p else f"{book} {p}" for p in rest]
        return "\n\n".join(t for t in ((shelf(p).state.text or "").strip() for p in parts) if t)
    except Exception:  # noqa: BLE001 - the words not on disk are a miss, said so
        return ""


def _source_line(source: Any, data_dir: Path | None) -> dict[str, Any]:
    """A ``RuleSource`` as the page shows it: the provision's words recited from disk, or counsel's reading labeled."""
    cite, counsel, reading = getattr(source, "cite", "") or "", getattr(source, "counsel", "") or "", getattr(source, "reading", "") or ""
    words = _recite(cite, data_dir)
    if counsel:
        label = f"{source.label}, a reading, not the provision's words"
    else:
        label = cite + ("" if words or data_dir is None else f" (its words are not on disk: jason cite \"{cite}\")")
    return {"onFile": True, "source": cite, "label": label, "words": words, "counsel": counsel, "reading": reading}


def board_rules(data_dir: Path | None = None, board: Any = _UNSET) -> dict[str, Any]:
    """The rules the room counts by, each with where it comes from: ``quorum``, ``voteBasis``, ``interested`` (whether a
    recused director counts toward the quorum and among those present), and ``openForum``. A rule on file carries its
    source and, with ``data_dir``, the provision's words recited from disk; counsel's reading is labeled as one. A rule
    not on file says so ("not on file; ask counsel") with what the room counts meanwhile, labeled as a reading."""
    rule = _board() if board is _UNSET else board
    if rule is not None and getattr(rule, "source", ""):
        q = {"onFile": True, "source": rule.source, "words": _recite(rule.source, data_dir), "label": rule.source}
    else:
        q = {"onFile": False, "source": "", "words": "",
             "label": f"The bylaws' quorum rule is {NOT_ON_FILE}. The room counts a majority of the directors listed, a reading, not the rule."}
    basis = getattr(rule, "vote_basis", None)
    if basis is not None:
        v = {**_source_line(getattr(rule, "vote_source", None), data_dir), "basis": basis.value,
             "key": basis.name.lower().replace("_", "-")}
        if not v["source"] and not v["counsel"]:
            v["label"] = "no source recorded for the vote rule; ask counsel"
    else:
        v = {"onFile": False, "basis": "", "source": "", "words": "", "counsel": "", "reading": "",
             "label": f"The vote rule is {NOT_ON_FILE}. The room counts a majority of the directors present, a reading, not the rule."}
    counts = getattr(rule, "interested_in_quorum", None)
    if counts is not None:
        i = {**_source_line(getattr(rule, "interested_source", None), data_dir), "counts": counts}
    else:
        i = {"onFile": False, "counts": None, "source": "", "words": "", "counsel": "", "reading": "",
             "label": (f"Whether a recused director counts toward the quorum and among the directors present is {NOT_ON_FILE}. "
                       "The room works the vote both ways and holds one the two readings decide differently.")}
    return {"quorum": q, "voteBasis": v, "interested": i, "openForum": forum_rule()}


def forum_rule() -> dict[str, Any]:
    """The members' speaking limit the board established (CIV 4925(b)), from the profile's ``open_forum_limit()``:
    ``{onFile, minutes, source, label}``. With none on file, ``minutes`` is 0 and the label says no limit is on record."""
    try:
        from jason.community import community

        limit = community().open_forum_limit()
    except Exception:  # noqa: BLE001 - no profile: none on record
        limit = None
    if limit is None:
        return {"onFile": False, "minutes": 0, "source": "", "label": NO_FORUM_LIMIT}
    return {"onFile": True, "minutes": int(limit.minutes), "source": limit.source,
            "label": f"{int(limit.minutes)} minutes each ({limit.source}; CIV 4925(b))."}


def forum_limit(room: dict[str, Any]) -> dict[str, Any]:
    """The limit the room runs open forum by: one a person entered in the room (``limitBy``), else the board's policy,
    else none (``minutes`` 0, with ``NO_FORUM_LIMIT``)."""
    forum = room.get("openForum") or {}
    entered = int(forum.get("limitMinutes") or 0)
    if entered and forum.get("limitBy"):   # who entered it is in the record and the log, not in what the stage shows
        return {"minutes": entered, "source": "entered in the room",
                "label": f"{entered} minutes each (entered in the room; the board sets the limit, CIV 4925(b))."}
    rule = forum_rule()
    return {"minutes": rule["minutes"], "source": rule["source"], "label": rule["label"]}


def tally(motion: dict[str, Any], room: dict[str, Any], board: Any = _UNSET) -> dict[str, Any]:
    """The roll call as it stands: counts, who may vote, what it needs, and whether it carries once every voter has answered.

    A recused director does not vote. Whether they still count toward the quorum and among the directors present is the
    profile's ``BoardRule.interested_in_quorum``. With it not on file the vote is worked both ways: ``readings`` gives
    each, and when they differ the state is "held" (``NOT_ON_FILE``), never one of them chosen silently."""
    rule = _board() if board is _UNSET else board
    here = present(room)
    recused = [n for n in motion.get("recused", []) if n in here]
    voters = [n for n in here if n not in recused]
    votes = motion.get("votes", {})
    counts = {v: sum(1 for n in voters if votes.get(n) == v) for v in VOTES}
    seats = len(room.get("directors", []))
    threshold = motion.get("threshold", "majority")
    basis = getattr(rule, "vote_basis", None)
    q = quorum(list(room.get("directors", [])), rule)
    answered = all(votes.get(n) in VOTES for n in voters) and bool(voters)

    def reading(base: int) -> dict[str, Any]:
        need = needed(base, threshold, seats, basis)
        quorate = q > 0 and base >= q
        state = "open" if not answered else ("carries" if quorate and counts["aye"] >= need else "fails")
        return {"needs": need, "quorum": quorate, "state": state}

    counted, apart = reading(len(here)), reading(len(voters))
    rule_counts = getattr(rule, "interested_in_quorum", None)
    if not recused or rule_counts is True:
        chosen, held, way = counted, False, "counted"
    elif rule_counts is False:
        chosen, held, way = apart, False, "not counted"
    else:
        held = answered and counted["state"] != apart["state"]
        chosen, way = counted, "not on file"
    state = "held" if held else chosen["state"]
    line = f"Yes {counts['aye']} · No {counts['no']} · Abstain {counts['abstain']} · Recused {len(recused)}. "
    if recused and way == "not on file":
        line += (f"Needs {counted['needs']} yes counting the recused director{'s' if len(recused) > 1 else ''} as present"
                 + ("" if counted["quorum"] else " (no quorum)")
                 + f", {apart['needs']} yes if not" + ("" if apart["quorum"] else " (no quorum)") + ". ")
        line += {"open": "Vote open.",
                 "carries": "Carries under either reading.", "fails": "Fails under either reading.",
                 "held": f"Held: the readings differ, and whether a recused director counts is {NOT_ON_FILE}."}[state]
    else:
        line += f"Needs {chosen['needs']} yes" + ("" if chosen["quorum"] or not answered else " (no quorum for this vote)") + ". "
        line += {"open": "Vote open.", "carries": "Carries.", "fails": "Fails."}[state]
    return {"aye": counts["aye"], "no": counts["no"], "abstain": counts["abstain"], "recused": len(recused), "recusedNames": recused,
            "voters": voters, "needs": chosen["needs"], "answered": answered, "state": state, "line": line,
            "readings": {"counted": counted, "notCounted": apart} if recused else {}, "recusal": way if recused else ""}


def _clock(iso: str) -> str:
    """A logged time as the association's clock time ("7:05 PM"), in the profile's time zone (America/Los_Angeles when
    it names none); the ISO time when it cannot be read."""
    try:
        from zoneinfo import ZoneInfo

        zone = "America/Los_Angeles"
        try:
            from jason.community import community

            c = community()
            for name in ("time_zone", "timezone"):
                value = getattr(c, name, None)
                value = value() if callable(value) else value
                if isinstance(value, str) and value.strip():
                    zone = value.strip()
                    break
        except Exception:
            pass
        at = datetime.fromisoformat(iso).astimezone(ZoneInfo(zone))
        return f"{at:%I:%M %p}".lstrip("0")
    except Exception:
        return iso


# -- writes -----------------------------------------------------------------------------------------------------------

def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "meeting-room", timeout=60, purpose=f"meeting room: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _log(room: dict[str, Any], title: str, by: str, tone: str = "neutral", **more: Any) -> None:
    """One entry in ``room``'s log: the open record's, or the executive record's (the caller picks)."""
    room["log"].append({"at": _now(), "title": title, "tone": tone, "by": by, **more})


def _one_of(value: Any, choices: tuple[str, ...], what: str) -> str:
    v = str(value or "").strip()
    if v not in choices:
        raise ValueError(f"{what} is one of {', '.join(c or '(empty)' for c in choices)}")
    return v


def _director(room: dict[str, Any], name: Any, what: str) -> str:
    n = str(name or "").strip()
    if not n:
        raise ValueError(f"{what} names a director")
    if room["directors"] and n not in room["directors"]:
        raise ValueError(f"{n} is not one of the directors")
    return n


def _int(value: Any, what: str, least: int = 0) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{what} is a whole number") from exc
    if n < least:
        raise ValueError(f"{what} is at least {least}")
    return n


def matters_of(body: dict[str, Any]) -> list[dict[str, str]]:
    """The matters an ``executive_start`` takes into executive session, each ``{id, subject, title}``, from ``matters``
    (a list of objects) or ``subjects`` (a list of words). Every matter needs its 4935 subject (an ``ExecutiveSubject``
    value): the open minutes note it by that and nothing else (CIV 4935(e)). A matter without one is refused with
    ``NAME_SUBJECT``; so is a body with no matter at all. The title is for the executive record only."""
    rows = body.get("matters")
    if rows is None:
        rows = [{"subject": s} for s in (body.get("subjects") or [])]
    if not isinstance(rows, list):
        raise ValueError("matters is a list of {id, subject}")
    out: list[dict[str, str]] = []
    for n, raw in enumerate(rows, 1):
        raw = raw if isinstance(raw, dict) else {"subject": raw}
        ident = str(raw.get("id", "") or "").strip() or f"matter-{n}"
        subject = executive_subject(raw.get("subject"))
        if subject is None:
            raise ValueError(f"{NAME_SUBJECT}: matter {ident} has no Civil Code 4935 subject (litigation, contracts, member "
                             "discipline, personnel, a member's payment of assessments, or a foreclosure decision)")
        out.append({"id": ident, "subject": subject.value, "title": str(raw.get("title", "") or "").strip()})
    if not out:
        raise ValueError(f"{NAME_SUBJECT}: the board adjourns to executive session only on a Civil Code 4935 subject")
    return out


@_store_lock
def update(data_dir: Path, day: str, body: dict[str, Any], by: str, *, directors: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    """Apply one named ``action`` from ``body`` to the room for ``day``, recorded as ``by``'s act. Anything that is not
    one of ``ACTIONS``, or breaks a rule above, is refused with ValueError; an unknown motion is a KeyError.

    While the room is in executive session, what the action logs, and any motion, roll call, decision, or admission, is
    written to the executive record (``room-<date>-executive.json``), never the open one: the open minutes note an
    executive matter only generally (CIV 4935(e)), and the minutes members receive are those "other than an executive
    session" (4950(a)). Returns the open room record."""
    by = str(by or "").strip()
    if not by:
        raise ValueError("every entry names the person who made it (by)")
    action = str(body.get("action", "")).strip()
    if action not in ACTIONS:
        raise ValueError(f"no action {action!r}; one of {', '.join(ACTIONS)}")
    room = load(data_dir, day)
    if directors:
        room["directors"] = [str(d) for d in directors]
    now = _now()
    if not room["created"]:
        room["created"] = now
    att = room["attendance"]
    ex = room["executive"]
    was_executive = bool(ex["active"])
    shut: dict[str, Any] = {}

    def closed() -> dict[str, Any]:
        """The executive record, loaded once."""
        if not shut:
            shut.update(load_executive(data_dir, room["date"]))
            if not shut["created"]:
                shut["created"] = now
        return shut

    def log(title: str, tone: str = "neutral") -> None:
        """One entry in the log of the session the room is in: the executive record while executive session is active."""
        _log(closed() if ex["active"] else room, title, by, tone)

    def find(motion_id: Any) -> tuple[dict[str, Any], bool]:
        """The motion and whether it was moved in executive session; refused when the room is in the other session."""
        key = str(motion_id or "")
        found = next((m for m in room["motions"] if m["id"] == key), None)
        executive = False
        if found is None and key.startswith("x"):
            found = next((m for m in closed()["motions"] if m["id"] == key), None)
            executive = True
        if found is None:
            raise KeyError(f"motion {motion_id}")
        if executive and not ex["active"]:
            raise ValueError("that motion was moved in executive session; the board votes on it in executive session")
        if not executive and ex["active"]:
            raise ValueError("that motion was moved in open session; the board votes on it when it returns to open session")
        return found, executive

    if action == "call_to_order":
        if room["calledToOrder"]:
            raise ValueError(f"already called to order at {room['calledToOrder']}")
        here = present(room)
        rule = _board()
        q = quorum(room["directors"], rule)
        room["calledToOrder"] = now
        absent = [n for n in room["directors"] if n not in here]
        roster = f"Present: {', '.join(here) or 'none recorded'}." + (f" Absent: {', '.join(absent)}." if absent else "")
        has_quorum = len(here) >= q and q > 0
        basis = f" ({rule.source})" if rule is not None and getattr(rule, "source", "") else \
            f" (a majority of the directors listed; the bylaws' quorum rule is {NOT_ON_FILE})"
        log(f"Called to order by {str(body.get('chair', '') or 'the chair').strip()}. {roster} "
            f"{len(here)} of {len(room['directors']) or '?'} directors present; a quorum is {q}{basis}. "
            + ("A quorum was present." if has_quorum else "No quorum was present; the board cannot act."), "good" if has_quorum else "warn")
    elif action == "go_to":
        idx = _int(body.get("item"), "item")
        room["current"] = idx
        title = str(body.get("title", "") or "").strip()
        if title:
            log(f"Item opened: {title}")
    elif action == "set_presenter":
        room["presenter"] = _one_of(body.get("presenter"), PRESENTERS, "presenter")
    elif action == "set_view":
        room["view"] = _one_of(body.get("view"), VIEWS, "view")
    elif action == "set_mode":
        room["mode"] = _one_of(body.get("mode"), MODES, "mode")
    elif action == "attendance":
        rows = body.get("attendance")
        if not isinstance(rows, dict):
            rows = {body.get("name"): body.get("state")}
        for name, state in rows.items():
            att[_director(room, name, "attendance")] = _one_of(state, ATTENDANCE, "attendance")
    elif action == "open_forum":
        forum = room["openForum"]
        if "count" in body:
            forum["count"] = _int(body["count"], "count")
        if "limitMinutes" in body:
            # A limit a person enters (the board's, read out by the chair); jason never supplies one (CIV 4925(b)).
            forum["limitMinutes"] = _int(body["limitMinutes"], "limitMinutes", 1)
            forum["limitBy"] = by
        if body.get("close"):
            n = forum["count"]
            limit = forum_limit(room)
            each = f", {limit['minutes']} minutes each ({limit['source']})" if limit["minutes"] else "; no time limit on record"
            log(f"Open forum: {n} member{'s' if n != 1 else ''} spoke{each} (CIV 4925(b)).")
    elif action == "motion_draft":
        text = str(body.get("text", "") or "").strip()
        if not text:
            raise ValueError("a motion needs its text")
        mover = _director(room, body.get("mover"), "mover")
        second = _director(room, body.get("second"), "second")
        if mover == second:
            raise ValueError("a motion needs two different directors: one moves, one seconds")
        here = present(room)
        q = quorum(room["directors"])
        if len(here) < q or q == 0:
            raise ValueError(f"no quorum: {len(here)} directors present, {q} needed")
        if mover not in here or second not in here:
            raise ValueError("the mover and the second must be present")
        threshold = _one_of(body.get("threshold") or "majority", THRESHOLDS, "threshold")
        # Each recusal is the director's own disclosure, entered by the secretary; jason infers none.
        recused = [_director(room, n, "recused") for n in (body.get("recused") or [])]
        if mover in recused or second in recused:
            raise ValueError("a recused director neither moves nor seconds")
        rest = [n for n in here if n not in recused]
        short = ""
        if recused and len(rest) < q:
            counts = getattr(_board(), "interested_in_quorum", None)
            if counts is False:
                raise ValueError(f"no quorum for this motion: {len(rest)} directors present and not recused, {q} needed "
                                 "(a recused director does not count toward the quorum, as the rule on file reads)")
            if counts is None:
                short = (f"With {', '.join(recused)} recused, {len(rest)} directors present are not recused; a quorum is {q}. "
                         f"Whether a recused director counts toward the quorum is {NOT_ON_FILE}.")
        where = closed()["motions"] if ex["active"] else room["motions"]
        motion = {"id": f"{'x' if ex['active'] else 'm'}{len(where) + 1}", "itemId": str(body.get("itemId", "") or ""),
                  "title": str(body.get("title", "") or "").strip(), "text": text, "mover": mover, "second": second, "recused": recused,
                  "threshold": threshold, "votes": {}, "result": "", "decidedAt": "", "movedAt": now,
                  "session": EXECUTIVE_SESSION if ex["active"] else OPEN_SESSION}
        where.append(motion)
        log(f"Motion by {mover}, seconded by {second}: {text}" + (f" {', '.join(recused)} recused." if recused else ""))
        if short:
            log(short, "warn")
    elif action == "vote":
        motion, _ = find(body.get("motion"))
        if motion["result"]:
            raise ValueError("the vote on that motion is recorded; a new motion is a new vote")
        name = _director(room, body.get("name"), "vote")
        if name in motion["recused"]:
            raise ValueError(f"{name} is recused from this motion and does not vote")
        if name not in present(room):
            raise ValueError(f"{name} is not present")
        motion["votes"][name] = _one_of(body.get("vote"), VOTES, "vote")
    elif action == "decide":
        motion, executive = find(body.get("motion"))
        if motion["result"]:
            raise ValueError("already decided")
        rule = _board()
        t = tally(motion, room, rule)
        if not t["answered"]:
            raise ValueError("roll call by name: every director present and not recused answers aye, no, or abstain first")
        if t["state"] == "held":
            raise ValueError(f"the two readings decide this vote differently ({t['line']}). Whether a recused director "
                             f"counts toward the quorum and among those present is {NOT_ON_FILE}; the vote is not recorded "
                             "as carried or failed. The board may continue the item until counsel's reading is on file.")
        motion["result"] = "carried" if t["state"] == "carries" else "failed"
        motion["decidedAt"] = now
        motion["tally"] = {k: t[k] for k in ("aye", "no", "abstain", "recused", "needs")}
        roll = ", ".join(f"{n} {motion['votes'][n]}" for n in t["voters"])
        unruled = [] if getattr(rule, "vote_basis", None) is not None or motion["threshold"] == "two-thirds" else \
            [f"the vote rule is {NOT_ON_FILE}; counted as a majority of the directors present, a reading"]
        if t["recusal"] == "not on file":
            unruled.append(f"whether a recused director counts is {NOT_ON_FILE}; the result is the same under either reading")
        log(f"Roll call: {roll}. {motion['result'].capitalize()}, {t['aye']}–{t['no']}–{t['abstain']}"
            + (f", {', '.join(t['recusedNames'])} recused" if t["recusedNames"] else "") + f" ({motion['threshold']}, {t['needs']} needed"
            + "".join(f"; {u}" for u in unruled) + ").",
            "good" if motion["result"] == "carried" else "warn")
        from jason.tasks import decisions

        votes = dict(motion["votes"])
        for n in room["directors"]:
            if n not in votes and n not in motion["recused"]:
                votes[n] = "absent"
        subject = ""
        if executive:
            # The decision's 4935 subject: its matter's when the motion names one, else the session's only subject.
            matters = (closed()["sessions"] or [{}])[-1].get("matters") or []
            subject = next((m["subject"] for m in matters if m.get("id") and m["id"] == motion["itemId"]), "")
            if not subject and len({m["subject"] for m in matters}) == 1:
                subject = matters[0]["subject"]
        decisions.record(data_dir, room["date"], motion["title"] or motion["text"][:60], motion["text"], item=motion["itemId"],
                         session=EXECUTIVE_SESSION if executive else OPEN_SESSION, subject=subject,
                         mover=motion["mover"], second=motion["second"], votes=votes, recused=list(motion["recused"]),
                         outcome="approved" if motion["result"] == "carried" else "denied", by=by,
                         notes=(f"Recused: {', '.join(motion['recused'])}. " if motion["recused"] else "") + f"Threshold {motion['threshold']}; {t['line']}"
                         + "".join(f" Note: {u}." for u in unruled))
    elif action == "off_agenda":
        path = str(body.get("path", "") or "").strip()
        if path not in OFF_AGENDA_PATHS:
            raise ValueError(f"a topic not on the agenda takes one of the CIV 4930 paths: {', '.join(OFF_AGENDA_PATHS)}")
        topic = str(body.get("topic", "") or "").strip()
        log((f"Not on the posted agenda: {topic}. " if topic else "A topic not on the posted agenda was raised. ")
            + OFF_AGENDA_PATHS[path] + (" " + IDENTIFY_FIRST if path.startswith("d") else ""), "warn")
    elif action == "executive_start":
        if ex["active"]:
            raise ValueError("already in executive session")
        matters = matters_of(body)
        pending = [m["id"] for m in room["motions"] if not m["result"]]
        if pending:
            raise ValueError(f"decide the motion on the floor ({', '.join(pending)}) before the board adjourns to executive session")
        subjects = list(dict.fromkeys(m["subject"] for m in matters))
        note = executive_general_note(subjects)
        ex.update(active=True, startedAt=now, endedAt="", note=note, subjects=subjects)
        ex.setdefault("sessions", []).append({"startedAt": now, "endedAt": "", "subjects": subjects})
        _log(room, f"{ADJOURNED_TO} at {_clock(now)} to discuss {note}. Members left the open session. The host pauses the "
             "recording and the live transcript; jason does not control them from here.", by, "warn", at=now, startedAt=now)
        record = closed()
        record["sessions"].append({"startedAt": now, "endedAt": "", "matters": matters, "by": by})
        note_text = str(body.get("note", "") or "").strip()
        _log(record, "Executive session began. Matters: " + "; ".join(f"{m['title'] or m['id']} ({m['subject']})" for m in matters)
             + (f". {note_text}" if note_text else "") + ".", by, "warn")
    elif action == "executive_end":
        if not ex["active"]:
            raise ValueError("not in executive session")
        started = ex["startedAt"]
        ex.update(active=False, endedAt=now)
        if ex.get("sessions"):
            ex["sessions"][-1]["endedAt"] = now
        record = closed()
        if record["sessions"]:
            record["sessions"][-1]["endedAt"] = now
        _log(record, "Executive session ended.", by)
        _log(room, f"The board met in executive session from {_clock(started)} to {_clock(now)} to discuss {ex['note']}. {RETURNED} "
             "The host resumes the recording and the live transcript; jason does not control them from here.", by,
             at=now, startedAt=started, endedAt=now)
    elif action == "poll":
        if ex["active"]:
            raise ValueError("members are not in executive session (CIV 4935); polls wait for the open session")
        question = str(body.get("question", "") or "").strip()
        if not question:
            raise ValueError("a poll needs its question")
        results = body.get("results") or {}
        if not isinstance(results, dict):
            raise ValueError("results is {answer: count}")
        results = {str(k): _int(v, "a poll count") for k, v in results.items()}
        room["polls"].append({"at": now, "question": question, "results": results, "note": "member input, not a vote"})
        log(f"Poll: {question} " + ", ".join(f"{k} {v}" for k, v in results.items()) + ". Member input, not a board vote (CIV 4926(a)(3)).")
    elif action == "admit":
        names = body.get("names")
        if names is None:
            names = [body.get("name")]
        names = [str(n or "").strip() for n in names if str(n or "").strip()]
        if not names:
            raise ValueError("admit names at least one matched owner")
        kept = closed()["admitted"] if ex["active"] else room["admitted"]
        for n in names:
            if n not in kept:
                kept.append(n)
        log(f"Admitted from the waiting room, matched to the owner roster: {', '.join(names)}. The chair decides on anyone unmatched (CIV 4925).")
    elif action == "suggest":
        if ex["active"]:
            raise ValueError("the live transcript is paused in executive session (CIV 4935); nothing from it is suggested for the minutes")
        text = str(body.get("text", "") or "").strip()
        if not text:
            raise ValueError("a suggestion needs its text")
        room["transcriptSuggestions"].append({"at": now, "text": text, "who": str(body.get("who", "") or "").strip(), "state": "suggested"})
    elif action == "suggestion_state":
        idx = _int(body.get("index"), "index")
        if idx >= len(room["transcriptSuggestions"]):
            raise KeyError(f"suggestion {idx}")
        state = _one_of(body.get("state"), SUGGESTION_STATES, "state")
        if state == "added" and ex["active"]:
            raise ValueError("add the open session's transcript lines after the board returns to open session")
        s = room["transcriptSuggestions"][idx]
        s["state"] = state
        if s["state"] == "added":
            log((f"{s['who']}: " if s.get("who") else "") + s["text"] + " (from the transcript, checked by the secretary)")
    elif action == "adjourn":
        if room["adjournedAt"]:
            raise ValueError(f"already adjourned at {room['adjournedAt']}")
        if ex["active"]:
            raise ValueError("end the executive session first")
        room["adjournedAt"] = now
        log("The open meeting was adjourned. Draft minutes go to members within 30 days (CIV 4950).", "good")

    room["updated"] = now
    line = f"{now[:10]}: {action} by {by}"
    if was_executive and ex["active"]:
        closed()["history"].append(line)       # what the board did inside the session is the executive record's
    else:
        room["history"].append(line)
    if shut:
        shut["updated"] = now
        save_executive(data_dir, shut)
    save(data_dir, room)
    return room


def with_tallies(room: dict[str, Any]) -> dict[str, Any]:
    """The open room with each motion's live tally, the present list, and the quorum, as the page reads it. It carries
    nothing from the executive record. ``openForum`` carries the limit the room runs by and where it comes from
    (``forum_limit``): ``limitMinutes`` 0 with ``limitNote`` when none is on record."""
    rule = _board()
    limit = forum_limit(room)
    forum = {**{k: v for k, v in (room.get("openForum") or {}).items() if k != "limitBy"},
             "limitMinutes": limit["minutes"], "limitSource": limit["source"], "limitNote": limit["label"]}
    return {**room, "motions": [{**m, "tally": tally(m, room, rule)} for m in room.get("motions", [])], "present": present(room),
            "quorum": quorum(list(room.get("directors", [])), rule), "openForum": forum}


def executive_view(room: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """The executive record with each motion's tally, for the private view only (P3)."""
    return {**record, "motions": [{**m, "tally": tally(m, room)} for m in record.get("motions", [])]}


# -- the one-time check of room files written before the executive record was kept apart -------------------------------

def _windows(room: dict[str, Any]) -> list[tuple[str, str]]:
    """The executive windows a room file shows: its kept sessions, or the start and end lines its log holds (an older
    file); a window still open runs to the end of the log."""
    sessions = [(str(s.get("startedAt") or ""), str(s.get("endedAt") or "")) for s in (room.get("executive") or {}).get("sessions") or []]
    if sessions:
        return [(a, b or "9999") for a, b in sessions if a]
    out: list[tuple[str, str]] = []
    start = ""
    for entry in room.get("log") or []:
        title, at = str(entry.get("title") or ""), str(entry.get("at") or "")
        if title.startswith(ADJOURNED_TO) and not start:
            start = at
        elif RETURNED in title and start:
            out.append((start, at))
            start = ""
    if start:
        out.append((start, "9999"))
    return out


def check_executive(data_dir: Path, day: str) -> dict[str, Any]:
    """How many of a room file's open entries fall inside an executive window (strictly after a start line and before
    its end line), by kind: log entries, motions moved or decided, polls, and transcript suggestions (admissions carry
    no time, so they are not counted). Counts only, never the text: the file is the association's record, and a person
    decides what to do with it; this rewrites nothing. ``found`` is False when there is no room file for ``day``."""
    path = _path(data_dir, day)
    if not path.is_file():
        return {"date": _day(day), "found": False, "windows": 0, "log": 0, "motions": 0, "polls": 0, "suggestions": 0, "total": 0}
    room = json.loads(path.read_text(encoding="utf-8"))
    windows = _windows(room)

    def inside(at: Any) -> bool:
        at = str(at or "")
        return bool(at) and any(a < at < b for a, b in windows)

    def boundary(entry: dict[str, Any]) -> bool:
        title = str(entry.get("title") or "")
        return title.startswith(ADJOURNED_TO) or RETURNED in title

    counts = {
        "log": sum(1 for e in room.get("log") or [] if inside(e.get("at")) and not boundary(e)),
        "motions": sum(1 for m in room.get("motions") or [] if inside(m.get("movedAt")) or inside(m.get("decidedAt"))),
        "polls": sum(1 for p in room.get("polls") or [] if inside(p.get("at"))),
        "suggestions": sum(1 for s in room.get("transcriptSuggestions") or [] if inside(s.get("at"))),
    }
    return {"date": _day(day), "found": True, "windows": len(windows), **counts, "total": sum(counts.values())}


def check_all(data_dir: Path) -> list[dict[str, Any]]:
    """``check_executive`` for every room file under ``data/meetings`` (the executive records themselves are skipped)."""
    folder = Path(data_dir) / STORE
    days = sorted(m.group(1) for p in folder.glob("room-*.json")
                  if (m := re.fullmatch(r"room-(\d{4}-\d{2}-\d{2})\.json", p.name)))
    return [check_executive(data_dir, d) for d in days]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "item"


def main(argv: list[str] | None = None) -> int:
    """``python -m jason.tasks.meeting_room --check-executive DATE`` (or ``all``): the counts, never the text."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m jason.tasks.meeting_room")
    parser.add_argument("--check-executive", metavar="DATE", required=True,
                        help="count the open room file's entries inside an executive window (YYYY-MM-DD, or all)")
    args = parser.parse_args(argv)
    from jason.config import apply_temp_dir_or_exit, data_dir

    apply_temp_dir_or_exit()

    root = Path(data_dir())
    rows = check_all(root) if args.check_executive == "all" else [check_executive(root, args.check_executive)]
    if not rows:
        print("no room files under data/meetings")
    for r in rows:
        if not r["found"]:
            print(f"{r['date']}: no room file")
            continue
        print(f"{r['date']}: {r['windows']} executive window(s); inside them {r['log']} log entr{'y' if r['log'] == 1 else 'ies'}, "
              f"{r['motions']} motion(s), {r['polls']} poll(s), {r['suggestions']} suggestion(s); total {r['total']}")
    return 0


__all__ = ["ACTIONS", "ATTENDANCE", "EXECUTIVE_SESSION", "IDENTIFY_FIRST", "MODES", "NAME_SUBJECT", "NOT_ON_FILE", "NO_FORUM_LIMIT",
           "OFF_AGENDA_PATHS", "OPEN_SESSION", "PRESENTERS", "RETURNED", "THRESHOLDS", "VIEWS", "VOTES", "board_rules", "check_all",
           "check_executive", "empty", "empty_executive", "executive_path", "executive_view", "forum_limit", "forum_rule", "load",
           "load_executive", "matters_of", "needed", "present", "quorum", "save",
           "save_executive", "tally", "update", "with_tallies"]


if __name__ == "__main__":
    raise SystemExit(main())
