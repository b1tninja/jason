"""Read-through for the statutes shelf: a section a reader asks for and no page holds is asked of lawlibrary.

``jason export-authorities`` writes the curated list (``jason.community.authorities``). A reader that misses
(``authority_text``, and through it ``jason cite``, the evidence resolver, the packets and rule-change notices, and the
MCP tools) calls ``ensure``: it asks the local lawlibrary checkout for that section or span (no internet; its own
environment), writes the page in the export's layout and header with the edition, the day, and that it came on
demand, and lists it under ``on_demand`` in the manifest, holding the shelf's store lock. Each attempt is a line in
``data/authorities/on-demand.jsonl``. The export keeps an on-demand page until a curated span holds its sections,
and prints those that none does, so a person can promote them with a Basis and a reason; the curated list stays the
person's.

A miss stays a miss, with its reason told apart: lawlibrary does not hold the section (an edition it has not
indexed, or no such section), the checkout is not there, or its worker failed. Text is only ever what lawlibrary
returned and this module wrote to disk. JASON_AUTHORITIES_FETCH=0 turns the read-through off (the tests do).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.authorities import LAWLIBRARY_CODES, number_key
from jason.sources.lawlibrary import LawLibrary

FETCH_ENV = "JASON_AUTHORITIES_FETCH"
ON_DEMAND_LOG = "on-demand.jsonl"
# A miss is not asked again in the same process for this long (a reader looping over citations spawns no worker per hit).
MISS_MEMORY_SECONDS = 3600


class Miss(Enum):
    """Why a read-through brought nothing back."""

    NOT_IN_LIBRARY = "not_in_library"            # lawlibrary has no such section in the editions it indexes
    LIBRARY_UNAVAILABLE = "library_unavailable"  # no checkout at lawlibrary_home (or no settings to find it)
    WORKER_FAILED = "worker_failed"              # the checkout is there; its worker failed or timed out
    FETCH_OFF = "fetch_off"                      # JASON_AUTHORITIES_FETCH=0: the disk only


_REASONS = {
    Miss.NOT_IN_LIBRARY: "not on the shelf, and lawlibrary does not hold it (a code or edition it has not indexed, or no such section)",
    Miss.LIBRARY_UNAVAILABLE: "not on the shelf, and the lawlibrary checkout is not available to look it up",
    Miss.WORKER_FAILED: "not on the shelf, and lawlibrary's worker failed while looking it up",
    Miss.FETCH_OFF: "not in the exported authorities; the read-through is off",
}


@dataclass(frozen=True)
class Fetched:
    code: str
    start: str
    end: str
    found: bool
    page: str = ""
    session: str = ""
    miss: Miss | None = None
    detail: str = ""

    @property
    def citation(self) -> str:
        return f"{self.code} {self.start}" if self.start == self.end else f"{self.code} {self.start}-{self.end}"

    def reason_text(self) -> str:
        return _REASONS.get(self.miss, "") if self.miss else ""


_misses: dict[tuple[str, str, str, str], tuple[float, Fetched]] = {}


def enabled() -> bool:
    return os.environ.get(FETCH_ENV, "1").strip().lower() not in ("0", "false", "no", "off")


def default_library() -> LawLibrary:
    """The checkout the settings name (lawlibrary_home), as ``Jason.lawlibrary`` builds it."""
    from jason.config import Settings

    return LawLibrary(Settings.load().lawlibrary_home)


_OWN = {__name__, "jason.tasks.export_authorities"}


def caller(depth: int = 3) -> str:
    """The modules that asked, nearest first ("jason.tasks.cite < jason.approvals.evidence"), for the log."""
    names: list[str] = []
    frame = sys._getframe(1)
    while frame is not None and len(names) < depth:
        name = str(frame.f_globals.get("__name__") or "")
        if name and name not in _OWN and (not names or names[-1] != name):
            names.append(name)
        frame = frame.f_back
    return " < ".join(names)


def _slug(citation: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", citation).strip("-")


def _held(root: Path, code: str, start: str, end: str):
    """An on-demand page already holding the span (another process may have written it while this one waited)."""
    from jason.tasks.export_authorities import on_demand_pages

    for page in on_demand_pages(root):
        if page.code == code and number_key(page.start) <= number_key(start) and number_key(end) <= number_key(page.end) \
                and (root / page.file).is_file():
            return page
    return None


def _log(root: Path, got: Fetched, asked_by: str) -> None:
    from jason.tasks.export_authorities import AUTHORITIES_DIR

    path = root / AUTHORITIES_DIR / ON_DEMAND_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "code": got.code,
           "section": got.start if got.start == got.end else f"{got.start}-{got.end}", "edition": got.session,
           "found": got.found, "reason": got.miss.value if got.miss else "", "detail": got.detail, "page": got.page,
           "asked_by": asked_by}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def log_rows(root: Path) -> list[dict[str, Any]]:
    """Every read-through attempt, oldest first."""
    from jason.tasks.export_authorities import AUTHORITIES_DIR

    path = Path(root) / AUTHORITIES_DIR / ON_DEMAND_LOG
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def ensure(root: Path, code: str, start: str, end: str | None = None, *, asked_by: str = "",
           library: LawLibrary | None = None) -> Fetched:
    """Bring one section or span onto the shelf from lawlibrary, or say why not. Nothing is written on a miss."""
    root = Path(root)
    code = code.strip().upper()
    end = end or start
    if code not in LAWLIBRARY_CODES:
        return Fetched(code, start, end, False, miss=Miss.NOT_IN_LIBRARY, detail="not a code on lawlibrary's California shelf")
    if not enabled():
        return Fetched(code, start, end, False, miss=Miss.FETCH_OFF)
    key = (str(root.resolve()), code, start, end)
    memo = _misses.get(key)
    if memo and time.monotonic() - memo[0] < MISS_MEMORY_SECONDS:
        return memo[1]
    from jason.locks import Resource, hold
    from jason.tasks.export_authorities import STORE_KEY

    with hold(Resource.STORE, STORE_KEY, purpose=f"fetch {code} {start}"):
        page = _held(root, code, start, end)
        if page is not None:
            return Fetched(code, start, end, True, page=page.file, session=page.session)
        got = _fetch(root, code, start, end, asked_by, library)
        _log(root, got, asked_by)
    if not got.found:
        _misses[key] = (time.monotonic(), got)
    return got


def _fetch(root: Path, code: str, start: str, end: str, asked_by: str, library: LawLibrary | None) -> Fetched:
    try:
        lib = library or default_library()
    except Exception as exc:  # noqa: BLE001 - settings that cannot be read leave no checkout to ask
        return Fetched(code, start, end, False, miss=Miss.LIBRARY_UNAVAILABLE, detail=f"{type(exc).__name__}: {exc}"[:300])
    if not lib.available():
        return Fetched(code, start, end, False, miss=Miss.LIBRARY_UNAVAILABLE,
                       detail=f"lawlibrary checkout not found at {lib.home}; set lawlibrary_home in .env")
    try:
        spans = lib.spans([(code, start, end)])
    except Exception as exc:  # noqa: BLE001 - LawLibraryUnavailable, a timeout, or unreadable output: a miss
        return Fetched(code, start, end, False, miss=Miss.WORKER_FAILED, detail=f"{type(exc).__name__}: {exc}"[-300:])
    if not spans or not spans[0].found:
        return Fetched(code, start, end, False, miss=Miss.NOT_IN_LIBRARY,
                       detail="lawlibrary's index has no such section in the editions it holds")
    return _write(root, code, start, end, spans[0].sections, asked_by)


def _write(root: Path, code: str, start: str, end: str, sections, asked_by: str) -> Fetched:
    from dataclasses import asdict

    from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, Page, _Want, heading_title, page_markdown, read_manifest

    citation = f"{code} {start}" if start == end else f"{code} {start}-{end}"
    session = sections[0].session
    title = heading_title(sections[0].heading)
    today = date.today().isoformat()
    fetched = f"{today}, on demand" + (f" (asked by {asked_by})" if asked_by else "")
    path = root / AUTHORITIES_DIR / code / (_slug(citation) + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page_markdown(citation, title, _Want(code, start, end, None, ()), sections, root, fetched=fetched),
                    encoding="utf-8")
    page = Page(path.relative_to(root).as_posix(), citation, title, code, start, end, [s.number for s in sections],
                "", [], session, fetched=today, asked_by=asked_by)
    from jason.tasks.authority_digests import page_digests

    page.digests = page_digests(root, page)
    manifest = read_manifest(root)
    rows = [p for p in manifest.get("on_demand") or [] if p.get("file") != page.file]
    manifest["on_demand"] = rows + [asdict(page)]
    (root / AUTHORITIES_DIR / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return Fetched(code, start, end, True, page=page.file, session=session)


def promotions(root: Path, curated=None) -> list[dict[str, Any]]:
    """The on-demand pages no curated span (``authorities()`` unless given) holds, each with the readers that asked:
    leads for a person to add to ``jason.community.authorities`` with a Basis and a reason."""
    from jason.community.authorities import authorities, section_in
    from jason.tasks.export_authorities import on_demand_pages

    curated = [a for a in (authorities() if curated is None else curated) if a.exportable]
    asked: dict[str, set[str]] = {}
    for row in log_rows(root):
        if row.get("found") and row.get("page"):
            asked.setdefault(str(row["page"]), set()).add(str(row.get("asked_by") or ""))
    out: list[dict[str, Any]] = []
    for page in on_demand_pages(root):
        if page.sections and all(any(a.code == page.code and section_in(a, n) for a in curated) for n in page.sections):
            continue
        out.append({"citation": page.citation, "title": page.title, "file": page.file, "session": page.session,
                    "fetched": page.fetched, "asked_by": sorted(x for x in asked.get(page.file, {page.asked_by}) if x)})
    return out
