"""The incident history: every repair document the association holds, read for events and placed on units and buildings.

Four channels, read from disk:

- PayHOA: each payment's attachments (the invoice review's text cache, OCR included), with the payment's day, amount,
  payee, category, memo, and the unit PayHOA tagged; a repair payment with no attachment is read by its own words;
- email: the attachments ``jason gmail --files`` saved, with each message's subject;
- the document library: its proposals, contracts, invoices, inspection reports, notices, and letters;
- Drive: the folders and loose files the specification's ``evidence_plan()`` names, fetched by ``fetch`` into
  ``data/drive/evidence`` (medical and veterinary records are never fetched).

A file held in several channels is read once (by content hash) and keeps its PayHOA payment. ``jason.community.incidents``
reads each document and groups the events. The report is ``data/reports/incidents.json``; nothing is sent, moved, or
changed anywhere. A confidential source's snippets are held back unless asked for.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from jason.community.incidents import (
    Evidence,
    Event,
    EvidencePlan,
    PlaceRole,
    Stage,
    ClaimStanding,
    Work,
    group_events,
    read_evidence,
)

REPORT = "incidents.json"
EVIDENCE_DIR = "evidence"
EVIDENCE_INDEX = "evidence.json"
TEXT_CACHE = "incident-text"
OCR_PAGES = 6

# Document kinds that are never repair paperwork, whatever words they carry (a policy lists every peril it covers).
NOT_EVIDENCE = frozenset({
    "insurance_policy", "evidence_of_insurance", "bank_statement", "tax_bill", "financial_statement", "treasurer_report",
    "minutes", "agenda", "budget", "reserve_study", "annual_disclosure", "grant_deed", "declaration", "bylaws", "articles",
    "amendment", "election_rules", "election_results", "ballot", "membership_list", "owner_statement", "owner_history",
    "delinquency_notice", "violation_notice", "recorded_lien", "tax_return", "financial_review", "resale_disclosure",
    "security_report", "audio", "image", "template", "map", "condominium_plan", "plan_set", "dre_report", "annexation",
    "operating_rules", "policy", "resolution", "utility_bill", "legal_brief", "legal_correspondence", "settlement",
    "committee_report", "form", "security_agreement", "subsidy_agreement", "bond_release", "surety_bond",
})
# A file whose name says it is about an event is read whatever its kind: the special resolution on the 2022 freshwater
# leak, the emergency meeting's minutes, a loss run. A policy, renewal, or declarations page is never an event.
EVENT_NAME = re.compile(r"^(?!.*(?:policy|renewal|declaration|dec page|RNL|FLD ))(?=.*(?:leak|emergency|damage|claim|loss run|repair|"
                        r"collision|mitigation|incident|intrusion|water test))", re.I)
LIBRARY_KINDS = ("proposal", "contract", "invoice", "inspection_report", "elevated_element_inspection", "notice")
# PayHOA categories whose payments are read even with nothing attached.
REPAIR_CATEGORY = re.compile(r"repair|improvement|insurance|claim|emergency|reserve", re.I)


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _private(name: str, plan: EvidencePlan | None) -> bool:
    return bool(plan) and any(fnmatch.fnmatchcase(name, g) for g in plan.private_names)


# -- Drive -----------------------------------------------------------------------------------------------------------


def evidence_dir(data_dir: Path) -> Path:
    from jason.tasks.drive_catalog import drive_dir

    return drive_dir(data_dir) / EVIDENCE_DIR


def select_drive(files: list[dict[str, Any]], plan: EvidencePlan) -> list[dict[str, Any]]:
    """The catalogued Drive files the plan names, each with its folder's facts; private names and oversize files left out."""
    chosen = []
    for f in files:
        path = str(f.get("path") or "")
        name = str(f.get("name") or "")
        mime = str(f.get("mimeType") or "")
        if not (mime.endswith("pdf") or mime == "application/vnd.google-apps.document"):
            continue
        if _private(name, plan) or int(f.get("size") or 0) > plan.max_bytes:
            continue
        rel = path.removeprefix("My Drive/")
        folder = next((d for d in plan.folders if rel.startswith(d.path + "/")), None)
        if folder is not None:
            inner = rel[len(folder.path) + 1:]
            if any(fnmatch.fnmatch(inner, g) for g in folder.skip):
                continue
            chosen.append({**f, "folder": folder.path, "confidential": folder.confidential})
        elif "/" not in rel and any(fnmatch.fnmatchcase(name, g) for g in plan.root_names):
            chosen.append({**f, "folder": "", "confidential": False})
    return chosen


