"""Open minutes that name a member in a matter the law keeps in executive session, and a corrected copy without it.

The board meets in executive session on a member's discipline, a member's assessment payment or payment plan, and a
foreclosure decision (Civil Code 4935(a)-(c)), and notes only the general nature of those matters in the open minutes
(4935(e)). A Zoom AI summary posted as the minutes retells them with the member's name and balance.

``scan`` reads every minutes reading's text (``data/documents/readings.json``, library and Drive) for a sentence or a
next-steps line that names a member (the names PayHOA lists, ``data/payhoa.db``) together with a confidential subject
(a delinquency, a balance owed, a payment plan, a fine, a violation, a hearing, a lien, collections, foreclosure). Each
hit gets a general replacement. ``correct`` writes a corrected copy of one meeting's minutes, every hit replaced, to
``data/board/minutes-corrected-<date>.md`` for the Secretary to review and post; the original is not changed.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

SUBJECTS = re.compile(r"\bdelinquen\w*|\boutstanding balance|\bbalance (?:of|owed)|\bowe[sd]?\b|\bpayment plan|\blate fees?|\bfined?\b|"
                      r"\bviolation|\bdisciplin\w*|\bhearing\b|\blien\b|\bcollections?\b|\bforeclos\w*|\bsmall claims", re.I)
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n\s*[●•○]\s*|\n(?=\s*[●•○])")
GENERAL = {
    "payment plan": "The board took up a member's request for an assessment payment plan in executive session (Civil Code "
                    "4935(a)); the decision is recorded in the executive session minutes.",
    "discipline": "The board took up a member discipline matter in executive session (Civil Code 4935(a)).",
    "foreclosure": "The board took up a foreclosure decision in executive session (Civil Code 4935(c)).",
    "delinquency": "The board took up a delinquent account in executive session (Civil Code 4935(a)).",
}


def member_names(data_dir: Path) -> list[str]:
    """Members' full names from PayHOA (two words or more), longest first so "Mary Ann Smith" wins over "Ann Smith"."""
    db = Path(data_dir) / "payhoa.db"
    if not db.is_file():
        return []
    with sqlite3.connect(db) as con:
        names = {n.strip() for (n,) in con.execute("select name from people") if n and len(n.split()) >= 2}
    # PayHOA keeps some names with a middle initial or last name first ("Jane Q. Public"); the minutes write them
    # "Public Jane". Each name is matched without its initials and in both orders.
    variants = set()
    for n in names:
        words = [w for w in n.split() if not re.fullmatch(r"[A-Z]\.?", w)]
        if len(words) >= 2:
            variants |= {f"{words[0]} {words[-1]}", f"{words[-1]} {words[0]}"}
    names |= variants
    # A director named in the board's role (delegated collections, the roll call) is not the subject of the matter.
    from jason.tasks.board_members import load as board

    roster = board(data_dir)
    directors = {m["name"].lower() for k in ("current", "former") for m in roster.get(k, []) if m.get("name")}
    directors |= {" ".join(reversed(d.split())) for d in directors if len(d.split()) == 2}
    return sorted((n for n in names if n.lower() not in directors), key=len, reverse=True)


def _general(sentence: str) -> str:
    s = sentence.lower()
    if re.match(r"\W*(?:notify|contact|send|call|email|tell|inform|follow up)\b", s):
        return "Notify the member of the board's decision (executive session matter)."   # a next-steps task stays a task
    if "payment plan" in s:
        return GENERAL["payment plan"]
    if "foreclos" in s:
        return GENERAL["foreclosure"]
    if re.search(r"violation|disciplin|hearing|fine", s):
        return GENERAL["discipline"]
    return GENERAL["delinquency"]


_ROLE_AFTER = re.compile(r"^\W{0,3}(?:,\s*)?(?:board\s+)?(?:president|vice[- ]president|secretary|treasurer|director|member at large|manager)\b", re.I)
_ROLE_BEFORE = re.compile(r"(?:president|vice[- ]president|secretary|treasurer|director|manager)\W{0,4}$|(?:moved|made|seconded)\s+by\s*$", re.I)


def _acting(piece: str, start: int, end: int) -> bool:
    """The name acts for the board ("motion was made by X, Board President"), not the subject of the matter."""
    return bool(_ROLE_AFTER.search(piece[end:end + 30]) or _ROLE_BEFORE.search(piece[max(0, start - 30):start]))


def hits_in(text: str, names: list[str]) -> list[dict[str, str]]:
    out = []
    for piece in _SPLIT.split(text or ""):
        piece = re.sub(r"\s+", " ", piece).strip()
        if not piece or not SUBJECTS.search(piece):
            continue
        # The member and the subject in the same breath: a name within 120 characters of the confidential word, so a roll
        # call that happens to share a paragraph with "discipline" is not a hit.
        subjects = [m.start() for m in SUBJECTS.finditer(piece)]
        named = next((n for n in names for m in re.finditer(rf"(?<!\w){re.escape(n)}(?!\w)", piece, re.I)
                      if any(abs(m.start() - s) <= 120 for s in subjects) and not _acting(piece, m.start(), m.end())), None)
        if named:
            out.append({"passage": piece, "member": named, "replacement": _general(piece)})
    return out


def scan(data_dir: Path) -> dict[str, Any]:
    from jason.tasks.library import text_for

    names = member_names(data_dir)
    store = json.loads((Path(data_dir) / "documents" / "readings.json").read_text(encoding="utf-8")).get("readings", [])
    found = []
    for r in store:
        if r.get("kind") != "minutes" or r.get("confidential"):
            continue                           # executive session minutes may name the member
        hits = hits_in(text_for(Path(data_dir), r["id"]), names)
        if hits:
            day = (r.get("fields") or {}).get("meeting_date") or r.get("period")
            found.append({"id": r["id"], "name": r.get("name"), "date": day, "hits": hits})
    return {"minutes": len([r for r in store if r.get("kind") == "minutes"]), "withNames": found}


def correct(data_dir: Path, minutes_id: str) -> Path:
    """A corrected copy of one meeting's minutes: each passage naming a member in a confidential matter replaced."""
    from jason.tasks.library import text_for

    text = text_for(Path(data_dir), minutes_id)
    names = member_names(data_dir)
    fixed = text
    for hit in hits_in(text, names):
        words = [re.escape(w) for w in hit["passage"].split()]
        pattern = re.compile(r"\s+".join(words))
        fixed = pattern.sub(hit["replacement"], fixed, count=1)
    store = json.loads((Path(data_dir) / "documents" / "readings.json").read_text(encoding="utf-8")).get("readings", [])
    row = next((r for r in store if r["id"] == minutes_id), {})
    day = (row.get("fields") or {}).get("meeting_date") or row.get("period") or "undated"
    out = Path(data_dir) / "board" / f"minutes-corrected-{day}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    note = (f"# CORRECTED DRAFT - {row.get('name', minutes_id)}\n\n_Prepared by jason for the Secretary: passages that named a "
            "member in a matter the board takes up in executive session are replaced with the general note Civil Code 4935(e) "
            "allows. The original is unchanged; the board approves the correction._\n\n")
    out.write_text(note + fixed, encoding="utf-8")
    return out


__all__ = ["correct", "hits_in", "member_names", "scan"]
