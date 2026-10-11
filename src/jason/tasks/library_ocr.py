"""OCR of a library file, as a background job (docs/pdf-splitter.md section 9.5, docs/record-intake.md Phase 4).

A split part taken in by the library intake is read for its text layer only, so a request never waits on OCR. A part that is a
scan has no words yet. This module queues one job per such part, on the local lane, in the confirming person's name, and the worker
runs ``jason library --ocr-doc ID --yes --by NAME``. The job reads the file with the engines that run on this machine without the
model server (``jason.community.ocr.local_engines``: Docling with RapidOCR, Tesseract) and keeps the words beside the library's
cached text, so every reader of ``library.text_for`` sees them. The vision model is a second text layer a person asks for
(``jason library --vision``); it is not part of this job, so the job needs no GPU and holds no GPU lock.

Idempotent by file hash: a file whose cached note names an OCR source and the library row's hash is skipped, and so is one that
already has a text layer. Nothing here names a file: job arguments, results, and history hold library ids and counts.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason import limits

LIMIT_KEY = "split.ocr_queue_max"
HAS_WORDS = 200                  # characters of text that make a file "has a text layer" (the library's own threshold)


def _row(root: Path, doc_id: str) -> dict[str, Any] | None:
    db = Path(root) / "library" / "library.db"
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT path, sha256 FROM documents WHERE id = ? LIMIT 1", (str(doc_id),)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return None if row is None else {"path": row[0], "sha256": row[1] or ""}


def _note(root: Path, doc_id: str) -> dict[str, Any]:
    from jason.tasks.library import TEXT_DIR

    try:
        return json.loads((Path(root) / TEXT_DIR / f"{doc_id}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def needs_ocr(root: Path, doc_id: str) -> tuple[bool, str]:
    """Whether the library file still needs OCR, and when it does not, why (in words, no file name)."""
    from jason.tasks import library as library_task

    row = _row(root, doc_id)
    if row is None:
        return False, "not in the library"
    note = _note(root, doc_id)
    if str(note.get("source") or "").startswith("ocr") and str(note.get("sha256") or "") == row["sha256"]:
        return False, "already read by OCR (same file hash)"
    if len(library_task.text_for(Path(root), doc_id).strip()) >= HAS_WORDS:
        return False, "has a text layer"
    return True, ""


def _argv(doc_id: str, by: str) -> list[str]:
    return ["library", "--ocr-doc", str(doc_id), "--yes", "--by", by]


def _pending(root: Path) -> set[str]:
    """Library ids with an OCR job queued or running."""
    from jason import jobs

    out: set[str] = set()
    for job in jobs.jobs(Path(root), limit=1000):
        a = job.argv
        if a[:1] == ["library"] and "--ocr-doc" in a and job.status.value in ("queued", "running"):
            out.add(a[a.index("--ocr-doc") + 1])
    return out


def plan(root: Path, doc_ids: list[str], *, community: Any = None) -> dict[str, Any]:
    """What queueing would do for these library ids, in the order given: ``queue``, ``skipped``, and ``notQueued`` (over the
    ``split.ocr_queue_max`` limit, or not in the library). Reads only."""
    cap = int(limits.value(LIMIT_KEY, community=community))
    pending = _pending(root)
    queue: list[str] = []
    skipped: list[dict[str, str]] = []
    over: list[dict[str, str]] = []
    for doc_id in dict.fromkeys(str(d) for d in doc_ids if d):
        needed, why = needs_ocr(root, doc_id)
        if doc_id in pending:
            skipped.append({"libraryId": doc_id, "why": "an OCR job is already queued for it"})
        elif not needed:
            if why == "not in the library":
                over.append({"libraryId": doc_id, "why": why})
            else:
                skipped.append({"libraryId": doc_id, "why": why})
        elif len(queue) >= cap:
            over.append({"libraryId": doc_id, "why": str(limits.refusal(LIMIT_KEY, len(queue) + 1, cap))})
        else:
            queue.append(doc_id)
    return {"queue": queue, "skipped": skipped, "notQueued": over, "limit": cap}


def queue(root: Path, doc_ids: list[str], by: str, *, community: Any = None) -> dict[str, Any]:
    """Queue one OCR job for each library file that needs it, on the local lane, in ``by``'s name. Never reads a file inline."""
    from jason import jobs

    p = plan(root, doc_ids, community=community)
    queued: list[dict[str, Any]] = []
    not_queued = list(p["notQueued"])
    for doc_id in p["queue"]:
        try:
            job = jobs.add(Path(root), _argv(doc_id, by), confirmed_by=by, job_class_override=jobs.JobClass.LOCAL)
        except jobs.JobRefused as exc:
            not_queued.append({"libraryId": doc_id, "why": str(exc)})
            continue
        queued.append({"libraryId": doc_id, "job": job.id})
    return {"ocrQueued": queued, "ocrSkipped": p["skipped"], "notQueued": not_queued}


def run(root: Path, doc_id: str, by: str, *, engines: Any = None) -> dict[str, Any]:
    """The job: OCR one library file and keep the words beside its cached text. Fails fast (RuntimeError) when no engine runs here.
    ``engines`` is for a test. Returns ``{"libraryId", "read", "why"|"engine", "chars"}``; the file's name is never in it."""
    from jason.community import ocr
    from jason.locks import Resource, hold
    from jason.tasks.library import TEXT_DIR

    root = Path(root)
    needed, why = needs_ocr(root, doc_id)
    if not needed:
        return {"libraryId": doc_id, "read": False, "why": why, "chars": 0}
    found = tuple(ocr.local_engines() if engines is None else engines)
    if not found:
        raise RuntimeError("no OCR engine runs on this machine (install Tesseract or docling[rapidocr]); nothing was read")
    row = _row(root, doc_id) or {}
    path = root / "library" / "files" / str(row.get("path") or "")
    if not path.is_file():
        raise RuntimeError("the library knows the file but this machine does not hold it; fetch it first")
    text, engine = "", ""
    for candidate in found:
        try:
            read = candidate.text_of(path)
        except Exception:  # noqa: BLE001 - the next engine tries
            continue
        if len(read.strip()) >= HAS_WORDS:
            text, engine = read, str(getattr(candidate, "name", type(candidate).__name__))
            break
    if not text:
        return {"libraryId": doc_id, "read": False, "why": "no engine read words from it", "chars": 0}
    folder = root / TEXT_DIR
    with hold(Resource.STORE, "library", timeout=120, purpose="jason library --ocr-doc"):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{doc_id}.txt").write_text(text, encoding="utf-8")
        note = {**_note(root, doc_id), "source": f"ocr: {engine}", "sha256": row["sha256"], "chars": len(text),
                "ocrBy": by, "ocrAt": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        (folder / f"{doc_id}.json").write_text(json.dumps(note), encoding="utf-8")
    return {"libraryId": doc_id, "read": True, "engine": engine, "chars": len(text)}
