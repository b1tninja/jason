"""The reference shelf and the statutes documents cite: four read-only loaders, from disk.

``reference_works(args)`` is ``GET /api/reference-works``: each published guide on the reference shelf with its author, year,
and how far to trust it, whether it is on disk, how many pages of text it has, and the survey kept for it (when, whether
lawlibrary was asked, and the counts by standing). ``citations(args)`` is ``GET /api/citations?source=&file=&limit=``
(``jason.mcp.citations.document_citations``): one source's cited sections and where each stands against the authorities
shelf. ``citation_gaps(args)`` is ``GET /api/citation-gaps?limit=``: what every surveyed source cites that the shelf lacks,
with the proposal a person adds as a row. ``reference_page(args)`` is ``GET /api/reference-page?work=&page=``: one page of
a work's text, to read beside a citation that names its page.

Nothing here calls lawlibrary, the county, or the network; a survey that asked lawlibrary was kept by ``jason reference
--cites``, and each section is placed against the shelf as it is now. A reference work is an explanation, not the law and
not the association's record: its page carries that as ``banner`` and the work's own ``caveat``. These are the board's
loaders: the owner view answers only its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

Args = dict[str, str]

BANNER = "An explanation, not the law and not the association's record."


def _root() -> Path:
    from jason.config import Settings

    return Settings.load().payhoa_catalog.parent


def _number(args: Args, key: str, default: int) -> int:
    raw = (args.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} is a number") from exc
    if value < 1:
        raise ValueError(f"{key} is a number from 1")
    return value


def reference_works(args: Args) -> dict[str, Any]:
    """GET /api/reference-works: the shelf's works, each with its caveat, its page count, and its kept survey."""
    from jason.community.reference_shelf import REFERENCE_WORKS, page_count, reference_dir
    from jason.mcp.citations import CAVEATS
    from jason.tasks.citation_coverage import from_dict, saved

    root = _root()
    kept = {s.get("name"): s for s in saved(root) if s.get("kind") == "reference"}
    works: list[dict[str, Any]] = []
    for work in REFERENCE_WORKS:
        raw = kept.get(work.title)
        survey = from_dict(raw, root) if raw else None
        works.append({
            "title": work.title, "file": work.filename, "author": work.author, "publisher": work.publisher, "year": work.year,
            "url": work.url, "covers": work.covers, "caveat": work.caveat, "topics": list(work.topics),
            "onDisk": (reference_dir(root) / work.filename).is_file(), "pages": page_count(root, work),
            "surveyed": raw.get("made") if raw else None, "lawChecked": survey.law_checked if survey else False,
            "counts": survey.counts() if survey else None,
            "command": f"jason reference --cites {work.filename}" if raw is None else None,
        })
    return {"works": works, "caveats": list(CAVEATS)}


def citations(args: Args) -> dict[str, Any]:
    """GET /api/citations?source=&file=&limit=: one source's citations (a reference work, or ``ingest``), or with no
    source the sources that can be read."""
    from jason.mcp.citations import document_citations

    return document_citations(args.get("source", ""), args.get("file", ""), _number(args, "limit", 100), data_dir=_root())


def citation_gaps(args: Args) -> dict[str, Any]:
    """GET /api/citation-gaps?limit=: the sections surveyed sources cite that the shelf lacks, and the proposal."""
    from jason.mcp.citations import citation_gaps as gaps

    return gaps(_number(args, "limit", 100), data_dir=_root())


def reference_page(args: Args) -> dict[str, Any]:
    """GET /api/reference-page?work=&page=: one page of a work's text. ``page`` counts PDF pages."""
    from jason.community.reference_shelf import find_work, page_count, page_text

    root = _root()
    page = _number(args, "page", 1)
    work = find_work(args.get("work", ""))
    if work is None:
        return {"found": False, "note": "name a reference work: its file name or part of its title"}
    pages = page_count(root, work)
    if not pages:
        return {"found": False, "work": work.title, "note": "not on disk", "command": "jason reference --fetch"}
    if page > pages:
        return {"found": False, "work": work.title, "pages": pages, "note": f"{work.title} has {pages} pages"}
    text = page_text(root, work, page)
    return {"found": True, "work": work.title, "file": work.filename, "author": work.author, "year": work.year, "page": page,
            "pages": pages, "text": text, "noText": not text, "banner": BANNER, "caveat": work.caveat}
