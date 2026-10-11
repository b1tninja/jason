"""Decisions: what the board did at a meeting, recorded once, where the minutes draft can read it.

One decision is one motion on one agenda item at one meeting: its text, who moved and seconded, each director's
vote, and the outcome. It is jason's own store (``data/board/decisions.json``), written by a person at or after the
meeting through the UI or a command. jason never decides: it records the board's decision in the board's words,
and the minutes draft quotes it. A roll-call vote is required for some matters (recording a lien, Civil Code 5673);
the record keeps every vote so the minutes can show it. A director who disclosed an interest and did not vote is in
``recused``, the secretary's record of that disclosure: never marked absent, never counted as a no, and never inferred
by jason.

A decision made in executive session is marked ``session="executive session"`` with its Civil Code 4935
``subject``. The minutes of a board meeting "other than an executive session" go to members (4950(a)), and "Any
matter discussed in executive session shall be generally noted in the minutes of the immediately following meeting
that is open to the entire membership" (4935(e)). So the open views (``open_only``: the minutes draft, the
meeting's page, the decisions screen outside the private view) leave an executive decision out and note it only by
its subject's general words; its motion, title, and votes are shown only in the private view.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.models.meetings import Outcome

STORE = Path("board") / "decisions.json"


class Vote(Enum):
    AYE = "aye"
    NO = "no"
    ABSTAIN = "abstain"
    ABSENT = "absent"


@dataclass
class Decision:
    id: str                                   # open session: "<meeting>--<item or slug of the motion>"; executive: "<meeting>--executive-<n>"
    meeting: str                              # ISO date
    title: str                                # the agenda item's title, or the motion's subject
    motion: str                               # the motion as made, in the board's words
    item: str = ""                            # the board item id, when there is one
    session: str = "open session"             # or "executive session"
    subject: str = ""                          # an executive decision's ExecutiveSubject value (CIV 4935(a)-(d))
    mover: str = ""
    second: str = ""
    votes: dict[str, str] = field(default_factory=dict)   # director -> Vote value
    recused: list[str] = field(default_factory=list)      # directors who disclosed an interest and did not vote
    outcome: str = ""                         # Outcome value, or "" while the vote is open
    kind: str = ""                            # "" for a main motion; "table", "continue", or "refer" (KINDS)
    by: str = ""                              # who recorded it
    notes: str = ""
    recorded: str = ""
    updated: str = ""
    history: list[str] = field(default_factory=list)


EDITABLE = ("title", "motion", "item", "session", "subject", "mover", "second", "votes", "recused", "outcome", "kind", "by", "notes")
OPEN = "open session"
EXECUTIVE = "executive session"
OUTCOMES = tuple(o.value for o in Outcome)
VOTES = tuple(v.value for v in Vote)
# A motion to table, continue, or refer is a decision of its own: carried, its outcome is its word (tabled, continued,
# referred); failed, "denied". Its id carries the kind, so it never replaces the main motion's decision on the item.
KINDS = ("", "table", "continue", "refer")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "motion"


# An executive decision's id says the meeting and a number, never the motion, the title, or the item (CIV 4935(e): the
# open records name the matter generally). Rows recorded before this keep the id they have; ``handle`` serves them
# outside the private view.
EXECUTIVE_ID = re.compile(r"^\d{4}-\d{2}-\d{2}--executive-(\d+)$")
HANDLE_KEY = Path("board") / "decisions.key"


def _handle_key(data_dir: Path) -> bytes:
    """The install's secret for ``handle``: random bytes made once and kept beside the store (``data/board/decisions.key``,
    not checked in). No other opaque id in jason is keyed (run, approval, and hearing ids are random and stored in the
    row, and an old decision's row is not rewritten), so this is the first. If the file cannot be made or read, a key
    for this one call is used: the handle then changes on every read, and never names a row."""
    path = Path(data_dir) / HANDLE_KEY
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as f:
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        key = path.read_text(encoding="utf-8").strip()
        if len(key) >= 32:
            return key.encode("ascii")
    except (OSError, UnicodeError):
        pass
    return secrets.token_bytes(32)


def handle(data_dir: Path, d: "Decision") -> str:
    """The id an open view may show for an executive decision: its own when it is already ``<meeting>--executive-<n>``,
    else ``<meeting>--held-<12 hex>``, a keyed hash (HMAC-SHA256 under the install's secret) of the stored id. The
    stored id of an old row has a slug of its motion in it; the hash cannot be reversed, nor checked by trying slugs
    without the key. Stable for a row, and it names only the meeting, which the open minutes already do."""
    if EXECUTIVE_ID.match(d.id):
        return d.id
    digest = hmac.new(_handle_key(data_dir), d.id.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{d.meeting}--held-{digest[:12]}"


def tally(votes: dict[str, str]) -> dict[str, int]:
    out = {v: 0 for v in VOTES}
    for v in votes.values():
        if v in out:
            out[v] += 1
    return out


def suggested_outcome(votes: dict[str, str]) -> str:
    """What the votes say on their face: more ayes than noes among those voting carries; the board's word stands."""
    t = tally(votes)
    if t["aye"] + t["no"] == 0:
        return ""
    return Outcome.APPROVED.value if t["aye"] > t["no"] else Outcome.DENIED.value


def _validate(changes: dict[str, Any]) -> None:
    if "votes" in changes:
        votes = changes["votes"]
        if not isinstance(votes, dict) or any(v not in VOTES for v in votes.values()):
            raise ValueError(f"votes is {{director: one of {', '.join(VOTES)}}}")
    if "recused" in changes:
        recused = changes["recused"]
        if not isinstance(recused, list) or not all(isinstance(n, str) and n.strip() for n in recused):
            raise ValueError("recused is a list of the directors who disclosed an interest and did not vote")
        voted = changes.get("votes") or {}
        both = [n for n in recused if n in voted]
        if both:
            raise ValueError(f"{', '.join(both)}: recused, so no vote (and no absence) is recorded for them")
    if "outcome" in changes and changes["outcome"] not in ("", *OUTCOMES):
        raise ValueError(f"outcome is one of {', '.join(OUTCOMES)}, or empty while the vote is open")
    if "kind" in changes and changes["kind"] not in KINDS:
        raise ValueError("kind is table, continue, or refer, or empty for a main motion")
    if "session" in changes and changes["session"] not in (OPEN, EXECUTIVE):
        raise ValueError("session is open session or executive session")
    if "subject" in changes and changes["subject"]:
        from jason.community.models.meetings import ExecutiveSubject, executive_subject

        if executive_subject(changes["subject"]) is None:
            raise ValueError(f"subject is one of {', '.join(s.value for s in ExecutiveSubject)} (CIV 4935(a)-(d))")
    if "meeting" in changes:
        date.fromisoformat(str(changes["meeting"]))


def load(data_dir: Path) -> list[Decision]:
    path = Path(data_dir) / STORE
    if not path.is_file():
        return []
    known = set(Decision.__dataclass_fields__)
    return [Decision(**{k: v for k, v in raw.items() if k in known}) for raw in json.loads(path.read_text(encoding="utf-8")).get("decisions", [])]


def save(data_dir: Path, items: list[Decision]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "decisions": [asdict(d) for d in items]}, indent=1), encoding="utf-8")
    return path


