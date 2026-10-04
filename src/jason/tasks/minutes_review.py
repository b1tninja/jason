"""The Secretary's review of a minutes draft: its blanks as a form, the privacy flags beside the lines they concern.

``jason board --minutes DATE`` writes ``data/board/minutes-draft-<date>.md`` (``jason.tasks.minutes_draft``) with
``UNKNOWN`` wherever the record does not show what a section asks for, and the minutes template
(``jason.community.minutes_template``) writes each prompt in braces. ``parse`` turns every such blank into a field
with the line it sits in; ``privacy_flags`` marks each line where a member's name sits beside a delinquency, fine,
hearing, lien, or collections word (``jason.tasks.minutes_privacy``: an executive session matter the open minutes note
only generally, Civil Code 4935(e)); ``fill`` puts the Secretary's answers in; ``save_review`` keeps the answers in
``minutes-draft-<date>.review.json`` and writes the filled copy to ``minutes-<date>.md``. The draft is never edited:
a redraft replaces it, and the saved answers are filled into the new one. The Secretary approves the text; the board
adopts the minutes at the next meeting (CIV 4950).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.minutes_template import UNKNOWN

try:  # the privacy scanner's subject words and matcher; the regex below stands in when it cannot load
    from jason.tasks.minutes_privacy import SUBJECTS, hits_in
except Exception:  # pragma: no cover - a missing optional dependency
    hits_in = None  # type: ignore[assignment]
    # from jason.tasks.minutes_privacy.SUBJECTS
    SUBJECTS = re.compile(r"\bdelinquen\w*|\boutstanding balance|\bbalance (?:of|owed)|\bowe[sd]?\b|\bpayment plan|\blate fees?|\bfined?\b|"
                          r"\bviolation|\bdisciplin\w*|\bhearing\b|\blien\b|\bcollections?\b|\bforeclos\w*|\bsmall claims", re.I)

BOARD = Path("board")
DRAFT = re.compile(r"^minutes-draft-(\d{4}-\d{2}-\d{2})\.md$")
# A blank: the draft's UNKNOWN marker (not the quoted one in the preamble that explains it), or a template instruction
# in {braces} or [brackets] (never a Markdown link's [text](url), and never a bare [x] checkbox).
_BLANK = re.compile(r'(?<!")' + re.escape(UNKNOWN) + r'(?!")|\{[^{}\n]+\}|\[(?![xX ]?\])[^\[\]\n]{3,}\](?!\()')
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
# A name a conservative reader would take for a person's: two or three capitalized words, none of them a word the
# minutes use for something else. Used only when PayHOA's member list is not on disk.
_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+(?:[A-Z]\.\s+)?[A-Z][a-z]+){1,2})\b")
_NOT_NAMES = {"board", "president", "vice", "secretary", "treasurer", "director", "directors", "executive", "session", "civil", "code",
              "open", "forum", "call", "order", "roll", "motion", "moved", "seconded", "result", "approval", "prior", "minutes", "next",
              "meeting", "adjournment", "recorded", "attendance", "quorum", "business", "association", "homeowners", "the", "zoom",
              "draft", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
              "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "payment", "plan", "small",
              "claims", "late", "fees", "collections", "lien", "notice", "hearing", "fine", "unit", "street", "drive", "court", "avenue"}


@dataclass
class Blank:
    id: str                    # "b<n>" in reading order
    section: str               # the nearest heading above
    context: str               # the line the blank sits in
    marker: str                # the text replaced (UNKNOWN or the braced instruction)
    value: str = ""


@dataclass
class Section:
    heading: str
    level: int
    body: str
    blanks: list[str] = field(default_factory=list)   # blank ids in this section


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def draft_path(data_dir: Path, day: str) -> Path:
    return Path(data_dir) / BOARD / f"minutes-draft-{day}.md"


def review_path(data_dir: Path, day: str) -> Path:
    return Path(data_dir) / BOARD / f"minutes-draft-{day}.review.json"


def minutes_path(data_dir: Path, day: str) -> Path:
    return Path(data_dir) / BOARD / f"minutes-{day}.md"


def relative(path: Path) -> str:
    """A file of this module (``data/board/<name>``) as the console names it, under the data folder
    (``board/<name>``): never an absolute path."""
    return f"{BOARD.as_posix()}/{Path(path).name}"


def minutes_file(data_dir: Path, day: str) -> str:
    """The filled copy's path under the data folder (``board/minutes-<date>.md``) when it is on disk, else ""."""
    path = minutes_path(data_dir, day)
    return relative(path) if path.is_file() else ""


