"""The association's insurance policies, term by term, from their own documents, the policy sheet, and the specification.

The specification (``Mystique.insurance().policies``) names each policy: kind, carrier, program, agent, the number in
force and its earlier numbers, the end of the term in force, and the master policy's deductible. The board's policy
sheet ("Vendors, Utilities, Accounts, Taxes, and Insurance", tab Insurance) carries the number, renewal date, and
premium by year, and links the policy files. This task:

1. reads the sheet's Insurance tab (read-only);
2. finds every Drive file that prints one of a policy's numbers (the Drive full-text search, read-only), plus the files
   the sheet links, and keeps the ones that are the policy's own papers: declarations and policy forms, binders and
   evidence, certificates, renewal and cancellation notices, premium invoices, and the annual insurance disclosure;
3. fetches them into ``data/insurance/documents`` (one copy per content), and reads each with its document model
   (``jason.community.models.contracts_insurance`` for declarations and certificates);
4. puts each policy's terms, limits, deductibles, premiums, and documents on one page (``data/insurance/pages``) and
   compares the specification, the sheet, and the documents.

The pages and the documents' text are the passage index's ``insurance`` catalog (``jason index --build``; a page is
generated, a summary), so questions about coverage are answered from the policies themselves. A claim's papers stay in the incident history,
not here. Nothing is sent, moved, or changed in Drive, the sheet, or PayHOA.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

REPORT = "policies.json"
ROOT = "insurance"
SHEET_TAB = "Insurance"

# What a policy file is, by its name first and its first page second. Order matters: a renewal invoice is an invoice.
ROLES: tuple[tuple[str, str], ...] = (
    ("claim", r"claim|status letter to insured|loss run"),
    ("certificate", r"certificate of (?:property |liability )?insurance|\bCOI\b|acord|evidence of (?:property )?insurance"),
    ("disclosure", r"annual disclosure|insurance summary|disclosure"),
    ("invoice", r"invoice|premium due|amount due|renewal \d{2}-\d{2}-\d{4}|installment"),
    ("cancellation", r"cancel"),
    ("renewal notice", r"renewal notice|notice of (?:conditional )?renewal|non-?renewal|RNL|renewal offer"),
    ("declarations", r"declarations?|dec page|policy\s+\w+\s+\w+\s+\d{2}-\d{2}|flood policy|\bFLD\b|binder|\bpolicy\b|TRIA|evidence - "),
)
# A file carrying a number that is not the policy's own paper: a lawsuit's demand, a lender's questionnaire, a resale
# packet, the books, the minutes, the sheet itself.
NOT_POLICY = re.compile(r"demand|questionnaire|resale|statements-|treasurer|minutes|agenda|budget|financial (?:statement|review)|"
                        r"REVIEW - MYSTIQUE|HOA Demand|Vendors,\s+Utilities|Dog Attack|Complaints|Case Summary|Shared with me", re.I)


@dataclass
class SheetRow:
    kind: str
    building: str
    number: str
    link_id: str
    renewal: date | None
    premiums: dict[int, int] = field(default_factory=dict)   # year -> cents


def _money(text: str) -> int | None:
    m = re.search(r"\$?\s*([\d,]+(?:\.\d\d)?)", text or "")
    if not m or not m.group(1).replace(",", "").replace(".", "").isdigit():
        return None
    return round(float(m.group(1).replace(",", "")) * 100)


def _us(text: str) -> date | None:
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})", text or "")
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None
    except ValueError:
        return None


def _drive_id(link: str) -> str:
    m = re.search(r"(?:id=|/d/)([\w-]{20,})", link or "")
    return m.group(1) if m else ""


def read_sheet(sheets: Any, spreadsheet_id: str) -> list[SheetRow]:
    """The Insurance tab's rows: kind, building, number (and its linked file), renewal date, and premium by year."""
    grid = sheets.grid(spreadsheet_id, SHEET_TAB)
    if not grid:
        return []
    header = [c.get("value") or "" for c in grid[0]]
    years = {i: int(m.group(1)) for i, h in enumerate(header) if (m := re.match(r"(\d{4}) Premium", h))}
    col = {h: i for i, h in enumerate(header)}
    out = []
    for row in grid[1:]:
        cells = [c.get("value") or "" for c in row] + [""] * len(header)
        kind = cells[col.get("Type", 1)]
        if not kind:
            continue
        link = next((c.get("link") for c in row if c.get("link")), "") or ""
        premiums = {y: v for i, y in years.items() if (v := _money(cells[i]))}
        out.append(SheetRow(kind, cells[col.get("Bldg", 2)], cells[col.get("NFIP # / Policy Number", 3)].strip(), _drive_id(link),
                            _us(cells[col.get("Renewal Date", 4)]), premiums))
    return out


