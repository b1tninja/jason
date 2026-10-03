"""The meeting room: the live record of one board meeting as the chair runs it and jason keeps the minutes' trail.

One meeting is one file, ``data/meetings/room-<date>.json``: which item is on the stage, who presents and in which
view and Zoom mode, each director's attendance, the call to order, open forum, each motion with its mover, second,
recusals, threshold, roll-call votes and result, the timestamped log the minutes draft reads, the executive session,
polls (member input, never a vote), who was admitted, and the transcript lines suggested for the minutes.

jason records; it decides nothing. A motion needs two different directors and a quorum of those present. A recused
director counts toward the quorum and not toward the vote (Corp. Code 7233; CIV 5350). A majority of the directors
present carries a motion (Corp. Code 7211), so it must carry without the recused director's vote; an off-agenda
emergency item needs two-thirds of the directors present, or every one of them when fewer than two-thirds of the board
is present (CIV 4930(d)(2)). A topic not on the agenda may take only the CIV 4930 paths. A
decided motion is also written to ``jason.tasks.decisions`` so the minutes draft quotes it.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

STORE = "meetings"

PRESENTERS = ("jason", "chair")
VIEWS = ("host", "shared")
MODES = ("co-host", "host", "portal")
ATTENDANCE = ("present", "absent", "remote")
THRESHOLDS = ("majority", "two-thirds")
VOTES = ("aye", "no", "abstain")
RESULTS = ("carried", "failed", "")
SUGGESTION_STATES = ("suggested", "added", "dismissed")

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


def empty(day: str) -> dict[str, Any]:
    return {"date": _day(day), "directors": [], "current": 0, "presenter": "jason", "view": "host", "mode": "co-host",
            "attendance": {}, "calledToOrder": "", "openForum": {"count": 0, "limitMinutes": 3}, "motions": [], "log": [],
            "executive": {"active": False, "startedAt": "", "endedAt": "", "note": ""}, "polls": [], "admitted": [],
            "transcriptSuggestions": [], "adjournedAt": "", "created": "", "updated": "", "history": []}


def load(data_dir: Path, day: str) -> dict[str, Any]:
    """The room record for ``day``, or an empty one when the meeting has not started."""
    path = _path(data_dir, day)
    if not path.is_file():
        return empty(day)
    return {**empty(day), **json.loads(path.read_text(encoding="utf-8"))}


def save(data_dir: Path, room: dict[str, Any]) -> Path:
    path = _path(data_dir, room["date"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(room, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


# -- rules ------------------------------------------------------------------------------------------------------------

def present(room: dict[str, Any]) -> list[str]:
    """The directors in the meeting, in the room or remote, in roster order."""
    att = room.get("attendance", {})
    names = list(room.get("directors", [])) + [n for n in att if n not in room.get("directors", [])]
    return [n for n in names if att.get(n) in ("present", "remote")]


def quorum(directors: list[str]) -> int:
    """Directors needed for a quorum: the profile's board rule when it has one, else a majority of the directors."""
    count = len(directors)
    try:
        from jason.community import community

        rule = community().board()
    except Exception:
        rule = None
    if rule is not None and count:
        try:
            return int(rule.quorum(count))
        except Exception:
            pass
    return count // 2 + 1 if count else 0


def needed(present_count: int, threshold: str, seats: int) -> int:
    """Ayes a motion needs, counted against the directors present (Corp. Code 7211): a majority of them; or for two-thirds
    (CIV 4930(d)(2)) two-thirds of them, or every one of them when fewer than two-thirds of the board is present. A recused
    director is present for this count and simply casts no vote (Corp. Code 7233), so the motion must carry without them."""
    if present_count <= 0:
        return 0
    if threshold == "two-thirds":
        enough_of_board = seats <= 0 or present_count >= math.ceil(2 * seats / 3)
        return math.ceil(2 * present_count / 3) if enough_of_board else present_count
    return present_count // 2 + 1


def tally(motion: dict[str, Any], room: dict[str, Any]) -> dict[str, Any]:
    """The roll call as it stands: counts, who may vote, what it needs, and whether it carries once every voter has answered."""
    here = present(room)
    recused = [n for n in motion.get("recused", []) if n in here]
    voters = [n for n in here if n not in recused]
    votes = motion.get("votes", {})
    counts = {v: sum(1 for n in voters if votes.get(n) == v) for v in VOTES}
    need = needed(len(here), motion.get("threshold", "majority"), len(room.get("directors", [])))
    answered = all(votes.get(n) in VOTES for n in voters) and bool(voters)
    state = "open" if not answered else ("carries" if counts["aye"] >= need else "fails")
    line = f"Yes {counts['aye']} · No {counts['no']} · Abstain {counts['abstain']} · Recused {len(recused)}. Needs {need} yes. " + \
           {"open": "Vote open.", "carries": "Carries.", "fails": "Fails."}[state]
    return {"aye": counts["aye"], "no": counts["no"], "abstain": counts["abstain"], "recused": len(recused), "recusedNames": recused,
            "voters": voters, "needs": need, "answered": answered, "state": state, "line": line}


