"""Related documents for each event in the incident history, found by several searches from what the event knows.

An event knows its claim numbers, its units (street addresses), its buildings, its vendors, and its dates. Each is a
search key, and each store is searched the way it can be:

- Drive (read-only API): full text for each claim number, and for each unit's address beside a claim or repair word;
- Gmail (read-only API): the message search for each claim number, and for each address with a claim or repair word
  inside the event's dates, reading only the headers and the attachment names, never a body;
- the stored email headers and saved attachments (``jason gmail``): subjects and file names that carry a key;
- the stored PayHOA ledger: entries inside the event's dates whose description or memo names the unit or a vendor;
- the library's text (minutes, agendas, notices): passages naming the unit or a claim inside the dates;
- the stored mail (PostScanMail): letters naming a claim number or the unit.

Every hit keeps why it matched. A Drive hit not yet in the evidence is fetched into ``data/drive/evidence`` as a linked
file, so the next ``jason incidents`` reads it into its event; a medical or veterinary record is never fetched. The
report is ``data/reports/incident-links.json``. Nothing is sent, moved, or changed anywhere.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from jason.community.incidents import claim_key

REPORT = "incident-links.json"
WINDOW_BEFORE = 30
WINDOW_AFTER = 150
MAX_DRIVE_HITS = 40
MAX_GMAIL_HITS = 40
EVENT_WORDS = ("claim", "leak", "damage", "repair", "water", "insurance", "adjuster", "mitigation", "roof", "estimate")
# Folders whose files are about people, not the property: a hit there is listed but never fetched.
# An owner's own ledger account (receivables, assessments, a unit's address) is the owner's standing, not work.
UNIT_ACCOUNT = re.compile(r"receivable|assessment|owner|prepaid|^\d{4} |unit", re.I)
# Subjects and attachment names that are about work or a claim; resale packets and governing documents are not.
EVENT_SUBJECT = re.compile(r"claim|leak|damage|repair|water|roof|flood|mitigation|estimate|invoice|insurance|emergency|collision|"
                           r"inspection|intrusion|mold|fire|tree|plumb|drain", re.I)
REPAIR_FILE = re.compile(r"claim|leak|damage|repair|estimate|invoice|proposal|mitigation|report|photo|pics|intrusion|test|"
                         r"work order|authorization|statement of loss|outcome|adjust|case performance", re.I)
NOT_REPAIR_FILE = re.compile(r"resale|questionnaire|registration|violation|ccrs|bylaws|articles|owner.s manual|budget|"
                             r"certificate of (?:liability|property)|condominium plan|minutes|agenda|reserve study|demand", re.I)
REPAIR_ACCOUNT = re.compile(r"repair|insurance|improvement|emergency|reserve|claim", re.I)
PEOPLE_FOLDERS = re.compile(r"Resident Registration|Collections|Disciplinary|Delinquencies|Registration/|Membership|Elections", re.I)


def event_id(row: dict[str, Any]) -> str:
    """A stable name for a stored event: its first day and its place, with a short hash of its claims and causes."""
    place = (row["addresses"] or [f"building {b}" for b in row["buildings"]] or ["community"])[0]
    digest = hashlib.sha1(json.dumps([row["first"], row["addresses"], row["claims"], row["causes"][:2]]).encode()).hexdigest()[:6]
    return f"{row['first']}:{place.lower().replace(' ', '-')}:{digest}"


def keys_of(row: dict[str, Any]) -> dict[str, Any]:
    """What an event can be searched by."""
    first = date.fromisoformat(row["first"]) if row["first"] else None
    last = date.fromisoformat(row["last"]) if row["last"] else first
    units = []
    for address in row["addresses"]:
        number, *street = address.split()
        units.append({"address": address, "short": f"{number} {street[0].title()}" if street else number})
    return {"claims": sorted({claim_key(c) for c in row["claims"]}), "units": units, "buildings": row["buildings"],
            "vendors": [v for v in row["vendors"] if v and len(v) > 3], "from": first - timedelta(days=WINDOW_BEFORE) if first else None,
            "to": last + timedelta(days=WINDOW_AFTER) if last else None}


def wanted(row: dict[str, Any]) -> bool:
    """The events worth a search: a claim, a sudden cause, or a unit with a repair."""
    return bool(row["claimed"] or row.get("otherInsurerClaims") or row["sudden"] or (row["addresses"] and "repair" in row["work"]))


# -- remote searches -------------------------------------------------------------------------------------------------


def drive_hits(drive: Any, keys: dict[str, Any], files: dict[str, dict[str, Any]], private: tuple[str, ...]) -> list[dict[str, Any]]:
    queries = [(f'fullText contains "{c}"', f"claim {c}") for c in keys["claims"]]
    # A unit by its file names only: its address fills every page a board member who lives there signs or orders.
    for unit in keys["units"]:
        number, word = unit["short"].split()[0], unit["short"].split()[1]
        queries.append((f'name contains "{number}" and name contains "{word}"', f"{unit['short']} in the file name"))
    found: dict[str, dict[str, Any]] = {}
    for query, why in queries:
        try:
            rows = drive.list_files(f"{query} and trashed = false", fields="id,name,mimeType,modifiedTime,size")
        except Exception:
            continue
        for r in rows[:MAX_DRIVE_HITS]:
            path = (files.get(r["id"]) or {}).get("path", "")
            if any(fnmatch.fnmatchcase(r["name"], g) for g in private) or NOT_REPAIR_FILE.search(r["name"]) or PEOPLE_FOLDERS.search(path):
                continue
            if "file name" in why and not REPAIR_FILE.search(r["name"]):
                continue  # a unit's closing papers, hearing packets, and folders are not its repairs
            hit = found.setdefault(r["id"], {"source": "drive", "id": r["id"], "title": r["name"],
                                             "ref": (files.get(r["id"]) or {}).get("path", r["name"]), "mimeType": r.get("mimeType"),
                                             "size": r.get("size"), "day": (r.get("modifiedTime") or "")[:10], "why": []})
            hit["why"].append(why)
    return list(found.values())


def gmail_hits(gmail: Any, keys: dict[str, Any]) -> list[dict[str, Any]]:
    """Messages found by Gmail's own search, read by their headers and attachment names only."""
    window = ""
    if keys["from"] and keys["to"]:
        window = f" after:{keys['from']:%Y/%m/%d} before:{keys['to']:%Y/%m/%d}"
    queries = [(f'"{c}"', f"claim {c}") for c in keys["claims"]]
    for unit in keys["units"]:
        queries.append((f'"{unit["short"]}" ({" OR ".join(EVENT_WORDS)}){window}', f"{unit['short']} in the event's dates"))
    found: dict[str, dict[str, Any]] = {}
    for query, why in queries:
        try:
            ids = [m["id"] for m in gmail.iter_messages(query, limit=MAX_GMAIL_HITS)]
        except Exception:
            continue
        for mid in ids:
            if mid in found:
                found[mid]["why"].append(why)
                continue
            try:
                meta = gmail.get_metadata(mid, headers=("From", "Subject", "Date"))
            except Exception:
                continue
            headers = meta.get("headers") or {}
            # An address search matches bodies; keep the message only when its subject names the unit.
            subject_line = str(headers.get("Subject") or "")
            if not why.startswith("claim") and (why.split()[0] not in subject_line or not EVENT_SUBJECT.search(subject_line)):
                continue
            sender = str(headers.get("From") or "")
            domain = sender.rsplit("@", 1)[-1].strip(" >").lower() if "@" in sender else ""
            found[mid] = {"source": "gmail", "id": mid, "title": str(headers.get("Subject") or ""), "from": domain,
                          "day": _gmail_day(str(headers.get("Date") or "")),
                          "attachments": [a["name"] for a in meta.get("attachments") or []],
                          "files": [a for a in meta.get("attachments") or [] if a.get("attachmentId")], "why": [why]}
    return list(found.values())


