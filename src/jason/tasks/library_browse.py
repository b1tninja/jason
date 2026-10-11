"""The library explorer's backend (docs/pdf-splitter.md, "Choosing a file from the library"): the library's PDF files listed,
searched, filtered, sorted, and paged, for a person who picks one to split.

Disk only. It reads ``library/library.db`` read-only, stats each file under ``library/files`` and its cached text under
``library/text``, and reads jason's own split drafts. It calls no service (no Drive, no PayHOA, no Gmail) and writes nothing.

A row is one distinct file (the same bytes filed in two folders are one row, ``copies`` says how many). It carries the library's
id (what ``open`` takes), a display name, the kind the library read it as, where it came from, its pages, size, and dates, whether
jason holds its text, and whether a split draft exists for it.

- **Masked.** A file the library holds as confidential is shown as "a confidential file (kind: ...)" with no id until the private
  view is open, and a search never matches its name outside the private view (a hit would say what the name holds).
- **Search** is by name, kind, source, a range of days the file was last changed, whether jason holds its text, and a smallest page
  count; it sorts by name, kind, pages, size, or date; a page is at most ``MAX_PAGE`` rows and ``next`` is the token for the following
  one. The name searched for is a POST body at the web layer, never a URL.
- **Pages** are counted from the file, a page of rows at a time, and remembered by the file's path, size, and time. A
  filter or a sort on pages counts at most ``COUNT_BUDGET`` files (those counted before cost nothing) and says how many it did not reach
  (``uncounted``): it never reports a count it did not make.
- **Counts** for the filter chips are over the files that match every other filter, so a chip's number is what choosing it gives.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

PAGE = 50
MAX_PAGE = 100
MAX_SEARCH = 100
COUNT_BUDGET = 400
SORTS = ("modified", "name", "kind", "pages", "size")
SOURCE_LABELS = {"payhoa": "PayHOA", "drive": "Drive", "gmail": "Gmail", "ingest": "Taken in by hand"}
CAVEATS = (
    "This is what jason's library holds on this machine. A file that is in Drive or PayHOA but not in the library is not listed: "
    "choose From Drive, or upload it.",
    "Choosing a file opens a copy for splitting. The library's file is only read; it is never changed.",
    "A confidential file is named by its kind and opens in the private view.",
)


def _rows(root: Path) -> list[dict[str, Any]] | None:
    """The library's rows (joined to what ``jason ingest`` recorded), or None when there is no store."""
    db = Path(root) / "library" / "library.db"
    if not db.is_file():
        return None
    try:
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return None
    try:
        has_ingested = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'ingested'").fetchone())
        sql = ("SELECT d.id, d.source, d.path, d.name, d.kind, d.confidential, d.sha256, d.period, "
               + ("i.origin AS origin, i.ingested_at AS added" if has_ingested else "'' AS origin, '' AS added")
               + " FROM documents d" + (" LEFT JOIN ingested i ON i.id = d.id" if has_ingested else ""))
        return [dict(r) for r in conn.execute(sql)]
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def source_of(row: dict[str, Any]) -> str:
    """Where the library says a file came from: PayHOA, Drive, Gmail, or taken in by hand (``jason ingest``)."""
    source = str(row.get("source") or "").lower()
    origin = str(row.get("origin") or "").lower()
    if source == "ingest":
        if origin.startswith("drive:"):
            return "drive"
        if origin.startswith("gmail:"):
            return "gmail"
        return "ingest"
    return source or "ingest"


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


@lru_cache(maxsize=8192)
def _count_pages(path: str, stamp: str) -> int | None:
    """The page count of the file at ``path`` as it stood at ``stamp`` (its size and time, so a changed file is counted again; the
    path is under the data folder, so a cache entry belongs to one community). None when the file cannot be read as a PDF."""
    try:
        import pymupdf

        with pymupdf.open(path) as doc:
            return None if (doc.needs_pass or doc.is_encrypted) else int(doc.page_count)
    except Exception:  # noqa: BLE001 - a file that cannot be opened has no count
        return None