def policy_key(policy: Any) -> str:
    kind = policy.kind.name.lower().replace("_", "-")
    return f"{kind}-{int(policy.building)}" if policy.building else kind


def sheet_row_for(policy: Any, rows: list[SheetRow]) -> SheetRow | None:
    numbers = {n.upper() for n in policy.numbers}
    by_number = next((r for r in rows if r.number.upper() in numbers), None)
    if by_number:
        return by_number
    label = {"MASTER": "Master", "UMBRELLA": "Umbrella", "FIDELITY": "Fidelity", "DIRECTORS_AND_OFFICERS": "D&O",
             "WORKERS_COMP": "Workers Comp", "FLOOD": "Flood"}.get(policy.kind.name, "")
    for r in rows:
        if r.kind == label and (not policy.building or r.building == str(int(policy.building))):
            return r
    return None


def role_of(name: str, text: str = "") -> str:
    for role, pattern in ROLES:
        if re.search(pattern, name or "", re.I):
            return role
    head = (text or "")[:2000]
    for role, pattern in ROLES:
        if re.search(pattern, head, re.I):
            return role
    return "other"


# -- finding and fetching --------------------------------------------------------------------------------------------


def find(drive: Any, community: Any, sheet: list[SheetRow], files: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Every Drive file that prints one of a policy's numbers, or that the sheet links, by policy."""
    out: dict[str, dict[str, Any]] = {}
    for policy in community.insurance().policies:
        key = policy_key(policy)
        hits: dict[str, dict[str, Any]] = {}
        for number in policy.numbers:
            for query in (f"fullText contains '\"{number}\"'", f"name contains '{number}'"):
                try:
                    rows = drive.list_files(f"{query} and trashed = false", fields="id,name,mimeType,modifiedTime,size,md5Checksum")
                except Exception:
                    continue
                for r in rows:
                    h = hits.setdefault(r["id"], {**r, "path": (files.get(r["id"]) or {}).get("path", r["name"]), "numbers": []})
                    if number not in h["numbers"]:
                        h["numbers"].append(number)
        row = sheet_row_for(policy, sheet)
        if row and row.link_id and row.link_id not in hits:
            meta = files.get(row.link_id) or {}
            try:
                meta = {**drive.get_file(row.link_id), **meta}
            except Exception:
                pass
            hits[row.link_id] = {"id": row.link_id, "name": meta.get("name", row.number), "mimeType": meta.get("mimeType", ""),
                                 "path": meta.get("path", meta.get("name", "")), "numbers": [row.number], "sheetLink": True}
        out[key] = {"numbers": list(policy.numbers), "files": hits}
    return out


def fetch(drive: Any, data_dir: Path, found: dict[str, dict[str, Any]], *, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Download each policy's own papers (not a lawsuit's, a lender's, or the books') into ``data/insurance/documents``,
    one copy per content, and index them by policy."""
    folder = Path(data_dir) / ROOT / "documents"
    folder.mkdir(parents=True, exist_ok=True)
    index_path = Path(data_dir) / ROOT / "documents.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.is_file() else {"files": {}}
    by_md5 = {v.get("md5"): k for k, v in index["files"].items() if v.get("md5")}
    fetched = 0
    for key, entry in found.items():
        for fid, h in entry["files"].items():
            mime = h.get("mimeType") or ""
            if NOT_POLICY.search(h.get("path") or h.get("name") or ""):
                continue
            if not (mime.endswith("pdf") or mime == "application/vnd.google-apps.document"):
                continue
            md5 = h.get("md5Checksum")
            known = index["files"].get(fid) or (index["files"].get(by_md5[md5]) if md5 in by_md5 else None)
            if known is None:
                day = (h.get("modifiedTime") or "")[:10]
                safe = re.sub(r'[<>:"/\\|?*]+', "_", h["name"]).strip()
                if not safe.lower().endswith(".pdf"):
                    safe += ".pdf"
                local = folder / f"{day} {safe}" if day else folder / safe
                if local.exists():
                    local = folder / f"{local.stem} {fid[:6]}.pdf"
                try:
                    if mime == "application/vnd.google-apps.document":
                        drive.export_pdf(fid, local)
                    else:
                        drive.download(fid, local)
                except Exception as exc:
                    if log:
                        log(f"  failed {h.get('path')}: {exc}")
                    continue
                known = index["files"][fid] = {"name": h["name"], "path": h.get("path"), "md5": md5, "modified": h.get("modifiedTime"),
                                               "local": str(local.relative_to(data_dir)), "policies": []}
                if md5:
                    by_md5[md5] = fid
                fetched += 1
            if key not in known["policies"]:
                known["policies"].append(key)
            for n in h.get("numbers") or []:
                known.setdefault("numbers", [])
                if n not in known["numbers"]:
                    known["numbers"].append(n)
            if h.get("sheetLink"):
                known["sheetLink"] = True
    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    return {"fetched": fetched, "documents": len(index["files"])}


def library_documents(data_dir: Path, community: Any) -> list[dict[str, Any]]:
    """The PayHOA library's policy papers (declarations, binders, certificates) whose text prints a policy's number."""
    import sqlite3

    path = Path(data_dir) / "library" / "library.db"
    if not path.is_file():
        return []
    numbers = {policy_key(p): [n for n in p.numbers if n] for p in community.insurance().policies}
    out = []
    with sqlite3.connect(path) as db:
        rows = db.execute("select id, path, name, sha256 from documents where kind in ('insurance_policy','evidence_of_insurance')").fetchall()
    for ident, rel, name, sha in rows:
        text_path = Path(data_dir) / "library" / "text" / f"{ident}.txt"
        local = Path(data_dir) / "library" / "files" / rel
        if not text_path.is_file():
            continue
        text = text_path.read_text(encoding="utf-8", errors="replace")
        flat = re.sub(r"[\s-]", "", text).upper()
        keys = [k for k, ns in numbers.items() if any(re.sub(r"[\s-]", "", n).upper() in flat for n in ns)]
        # A D&O binder's number can roll ("-01" for "-00"); the carrier's name ties it to its line.
        if re.search(r"D&O|Directors and Officers", name + text[:3000], re.I) and "directors-and-officers" not in keys:
            keys.append("directors-and-officers")
        if keys:
            out.append({"id": f"library:{ident}", "name": name, "path": f"library/{rel}", "local": str(local.relative_to(data_dir)),
                        "textFile": str(text_path.relative_to(data_dir)), "sha256": sha or "", "policies": keys})
    return out


POLICY_FILE = re.compile(r"^Policy\s|D&O|Evidence|FLOOD POLICY|Certificate of (?:Liability |Property )?Insurance|Declarations?|Binder|"
                         r"Renewal|TRIA|Loss Runs", re.I)


def email_documents(data_dir: Path, community: Any) -> list[dict[str, Any]]:
    """The email attachments that are policy papers (a D&O binder arrives only by email), matched to their policies by the
    numbers they print or, for a D&O binder, by its line."""
    from jason.tasks.gmail import email_files
    from jason.tasks.incidents import file_text

    numbers = {policy_key(p): [n for n in p.numbers if n] for p in community.insurance().policies}
    seen: set[str] = set()
    out = []
    for f in email_files(data_dir):
        name = str(f.get("name") or "")
        path = Path(data_dir) / f["path"]
        if not name.lower().endswith(".pdf") or not POLICY_FILE.search(name) or f["sha256"] in seen or not path.is_file():
            continue
        seen.add(f["sha256"])
        text = file_text(data_dir, path, f["sha256"])
        flat = re.sub(r"[\s-]", "", text).upper()
        keys = [k for k, ns in numbers.items() if any(re.sub(r"[\s-]", "", n).upper() in flat for n in ns)]
        if re.search(r"D&O|Directors and Officers", name + text[:3000], re.I) and "directors-and-officers" not in keys:
            keys.append("directors-and-officers")
        if keys:
            out.append({"id": f"email:{f['sha256'][:16]}", "name": name, "path": f["path"], "local": f["path"], "sha256": f["sha256"],
                        "modified": f.get("at"), "policies": keys})
    return out


# -- reading ---------------------------------------------------------------------------------------------------------


def _text(data_dir: Path, row: dict[str, Any]) -> str:
    from jason.tasks.incidents import _sha_file, file_text

    if row.get("textFile"):
        path = Path(data_dir) / row["textFile"]
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    local = Path(data_dir) / row["local"]
    if not local.is_file():
        return ""
    return file_text(data_dir, local, _sha_file(local))


def read_documents(data_dir: Path, community: Any, *, today: date | None = None) -> list[dict[str, Any]]:
    """Every policy paper read by its document model: the role, the model, its fields, and its findings."""
    from jason.community.document_models import ModelContext, read, to_plain
    from jason.community.symbols import DocumentKind

    index = json.loads((Path(data_dir) / ROOT / "documents.json").read_text(encoding="utf-8")) if (Path(data_dir) / ROOT / "documents.json").is_file() else {"files": {}}
    rows = [{"id": k, **v} for k, v in index["files"].items()] + library_documents(data_dir, community) + email_documents(data_dir, community)
    out = []
    for row in rows:
        text = _text(data_dir, row)
        role = role_of(row["name"], text)
        kinds = {"certificate": (DocumentKind.EVIDENCE_OF_INSURANCE,), "disclosure": (DocumentKind.ANNUAL_DISCLOSURE,),
                 "claim": ()}.get(role, (DocumentKind.INSURANCE_POLICY, DocumentKind.EVIDENCE_OF_INSURANCE))
        context = ModelContext(community=community, data_dir=Path(data_dir), today=today or date.today(), name=row["name"])
        reading = None
        for kind in kinds:
            reading = read(kind, text, context) if text else None
            if reading is not None:
                break
        out.append({"id": row["id"], "name": row["name"], "path": row.get("path"), "local": row.get("local"), "policies": row.get("policies", []),
                    "role": role, "sheetLink": bool(row.get("sheetLink")), "modified": (row.get("modified") or "")[:10],
                    "model": reading.model if reading else None, "fields": to_plain(reading.record) if reading else None,
                    "missing": list(reading.missing) if reading else [],
                    "findings": [f.as_dict() for f in reading.findings] if reading else []})
    return out


# -- one policy on a page --------------------------------------------------------------------------------------------


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _fold(number: str) -> str:
    return re.sub(r"[\s-]", "", number or "").upper()


def term_of(doc: dict[str, Any], policy: Any) -> dict[str, Any] | None:
    """A declarations reading as one term of ``policy``: its number, dates, premium, limits, and deductible."""
    f = doc.get("fields") or {}
    number = f.get("policy_number") or f.get("evidence_number") or ""
    if doc["model"] in (None, "acord-certificate", "annual-budget-report"):
        return None
    numbers = {_fold(n) for n in policy.numbers}
    if number and not any(n in _fold(number) for n in numbers):
        if not (policy.kind.name == "FLOOD" and f.get("building") and policy.building and f.get("building") == int(policy.building)):
            return None
    start, end = _day(f.get("term_start")), _day(f.get("term_end"))
    if not (start or end):
        return None
    limits = {k: f[k] for k in ("limit", "building_limit", "each_occurrence", "general_aggregate", "aggregate", "contents_limit") if f.get(k)}
    for a in f.get("agreements") or []:
        limits[a["name"]] = a["limit"]
    return {"number": number, "start": start.isoformat() if start else None, "end": end.isoformat() if end else None,
            "premium": f.get("premium"), "deductible": f.get("deductible") or f.get("property_deductible"), "limits": limits,
            "carrier": f.get("carrier"), "document": doc["name"], "path": doc["path"], "model": doc["model"]}


def build(community: Any, sheet: list[SheetRow], docs: list[dict[str, Any]], *, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    out = []
    for policy in community.insurance().policies:
        key = policy_key(policy)
        mine = [d for d in docs if key in d["policies"]]
        terms: dict[tuple, dict[str, Any]] = {}
        for d in mine:
            t = term_of(d, policy)
            if t:
                terms.setdefault((t["start"], t["end"]), t)
        terms_list = sorted(terms.values(), key=lambda t: t["start"] or "")
        row = sheet_row_for(policy, sheet)
        findings: list[dict[str, str]] = []

        def note(code: str, message: str, severity: str = "check") -> None:
            findings.append({"code": code, "message": message, "severity": severity})

        if row is None:
            note("not-on-sheet", "the policy sheet has no row for this policy")
        else:
            if row.number and policy.number and _fold(row.number) != _fold(policy.number):
                prior = _fold(row.number) in {_fold(n) for n in policy.prior_numbers}
                note("sheet-number", f"the sheet carries {row.number}" + (", an earlier term's number" if prior else "") +
                     f"; the term in force is {policy.number}: update the sheet")
            if row.renewal and policy.renewal and row.renewal != policy.renewal:
                if any(_day(t["end"]) == row.renewal for t in terms_list):
                    note("sheet-next-term", f"the sheet already carries the next term's end ({row.renewal}); its declarations are on file",
                         "info")
                else:
                    note("sheet-renewal", f"the sheet's renewal date is {row.renewal}; the specification's term in force ends {policy.renewal} "
                         "and no declarations end on the sheet's date")
            year = today.year
            if policy.renewal and not row.premiums.get(year) and policy.kind.name != "WORKERS_COMP":
                note("sheet-premium-missing", f"the sheet has no {year} premium")
        latest = terms_list[-1] if terms_list else None
        if policy.kind.name not in ("WORKERS_COMP",):
            if latest is None:
                note("no-declarations", "no declarations page for any term was found in Drive or the library", "problem")
            else:
                end = _day(latest["end"])
                if end and end < today:
                    note("declarations-ended", f"the latest declarations found run to {end}: the renewed term's declarations are not on file")
                if policy.renewal and end and end != policy.renewal and _day(latest["start"]) and _day(latest["start"]) < policy.renewal:
                    if end > policy.renewal:
                        note("next-term-on-file", f"declarations for the next term (to {end}) are on file; the specification's term in force "
                             f"ends {policy.renewal}", "info")
        for d in mine:
            if d["model"] in ("acord-certificate",):
                for line in (d.get("fields") or {}).get("lines") or []:
                    number = line.get("policy_number") or ""
                    if number and policy.kind.name == "DIRECTORS_AND_OFFICERS" and "SKN" in number.upper() and \
                            _fold(number) not in {_fold(n) for n in policy.numbers}:
                        note("certificate-number", f"a certificate ({d['name']}) names D&O policy {number}, not the specification's "
                             f"{policy.number}: the number rolled at renewal")
                        break
        model_findings = []
        if latest:
            doc = next((d for d in mine if d["name"] == latest["document"]), None)
            model_findings = [f for f in (doc or {}).get("findings", []) if not f["code"].startswith("missing-")]
        out.append({"key": key, "kind": policy.kind.name.lower(), "building": int(policy.building) if policy.building else None,
                    "carrier": policy.carrier, "program": policy.program, "agent": policy.agent, "number": policy.number,
                    "priorNumbers": list(policy.prior_numbers), "renewal": policy.renewal.isoformat() if policy.renewal else None,
                    "deductibleCents": policy.deductible_cents,
                    "sheet": {"number": row.number, "renewal": row.renewal.isoformat() if row.renewal else None,
                              "premiums": row.premiums, "linked": bool(row.link_id)} if row else None,
                    "terms": terms_list, "documents": [{"name": d["name"], "path": d["path"], "role": d["role"], "model": d["model"]}
                                                        for d in sorted(mine, key=lambda d: d["modified"] or "")],
                    "findings": findings + model_findings})
    return out


def _dollars(cents_value: Any) -> str:
    return f"${cents_value / 100:,.0f}" if isinstance(cents_value, (int, float)) and cents_value else "-"


def page(policy: dict[str, Any]) -> str:
    """One policy as a page for people and for the passage index: what it covers, each term, the sheet, the documents, findings."""
    title = policy["kind"].replace("_", " ").title() + (f" - Building {policy['building']}" if policy["building"] else "")
    lines = [f"# {title} policy", "",
             f"Carrier: {policy['carrier'] or '-'}. Program: {policy['program'] or '-'}. Agent: {policy['agent'] or '-'}.",
             f"Number in force: {policy['number'] or '-'} (earlier: {', '.join(policy['priorNumbers']) or 'none'}). "
             f"Term in force ends {policy['renewal'] or '-'}." + (f" Deductible {_dollars(policy['deductibleCents'])}." if policy["deductibleCents"] else ""),
             "", "## Terms read from the declarations", "",
             "| Term | Number | Premium | Deductible | Limits | Document |", "|---|---|---|---|---|---|"]
    for t in policy["terms"]:
        limits = "; ".join(f"{k.replace('_', ' ')} {_dollars(v)}" for k, v in t["limits"].items())
        lines.append(f"| {t['start']} to {t['end']} | {t['number']} | {_dollars(t['premium'])} | {_dollars(t['deductible'])} | {limits} | {t['document']} |")
    if not policy["terms"]:
        lines.append("| none found | | | | | |")
    sheet = policy["sheet"]
    lines += ["", "## The policy sheet", ""]
    if sheet:
        premiums = ", ".join(f"{y}: {_dollars(v)}" for y, v in sorted(sheet["premiums"].items()))
        lines.append(f"Number {sheet['number'] or '-'}, renewal {sheet['renewal'] or '-'}; premiums {premiums or '-'}.")
    else:
        lines.append("No row.")
    lines += ["", "## Findings", ""]
    lines += [f"- ({f['severity']}) {f['message']}" + (f" [{f['authority']}]" if f.get("authority") else "") for f in policy["findings"]] or ["- none"]
    lines += ["", "## Documents", ""]
    lines += [f"- {d['role']}: {d['name']} ({d['path']})" for d in policy["documents"]] or ["- none"]
    lines += ["", "The declarations and the policy forms govern; this page is Jason's reading of them."]
    return "\n".join(lines) + "\n"


def overview(policies: list[dict[str, Any]], built_at: str) -> str:
    """Every policy on one page: the coverage summary a member or lender asks for, with the findings."""
    lines = ["# Mystique insurance: every policy", "", f"Read {built_at[:10]} from the declarations, certificates, and the policy sheet.", "",
             "| Policy | Carrier | Number | Term in force ends | Latest declarations | Premium | Deductible | Limits |", "|---|---|---|---|---|---|---|---|"]
    for p in policies:
        t = p["terms"][-1] if p["terms"] else None
        name = p["kind"].replace("_", " ") + (f" {p['building']}" if p["building"] else "")
        limits = "; ".join(f"{k.replace('_', ' ')} {_dollars(v)}" for k, v in list((t or {}).get("limits", {}).items())[:3])
        lines.append(f"| {name} | {p['carrier'] or '-'} | {p['number'] or '-'} | {p['renewal'] or '-'} | "
                     f"{(t['start'] + ' to ' + t['end']) if t else 'none'} | {_dollars((t or {}).get('premium'))} | "
                     f"{_dollars((t or {}).get('deductible'))} | {limits} |")
    lines += ["", "## Findings", ""]
    for p in policies:
        for f in p["findings"]:
            if f["severity"] in ("problem", "check"):
                lines.append(f"- {p['key']}: ({f['severity']}) {f['message']}")
    return "\n".join(lines) + "\n"


def gather_copies(data_dir: Path, docs: list[dict[str, Any]]) -> int:
    """Copy the library's and email's policy papers beside Drive's in ``data/insurance/documents``, so the insurance
    catalog holds every policy paper in one folder (one copy per content)."""
    import shutil

    folder = Path(data_dir) / ROOT / "documents"
    have = {hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("*.pdf")}
    copied = 0
    for d in docs:
        if not d["id"].startswith(("library:", "email:")) or d["role"] == "claim" or not d.get("local"):
            continue
        src = Path(data_dir) / d["local"]
        if not src.is_file():
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if digest in have:
            continue
        safe = re.sub(r'[<>:"/\\|?*]+', "_", d["name"]).strip()
        dest = folder / f"{(d.get('modified') or '')[:10]} {safe}".strip()
        if dest.exists():
            dest = folder / f"{dest.stem} {digest[:6]}.pdf"
        shutil.copyfile(src, dest)
        have.add(digest)
        copied += 1
    return copied


def run(data_dir: Path, community: Any, *, sheet: list[SheetRow] | None = None, today: date | None = None) -> dict[str, Any]:
    """Read the fetched policy papers and write the report and the pages."""
    docs = read_documents(data_dir, community, today=today)
    gather_copies(data_dir, docs)
    sheet_path = Path(data_dir) / ROOT / "sheet.json"
    if sheet is not None:
        sheet_path.write_text(json.dumps([{**r.__dict__, "renewal": r.renewal.isoformat() if r.renewal else None} for r in sheet], indent=1),
                              encoding="utf-8")
    elif sheet_path.is_file():
        sheet = [SheetRow(r["kind"], r["building"], r["number"], r["link_id"], _day(r["renewal"]), {int(y): v for y, v in r["premiums"].items()})
                 for r in json.loads(sheet_path.read_text(encoding="utf-8"))]
    policies = build(community, sheet or [], docs, today=today)
    built = datetime.now().isoformat(timespec="seconds")
    pages = Path(data_dir) / ROOT / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    for p in policies:
        (pages / f"{p['key']}.md").write_text(page(p), encoding="utf-8")
    (pages / "overview.md").write_text(overview(policies, built), encoding="utf-8")
    report = {"found": True, "builtAt": built, "documents": len(docs), "policies": policies,
              "unread": [d["name"] for d in docs if not d["model"] and d["role"] not in ("claim", "invoice")]}
    (Path(data_dir) / "reports" / REPORT).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


def load(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / "reports" / REPORT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"found": False}


def lines(report: dict[str, Any], *, policy: str = "") -> list[str]:
    if not report.get("found"):
        return ["No policy report yet; run `jason policies --fetch`."]
    out = [f"Insurance policies: {len(report['policies'])} policies from {report['documents']} documents (read {report['builtAt'][:10]})."]
    for p in report["policies"]:
        if policy and policy not in p["key"]:
            continue
        t = p["terms"][-1] if p["terms"] else None
        out.append(f"\n{p['key']}: {p['carrier'] or '-'} {p['number'] or '-'} (term in force to {p['renewal'] or '-'}); latest declarations "
                   f"{(t['start'] + '..' + t['end']) if t else 'none'} premium {_dollars((t or {}).get('premium'))} "
                   f"deductible {_dollars((t or {}).get('deductible'))}")
        for f in p["findings"]:
            if f["severity"] in ("problem", "check") or policy:
                out.append(f"   ({f['severity']}) {f['message'][:220]}")
    return out


__all__ = ["SheetRow", "read_sheet", "policy_key", "sheet_row_for", "role_of", "find", "fetch", "library_documents", "read_documents",
           "build", "page", "overview", "run", "load", "lines"]
