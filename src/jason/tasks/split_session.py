"""The PDF splitter's sessions (docs/pdf-splitter.md): open a file, keep a draft of where its documents start, suggest, and apply.

A session lives in ``<data>/split/sessions/<id>.json`` (``jason.community.split_session``); the file it is about is copied once into
``<data>/split/sources/<sha256[:2]>/<sha256>.pdf`` so every picture and every cut reads one copy that cannot change under it, and the
page facts it was drawn from are kept in ``<data>/split/facts/<sha256[:2]>/<sha256>.json`` (shared by every session on the same bytes).
Two entries to the same bytes resume the same draft. The original, in the library or on this machine, is only read.

- ``open_session``: the file's hash, its page count (``split.max_pages``), the copy, and the first facts and suggestions.
- ``act``: one change to a draft (mark, move, clear, range, label, undo, redo, suggest, accept, reject, decline), held to the draft's
  ``version`` so a second writer is told of a conflict (``SplitConflict``) and never overwrites.
- ``review`` and ``apply``: the review of what would be written (counts, collisions, duplicates), and the write, through the record
  intake's one split writer (``record_upload.plan_parts`` and ``write_part``): a **dry run unless a person confirms**. Nothing here
  applies a split on its own; the original is never changed.

Every write names a person (``by``; never jason), holds the session's store lock, writes only jason's own stores, and leaves one line in
``records/history.jsonl`` with the session id and counts, never a file name or a page's text.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from jason import limits, storage
from jason.community import split_suggest
from jason.community.split_session import PageFact, Source, SplitConflict, SplitSession, new_id, now
from jason.tasks import record_slots as rs

FOLDER = "split"
INLINE_PAGES = 60                    # a file this short has its facts and first suggestions made as it opens; a longer one is a job
ID_FORM = re.compile(r"^[0-9a-f]{8}$")
CAVEATS = (
    "A suggestion is jason's guess from the pages' shapes, with the reasons shown; it is not a boundary until a person accepts it.",
    "A split writes new files of just the pages a person marked, through the record intake's own writer. The original is never changed.",
)


# --- where things are kept -------------------------------------------------------------------------------------------------

def _root(root: Path | None) -> Path:
    return rs._root(root)


def split_dir(root: Path) -> Path:
    return Path(root) / FOLDER


def session_file(root: Path, sid: str) -> Path:
    if not ID_FORM.match(str(sid or "")):
        raise KeyError(sid)
    return split_dir(root) / "sessions" / f"{sid}.json"


def source_file(root: Path, sha256: str) -> Path:
    return split_dir(root) / "sources" / sha256[:2] / f"{sha256}.pdf"


def facts_file(root: Path, sha256: str) -> Path:
    return split_dir(root) / "facts" / sha256[:2] / f"{sha256}.json"


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def load(root: Path, sid: str) -> SplitSession:
    try:
        raw = json.loads(session_file(root, sid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise KeyError(sid) from None
    return SplitSession.from_dict(raw)


def save(root: Path, session: SplitSession) -> None:
    _write_json(session_file(root, session.id), session.to_dict())


def sessions(root: Path) -> list[SplitSession]:
    out = []
    for path in sorted((split_dir(root) / "sessions").glob("*.json")) if (split_dir(root) / "sessions").is_dir() else ():
        try:
            out.append(SplitSession.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, ValueError, KeyError):
            continue
    return sorted(out, key=lambda s: s.updated, reverse=True)


def _locked(root: Path, sid: str):
    from jason.locks import Resource, hold

    return hold(Resource.STORE, f"split-{sid}", timeout=60, purpose="pdf splitter")


# --- the file --------------------------------------------------------------------------------------------------------------

def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _library_row(root: Path, doc_id: str) -> dict[str, Any] | None:
    db = Path(root) / "library" / "library.db"
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT path, sha256, confidential FROM documents WHERE id = ? LIMIT 1", (str(doc_id),)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return None if row is None else {"path": row[0], "sha256": row[1] or "", "confidential": bool(row[2])}


def _resolve(ref: dict[str, Any], root: Path) -> dict[str, Any]:
    """Where the bytes come from: ``{"path": Path | None, "data": bytes | None, "kind", "ref", "confidential", "stamp"}``. A ref is
    ``{"kind": "library", "id"}``, ``{"kind": "path", "path"}`` (a person's own machine: the command line), ``{"kind": "upload", "name",
    "base64"}`` (the console), or ``{"kind": "drive"}`` (not built: a Drive pick is copied to the library or uploaded first)."""
    kind = str(ref.get("kind") or ("library" if ref.get("id") else "path" if ref.get("path") else "")).strip().lower()
    if kind == "library":
        row = _library_row(root, str(ref.get("id") or ""))
        if row is None:
            raise ValueError("the library holds no file with that id; nothing was opened")
        path = Path(root) / "library" / "files" / row["path"]
        if not path.is_file():
            raise ValueError("the library knows that file but this machine does not hold it; fetch it first (jason ingest)")
        st = path.stat()
        return {"path": path, "data": None, "kind": kind, "ref": str(ref["id"]), "confidential": row["confidential"],
                "stamp": f"{st.st_size}:{st.st_mtime_ns}"}
    if kind == "path":
        path = Path(str(ref.get("path") or "")).expanduser()
        if not path.is_file():
            raise ValueError("no such file on this machine; nothing was opened")
        st = path.stat()
        return {"path": path, "data": None, "kind": kind, "ref": "", "confidential": bool(ref.get("confidential")),
                "stamp": f"{st.st_size}:{st.st_mtime_ns}"}
    if kind == "upload":
        import base64

        raw = str(ref.get("base64") or "")
        if not raw:
            raise ValueError("an upload carries the file's bytes")
        cap = int(limits.value("upload.max_bytes"))
        if len(raw) > (cap // 3 + 2) * 4 + 4:
            raise limits.refusal("upload.max_bytes", len(raw) // 4 * 3, cap)
        try:
            data = base64.b64decode(raw.split(",", 1)[-1] if raw.startswith("data:") else raw, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("the upload is not base64") from exc
        from jason.tasks import record_upload

        name = str(ref.get("name") or "scan.pdf")
        clean, _what = record_upload.check(name, data, cap)
        if not clean.lower().endswith(".pdf"):
            raise ValueError("the splitter takes a PDF")
        return {"path": None, "data": data, "kind": kind, "ref": "", "confidential": False, "stamp": ""}
    if kind == "drive":
        raise ValueError("A Drive file is split from a copy: put it in the library or upload it first (picking from Drive comes "
                         "with the record chooser's join). Nothing was opened.")
    raise ValueError("a file to split is a library id, a path on this machine, or an upload")


def _ingest(root: Path, found: dict[str, Any]) -> tuple[str, int]:
    """Copy the bytes into the splitter's own store, once, addressed by hash. Returns (sha256, size). The temp-drive guard speaks first."""
    path, data = found["path"], found["data"]
    size = len(data) if data is not None else path.stat().st_size
    storage.require_room(Path(root), size)
    stage = split_dir(root) / "sources" / "_incoming"
    stage.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=stage, suffix=".part")
    h = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as out:
            if data is not None:
                h.update(data)
                out.write(data)
            else:
                with open(path, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                        out.write(chunk)
        sha = h.hexdigest()
        target = source_file(root, sha)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            os.unlink(tmp_name)
        else:
            os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return sha, size


def _peek_pages(found: dict[str, Any]) -> int:
    """The page count of the file before anything is kept, so a file over the limit leaves nothing behind."""
    if found["path"] is not None:
        return _read_pdf(found["path"])
    tmp = Path(tempfile.mkdtemp(prefix="split-peek-"))
    try:
        peek = tmp / "peek.pdf"
        peek.write_bytes(found["data"])
        return _read_pdf(peek)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _read_pdf(path: Path) -> int:
    """The page count, or a refusal in words for a file that cannot be read."""
    try:
        import pymupdf

        with pymupdf.open(str(path)) as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise ValueError("This file could not be read: it is protected with a password. Remove the password in the original "
                                 "program, or upload a copy without one. Nothing was opened.")
            if doc.page_count < 1:
                raise ValueError("This file could not be read: it has no pages. Nothing was opened.")
            return int(doc.page_count)
    except ValueError:
        raise
    except ImportError as exc:
        raise ValueError("No PDF reader is installed on this machine (the pdf extra), so a file cannot be opened.") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"This file could not be read ({type(exc).__name__}): it may be damaged. Nothing was opened.") from exc