def _drafts(root: Path) -> dict[str, dict[str, str]]:
    """The newest open-or-finished split session on each library id: ``{id: {"id", "status"}}``."""
    from jason.tasks import split_session as ss

    out: dict[str, dict[str, str]] = {}
    for s in ss.sessions(root):                        # newest first
        if s.source.kind == "library" and s.source.ref and s.source.ref not in out:
            out[s.source.ref] = {"id": s.id, "status": s.status}
    return out


def _clamp(size: Any) -> int:
    try:
        return max(1, min(int(size), MAX_PAGE))
    except (TypeError, ValueError):
        return PAGE


def _word(value: Any) -> str:
    return " ".join(str(value or "").split())


def _flag(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _int(value: Any) -> int | None:
    try:
        return int(value) if str(value).strip() != "" else None
    except (TypeError, ValueError):
        return None


def files(root: Path, *, q: str = "", kind: str = "", source: str = "", since: str = "", until: str = "", has_text: Any = None,
          min_pages: Any = None, draft: Any = None, sort: str = "modified", order: str = "", size: Any = PAGE, page: str = "",
          private: bool = False) -> dict[str, Any]:
    """The library's PDFs matching the filters, a page at a time, with the counts a filter chip shows. See the module."""
    root = Path(root)
    clean = _word(q)
    if len(clean) > MAX_SEARCH:
        return {"found": False, "why": f"A search is at most {MAX_SEARCH} characters.", "caveats": list(CAVEATS)}
    sort = sort if sort in SORTS else "modified"
    descending = (order or ("desc" if sort in ("modified", "size", "pages") else "asc")).lower() != "asc"
    rows = _rows(root)
    if rows is None:
        return {"found": False, "why": "jason has no library on this machine yet. A person runs `jason library`; until then, choose "
                                       "From Drive or From this computer.", "command": "jason library", "caveats": list(CAVEATS)}
    held_kinds = _held_kinds()
    base = Path(root) / "library"
    drafts = _drafts(root)
    seen: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not str(r.get("path") or "").lower().endswith(".pdf"):
            continue
        key = r.get("sha256") or f"{str(r.get('name') or '').casefold()}|{r.get('period') or ''}|{r.get('kind') or ''}"
        if key in seen:                                  # the same bytes filed again: one row
            seen[key]["copies"] += 1
            seen[key]["held"] = seen[key]["held"] or bool(r.get("confidential"))
            continue
        path = base / "files" / str(r["path"])
        try:
            st = path.stat()
            on_disk, nbytes, mtime = True, int(st.st_size), st.st_mtime
        except OSError:
            on_disk, nbytes, mtime = False, None, 0.0
        try:
            text_size = (base / "text" / f"{r['id']}.txt").stat().st_size
        except OSError:
            text_size = 0
        k = str(r.get("kind") or "")
        seen[key] = {"_row": r, "_path": path, "_stamp": f"{nbytes}:{int(mtime * 1e9)}", "id": str(r["id"]), "kind": k,
                     "name": str(r.get("name") or "") or str(r["path"]).rsplit("/", 1)[-1],
                     "source": source_of(r), "size": nbytes, "modified": _day(mtime) if on_disk else "",
                     "added": str(r.get("added") or "")[:10], "hasText": text_size > 0, "onDisk": on_disk, "copies": 1,
                     "held": bool(r.get("confidential")) or k in held_kinds, "draft": drafts.get(str(r["id"]))}
    everything = list(seen.values())

    needle = clean.casefold()

    def passes(f: dict[str, Any], skip: str = "") -> bool:
        if skip != "kind" and kind and (f["kind"] or "(none)") != kind:
            return False
        if skip != "source" and source and f["source"] != source:
            return False
        if needle and (f["held"] and not private or needle not in f["name"].casefold()):
            return False
        if since and (not f["modified"] or f["modified"] < since[:10]):
            return False
        if until and (not f["modified"] or f["modified"] > until[:10]):
            return False
        wanted = _flag(has_text)
        if wanted is not None and f["hasText"] != wanted:
            return False
        wanted = _flag(draft)
        if wanted is not None and bool(f["draft"]) != wanted:
            return False
        return True

    matched = [f for f in everything if passes(f)]
    counts = {"kinds": _tally(f["kind"] or "(none)" for f in everything if passes(f, "kind")),
              "sources": _tally(f["source"] for f in everything if passes(f, "source")),
              "files": len(matched), "all": len(everything), "noText": sum(1 for f in matched if not f["hasText"]),
              "withDraft": sum(1 for f in matched if f["draft"]), "notHere": sum(1 for f in matched if not f["onDisk"])}

    smallest = _int(min_pages)
    uncounted = 0
    if smallest is not None or sort == "pages":
        budget = COUNT_BUDGET
        for f in matched:
            if not f["onDisk"]:
                f["pages"] = None
            elif budget > 0:
                budget -= 1
                f["pages"] = _count_pages(str(f["_path"]), f["_stamp"])
            else:
                f["pages"] = None
                uncounted += 1
        if smallest is not None:
            matched = [f for f in matched if f["pages"] is not None and f["pages"] >= smallest]

    def key_of(f: dict[str, Any]):
        if sort == "name":
            return (f["name"].casefold(), f["id"])
        if sort == "kind":
            return (f["kind"] or "~", f["name"].casefold())
        if sort == "pages":
            return (f.get("pages") is None, f.get("pages") or 0, f["name"].casefold())
        if sort == "size":
            return (f["size"] is None, f["size"] or 0, f["name"].casefold())
        return (not f["modified"], f["modified"], f["name"].casefold())

    ordered = sorted(matched, key=key_of, reverse=descending)
    if sort in ("pages", "size", "modified") and descending:       # a file with no value sorts last either way
        ordered = [f for f in ordered if _has_value(f, sort)] + [f for f in ordered if not _has_value(f, sort)]
    start = _int(page) or 0
    start = max(0, start)
    step = _clamp(size)
    window = ordered[start:start + step]
    out_rows = []
    for f in window:
        if "pages" not in f:
            f["pages"] = _count_pages(str(f["_path"]), f["_stamp"]) if f["onDisk"] else None
        out_rows.append(_shown(f, private))
    log.info("library browse: %d of %d files", len(out_rows), len(matched))
    return {"found": True, "files": out_rows, "total": len(matched), "next": str(start + step) if start + step < len(ordered) else None,
            "counts": counts, "uncounted": uncounted, "sort": sort, "order": "desc" if descending else "asc",
            "empty": ("Nothing in the library matches. Clear a filter or the search." if not out_rows and everything else
                      "The library holds no PDF files yet." if not out_rows else ""),
            "caveats": list(CAVEATS)}


def _has_value(f: dict[str, Any], sort: str) -> bool:
    return bool(f.get("pages") is not None) if sort == "pages" else f["size"] is not None if sort == "size" else bool(f["modified"])


def _tally(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def _held_kinds() -> frozenset[str]:
    from jason.community.library import CONFIDENTIAL_KINDS

    return frozenset(k.value for k in CONFIDENTIAL_KINDS)


def _shown(f: dict[str, Any], private: bool) -> dict[str, Any]:
    masked = f["held"] and not private
    name = f["name"]
    if masked:
        name = f"a confidential file (kind: {(f['kind'] or 'unclassified').replace('_', ' ')})"
    reason = ""
    if not f["onDisk"]:
        reason = "this machine does not hold the file; fetch it first (jason ingest)"
    elif f.get("pages") is None:
        reason = "jason could not read this file as a PDF (it may be protected or damaged)"
    return {"id": "" if masked else f["id"], "name": name, "kind": f["kind"], "source": f["source"],
            "sourceLabel": SOURCE_LABELS.get(f["source"], f["source"] or "unknown"), "pages": f.get("pages"), "size": f["size"],
            "modified": f["modified"], "added": f["added"], "hasText": f["hasText"], "draft": None if masked else f["draft"],
            "held": f["held"], "copies": f["copies"], "onDisk": f["onDisk"], "openable": f["onDisk"] and not masked,
            "why": reason, "opens": "opens in the private view" if masked else ""}


__all__ = ["CAVEATS", "COUNT_BUDGET", "MAX_PAGE", "PAGE", "SORTS", "files", "source_of"]
