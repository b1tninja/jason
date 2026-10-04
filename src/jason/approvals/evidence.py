"""Evidence you can open: an approval item's evidence address resolved back to the record, from disk only.

An item's evidence is ``Evidence(label, address)``: ``payhoa:submission:N`` (a PayHOA request), a citation
(``CIV 4040(a)(2)``, ``decl#6.2(a)``), ``board-item:ID``, or a command (``jason owner-info --responses``). ``resolve``
answers what jason holds of it on disk, copy by copy (``sources``), and never reads PayHOA, Google, or Keeper: each
copy says when it was read, and ``refresh`` names the command that reads it again and whether that command reads a
live system.

- **A PayHOA request.** The plan's own read first: a plan that read requests live keeps what it read beside the
  approval (``approvals/<id>.evidence.json``, written with the plan), so "This plan's read" is what PayHOA said when
  the plan was made. Then the PayHOA catalog (``jason sync-catalog``) and the request's saved files
  (``jason sync-request-files``). ``changed`` compares the plan's read with a catalog synced later, where the two
  can be compared (the status); null when they cannot.
- **A citation.** ``jason.tasks.cite.resolve``: the words recited from disk (``jason export-authorities`` for the
  statutes), never paraphrased.
- **A board item.** ``data/board/items.json``; an executive-session item's summary and notes are held back.
- **A command.** Found, with no copy: the command is what produced the evidence, and running it is the refresh.

Which reader answers is the first rule row whose matcher takes the address (``RULES``; the order is part of the rule).
An address no row takes is ``found: false, kind: "unknown"`` with the reason, never an exception.

Privacy: the snapshot on disk holds a request's answers as read (P2, like the catalog). An owner's contact details
(email, phone, mailing address) and other P2 answers are masked here, before anything leaves the server
(docs/console/security-and-privacy.md).
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

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
class Resolver:
    """One rule row: the kind, how it takes an address, the reader (disk only), the commands that refresh it, and
    whether refreshing it reads a live system."""
    kind: EvidenceKind
    matches: Callable[[str], re.Match[str] | None]
    read: Callable[[Ask], dict[str, Any]]
    refresh: tuple[Refresh, ...] = ()
    live: bool = False


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


def read_submission(ask: Ask) -> dict[str, Any]:
    from jason.tasks.payhoa_forms import requests_link

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
    row = _catalog_row(catalog, sid)
    if row is not None:
        fields = [mask_field("Status", row.get("status") or ""), mask_field("Form", row.get("form_name") or ""),
                  mask_field("Submitted", row.get("created_at") or "")]
        out["sources"].append(source(SourceName.CATALOG, read_at=row.get("synced_at") or "", fields=fields,
                                     caveat="The catalog as last synced (jason sync-catalog), not a live read."))
        unit_id = unit_id or int(row.get("unit_id") or 0)
    else:
        misses.append("the PayHOA catalog has no row for it (`jason sync-catalog --only requests` fills it)")
    folder = catalog.parent / "payhoa-files" / "requests" / str(sid)
    if folder.is_dir():
        comments, notes = _json_rows(folder / "comments.json"), _json_rows(folder / "notes.json")
        files = sorted(p.name for p in folder.iterdir() if p.is_file() and p.name not in ("comments.json", "notes.json"))
        fields = [mask_field("Comments", "" if comments is None else str(len(comments))),
                  mask_field("Internal notes", "" if notes is None else str(len(notes))),
                  mask_field("Latest comment", _latest(comments or [])),
                  mask_field("Attachments", str(len(files)))]
        read_at = max((_mtime(folder / n) for n in ("comments.json", "notes.json") if (folder / n).is_file()),
                      default="")
        out["sources"].append(source(SourceName.REQUEST_FILES, read_at=read_at, fields=fields,
                                     caveat="Counts only; the comments and notes are read in PayHOA or with "
                                            "get_request_local_export."))
    else:
        misses.append(f"no request files are saved for it (`jason sync-request-files --requests {sid}` saves them)")
    if snap and row is not None:
        then, now = _when(snap.get("readAt", "")), _when(row.get("synced_at") or "")
        was, is_ = snap.get("status", ""), row.get("status") or ""
        if then is None or now is None:
            out["changedNote"] = "When one of the copies was read is unknown: the two cannot be compared."
        elif now <= then:
            out["changedNote"] = ("The catalog was synced before the plan read the request: it cannot say whether "
                                  "anything changed since.")
        elif was != is_:
            out["changed"] = True
            out["changedNote"] = (f"The catalog, synced later, shows status {is_ or '(none)'}; the plan read "
                                  f"{was or '(none)'}.")
        else:
            out["changed"] = False
            out["changedNote"] = (f"The catalog, synced later, shows the same status ({is_ or '(none)'}); it holds no "
                                  "answers to compare.")
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


# The rule rows, in order: the first whose matcher takes the address reads it.
RULES: tuple[Resolver, ...] = (
    Resolver(EvidenceKind.PAYHOA_SUBMISSION, re.compile(r"^payhoa:submission:(\d+)$").match, read_submission,
             (Refresh("jason approvals apply {approval}", True,
                      "re-read PayHOA and compare with this plan, writing nothing", "PayHOA", needs_approval=True),
              Refresh("jason sync-catalog --only requests", True, "re-read every request's status into the catalog",
                      "PayHOA"),
              Refresh("jason sync-request-files --requests {id}", True,
                      "re-read this request's comments, internal notes, and attachments", "PayHOA")),
             live=True),
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
    citation, caveat, note}], changed, changedNote, link, refresh: [{command, live, what, system}], caveats, note}``"""
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
           "caveats": list(dict.fromkeys(caveats)), "note": note}
    return _scrub(out)


__all__ = ["Ask", "CAVEAT", "EvidenceKind", "RULES", "Refresh", "Resolver", "SNAPSHOT_CAVEAT", "SourceName",
           "mask_field", "mask_text", "resolve", "rule_for"]
