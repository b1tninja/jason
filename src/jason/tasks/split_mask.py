"""What the splitter says about a confidential file (docs/pdf-splitter.md, section 8, "Confidential files").

A confidential file's page text is the board's private view (P3). Everything the splitter reads back from its saved drafts is built from
the page text: a printed header or footer, a title, a date, the reason in words behind a suggestion, the title or kind a segment was
labelled with. Before the private view is open, a screen, a command, or a tool gets only numbers, states, and codes.

This module is the one place that decides. Every reader of a session (the session view, the page facts, the review, the console's
loaders, the command line, the MCP tool) passes its answer through these functions; none of them has an ``if confidential`` of its own.

- ``Standing``: whether the file is confidential now, and whether the library could be asked. When it could not (the library database
  was busy or unreadable) the file is treated as confidential and the words say so: a flag that cannot be read is never read as "no".
- ``hide_text(standing, private)``: whether text-derived fields are withheld. ``private`` is True only where the private view is open
  for the viewer (a console request) or a person explicitly asked for it; outside a request it is False.
- ``session_view`` / ``facts`` / ``review``: the withheld form of each answer. They never change their argument.

Pure: no file, library, or profile is read here, except ``private_open``, which asks the web layer whether this request has the
private view open.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BUSY_WORDS = ("The library could not be read just now (it may be busy), so this file is treated as confidential until it can be. "
              "Page text is withheld. Try again in a moment.")
HELD_WORDS = ("This file is confidential. Page text (headers, titles, dates, and the reasons behind suggestions) is withheld; "
              "it opens in the private view.")

# The per-page facts that come from the page's text or picture. Counts, sizes, states, and measured degrees stay.
TEXT_FACT_FIELDS = ("header", "footer", "title", "date", "phash", "lqip")
# The labels a person or a guess put on a segment that are words. ``slot``, ``period``, ``entry`` and ``nested`` are codes.
TEXT_LABELS = ("title", "kind")
TEXT_REVIEW_FIELDS = ("title", "kind")


@dataclass(frozen=True)
class Standing:
    """Whether the file is confidential now. ``known`` is False when the library could not be asked (then ``confidential`` is True)."""

    confidential: bool
    known: bool = True
    why: str = ""

    @property
    def words(self) -> str:
        return self.why or (HELD_WORDS if self.confidential else "")


def private_open() -> bool:
    """True when this request has the private view open for the viewer. False outside a request (a script, a command, a tool)."""
    try:
        from flask import has_request_context

        if not has_request_context():
            return False
        from jason.web import access

        return access.private_window() is not None
    except Exception:  # noqa: BLE001 - a window that cannot be read is not open
        return False


def hide_text(standing: Standing, private: bool | None = None) -> bool:
    """Whether text-derived fields are withheld: the file is confidential and the private view is not open."""
    if not standing.confidential:
        return False
    return not (private_open() if private is None else bool(private))


def withheld_note(standing: Standing) -> dict[str, Any]:
    return {"text": "withheld", "why": standing.words, "known": standing.known}


def session_view(view: dict[str, Any], hide: bool, standing: Standing | None = None) -> dict[str, Any]:
    """A session as a screen reads it, with the words behind a suggestion and a segment's title and kind withheld when ``hide``."""
    if not hide:
        return view
    out = dict(view)
    out["suggestions"] = [{**{k: v for k, v in s.items() if k not in ("why", "signals")},
                           "why": "", "signals": [{"signal": g.get("signal"), "weight": g.get("weight")} for g in s.get("signals") or ()]}
                          for s in view.get("suggestions") or ()]
    out["segments"] = [{**g, "labels": {k: v for k, v in (g.get("labels") or {}).items() if k not in TEXT_LABELS}}
                       for g in view.get("segments") or ()]
    out["masked"] = withheld_note(standing or Standing(True))
    return out


def facts(rows: list[dict[str, Any]], hide: bool) -> list[dict[str, Any]]:
    """The page facts as a screen draws its placeholders, without the fields the page's text or picture gave when ``hide``."""
    if not hide:
        return rows
    return [{k: v for k, v in row.items() if k not in TEXT_FACT_FIELDS} for row in rows]


def review(rev: dict[str, Any], hide: bool) -> dict[str, Any]:
    """The review of an apply (or the review inside a dry-run apply), without the title and kind each part was labelled with."""
    if not hide:
        return rev
    out = dict(rev)
    out["parts"] = [{k: v for k, v in p.items() if k not in TEXT_REVIEW_FIELDS} for p in rev.get("parts") or ()]
    return out


def apply_result(result: dict[str, Any], hide: bool) -> dict[str, Any]:
    """An apply's answer: the review inside a dry run is masked; the written parts carry only codes already."""
    if not hide or "review" not in result:
        return result
    return {**result, "review": review(result["review"], True)}


__all__ = ["BUSY_WORDS", "HELD_WORDS", "Standing", "TEXT_FACT_FIELDS", "TEXT_LABELS", "apply_result", "facts", "hide_text", "private_open",
           "review", "session_view"]
