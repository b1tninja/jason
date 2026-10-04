"""Evidence you can open: an approval item's evidence address resolved back to the record, from disk only.

An item's evidence is ``Evidence(label, address)``: ``payhoa:submission:N`` (a PayHOA request), a citation
(``CIV 4040(a)(2)``, ``decl#6.2(a)``), ``board-item:ID``, or a command (``jason owner-info --responses``). ``resolve``
answers what jason holds of it on disk, copy by copy (``sources``), and never reads PayHOA, Google, or Keeper: each
copy says when it was read, and ``refresh`` names the command that reads it again and whether that command reads a
live system.

- **A PayHOA request.** The plan's own read first: a plan that read requests live keeps what it read beside the
  approval (``approvals/<id>.evidence.json``, written with the plan), so "This plan's read" is what PayHOA said when
  the plan was made. Then "Last read from PayHOA": the latest full read of the submission, whoever made it (a plan,
  ``jason sync-request-files``, a person's refresh from the console), kept in ``payhoa-files/requests/N/submission.json``
  (``jason.tasks.submission_cache``). Then the PayHOA catalog (``jason sync-catalog``) and the request's saved files
  (``jason sync-request-files``). ``changed`` compares the plan's read with a later last read (status and answers) and
  with a catalog synced later (status), where they can be compared; null when none can.
- **A citation.** ``jason.tasks.cite.resolve``: the words recited from disk (``jason export-authorities`` for the
  statutes), never paraphrased.
- **A board item.** ``data/board/items.json``; an executive-session item's summary and notes are held back.
- **A command.** Found, with no copy: the command is what produced the evidence, and running it is the refresh.

Which reader answers is the first rule row whose matcher takes the address (``RULES``; the order is part of the rule).
An address no row takes is ``found: false, kind: "unknown"`` with the reason, never an exception.

**Refreshing one record.** A rule row may carry a ``Refresher``: a live re-read of just that record into jason's own
cache (a PayHOA request: one ``get_form_submission``, kept as its last read). ``resolve`` says so in ``refreshable``.
``refresh`` runs it for a named person under the cache's store lock, appends one line to
``evidence/refreshes.jsonl`` (who, when, what, and whether it worked; never the answers), and returns the fresh
``resolve``. It never writes to PayHOA; jason-mcp has no refresh (it stays read-only); jason-web's
``POST /api/evidence/refresh`` calls it behind the write guard.

Privacy: the snapshot on disk holds a request's answers as read (P2, like the catalog). An owner's contact details
(email, phone, mailing address) and other P2 answers are masked here, before anything leaves the server
(docs/console/security-and-privacy.md).
"""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterator

CAVEAT = "Evidence, not a finding."
SNAPSHOT_CAVEAT = "What PayHOA said when the plan was read; `jason approvals apply {approval}` reads it again."
DISK_ONLY = "Read from disk only: nothing was read live to open it."
STATUTE_CAVEAT = ("jason's copy of the statute, exported from lawlibrary; not an official restatement. Check the words "
                  "in force on the date that matters.")
MASKED_CAVEAT = ("An owner's contact details and other P2 answers are masked by the server; a person reveals one in "
                 "PayHOA itself.")


class EvidenceKind(Enum):
    PAYHOA_SUBMISSION = "payhoa_submission"
    CITATION = "citation"
    BOARD_ITEM = "board_item"
    COMMAND = "command"
    UNKNOWN = "unknown"


class SourceName(Enum):
    """The copies jason may hold of a record, by the name a reader sees."""
    PLAN_READ = "This plan's read"
    LAST_READ = "Last read from PayHOA"
    CATALOG = "PayHOA catalog"
    REQUEST_FILES = "Request files"
    STATUTES = "Statutes on disk"
    DOCUMENTS = "Documents on disk"
    BOARD_ITEMS = "Board items"


@dataclass(frozen=True)
class Refresh:
    """A command that reads a copy again: its template (``{id}``, ``{approval}``, ``{address}``), whether it reads a
    live system, and what it does. ``needs_approval``: offered only when the evidence was opened from an approval."""
    command: str
    live: bool
    what: str
    system: str = ""                           # the outside system a live command reads ("PayHOA", "Google")
    needs_approval: bool = False

    def as_dict(self, values: dict[str, str]) -> dict[str, Any]:
        return {"command": self.command.format(**values), "live": self.live, "what": self.what,
                "system": self.system if self.live else ""}


@dataclass
class Ask:
    """What a reader is given: the address and its match, the data folder, and the approval it was opened from (its
    evidence row and the plan's snapshot of the record), when one was named."""
    address: str
    match: re.Match[str] | None
    root: Path
    approval: Any = None                       # model.Approval
    evidence: Any = None                       # model.Evidence: the approval's row for this address
    snapshot: dict[str, Any] | None = None     # the plan's read of the record
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Refresher:
    """A live re-read of one record into jason's own cache: the system it reads, what a person is offered, and the
    reader ``run(client, org_id, match, root, via)``. It never writes to the system it reads."""
    system: str
    what: str
    run: Callable[[Any, int, re.Match[str], Path, str], None]

    def as_dict(self) -> dict[str, str]:
        return {"system": self.system, "what": self.what}


