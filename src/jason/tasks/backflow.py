"""The backflow program's view: its assemblies, its notices with their clocks, where sources disagree, and the tester check.

``view(data_dir, community)`` is what ``GET /api/backflow`` returns, built from the profile's ``BackflowProgram``
(``Community.backflow_program()``), the library and Drive on disk, and the dated snapshot of the program's published
tester lists. It reads disk only. ``fetch_tester_lists`` is the one function here that goes to the network, and only a
person's ``jason backflow --fetch-testers`` calls it.

What the view keeps (docs/console/handoff-inspections-and-portals.md):

- **No clock picks a date.** A notice's days are counted from each date it could run from, side by side. The standing is
  "met" or "passed" only when every reading gives the same answer, otherwise "unknown": which date counts is the
  program's to say.
- **No source wins.** A count another source gives that differs from the assemblies' is a ``Discrepancy`` with each
  source's words, and the view never settles it.
- **The tester is looked up, not certified.** The check says whether the tester's name is on each published list as of the
  list's date. The snapshot keeps each entry's id and words (names, business, city), never a phone number or an email.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

SNAPSHOT = Path("backflow") / "tester-lists.json"
ID = re.compile(r"^[A-Z]{2}\d{7}$")
UPDATED = re.compile(r"[Uu]pdated\s+(\d{1,2})/(\d{1,2})/(\d{4})")
PHONE = re.compile(r"\(?\d{3}\)?[ -]?\d{3}-\d{4}")
TOKEN = re.compile(r"[A-Z][A-Z'&.-]*[A-Z]|[A-Z]")
CAVEATS = [
    "A list shows who is certified and listed as of its date; it shows no registration for the year and no expiry.",
    "A notice's clock is the program's. Each date it could run from is shown, and none is chosen.",
    "A count from another source is shown beside the assemblies' and never settled.",
]


# --- The tester lists -------------------------------------------------------------------------------------------------

def parse_tester_list(pdf: bytes) -> tuple[str, list[dict[str, str]]]:
    """A published list's date (ISO, or "") and its entries as ``{id, text}``: the words of one record with phone
    numbers and emails dropped. A list with tester ids is split at each id, one without at each email line."""
    import pymupdf

    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        lines = [ln.strip() for page in doc for ln in page.get_text().splitlines() if ln.strip()]
    text = "\n".join(lines)
    found = UPDATED.search(text)
    dated = f"{found.group(3)}-{int(found.group(1)):02d}-{int(found.group(2)):02d}" if found else ""
    blocks: list[tuple[str, list[str]]] = []
    if any(ID.match(ln.split()[0]) for ln in lines if ln.split()):
        for ln in lines:
            first = ln.split()[0] if ln.split() else ""
            if ID.match(first):
                blocks.append((first, [ln[len(first):]]))
            elif blocks:
                blocks[-1][1].append(ln)
    else:
        current: list[str] = []
        start = next((i + 1 for i, ln in enumerate(lines) if ln == "EMAIL"), 0)      # past the column headings
        for ln in lines[start:]:
            current.append(ln)
            if "@" in ln:
                blocks.append(("", current))
                current = []
    entries = []
    for ident, parts in blocks:
        words = " ".join(TOKEN.findall(PHONE.sub(" ", " ".join(p for p in parts if "@" not in p)).upper()))
        if words:
            entries.append({"id": ident, "text": words})
    return dated, entries


def fetch_tester_lists(data_dir: Path, program: Any, *, http: Any = None, today: date | None = None) -> dict[str, Any]:
    """Download each list the program names and keep a dated snapshot under ``data/backflow``. Names, ids, and
    businesses are kept; phone numbers and emails are not."""
    import httpx

    client = http or httpx.Client(timeout=60.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
    lists = []
    for ref in program.lists:
        response = client.get(ref.url)
        if response.status_code != 200 or not response.content.startswith(b"%PDF"):
            lists.append({"name": ref.name, "url": ref.url, "error": f"HTTP {response.status_code}, not a PDF", "entries": []})
            continue
        dated, entries = parse_tester_list(response.content)
        lists.append({"name": ref.name, "url": ref.url, "dated": dated, "entries": entries})
    body = {"fetched": (today or date.today()).isoformat(), "lists": lists}
    path = Path(data_dir) / SNAPSHOT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=1), encoding="utf-8")
    return body


def _tokens(text: str) -> set[str]:
    return {t for t in TOKEN.findall((text or "").upper().replace("(", " ").replace(")", " ")) if len(t) > 1}


def check_tester(program: Any, snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Whether the tester's name is on each list in the snapshot: ``listed``, ``listed under another business`` (the name
    is there but not the business the reports print), ``not listed``, or ``not fetched``."""
    tester = program.tester
    if tester is None:
        return {}
    name, business = _tokens(tester.name), _tokens(tester.business)
    rows = []
    by_name = {s["name"]: s for s in (snapshot or {}).get("lists", [])}
    for ref in program.lists:
        kept = by_name.get(ref.name)
        if not kept or kept.get("error"):
            rows.append({"name": ref.name, "found": "not fetched"})
            continue
        hits = [e for e in kept["entries"] if name <= _tokens(e["text"])]
        best = next((e for e in hits if business and business <= _tokens(e["text"])), None)
        row: dict[str, Any] = {"name": ref.name, "found": "not listed"}
        if best or hits:
            entry = best or hits[0]
            row["found"] = "listed" if best else "listed under another business"
            if entry.get("id"):
                row["id"] = entry["id"]
        if kept.get("dated"):
            row["dated"] = kept["dated"]
        rows.append(row)
    return {"tester": tester.name, "certificate": tester.certificate, "lists": rows, "contactsMasked": True}


