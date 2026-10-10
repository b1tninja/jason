"""The PDF splitter's suggestions, read only (docs/pdf-splitter.md, 7.3). One tool, ``split_suggestions``.

It reads what a session saved on disk: its status, page count, the boundaries a person chose, and the suggestions jason made with their
confidence, tier, and reason in words. It never runs the suggestion engine, a model, or the renderer, opens no file, and changes
nothing: marking and applying a split are a person's, in the console or at the command line. A suggestion is evidence, not a pin.
A confidential file is held back unless asked, because a reason quotes the page's own words.
"""

from __future__ import annotations

from typing import Any

CAVEATS = ("A suggestion is jason's guess from the pages' shapes, with the reasons shown. It is evidence, not a boundary and not a pin: "
           "only a person marks where a document starts, and only a person's confirmation writes any file.",
           "This tool reads what a session saved. It never runs the engine and cannot open, edit, or apply a split.")


def _root() -> Any:
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def split_suggestions(session: str = "", library_id: str = "", include_confidential: bool = False) -> dict[str, Any]:
    """The PDF splitter's saved drafts for one session id (``session``) or one library file (``library_id``): status, page count, the
    boundaries a person chose, the segments they make, and jason's suggested first pages, each with its confidence, band, tier, and
    reason. With neither argument, the sessions in short. Reads disk only. A confidential file's suggestions are held back unless
    ``include_confidential`` is true. A suggestion is evidence for a person to accept or reject; it is not a pin."""
    from pathlib import Path

    from jason.tasks import split_session as ss

    try:
        root = Path(_root())
        sid, lib = (session or "").strip(), (library_id or "").strip()
        if not sid and not lib:
            return {"found": True, "sessions": ss.listing(root), "caveats": list(CAVEATS)}
        found = ss.find(root, session=sid, library=lib.removeprefix("library:"))
        if not found:
            return {"found": False, "session": sid, "libraryId": lib, "caveats": list(CAVEATS)}
        rows = []
        for s in found:
            held = ss.is_confidential(root, s) and not include_confidential
            row: dict[str, Any] = {"id": s.id, "status": s.status, "pages": s.pages, "updated": s.updated, "version": s.version,
                                   "counts": s.counts(), "confidential": ss.is_confidential(root, s)}
            if held:
                row["heldBack"] = ("This file is confidential. Its boundaries and suggestions are held back; ask for them with "
                                   "include_confidential when the question needs them.")
            else:
                row["boundaries"] = [b.page for b in s.ordered()]
                row["segments"] = [{"key": g.key, "start": g.start, "end": g.end, "level": g.level} for g in s.segments()]
                row["suggestions"] = [x.to_dict() for x in s.suggestions if x.state == "open"]
                row["suggestedAt"] = s.suggested_at
            rows.append(row)
        return {"found": True, "sessions": rows, "caveats": list(CAVEATS)}
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"found": False, "error": f"{type(exc).__name__}: {exc}", "caveats": list(CAVEATS)}


TOOLS = (split_suggestions,)