# -- writes -----------------------------------------------------------------------------------------------------------

def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "meeting-room", timeout=60, purpose=f"meeting room: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _log(room: dict[str, Any], title: str, by: str, tone: str = "neutral") -> None:
    room["log"].append({"at": _now(), "title": title, "tone": tone, "by": by})


def _one_of(value: Any, choices: tuple[str, ...], what: str) -> str:
    v = str(value or "").strip()
    if v not in choices:
        raise ValueError(f"{what} is one of {', '.join(c or '(empty)' for c in choices)}")
    return v


def _motion(room: dict[str, Any], motion_id: Any) -> dict[str, Any]:
    found = next((m for m in room["motions"] if m["id"] == str(motion_id or "")), None)
    if found is None:
        raise KeyError(f"motion {motion_id}")
    return found


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


@_store_lock
def update(data_dir: Path, day: str, body: dict[str, Any], by: str, *, directors: list[str] | tuple[str, ...] = ()) -> dict[str, Any]:
    """Apply one named ``action`` from ``body`` to the room for ``day``, recorded as ``by``'s act. Anything that is not
    one of ``ACTIONS``, or breaks a rule above, is refused with ValueError; an unknown motion is a KeyError."""
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

    if action == "call_to_order":
        if room["calledToOrder"]:
            raise ValueError(f"already called to order at {room['calledToOrder']}")
        here = present(room)
        q = quorum(room["directors"])
        room["calledToOrder"] = now
        absent = [n for n in room["directors"] if n not in here]
        roster = f"Present: {', '.join(here) or 'none recorded'}." + (f" Absent: {', '.join(absent)}." if absent else "")
        has_quorum = len(here) >= q and q > 0
        _log(room, f"Called to order by {str(body.get('chair', '') or 'the chair').strip()}. {roster} "
             f"{len(here)} of {len(room['directors']) or '?'} directors present; a quorum is {q}. "
             + ("A quorum was present." if has_quorum else "No quorum was present; the board cannot act."), by, "good" if has_quorum else "warn")
    elif action == "go_to":
        idx = _int(body.get("item"), "item")
        room["current"] = idx
        title = str(body.get("title", "") or "").strip()
        if title:
            _log(room, f"Item opened: {title}", by)
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
            forum["limitMinutes"] = _int(body["limitMinutes"], "limitMinutes", 1)
        if body.get("close"):
            n = forum["count"]
            _log(room, f"Open forum: {n} member{'s' if n != 1 else ''} spoke, {forum['limitMinutes']} minutes each (CIV 4925).", by)
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
        recused = [_director(room, n, "recused") for n in (body.get("recused") or [])]
        if mover in recused or second in recused:
            raise ValueError("a recused director neither moves nor seconds")
        motion = {"id": f"m{len(room['motions']) + 1}", "itemId": str(body.get("itemId", "") or ""), "title": str(body.get("title", "") or "").strip(),
                  "text": text, "mover": mover, "second": second, "recused": recused, "threshold": threshold, "votes": {}, "result": "",
                  "decidedAt": "", "movedAt": now}
        room["motions"].append(motion)
        _log(room, f"Motion by {mover}, seconded by {second}: {text}" + (f" {', '.join(recused)} recused." if recused else ""), by)
    elif action == "vote":
        motion = _motion(room, body.get("motion"))
        if motion["result"]:
            raise ValueError("the vote on that motion is recorded; a new motion is a new vote")
        name = _director(room, body.get("name"), "vote")
        if name in motion["recused"]:
            raise ValueError(f"{name} is recused from this motion and does not vote")
        if name not in present(room):
            raise ValueError(f"{name} is not present")
        motion["votes"][name] = _one_of(body.get("vote"), VOTES, "vote")
    elif action == "decide":
        motion = _motion(room, body.get("motion"))
        if motion["result"]:
            raise ValueError("already decided")
        t = tally(motion, room)
        if not t["answered"]:
            raise ValueError("roll call by name: every director present and not recused answers aye, no, or abstain first")
        motion["result"] = "carried" if t["state"] == "carries" else "failed"
        motion["decidedAt"] = now
        motion["tally"] = {k: t[k] for k in ("aye", "no", "abstain", "recused", "needs")}
        roll = ", ".join(f"{n} {motion['votes'][n]}" for n in t["voters"])
        _log(room, f"Roll call: {roll}. {motion['result'].capitalize()}, {t['aye']}–{t['no']}–{t['abstain']}"
             + (f", {', '.join(t['recusedNames'])} recused" if t["recusedNames"] else "") + f" ({motion['threshold']}, {t['needs']} needed).",
             by, "good" if motion["result"] == "carried" else "warn")
        from jason.tasks import decisions

        votes = dict(motion["votes"])
        for n in room["directors"]:
            if n not in votes and n not in motion["recused"]:
                votes[n] = "absent"
        decisions.record(data_dir, room["date"], motion["title"] or motion["text"][:60], motion["text"], item=motion["itemId"], session="open session",
                         mover=motion["mover"], second=motion["second"], votes=votes,
                         outcome="approved" if motion["result"] == "carried" else "denied", by=by,
                         notes=(f"Recused: {', '.join(motion['recused'])}. " if motion["recused"] else "") + f"Threshold {motion['threshold']}; {t['line']}")
    elif action == "off_agenda":
        path = str(body.get("path", "") or "").strip()
        if path not in OFF_AGENDA_PATHS:
            raise ValueError(f"a topic not on the agenda takes one of the CIV 4930 paths: {', '.join(OFF_AGENDA_PATHS)}")
        topic = str(body.get("topic", "") or "").strip()
        _log(room, (f"Not on the posted agenda: {topic}. " if topic else "A topic not on the posted agenda was raised. ")
             + OFF_AGENDA_PATHS[path] + (" " + IDENTIFY_FIRST if path.startswith("d") else ""), by, "warn")
    elif action == "executive_start":
        ex = room["executive"]
        if ex["active"]:
            raise ValueError("already in executive session")
        ex.update(active=True, startedAt=now, endedAt="", note=str(body.get("note", "") or "").strip())
        _log(room, "The board adjourned to executive session" + (f" to discuss {ex['note']}" if ex["note"] else "")
             + " (CIV 4935). Members left the open session. The host pauses the recording and the live transcript; jason does not control them from here.", by, "warn")
    elif action == "executive_end":
        ex = room["executive"]
        if not ex["active"]:
            raise ValueError("not in executive session")
        ex.update(active=False, endedAt=now)
        _log(room, "The board returned to open session. The host resumes the recording and the live transcript; jason does not control them from here. "
             "Executive session matters are noted generally in the open minutes (CIV 4935(e)).", by)
    elif action == "poll":
        question = str(body.get("question", "") or "").strip()
        if not question:
            raise ValueError("a poll needs its question")
        results = body.get("results") or {}
        if not isinstance(results, dict):
            raise ValueError("results is {answer: count}")
        results = {str(k): _int(v, "a poll count") for k, v in results.items()}
        room["polls"].append({"at": now, "question": question, "results": results, "note": "member input, not a vote"})
        _log(room, f"Poll: {question} " + ", ".join(f"{k} {v}" for k, v in results.items()) + ". Member input, not a board vote (CIV 4926(a)(3)).", by)
    elif action == "admit":
        names = body.get("names")
        if names is None:
            names = [body.get("name")]
        names = [str(n or "").strip() for n in names if str(n or "").strip()]
        if not names:
            raise ValueError("admit names at least one matched owner")
        for n in names:
            if n not in room["admitted"]:
                room["admitted"].append(n)
        _log(room, f"Admitted from the waiting room, matched to the owner roster: {', '.join(names)}. The chair decides on anyone unmatched (CIV 4925).", by)
    elif action == "suggest":
        text = str(body.get("text", "") or "").strip()
        if not text:
            raise ValueError("a suggestion needs its text")
        room["transcriptSuggestions"].append({"at": now, "text": text, "who": str(body.get("who", "") or "").strip(), "state": "suggested"})
    elif action == "suggestion_state":
        idx = _int(body.get("index"), "index")
        if idx >= len(room["transcriptSuggestions"]):
            raise KeyError(f"suggestion {idx}")
        s = room["transcriptSuggestions"][idx]
        s["state"] = _one_of(body.get("state"), SUGGESTION_STATES, "state")
        if s["state"] == "added":
            _log(room, (f"{s['who']}: " if s.get("who") else "") + s["text"] + " (from the transcript, checked by the secretary)", by)
    elif action == "adjourn":
        if room["adjournedAt"]:
            raise ValueError(f"already adjourned at {room['adjournedAt']}")
        if room["executive"]["active"]:
            raise ValueError("end the executive session first")
        room["adjournedAt"] = now
        _log(room, "The open meeting was adjourned. Draft minutes go to members within 30 days (CIV 4950).", by, "good")

    room["updated"] = now
    room["history"].append(f"{now[:10]}: {action} by {by}")
    save(data_dir, room)
    return room


def with_tallies(room: dict[str, Any]) -> dict[str, Any]:
    """The room with each motion's live tally, the present list, and the quorum, as the page reads it."""
    return {**room, "motions": [{**m, "tally": tally(m, room)} for m in room.get("motions", [])], "present": present(room),
            "quorum": quorum(list(room.get("directors", [])))}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "item"


__all__ = ["ACTIONS", "ATTENDANCE", "IDENTIFY_FIRST", "MODES", "OFF_AGENDA_PATHS", "PRESENTERS", "THRESHOLDS", "VIEWS", "VOTES",
           "empty", "load", "needed", "present", "quorum", "save", "tally", "update", "with_tallies"]