def is_confidential(root: Path, session: SplitSession) -> bool:
    """Whether the file is confidential now: a library file is asked again each time (the flag may have been set since), any other
    keeps what it was opened with."""
    if session.source.kind == "library" and session.source.ref:
        row = _library_row(root, session.source.ref)
        if row is not None:
            return bool(row["confidential"])
    return bool(session.source.confidential)


def view_of(root: Path, session: SplitSession) -> dict[str, Any]:
    """The session as a screen reads it, with a confidential file's reference withheld (the flag is read again here)."""
    return session.view(mask=is_confidential(root, session))


def find(root: Path, *, session: str = "", library: str = "") -> list[SplitSession]:
    """The sessions with this id, or on this library file (newest first)."""
    if session:
        try:
            return [load(root, session)]
        except KeyError:
            return []
    return [s for s in sessions(root) if library and s.source.kind == "library" and s.source.ref == library]


# --- the facts -------------------------------------------------------------------------------------------------------------

def scan(path: Path, *, lqip: bool = True, progress: Callable[[int, int], None] | None = None) -> tuple[list[PageFact], list[Any]]:
    """The per-page facts of a PDF and the segmentation's page rows: one pass over the text layer
    (``jason.tasks.segments.read_pages``), then one over the images (``pdf_preflight``'s own image and colour readers; a page with
    no image is not drawn for its colour). The file is only read."""
    import pymupdf

    from jason.community import pdf_preflight as pf
    from jason.tasks import segments

    infos, _toc = segments.read_pages(path)
    facts = split_suggest.facts_from_pages(infos)
    out: list[PageFact] = []
    with pymupdf.open(str(path)) as doc:
        for i, fact in enumerate(facts):
            page = doc[i]
            images = pf.image_facts(doc, page)
            main = pf._main_image(images)
            colour = ""
            if images:
                try:
                    colour = pf.color_mode(doc, page, images).value
                except Exception:  # noqa: BLE001
                    colour = ""
            tiny = ""
            if lqip:
                try:
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(16 / max(page.rect.width, 1), 16 / max(page.rect.height, 1)),
                                          colorspace=pymupdf.csGRAY, alpha=False, annots=False)
                    tiny = bytes(pix.samples)[:256].hex()
                except Exception:  # noqa: BLE001
                    tiny = ""
            out.append(PageFact(**{**fact.__dict__, "rotation": int(page.rotation or 0), "dpi": main.dpi if main else 0, "colour": colour,
                                   "codec": main.codec if main else "", "lqip": tiny}))
            if progress:
                progress(i + 1, len(facts))
    return out, infos