@dataclass(frozen=True)
class Resolver:
    """One rule row: the kind, how it takes an address, the reader (disk only), the commands that refresh it, whether
    refreshing it reads a live system, and the one-record live refresher, when the kind has one."""
    kind: EvidenceKind
    matches: Callable[[str], re.Match[str] | None]
    read: Callable[[Ask], dict[str, Any]]
    refresh: tuple[Refresh, ...] = ()
    live: bool = False
    refresher: Refresher | None = None


# --- masking --------------------------------------------------------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w-])(?:\+?1[-. ]?)?(?:\(\d{3}\)\s?|\d{3}[-. ])\d{3}[-. ]\d{4}(?![\w-])")
# a field whose name says it holds contact details; a unit's own address is the unit's, not an owner's
_CONTACT_NAME = re.compile(r"e-?mail|phone|mobile|\bcell|\bfax|mailing|postal|\bzip|(?<!unit[-_ ])(?<!unit)address",
                           re.IGNORECASE)
DOT = "•"


def _mask_email(m: re.Match[str]) -> str:
    local, _, domain = m.group(0).partition("@")
    return f"{local[:1]}{DOT * 4}@{domain}"


def mask_text(value: str) -> tuple[str, bool]:
    """``value`` with each email address (``a••••@example.com``) and phone number masked, and whether any was."""
    out = _EMAIL.sub(_mask_email, value or "")
    out = _PHONE.sub(f"({DOT * 3}) {DOT * 3}-{DOT * 4}", out)
    return out, out != (value or "")


def mask_field(name: str, value: str, p2: bool = False) -> dict[str, Any]:
    """One field as it may leave the server: a P2 field (flagged when read, or named as contact details) masked whole,
    keeping an email's first letter and domain; any other field with an email or a phone in it masked there."""
    value = "" if value is None else str(value)
    if value and (p2 or _CONTACT_NAME.search(name or "")):
        emailed, found = mask_text(value)
        return {"name": name, "value": emailed if found and _EMAIL.fullmatch(value.strip()) else DOT * 4,
                "masked": True}
    masked, found = mask_text(value)
    return {"name": name, "value": masked, "masked": found}