def for_meeting(data_dir: Path, day: date | str) -> list[Decision]:
    iso = day if isinstance(day, str) else day.isoformat()
    return [d for d in load(data_dir) if d.meeting == iso]


def is_executive(d: Decision) -> bool:
    """Whether the board made d in executive session."""
    return d.session == EXECUTIVE


def open_only(rows: list[Decision]) -> list[Decision]:
    """The decisions an open view shows: an executive-session decision is left out (CIV 4935(e), 4950(a))."""
    return [d for d in rows if not is_executive(d)]


def general_notes(rows: list[Decision]) -> list[str]:
    """The executive decisions among ``rows``, noted generally by their 4935 subjects and never by title or motion:
    "The board met in executive session to discuss litigation (Civil Code 4935(a))." (4935(e)). One line for all of
    them; a decision with no subject is counted, not described."""
    from jason.community.models.meetings import executive_general_note

    shut = [d for d in rows if is_executive(d)]
    if not shut:
        return []
    said = executive_general_note([d.subject for d in shut])
    return [f"The board met in executive session to discuss {said}." if said else
            "The board met in executive session; the 4935 subject of what it decided there is not named (the secretary names it)."]


def held_rows(data_dir: Path, rows: list[Decision]) -> list[dict[str, str]]:
    """What an open view may say of each executive decision among ``rows``: its ``handle``, its meeting, and its 4935
    subject (the word and the statute's general words), never the title, motion, item, votes, notes, or stored id."""
    from jason.community.models.meetings import executive_general_note, executive_subject

    out = []
    for d in rows:
        if is_executive(d):
            s = executive_subject(d.subject)
            out.append({"id": handle(data_dir, d), "meeting": d.meeting, "subject": s.value if s else "",
                        "general": executive_general_note([s]) if s else ""})
    return sorted(out, key=lambda r: (r["meeting"], r["id"]))


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "board-decisions", timeout=60, purpose=f"decisions: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _next_executive_id(items: list[Decision], meeting: str) -> str:
    """``<meeting>--executive-<n>``, n one past the highest taken for that meeting. Called under the store lock."""
    taken = [int(m.group(1)) for d in items if d.id.startswith(f"{meeting}--") and (m := EXECUTIVE_ID.match(d.id))]
    return f"{meeting}--executive-{max(taken, default=0) + 1}"


