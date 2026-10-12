"""Files a person chose with Google's Picker, read once and held (docs/google-picker.md).

The Picker (redirect form, scope ``drive.file``) hands the server a list of file ids the signed-in person picked in their own
Google Drive. This task is what the server does with them, after ``jason.web.pick`` has traded the code for a token and given
this module a Drive client built from it:

- every id is read **once, read-only**: the metadata first, and every refusal that needs only it is made before a byte moves
  (not a file, a folder, not a PDF, a file the account cannot open, a file over ``fetch.max_bytes``, a drive with no room); then
  the bytes, then the page count against ``split.max_pages`` before any copy is kept;
- a kept file is a **held copy** addressed by its SHA-256 under ``<data>/drive-picks/held/``, with a provenance note: who picked
  it, when, that it came "picked via Picker", its size, pages, Drive's modified time, and a *hash* of the Drive id (never the id,
  never the name). Nothing is written to Drive: no copy, move, rename or sharing change;
- the same bytes picked twice are one held copy ("already held");
- a **dry run** reads metadata only and says what each file would do; nothing is read or kept;
- each real run leaves one line in ``records/history.jsonl`` with the person, the purpose and counts, and the held ids (hash
  prefixes), never a file name or a Drive id;
- the one-use **state** of a pick and the **result** the page reads once are small files under ``<data>/drive-picks/`` of the
  active community: the state is claimed by an atomic rename so it works once, and both die by their time.

A held copy opens as a split draft with ``{"kind": "held", "id": <heldId>}`` (``split_session._resolve``); it is not a pin to a
Drive file, because the server's own account cannot see a person's private file again.

Run ``python -m jason.tasks.drive_pick --purge`` to see the held copies, and add ``--yes`` to remove them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import secrets
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jason import limits, storage

log = logging.getLogger(__name__)

FOLDER = "drive-picks"
VIA = "picked via Picker"
PDF = "application/pdf"
ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
SLOT_RE = re.compile(r"^[a-z0-9][a-z0-9/._-]{0,119}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
MAX_FILES = 25
RESULT_MINUTES = 15


class Purpose(Enum):
    """What the picked files are for: a PDF to split, or a file for a record slot (a slot key is carried along)."""

    SPLIT = "split"
    SLOT = "slot"


class Outcome(Enum):
    HELD = "held"
    ALREADY = "already held"
    WOULD = "would hold"
    REFUSED = "refused"


class PickRefused(ValueError):
    """A pick that cannot go on, in words a person can act on."""


@dataclass
class Row:
    """One picked file's result. ``reason`` is a short code (``too_large``, ``not_pdf``, ``folder``, ``no_access``,
    ``not_readable``, ``no_room``, ``too_many_pages``, ``bad_id``, ``not_a_pdf``, ``duplicate``); ``words`` says it in jason's
    words. ``name`` is shown once, on the page that asked, and is never logged or kept in the provenance."""

    outcome: Outcome
    reason: str = ""
    words: str = ""
    held_id: str = ""
    size: int = 0
    pages: int = 0
    name: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"outcome": self.outcome.value, "reason": self.reason, "words": self.words, "heldId": self.held_id,
                "size": self.size, "pages": self.pages, "name": self.name}


@dataclass
class Report:
    rows: list[Row] = field(default_factory=list)
    dry_run: bool = False

    @property
    def counts(self) -> dict[str, int]:
        c = {o.value: 0 for o in Outcome}
        for r in self.rows:
            c[r.outcome.value] += 1
        return c

    def as_dict(self) -> dict[str, Any]:
        return {"dryRun": self.dry_run, "counts": self.counts, "rows": [r.as_dict() for r in self.rows]}


# --- where things are kept --------------------------------------------------------------------------------------------------

def base(root: Path) -> Path:
    return Path(root) / FOLDER


def held_dir(root: Path) -> Path:
    return base(root) / "held"


def held_file(root: Path, sha: str) -> Path:
    return held_dir(root) / f"{sha}.pdf"


def _prov_file(root: Path, sha: str) -> Path:
    return held_dir(root) / f"{sha}.json"


def _is_sha(text: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", text or ""))


def held_path(root: Path, held_id: str) -> Path | None:
    """The held copy with this id (a SHA-256), or None."""
    if not _is_sha(held_id):
        return None
    path = held_file(root, held_id)
    return path if path.is_file() else None


def provenance(root: Path, held_id: str) -> dict[str, Any]:
    try:
        return json.loads(_prov_file(root, held_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- the one-use state and the one-read result -------------------------------------------------------------------------------

def _state_file(root: Path, state: str) -> Path:
    return base(root) / "states" / f"{_hash(state)}.json"


def _sweep(folder: Path) -> None:
    """Remove what has outlived its time (best effort)."""
    try:
        now = time.time()
        for p in folder.glob("*"):
            try:
                if p.suffix == ".json":
                    if float(json.loads(p.read_text(encoding="utf-8")).get("expires", 0)) < now:
                        p.unlink()
                elif now - p.stat().st_mtime > 3600:          # a claimed or half-written leftover
                    p.unlink()
            except (OSError, ValueError):
                continue
    except OSError:
        pass


def new_state(root: Path, *, by: str, purpose: Purpose, slot: str = "", to: str = "", community: Any = None) -> str:
    """Start a pick: a random state, kept (hashed) with the person, the purpose and when it dies. The page gets the state;
    only its hash is on disk."""
    minutes = int(limits.value("pick.state_minutes", community=community))
    state = secrets.token_urlsafe(24)
    folder = base(root) / "states"
    _sweep(folder)
    row = {"by": by, "purpose": purpose.value, "slot": slot, "next": to, "expires": time.time() + minutes * 60}
    _write_atomic(_state_file(root, state), json.dumps(row).encode("utf-8"))
    return state


def take_state(root: Path, state: str, *, by: str) -> dict[str, Any]:
    """Claim a state once. It is renamed away first (an atomic step only one caller wins), so a second use, a forged state, an
    expired one, and a state started by another person all fail. Returns the row (``purpose``, ``slot``, ``next``)."""
    if not state or len(state) > 200:
        raise PickRefused("The pick did not come back as it was sent: start it again.")
    path = _state_file(root, state)
    claim = path.with_name(path.stem + "." + secrets.token_hex(6) + ".claimed")
    try:
        os.replace(path, claim)
    except OSError:
        raise PickRefused("This pick was already used, or was not started here: start it again from the button.") from None
    try:
        row = json.loads(claim.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        row = {}
    finally:
        try:
            claim.unlink()
        except OSError:
            pass
    if not isinstance(row, dict) or float(row.get("expires", 0)) < time.time():
        raise PickRefused("The pick took too long and was not used: start it again from the button.")
    if str(row.get("by", "")) != by:
        raise PickRefused("The pick was started by someone else: start it again as yourself.")
    return row


def save_result(root: Path, *, by: str, purpose: str, slot: str, report: Report | None, error: str = "") -> str:
    """Keep what the page will read once; returns the opaque token the redirect carries."""
    token = secrets.token_urlsafe(18)
    folder = base(root) / "results"
    _sweep(folder)
    row = {"by": by, "purpose": purpose, "slot": slot, "error": error, "report": report.as_dict() if report else None,
           "expires": time.time() + RESULT_MINUTES * 60}
    _write_atomic(folder / f"{token}.json", json.dumps(row).encode("utf-8"))
    return token


def take_result(root: Path, token: str, *, by: str) -> dict[str, Any] | None:
    """Read a result once (it is removed as it is read); None when there is none, it is the wrong person's, or it expired."""
    if not TOKEN_RE.match(token or ""):
        return None
    path = base(root) / "results" / f"{token}.json"
    claim = path.with_name(path.stem + "." + secrets.token_hex(6) + ".claimed")
    try:
        os.replace(path, claim)
    except OSError:
        return None
    try:
        row = json.loads(claim.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    finally:
        try:
            claim.unlink()
        except OSError:
            pass
    if not isinstance(row, dict) or float(row.get("expires", 0)) < time.time() or str(row.get("by", "")) != by:
        return None
    row.pop("expires", None)
    return row


# --- the pick ---------------------------------------------------------------------------------------------------------------

def _refused(reason: str, words: str, name: str = "") -> Row:
    return Row(Outcome.REFUSED, reason, words, name=name)


def _peek_pages(data: bytes) -> int:
    from jason.tasks import split_session as ss

    return ss._peek_pages({"path": None, "data": data})


def _one(file_id: str, *, drive: Any, root: Path, community: Any, by: str, dry_run: bool) -> Row:
    from jason.tasks import drive_choose as dc

    try:
        meta = drive.file_metadata(file_id, dc.FIELDS)
    except Exception as exc:  # noqa: BLE001 - a Google refusal is told in jason's words, never with its text
        return _refused("no_access", dc.refusal_words(exc).replace("Nothing was picked.", "Nothing was kept."))
    name = str(meta.get("name") or "")
    mime = str(meta.get("mimeType") or "")
    if mime == dc.FOLDER_MIME_TYPE:
        return _refused("folder", "That is a folder. A folder picked here does not give jason its files: choose the PDFs "
                                  "themselves. Nothing was kept.", name)
    if mime != PDF:
        what = ("a " + dc.type_word(mime)) if mime else "not a PDF"
        return _refused("not_pdf", f"jason takes a PDF here, and that is {what}. Export it as a PDF in Google (File, Download, "
                                   "PDF) and choose that. Nothing was kept.", name)
    ok, why = dc.readable(meta)
    if not ok:
        return _refused("not_readable", f"jason cannot open this file: {why}. Nothing was kept.", name)
    size = dc._size(meta)
    if size is not None:
        try:
            limits.check("fetch.max_bytes", size, community=community, record=not dry_run)
        except limits.LimitReached as exc:
            return _refused("too_large", str(exc), name)
    if dry_run:
        return Row(Outcome.WOULD, words="Would be read once and held; the original in Drive is never changed.", size=size or 0,
                   name=name)
    try:
        if size is not None:
            storage.require_room(Path(root), size)
        data = drive.download_bytes(file_id)
    except storage.DriveShort as exc:
        return _refused("no_room", str(exc), name)
    except Exception as exc:  # noqa: BLE001
        return _refused("no_access", dc.refusal_words(exc).replace("Nothing was picked.", "Nothing was kept."), name)
    try:
        cap = int(limits.value("fetch.max_bytes", community=community))
        if len(data) > cap:
            raise limits.refusal("fetch.max_bytes", len(data), cap)
        if not data.lstrip()[:5].startswith(b"%PDF"):
            return _refused("not_pdf", "That file says it is a PDF but is not one jason can read. Nothing was kept.", name)
        pages = _peek_pages(data)
        limits.check("split.max_pages", pages, community=community, record=True)
    except limits.LimitReached as exc:
        return _refused("too_large" if exc.key == "fetch.max_bytes" else "too_many_pages", str(exc), name)
    except ValueError as exc:                    # the reader's words ("protected with a password", "damaged")
        return _refused("not_readable", str(exc), name)
    sha = hashlib.sha256(data).hexdigest()
    target = held_file(root, sha)
    already = target.is_file()
    if not already:
        try:
            storage.require_room(Path(root), len(data))
        except storage.DriveShort as exc:
            return _refused("no_room", str(exc), name)
        _write_atomic(target, data)
    note = provenance(root, sha)
    picks = list(note.get("picks") or [])
    picks.append({"by": by, "at": _now(), "via": VIA, "driveIdHash": _hash(file_id)[:16], "modified": str(meta.get("modifiedTime") or "")})
    note = {"sha256": sha, "size": len(data), "pages": pages, "mime": PDF, "confidential": _held(community, root, meta) or bool(note.get("confidential")),
            "picks": picks[-20:]}
    _write_atomic(_prov_file(root, sha), json.dumps(note, ensure_ascii=False).encode("utf-8"))
    return Row(Outcome.ALREADY if already else Outcome.HELD, words="Already held; nothing new was kept." if already else
               "Read once and held. The original in Drive was not changed.", held_id=sha, size=len(data), pages=pages, name=name)


def _held(community: Any, root: Path, meta: dict[str, Any]) -> bool:
    """Whether jason's own records class the file as confidential (as the splitter's Drive source does)."""
    try:
        from jason.tasks import drive_choose as dc

        return bool(dc.known(community, root).for_item(meta).get("held"))
    except Exception:  # noqa: BLE001 - a miss stays a miss
        return False


def pick(file_ids: list[str], *, by: str, drive: Any, root: Path, purpose: Purpose = Purpose.SPLIT, slot: str = "",
         community: Any = None, dry_run: bool = False) -> Report:
    """Read each picked id once and hold it (see the module). ``dry_run`` reads metadata only and keeps nothing. ``drive`` is a
    client with ``file_metadata`` and ``download_bytes`` (``jason.google.drive.GoogleDrive``); it is built from the person's
    one-time token by the caller, which drops the token."""
    from jason.tasks import record_slots as rs

    person = rs._who(by)
    report = Report(dry_run=dry_run)
    seen: set[str] = set()
    ids = [str(i).strip() for i in file_ids if str(i).strip()]
    if len(ids) > MAX_FILES:
        raise PickRefused(f"{len(ids)} files were picked; one pick takes at most {MAX_FILES}. Nothing was read.")
    for file_id in ids:
        if not ID_RE.match(file_id):
            report.rows.append(_refused("bad_id", "That is not a Drive file id. Nothing was kept."))
        elif file_id in seen:
            report.rows.append(_refused("duplicate", "That file was picked twice; it is read once."))
        else:
            seen.add(file_id)
            report.rows.append(_one(file_id, drive=drive, root=Path(root), community=community, by=person, dry_run=dry_run))
    if not dry_run:
        c = report.counts
        rs._append_history(Path(root), {"at": rs._now(), "profile": rs._profile(None, community), "act": "drive-pick", "by": person,
                                        "purpose": purpose.value, "picked": len(ids), "held": c["held"], "already": c["already held"],
                                        "refused": c["refused"],
                                        "heldIds": [r.held_id[:12] for r in report.rows if r.held_id]})
        log.info("drive-pick: %d picked, %d held, %d already, %d refused", len(ids), c["held"], c["already held"], c["refused"])
    return report


# --- the held copies ---------------------------------------------------------------------------------------------------------

def listing(root: Path, *, limit: int = 20, private: bool = False) -> dict[str, Any]:
    """The held copies, newest pick first, as a screen shows them: a number, a size, a page count, and the day of the last pick. No
    name (none is kept) and no Drive id. A confidential copy's size and pages, and its id, are withheld unless ``private`` (the private
    view is open); its row still says it is there. Read-only; disk only."""
    folder = held_dir(root)
    rows: list[dict[str, Any]] = []
    for pdf in sorted(folder.glob("*.pdf")) if folder.is_dir() else []:
        sha = pdf.stem
        if not _is_sha(sha):
            continue
        note = provenance(root, sha)
        picks = [p for p in (note.get("picks") or []) if isinstance(p, dict)]
        rows.append({"id": sha, "size": int(note.get("size") or pdf.stat().st_size), "pages": int(note.get("pages") or 0),
                     "at": str(picks[-1].get("at", "")) if picks else "", "confidential": bool(note.get("confidential"))})
    rows.sort(key=lambda r: r["at"], reverse=True)
    out = []
    for n, r in enumerate(rows[:max(1, limit)], start=1):
        hide = r["confidential"] and not private
        out.append({"n": n, "id": "" if hide else r["id"], "size": None if hide else r["size"], "pages": None if hide else r["pages"],
                    "day": r["at"][:10], "confidential": r["confidential"], "held": hide})
    return {"found": True, "copies": out, "total": len(rows),
            "note": "Copies jason read once from files you picked in your own Drive. Nothing is kept of their names."}


def purge(root: Path, *, dry_run: bool = True) -> dict[str, Any]:
    """Remove every held copy and its note. A dry run lists the count and bytes. Draft sessions that were opened from a held copy
    keep their own copy in the splitter's store; this removes the held originals only."""
    folder = held_dir(root)
    files = [p for p in folder.glob("*") if p.is_file()] if folder.is_dir() else []
    size = sum(p.stat().st_size for p in files)
    if not dry_run:
        for p in files:
            p.unlink()
    return {"dryRun": dry_run, "files": len(files), "bytes": size}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Held copies of files picked with Google's Picker.")
    ap.add_argument("--purge", action="store_true", help="remove every held copy (a dry run unless --yes)")
    ap.add_argument("--yes", action="store_true")
    ns = ap.parse_args(argv)
    from jason.mcp.county import _data_dir

    if not ns.purge:
        ap.print_help()
        return 0
    out = purge(Path(_data_dir(None)), dry_run=not ns.yes)
    print(("Would remove" if out["dryRun"] else "Removed"), f"{out['files']} files, {out['bytes']} bytes.",
          "Add --yes to remove them." if out["dryRun"] else "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
