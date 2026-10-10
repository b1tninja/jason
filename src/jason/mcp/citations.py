"""The statutes documents cite, and where each stands against the authorities shelf. Read only, from disk.

Two tools. ``document_citations`` is one source's citations: a reference work on the reference shelf, or the files the
last ``jason ingest`` read. ``citation_gaps`` is what all of them cite that the shelf lacks, with the proposal a person
adds as a row. Neither calls lawlibrary, PayHOA, Google, or Keeper: a survey that looked sections up in lawlibrary was
kept under ``data/citations`` by ``jason reference --cites``, and an ingest's survey is in its report. The governing
documents' own citations are ``document_references``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CAVEATS = (
    "Citations are read by a grammar: a range is read as its two ends, a citation the grammar misses stays missed, and a "
    "document is never said to cite nothing else.",
    "A standing is against the authorities shelf as it is now and, where the survey asked lawlibrary, the current publication "
    "when it was made. 'In the law, not exported' is a lead to add a row, not a pin; 'not in the current publication' can be "
    "the document's own error or a reading error: read the passage.",
    "A reference work explains a process. It is not the law and not the association's record: quote a section from the "
    "authorities shelf, never from the work.",
    "An ingest report names the association's files: it is private.",
)
# What a person looks at first.
_GAPS = ("NOT_FOUND", "NOT_EXPORTED", "RENUMBERED")


def _root(data_dir: Path | None) -> Path:
    from jason.config import Settings

    return Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent


def _row(row: Any) -> dict[str, Any]:
    return {"citation": row.citation, "standing": row.standing.name, "meaning": row.standing.value, "mentions": row.mentions,
            "citedBy": row.sources, "page": row.page, "subdivisions": sorted(row.subdivisions), "quote": row.quote}


def _order(rows: list[Any]) -> list[Any]:
    return sorted(rows, key=lambda r: (r.standing.name not in _GAPS, _GAPS.index(r.standing.name) if r.standing.name in _GAPS else 9,
                                       r.code, r.section))


def _view(name: str, result: Any, limit: int, **extra: Any) -> dict[str, Any]:
    rows = _order(result.rows)
    return {"found": True, "source": name, **extra, "lawChecked": result.law_checked, "counts": result.counts(), "total": len(rows),
            "shown": min(len(rows), limit), "sections": [_row(r) for r in rows[:limit]], "proposal": result.proposal(),
            "notes": result.notes, "caveats": list(CAVEATS)}


def _ingest_report(root: Path) -> tuple[Path | None, dict[str, Any]]:
    import json

    from jason.tasks.ingest import last_report

    path = last_report(root)
    if path is None:
        return None, {}
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return path, {}


def _sources(root: Path) -> list[dict[str, Any]]:
    from jason.community.reference_shelf import REFERENCE_WORKS, reference_dir
    from jason.tasks.citation_coverage import from_dict, saved

    kept = {s.get("name"): s for s in saved(root) if s.get("kind") == "reference"}
    found: list[dict[str, Any]] = []
    for work in REFERENCE_WORKS:
        raw = kept.get(work.title)
        found.append({"source": work.title, "kind": "reference work", "file": work.filename,
                      "onDisk": (reference_dir(root) / work.filename).is_file(), "surveyed": raw.get("made") if raw else None,
                      "counts": from_dict(raw, root).counts() if raw else None})
    path, report = _ingest_report(root)
    cited = report.get("citations")
    found.append({"source": "ingest", "kind": "the files the last jason ingest read", "report": path.name if path else None,
                  "counts": from_dict(cited, root).counts() if cited else None})
    return found


def document_citations(source: str = "", file: str = "", limit: int = 100, data_dir: Path | None = None) -> dict[str, Any]:
    """The statutes a source cites and where each stands against the authorities shelf: on it, in the law but not exported
    (a lead for a row), not in the current publication, a pre-2014 Davis-Stirling number, a regulation, or a code lawlibrary
    does not hold. With no ``source``: the sources that can be read (each reference work with whether it is on disk and
    when it was surveyed, and the last ingest). ``source`` a reference work (its file name or part of its title): its
    citations with the first page and sentence each appears in, counts by standing, and the proposal (the sections to add,
    as a duty's ``sections`` string). ``source`` "ingest": the files the last ``jason ingest`` read, with ``file`` (part of
    a file's path) narrowing to one. A section is placed against the shelf as it is now. Reads disk only. Citations are
    read by a grammar, a gap is a lead for a person, and a reference work is not the law: repeat the caveats."""
    try:
        root = _root(data_dir)
        limit = max(1, int(limit))
        if not source.strip():
            return {"sources": _sources(root), "note": "name a source: a reference work, or ingest", "caveats": list(CAVEATS)}
        from jason.tasks.citation_coverage import Survey, from_dict, saved, survey

        if source.strip().casefold() == "ingest":
            path, report = _ingest_report(root)
            if not report.get("citations"):
                return {"found": False, "note": "no ingest report with citations; run jason ingest SOURCE", "caveats": list(CAVEATS)}
            result = from_dict(report["citations"], root)
            if file.strip():
                wanted = file.strip().casefold()
                result = Survey([r for r in result.rows if any(wanted in s.casefold() for s in r.sources)], result.notes, result.law_checked)
            return _view("ingest", result, limit, report=path.name if path else "", file=file.strip())
        from jason.community.reference_shelf import find_work

        work = find_work(source)
        if work is None:
            return {"found": False, "note": f"no reference work {source!r}", "sources": _sources(root), "caveats": list(CAVEATS)}
        raw = next((s for s in saved(root) if s.get("kind") == "reference" and s.get("name") == work.title), None)
        if raw is not None:
            return _view(work.title, from_dict(raw, root), limit, made=raw.get("made"))
        from jason.community.reference_shelf import reference_dir

        text = reference_dir(root) / (Path(work.filename).stem + ".txt")
        if not text.is_file():
            return {"found": False, "source": work.title, "note": "not on disk; run jason reference --fetch", "caveats": list(CAVEATS)}
        result = survey({work.title: text.read_text(encoding="utf-8")}, root, external=True)
        return _view(work.title, result, limit, made=None,
                     note="read from the text against the shelf only; jason reference --cites looks the rest up in lawlibrary and keeps it")
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"error": f"{type(exc).__name__}: {exc}"}


def citation_gaps(limit: int = 100, data_dir: Path | None = None) -> dict[str, Any]:
    """What the surveyed documents cite that the authorities shelf lacks, all together: each section in the law but not
    exported, not found in the current publication, or cited by a pre-2014 Davis-Stirling number, with how often and by
    which sources, and one ``proposal`` (the sections to add as a row in ``jason.community.authorities``, as a duty's
    ``sections`` string). A section a survey called a gap is placed against the shelf as it is now, so one exported since
    is not listed. ``unchecked`` counts sections whose survey did not ask lawlibrary. Reads disk only. A gap is a lead for
    a person, who adds the row; jason adds nothing: repeat the caveats."""
    try:
        root = _root(data_dir)
        limit = max(1, int(limit))
        from jason.tasks.citation_coverage import Standing, from_dict, merge, saved

        raws = [s for s in saved(root)]
        path, report = _ingest_report(root)
        if report.get("citations"):
            raws.append({"name": "ingest", "kind": "ingest", "made": report.get("day"), **report["citations"]})
        if not raws:
            return {"found": False, "note": "no citation survey; run jason reference --cites WORK, or jason ingest SOURCE",
                    "caveats": list(CAVEATS)}
        combined = merge([from_dict(r, root) for r in raws])
        gaps = _order([r for r in combined.rows if r.standing.name in _GAPS])
        return {"found": True, "surveys": [{"name": r.get("name"), "kind": r.get("kind"), "made": r.get("made"),
                                            "lawChecked": bool(r.get("lawChecked"))} for r in raws],
                "total": len(gaps), "shown": min(len(gaps), limit), "gaps": [_row(r) for r in gaps[:limit]],
                "proposal": combined.proposal(), "unchecked": len(combined.of(Standing.UNCHECKED)), "caveats": list(CAVEATS)}
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"error": f"{type(exc).__name__}: {exc}"}


TOOLS = (document_citations, citation_gaps)