def load_evidence_index(data_dir: Path) -> dict[str, Any]:
    path = evidence_dir(data_dir).parent / EVIDENCE_INDEX
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"files": {}}


def fetch(drive: Any, data_dir: Path, community: Any, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Download the plan's Drive files that are not on disk yet (or changed) into ``data/drive/evidence``."""
    from jason.tasks.drive_catalog import load_files

    plan = community.evidence_plan()
    if plan is None:
        return {"selected": 0}
    folder = evidence_dir(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    index = load_evidence_index(data_dir)
    rows = index.setdefault("files", {})
    counts = Counter()
    for f in select_drive(load_files(data_dir), plan):
        counts["selected"] += 1
        known = rows.get(f["id"])
        local = folder / f"{f['id']}.pdf"
        if known and local.is_file() and known.get("md5") == f.get("md5") and known.get("modified") == f.get("modified"):
            counts["kept"] += 1
            continue
        try:
            if f.get("mimeType") == "application/vnd.google-apps.document":
                drive.export_pdf(f["id"], local)
            else:
                drive.download(f["id"], local)
        except Exception as exc:  # a file that cannot be read now is tried again next time
            counts["failed"] += 1
            if log:
                log(f"  failed {f['path']}: {exc}")
            continue
        rows[f["id"]] = {"name": f["name"], "path": f["path"], "folder": f["folder"], "confidential": f["confidential"],
                         "modified": f.get("modified"), "md5": f.get("md5"), "size": f.get("size"),
                         "local": str(local.relative_to(data_dir)), "sha256": _sha_file(local)}
        counts["fetched"] += 1
        if log and counts["fetched"] % 25 == 0:
            log(f"  fetched {counts['fetched']}")
    index["fetchedAt"] = datetime.now().isoformat(timespec="seconds")
    (folder.parent / EVIDENCE_INDEX).write_text(json.dumps(index, indent=1), encoding="utf-8")
    return dict(counts)


# -- text ------------------------------------------------------------------------------------------------------------


def _ocr(path: Path, pages: int = OCR_PAGES) -> str:
    from jason.community.ocr import OllamaVisionOcr, PyMuPdfTesseract

    vision = OllamaVisionOcr(max_pages=pages)
    if vision.available():
        try:
            text = vision.text_of(path)
        except Exception:
            text = ""
        if text.strip():
            return text
    if not PyMuPdfTesseract.available():
        return ""
    import pymupdf

    tessdata = PyMuPdfTesseract.tessdata()
    out = []
    try:
        with pymupdf.open(path) as document:
            for i, page in enumerate(document):
                if i >= pages:
                    break
                textpage = page.get_textpage_ocr(dpi=200, language="eng", full=True, tessdata=tessdata)
                out.append(page.get_text(textpage=textpage))
    except Exception:
        return ""
    return "\n\n".join(out)


def file_text(data_dir: Path, path: Path, sha: str, *, ocr: bool = True) -> str:
    """A PDF's text layer, or its first pages' OCR when the layer is empty or glyph codes; cached by content hash."""
    from jason.community.invoices import readable
    from jason.tasks.utilities import pdf_text

    cache = Path(data_dir) / "documents" / TEXT_CACHE
    plain = cache / f"{sha}.txt"
    read = cache / f"{sha}.ocr.txt"
    if read.is_file():
        return read.read_text(encoding="utf-8")
    if plain.is_file():
        text = plain.read_text(encoding="utf-8")
    else:
        try:
            text = pdf_text(path) if path.suffix.lower() == ".pdf" else ""
        except Exception:
            text = ""
        cache.mkdir(parents=True, exist_ok=True)
        plain.write_text(text, encoding="utf-8")
    if ocr and (len(text.strip()) < 50 or not readable(text)) and path.suffix.lower() == ".pdf":
        text = _ocr(path)
        read.write_text(text, encoding="utf-8")
    return text


# -- the channels ----------------------------------------------------------------------------------------------------


def parcel_buildings(data_dir: Path, community: Any) -> dict[str, Any]:
    """Street address -> building, for every parcel in the stored tax roll whose assessor block is a building's block.
    The building table covers each street's run of numbers; an end unit addressed on the cross street is placed here."""
    from jason.community.reports import plan_block

    path = Path(data_dir) / "tax.db"
    if not path.is_file():
        return {}
    blocks = tuple(community.unit_blocks())
    out = {}
    with sqlite3.connect(path) as db:
        for apn, address in db.execute("select apn, address from accounts where address is not null"):
            block = plan_block(str(apn).replace("-", ""), blocks)
            street = str(address).split(" SACRAMENTO")[0].strip().upper()
            if block is not None and street[:1].isdigit():
                out[street] = block.building
    return out


def parcel_addresses(data_dir: Path) -> frozenset[str] | None:
    """Every street address in the stored tax roll; None when there is no roll (then every address is taken)."""
    path = Path(data_dir) / "tax.db"
    if not path.is_file():
        return None
    with sqlite3.connect(path) as db:
        rows = db.execute("select address from accounts where address is not null").fetchall()
    return frozenset(str(a).split(" SACRAMENTO")[0].strip().upper() for (a,) in rows if str(a)[:1].isdigit())


def _context(community: Any, data_dir: Path) -> dict[str, Any]:
    plan = community.evidence_plan()
    site = tuple(w for a in community.mail_addresses() if getattr(a.kind, "name", "") == "PROPERTY" for w in a.words)
    site += tuple(plan.site_words) if plan else ()
    senders = tuple(community.senders())
    kinds, names = {}, {}
    for s in senders:
        kinds[s.name.upper()] = s.kind.value
        names[s.name.upper()] = s.name
        if s.payhoa_vendor:
            kinds[s.payhoa_vendor.upper()] = s.kind.value
            names[s.payhoa_vendor.upper()] = s.name
    return {"community": community, "buildings": tuple(community.buildings()), "site_words": site, "senders": senders, "kinds": kinds, "names": names,
            "plan": plan, "known": parcel_buildings(data_dir, community), "parcels": parcel_addresses(data_dir)}


def _trade(vendor: str, ctx: dict[str, Any]) -> bool | None:
    from jason.community.incidents import TRADE_KINDS

    kind = ctx["kinds"].get((vendor or "").upper())
    return None if kind is None else kind in TRADE_KINDS


def _vendor(text: str, ctx: dict[str, Any], domains: list[str] | None = None) -> str:
    from jason.community.sources import resolve

    if domains:
        from jason.tasks.gmail import sender_of

        named = sender_of(domains, ctx["senders"])
        if named:
            return named.name
    named = resolve("", text[:3000], ctx["senders"])[0]
    return named.name if named else ""


def _kind(text: str) -> str:
    from jason.community.content import classify_text

    kind, _ = classify_text(text)
    return kind.value if kind else ""


def _units(data_dir: Path) -> dict[int, str]:
    """PayHOA unit id -> its street address."""
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return {}
    with sqlite3.connect(path) as db:
        return {int(i): str(a or "") for i, a in db.execute("select id, address_line1 from units")}


def payhoa_evidence(data_dir: Path, community: Any, roots: dict, ctx: dict[str, Any]) -> list[Evidence]:
    from jason.community.invoice_formats import INVOICE_FORMATS
    from jason.tasks.invoice_review import TEXT_CACHE as PAYHOA_TEXT, _payhoa_dir, payments, read_documents

    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return []
    snap = json.loads(path.read_text(encoding="utf-8"))
    documents = read_documents(data_dir, snap, roots, INVOICE_FORMATS)
    memos: dict[int, list[str]] = defaultdict(list)
    tagged: dict[int, set[int]] = defaultdict(set)
    for tx in snap["transactions"]:
        key = int(tx.get("parentId") or tx["id"])
        if tx.get("memo"):
            memos[key].append(str(tx["memo"]))
        if tx.get("unitId"):
            tagged[key].add(int(tx["unitId"]))
    units = _units(data_dir)
    cache = _payhoa_dir(data_dir) / PAYHOA_TEXT
    out = []
    for pay in payments(snap, documents):
        if pay.utility:
            continue
        categories = sorted({r["category"] for r in pay.rows if r["category"]})
        unit_addresses = [units[u] for u in tagged.get(pay.key, ()) if units.get(u)]
        extra = "; ".join(x for x in (", ".join(categories), pay.description, *memos.get(pay.key, ()),
                                      *(f"unit: {a}" for a in unit_addresses)) if x)
        payment = {"key": pay.key, "day": pay.day.isoformat(), "amountCents": pay.amount_cents, "payee": pay.payee,
                   "memo": "; ".join(memos.get(pay.key, ())), "categories": categories, "inflow": pay.inflow}
        docs = [d for d in pay.documents if d.path and not d.utility]
        read_any = False
        for doc in docs:
            if doc.kind in NOT_EVIDENCE and not EVENT_NAME.search(doc.filename):
                continue
            name = f"{doc.sha256}.{doc.ocr}.txt" if doc.ocr else f"{doc.sha256}.txt"
            text = (cache / name).read_text(encoding="utf-8") if (cache / name).is_file() else ""
            inv = doc.invoice
            ev = read_evidence(text, title=doc.filename, ref=str(Path(doc.path).relative_to(data_dir)) if doc.path else "",
                               channel="payhoa", day=(inv.invoice_date if inv and inv.invoice_date else pay.day),
                               buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"], parcels=ctx["parcels"],
                               vendor=pay.payee or (inv.vendor if inv else ""), amount_cents=(inv.total_cents if inv else None) or pay.amount_cents,
                               extra=extra, sha256=doc.sha256, payment=payment)
            if ev.stage is Stage.OTHER:
                ev.stage = Stage.INVOICE
            out.append(ev)
            read_any = True
        if not read_any and not pay.inflow and any(REPAIR_CATEGORY.search(c) for c in categories):
            ev = read_evidence("", title=pay.payee or pay.description, ref=f"payhoa payment {pay.key}", channel="payhoa",
                               day=pay.day, buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"], parcels=ctx["parcels"], vendor=pay.payee,
                               amount_cents=pay.amount_cents, extra=extra, payment=payment)
            ev.stage = Stage.INVOICE
            out.append(ev)
    return out


def email_evidence(data_dir: Path, ctx: dict[str, Any], *, ocr: bool = True) -> list[Evidence]:
    from jason.tasks.gmail import email_files

    out = []
    for f in email_files(data_dir):
        name = str(f.get("name") or "")
        path = Path(data_dir) / f["path"]
        if not name.lower().endswith(".pdf") or _private(name, ctx["plan"]) or not path.is_file():
            continue
        text = file_text(data_dir, path, f["sha256"], ocr=ocr)
        claims = loss_run_evidence(text, ref=f["path"], channel="email", sha256=f["sha256"], ctx=ctx) or             case_report_evidence(text, ref=f["path"], channel="email", ctx=ctx)
        if claims:
            out.extend(claims)
            continue
        if _kind(text) in NOT_EVIDENCE and not EVENT_NAME.search(name):
            continue
        subject = str(f.get("subject") or "")
        out.append(enrich_claim(read_evidence(text, title=name, ref=f["path"], channel="email", day=_day(f.get("at")),
                                 buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"], parcels=ctx["parcels"],
                                 vendor=_vendor(text, ctx, f.get("domains")), amount_cents=_amount(text),
                                 extra=f"subject: {subject}", sha256=f["sha256"]), text, ctx))
    return out


def library_evidence(data_dir: Path, ctx: dict[str, Any]) -> list[Evidence]:
    path = Path(data_dir) / "library" / "library.db"
    if not path.is_file():
        return []
    out = []
    with sqlite3.connect(path) as db:
        marks = ",".join("?" * len(LIBRARY_KINDS))
        rows = db.execute(f"select id, path, name, kind, period, confidential, sha256 from documents where kind in ({marks})", LIBRARY_KINDS).fetchall()
    for ident, rel, name, kind, period, confidential, sha in rows:
        text_path = Path(data_dir) / "library" / "text" / f"{ident}.txt"
        text = text_path.read_text(encoding="utf-8", errors="replace") if text_path.is_file() else ""
        out.append(read_evidence(text, title=name, ref=f"library/{rel}", channel="library", day=_first_date(text) or _day(period),
                                 buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"], parcels=ctx["parcels"], vendor=_vendor(text, ctx),
                                 amount_cents=_amount(text), sha256=sha or "", confidential=bool(confidential)))
    return out


def loss_run_evidence(text: str, *, ref: str, channel: str, sha256: str, ctx: dict[str, Any]) -> list[Evidence]:
    """A carrier's loss run as one piece of claim evidence per claim it details: the claim number, the date of loss, the
    cause, the location, the carrier's status, and what it paid. Each row keeps the file's hash with its claim number, so
    the copies of one loss run are one set of rows."""
    from jason.community.incidents import loss_run_text, read_loss_run

    out = []
    for claim in read_loss_run(text):
        ev = read_evidence(loss_run_text(claim), title=f"Loss run: claim {claim.number} ({claim.carrier})", ref=ref, channel=channel,
                           day=claim.date_of_loss, buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"],
                           parcels=ctx["parcels"], vendor=claim.carrier, amount_cents=claim.paid_cents,
                           sha256=f"{sha256}:{claim.number}", confidential=True)
        ev.stage, ev.claimed, ev.claim = Stage.CLAIM, True, claim.number
        ev.claim_status, ev.claim_paid_cents = claim.status, claim.paid_cents
        ev.snippet = f"{claim.carrier} policy {claim.policy}: {claim.claim_type}, {claim.cause}, {claim.status}"
        out.append(ev)
    return out


def case_report_evidence(text: str, *, ref: str, channel: str, ctx: dict[str, Any]) -> list[Evidence]:
    """A manager's case report as one piece of evidence per open case about the property (work, a claim, a unit's
    problem), keyed by the case number so each case is one row however many weekly reports carry it."""
    from jason.community.models.manager_reports import is_work_case, open_cases

    if not re.search(r"Cases Currently Open", text or "", re.I):
        return []
    from jason.community.models.manager_reports import _as_of

    day = _as_of(text)
    manager = "The Helsing Group" if re.search(r"helsing", text or "", re.I) else "manager"
    out = []
    for case in open_cases(text):
        if not is_work_case(case):
            continue
        ev = read_evidence(case.subject, title=f"Case {case.number}: {case.subject}", ref=ref, channel=channel, day=day,
                           buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"], parcels=ctx["parcels"],
                           vendor=manager, sha256=f"case:{case.number}", confidential=True)
        if ev.stage is Stage.OTHER:
            ev.stage = Stage.REPORT
        out.append(ev)
    return out


# Most particular first: an estimate and a work authorization also print a claim number, which is all a letter needs.
CLAIM_KINDS = ("claim_estimate", "claim_payment", "claim_authorization", "police_report", "claim_letter")


def enrich_claim(ev: Evidence, text: str, ctx: dict[str, Any]) -> Evidence:
    """A claim paper read by its document model: its claim number, the date of loss (a letter dated months after the loss
    joins the loss's event by it), the letter's outcome, and what the carrier paid."""
    if not (ev.claimed or ev.stage is Stage.CLAIM):
        return ev
    from jason.community.document_models import ModelContext, read
    from jason.community.symbols import DocumentKind

    context = ModelContext(community=ctx.get("community"), name=ev.title)
    for value in CLAIM_KINDS:
        reading = read(DocumentKind(value), text, context)
        if reading is None:
            continue
        r = reading.record
        number = getattr(r, "claim_number", "") or ""
        if number:
            ev.claim = number
        loss = getattr(r, "loss_date", None) or getattr(r, "date_of_loss", None) or getattr(r, "occurred", None)
        if loss and (ev.day is None or timedelta(0) <= ev.day - loss <= timedelta(days=400)):
            ev.day = loss
        kind = getattr(r, "letter_type", None) or getattr(r, "form", None)
        if kind is not None:
            ev.claim_status = kind.value
        paid = getattr(r, "paid_cents", None) or getattr(r, "amount_cents", None)
        if paid and value in ("claim_letter", "claim_payment"):
            ev.claim_paid_cents = paid
        ev.stage, ev.claimed = Stage.CLAIM, True
        break
    return ev


def drive_evidence(data_dir: Path, ctx: dict[str, Any], *, ocr: bool = True) -> list[Evidence]:
    index = load_evidence_index(data_dir).get("files", {})
    out = []
    for ident, row in index.items():
        path = Path(data_dir) / row["local"]
        if not path.is_file() or _private(row["name"], ctx["plan"]):
            continue
        text = file_text(data_dir, path, row["sha256"], ocr=ocr)
        claims = loss_run_evidence(text, ref=f"drive:{row['path']}", channel="drive", sha256=row["sha256"], ctx=ctx) or             case_report_evidence(text, ref=f"drive:{row['path']}", channel="drive", ctx=ctx)
        if claims:
            out.extend(claims)
            continue
        if _kind(text) in NOT_EVIDENCE and not EVENT_NAME.search(row["name"]):
            continue
        day = _name_date(row["name"]) or _first_date(text) or _day(row.get("modified"))
        out.append(enrich_claim(read_evidence(text, title=row["name"], ref=f"drive:{row['path']}", channel="drive", day=day,
                                 buildings=ctx["buildings"], site_words=ctx["site_words"], known=ctx["known"], parcels=ctx["parcels"], vendor=_vendor(text, ctx),
                                 amount_cents=_amount(text) or _amount(row["name"]), extra=f"folder: {row['folder']}",
                                 sha256=row["sha256"], confidential=bool(row.get("confidential"))), text, ctx))
    return out


_TOTAL = re.compile(r"(?:grand total|total (?:due|price|amount|estimate|cost)|estimate total|contract (?:price|amount)|amount due|"
                    r"balance due|subtotal|\btotal|totaling|sum of)\s*:?\s*\$?\s*([\d,]+\.\d\d|[\d,]{3,})", re.I)


def _amount(text: str) -> int | None:
    """The largest labeled total in the text, in cents."""
    found = []
    for m in _TOTAL.finditer(text or ""):
        raw = m.group(1).replace(",", "")
        try:
            cents = round(float(raw) * 100)
        except ValueError:
            continue
        if 0 < cents < 50_000_000:
            found.append(cents)
    return max(found) if found else None


def _first_date(text: str) -> date | None:
    from jason.community.document_models import dates_in

    days = [d for d in dates_in((text or "")[:1500]) if date(2000, 1, 1) <= d <= date.today()]
    return days[0] if days else None


_YYYYMMDD = re.compile(r"(?:^|[ _-])(20\d\d)(0[1-9]|1[0-2])([0-3]\d)(?=[ _.)(-])")
_YYMMDD = re.compile(r"(?:^|[ _-])(2[0-9])(0[1-9]|1[0-2])([0-3]\d)(?=[ _.-])")
_ISO = re.compile(r"(20\d\d)[-_.](0[1-9]|1[0-2])[-_.]([0-3]\d)")
_MDY = re.compile(r"\((\d{1,2})\.(\d{1,2})\.(\d{2})\)")


def _name_date(name: str) -> date | None:
    """A date the file's name carries: "Mystique - 230222 - ...", "2026-01-12", "(9.4.26)"."""
    for pattern, order in ((_ISO, "ymd"), (_YYYYMMDD, "ymd"), (_YYMMDD, "yymmdd"), (_MDY, "mdy")):
        m = pattern.search(name or "")
        if not m:
            continue
        try:
            if order == "ymd":
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if order == "yymmdd":
                return date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return date(2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
    return None


# -- the run ---------------------------------------------------------------------------------------------------------


def dedupe(evidence: list[Evidence]) -> list[Evidence]:
    """One row per file content: the PayHOA copy first (it carries the payment), then the others as ``also``."""
    order = {"payhoa": 0, "drive": 1, "library": 2, "email": 3}
    by_sha: dict[str, list[Evidence]] = defaultdict(list)
    loose = []
    for ev in evidence:
        (by_sha[ev.sha256].append(ev) if ev.sha256 else loose.append(ev))
    out = loose
    for rows in by_sha.values():
        rows.sort(key=lambda e: (order.get(e.channel, 9), e.day or date.max))
        head = rows[0]
        head.also = tuple(dict.fromkeys(r.ref for r in rows[1:] if r.ref != head.ref))
        head.confidential = any(r.confidential for r in rows)
        # A copy dated by its email or payment is later than the document; keep the earliest date any copy gives.
        days = [r.day for r in rows if r.day]
        head.day = min(days) if days and head.channel != "payhoa" else head.day
        out.append(head)
    return out


def collect(data_dir: Path, community: Any, roots: dict, *, ocr: bool = True, log: Callable[[str], None] | None = None) -> list[Evidence]:
    ctx = _context(community, data_dir)
    evidence: list[Evidence] = []
    for name, reader in (("payhoa", lambda: payhoa_evidence(data_dir, community, roots, ctx)),
                         ("email", lambda: email_evidence(data_dir, ctx, ocr=ocr)),
                         ("library", lambda: library_evidence(data_dir, ctx)),
                         ("drive", lambda: drive_evidence(data_dir, ctx, ocr=ocr))):
        rows = reader()
        if log:
            log(f"  {name}: {len(rows)} documents")
        evidence.extend(rows)
    from jason.community.incidents import apply_vendor_work, is_repair_paperwork

    kept = [e for e in dedupe(evidence) if is_repair_paperwork(e, trade=_trade(e.vendor, ctx))]
    plan = ctx["plan"]
    if plan is not None and plan.vendor_work:
        apply_vendor_work(kept, plan.vendor_work, ctx["names"])
    if log:
        log(f"  {len(kept)} documents are repair paperwork")
    return kept


def _place_row(p: Any) -> dict[str, Any]:
    return {"address": p.address, "building": int(p.building) if p.building else None, "role": p.role.value, "unit": p.unit_label}


def evidence_row(ev: Evidence, *, private: bool = False) -> dict[str, Any]:
    held = ev.confidential and not private
    return {"day": ev.day.isoformat() if ev.day else None, "channel": ev.channel, "ref": ev.ref, "title": ev.title,
            "stage": ev.stage.value, "work": ev.work.value, "claimed": ev.claimed, "vendor": ev.vendor,
            "amountCents": ev.amount_cents, "causes": [c.value for c in ev.causes], "elements": [e.value for e in ev.elements],
            "places": [_place_row(p) for p in ev.where], "snippet": "" if held else ev.snippet, "claim": ev.claim,
            "payment": ev.payment, "confidential": ev.confidential, "also": list(ev.also), "hint": ev.hint,
            "claimStatus": ev.claim_status, "claimPaidCents": ev.claim_paid_cents}


def event_row(event: Event, *, private: bool = False, deductible: int | None = None) -> dict[str, Any]:
    return {"first": event.first.isoformat() if event.first else None, "last": event.last.isoformat() if event.last else None,
            "work": [w.value for w in event.works if w is not Work.NONE], "claimed": event.claimed, "sudden": event.sudden,
            "routine": event.routine, "costCents": event.cost_cents, "standing": event.standing(deductible).value, "causes": [c.value for c in event.causes], "elements": [e.value for e in event.elements],
            "addresses": list(event.addresses), "buildings": [int(b) for b in event.buildings], "communityWide": event.community_wide,
            "vendors": list(event.vendors), "estimatedCents": event.estimated_cents, "invoicedCents": event.invoiced_cents,
            "paidCents": event.paid_cents, "claims": list(event.claims), "claimOutcomes": event.claim_outcomes,
            "documents": [evidence_row(e, private=private) for e in sorted(event.evidence, key=lambda e: (e.day or date.min, e.ref))]}


def _tally(event: Event, deductible: int | None) -> list[str]:
    """What one event adds to a building's or unit's history: each kind of work, and where it stands against the deductible."""
    marks = [w.value for w in event.works if w is not Work.NONE]
    standing = event.standing(deductible)
    if standing is not ClaimStanding.NONE:
        marks.append(standing.value)
    return marks


def master_deductible(community: Any) -> int | None:
    """The master policy's deductible, integer cents, from the specification's insurance catalog."""
    try:
        master = community.insurance().master()
    except Exception:
        return None
    return getattr(master, "deductible_cents", None) if master else None


def history(evidence: list[Evidence], deductible: int | None = None) -> dict[str, Any]:
    """The events, and each building's and unit's maintenance history and claims."""
    events = group_events(evidence)
    by_building: dict[str, Counter] = defaultdict(Counter)
    by_unit: dict[str, Counter] = defaultdict(Counter)
    for e in events:
        marks = _tally(e, deductible)
        for b in e.buildings or ((None,) if e.community_wide else ()):
            key = "community" if b is None else f"building {int(b)}"
            by_building[key]["events"] += 1
            by_building[key].update(marks)
        for a in e.addresses:
            by_unit[a]["events"] += 1
            by_unit[a].update(marks)
    return {"events": events, "byBuilding": by_building, "byUnit": by_unit}


def run(data_dir: Path, community: Any, roots: dict, *, ocr: bool = True, private: bool = False,
        log: Callable[[str], None] | None = None) -> dict[str, Any]:
    evidence = collect(data_dir, community, roots, ocr=ocr, log=log)
    deductible = master_deductible(community)
    result = history(evidence, deductible)
    events: list[Event] = result["events"]
    counts = Counter(w.value for e in events for w in e.works if w is not Work.NONE)
    counts.update(Counter(e.standing(deductible).value for e in events if e.standing(deductible) is not ClaimStanding.NONE))
    counts["routine"] = sum(e.routine for e in events)
    report = {
        "found": True,
        "builtAt": datetime.now().isoformat(timespec="seconds"),
        "documents": len(evidence),
        "byChannel": dict(Counter(e.channel for e in evidence)),
        "deductibleCents": deductible, "events": [event_row(e, private=private, deductible=deductible) for e in events],
        "counts": dict(counts),
        "byBuilding": {k: dict(v) for k, v in sorted(result["byBuilding"].items())},
        "byUnit": {a: dict(v) for a, v in sorted(result["byUnit"].items(), key=lambda kv: (-kv[1]["events"], kv[0]))},
        "caveats": [
            "An event is read from the paperwork's own words by rule rows; a person confirms it before it is cited.",
            "Claimed means the paperwork ties the event to an insurance claim; whether the peril was covered is the insurer's answer.",
            "A claim candidate names a sudden cause (a leak, a break, a collision), has no claim on file, and its cost on the paperwork "
            "reaches the master policy's deductible; under the deductible the carrier pays nothing. The cost is the paperwork's, "
            "not the loss's: interior damage an owner paid may not be in it.",
            "A unit is the street address the document names; an address labeled bill-to is the payer's, not the job's.",
            "Confidential sources (claims, losses) keep their facts; their snippets are held back unless asked for.",
            "Payments before January 2024 are not in the stored ledger, so older work shows its paperwork only.",
        ],
    }
    out = Path(data_dir) / "reports" / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    stored = {**report, "events": [event_row(e, private=False, deductible=deductible) for e in events]}
    out.write_text(json.dumps(stored, indent=1, default=str), encoding="utf-8")
    return report


def load(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / "reports" / REPORT
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"found": False}


def select(report: dict[str, Any], *, building: int | None = None, address: str = "", work: str = "", claims: bool = False,
           standing: str = "",
           cause: str = "", since: str = "", routine: bool = True) -> list[dict[str, Any]]:
    """The stored events a person asked for. ``claims`` keeps the claimed events; ``routine=False`` drops upkeep and
    inspections that carry no claim and no sudden cause."""
    rows = report.get("events") or []
    words = address.upper().replace("LANE", "LN").replace("DRIVE", "DR").split()
    out = []
    for r in rows:
        if building is not None and building not in r["buildings"]:
            continue
        if words and not any(all(w in a for w in words) for a in r["addresses"]):
            continue
        if work and work not in r["work"]:
            continue
        if claims and not r["claimed"]:
            continue
        if standing and r.get("standing") != standing:
            continue
        if cause and not any(cause.lower() in c for c in r["causes"]):
            continue
        if since and (r["last"] or "") < since:
            continue
        if not routine and r["routine"]:
            continue
        out.append(r)
    return out


def _money(cents: int | None) -> str:
    return f"${cents / 100:,.0f}" if cents else "-"


def lines(report: dict[str, Any], rows: list[dict[str, Any]] | None = None, *, limit: int = 60) -> list[str]:
    if not report.get("found"):
        return ["No history yet; run `jason incidents` (and `--fetch` for the Drive paperwork)."]
    rows = rows if rows is not None else select(report, routine=False)
    out = [f"Maintenance and claims history: {report['documents']} repair documents ({report['byChannel']}) in "
           f"{len(report['events'])} events {report['counts']}."]
    out.append("By building: " + "; ".join(f"{k}: {v}" for k, v in report.get("byBuilding", {}).items()))
    top = list(report.get("byUnit", {}).items())[:12]
    if top:
        out.append("Units with the most: " + ", ".join(f"{a} ({v['events']})" for a, v in top))
    out.append("")
    for r in rows[-limit:]:
        where = ", ".join(r["addresses"]) or ", ".join(f"building {b}" for b in r["buildings"]) or "community"
        money = " ".join(x for x in (f"est {_money(r['estimatedCents'])}" if r["estimatedCents"] else "",
                                     f"paid {_money(r['paidCents'])}" if r["paidCents"] else "",
                                     f"cost {_money(r['costCents'])}" if r.get("costCents") and r.get("standing") not in (None, "none") else "") if x)
        span = r["first"] if r["first"] == r["last"] else f"{r['first']}..{r['last']}"
        mark = {"claimed": "CLAIM", "claim candidate": "CANDIDATE", "under deductible": "under-ded", "sudden, cost unknown": "sudden?"}.get(
            r.get("standing", ""), "")
        out.append(f"{span}  {'+'.join(r['work']) or '-':<18} {mark:<9} {where} | {', '.join(r['causes'][:2]) or '-'} | {', '.join(r['elements'][:3]) or '-'} "
                   f"| {', '.join(r['vendors'][:2]) or '-'} | {len(r['documents'])} docs {money}"
                   + (f" | claim {', '.join(r['claims'])}" if r["claims"] else "")
                   + "".join(f" | {n}: {o['status']}" + (f" {_money(o['paidCents'])}" if o.get("paidCents") else "") for n, o in (r.get("claimOutcomes") or {}).items()))
    for c in report.get("caveats", []):
        out.append(f"  note: {c}")
    return out


__all__ = ["fetch", "select_drive", "collect", "history", "run", "load", "select", "lines", "file_text", "dedupe",
           "payhoa_evidence", "email_evidence", "library_evidence", "drive_evidence", "evidence_row", "event_row"]
