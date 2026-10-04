"""Canvases: one scratchpad per topic a person is researching or preparing for board action.

A canvas is the work before a board item: the question, the person's notes, clips of evidence gathered from the
read-only tools (a row, a passage, a figure, with where it came from), links, a checklist, and where it stands.
It is jason's own store (``data/canvases/<key>.json``), written by a person through the UI or a command; it reads
no profile fact and calls no service. A clip is evidence a person kept, not a pin in the specification's sense.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STORE = "canvases"


class CanvasStatus(Enum):
    RESEARCH = "research"          # gathering what the records show
    PREPARING = "preparing"        # drafting the ask, the options, the motion
    ON_AGENDA = "on agenda"        # handed to a board item or a meeting
    DONE = "done"


@dataclass
class Clip:
    at: str                        # when it was kept (ISO, UTC)
    source: str                    # the tool or page it came from ("board_digest", "duty brief: Money", a URL)
    text: str                      # the row, passage, or figure as kept
    label: str = ""                # what it shows, in the person's words
    args: dict[str, Any] = field(default_factory=dict)  # the query that produced it, so it can be re-read


@dataclass
class Canvas:
    key: str                       # a slug ("reserve-loan-2025")
    title: str
    question: str = ""             # what the board will be asked, or what is being found out
    status: CanvasStatus = CanvasStatus.RESEARCH
    matter: str = ""               # a board item id once one exists
    duty: str = ""                 # the duty anchor it falls under ("Money")
    notes: str = ""                # the person's notes, Markdown
    clips: list[Clip] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)      # {"label", "url"}
    attachments: list[dict[str, Any]] = field(default_factory=list)  # {"kind", "ref", "title", "opts"?}: a Doc, Sheet, Form, Drive file, photo, PDF, calendar, Zoom recording, audio, map, chart, or mail thread shown on the canvas; opts is str -> str
    checklist: list[dict[str, Any]] = field(default_factory=list)  # {"text", "done"}
    created: str = ""
    updated: str = ""
    history: list[str] = field(default_factory=list)


# The fields a person edits in place; everything else is set by a call (a clip is added, never edited).
EDITABLE = ("title", "question", "status", "matter", "duty", "notes", "links", "checklist", "attachments")
ATTACHMENT_KINDS = ("doc", "sheet", "slides", "form", "drive", "image", "pdf", "url", "calendar", "zoom", "audio", "map", "chart", "thread")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "canvas"


def encode(c: Canvas) -> dict[str, Any]:
    raw = asdict(c)
    raw["status"] = c.status.value
    return raw


# Attachment kinds that name a Drive file by its id or link, and kinds that name a file under data/ by its path.
DRIVE_KINDS = ("doc", "sheet", "slides", "form", "drive")
# The evidence's `file:` row shows PDFs, images, text, and audio (played in the viewer's player).
FILE_KINDS = ("image", "pdf", "audio")
_WEB = re.compile(r"^(?:https?|blob|data):", re.IGNORECASE)
_GOOGLE_ID = (re.compile(r"/(?:d|folders|file/d)/([A-Za-z0-9_-]{10,})"), re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"))


def attachment_ref(a: dict[str, Any], data_dir: Path) -> dict[str, Any] | None:
    """An attachment's document reference (docs/console/doc-component.md): a Drive kind's ``drive:<id>`` (from the id or
    a private link; a published ``/d/e/`` link is no file of the association's Drive and stays a frame), a photo, PDF,
    or recording under data/ as ``file:<path>``; None for anything else (a web page, the calendar, a map, a chart, a
    Zoom share page, a Gmail thread, remote audio), which stays what it is."""
    from jason.approvals.docref import drive_ref, file_ref

    kind, ref = str(a.get("kind") or ""), str(a.get("ref") or "").strip()
    title = str(a.get("title") or "") or None
    try:
        if kind in DRIVE_KINDS:
            if "/d/e/" in ref:
                return None
            found = next((m.group(1) for p in _GOOGLE_ID for m in [p.search(ref)] if m), ref)
            return drive_ref(found, name=title, data_dir=data_dir)
        if kind in FILE_KINDS and ref and not _WEB.match(ref):
            return file_ref(ref, name=title, data_dir=data_dir)
    except ValueError:
        return None
    return None


def with_refs(raw: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    """An encoded canvas with document references beside the old fields: ``doc`` on each attachment that names a Drive
    file or a file under data/, and on each clip whose source names a document (an evidence address, ``data/<path>``,
    ``library: <path>``, or a citation; ``refs_from_strings``). Anything else stays as written. Reads disk only."""
    from jason.approvals.docref import ref_from_string

    out = dict(raw)
    attachments = []
    for a in raw.get("attachments") or []:
        doc = attachment_ref(a, data_dir) if isinstance(a, dict) else None
        attachments.append({**a, "doc": doc} if doc else a)
    out["attachments"] = attachments
    clips = []
    for c in raw.get("clips") or []:
        said = str(c.get("source") or "") if isinstance(c, dict) else ""
        try:
            got = ref_from_string(said, data_dir=data_dir) if said.strip() else {}
        except (OSError, ValueError):
            got = {}
        clips.append({**c, "doc": got} if "address" in got else c)
    out["clips"] = clips
    return out


def decode(raw: dict[str, Any]) -> Canvas:
    data = dict(raw)
    data["status"] = CanvasStatus(data.get("status") or "research")
    data["clips"] = [Clip(**x) for x in data.get("clips", [])]
    known = {f for f in Canvas.__dataclass_fields__}
    return Canvas(**{k: v for k, v in data.items() if k in known})


def _dir(data_dir: Path) -> Path:
    return Path(data_dir) / STORE


def _path(data_dir: Path, key: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", key):
        raise KeyError(key)
    return _dir(data_dir) / f"{key}.json"


def load(data_dir: Path, key: str) -> Canvas:
    path = _path(data_dir, key)
    if not path.is_file():
        raise KeyError(key)
    return decode(json.loads(path.read_text(encoding="utf-8")))


def load_all(data_dir: Path) -> list[Canvas]:
    folder = _dir(data_dir)
    if not folder.is_dir():
        return []
    items = [decode(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(folder.glob("*.json"))]
    return sorted(items, key=lambda c: (c.updated, c.key), reverse=True)


def save(data_dir: Path, c: Canvas) -> Path:
    path = _path(data_dir, c.key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(encode(c), indent=1), encoding="utf-8")
    return path


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, STORE, timeout=60, purpose=f"canvases: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def create(data_dir: Path, title: str, *, question: str = "", duty: str = "", matter: str = "") -> Canvas:
    title = title.strip()
    if not title:
        raise ValueError("a canvas needs a title")
    key = base = slug(title)
    n = 2
    while _path(data_dir, key).exists():
        key, n = f"{base}-{n}", n + 1
    now = _now()
    c = Canvas(key=key, title=title, question=question.strip(), duty=duty.strip(), matter=matter.strip(), created=now, updated=now,
               history=[f"{now[:10]}: opened"])
    save(data_dir, c)
    return c


@_store_lock
def update(data_dir: Path, key: str, **changes: Any) -> Canvas:
    """Change the fields a person edits. Anything else is refused."""
    unknown = sorted(set(changes) - set(EDITABLE))
    if unknown:
        raise ValueError(f"{', '.join(unknown)}: not a field a person edits; a clip is added with add_clip")
    c = load(data_dir, key)
    now = _now()
    for k, v in changes.items():
        if k == "status":
            v = CanvasStatus(v) if not isinstance(v, CanvasStatus) else v
        if k in ("links", "checklist", "attachments") and not isinstance(v, list):
            raise ValueError(f"{k} is a list")
        if k == "attachments":
            # A reference is the loader's (with_refs), built afresh on each read: never kept in the store.
            v = [{x: y for x, y in a.items() if x != "doc"} if isinstance(a, dict) else a for a in v]
            bad = [a for a in v if not isinstance(a, dict) or a.get("kind") not in ATTACHMENT_KINDS or not str(a.get("ref", "")).strip()]
            if bad:
                raise ValueError(f"an attachment is {{kind: one of {', '.join(ATTACHMENT_KINDS)}, ref, title, opts?}}")
            bad_opts = [a for a in v if "opts" in a and not (isinstance(a["opts"], dict)
                                                             and all(isinstance(k, str) and isinstance(x, str) for k, x in a["opts"].items()))]
            if bad_opts:
                raise ValueError("an attachment's opts is an object of string values")
        if getattr(c, k) != v:
            if k == "status":
                c.history.append(f"{now[:10]}: status {c.status.value} -> {v.value}")
            setattr(c, k, v)
    c.updated = now
    save(data_dir, c)
    return c


@_store_lock
def add_clip(data_dir: Path, key: str, *, source: str, text: str, label: str = "", args: dict[str, Any] | None = None) -> Canvas:
    if not text.strip():
        raise ValueError("a clip needs text")
    c = load(data_dir, key)
    now = _now()
    c.clips.append(Clip(at=now, source=source.strip() or "unknown", text=text.strip(), label=label.strip(), args=dict(args or {})))
    c.updated = now
    save(data_dir, c)
    return c
