"""Questions for a person: what jason could not decide while reading a document, parked with its evidence.

Every step that reads a document can be unsure: which kind it is, whether an amendment took effect, what an OCR'd word
says, whether the working copy's difference is a correction or a slip. Instead of guessing, the step asks. An ``Ask``
names its kind, its subject (a document and section), the question, the choices with jason's suggestion, and the
evidence. A person answers; the answer becomes a durable record the next run applies (a transcription becomes a
``living.Correction``; a classification, a library row). An ask is generated again on every run, keyed by what it is
about, so an answered one stays answered and a new one is added; one that no run produces any more is stale.

``likely`` marks a suggestion strong enough to accept in a batch after a look (an OCR slip where the working copy has
a dictionary word and the extract has none). Nothing is accepted without a person's word, and the person is named.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class AskKind(Enum):
    CLASSIFY = "classify"                    # which kind of document this is
    STANDING = "standing"                    # whether an instrument took effect (signed, adopted, recorded)
    OCR_READING = "ocr reading"              # what the page says where the extract and the working copy differ
    DRIFT = "drift"                          # the working copy differs from the current text in an amended section
    BEFORE_DIFFERS = "before differs"        # an amendment's before words are not the document's
    READINGS_DIFFER = "readings differ"      # two copies of one instrument disagree
    ORPHANED_NOTE = "orphaned note"          # an annotation whose words are gone
    HELD_SOURCE = "held source"              # a source not read (changed since review, or never fetched)
    SECTION_KIND = "section kind"            # what a section of a document is: a rule, a copy, a policy, guidance
                                             # (jason.community.manual); the answer is read by the next run


class AskStatus(Enum):
    OPEN = "open"
    ANSWERED = "answered"
    APPLIED = "applied"                      # the answer became a record a run uses
    DISMISSED = "dismissed"
    STALE = "stale"                          # no run asks it any more (the cause went away)


@dataclass
class Ask:
    id: str
    kind: AskKind
    subject: str                             # "ccrs#4.15(a)", "library:Governing Documents/x.pdf"
    question: str
    choices: tuple[str, ...] = ()
    suggestion: str = ""
    likely: bool = False                     # a suggestion strong enough to accept in a batch, after a look
    evidence: tuple[str, ...] = ()
    detail: dict = field(default_factory=dict)   # what applying the answer needs (the wrong words, the section)
    status: AskStatus = AskStatus.OPEN
    answer: str = ""
    answered_by: str = ""
    answered_at: str = ""
    applied_to: str = ""                     # the record the answer became


def ask_id(kind: AskKind, subject: str, key: str) -> str:
    """A stable id from what the ask is about, so a run regenerates the same id."""
    return hashlib.sha1(f"{kind.value}|{subject}|{key}".encode("utf-8")).hexdigest()[:10]


def store_path(data_dir: Path) -> Path:
    return Path(data_dir) / "intake" / "asks.json"


def load(data_dir: Path) -> list[Ask]:
    path = store_path(data_dir)
    if not path.is_file():
        return []
    out = []
    for r in json.loads(path.read_text(encoding="utf-8")):
        out.append(Ask(r["id"], AskKind(r["kind"]), r["subject"], r["question"], tuple(r.get("choices") or ()),
                       r.get("suggestion", ""), bool(r.get("likely")), tuple(r.get("evidence") or ()),
                       dict(r.get("detail") or {}), AskStatus(r.get("status", "open")), r.get("answer", ""),
                       r.get("answered_by", ""), r.get("answered_at", ""), r.get("applied_to", "")))
    return out


def save(data_dir: Path, asks: list[Ask]) -> Path:
    path = store_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{**asdict(a), "kind": a.kind.value, "status": a.status.value} for a in asks]
    path.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return path


def merge(old: list[Ask], new: list[Ask], *, scope: tuple[str, ...] = ()) -> list[Ask]:
    """The store after a run: a new ask is added; one already there keeps its answer and status but takes the run's
    words and evidence; an open one the run (within ``scope``, subject prefixes it covered) no longer asks is stale."""
    fresh = {a.id: a for a in new}
    out = []
    for a in old:
        if a.id in fresh:
            n = fresh.pop(a.id)
            status = AskStatus.OPEN if a.status is AskStatus.STALE else a.status
            out.append(replace(n, status=status, answer=a.answer, answered_by=a.answered_by,
                               answered_at=a.answered_at, applied_to=a.applied_to))
        elif a.status is AskStatus.OPEN and any(a.subject.startswith(s) for s in scope):
            out.append(replace(a, status=AskStatus.STALE))
        else:
            out.append(a)
    return out + list(fresh.values())


def answer(asks: list[Ask], ident: str, text: str, by: str) -> Ask:
    """Record a person's answer. ``text`` may be a choice's number (1-based) or words."""
    if not by:
        raise ValueError("an answer names who gave it")
    a = next((x for x in asks if x.id == ident), None)
    if a is None:
        raise KeyError(ident)
    if text.isdigit() and a.choices and 1 <= int(text) <= len(a.choices):
        text = a.choices[int(text) - 1]
    a.answer, a.answered_by = text, by
    a.answered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    a.status = AskStatus.DISMISSED if text.lower() in ("dismiss", "dismissed") else AskStatus.ANSWERED
    return a


__all__ = ["Ask", "AskKind", "AskStatus", "answer", "ask_id", "load", "merge", "save", "store_path"]