# --- The notices' clocks ----------------------------------------------------------------------------------------------

def notice_clock(notice: Any, today: date) -> dict[str, Any]:
    """A notice's days counted from each date it could run from, to the day it was settled or to today. A reading that
    came after that day has elapsed 0 and no answer. The standing is "met" or "passed" only when every reading with an
    answer agrees, "running" while open and every reading is within the days, else "unknown"."""
    end = date.fromisoformat(notice.settled_on) if notice.settled_on else today
    readings = []
    for label, iso in notice.runs_from:
        start = date.fromisoformat(iso)
        elapsed = (end - start).days
        if elapsed < 0:
            readings.append({"label": label, "date": iso, "elapsed": 0, "met": None})
        else:
            readings.append({"label": label, "date": iso, "elapsed": elapsed, "met": elapsed <= notice.days})
    answers = {r["met"] for r in readings if r["met"] is not None}
    if answers == {True}:
        standing = "met" if notice.settled_on else "running"
    elif answers == {False}:
        standing = "passed"
    else:
        standing = "unknown"
    return {"program": notice.program, "basis": notice.basis, "days": notice.days, "runsFrom": readings,
            "standing": standing, "caveat": notice.caveat, "document": notice.document}


# --- The view ---------------------------------------------------------------------------------------------------------

_NUMBERS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def _library_names(root: Path) -> dict[str, str]:
    import sqlite3

    db = root / "library" / "library.db"
    if not db.is_file():
        return {}
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
        return {name: str(doc_id) for doc_id, name in conn.execute("SELECT id, name FROM documents")}


def doc_refs(names: Any, data_dir: Path) -> list[dict[str, Any]]:
    """References for documents named in the profile: a library document by name, else a Drive file when exactly one has
    that name, else the name as text. Never a guess, never a path."""
    from jason.approvals.docref import library_ref, refs_from_strings

    root = Path(data_dir)
    held = _library_names(root)
    out: list[dict[str, Any]] = []
    for name in names:
        if name in held:
            out.append(library_ref(held[name], name=name, data_dir=root))
        else:
            # A Drive file when exactly one has the name; otherwise the name as text, without the lookup's prefix.
            out += [{"text": name} if "text" in e else e for e in refs_from_strings([f"Drive: {name}"], data_dir=root)]
    return out


def _discrepancies(program: Any) -> list[dict[str, Any]]:
    out = []
    for source, service, count, document in program.counts:
        ours = [a for a in program.assemblies if a.service.value == service]
        if len(ours) == count:
            continue
        listed_by = sorted({s for a in ours for s, _ in a.ids})
        out.append({
            "subject": f"The number of {service} backflow assemblies",
            "sources": [{"source": " and ".join(listed_by) or "the program's lists", "says": _NUMBERS.get(len(ours), str(len(ours)))},
                        {"source": source, "says": _NUMBERS.get(count, str(count)), "doc": {"text": document}}],
            "next": "A person reconciles the figures against the devices on the property; neither is chosen here.",
        })
    return out


