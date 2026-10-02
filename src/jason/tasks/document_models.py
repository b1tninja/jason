"""Read every classified library file with its kind's document model; store the readings and report coverage.

``run`` walks the classified library (``jason library``), reads each file's cached text with the models registered
for its kind (``jason.community.document_models``), and writes ``data/documents/readings.json``: per file its kind,
the model that read it, whether the record is complete, what is missing, the fields, and the findings. ``read_file``
reads one file on disk (a Drive copy the library lacks) the same way. ``coverage`` says, per kind, how many files
there are, how many have text, how many a model read, and how many readings are complete, and lists the kinds no
model reads yet. It reads disk only.

A confidential library file's fields stay on disk; ``summary`` leaves them out unless asked.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.document_models import ModelContext, modeled_kinds, read
from jason.community.symbols import DocumentKind

STORE = Path("documents") / "readings.json"


def _kind(value: str) -> DocumentKind | None:
    try:
        return DocumentKind(value)
    except ValueError:
        return None


def run(data_dir: Path, community: Any, *, kinds: tuple[DocumentKind, ...] = (), today: date | None = None) -> dict[str, Any]:
    """Read the library with the document models and save the readings."""
    from jason.tasks.library import distinct, load, text_for

    data_dir = Path(data_dir)
    rows = distinct(load(data_dir))
    readings = []
    for row in rows:
        kind = _kind(str(row.get("kind") or ""))
        if kind is None or (kinds and kind not in kinds):
            continue
        text = text_for(data_dir, row["id"])
        entry = {"id": row["id"], "name": row.get("name"), "period": row.get("period"), "kind": kind.value,
                 "confidential": bool(row.get("confidential")), "hasText": bool(text.strip()), "model": None}
        if text.strip():
            context = ModelContext(community, data_dir, today or date.today(), str(row.get("name") or ""), str(row.get("period") or ""),
                                   bool(row.get("confidential")))
            try:
                reading = read(kind, text, context)
            except Exception as exc:  # one bad file does not stop the run; the error is the finding
                entry["error"] = f"{type(exc).__name__}: {exc}"
                reading = None
            if reading is not None:
                entry.update(reading.as_dict())
        readings.append(entry)
    path = data_dir / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {"readAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "readings": readings}
    if path.is_file():
        # A run over some kinds keeps the other kinds' readings; every run keeps the readings of files read from Drive
        # (``jason.tasks.drive_minutes``), which the library does not hold.
        old = json.loads(path.read_text(encoding="utf-8")).get("readings", [])
        kept = [r for r in old if r.get("source") == "Drive" or (kinds and _kind(r["kind"]) not in kinds)]
        result["readings"] = kept + readings
    path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return coverage(result["readings"])


def read_file(path: Path, kind: DocumentKind, community: Any, *, data_dir: Path | None = None, today: date | None = None) -> dict[str, Any]:
    """One file on disk (a PDF, or its text) read with ``kind``'s models."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from jason.tasks.library import text_of

        text, _how = text_of(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    reading = read(kind, text, ModelContext(community, data_dir, today or date.today(), path.name, ""))
    return {"file": str(path), "kind": kind.value, **(reading.as_dict() if reading else {"model": None, "note": "no model recognized the text"})}


def load(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / STORE
    return json.loads(path.read_text(encoding="utf-8")).get("readings", []) if path.is_file() else []


def coverage(readings: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, Counter] = defaultdict(Counter)
    severities: dict[str, Counter] = defaultdict(Counter)
    for r in readings:
        c = by_kind[r["kind"]]
        c["files"] += 1
        c["text"] += int(r["hasText"])
        c["read"] += int(bool(r.get("model")))
        c["complete"] += int(bool(r.get("complete")))
        c["errors"] += int(bool(r.get("error")))
        for f in r.get("findings") or []:
            severities[r["kind"]][f["severity"]] += 1
    modeled = {k.value for k in modeled_kinds()}
    rows = [{"kind": k, "modeled": k in modeled, **dict(c), "findings": dict(severities[k])} for k, c in by_kind.items()]
    rows.sort(key=lambda r: (-r["files"], r["kind"]))
    return {"kinds": rows, "files": sum(r["files"] for r in rows), "read": sum(r.get("read", 0) for r in rows),
            "unmodeled": [r["kind"] for r in rows if not r["modeled"]]}


def summary(data_dir: Path, *, kind: str = "", include_confidential: bool = False, limit: int = 50) -> dict[str, Any]:
    """The stored readings of one kind (or all), newest first, with the findings; a confidential file's fields are held back."""
    readings = [r for r in load(data_dir) if not kind or r["kind"] == kind]
    readings.sort(key=lambda r: str(r.get("period") or ""), reverse=True)
    out = []
    for r in readings[:limit]:
        row = {k: v for k, v in r.items() if k != "fields"}
        if r.get("fields") is not None and (include_confidential or not r.get("confidential")):
            row["fields"] = r["fields"]
        out.append(row)
    return {"found": bool(readings), "coverage": coverage(load(data_dir)), "readings": out,
            "caveats": ["A reading is what a model found in the file's text; OCR text can be wrong, and a finding is a lead, not a determination."]}


def coverage_lines(result: dict[str, Any]) -> list[str]:
    out = [f"{result['read']} of {result['files']} library files read by a document model", "",
           f"  {'kind':<30} {'files':>5} {'text':>5} {'read':>5} {'complete':>8}  findings"]
    for r in result["kinds"]:
        mark = "" if r["modeled"] else "  (no model)"
        findings = ", ".join(f"{k} {v}" for k, v in sorted(r["findings"].items()))
        out.append(f"  {r['kind']:<30} {r['files']:>5} {r.get('text', 0):>5} {r.get('read', 0):>5} {r.get('complete', 0):>8}  {findings}{mark}")
    return out


__all__ = ["run", "read_file", "load", "coverage", "summary", "coverage_lines"]