@_store_lock
def record(data_dir: Path, meeting: str, title: str, motion: str, **fields: Any) -> Decision:
    """Record a decision, or replace one already recorded for the same meeting and item (or motion)."""
    meeting = str(meeting).strip()
    date.fromisoformat(meeting)
    title, motion = title.strip(), motion.strip()
    if not title or not motion:
        raise ValueError("a decision needs the item's title and the motion as made")
    unknown = sorted(set(fields) - set(EDITABLE))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a decision field")
    _validate(fields)
    item = str(fields.get("item", "")).strip()
    kind = str(fields.get("kind", "") or "").strip()
    key = f"{meeting}--{item or slug(motion)}" + (f"--{kind}" if kind else "")
    items = load(data_dir)
    now = _now()
    found = next((d for d in items if d.id == key), None)
    if fields.get("session") == EXECUTIVE:
        # Never the motion or the item in the id. The same item (or, with none, the same motion) recorded again in
        # this session replaces its row, as an open decision does, whatever id the row has; an open row is never taken.
        found = next((d for d in items if is_executive(d) and d.meeting == meeting and d.kind == kind
                      and (d.id == key or (item and d.item == item and EXECUTIVE_ID.match(d.id)))), None)
        key = found.id if found else _next_executive_id(items, meeting)
    if found is None:
        found = Decision(id=key, meeting=meeting, title=title, motion=motion, recorded=now, history=[f"{now[:10]}: recorded"])
        items.append(found)
    else:
        found.title, found.motion = title, motion
        found.history.append(f"{now[:10]}: re-recorded")
    for k, v in fields.items():
        setattr(found, k, v)
    found.updated = now
    save(data_dir, items)
    return found


@_store_lock
def update(data_dir: Path, decision_id: str, **changes: Any) -> Decision:
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a decision field")
    _validate(changes)
    items = load(data_dir)
    found = next((d for d in items if d.id == decision_id), None)
    if found is None:
        raise KeyError(decision_id)
    now = _now()
    for k, v in changes.items():
        if getattr(found, k) != v:
            if k == "outcome":
                found.history.append(f"{now[:10]}: outcome {found.outcome or '(open)'} -> {v or '(open)'}")
            setattr(found, k, v)
    found.updated = now
    save(data_dir, items)
    return found


def as_dict(d: Decision) -> dict[str, Any]:
    return {**asdict(d), "tally": tally(d.votes), "suggested": suggested_outcome(d.votes)}