def view(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    program = community.backflow_program()
    if program is None:
        return {"found": False, "note": "The specification sets no backflow program (Community.backflow_program)."}
    root = Path(data_dir)
    day = today or date.today()
    snapshot_path = root / SNAPSHOT
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.is_file() else None
    assemblies = []
    for a in program.assemblies:
        assemblies.append({
            "service": a.service.value, "type": a.kind.value, "sizeIn": a.size_in, "serial": a.serial, "location": a.location,
            "ids": [{"source": s, "id": i} for s, i in a.ids], "testDue": a.test_due,
            "history": [{"date": d, "result": r, "document": (doc_refs([n], root) or [{"text": n}])[0]} for d, r, n in a.history],
            # A key with no value is left out, as the TypeScript type's optional fields are.
            **{k: v for k, v in (("account", a.account), ("meter", a.meter), ("lastPassed", a.last_passed),
                                 ("lastFailed", a.last_failed), ("tag", a.tag)) if v},
        })
    tester = check_tester(program, snapshot)
    if snapshot is None:
        tester["snapshot"] = None
        tester["note"] = "The tester lists have not been fetched. Run `jason backflow --fetch-testers`."
    else:
        tester["snapshot"] = snapshot.get("fetched")
    return {"found": True, "program": program.program, "supplier": program.supplier, "asOf": day.isoformat(),
            "assemblies": assemblies, "notices": [notice_clock(n, day) for n in program.notices],
            "discrepancies": _discrepancies(program), "tester": tester, "caveats": CAVEATS,
            "command": "jason backflow"}


def view_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result["note"]]
    out = [f"{result['program']} ({result['supplier']}) as of {result['asOf']}", ""]
    for a in result["assemblies"]:
        ids = ", ".join(f"{i['source']} {i['id']}" for i in a["ids"])
        out.append(f"  {a['service']:<10} {a['type']} {a['sizeIn']:g} in  {a['serial']:<8} due {a['testDue']}  last passed {a['lastPassed'] or '-'}"
                   f"{'  FAILED ' + a['lastFailed'] if a['lastFailed'] and a['lastFailed'] >= (a['lastPassed'] or '') else ''}  ({ids})")
    for n in result["notices"]:
        out += ["", f"{n['program']}: {n['days']} days, {n['standing']}", f"  {n['basis']}"]
        out += [f"    from {r['label']} {r['date']}: {r['elapsed']} days, " + {True: "within", False: "past", None: "no answer"}[r["met"]] for r in n["runsFrom"]]
        out.append(f"  {n['caveat']}")
    for d in result["discrepancies"]:
        out += ["", d["subject"]] + [f"  {s['source']}: {s['says']}" for s in d["sources"]] + [f"  {d['next']}"]
    t = result["tester"]
    if t:
        out += ["", f"Tester {t['tester']} (certificate {t['certificate'] or 'not given'}, as printed)"]
        out += [f"  {x['name']}: {x['found']}" + (f" ({x['id']})" if x.get("id") else "") + (f", list dated {x['dated']}" if x.get("dated") else "")
                for x in t["lists"]]
        if t.get("note"):
            out.append(f"  {t['note']}")
    out += [""] + [f"* {c}" for c in result["caveats"]]
    return out


# --- The watchlist ------------------------------------------------------------------------------------------------------

# The calendar's standing words and the watchlist's. A word the calendar does not know is "unknown", never "overdue".
_FROM_CALENDAR = {"overdue": "overdue", "done": "current", "done late": "current", "upcoming": "current", "due soon": "current",
                  "no evidence": "unknown", "no store shows it": "unknown", "payments listed, not judged": "unknown"}


def watchlist(data_dir: Path, community: Any, *, today: date | None = None) -> dict[str, Any]:
    """``GET /api/watchlist``: each life-safety item the profile lists, with a standing in words. An item tied to an
    obligation takes the deadlines calendar's standing; the others carry the standing the profile entered. Evidence
    is references to documents; ``searched`` says how the records were looked through."""
    rows = community.life_safety_watch()
    if not rows:
        return {"found": False, "note": "The specification lists no life-safety watchlist (Community.life_safety_watch)."}
    root = Path(data_dir)
    calendar: dict[str, dict[str, Any]] = {}
    note = ""
    if any(r.obligation for r in rows):
        try:
            from jason.tasks.deadlines import calendar as build

            calendar = {o["name"]: o for o in build(root, community, today=today)["obligations"]}
        except Exception as exc:  # noqa: BLE001 - the list still stands without the calendar
            note = f"The deadlines calendar could not be read: {exc}"
    items = []
    for r in rows:
        entry: dict[str, Any] = {"item": r.item, "standing": r.standing.value, "changes": r.changes, "searched": r.searched,
                                 "evidence": doc_refs(r.evidence, root)}
        if r.obligation:
            row = calendar.get(r.obligation)
            if row:
                entry["standing"] = _FROM_CALENDAR.get(row["standing"], "unknown")
                entry["obligation"] = {"name": r.obligation, "next": row.get("next"), "lastDone": row.get("lastDone"),
                                       "daysLeft": row.get("daysLeft")}
            else:
                entry["standing"] = "unknown"
                entry["obligation"] = {"name": r.obligation}
        items.append(entry)
    order = {"overdue": 0, "unknown": 1, "partly answered": 2, "current": 3, "not applicable": 4}
    items.sort(key=lambda i: order.get(i["standing"], 1))
    out = {"found": True, "items": items, "command": "jason deadlines",
           "caveats": ["A record kept under another name is not seen: a person confirms before treating an item as missing.",
                       "An unknown standing is not a finding that the thing was not done."]}
    if note:
        out["note"] = note
    return out


__all__ = ["SNAPSHOT", "check_tester", "watchlist", "doc_refs", "fetch_tester_lists", "notice_clock", "parse_tester_list", "view", "view_lines"]
