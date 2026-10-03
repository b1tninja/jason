"""The words a notice carried, kept with it in ``data/notices/KEY/``.

When jason sends a notice, or saves one as a draft for a person to send, it keeps what it rendered there:

- the body as rendered (``message.html``, ``notice.md``, ``notice.txt``; a letter's PDF), before PayHOA fills each
  member's own placeholders;
- the subject;
- the fill records of its ``{QUOTE:}`` and ``{CITE:}`` tokens, or of the sections it recited (``BODY.refs.json``), each
  with the words' digest;
- the recipients plan when one was built (``recipients.json``: ids and counts, never names or addresses).

``kept.json`` lists each keeping: what it was (``kind``), how it went out (``state``: sent, or saved as a draft for a
person to send), when, by whom, and each file with its sha256, so a later edit is detectable. ``read`` compares each
file with its digest. A dry run keeps nothing: the callers keep only once they have sent or saved. A kept file is never
overwritten: a different text under the same key is kept beside it (``message-2.html``), and the same text kept again
adds nothing.

KEY is the notice's ledger key (``jason notices KEY``), which starts with its requirement's key
(``rule-change-proposed-fines-2099-01-02``) or the form whose request it is (``owner-info-2099``), so its record
(``jason://notice/KEY``, ``jason.tasks.notice_record``) finds the requirement, the stage, and these files.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

KEPT = "kept.json"
RECIPIENTS = "recipients.json"
_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class NoticeKeyError(ValueError):
    """A key that cannot name a notice's folder."""


def check_key(key: str) -> str:
    key = str(key or "").strip()
    if not _KEY.match(key) or ".." in key:
        raise NoticeKeyError(f"{key!r} is not a notice key: lower-case words joined by hyphens, starting with the "
                             "requirement's key (board-meeting-2099-01-14)")
    return key


def notice_key(batch_id: str) -> str | None:
    """The notice a batch belongs to: its own id; a resend's (``-resend-``) is the notice it resends; a test batch
    (``-test-``) is no notice (None)."""
    if "-test-" in batch_id:
        return None
    return batch_id.split("-resend-", 1)[0]


def folder(data_dir: Path, key: str) -> Path:
    return Path(data_dir) / "notices" / check_key(key)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bytes(body: str | bytes | Path) -> bytes:
    if isinstance(body, Path):
        return body.read_bytes()
    return body.encode("utf-8") if isinstance(body, str) else bytes(body)


def _place(where: Path, name: str, data: bytes) -> tuple[Path, bool]:
    """Where ``data`` is kept under ``name``: the file already holding the same bytes, else a free name. Returns the
    path and whether it is new."""
    stem, suffix = (name.split(".", 1) + [""])[:2]
    suffix = "." + suffix if suffix else ""
    n = 1
    while True:
        path = where / (name if n == 1 else f"{stem}-{n}{suffix}")
        if not path.exists():
            return path, True
        if path.read_bytes() == data:
            return path, False
        n += 1


def load(data_dir: Path, key: str) -> dict[str, Any]:
    path = folder(data_dir, key) / KEPT
    if not path.is_file():
        return {"key": key, "entries": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"key": key, "entries": [], "unreadable": True}
    raw.setdefault("entries", [])
    return raw


def keep(data_dir: Path, key: str, *, kind: str, state: str, body: str | bytes | Path | None = None,
         body_name: str = "message.html", subject: str = "", refs: Iterable[dict[str, Any]] | None = None,
         recipients: dict[str, Any] | None = None, attachments: Iterable[Path] = (), batch: str = "", by: str = "",
         source: str = "", now: datetime | None = None) -> dict[str, Any]:
    """Keep a notice's words as rendered, once it is sent or saved for sending. Returns the entry added to
    ``kept.json`` (or the one already there for the same files)."""
    where = folder(data_dir, key)
    where.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []

    def put(name: str, data: bytes, role: str) -> Path:
        path, _ = _place(where, name, data)
        if not path.exists():
            path.write_bytes(data)
        files.append({"path": path.name, "role": role, "sha256": sha256_of(data)})
        return path

    text_path = None
    if body is not None:
        text_path = put(body_name, _bytes(body), "letter" if body_name.lower().endswith(".pdf") else "text")
    refs = list(refs or ())
    if refs and text_path is not None:
        sidecar = json.dumps({"source": source or text_path.name, "references": refs}, indent=1)
        put(text_path.name + ".refs.json", sidecar.encode("utf-8"), "fills")
    if recipients is not None:
        put(RECIPIENTS, json.dumps(recipients, indent=1, default=str).encode("utf-8"), "recipients")
    for a in attachments:
        a = Path(a)
        if a.is_file():
            put(a.name, a.read_bytes(), "attachment")
    manifest = load(data_dir, key)
    digests = sorted((f["path"], f["sha256"]) for f in files)
    for e in manifest["entries"]:
        if sorted((f["path"], f["sha256"]) for f in e.get("files") or ()) == digests and e.get("subject") == subject:
            return e
    entry = {"kept": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"), "kind": kind, "state": state,
             "subject": subject, "batch": batch, "by": by, "source": source, "files": files}
    manifest["key"] = key
    manifest["entries"].append(entry)
    (where / KEPT).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return entry


def read(data_dir: Path, key: str) -> dict[str, Any] | None:
    """The keepings under ``key``, each file compared with the digest it was kept with: ``same`` is False for a file
    edited since, None for one that is gone. None when nothing is kept."""
    try:
        where = folder(data_dir, key)
    except NoticeKeyError:
        return None
    manifest = load(data_dir, key)
    if not manifest["entries"]:
        return None
    for e in manifest["entries"]:
        for f in e.get("files") or ():
            path = where / f["path"]
            if path.is_file():
                f["sha256Now"] = sha256_of(path.read_bytes())
                f["same"] = f["sha256Now"] == f["sha256"]
            else:
                f["sha256Now"], f["same"] = "", None
    manifest["edited"] = [f["path"] for e in manifest["entries"] for f in e.get("files") or () if f["same"] is not True]
    return manifest


def fill_records(records: Iterable[Any]) -> list[dict[str, Any]]:
    """The fill records of a rendering (``section_refs.Embedded``), as ``.refs.json`` keeps them."""
    out = []
    for r in records:
        out.append(r.as_dict() if hasattr(r, "as_dict") else dict(r))
    return out


def words_digest(words: str) -> str:
    """A recited section's digest, as the section reader computes it (``SectionText.digest``)."""
    return hashlib.sha256(re.sub(r"\s+", " ", words or "").strip().encode("utf-8")).hexdigest()[:16]


__all__ = ["KEPT", "NoticeKeyError", "RECIPIENTS", "check_key", "fill_records", "folder", "keep", "load", "notice_key",
           "read", "sha256_of", "words_digest"]