def transcript_file(data_dir: Path, day: str) -> str:
    """The Zoom transcript the draft of ``day`` was read from, as a path under the data folder
    (``zoom/meetings/<folder>/transcript.txt``): the board meeting of that day in the Zoom index, the longest when
    there are several (``jason.tasks.minutes_draft.meeting_record``'s choice). "" when the index lists none; the file
    itself may be missing."""
    from jason.tasks.zoom import ZOOM_DIR, load_index

    try:
        rows = load_index(data_dir).get("meetings", [])
    except (OSError, ValueError, AttributeError):
        return ""
    rows = [m for m in rows if isinstance(m, dict) and m.get("date") == day and m.get("folder")
            and "board" in str(m.get("kind", ""))]
    if not rows:
        return ""
    row = max(rows, key=lambda m: m.get("duration") or 0)
    folder = str(row["folder"]).replace("\\", "/").strip("/")
    return f"{Path(ZOOM_DIR).as_posix()}/{folder}/transcript.txt"


def list_drafts(data_dir: Path) -> list[dict[str, Any]]:
    """The minutes drafts under data/board, newest first, each with whether a review and a filled copy exist. Files
    are named by their paths under the data folder (``board/...``), never absolute."""
    folder = Path(data_dir) / BOARD
    out = []
    for path in folder.glob("minutes-draft-*.md") if folder.is_dir() else []:
        m = DRAFT.match(path.name)
        if not m:
            continue
        day = m.group(1)
        text = path.read_text(encoding="utf-8", errors="replace")
        review = load_review(data_dir, day)
        blanks = parse(text)["blanks"]
        out.append({"date": day, "file": relative(path), "blanks": len(blanks),
                    "filled": sum(1 for b in blanks if review.get("values", {}).get(b.id, "").strip()),
                    "reviewed": bool(review), "reviewedBy": review.get("by", ""), "savedAt": review.get("savedAt", ""),
                    "minutesFile": minutes_file(data_dir, day),
                    "privacyFlags": len(privacy_flags(text, names=_names(data_dir)))})
    return sorted(out, key=lambda r: r["date"], reverse=True)


def parse(text: str) -> dict[str, Any]:
    """The draft's sections (heading, body) and its blanks: every UNKNOWN marker or braced instruction, as a field."""
    sections: list[Section] = []
    blanks: list[Blank] = []
    current = Section("", 0, "")
    body: list[str] = []

    def close() -> None:
        current.body = "\n".join(body).strip()
        if current.heading or current.body:
            sections.append(current)

    for line in (text or "").splitlines():
        h = _HEADING.match(line)
        if h:
            close()
            current, body = Section(h.group(2), len(h.group(1)), ""), []
            continue
        body.append(line)
        for m in _BLANK.finditer(line):
            b = Blank(id=f"b{len(blanks) + 1}", section=current.heading, context=line.strip(), marker=m.group(0))
            blanks.append(b)
            current.blanks.append(b.id)
    close()
    return {"sections": sections, "blanks": blanks}


def _names(data_dir: Path | None) -> list[str] | None:
    """PayHOA's member names when the scanner and its store are here; None means the conservative name reader."""
    if data_dir is None:
        return None
    try:
        from jason.tasks.minutes_privacy import member_names

        return member_names(Path(data_dir)) or None
    except Exception:
        return None


