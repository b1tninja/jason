"""The register of license numbers the association's documents print: who holds each, which board issued it, and where.

``run_library`` reads every file the library holds (its cached text), finds each license mention
(``jason.community.licenses``), resolves an unspecified number against the same number printed with its board elsewhere,
and keeps one row per license: its board, number, classification, jurisdiction, the holders it was printed beside (with
how often), the documents it appears in, and where a person checks it. The register is ``data/parties/licenses.json``;
it names vendors and quotes documents, so it is private. A notary's commission and a certification are kept apart from
the vendors' licenses (``persons``): they name people.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.licenses import Board, LicenseMention, by_license, find_licenses, resolve

STORE = Path("parties") / "licenses.json"
PERSONAL = (Board.NOTARY, Board.CERTIFICATION)


def register(found: list[tuple[dict[str, Any], LicenseMention]]) -> list[dict[str, Any]]:
    """One row per license from (document, mention) pairs: the holders it was printed beside, its documents, newest
    first, and the board taken from wherever the number is printed with one."""
    resolved = resolve([m for _, m in found])
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for (doc, _), m in zip(found, resolved):
        row = rows.setdefault(m.key, {"board": m.board.value, "boardKey": m.board.name, "kind": m.kind, "label": m.label,
                                      "number": m.number, "classification": m.classification,
                                      "jurisdiction": m.jurisdiction, "verify": m.verify, "holders": Counter(),
                                      "documents": [], "personal": m.board in PERSONAL})
        if m.holder:
            row["holders"][m.holder] += 1
        row["classification"] = row["classification"] or m.classification
        if not any(d["id"] == doc.get("id") for d in row["documents"]):
            row["documents"].append({"id": doc.get("id", ""), "path": doc.get("path", ""), "period": doc.get("period", ""),
                                     "kind": doc.get("kind", ""), "quote": m.quote[:120]})
    out = []
    for row in rows.values():
        holders = row.pop("holders")
        row["holder"] = holders.most_common(1)[0][0] if holders else ""
        row["holders"] = dict(holders.most_common())
        row["documents"].sort(key=lambda d: d["period"], reverse=True)
        out.append(row)
    return sorted(out, key=lambda r: (r["personal"], r["boardKey"], (r["holder"] or "~").lower(), r["number"]))


def run_library(root: Path, *, log: Callable[[str], None] = lambda s: None) -> list[dict[str, Any]]:
    from jason.tasks.library import distinct, load, text_for

    found: list[tuple[dict[str, Any], LicenseMention]] = []
    for row in distinct(load(root)):
        text = text_for(root, str(row["id"]))
        if not text.strip():
            continue
        for m in by_license(find_licenses(text)):
            found.append(({"id": str(row["id"]), "path": str(row.get("path") or ""), "period": str(row.get("period") or ""),
                           "kind": str(row.get("kind") or "")}, m))
    rows = register(found)
    log(f"{len(rows)} licenses in {len({d['id'] for r in rows for d in r['documents']})} documents")
    return rows


def save(root: Path, rows: list[dict[str, Any]]) -> Path:
    path = Path(root) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"readAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "licenses": rows},
                               indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def load_register(root: Path) -> list[dict[str, Any]]:
    path = Path(root) / STORE
    return json.loads(path.read_text(encoding="utf-8")).get("licenses", []) if path.is_file() else []


def _cell(text: Any) -> str:
    return " ".join(str(text if text is not None else "").split()).replace("|", "/")


def markdown(rows: list[dict[str, Any]], *, personal: bool = False) -> str:
    """The vendors' licenses as a table a person checks, each with its board's page. A reading: the holder is the name
    the number was printed beside, and whether the license is current is the board's to say."""
    vendors = [r for r in rows if not r["personal"]]
    out = ["# Licenses the documents print", "",
           f"{len(vendors)} licenses. The holder is the business the number is printed beside. Whether a license is "
           "current, its classifications, and its bond are on the board's page.", "",
           "| Holder | Board | Number | Class | Documents | Check |", "| --- | --- | --- | --- | ---: | --- |"]
    for r in vendors:
        board = r["board"] if r["jurisdiction"] in ("CA", "") else f"{r['board']} ({r['jurisdiction']})"
        out.append(f"| {_cell(r['holder']) or '(not read)'} | {_cell(board)} | {r['number']} | {r['classification']} | "
                   f"{len(r['documents'])} | {r['verify']} |")
    if personal:
        people = [r for r in rows if r["personal"]]
        out += ["", "## Notaries and certifications", "",
                "| Kind | Number | Jurisdiction | Documents |", "| --- | --- | --- | ---: |"]
        out += [f"| {r['label']} | {r['number']} | {r['jurisdiction']} | {len(r['documents'])} |" for r in people]
    unread = [r for r in vendors if not r["holder"]]
    if unread:
        out += ["", f"{len(unread)} numbers have no holder read beside them (a logo, not text, may carry the name); "
                    "their documents say whose they are."]
    return "\n".join(out) + "\n"


__all__ = ["STORE", "register", "run_library", "save", "load_register", "markdown"]