def ensure_facts(root: Path, sha256: str, *, progress: Callable[[int, int], None] | None = None) -> list[PageFact]:
    """The page facts of the file with this hash: read from the cache, else measured now and kept. Reads the splitter's copy only."""
    cached = read_facts(root, sha256)
    if cached:
        return cached
    facts, _infos = scan(source_file(root, sha256), lqip=True, progress=progress)
    _write_json(facts_file(root, sha256), {"version": 1, "sha256": sha256, "pages": [f.to_dict() for f in facts]})
    return facts


def read_facts(root: Path, sha256: str) -> list[PageFact]:
    try:
        raw = json.loads(facts_file(root, sha256).read_text(encoding="utf-8"))
        return [PageFact.from_dict(p) for p in raw["pages"]]
    except (OSError, ValueError, KeyError):
        return []


def facts_view(root: Path, sid: str, first: int = 1, last: int = 0, *, lqip: bool = True) -> dict[str, Any]:
    """The facts of pages ``first`` to ``last`` as a screen draws its placeholders. A page not measured yet is ``pending``."""
    session = load(root, sid)
    facts = read_facts(root, session.source.sha256)
    last = last or session.pages
    first = max(1, first)
    rows = []
    for n in range(first, min(last, session.pages) + 1):
        f = facts[n - 1].to_dict() if n - 1 < len(facts) else PageFact(n, pending=True).to_dict()
        if not lqip:
            f.pop("lqip", None)
        rows.append(f)
    return {"id": sid, "pages": session.pages, "ready": len(facts), "facts": rows}


# --- opening ---------------------------------------------------------------------------------------------------------------

def _history(root: Path, row: dict[str, Any]) -> None:
    rs._append_history(root, {"at": rs._now(), **row})


def find_resumable(root: Path, sha256: str) -> SplitSession | None:
    for s in sessions(root):
        if s.source.sha256 == sha256 and s.status in ("draft", "confirmed"):
            return s
    return None


