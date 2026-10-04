"""Questions for a person: what jason could not decide while reading a document, parked with its evidence.

Every step that reads a document can be unsure: which kind it is, whether an amendment took effect, what an OCR'd word
says, whether the working copy's difference is a correction or a slip. Instead of guessing, the step asks. An ``Ask``
names its kind, its subject (a document and section), the question, the choices with jason's suggestion, and the
evidence. A person answers; the answer becomes a durable record the next run applies (a transcription becomes a
``living.Correction``; a classification, a library row). An ask is generated again on every run, keyed by what it is
about, so an answered one stays answered and a new one is added; one that no run produces any more is stale.

``likely`` marks a suggestion strong enough to accept in a batch after a look (an OCR slip where the working copy has
a dictionary word and the extract has none). Nothing is accepted without a person's word, and the person is named.

Onboarding adds two kinds (``jason.tasks.onboarding_session``): a ``FACT`` the checklist needs and no document holds
(the tax ID, the bank signers), and a ``MAP`` from a document to the book or Civil Code 5200 record it fills. Each
names the checklist item it ``serves``.

Three guards hold for every answer:

- **No secret is stored.** An answer that looks like a password, a PIN or code, or a long token is refused before it
  is written (``secret_reason``); the person puts it in Keeper and answers with the Keeper record's name.
- **A high-stakes answer needs a second person.** Which text is in force, whether an instrument was recorded, or a
  fact marked ``stakes`` (``high_stakes``): ``confirm`` records a second person, and apply refuses without one.
- **Every answer is signed.** Who answered and when, and who confirmed and when.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, fields, replace
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
    FACT = "fact"                            # a fact the onboarding checklist needs and no document holds
    MAP = "map"                              # which book or 5200 record a document or folder fills
    APPLICABILITY = "applicability"          # a fact a rule row's condition needs and no record on hand states
                                             # (jason.community.applicability_asks); the answer is read by the next run


# The kinds whose answer decides which words are in force, or whether an instrument took effect: a second person
# confirms before apply (``confirm``).
HIGH_STAKES = frozenset({AskKind.STANDING, AskKind.READINGS_DIFFER, AskKind.BEFORE_DIFFERS, AskKind.DRIFT})

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
    serves: str = ""                         # the onboarding checklist item it serves ("tax-id"), when one
    stakes: bool = False                     # high stakes on its own (a FACT so marked): a second person confirms
    confirmed_by: str = ""                   # the second person, for a high-stakes answer
    confirmed_at: str = ""


def high_stakes(a: Ask) -> bool:
    """Whether a second person must confirm the answer before it is applied."""
    return a.stakes or a.kind in HIGH_STAKES


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
    text = {f.name for f in fields(Ask)} - {"id", "kind", "subject", "question", "choices", "likely", "evidence",
                                            "detail", "status", "stakes"}
    for r in json.loads(path.read_text(encoding="utf-8")):
        out.append(Ask(r["id"], AskKind(r["kind"]), r["subject"], r["question"], choices=tuple(r.get("choices") or ()),
                       likely=bool(r.get("likely")), evidence=tuple(r.get("evidence") or ()),
                       detail=dict(r.get("detail") or {}), status=AskStatus(r.get("status", "open")),
                       stakes=bool(r.get("stakes")), **{k: str(r.get(k) or "") for k in text}))
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
                               answered_at=a.answered_at, applied_to=a.applied_to, confirmed_by=a.confirmed_by,
                               confirmed_at=a.confirmed_at))
        elif a.status is AskStatus.OPEN and any(a.subject.startswith(s) for s in scope):
            out.append(replace(a, status=AskStatus.STALE))
        else:
            out.append(a)
    return out + list(fresh.values())


class SecretRefused(ValueError):
    """An answer that looks like a secret: it is not stored anywhere."""


_URL = re.compile(r"https?://\S+", re.I)
_RUN = re.compile(r"[A-Za-z0-9_+=.\-]{20,}")
_HEX = re.compile(r"\b[0-9a-fA-F]{32,}\b")
_PASSWORD = re.compile(r"\b(?:pass(?:word|code|phrase)|passwd|pwd)\b\s*(?:is|:|=|-)\s*(?!(?:in|kept|stored|saved|held)\b)\S+",
                       re.I)
_CODE = re.compile(r"(?<!zip )(?<!postal )\b(?:pin|code|combination|combo|passcode)\b\s*(?:no\.?|number|#)?\s*"
                   r"(?:is|:|=|-)?\s*#?\d{3,}", re.I)
_KEY = re.compile(r"\b(?:api[ _-]?key|secret|token|otp|2fa|mfa|recovery code)s?\b\s*(?:is|:|=)\s*\S+", re.I)


def secret_reason(text: str, kind: AskKind | None = None) -> str:
    """Why ``text`` looks like a secret ("" when it does not): a password, a PIN or code given with its digits, a key
    or token given with its value, or a long token (twenty characters or more without a space, mixing letters and
    digits, or a long hex string). A link is not a token: a Drive folder is answered with its link. The words of a
    page (an OCR reading) may say "code" or "PIN" with a number, so for them only the token rule applies."""
    body = _URL.sub(" ", text or "")
    if kind is not AskKind.OCR_READING:
        if _PASSWORD.search(body):
            return "it gives a password"
        if _CODE.search(body):
            return "it gives a PIN or code with its digits"
        if _KEY.search(body):
            return "it gives a key, token, or one-time code with its value"
    if _HEX.search(body):
        return "it holds a long hex string, like a key"
    for run in _RUN.findall(body):
        digits = any(c.isdigit() for c in run)
        if digits and any(c.isupper() for c in run) and any(c.islower() for c in run):
            return "it holds a long token of mixed letters and digits"
    return ""


def answer(asks: list[Ask], ident: str, text: str, by: str) -> Ask:
    """Record a person's answer. ``text`` may be a choice's number (1-based) or words. An answer that looks like a
    secret is refused (``SecretRefused``) and nothing is written; a new answer clears an earlier confirmation."""
    if not by:
        raise ValueError("an answer names who gave it")
    a = next((x for x in asks if x.id == ident), None)
    if a is None:
        raise KeyError(ident)
    if text.isdigit() and a.choices and 1 <= int(text) <= len(a.choices):
        text = a.choices[int(text) - 1]
    why = secret_reason(text, a.kind)
    if why:
        raise SecretRefused(f"not stored: {why}. jason never keeps a secret. Put it in Keeper, then answer with the "
                            f"Keeper record's name (its title, not its value or id).")
    a.answer, a.answered_by = text, by
    a.answered_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    a.confirmed_by = a.confirmed_at = ""
    a.status = AskStatus.DISMISSED if text.lower() in ("dismiss", "dismissed") else AskStatus.ANSWERED
    return a


def confirm(asks: list[Ask], ident: str, by: str) -> Ask:
    """A second person confirms an answered question: needed before a high-stakes answer is applied. The person
    confirming is named and is not the person who answered."""
    if not by:
        raise ValueError("a confirmation names who gave it")
    a = next((x for x in asks if x.id == ident), None)
    if a is None:
        raise KeyError(ident)
    if a.status is not AskStatus.ANSWERED:
        raise ValueError(f"only an answered question is confirmed; this one is {a.status.value}")
    if by.strip().casefold() == a.answered_by.strip().casefold():
        raise ValueError(f"a second person confirms: {by} gave the answer")
    a.confirmed_by = by
    a.confirmed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return a


__all__ = ["Ask", "AskKind", "AskStatus", "HIGH_STAKES", "SecretRefused", "answer", "ask_id", "confirm", "high_stakes",
           "load", "merge", "save", "secret_reason", "store_path"]
