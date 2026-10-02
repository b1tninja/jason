"""The association's building permits from Sacramento Citizen Access: every record, and the open ones in full.

``sync`` reads, with a signed-in ``SacramentoCitizenAccess`` (``jason.community.accela``), the collection the
specification names (``mystique/permits.py``): its totals and every record row (all pages), and each record that is not
closed (Finaled, Expired, ...) in full: its status, conditions, inspections, fees paid and unpaid, review tasks, and
related records. Everything is saved under ``data/accela``.

``permits`` reads it back: each open record with its status, what it waits on (the last review mark, conditions not
met), its fees due, and the collection's totals (fees paid and due, inspections by result). Money is cents.

The portal is read, never written: jason pays no fee (the portal hands payment to Paymentus), schedules no inspection,
and uploads nothing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

ACCELA_DIR = "accela"
_MET = ("resolved", "met", "condition met")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _closed(status: str, closed: tuple[str, ...]) -> bool:
    return any(status.lower().startswith(s.lower()) for s in closed) or "expired" in status.lower()


def sync(client: Any, data_dir: Path, portal: Any, closed: tuple[str, ...], *, everything: bool = False,
         log: Callable[[str], None] | None = None) -> dict[str, int]:
    say = log or (lambda _m: None)
    root = Path(data_dir) / ACCELA_DIR
    (root / "records").mkdir(parents=True, exist_ok=True)
    collections = client.collections()
    found = next((c for c in collections if c.name.lower() == portal.collection.lower()), None)
    if found is None:
        raise LookupError(f"no collection named {portal.collection!r} on the account (have: {[c.name for c in collections]})")
    summary, records = client.collection(found.id)
    say(f"collection {portal.collection}: {len(records)} records")
    (root / "collection.json").write_text(json.dumps(_jsonable({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                                                 "collectionId": found.id, "summary": summary, "records": records}),
                                                     indent=1), encoding="utf-8")
    read = 0
    for record in records:
        if record.cap is None or (not everything and _closed(record.status, closed)):
            continue
        detail = client.detail(record.cap)
        (root / "records" / f"{record.number}.json").write_text(
            json.dumps(_jsonable({"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "number": record.number,
                                  "detail": detail, "paidCents": detail.paid_cents, "unpaidCents": detail.unpaid_cents,
                                  "feesComplete": detail.fees_complete}), indent=1),
            encoding="utf-8")
        read += 1
        say(f"  {record.number} {record.status}")
    return {"records": len(records), "readInFull": read}


def permits(data_dir: Path, *, number: str = "") -> dict[str, Any]:
    root = Path(data_dir) / ACCELA_DIR
    path = root / "collection.json"
    if not path.is_file():
        return {"found": False, "hint": "run jason permit-status --sync"}
    coll = json.loads(path.read_text(encoding="utf-8"))
    details = {}
    for f in (root / "records").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        details[d.get("number") or f.stem] = d
    out = []
    for r in coll["records"]:
        if number and number.upper() not in (r["number"] or "").upper():
            continue
        entry: dict[str, Any] = {"number": r["number"], "type": r["record_type"], "status": r["status"], "opened": r["opened"],
                                 "address": r["address"], "description": (r["description"] or "")[:160], "readInFull": r["number"] in details}
        d = details.get(r["number"])
        if d:
            detail = d["detail"]
            marks = [(m.get("when") or "", t["name"], m.get("status")) for t in detail.get("tasks") or [] for m in t.get("marks") or []]
            conditions = detail.get("conditions") or []
            entry.update({
                "status": detail.get("status") or r["status"],
                "feesDueCents": d.get("unpaidCents") or 0,
                "feesPaidCents": d.get("paidCents") or 0,
                "feesPrinted": {"paidCents": detail.get("paid_total_cents"), "dueCents": detail.get("unpaid_total_cents")},
                "feesComplete": d.get("feesComplete", True),
                "lastMark": max(marks, default=None),
                "openConditions": [{"name": c["name"], "status": c["status"], "applied": c["applied"]} for c in conditions
                                   if (c.get("status") or "").lower() not in _MET and (c.get("severity") or "").lower() != "notice"],
                "conditionsMet": sum(1 for c in conditions if (c.get("status") or "").lower() in _MET),
                "inspections": len(detail.get("inspections") or []),
                "related": [x["number"] for x in detail.get("related") or [] if x.get("number") != r["number"]],
            })
        out.append(entry)
    out.sort(key=lambda e: (not e["readInFull"], e["opened"] or ""))
    summary = coll.get("summary") or {}
    read_due = sum(e.get("feesDueCents") or 0 for e in out if e["readInFull"])
    unplaced = (summary.get("fees_due_cents") or 0) - read_due if not number else 0
    return {"found": True, "syncedAt": coll.get("syncedAt"), "collection": summary, "permits": out,
            "dueOnRecordsNotRead": max(unplaced, 0),
            "caveats": ["Read from the City's portal as of the sync; a fee paid since is not seen until the next sync.",
                        "A closed record (Finaled, Expired) is listed from the collection's row only; --all reads each in full.",
                        "A fee line's date is the invoice date, not the day it was paid.",
                        "The collection's fees paid include the developer's permits for the buildings, not only the association's.",
                        "Jason pays no fee, schedules no inspection, and uploads nothing to the portal."]}


def permit_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result.get("hint", "no permits on disk")]
    s = result.get("collection") or {}
    out = [f"Permits as of {str(result['syncedAt'])[:10]}: {s.get('records', '?')} records; fees paid ${(s.get('fees_paid_cents') or 0) / 100:,.2f}, "
           f"due ${(s.get('fees_due_cents') or 0) / 100:,.2f}; inspections {s.get('inspections', '?')} {s.get('inspections_by', {})}", ""]
    for p in result["permits"]:
        if not p["readInFull"]:
            continue
        out.append(f"{p['number']} {p['type']} - {p['status']} ({p['address']})")
        out.append(f"  fees due ${p['feesDueCents'] / 100:,.2f}, paid ${p['feesPaidCents'] / 100:,.2f}; conditions met {p['conditionsMet']}"
                   + (f"; open: {', '.join(c['name'] for c in p['openConditions'])}" if p["openConditions"] else ""))
        if not p.get("feesComplete", True):
            printed = p["feesPrinted"]
            out.append(f"  ! fee lines read do not match the portal's totals (paid {printed['paidCents']}, due {printed['dueCents']} cents)")
        if p.get("lastMark"):
            when, task, status = p["lastMark"]
            out.append(f"  last review mark: {task} marked {status}" + (f" on {when}" if when else ""))
    if result.get("dueOnRecordsNotRead"):
        out.append(f"${result['dueOnRecordsNotRead'] / 100:,.2f} of the collection's fees due is on records not read in full (sync --all to place it)")
    closed = [p for p in result["permits"] if not p["readInFull"]]
    if closed:
        out.append("")
        out.append(f"Other records ({len(closed)}): " + ", ".join(f"{p['number']} {p['status']}" for p in closed[:14]) + (" ..." if len(closed) > 14 else ""))
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["sync", "permits", "permit_lines"]