def open_session(ref: dict[str, Any], *, by: str, dry_run: bool = False, suggest: bool = True, facts: bool | None = None,
                 community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Open a file for splitting, or resume the draft on the same bytes. ``dry_run`` says what would happen and keeps nothing (no copy,
    no session). A file over ``split.max_pages`` is refused in the limit's words before anything is kept. Small files get their facts
    and the first suggestions now; a longer one is left with its facts pending for a job (``queue_facts``)."""
    root = _root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    found = _resolve(ref, root)
    pages = _peek_pages(found)
    limits.check("split.max_pages", pages, community=community, record=not dry_run)
    if dry_run:
        size = len(found["data"]) if found["data"] is not None else found["path"].stat().st_size
        return {"dryRun": True, "would": {"act": "open", "pages": pages, "size": size, "by": person,
                                          "keeps": "a copy of the file under the splitter's own folder and a draft session"},
                "note": "A dry run: nothing was kept. Add --yes to open the file.", "caveats": list(CAVEATS)}
    sha, size = _ingest(root, found)
    existing = find_resumable(root, sha)
    if existing is not None:
        return {"ok": True, "resumed": True, "session": view_of(root, existing), "caveats": list(CAVEATS)}
    stamp = now()
    session = SplitSession(new_id(), Source(sha, size, pages, found["kind"], found["ref"] or ("upload:" + sha[:12] if found["kind"] == "upload" else ""),
                                            found["confidential"], found["stamp"]), "draft", stamp, stamp, person, 1)
    session.mark(1, level=0, by=person, at=stamp)
    session.undo, session.version = [], 1
    save(root, session)
    out: dict[str, Any] = {"ok": True, "resumed": False}
    inline = (pages <= INLINE_PAGES) if facts is None else facts
    if inline:
        ensure_facts(root, sha)
        if suggest and _suggestions_on(community):
            _suggest(root, session, person, community)
    else:
        session.notes.append("Page facts are not measured yet; they fill in as the background job runs.")
        save(root, session)
        out["factsPending"] = True
    _history(root, {"profile": profile, "act": "split-open", "session": session.id, "by": person, "pages": pages})
    out["session"] = view_of(root, session)
    out["caveats"] = list(CAVEATS)
    return out


def queue_facts(root: Path, sid: str, by: str) -> dict[str, Any]:
    """Queue the facts and the first suggestions of a long file as a job on the local lane, in the person's name."""
    from jason import jobs

    argv = ["split", sid, "--facts", "--by", rs._who(by), "--yes"]
    job = jobs.add(_root(root), argv, confirmed_by=by, job_class_override=jobs.JobClass.LOCAL)
    return {"job": job.id, "command": "jason " + " ".join(argv)}


def build_facts(sid: str, *, by: str, suggest: bool = True, community: Any = None, root: Path | None = None,
                progress: Callable[[int, int], None] | None = None, profile: str | None = None) -> dict[str, Any]:
    """Measure every page of the session's file and keep the facts, then run the rule pass. The job a long file's open queues."""
    root = _root(root)
    person = rs._who(by)
    session = load(root, sid)
    facts = ensure_facts(root, session.source.sha256, progress=progress)
    out: dict[str, Any] = {"ok": True, "id": sid, "pages": len(facts)}
    if suggest and _suggestions_on(community):
        with _locked(root, sid):
            session = load(root, sid)
            session.notes = [n for n in session.notes if not n.startswith("Page facts are not measured")]
            out["suggestions"] = _suggest(root, session, person, community)
    return out


# --- suggestions -----------------------------------------------------------------------------------------------------------

def _suggestions_on(community: Any) -> bool:
    return bool(limits.value("split.suggest_enabled", community=community))


def _suggest(root: Path, session: SplitSession, by: str, community: Any) -> int:
    """The rule pass over the session's pages; the suggestions replace the old ones, the boundaries are not touched. Saves."""
    from jason.tasks import segments

    facts = ensure_facts(root, session.source.sha256)
    infos, _toc = segments.read_pages(source_file(root, session.source.sha256))
    session.replace_suggestions(split_suggest.suggest(facts, infos))
    save(root, session)
    return len([s for s in session.suggestions if s.state == "open"])


def suggest(sid: str, *, by: str, community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Run the cheap suggestion pass again. Refused in the limit's words when suggestions are off for this community."""
    root = _root(root)
    person = rs._who(by)
    limits.check("split.suggest_enabled", True, community=community)
    with _locked(root, sid):
        session = load(root, sid)
        n = _suggest(root, session, person, community)
        return {"ok": True, "id": sid, "open": n, "version": session.version, "session": view_of(root, session)}


# --- the acts on a draft ---------------------------------------------------------------------------------------------------

DRAFT_ACTS = ("boundaries", "mark", "unmark", "move", "level", "clear", "range", "label", "undo", "redo", "accept", "reject")


def _pages(value: Any) -> list[int]:
    if value in (None, "", []):
        return []
    if isinstance(value, str):
        out: list[int] = []
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            a, _, b = part.partition("-")
            out += list(range(int(a), int(b or a) + 1))
        return out
    if isinstance(value, int):
        return [value]
    return [int(v) for v in value]


def _do_act(session: SplitSession, act: str, body: dict[str, Any], person: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if act == "boundaries":
        rows = body.get("boundaries")
        if rows is None:
            rows = [(p, 0) for p in _pages(body.get("pages"))]
        session.set_boundaries(rows, by=person)
    elif act == "mark":
        for p in _pages(body.get("pages", body.get("page"))):
            session.mark(p, level=int(body.get("level") or 0), by=person)
    elif act == "unmark":
        for p in _pages(body.get("pages", body.get("page"))):
            session.unmark(p, by=person)
    elif act == "move":
        session.move(int(body["from"]), int(body["to"]), by=person)
    elif act == "level":
        session.set_level(int(body["page"]), int(body.get("level") or 0), by=person)
    elif act == "clear":
        pages = _pages(body.get("pages")) or None
        out["cleared"] = session.clear(pages, by=person)
    elif act == "range":
        out["added"] = session.mark_range(int(body["first"]), int(body["last"]), every=int(body.get("every") or 1),
                                          level=int(body.get("level") or 0), by=person)
    elif act == "label":
        session.label(int(body["page"]), str(body.get("field") or ""), str(body.get("value") or ""), by=person)
    elif act == "undo":
        out["undone"] = session.do_undo(by=person)
    elif act == "redo":
        out["redone"] = session.do_redo(by=person)
    elif act == "accept":
        which = str(body.get("id") or "").strip()
        if which.lower() in ("all", "high"):
            out["accepted"] = session.accept_all(minimum=0.85, by=person)
        elif which.lower() == "medium":
            out["accepted"] = session.accept_all(minimum=0.6, by=person)
        else:
            ids = [i for i in re.split(r"[,\s]+", which) if i]
            if not ids:
                raise ValueError("accept names a suggestion (g12), a list, or all (High and better)")
            for i in ids:
                session.accept(i, by=person)
            out["accepted"] = len(ids)
    elif act == "reject":
        ids = [i for i in re.split(r"[,\s]+", str(body.get("id") or "")) if i]
        if not ids:
            raise ValueError("reject names a suggestion (g12) or a list")
        for i in ids:
            session.reject(i, by=person)
        out["rejected"] = len(ids)
    else:
        raise ValueError(f"an act on a draft is one of {', '.join(DRAFT_ACTS)}")
    return out


def act(sid: str, name: str, body: dict[str, Any] | None = None, *, by: str, version: int | None = None, dry_run: bool = False,
        community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """One change to a draft. ``version`` is the draft's version the caller started from; a draft that has moved on raises
    ``SplitConflict`` with the server's copy. ``dry_run`` makes the change on a copy and keeps nothing."""
    root = _root(root)
    person = rs._who(by)
    body = dict(body or {})
    if name not in DRAFT_ACTS:
        raise ValueError(f"an act on a draft is one of {', '.join(DRAFT_ACTS)}")
    with _locked(root, sid):
        session = load(root, sid)
        if version is not None and int(version) != session.version:
            raise SplitConflict("The draft changed since you opened it (another tab or person). Nothing was saved; compare and choose.",
                                view_of(root, session))
        _check_not_stale(root, session)
        before = session.version
        result = _do_act(session, name, body, person)
        if not dry_run and session.version != before:
            save(root, session)
        elif dry_run:
            result["dryRun"] = True
        return {"ok": True, "act": name, **result, "version": session.version, "changed": session.version != before,
                "session": view_of(root, session)}


def decline(sid: str, *, by: str, note: str = "", dry_run: bool = True, root: Path | None = None, community: Any = None,
            profile: str | None = None) -> dict[str, Any]:
    """A person looked at the draft and wants none of it. Records it and changes no file."""
    root = _root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    text = rs._words(note, "note", required=False)
    with _locked(root, sid):
        session = load(root, sid)
        if session.status == "applied":
            raise ValueError("this split was applied; it cannot be declined")
        if dry_run:
            return {"dryRun": True, "would": {"act": "decline", "id": sid, "by": person},
                    "note": "A dry run: nothing was written. Add --yes to record that you want none of this split."}
        session.status = "declined"
        session.applied = {"declined": {"by": person, "at": now(), "note": text}}
        session.version += 1
        session.updated = now()
        save(root, session)
    _history(root, {"profile": profile, "act": "split-decline", "session": sid, "by": person})
    return {"dryRun": False, "ok": True, "declined": True, "id": sid}


def _check_not_stale(root: Path, session: SplitSession) -> None:
    """A library file whose size or time changed since the session opened is stale: the draft is for the old bytes."""
    src = session.source
    if src.kind != "library" or not src.stamp or session.status != "draft":
        return
    row = _library_row(root, src.ref)
    if row is None:
        return
    path = Path(root) / "library" / "files" / row["path"]
    try:
        st = path.stat()
    except OSError:
        return
    if f"{st.st_size}:{st.st_mtime_ns}" != src.stamp:
        session.status = "stale"
        session.notes.append("This file changed after you started. Your marks are for the old version, kept here. Open the file "
                             "again to start a new draft.")
        save(root, session)
        raise ValueError("This file changed after you started. Your marks are for the old version, kept here; open the file again "
                         "to start a new draft.")


# --- review and apply ------------------------------------------------------------------------------------------------------

def _runs(pages: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for p in sorted(pages):
        if out and p == out[-1][1] + 1:
            out[-1] = (out[-1][0], p)
        else:
            out.append((p, p))
    return out


def _part_items(session: SplitSession, parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The files the draft would make, in page order: every top-level segment, and each nested segment a person asked to also make a file."""
    given = {str(p.get("segment") or ""): p for p in parts}
    items = []
    n = 0
    for seg in session.segments():
        lab = session.label_of(seg.start)
        if seg.level > 0 and lab.get("nested") != "file":
            continue
        n += 1
        over = given.get(seg.key, {})
        items.append({"segment": seg.key, "level": seg.level, "start": seg.start, "end": seg.end, "ordinal": n,
                      "slot": str(over.get("slot") or lab.get("slot") or ""), "period": str(over.get("period") or lab.get("period") or ""),
                      "entry": str(over.get("entry") or lab.get("entry") or ""),
                      "title": str(over.get("title") or lab.get("title") or ""), "kind": lab.get("kind") or None})
    return items


def _known_hashes(root: Path, profile: str) -> dict[str, str]:
    """Hashes of files jason already holds: slot pins and the library. Value: where, in words (no file name)."""
    held: dict[str, str] = {}
    for p in rs.load_store(profile).get("pins") or ():
        if p.get("sha256") and not p.get("unpinned"):
            held.setdefault(str(p["sha256"]), f"a file pinned to {p.get('slot', 'a slot')}")
    db = Path(root) / "library" / "library.db"
    if db.is_file():
        try:
            conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
            try:
                for (sha, doc_id) in conn.execute("SELECT sha256, id FROM documents WHERE sha256 IS NOT NULL AND sha256 != ''"):
                    held.setdefault(str(sha), f"library file {doc_id}")
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    return held


def _held_in_store(root: Path, profile: str, sha256: str) -> bool:
    """Whether jason's record-intake store already keeps these bytes (it addresses a file by the first 16 of its hash)."""
    from jason.tasks import record_upload

    folder = record_upload.folder(root, profile) / sha256[:16]
    return folder.is_dir() and any(folder.iterdir())


def review(sid: str, *, parts: list[dict[str, Any]] | tuple[Any, ...] = (), drop: list[int] | None = None, keep_copies: bool = False,
           community: Any = None, root: Path | None = None, profile: str | None = None, hashes: bool = True) -> dict[str, Any]:
    """What applying the draft would do, written nowhere: each file with its pages and slot, the pages left out, the totals, the
    collisions with slots that hold a file, and the duplicates of files jason already holds. ``hashes`` cuts each part in memory to
    hash it (a large file takes a while); without it duplicates are not checked."""
    from jason.tasks import record_upload

    root = _root(root)
    profile = rs._profile(profile, community)
    session = load(root, sid)
    items = _part_items(session, [dict(p) if isinstance(p, dict) else record_upload._parse_part(p) for p in parts])
    dropped = sorted(set(int(p) for p in (drop or ())))
    for p in dropped:
        session._check_page(p)
    top = [i for i in items if i["level"] == 0]
    if not top:
        raise ValueError("there are no segments to write")
    source = source_file(root, session.source.sha256)
    known = _known_hashes(root, profile) if hashes else {}
    rows, problems = [], []
    for it in items:
        pages = [p for p in range(it["start"], it["end"] + 1) if p not in dropped]
        if not pages:
            raise ValueError(f"segment {it['segment']} would be empty after the pages left out; merge it or keep its pages")
        row = {**it, "pages": _runs(pages), "count": len(pages), "name": f"Part {it['ordinal']} of {len(items)} (pages {it['start']}-{it['end']})",
               "action": "held" if not it["slot"] else "fill"}
        if hashes:
            data = record_upload.cut_pages(source, row["pages"])
            row["sha256"] = hashlib.sha256(data).hexdigest()
            row["size"] = len(data)
            twin = known.get(row["sha256"]) or ("a file already held in jason's store" if _held_in_store(root, profile, row["sha256"]) else "")
            if twin and not keep_copies:
                row.update({"action": "duplicate", "why": f"identical to {twin}; it will not be written again", "of": twin})
        rows.append(row)
    wanted = [r for r in rows if r["action"] == "fill"]
    if wanted:
        computed = rs.compute(community, root, profile)
        planned = record_upload.plan_parts(community, computed, [{**r, "pages": (r["pages"][0][0], r["pages"][-1][1])} for r in wanted])
        for r, plan in zip(wanted, planned):
            r["action"] = plan["action"]
            r.update({k: v for k, v in plan.items() if k in ("why", "kept", "fits")})
    in_files = sum(r["count"] for r in rows if r["level"] == 0)
    totals_ok = in_files + len(dropped) == session.pages
    if not totals_ok:
        problems.append(f"the pages do not add up: {in_files} in files + {len(dropped)} left out is not {session.pages}")
    limits.check("split.max_parts", len(rows), community=community, record=False)
    return {"id": sid, "status": session.status, "version": session.version, "sourcePages": session.pages, "files": len(rows),
            "parts": rows, "dropped": dropped, "pagesInFiles": in_files, "totalsOk": totals_ok, "problems": problems,
            "collisions": [r["slot"] for r in rows if r["action"] == "collision"],
            "duplicates": [r["segment"] for r in rows if r["action"] == "duplicate"],
            "held": [r["segment"] for r in rows if r["action"] == "held"],
            "result": f"{len(rows)} new files; the original is kept untouched", "caveats": list(CAVEATS)}


def apply(sid: str, *, by: str, parts: list[dict[str, Any]] | tuple[Any, ...] = (), drop: list[int] | None = None, keep_copies: bool = False,
          confirm: bool = False, dry_run: bool | None = None, community: Any = None, root: Path | None = None,
          profile: str | None = None) -> dict[str, Any]:
    """Write the new files. A **dry run unless a person confirms** (``confirm=True``): it returns the review and writes nothing. On
    confirm the session becomes ``confirmed`` (who, when, the final boundary list), each part is written through the record
    intake's writer in page order, and the session becomes ``applied``. A part that fails leaves the session ``confirmed`` with the
    parts already written recorded, and the apply can be run again for the rest. Nothing is deleted; the original is not touched."""
    from jason.tasks import record_upload

    root = _root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    if not confirm:                          # nothing is written without a person's confirmation, whatever else was passed
        dry_run = True
    elif dry_run is None:
        dry_run = False
    plan = review(sid, parts=parts, drop=drop, keep_copies=keep_copies, community=community, root=root, profile=profile)
    if dry_run:
        return {"dryRun": True, "would": {"act": "apply", "id": sid, "by": person, "files": plan["files"]}, "review": plan,
                "note": "A dry run: nothing was written. Confirm as a person (--yes) to write the files."}
    if not plan["totalsOk"]:
        raise ValueError("; ".join(plan["problems"]))
    with _locked(root, sid):
        session = load(root, sid)
        if session.status == "applied":
            raise ValueError("this split was applied already; nothing was written again")
        if session.status not in ("draft", "confirmed"):
            raise ValueError(f"this split is {session.status}; open the file again to split it")
        source = source_file(root, session.source.sha256)
        if sha256_of(source) != session.source.sha256:
            session.status = "stale"
            save(root, session)
            raise ValueError("the splitter's copy of the file changed since it was opened; open the file again")
        _check_not_stale(root, session)
        if session.status != "confirmed":
            session.status = "confirmed"
            session.confirmed = {"by": person, "at": now(), "boundaries": ",".join(str(b.page) for b in session.ordered())}
            session.version += 1
            save(root, session)
        done = {p["segment"]: p for p in (session.applied.get("parts") or ())}
        made: list[dict[str, Any]] = list(done.values())
        failed: list[dict[str, Any]] = []
        source_ref = f"session:{session.id}"
        for row in plan["parts"]:
            if row["segment"] in done:
                continue
            if row["action"] in ("collision", "duplicate"):
                made.append({"segment": row["segment"], "action": row["action"], "slot": row.get("slot", ""), "why": row.get("why", ""),
                             "of": row.get("of", "")})
                continue
            try:
                data = record_upload.cut_pages(source, [tuple(r) for r in row["pages"]])
                prov = {"splitSession": session.id, "splitSource": session.source.sha256, "pages": {"ranges": row["pages"], "of": session.pages},
                        "segment": {"key": row["segment"], "level": row["level"], "title": row["title"], "kind": row["kind"],
                                    "kindIsGuess": True}, "confirmedBy": {"name": person, "at": session.confirmed.get("at", "")},
                        "ordinal": row["ordinal"]}
                label = f"Part-{row['ordinal']}-pages-{row['start']}-{row['end']}.pdf"
                if row["action"] == "fill":
                    why = f"pages {row['start']}-{row['end']} of a scan split in the PDF splitter, confirmed"
                    got = record_upload.write_part(root, profile, community, {**row, "pages": (row["start"], row["end"])}, data, by=person,
                                                   why=why, source_pin=source_ref, extra=prov, label=label)
                    made.append({**got, "action": "filled", "sha256": row.get("sha256", ""), "ordinal": row["ordinal"]})
                else:
                    kept = record_upload.keep_held(root, profile, data, label)
                    made.append({"segment": row["segment"], "action": "held", "ordinal": row["ordinal"], **kept})
            except Exception as exc:  # noqa: BLE001 - one part that cannot be written stops the rest and is reported
                failed.append({"segment": row["segment"], "why": f"{type(exc).__name__}: {str(exc)[:200]}"})
                break
            session.applied = {"parts": made, "partial": True, "by": person}
            save(root, session)
        out: dict[str, Any] = {"dryRun": False, "ok": not failed, "id": sid, "filled": [m for m in made if m.get("action") == "filled"],
                               "held": [m for m in made if m.get("action") == "held"],
                               "skipped": [m for m in made if m.get("action") in ("collision", "duplicate")], "failed": failed,
                               "dropped": plan["dropped"], "caveats": list(CAVEATS)}
        if failed:
            session.applied = {"parts": made, "partial": True, "by": person, "failed": failed}
            save(root, session)
            out["note"] = "Some parts were written; the apply can be run again for the rest. Nothing was deleted."
            return out
        auto = bool(limits.value("split.auto_read", community=community))
        slotted = [m for m in out["filled"] if m.get("pin")]
        if auto and slotted:
            out.update(record_upload.queue_reads(root, slotted, person))
        elif slotted:
            out["reading"] = "the new files are not read yet (the split.auto_read limit is off): jason records --read SLOT for each"
        out["autoRead"] = auto
        if out["held"]:
            out["notQueued"] = [{"segment": m["segment"], "why": "held with no slot yet; read it when it is filed"} for m in out["held"]]
        session.status = "applied"
        session.applied = {"parts": made, "partial": False, "by": person, "at": now(), "dropped": plan["dropped"]}
        session.version += 1
        session.updated = now()
        save(root, session)
    _history(root, {"profile": profile, "act": "split-apply", "session": sid, "by": person, "files": len(made), "dropped": len(plan["dropped"]),
                    "slots": sorted({m["slot"] for m in made if m.get("slot")}), "pins": [m["pin"] for m in made if m.get("pin")],
                    "boundaries": session.confirmed.get("boundaries", "")})
    return out


# --- listing, retention, purge ---------------------------------------------------------------------------------------------

def listing(root: Path | None = None, *, mask_confidential: bool = True) -> list[dict[str, Any]]:
    """The sessions, newest first: id, status, pages, counts, updated. No file name, ever."""
    root = _root(root)
    out = []
    for s in sessions(root):
        c = s.counts()
        out.append({"id": s.id, "status": s.status, "pages": s.pages, "segments": c["segments"], "suggestionsOpen": c["suggestionsOpen"],
                    "updated": s.updated, "by": s.by, "confidential": s.source.confidential, "kind": s.source.kind,
                    "label": "a confidential file" if (mask_confidential and s.source.confidential) else f"{s.pages} pages, {s.source.sha256[:8]}"})
    return out


def _unreferenced(root: Path, keep: set[str]) -> int:
    """Remove the copy, facts, and pictures of every hash no remaining session needs. Returns the bytes freed."""
    from jason.tasks import split_thumbs

    needed = {s.source.sha256 for s in sessions(root) if s.status in ("draft", "confirmed")} | keep
    freed = 0
    base = split_dir(root) / "sources"
    for shard in (base.iterdir() if base.is_dir() else ()):
        if not shard.is_dir() or shard.name == "_incoming":
            continue
        for f in shard.glob("*.pdf"):
            if f.stem not in needed:
                try:
                    freed += f.stat().st_size
                    f.unlink()
                except OSError:
                    pass
                facts = facts_file(root, f.stem)
                if facts.is_file():
                    facts.unlink()
                freed += split_thumbs.purge(root, f.stem)
    return freed


def purge(*, sid: str = "", all_drafts: bool = False, dry_run: bool = True, by: str = "", root: Path | None = None,
          community: Any = None, profile: str | None = None) -> dict[str, Any]:
    """Drop a draft (or every draft) with its copy, facts, and page pictures. Never an original, and never an applied session's record."""
    root = _root(root)
    profile = rs._profile(profile, community)
    chosen = [s for s in sessions(root) if (s.id == sid if sid else all_drafts) and s.status != "applied"]
    if sid and not chosen:
        raise KeyError(sid)
    if dry_run:
        return {"dryRun": True, "would": {"act": "purge", "sessions": [s.id for s in chosen]},
                "note": "A dry run: nothing was removed. Add --yes. Originals and applied splits are never removed."}
    person = rs._who(by)
    for s in chosen:
        session_file(root, s.id).unlink(missing_ok=True)
    freed = _unreferenced(root, set())
    _history(root, {"profile": profile, "act": "split-purge", "by": person, "sessions": [s.id for s in chosen], "freed": freed})
    return {"dryRun": False, "ok": True, "removed": [s.id for s in chosen], "freed": freed}


def sweep(*, dry_run: bool = True, community: Any = None, root: Path | None = None, today: datetime | None = None,
          profile: str | None = None) -> dict[str, Any]:
    """The retention sweep: a draft (or a declined or stale one) not changed for ``split.draft_days`` days is removed with its copy and
    pictures. An applied split's record stays; only its leftover copy and pictures go once no draft needs them."""
    root = _root(root)
    days = int(limits.value("split.draft_days", community=community))
    cutoff = (today or datetime.now(timezone.utc)) - timedelta(days=days)
    old = []
    for s in sessions(root):
        try:
            changed = datetime.fromisoformat(s.updated)
        except ValueError:
            continue
        if changed < cutoff and s.status in ("draft", "stale", "declined"):
            old.append(s.id)
    if dry_run:
        return {"dryRun": True, "would": {"act": "sweep", "sessions": old, "days": days}}
    for sid in old:
        session_file(root, sid).unlink(missing_ok=True)
    return {"dryRun": False, "ok": True, "removed": old, "freed": _unreferenced(root, set()), "days": days}