def privacy_flags(text: str, *, names: list[str] | None = None) -> list[dict[str, Any]]:
    """Each line where a person's name sits beside a delinquency, balance, payment plan, fine, violation, hearing, lien,
    collections, or foreclosure word: {line, text, why}. With ``names`` (PayHOA's members) the scanner's matcher
    decides; without, any capitalized two- or three-word name counts, so a flag is a lead for the Secretary, never a
    finding."""
    out: list[dict[str, Any]] = []
    for n, line in enumerate((text or "").splitlines(), 1):
        if not line.strip() or not SUBJECTS.search(line):
            continue
        subject = SUBJECTS.search(line).group(0)  # type: ignore[union-attr]
        if names and hits_in is not None:
            hits = hits_in(line, names)
            if hits:
                out.append({"line": n, "text": line.strip(), "member": hits[0]["member"], "replacement": hits[0]["replacement"],
                            "why": f"\"{hits[0]['member']}\" is a member's name beside \"{subject}\": an executive session matter the open minutes note only generally (CIV 4935(e))"})
            continue
        positions = [m.start() for m in SUBJECTS.finditer(line)]
        for m in _NAME.finditer(line):
            words = [w.lower().rstrip(".") for w in m.group(1).split()]
            if any(w in _NOT_NAMES for w in words) or not any(abs(m.start() - p) <= 120 for p in positions):
                continue
            out.append({"line": n, "text": line.strip(), "member": m.group(1), "replacement": "",
                        "why": f"\"{m.group(1)}\" reads as a person's name beside \"{subject}\": if a member, an executive session matter the open minutes note only generally (CIV 4935(e))"})
            break
    return out


def fill(text: str, values: dict[str, str]) -> str:
    """The text with each blank replaced by its value; a blank with no value stays as it was."""
    ids = iter(f"b{n}" for n in range(1, 10**6))

    def sub(m: re.Match[str]) -> str:
        v = values.get(next(ids), "")
        return v if v and v.strip() else m.group(0)

    # The same walk as parse: headings are never blanks, so the ids line up.
    return "\n".join(line if _HEADING.match(line) else _BLANK.sub(sub, line) for line in (text or "").splitlines())


def load_review(data_dir: Path, day: str) -> dict[str, Any]:
    path = review_path(data_dir, day)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "board-minutes-review", timeout=60, purpose=f"minutes review: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def save_review(data_dir: Path, day: str, values: dict[str, str], by: str) -> dict[str, Any]:
    """Keep the Secretary's answers and write the filled copy. Refuses an unknown blank id, an empty ``by``, or a date
    with no draft. The draft itself is never changed."""
    day = str(day).strip()
    date.fromisoformat(day)
    by = str(by or "").strip()
    if not by:
        raise ValueError("the review needs who made it (by)")
    src = draft_path(data_dir, day)
    if not src.is_file():
        raise KeyError(day)
    text = src.read_text(encoding="utf-8")
    known = {b.id for b in parse(text)["blanks"]}
    clean = {str(k): str(v) for k, v in (values or {}).items() if v is not None}
    unknown = sorted(set(clean) - known)
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a blank in the {day} draft")
    previous = load_review(data_dir, day)
    now = _now()
    merged = {**previous.get("values", {}), **clean}
    changed = sorted(k for k in clean if previous.get("values", {}).get(k, "") != clean[k])
    history = list(previous.get("history", []))
    history.append(f"{now[:10]}: {by} filled {len(changed)} blank(s)" + (f" ({', '.join(changed)})" if changed else ""))
    review = {"date": day, "values": merged, "by": by, "savedAt": now, "history": history, "draft": relative(src)}
    review_path(data_dir, day).write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
    filled = fill(text, merged)
    out = minutes_path(data_dir, day)
    out.write_text(filled, encoding="utf-8")
    review["minutesFile"] = relative(out)
    review["open"] = len(known) - sum(1 for k in known if merged.get(k, "").strip())
    return review


def encode_blank(b: Blank) -> dict[str, Any]:
    return asdict(b)


def encode_section(s: Section) -> dict[str, Any]:
    return asdict(s)


__all__ = ["Blank", "Section", "draft_path", "encode_blank", "encode_section", "fill", "list_drafts", "load_review",
           "minutes_file", "minutes_path", "parse", "privacy_flags", "relative", "review_path", "save_review",
           "transcript_file"]