def _scrub(value: Any) -> Any:
    """Every string in ``value`` with emails and phone numbers masked (a label, a note, a caveat), but a recited
    ``text``: the words are quoted as stored."""
    if isinstance(value, str):
        return mask_text(value)[0]
    if isinstance(value, dict):
        return {k: v if k == "text" else _scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


# --- helpers --------------------------------------------------------------------------------------------------------------

def _mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return ""


def _when(text: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat((text or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def source(name: SourceName, *, read_at: str = "", digest: str = "", fields: list[dict[str, Any]] | None = None,
           text: str = "", citation: str = "", caveat: str = "", note: str = "") -> dict[str, Any]:
    return {"name": name.value, "readAt": read_at or "", "digest": digest or "", "fields": list(fields or ()),
            "text": text or "", "citation": citation or "", "caveat": caveat or "", "note": note or ""}


def _root(data_dir: Path | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    from jason.config import data_dir as profile_data_dir

    return profile_data_dir()


def _catalog_path(root: Path) -> Path:
    """The PayHOA catalog in ``root``: the file the settings name when it is there (``PAYHOA_CATALOG``), else
    ``payhoa.db``."""
    try:
        from jason.config import Settings

        named = Settings.load().payhoa_catalog
        if named.parent.resolve() == root.resolve():
            return named
    except Exception:  # noqa: BLE001 - settings that cannot be read leave the data folder's own name
        pass
    return root / "payhoa.db"


# --- readers --------------------------------------------------------------------------------------------------------------

def _catalog_row(path: Path, sid: int) -> dict[str, Any] | None:
    """The request's row in the catalog, read only (a missing catalog is not created)."""
    if not path.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT id, form_name, unit_id, status, created_at, synced_at FROM requests "
                               "WHERE id = ? ORDER BY synced_at DESC LIMIT 1", (sid,)).fetchone()
    except sqlite3.Error:
        return None
    return dict(row) if row is not None else None


def _json_rows(path: Path) -> list[Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(data, dict):
        data = data.get("data") or data.get("items") or []
    return data if isinstance(data, list) else []


def _latest(rows: list[Any]) -> str:
    stamps = [str(r.get("createdAt") or r.get("created_at") or "") for r in rows if isinstance(r, dict)]
    return max((s for s in stamps if s), default="")


def _files_root(root: Path) -> Path:
    """``payhoa-files`` beside the catalog: where ``sync-request-files`` keeps each request's folder."""
    return _catalog_path(root).parent / "payhoa-files"


_TAG = re.compile(r"<[^>]+>")


def _plain(value: Any) -> str:
    """A raw answer as text: a checkbox's icon as yes or no (``payhoa_forms._truthy``'s reading), HTML as its words."""
    import html

    text = "" if value is None else str(value)
    folded = text.casefold()
    if "fa-check" in folded:
        return "yes"
    if "fa-times" in folded:
        return "no"
    return " ".join(html.unescape(_TAG.sub(" ", text)).split())


def _form_for(root: Path, form_id: Any) -> tuple[dict[str, Any] | None, Any, frozenset[str]]:
    """The PayHOA form recorded with ``form_id`` (``data/payhoa/forms.json``), the profile's definition it was made
    from (``Community.owner_information``), and the profile's other P2 answers; each None or empty when unknown."""
    from jason.tasks.payhoa_forms import load_records

    try:
        wanted = int(form_id or 0)
        record = next((r for r in reversed(load_records(root)) if wanted and int(r.get("formId") or 0) == wanted),
                      None)
    except (OSError, ValueError, TypeError):
        record = None
    if record is None:
        return None, None, frozenset()
    try:
        from jason.approvals.kinds.owner_info import private_answers
        from jason.community import community
        from jason.tasks.owner_info_apply import owner_information

        active = community()
        form = getattr(owner_information(active), "OWNER_INFO", None)
        private = private_answers(active)
    except Exception:  # noqa: BLE001 - a profile that cannot be read leaves the raw answers, masked by name
        return record, None, frozenset()
    key = getattr(getattr(form, "key", None), "value", None)
    return record, (form if form is not None and key == record.get("key") else None), private


def _last_read_answers(cached: dict[str, Any], root: Path
                       ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, dict[str, Any] | None]:
    """The answers of a kept read as masked fields by question title, and the answers by field when the form's
    definition reads them (as the plan's snapshot does, so their digests compare); else the raw answers by their
    labels, with None. Last, the recorded form, when there is one."""
    from jason.approvals.kinds.owner_info import answer_fields, is_p2
    from jason.tasks.payhoa_forms import submission_answers
    from jason.tasks.submission_cache import body

    sub = body(cached.get("submission"))
    record, form, private = _form_for(root, cached.get("formId") or sub.get("formId"))
    questions = (record or {}).get("questions") or {}
    if form is not None and questions:
        try:
            parsed = dict(submission_answers(cached["submission"], record, form).answers)
        except Exception:  # noqa: BLE001 - a submission the definition no longer reads: its raw answers instead
            parsed = None
        if parsed is not None:
            rows = answer_fields(parsed, form, private)
            return [mask_field(f["title"] or f["name"], f["value"], f["p2"]) for f in rows], parsed, record
    fields = []
    for answer in sub.get("answers") or ():
        if not isinstance(answer, dict):
            continue
        value = answer.get("answer") if "answer" in answer else answer.get("value")
        if value in (None, ""):
            continue
        question = answer.get("question") if isinstance(answer.get("question"), dict) else {}
        qid = answer.get("questionId") or answer.get("formQuestionId") or question.get("id")
        title = str(question.get("label") or answer.get("label") or (f"Question {qid}" if qid else "Answer"))
        field_name = str(questions.get(str(qid), ""))
        fields.append(mask_field(title, _plain(value), bool(field_name) and is_p2(field_name, form, private)))
    return fields, None, record


def _last_read(ask: Ask, sid: int, files: Path) -> tuple[dict[str, Any] | None, dict[str, Any], str]:
    """The source "Last read from PayHOA" from ``submission.json``, what it read (status, answers, readAt), and why it
    is missing when it is."""
    from jason.approvals.kinds.owner_info import request_digest
    from jason.tasks import submission_cache

    try:
        cached = submission_cache.read(files, sid)
    except ValueError as exc:
        return None, {}, (f"its last read could not be opened ({exc}); `jason sync-request-files --requests {sid}` "
                          "reads it again")
    if cached is None:
        return None, {}, ""
    sub = submission_cache.body(cached.get("submission"))
    status = str(cached.get("status") or sub.get("status") or "")
    answers, parsed, record = _last_read_answers(cached, ask.root)
    unit = sub.get("unit") if isinstance(sub.get("unit"), dict) else {}
    form_name = str(cached.get("formName") or (record or {}).get("title") or "")
    fields = [mask_field("Status", status), mask_field("Form", form_name)]
    title = str(unit.get("title") or unit.get("streetAddress") or "").strip()
    if title:
        fields.append(mask_field("Unit", title))
    if sub.get("createdAt"):
        fields.append(mask_field("Submitted", str(sub["createdAt"])))
    via = str(cached.get("via") or "")
    src = source(SourceName.LAST_READ, read_at=str(cached.get("readAt") or ""),
                 digest=request_digest(status, parsed) if parsed is not None else "", fields=fields + answers,
                 caveat="The latest full read of this request jason keeps, not a live read; refreshing it reads "
                        "PayHOA again.",
                 note=(f"Read by {via}." if via else "") + ("" if parsed is not None else
                                                           " The answers are shown as PayHOA labels them: the form's "
                                                           "definition does not read them, so they are not compared."))
    src["note"] = src["note"].strip()
    got = {"readAt": str(cached.get("readAt") or ""), "status": status, "answers": parsed, "via": via,
           "unitId": int(sub.get("unitId") or unit.get("id") or 0)}
    return src, got, ""


def _against_plan(snap: dict[str, Any], last: dict[str, Any]) -> tuple[bool | None, str]:
    """The plan's read against the last read from PayHOA: status and the answers' digest, where both are known."""
    from jason.approvals.kinds.owner_info import request_digest

    then, now = _when(snap.get("readAt", "")), _when(last.get("readAt", ""))
    if then is None or now is None:
        return None, "When the plan or the last read from PayHOA was read is unknown: the two cannot be compared."
    if now < then:
        return None, ("The last read from PayHOA was made before the plan read the request: it cannot say whether "
                      "anything changed since.")
    was, is_ = str(snap.get("status") or ""), last.get("status") or ""
    differs, same = [], []
    if was and is_ and was != is_:
        differs.append(f"status {is_} (the plan read {was})")
    elif was and is_:
        same.append("status")
    if last.get("answers") is not None and snap.get("digest"):
        (differs if request_digest(was, last["answers"]) != snap["digest"] else same).append("the answers")
    if not differs and not same:
        return None, "The last read from PayHOA holds nothing the plan's read can be compared with."
    when = f"read {last['readAt']}" + (f" by {last['via']}" if last.get("via") else "")
    if differs:
        return True, f"The last read from PayHOA ({when}) differs from the plan's read: {'; '.join(differs)}."
    unread = "" if "the answers" in same else "; its answers could not be compared"
    return False, f"The last read from PayHOA ({when}) shows the same {' and '.join(same)} as the plan's read{unread}."


def _against_catalog(snap: dict[str, Any], row: dict[str, Any]) -> tuple[bool | None, str]:
    """The plan's read against a catalog synced later: the status only (the catalog holds no answers)."""
    then, now = _when(snap.get("readAt", "")), _when(row.get("synced_at") or "")
    was, is_ = snap.get("status", ""), row.get("status") or ""
    if then is None or now is None:
        return None, "When one of the copies was read is unknown: the two cannot be compared."
    if now <= then:
        return None, ("The catalog was synced before the plan read the request: it cannot say whether anything "
                      "changed since.")
    if was != is_:
        return True, f"The catalog, synced later, shows status {is_ or '(none)'}; the plan read {was or '(none)'}."
    return False, f"The catalog, synced later, shows the same status ({is_ or '(none)'}); it holds no answers to compare."


def read_submission(ask: Ask) -> dict[str, Any]:
    from jason.tasks.payhoa_forms import requests_link
    from jason.tasks.submission_cache import FILE

    sid = int(ask.match.group(1)) if ask.match else 0
    out: dict[str, Any] = {"label": f"PayHOA request {sid}", "sources": [], "changed": None, "changedNote": "",
                           "link": "", "caveats": [], "note": ""}
    snap, misses, unit_id = ask.snapshot, [], 0
    if snap:
        fields = [mask_field("Status", snap.get("status", ""))]
        if snap.get("unit"):
            fields.append(mask_field("Unit", snap["unit"]))
        fields += [mask_field(f.get("title") or f.get("name", ""), f.get("value", ""), bool(f.get("p2")))
                   for f in snap.get("fields") or ()]
        note = ""
        if ask.evidence is not None and ask.evidence.digest and ask.evidence.digest != snap.get("digest"):
            note = "The snapshot's digest is not the one the plan recorded on this evidence: it was changed after."
        out["label"] = snap.get("label") or out["label"]
        out["sources"].append(source(SourceName.PLAN_READ, read_at=snap.get("readAt", ""),
                                     digest=snap.get("digest", ""), fields=fields,
                                     caveat=SNAPSHOT_CAVEAT.format(approval=ask.approval.id), note=note))
        out["caveats"].append(SNAPSHOT_CAVEAT.format(approval=ask.approval.id))
        unit_id = int(snap.get("unitId") or 0)
    elif ask.approval is not None:
        misses.append(f"{ask.approval.id} kept no snapshot of this request (a plan made before plans kept what they "
                      "read, or one that did not read it)")
    catalog = _catalog_path(ask.root)
    files_root = _files_root(ask.root)
    last_src, last, last_miss = _last_read(ask, sid, files_root)
    if last_src is not None:
        out["sources"].append(last_src)
        unit_id = unit_id or last.get("unitId", 0)
    row = _catalog_row(catalog, sid)
    if row is not None:
        fields = [mask_field("Status", row.get("status") or ""), mask_field("Form", row.get("form_name") or ""),
                  mask_field("Submitted", row.get("created_at") or "")]
        out["sources"].append(source(SourceName.CATALOG, read_at=row.get("synced_at") or "", fields=fields,
                                     caveat="The catalog as last synced (jason sync-catalog), not a live read."))
        unit_id = unit_id or int(row.get("unit_id") or 0)
    else:
        misses.append("the PayHOA catalog has no row for it (`jason sync-catalog --only requests` fills it)")
    folder = files_root / "requests" / str(sid)
    saved = [n for n in ("comments.json", "notes.json") if (folder / n).is_file()]
    if saved:
        comments, notes = _json_rows(folder / "comments.json"), _json_rows(folder / "notes.json")
        files = sorted(p.name for p in folder.iterdir() if p.is_file() and p.name not in ("comments.json", "notes.json",
                                                                                          FILE)
                       and not p.name.endswith(".tmp"))
        fields = [mask_field("Comments", "" if comments is None else str(len(comments))),
                  mask_field("Internal notes", "" if notes is None else str(len(notes))),
                  mask_field("Latest comment", _latest(comments or [])),
                  mask_field("Attachments", str(len(files)))]
        out["sources"].append(source(SourceName.REQUEST_FILES, read_at=max(_mtime(folder / n) for n in saved),
                                     fields=fields,
                                     caveat="Counts only; the comments and notes are read in PayHOA or with "
                                            "get_request_local_export."))
    if last_miss:
        misses.append(last_miss)
    if last_src is None and not saved and not last_miss:
        misses.append(f"neither its full read nor its request files are saved (`jason sync-request-files --requests "
                      f"{sid}` reads it in full and saves both)")
    elif last_src is None and not last_miss:
        misses.append(f"no full read of it is kept (`jason sync-request-files --requests {sid}` reads it in full)")
    elif not saved:
        misses.append(f"no request files are saved for it (`jason sync-request-files --requests {sid}` saves them)")
    compared = []
    if snap and last_src is not None:
        compared.append(_against_plan(snap, last))
    if snap and row is not None:
        compared.append(_against_catalog(snap, row))
    values = [c for c, _ in compared]
    out["changed"] = True if True in values else (False if False in values else None)
    out["changedNote"] = " ".join(n for _, n in compared if n)
    if unit_id:
        out["link"] = requests_link(unit_id)
    out["found"] = bool(out["sources"])
    if misses:
        out["note"] = ("No copy on disk: " if not out["sources"] else "Not on disk: ") + "; ".join(misses) + "."
    return out


def _history_apart(text: str) -> tuple[str, str]:
    """The stored words, and the export's leading ``- History: ...`` lines apart from them, so the recital opens with
    the section itself. The words are otherwise left exactly as stored."""
    lines = text.lstrip("\n").split("\n")
    history: list[str] = []
    while lines and lines[0].startswith("- History:"):
        history.append(lines.pop(0)[len("- History:"):].strip())
        while lines and not lines[0].strip():
            lines.pop(0)
    return ("\n".join(lines), "; ".join(history)) if history else (text, "")


def read_citation(ask: Ask) -> dict[str, Any]:
    from jason.tasks import cite

    try:
        got = cite.resolve(ask.address, data_dir=ask.root)
    except Exception as exc:  # noqa: BLE001 - a shelf that cannot be opened is a miss with its reason
        got = {"found": False, "reason": "unreadable", "detail": f"{type(exc).__name__}: {exc}"}
    citation = str(got.get("citation") or ask.address)
    statute = bool(re.match(r"^[A-Z]{2,5} \d", citation))
    out: dict[str, Any] = {"label": citation, "sources": [], "changed": None, "changedNote": "", "link": "",
                           "caveats": [], "note": "", "found": bool(got.get("found"))}
    if got.get("found"):
        text, history = _history_apart(str(got.get("text") or ""))
        got["text"] = text
        fields = [mask_field("Cited at", str(got.get("address") or "")), mask_field("In force", got.get("inForce", "")),
                  mask_field("History", history)]
        name = SourceName.STATUTES if statute else SourceName.DOCUMENTS
        read_at = _mtime(ask.root / "authorities" / "manifest.json") if statute else ""
        caveat = str(got.get("caveat") or (STATUTE_CAVEAT if statute else ""))
        out["sources"].append(source(name, read_at=read_at, fields=[f for f in fields if f["value"]],
                                     text=str(got.get("text") or ""), citation=citation, caveat=caveat,
                                     note="" if got.get("text") else "An outline, not words: open each section."))
        if caveat:
            out["caveats"].append(caveat)
    else:
        reason = str(got.get("reason") or "not found")
        detail = f" ({got['detail']})" if got.get("detail") else ""
        fill = ("`jason export-authorities` exports the statutes' words into data/authorities"
                if statute or reason == "statute_not_on_disk" else f"`jason cite \"{ask.address}\"` says what it names")
        out["note"] = f"Not recited: {reason.replace('_', ' ')}{detail}. {fill}."
    return out


def read_board_item(ask: Ask) -> dict[str, Any]:
    from jason.community.board_items import Session, agenda_session
    from jason.tasks.board_items import STORE, load

    key = ask.match.group(1).strip() if ask.match else ""
    path = ask.root / STORE
    out: dict[str, Any] = {"label": f"Board item {key}", "sources": [], "changed": None, "changedNote": "",
                           "link": "", "caveats": [], "note": "", "found": False}
    try:
        items = load(ask.root)
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read is a miss with its reason
        out["note"] = f"The board's items could not be read ({type(exc).__name__}: {exc})."
        return out
    item = next((i for i in items if i.id == key), None)
    if item is None:
        out["note"] = (f"No board item {key} in {STORE.as_posix()}" + ("" if path.is_file() else " (the file is not "
                       "there)") + ": the reviews that find a matter add it (`jason board` lists them).")
        return out
    executive = agenda_session(item) is Session.EXECUTIVE
    rows = [("Title", item.title), ("Ask", item.ask), ("Status", item.status.value),
            ("Priority", item.priority.value), ("Category", item.category.value), ("Authority", item.authority),
            ("Session", agenda_session(item).value), ("Due", item.due.isoformat() if item.due else ""),
            ("Meeting", item.meeting), ("Owner", item.owner),
            ("Summary", "" if executive else item.summary), ("Notes", "" if executive else item.notes),
            ("Evidence", "; ".join(item.evidence))]
    out["sources"].append(source(SourceName.BOARD_ITEMS, read_at=_mtime(path),
                                 fields=[mask_field(n, v) for n, v in rows if v],
                                 caveat="The board's running list; the board owns its status, owner, meeting, and "
                                        "notes. An item is a matter to decide, never the decision.",
                                 note="Executive session: its summary and notes are held back." if executive else ""))
    out.update(label=f"Board item {key}: {item.title}", found=True)
    return out


# What a command's words say it reads live, in order: the first that matches names the system.
COMMAND_SYSTEMS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"--payhoa\b|\bsync-(catalog|request-files|bills|liens)\b|\bapprovals apply\b|\bmailroom\b"), "PayHOA"),
    (re.compile(r"--sheet\b|--doc\b|--tasks\b|\bsync-(gmail|drive|library)\b"), "Google"),
)


def read_command(ask: Ask) -> dict[str, Any]:
    return {"label": ask.address, "sources": [], "changed": None, "changedNote": "", "link": "", "caveats": [],
            "note": "A command, not a record: run it to see what it shows.", "found": True}


def _command_refresh(ask: Ask) -> list[dict[str, Any]]:
    """The command itself; live when its words name a system it reads (``COMMAND_SYSTEMS``), else not known to be."""
    system = next((name for pattern, name in COMMAND_SYSTEMS if pattern.search(ask.address)), "")
    return [{"command": ask.address, "live": bool(system), "what": "the command that produced this",
             "system": system}]


def read_unknown(ask: Ask) -> dict[str, Any]:
    why = ("no address" if not ask.address else
           "jason cannot open this address: it is not a PayHOA request (payhoa:submission:N), a board item "
           "(board-item:ID), a command (jason ...), or a citation jason cite reads")
    return {"label": ask.address, "sources": [], "changed": None, "changedNote": "", "link": "", "caveats": [],
            "note": why + ".", "found": False}


def _citation(address: str) -> re.Match[str] | None:
    """A citation the cite grammar names: a statute, a document's section, a resolution, an instrument, minutes."""
    from jason.community.cite import Target, parse

    try:
        hit = parse(address, {})
    except Exception:  # noqa: BLE001 - the grammar never takes it: not a citation
        return None
    if isinstance(hit, Target) or address.lower().startswith("jason://") or "#" in address:
        return re.match(r".+", address)
    return None


def refresh_submission(client: Any, org_id: int, match: re.Match[str], root: Path, via: str) -> None:
    """Read one PayHOA request in full (one ``get_form_submission``) and keep it as its last read. Its form's name is
    the recorded form's or the catalog's when the submission does not carry it. Writes nothing to PayHOA."""
    from jason.tasks import submission_cache

    sid = int(match.group(1))
    detail = client.get_form_submission(org_id, sid)
    form_id, name = submission_cache.form_of(detail)
    if not name:
        record, _, _ = _form_for(root, form_id)
        name = str((record or {}).get("title") or (_catalog_row(_catalog_path(root), sid) or {}).get("form_name")
                   or "")
    submission_cache.write(_files_root(root), sid, detail, via=via, form_id=form_id, form_name=name)


# The rule rows, in order: the first whose matcher takes the address reads it.
RULES: tuple[Resolver, ...] = (
    Resolver(EvidenceKind.PAYHOA_SUBMISSION, re.compile(r"^payhoa:submission:(\d+)$").match, read_submission,
             (Refresh("jason approvals apply {approval}", True,
                      "re-read PayHOA and compare with this plan, writing nothing", "PayHOA", needs_approval=True),
              Refresh("jason sync-request-files --requests {id}", True,
                      "re-read this request in full: its answers, comments, notes, and attachments", "PayHOA"),
              Refresh("jason sync-catalog --only requests", True, "re-read every request's status into the catalog",
                      "PayHOA")),
             live=True,
             refresher=Refresher("PayHOA", "Read this request again from PayHOA", refresh_submission)),
    Resolver(EvidenceKind.BOARD_ITEM, re.compile(r"^board-item:(.+)$").match, read_board_item,
             (Refresh("jason board", False, "list the board's items as stored"),
              Refresh("jason board --sheet", True,
                      "sync the board's Sheet: read the board's columns back from Google, then write jason's",
                      "Google")),
             live=False),
    Resolver(EvidenceKind.COMMAND, re.compile(r"^jason\s+\S").match, read_command, (), live=False),
    Resolver(EvidenceKind.CITATION, _citation, read_citation,
             (Refresh("jason export-authorities", False,
                      "export the statutes' words from lawlibrary into data/authorities"),
              Refresh('jason cite "{address}"', False, "recite it from disk, with what it cites")),
             live=False),
)
UNKNOWN = Resolver(EvidenceKind.UNKNOWN, lambda a: None, read_unknown, (), live=False)


def rule_for(address: str) -> tuple[Resolver, re.Match[str] | None]:
    """The first rule row that takes ``address``, and its match; ``UNKNOWN`` when none does."""
    for rule in RULES:
        found = rule.matches(address) if address else None
        if found:
            return rule, found
    return UNKNOWN, None


# --- resolve --------------------------------------------------------------------------------------------------------------

def _from_approval(approval_id: str, address: str, root: Path, notes: list[str]) -> tuple[Any, Any, Any]:
    """The approval, its evidence row for ``address``, and the plan's snapshot of it; a miss is noted, not raised."""
    from jason.approvals import store

    try:
        approval = store.load(store.resolve(approval_id, root), root)
    except KeyError as exc:
        notes.append(f"{exc.args[0] if exc.args else 'no approval ' + approval_id}: opened without a plan")
        return None, None, None
    except (OSError, ValueError) as exc:
        notes.append(f"approval {approval_id} could not be read ({type(exc).__name__}): opened without a plan")
        return None, None, None
    rows = list(approval.evidence) + [e for i in approval.items for e in i.evidence]
    evidence = next((e for e in rows if e.address == address), None)
    try:
        snapshot = store.load_snapshots(approval.id, root).get(address)
    except (OSError, ValueError):
        snapshot = None
        notes.append(f"{approval.id}'s snapshot could not be read")
    return approval, evidence, snapshot


def resolve(address: str, *, approval_id: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """What jason holds on disk of the record ``address`` names, copy by copy, with the commands that read it again.
    ``approval_id`` (an id or a unique prefix) adds the plan's own read of it. Reads disk only, never PayHOA, Google,
    or Keeper. Never raises on what it is asked: a miss is ``found: false`` with its reason (``note``).

    ``{found, address, label, kind, sources: [{name, readAt, digest, fields: [{name, value, masked}], text,
    citation, caveat, note}], changed, changedNote, link, refresh: [{command, live, what, system}],
    refreshable: {system, what} | null, caveats, note}``; ``refreshable`` is null when the kind has no one-record live
    refresher (``refresh``)."""
    address = " ".join(str(address or "").split())
    notes: list[str] = []
    try:
        root = _root(data_dir)
    except Exception as exc:  # noqa: BLE001 - settings that cannot be read leave the profile's own folder
        from jason.config import default_data_dir

        root = default_data_dir()
        notes.append(f"the settings could not be read ({type(exc).__name__}): the profile's own data folder was read")
    rule, found = rule_for(address)
    approval = evidence = snapshot = None
    if approval_id.strip():
        approval, evidence, snapshot = _from_approval(approval_id.strip(), address, root, notes)
        if approval is not None and evidence is None and address:
            notes.append(f"{approval.id} names no evidence at this address")
    ask = Ask(address, found, root, approval, evidence, snapshot, notes)
    try:
        got = rule.read(ask)
    except Exception as exc:  # noqa: BLE001 - a reader that fails is a miss with its reason, never a traceback
        got = {"label": address, "sources": [], "changed": None, "changedNote": "", "link": "", "caveats": [],
               "note": f"could not be read: {type(exc).__name__}: {exc}", "found": False}
    values = {"id": found.group(1) if found is not None and found.groups() else "", "address": address,
              "approval": approval.id if approval is not None else ""}
    if rule.kind is EvidenceKind.COMMAND:
        refresh = _command_refresh(ask)
    else:
        refresh = [r.as_dict(values) for r in rule.refresh if approval is not None or not r.needs_approval]
    caveats = [CAVEAT] + [c for c in got.get("caveats") or () if c and c != CAVEAT]
    if any(f.get("masked") for s in got.get("sources") or () for f in s.get("fields") or ()):
        caveats.append(MASKED_CAVEAT)
    caveats.append(DISK_ONLY)
    note = " ".join(n for n in [got.get("note", "")] + [n[:1].upper() + n[1:] + "." for n in notes] if n)
    label = evidence.label if evidence is not None and evidence.label else got.get("label") or address
    out = {"found": bool(got.get("found")), "address": address, "label": label, "kind": rule.kind.value,
           "sources": got.get("sources") or [], "changed": got.get("changed"),
           "changedNote": got.get("changedNote", ""), "link": got.get("link", ""), "refresh": refresh,
           "refreshable": rule.refresher.as_dict() if rule.refresher is not None else None,
           "caveats": list(dict.fromkeys(caveats)), "note": note}
    return _scrub(out)


# --- refresh one record ---------------------------------------------------------------------------------------------------

CACHE_LOCK = "evidence-cache"                  # the store lock a refresh holds while it reads and keeps one record
REFRESH_LOG = Path("evidence") / "refreshes.jsonl"
KEEPER_SIGN_IN = "Keeper is not signed in; run `jason login` in a terminal, then refresh again."


class RefreshFailed(RuntimeError):
    """The live read a refresh made did not answer (Keeper not signed in, PayHOA refused or failed). Its message is
    for the person; the audit line records it."""


@contextmanager
def payhoa_live() -> Iterator[Any]:
    """PayHOA signed in non-interactively, as jason-web's ``default_live`` does: a missing Keeper session fails fast
    (``KeeperAuthRequired``). Yields an object with ``client`` and ``org_id``."""
    from types import SimpleNamespace

    from jason.agent import Jason

    with Jason(interactive=False) as agent:
        yield SimpleNamespace(client=agent.payhoa(), org_id=agent.org_id)


def _failure(exc: BaseException, system: str) -> str:
    from jason.secrets import KeeperAuthRequired

    if isinstance(exc, KeeperAuthRequired) or type(exc).__name__ == "KeeperAuthRequired":
        return KEEPER_SIGN_IN
    return f"{system} could not be read: {type(exc).__name__}: {exc}"


def _log_refresh(root: Path, entry: dict[str, Any]) -> None:
    file = root / REFRESH_LOG
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as out:
        out.write(json.dumps(_scrub(entry), ensure_ascii=False, sort_keys=True) + "\n")


def refresh(address: str, *, by: str, client_factory: Callable[[], ContextManager[Any]] | None = None,
            data_dir: Path | None = None, approval_id: str = "") -> dict[str, Any]:
    """Read one record again live, for the person ``by``, and keep it in jason's own cache (a PayHOA request: one
    ``get_form_submission``, written as its last read). Never writes to the system it reads.

    Holds the cache's store lock (``jason.locks``) for the read and the write, and appends one line to
    ``evidence/refreshes.jsonl`` (``at``, ``by``, ``address``, ``system``, ``ok``, ``error``; never what was read).
    ``client_factory()`` is a context manager yielding ``client`` and ``org_id`` (default ``payhoa_live``: never
    interactive). Returns ``resolve(address, approval_id=...)`` with ``refreshed: {at, by, system}``.

    Refuses (``ValueError``) an empty ``by`` and a kind with no refresher; a live read that fails is ``RefreshFailed``
    (a Keeper session that needs a person says to run ``jason login`` in a terminal)."""
    from jason.locks import Resource, hold

    by = " ".join(str(by or "").split())
    if not by:
        raise ValueError("a refresh names the person (by): it reads PayHOA under their name")
    address = " ".join(str(address or "").split())
    rule, found = rule_for(address)
    if rule.refresher is None or found is None:
        raise ValueError(f"{address or '(no address)'} ({rule.kind.value}) has no live refresher: "
                         + ("open it to see the commands that read it again" if address else "name an address"))
    root = _root(data_dir)
    system = rule.refresher.system
    with hold(Resource.STORE, CACHE_LOCK, timeout=120, purpose=f"evidence refresh {address}"):
        at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry = {"at": at, "by": by, "address": address, "system": system, "ok": True, "error": ""}
        try:
            with (client_factory or payhoa_live)() as live:
                rule.refresher.run(live.client, int(live.org_id), found, root, f"console refresh by {by}")
        except Exception as exc:  # noqa: BLE001 - said to the person and logged, never a traceback
            entry.update(ok=False, error=_failure(exc, system))
            _log_refresh(root, entry)
            raise RefreshFailed(entry["error"]) from exc
        _log_refresh(root, entry)
    out = resolve(address, approval_id=approval_id, data_dir=root)
    out["refreshed"] = {"at": at, "by": by, "system": system}
    return out


__all__ = ["Ask", "CACHE_LOCK", "CAVEAT", "EvidenceKind", "KEEPER_SIGN_IN", "REFRESH_LOG", "RULES", "Refresh",
           "RefreshFailed", "Refresher", "Resolver", "SNAPSHOT_CAVEAT", "SourceName", "mask_field", "mask_text",
           "payhoa_live", "refresh", "refresh_submission", "resolve", "rule_for"]
