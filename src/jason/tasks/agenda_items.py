"""Each agenda item with the documents related to it, and what the agendas say those documents are.

``build`` reads the agenda Docs kept by `jason meetings --links` (``data/meetings/agenda-docs``) into items and relates
documents to each item three ways, in order of strength:

- **linked**: the item's chip or link resolves to a Drive file;
- **named**: the item's words name a file ("[Proposal 6021-1.pdf]") or a numbered document ("estimate 000999") that a
  Drive file, a PayHOA library file, or a Gmail attachment carries in its name;
- **received**: a Gmail attachment whose kind the item brings (by name rules), received in the 45 days before the
  meeting, whose name shares a distinctive word with the item. This is a candidate, never a join.

Each related document's kind by the library's name rules is set beside the kinds the item brings
(``expected_kinds``): it **agrees**, **differs**, or, when the name rules say nothing, the item **suggests** its first
kind. ``hints`` gathers, per document, every item that used it and the kinds they suggest: a lead for the classifier,
recorded with its evidence, never the classification. The result is ``data/meetings/agenda-items.json``.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.agenda_items import expected_kinds, items_in_doc, mentions
from jason.community.agenda_links import LinkKind
from jason.community.meeting_records import meeting_date

OUT = Path("meetings") / "agenda-items.json"
RECEIVED_DAYS = 45
STOP = {"the", "and", "for", "of", "to", "a", "in", "on", "with", "review", "report", "proposal", "proposals", "see", "pdf", "all",
        "open", "requests", "board", "association", "mystique", "community", "meeting", "discussion", "item", "items", "new"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z0-9]{3,}", text.lower()) if w not in STOP}


def _names(data_dir: Path) -> list[dict[str, Any]]:
    """Every file name jason knows, with where it is: Drive, the PayHOA library, Gmail attachments."""
    out: list[dict[str, Any]] = []
    drive = Path(data_dir) / "drive" / "files.json"
    if drive.is_file():
        raw = json.loads(drive.read_text(encoding="utf-8"))
        for r in raw if isinstance(raw, list) else raw.get("files", []):
            out.append({"where": "Drive", "name": r["name"], "ref": r["id"], "path": r.get("path"), "day": (r.get("modified") or "")[:10]})
    db = Path(data_dir) / "library" / "library.db"
    if db.is_file():
        import sqlite3

        with sqlite3.connect(db) as con:
            for doc_id, name, path, kind in con.execute("select id, name, path, kind from documents"):
                out.append({"where": "PayHOA library", "name": name, "ref": str(doc_id), "path": path, "kind": kind, "day": ""})
    files = Path(data_dir) / "gmail" / "files.json"
    if files.is_file():
        raw = json.loads(files.read_text(encoding="utf-8"))
        for f in raw if isinstance(raw, list) else raw.get("files", []):
            out.append({"where": "Gmail", "name": f["name"], "ref": f.get("messageId", ""), "path": str(f.get("path", "")).replace("\\", "/"),
                        "day": (f.get("at") or "")[:10], "subject": f.get("subject", "")})
    return out


def _judge(kind: Any, expected: tuple) -> str:
    if not expected:
        return ""
    if kind is None:
        return f"suggests {expected[0].value}"
    return "agrees" if kind in expected else f"differs (the item brings {', '.join(k.value for k in expected[:3])})"


def build(data_dir: Path, community: Any) -> dict[str, Any]:
    link_rules, item_rules = tuple(community.agenda_link_rules()), tuple(community.agenda_item_rules())
    schedule = community.meeting_schedule()
    names = _names(data_dir)
    drive_by_id = {n["ref"]: n for n in names if n["where"] == "Drive"}
    by_folded: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in names:
        by_folded[n["name"].casefold()].append(n)
    meetings: list[dict[str, Any]] = []
    hints: dict[str, dict[str, Any]] = {}

    def hint(doc: dict[str, Any], day: str, label: str, relation: str, expected: tuple, kind: Any) -> None:
        key = f"{doc['where']}:{doc['ref']}"
        h = hints.setdefault(key, {"where": doc["where"], "ref": doc["ref"], "name": doc["name"], "path": doc.get("path"),
                                   "nameKind": kind.value if kind else None, "uses": [], "suggested": Counter()})
        h["uses"].append({"date": day, "item": label, "relation": relation})
        for k in expected[:3]:
            h["suggested"][k.value] += 1

    for path in sorted((Path(data_dir) / "meetings" / "agenda-docs").glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        day = meeting_date(doc.get("title", ""), doc.get("_path", ""), schedule=schedule)
        if day is None:
            continue
        rows = []
        for item in items_in_doc(doc, link_rules):
            expected = expected_kinds(item.label, item_rules)
            related: list[dict[str, Any]] = []
            seen: set[str] = set()
            refers = []
            for link in item.links:
                if link.kind is LinkKind.INTERNAL and link.refers_to:
                    refers.append({"to": link.refers_to, "text": link.text})     # another item of the same agenda
                    continue
                if link.kind in (LinkKind.ZOOM, LinkKind.LAW, LinkKind.WEB, LinkKind.COURT, LinkKind.CALENDAR, LinkKind.INTERNAL):
                    continue
                d = drive_by_id.get(link.target)
                if d is None:
                    related.append({"relation": "linked", "name": link.text, "url": link.url, "kind": link.kind.value, "where": "not in Drive"})
                    continue
                kind = community.classify_document(d["name"], path=d.get("path") or "")
                related.append({"relation": "linked", "where": "Drive", "ref": d["ref"], "name": d["name"], "path": d["path"],
                                "nameKind": kind.value if kind else None, "judgment": _judge(kind, expected)})
                seen.add(d["name"].casefold())
                hint(d, day.isoformat(), item.label, "linked", expected, kind)
            for token in mentions(item.text):
                folded = token.casefold()
                hits = by_folded.get(folded, []) or [n for n in names if re.search(rf"(?<![\w]){re.escape(folded)}(?![\w])", n["name"].casefold())]
                for n in hits[:6]:
                    if n["name"].casefold() in seen:
                        continue
                    seen.add(n["name"].casefold())
                    kind = community.classify_document(n["name"], path=n.get("path") or "")
                    related.append({"relation": "named", "mention": token, "where": n["where"], "ref": n["ref"], "name": n["name"],
                                    "path": n.get("path"), "nameKind": kind.value if kind else None, "judgment": _judge(kind, expected)})
                    hint(n, day.isoformat(), item.label, "named", expected, kind)
            if expected and set(expected) & {k for k in expected if k.value in ("proposal", "invoice", "claim_estimate", "claim_letter",
                                                                                    "inspection_report")}:
                words = _words(item.text)
                window = (day - timedelta(days=RECEIVED_DAYS)).isoformat()
                for n in names:
                    if n["where"] != "Gmail" or not (window <= n["day"] <= day.isoformat()) or n["name"].casefold() in seen:
                        continue
                    kind = community.classify_document(n["name"], path=n.get("path") or "")
                    shared = words & _words(n["name"] + " " + n.get("subject", ""))
                    if kind in expected and shared:
                        seen.add(n["name"].casefold())
                        related.append({"relation": "received", "where": "Gmail", "ref": n["ref"], "name": n["name"], "path": n["path"],
                                        "received": n["day"], "nameKind": kind.value, "because": sorted(shared)[:4]})
            if related or expected or refers:
                rows.append({"item": item.title, "subitem": item.subitem, "expects": [k.value for k in expected],
                             "notes": item.notes[:6], "related": related, "refersTo": refers})
        meetings.append({"date": day.isoformat(), "agenda": doc.get("title"), "items": rows})

    for h in hints.values():
        h["suggested"] = [k for k, _ in h["suggested"].most_common(3)]
        h["agrees"] = bool(h["nameKind"]) and h["nameKind"] in h["suggested"]
    result = {"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "meetings": sorted(meetings, key=lambda m: m["date"], reverse=True),
              "hints": sorted(hints.values(), key=lambda h: (-len(h["uses"]), h["name"]))}
    out = Path(data_dir) / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def summary_lines(result: dict[str, Any], *, limit: int = 20) -> list[str]:
    rel = Counter(r["relation"] for m in result["meetings"] for i in m["items"] for r in i["related"])
    judg = Counter((r.get("judgment") or "").split(" (")[0].split(" ")[0] for m in result["meetings"] for i in m["items"]
                   for r in i["related"] if r.get("judgment"))
    hints = result["hints"]
    unclassified = [h for h in hints if not h["nameKind"] and h["suggested"]]
    differs = [h for h in hints if h["nameKind"] and h["suggested"] and not h["agrees"]]
    lines = [f"{len(result['meetings'])} agendas; related documents: " + ", ".join(f"{v} {k}" for k, v in rel.most_common()),
             "against the item's kinds: " + ", ".join(f"{v} {k}" for k, v in judg.most_common()),
             f"{len(hints)} documents used by agenda items; {len(unclassified)} the name rules leave unclassified now have a "
             f"suggested kind; {len(differs)} are named one kind and used as another", ""]
    lines.append("Suggested kinds for files the name rules do not classify:")
    for h in unclassified[:limit]:
        uses = "; ".join(f"{u['date']} {u['item']}" for u in h["uses"][:2])
        lines.append(f"- {h['name'][:70]} -> {', '.join(h['suggested'])}  [{uses}]")
    return lines


__all__ = ["build", "summary_lines"]