def _gmail_day(value: str) -> str:
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(value).date().isoformat()
    except Exception:
        return ""


# -- local searches --------------------------------------------------------------------------------------------------


def _in_window(day: str, keys: dict[str, Any]) -> bool:
    if not day or not keys["from"]:
        return True
    try:
        d = date.fromisoformat(day[:10])
    except ValueError:
        return True
    return keys["from"] <= d <= keys["to"]


def _names(keys: dict[str, Any]) -> list[tuple[str, str]]:
    """(pattern, why) pairs for the text searches: claim numbers anywhere, and each unit's address."""
    out = [(re.escape(c), f"claim {c}") for c in keys["claims"]]
    for unit in keys["units"]:
        number, word = unit["short"].split()[0], unit["short"].split()[1]
        out.append((rf"\b{number}\s+{word}", unit["short"]))
    return out


def local_hits(data_dir: Path, keys: dict[str, Any]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    patterns = _names(keys)
    if not patterns:
        return hits
    # Stored email headers and saved attachments.
    corr = Path(data_dir) / "gmail" / "correspondence.json"
    if corr.is_file():
        data = json.loads(corr.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [])
        for m in rows:
            words = " ".join([str(m.get("subject") or "")] + [str(a) for a in (m.get("attachments") or [])])
            for pattern, why in patterns:
                unit_ok = _in_window(str(m.get("at") or ""), keys) and re.search("|".join(EVENT_WORDS), words, re.I)
                if re.search(pattern, words, re.I) and (why.startswith("claim") or unit_ok):
                    hits.append({"source": "email header", "id": m.get("messageId"), "title": m.get("subject"), "day": str(m.get("at") or "")[:10],
                                 "from": ",".join(m.get("domains") or []), "attachments": m.get("attachments") or [], "why": [why]})
                    break
    # The stored ledger: entries in the dates naming the unit or a vendor.
    ledger = Path(data_dir) / "payhoa" / "ledger.db"
    if ledger.is_file() and keys["from"]:
        vendor_words = []
        for v in keys["vendors"]:
            words = v.split(",")[0].upper().split()
            if words:
                vendor_words.append(words[0] if len(words[0]) > 3 or len(words) == 1 else " ".join(words[:2]))
        with sqlite3.connect(ledger) as db:
            rows = db.execute("select day, account, description, memo, vendor, debit, credit from entries where day between ? and ? "
                              "and account not like '%Operating%' and account not like '%Reserve%'",
                              (keys["from"].isoformat(), keys["to"].isoformat())).fetchall()
        near_from = (keys["from"] + timedelta(days=WINDOW_BEFORE - 7)) if keys["from"] else None
        near_to = (keys["to"] - timedelta(days=WINDOW_AFTER - 60)) if keys["to"] else None
        for day, account, description, memo, vendor, debit, credit in rows:
            if UNIT_ACCOUNT.search(account or ""):
                continue
            words = f"{description} {memo} {vendor}".upper()
            why = next((w for p, w in patterns if re.search(p, words, re.I)), None) or \
                (next((f"vendor {v}" for v in vendor_words if v and len(v) > 3 and v in words), None)
                 if REPAIR_ACCOUNT.search(account or "") and near_from and near_from.isoformat() <= day <= near_to.isoformat() else None)
            if why:
                hits.append({"source": "ledger", "id": f"{day}:{description[:40]}", "title": f"{account}: {description[:80]} {memo or ''}".strip(),
                             "day": day, "amountCents": debit or -credit, "why": [why]})
    # The library's text: minutes, agendas, notices.
    library = Path(data_dir) / "library" / "library.db"
    if library.is_file():
        with sqlite3.connect(library) as db:
            docs = db.execute("select id, path, kind, period from documents where kind in ('minutes','agenda','notice','correspondence',"
                              "'executive_session','resolution')").fetchall()
        for ident, path, kind, period in docs:
            text_path = Path(data_dir) / "library" / "text" / f"{ident}.txt"
            if not text_path.is_file():
                continue
            text = text_path.read_text(encoding="utf-8", errors="replace")
            for pattern, why in patterns:
                m = re.search(pattern, text, re.I)
                if m and (why.startswith("claim") or _in_window(str(period or ""), keys) or not period):
                    passage = " ".join(text[max(0, m.start() - 120): m.end() + 160].split())
                    hits.append({"source": "library", "id": ident, "title": path, "kind": kind, "day": str(period or ""),
                                 "passage": passage, "why": [why]})
                    break
    # The stored mail.
    mail_dir = Path(data_dir) / "mail"
    if mail_dir.is_dir():
        for text_file in mail_dir.glob("*/text.txt"):
            text = text_file.read_text(encoding="utf-8", errors="replace")
            for pattern, why in patterns:
                if why.startswith("claim") and re.search(pattern, text, re.I):
                    hits.append({"source": "mail", "id": text_file.parent.name, "title": text.strip().splitlines()[0][:80] if text.strip() else "",
                                 "day": "", "why": [why]})
                    break
    return hits


# -- the run ---------------------------------------------------------------------------------------------------------


def link(data_dir: Path, community: Any, *, drive: Any = None, gmail: Any = None, fetch: bool = True,
         log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Search for each wanted event's related documents, fetch new Drive hits as linked evidence, and store the links."""
    from jason.tasks.drive_catalog import load_files
    from jason.tasks.incidents import EVIDENCE_INDEX, _sha_file, evidence_dir, load, load_evidence_index

    report = load(data_dir)
    if not report.get("found"):
        return {"found": False, "note": "run `jason incidents` first"}
    plan = community.evidence_plan()
    private = tuple(plan.private_names) if plan else ()
    files = {f["id"]: f for f in load_files(data_dir)} if drive is not None else {}
    index = load_evidence_index(data_dir)
    have = set(index.get("files", {}))
    events = [r for r in report["events"] if wanted(r)]
    out: dict[str, Any] = {}
    fetched = 0
    kept: set[str] = set()
    kept_mail: set[str] = set()
    for n, row in enumerate(events, 1):
        keys = keys_of(row)
        hits = local_hits(data_dir, keys)
        if drive is not None:
            hits += drive_hits(drive, keys, files, private)
        if gmail is not None:
            hits += gmail_hits(gmail, keys)
        kept.update(h["id"] for h in hits if h["source"] == "drive")
        kept_mail.update(h["id"] for h in hits if h["source"] == "gmail")
        own = {d["ref"] for d in row["documents"]} | {a for d in row["documents"] for a in d.get("also") or []}
        new = [h for h in hits if not (h["source"] == "drive" and (h["id"] in have and any(h["ref"] in o for o in own)))]
        for h in new:
            h["inEvidence"] = h["source"] == "drive" and h["id"] in have
        if fetch and drive is not None:
            for h in new:
                if h["source"] != "drive" or h["inEvidence"] or PEOPLE_FOLDERS.search(h["ref"]):
                    continue
                mime = h.get("mimeType") or ""
                if not (mime.endswith("pdf") or mime == "application/vnd.google-apps.document") or int(h.get("size") or 0) > 25_000_000:
                    continue
                local = evidence_dir(data_dir) / f"{h['id']}.pdf"
                try:
                    if mime == "application/vnd.google-apps.document":
                        drive.export_pdf(h["id"], local)
                    else:
                        drive.download(h["id"], local)
                except Exception:
                    continue
                meta = files.get(h["id"]) or {}
                index.setdefault("files", {})[h["id"]] = {
                    "name": h["title"], "path": meta.get("path", h["ref"]), "folder": "linked", "confidential": True,
                    "modified": meta.get("modified"), "md5": meta.get("md5"), "size": h.get("size"),
                    "local": str(local.relative_to(data_dir)), "sha256": _sha_file(local), "linkedTo": event_id(row)}
                have.add(h["id"])
                h["fetched"] = True
                fetched += 1
        if fetch and gmail is not None:
            fetched += _save_attachments(data_dir, gmail, [h for h in new if h["source"] == "gmail"], private, event_id(row))
        for h in new:
            h.pop("files", None)
        out[event_id(row)] = {"first": row["first"], "last": row["last"], "addresses": row["addresses"], "buildings": row["buildings"],
                              "claims": row["claims"], "causes": row["causes"], "keys": {k: (str(v) if isinstance(v, date) else v) for k, v in keys.items()},
                              "links": sorted(new, key=lambda h: (h.get("day") or "", h["source"]))}
        if log and n % 10 == 0:
            log(f"  searched {n} of {len(events)} events")
    if gmail is not None:
        saved, reports = fetch_case_reports(data_dir, gmail, private, query=getattr(plan, "case_report_query", ""))
        fetched += saved
        kept_mail |= reports
        pruned_mail = _prune_mail(data_dir, kept_mail)
    else:
        pruned_mail = 0
    # A file an earlier, looser search linked and this one does not find again leaves the evidence.
    pruned = 0
    for ident in [i for i, row in index.get("files", {}).items() if row.get("folder") == "linked" and i not in kept]:
        local = Path(data_dir) / index["files"][ident]["local"]
        if local.is_file():
            local.unlink()
        del index["files"][ident]
        pruned += 1
    (evidence_dir(data_dir).parent / EVIDENCE_INDEX).write_text(json.dumps(index, indent=1), encoding="utf-8")
    result = {"found": True, "builtAt": datetime.now().isoformat(timespec="seconds"), "events": len(events), "fetched": fetched, "pruned": pruned, "prunedMail": pruned_mail,
              "links": out}
    path = Path(data_dir) / "reports" / REPORT
    path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def _save_attachments(data_dir: Path, gmail: Any, hits: list[dict[str, Any]], private: tuple[str, ...], linked_to: str) -> int:
    """Save the PDF attachments of the Gmail hits that ``jason gmail --files`` has not, into its folder and its index, so the
    incident history reads them as email attachments. A medical or veterinary record's name is never saved."""
    from jason.tasks.gmail import FILE_INDEX, email_files

    index_path = Path(data_dir) / "gmail" / FILE_INDEX
    stored = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {"files": []}
    known = {(f.get("messageId"), f.get("name")) for f in email_files(data_dir)}
    saved = 0
    for h in hits:
        for f in h.get("files") or []:
            name = str(f.get("name") or "")
            claim_hit = any(w.startswith("claim") for w in h.get("why") or [])
            if not name.lower().endswith(".pdf") or (h["id"], name) in known or any(fnmatch.fnmatchcase(name, g) for g in private):
                continue
            if not (claim_hit or REPAIR_FILE.search(name)) or NOT_REPAIR_FILE.search(name):
                continue
            try:
                data = gmail.get_attachment(h["id"], f["attachmentId"])
            except Exception:
                continue
            rel = Path("gmail") / "files" / h["id"] / re.sub(r'[<>:"/\\|?*]', "_", name)
            (Path(data_dir) / rel).parent.mkdir(parents=True, exist_ok=True)
            (Path(data_dir) / rel).write_bytes(data)
            stored.setdefault("files", []).append({
                "messageId": h["id"], "at": h.get("day"), "direction": "in", "domains": [h.get("from")] if h.get("from") else [],
                "subject": h.get("title") or "", "name": name, "path": str(rel), "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "linkedTo": linked_to})
            known.add((h["id"], name))
            saved += 1
    index_path.write_text(json.dumps(stored, indent=1), encoding="utf-8")
    return saved


def fetch_case_reports(data_dir: Path, gmail: Any, private: tuple[str, ...] = (), *, query: str = "") -> tuple[int, set[str]]:
    """Every manager case report in Gmail (a manager's weekly "Case Performance" PDFs), saved beside the synced
    email attachments; the incident history reads each open case about the property. ``query`` is the Gmail search
    that finds them (``EvidencePlan.case_report_query``); without one nothing is searched. Returns the count saved
    and the messages found, which keep their saved files from pruning."""
    if not query:
        return 0, set()
    hits = []
    for row in gmail.iter_messages(query, limit=400):
        try:
            meta = gmail.get_metadata(row["id"], headers=("From", "Subject", "Date"))
        except Exception:
            continue
        headers = meta.get("headers") or {}
        files = [a for a in meta.get("attachments") or [] if a.get("attachmentId") and "case performance" in a["name"].lower()]
        if files:
            hits.append({"source": "gmail", "id": row["id"], "title": str(headers.get("Subject") or ""), "from": "",
                         "day": _gmail_day(str(headers.get("Date") or "")), "files": files, "why": ["claim: manager case report"]})
    return _save_attachments(data_dir, gmail, hits, private, "manager case reports"), {h["id"] for h in hits}


def _prune_mail(data_dir: Path, kept: set[str]) -> int:
    """Drop the attachments an earlier, looser search saved for messages this one does not find again."""
    from jason.tasks.gmail import FILE_INDEX

    path = Path(data_dir) / "gmail" / FILE_INDEX
    if not path.is_file():
        return 0
    stored = json.loads(path.read_text(encoding="utf-8"))
    keep, dropped = [], 0
    for f in stored.get("files") or []:
        if f.get("linkedTo") and f.get("messageId") not in kept:
            local = Path(data_dir) / f["path"]
            if local.is_file():
                local.unlink()
            dropped += 1
            continue
        keep.append(f)
    stored["files"] = keep
    path.write_text(json.dumps(stored, indent=1), encoding="utf-8")
    return dropped


def load_links(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / "reports" / REPORT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"found": False}


def link_lines(result: dict[str, Any], *, event: str = "", limit: int = 12) -> list[str]:
    if not result.get("found"):
        return ["No links yet; run `jason incidents --link`."]
    out = [f"Related documents for {result['events']} events ({result.get('fetched', 0)} Drive files fetched as linked evidence)."]
    for eid, e in result["links"].items():
        if event and event not in eid:
            continue
        links = e["links"]
        if not links:
            continue
        where = ", ".join(e["addresses"]) or ", ".join(f"building {b}" for b in e["buildings"]) or "community"
        out.append(f"\n{e['first']}..{e['last']} {where} | {', '.join(e['causes'][:2])} | claims {', '.join(e['claims']) or '-'}")
        for h in links[:limit]:
            out.append(f"   {h.get('day') or '':<10} {h['source']:<12} {str(h.get('title') or '')[:80]} | {'; '.join(h['why'])[:60]}")
        if len(links) > limit:
            out.append(f"   ... {len(links) - limit} more")
    return out


__all__ = ["event_id", "keys_of", "wanted", "drive_hits", "gmail_hits", "local_hits", "link", "load_links", "link_lines"]
