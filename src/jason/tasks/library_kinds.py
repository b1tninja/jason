"""The document kinds' shelf: every kind jason knows, what the library holds of each, and how each file got its kind.

Reads the classified library on disk (``jason library``) and the kind profile (``documents.PROFILE``). It calls no
network and no model. A confidential file is counted and never named, so a person without the right sees only the count.
The shapes are in docs/console/handoff-document-kinds.md and the screen is docs/console/screens/document-kinds.md.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from jason.community.documents import PROFILE
from jason.community.records import CITATION
from jason.community.symbols import DocumentCategory, DocumentKind

# library.Method names as stored, to the words the console uses.
METHODS = ("name", "content", "agenda", "model", "person", "none")
METHOD_WORDS = {
    "name": "by name or folder",
    "content": "by its text",
    "agenda": "by an agenda item",
    "model": "by a model",
    "person": "by a person",
    "none": "no rule",
}
UNCLASSIFIED = "unclassified"


def _label(word: str) -> str:
    return word.replace("_", " ").capitalize()


def _method(row: dict[str, Any]) -> str:
    stored = str(row.get("method") or "").strip().lower()
    return stored if stored in METHODS else "none"


def _kind_of(row: dict[str, Any]) -> str:
    return str(row.get("kind") or "")


def _methods(rows: list[dict[str, Any]]) -> dict[str, int]:
    counted = Counter(_method(r) for r in rows)
    return {m: counted.get(m, 0) for m in METHODS}


def _record(kind: DocumentKind) -> dict[str, str] | None:
    record = PROFILE[kind].record if kind in PROFILE else None
    if record is None:
        return None
    return {"citation": CITATION.get(record, ""), "label": _label(record.value)}


def _summary(kind: DocumentKind, rows: list[dict[str, Any]]) -> dict[str, Any]:
    periods = sorted((str(r.get("period") or "") for r in rows if r.get("period")), reverse=True)
    return {
        "kind": kind.value,
        "label": _label(kind.value),
        "shelf": PROFILE[kind].category.value if kind in PROFILE else "",
        "files": len(rows),
        "held": sum(1 for r in rows if r["confidential"]),
        "newest": periods[0] if periods else None,
        "record": _record(kind),
        "methods": _methods(rows),
    }


def _rows(root: Path) -> list[dict[str, Any]]:
    from jason.tasks.library import distinct, load

    return distinct(load(root))


def shelf(root: Path) -> dict[str, Any]:
    """Every kind on its shelf, in the shelves' fixed order, with counts; ``found`` is false with no library store."""
    rows = _rows(Path(root))
    if not rows:
        return {"found": False, "note": "no library store; run jason library", "shelves": [], "unclassified": 0, "total": 0}
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_kind.setdefault(_kind_of(row), []).append(row)
    shelves = []
    for category in DocumentCategory:
        kinds = [_summary(k, by_kind.get(k.value, [])) for k in DocumentKind if k in PROFILE and PROFILE[k].category is category]
        if kinds:
            shelves.append({"shelf": category.value, "label": _label(category.value), "kinds": kinds})
    stamps = sorted(str(r.get("classified_at") or "") for r in rows if r.get("classified_at"))
    known = {k.value for k in DocumentKind}
    return {
        "found": True,
        "shelves": shelves,
        "unclassified": sum(len(v) for k, v in by_kind.items() if k not in known),
        "total": len(rows),
        "kindsTotal": sum(len(s["kinds"]) for s in shelves),
        "kindsWithFiles": sum(1 for s in shelves for k in s["kinds"] if k["files"]),
        "generated": stamps[-1] if stamps else None,
        "methodWords": METHOD_WORDS,
    }


def kind_detail(root: Path, kind: str, *, include_held: bool = False) -> dict[str, Any]:
    """One kind: its summary and its files. A held file is counted in the summary and listed nowhere; with ``kind`` =
    ``unclassified``, the files no rule placed. ``ValueError`` for a word that is not a kind (a 400)."""
    word = kind.strip().lower().replace(" ", "_")
    rows = _rows(Path(root))
    if word == UNCLASSIFIED:
        known = {k.value for k in DocumentKind}
        mine = [r for r in rows if _kind_of(r) not in known]
        summary = {"kind": UNCLASSIFIED, "label": "No kind yet", "shelf": "", "files": len(mine),
                   "held": sum(1 for r in mine if r["confidential"]), "newest": None, "record": None, "methods": _methods(mine)}
    else:
        try:
            member = DocumentKind(word)
        except ValueError:
            raise ValueError(f"not a document kind: {kind!r}") from None
        mine = [r for r in rows if _kind_of(r) == member.value]
        summary = _summary(member, mine)
    files = [
        {"id": r["id"], "name": r["name"], "period": r.get("period") or "", "method": _method(r),
         "methodWord": METHOD_WORDS[_method(r)], "evidence": r.get("evidence") or "",
         "confidence": r.get("confidence"), "copies": len(r.get("copies") or [])}
        for r in sorted(mine, key=lambda r: (str(r.get("period") or ""), r["path"]), reverse=True)
        if include_held or not r["confidential"]
    ]
    return {"found": bool(rows), "summary": summary, "files": files, "heldBack": summary["held"] if not include_held else 0,
            "methodWords": METHOD_WORDS}
