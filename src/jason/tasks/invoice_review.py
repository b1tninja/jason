"""Every PayHOA payment against the documents attached to it: right amount, right vendor, right category.

``fetch`` reads all transactions, the category tree, and the vendor directory from PayHOA,
and downloads any attachment not already on disk (the monthly export under
``data/transactions/<year>/<month>/invoices``, the utility portals' files, and
``data/payhoa/attachments`` are all reused). It changes nothing in PayHOA.

``review`` reads each attached PDF: a SMUD or City bill is left to the utility audit; any
other document is read as an invoice (``jason.community.invoices``) and classified. Each
expense payment is then checked:

- an expense with nothing attached;
- no attachment prints the payment's amount (the wrong file, a partial payment, or a total
  that includes a credit);
- the attachment names another vendor from the directory, and not the payee;
- the same file, or the same vendor's invoice number, is attached to another payment
  (a misattachment, or the same invoice paid twice when the amounts agree);
- the invoice is dated after the payment, or more than a year before it;
- the payment's category is not the one this vendor's other payments carry.

The per-vendor scorecard shows how well the general reader handles each vendor's layout:
a vendor whose invoices rarely yield a number, a date, or the payment's amount is the next
``InvoiceFormat`` to write. Findings are for the treasurer; jason changes nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.content import classify_text
from jason.community.invoices import Invoice, InvoiceFormat, names_vendor, read_invoice, readable
from jason.community.utility_payments import identify, provider_of
from jason.tasks.utilities import bill_files, pdf_text
from jason.tasks.utility_payments import attachment_path

TRANSACTIONS = "transactions.json"
REVIEW = "invoice-review.json"
TEXT_CACHE = "attachment-text"
# Categories whose payments move money between the association's own accounts or carry no vendor document.
NO_DOCUMENT = ("transfer", "reserves", "bank fee", "service charge", "interest", "owner refund", "refund")
# Bank descriptions of money moving between the association's own accounts, or coming back.
NO_DOCUMENT_DESCRIPTIONS = ("online transfer to", "online transfer from", "credit return", "monthly service fee",
                            "service charges for the month")
RETURNED = re.compile(r"Credit Return:\s*Online Payment\s+(\d+)", re.I)


def _payhoa_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "payhoa"


def _flatten(rows: list[dict[str, Any]], parent: str = "") -> dict[int, dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    for row in rows:
        if row.get("id") is not None:
            found[int(row["id"])] = {"name": str(row.get("name") or row.get("label") or ""), "type": str(row.get("type") or ""),
                                     "parent": parent}
        found.update(_flatten(row.get("children") or [], str(row.get("name") or "")))
    return found


def local_attachment(data_dir: Path, tx: dict[str, Any], raw: dict[str, Any], portal: dict[str, Path]) -> Path:
    """Where an attachment is on disk, or where it goes: the portal's own bill, the monthly export, or data/payhoa/attachments."""
    name = str(raw.get("filename") or "")
    if name in portal:
        return portal[name]
    day = str(tx.get("transactionDate") or "")[:10]
    if len(day) == 10:
        exported = Path(data_dir) / "transactions" / day[:4] / day[5:7] / "invoices" / f"{tx['id']}-{name}"
        if exported.is_file():
            return exported
    return attachment_path(data_dir, int(tx["id"]), int(raw["id"]), name)


def fetch(client: Any, org_id: int, data_dir: Path, roots: dict, *, log: Callable[[str], None] | None = None) -> dict[str, int]:
    """Read every transaction, category, and vendor; download the attachments not on disk. Read-only in PayHOA."""
    transactions = list(client.iter_transactions(org_id, per_page=1000))
    categories = _flatten(client.list_categories(org_id))
    vendors = {int(v["id"]): str(v.get("name") or v.get("displayName") or "") for v in client.list_vendors(org_id) if v.get("id") is not None}
    portal = {pdf.name: pdf for _u, _a, pdf in bill_files(roots)}
    downloaded = present = failed = 0
    for tx in transactions:
        for raw in tx.get("attachments") or []:
            dest = local_attachment(data_dir, tx, raw, portal)
            if dest.is_file():
                present += 1
                continue
            url = raw.get("url")
            if not url:
                detail = client.get_transaction(org_id, int(tx["id"]))
                url = next((a.get("url") for a in detail.get("attachments") or [] if int(a.get("id") or 0) == int(raw["id"])), None)
            if not url:
                failed += 1
                continue
            try:
                client.download_signed_url(url, dest)
            except Exception as exc:  # one missing file is reported, not fatal
                failed += 1
                if log:
                    log(f"attachment {raw['id']} on transaction {tx['id']}: {exc}")
                continue
            downloaded += 1
            if log and downloaded % 50 == 0:
                log(f"downloaded {downloaded} attachments")
    for tx in transactions:
        for raw in tx.get("attachments") or []:
            raw.pop("url", None)
    out = _payhoa_dir(data_dir) / TRANSACTIONS
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "categories": {str(k): v for k, v in sorted(categories.items())},
        "vendors": {str(k): v for k, v in sorted(vendors.items())},
        "transactions": transactions,
    }, indent=1, default=str), encoding="utf-8")
    return {"transactions": len(transactions), "downloaded": downloaded, "present": present, "failed": failed}


@dataclass
class Document:
    attachment_id: int
    filename: str
    path: str
    sha256: str = ""
    text_chars: int = 0
    kind: str = ""
    utility: str = ""
    invoice: Invoice | None = None
    # The OCR engine that read a scan or a glyph-coded text layer; empty when the PDF's own text was read.
    ocr: str = ""


def _ocr_engine() -> Any:
    """The first OCR engine that can run here (a vision model, Docling, Tesseract), or None."""
    from jason.community.ocr import engines

    return next(iter(engines()), None)


def _ocr_text(data_dir: Path, path: Path, digest: str, engine: Any) -> str:
    """OCR text for a file, cached beside the text layer by content hash and engine."""
    cache = _payhoa_dir(data_dir) / TEXT_CACHE / f"{digest}.{engine.name}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    try:
        text = engine.text_of(path)
    except Exception:  # an image the engine cannot open stays unread
        text = ""
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


@dataclass
class Payment:
    key: int
    day: date
    amount_cents: int
    payee: str
    description: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    utility: bool = False
    # Money in: PayHOA's ``originalAmount`` is negative for a deposit (a refund or credit booked against a category).
    inflow: bool = False


# The OCR engines whose cached text is read first when a text layer is unreadable: the vision model reads a
# glyph-coded page cleanly where Tesseract garbles it.
OCR_PREFERENCE = ("ollama-vision", "pymupdf-tesseract", "docling-rapidocr")


def best_text(data_dir: Path, path: Path) -> str:
    """The best text on file for an attachment: its text layer when it reads as characters, else the OCR text the
    invoice review cached for the same file (by content hash), the vision model's first, else the one the document
    readers (``jason incidents``, ``jason policies``) cached. A PDF whose font carries no character map (Philadelphia's
    2024 flood renewal notices) draws the right letters and extracts as glyph codes, so its OCR text is the one to parse.
    Reads the caches only; OCR runs in those reviews. "" when nothing reads."""
    if not path.is_file():
        return ""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    cache = _payhoa_dir(data_dir) / TEXT_CACHE
    layer = cache / f"{digest}.txt"
    text = layer.read_text(encoding="utf-8") if layer.is_file() else ""
    if not text and not layer.is_file():
        try:
            text = pdf_text(path) if path.suffix.lower() == ".pdf" else ""
        except Exception:
            text = ""
    if text.strip() and readable(text):
        return text
    from jason.tasks.incidents import TEXT_CACHE as DOCUMENT_CACHE

    documents = Path(data_dir) / "documents" / DOCUMENT_CACHE / f"{digest}.ocr.txt"
    for cached in (*(cache / f"{digest}.{engine}.txt" for engine in OCR_PREFERENCE), documents):
        if cached.is_file():
            read = cached.read_text(encoding="utf-8")
            if read.strip() and readable(read):
                return read
    return ""


def _text(data_dir: Path, path: Path, digest: str) -> str:
    cache = _payhoa_dir(data_dir) / TEXT_CACHE / f"{digest}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    try:
        text = pdf_text(path) if path.suffix.lower() == ".pdf" else ""
    except RuntimeError:
        raise
    except Exception:  # a damaged file reads as no text
        text = ""
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(text, encoding="utf-8")
    return text


def _name_pattern(community: Any) -> str:
    """The association's name word as letters print it (``Community.name_pattern()``); none without a specification."""
    return str(getattr(community, "name_pattern", str)() or "")


def read_documents(data_dir: Path, snap: dict[str, Any], roots: dict, formats: tuple[InvoiceFormat, ...],
                   name_pattern: str = "") -> dict[int, Document]:
    """Each attachment read once: its content hash, its kind, and the invoice or utility bill it holds.
    ``name_pattern`` is the association's name word (``Community.name_pattern()``), for a layout that prints it."""
    portal = {pdf.name: pdf for _u, _a, pdf in bill_files(roots)}
    vendor_names = tuple(v for v in snap["vendors"].values() if v)
    engine = _ocr_engine()
    found: dict[int, Document] = {}
    for tx in snap["transactions"]:
        for raw in tx.get("attachments") or []:
            ident = int(raw["id"])
            if ident in found:
                continue
            path = local_attachment(data_dir, tx, raw, portal)
            doc = Document(ident, str(raw.get("filename") or ""), str(path) if path.is_file() else "")
            if path.is_file():
                data = path.read_bytes()
                doc.sha256 = hashlib.sha256(data).hexdigest()
                text = _text(data_dir, path, doc.sha256)
                doc.text_chars = len(text.strip())
                who = identify(text) if text else None
                scanned = not who and (doc.text_chars < 50 or not readable(text))
                if scanned and engine is not None and path.suffix.lower() == ".pdf":
                    read = _ocr_text(data_dir, path, doc.sha256, engine)
                    if len(read.strip()) >= 50 and readable(read):
                        text, doc.ocr = read, engine.name
                        doc.text_chars = len(text.strip())
                        who = identify(text)
                if who:
                    doc.kind, doc.utility = "utility_bill", who[0].value
                elif doc.text_chars < 50:
                    doc.kind = "scan without a text layer" if path.suffix.lower() == ".pdf" else f"{path.suffix or 'unknown'} file"
                elif not readable(text):
                    doc.kind = "unreadable text layer"
                else:
                    kind, _why = classify_text(text)
                    doc.kind = kind.value if kind else "unclassified"
                    doc.invoice = read_invoice(text, vendors=vendor_names, formats=formats, name_pattern=name_pattern)
            found[ident] = doc
    return found


def payments(snap: dict[str, Any], documents: dict[int, Document]) -> list[Payment]:
    """Transactions as payments: a standalone row, or the split rows that share one parent. Oldest first."""
    vendors = {int(k): v for k, v in snap["vendors"].items()}
    categories = {int(k): v for k, v in snap["categories"].items()}
    found: dict[int, Payment] = {}
    for tx in snap["transactions"]:
        if tx.get("deletedAt"):
            continue
        key = int(tx.get("parentId") or tx["id"])
        day = date.fromisoformat(str(tx["transactionDate"])[:10])
        payee = vendors.get(int(tx.get("vendorId") or 0)) or str((tx.get("transactionRule") or {}).get("name") or "")
        pay = found.get(key)
        if pay is None:
            pay = found[key] = Payment(key, day, 0, payee, str(tx.get("description") or ""),
                                       inflow=float(tx.get("originalAmount") or tx.get("amount") or 0) < 0)
        pay.amount_cents += int(tx.get("amount") or 0)
        pay.payee = pay.payee or payee
        pay.utility = pay.utility or provider_of(tx) is not None
        category = categories.get(int(tx.get("categoryId") or 0), {})
        pay.rows.append({"txId": int(tx["id"]), "amountCents": int(tx.get("amount") or 0), "category": category.get("name", ""),
                         "categoryType": category.get("type", ""), "parentCategory": category.get("parent", ""),
                         "bank": tx.get("bankAccountId"), "excluded": bool(tx.get("excluded"))})
        seen = {d.attachment_id for d in pay.documents}
        for raw in tx.get("attachments") or []:
            doc = documents.get(int(raw["id"]))
            if doc is not None and doc.attachment_id not in seen:
                pay.documents.append(doc)
                seen.add(doc.attachment_id)
    return sorted(found.values(), key=lambda p: (p.day, p.key))


@dataclass
class LedgerPayment:
    """A payment as the vendor recorded it in its customer portal: the day, the amount, and the invoices it paid."""

    vendor: str
    day: date
    amount_cents: int
    invoice_ids: tuple[str, ...]
    invoice_files: tuple[str, ...] = ()
    used: bool = False


def vendor_ledgers(data_dir: Path, community: Any) -> dict[str, tuple[Any, list[LedgerPayment]]]:
    """Each vendor portal's recorded payments, from ``data/vendors/<key>/<customer>/account.json`` (``jason vendor-portals``)."""
    found: dict[str, tuple[Any, list[LedgerPayment]]] = {}
    for portal in community.vendor_portals():
        rows: list[LedgerPayment] = []
        for account in sorted((Path(data_dir) / "vendors" / portal.key).glob("*/account.json")):
            data = json.loads(account.read_text(encoding="utf-8"))
            for tx in data.get("transactions") or []:
                if tx.get("kind") != "payment" or not tx.get("payment_cents"):
                    continue
                ids = tuple(str(i) for i in tx.get("invoice_ids") or [])
                files = tuple(str(account.parent / "invoices" / f"{i}.pdf") for i in ids if (account.parent / "invoices" / f"{i}.pdf").is_file())
                rows.append(LedgerPayment(portal.vendor, date.fromisoformat(str(tx["day"])[:10]), int(tx["payment_cents"]), ids, files))
        if rows:
            found[portal.key] = (portal, sorted(rows, key=lambda r: r.day))
    return found


def _portal_of(pay: Payment, ledgers: dict[str, tuple[Any, list[LedgerPayment]]]) -> tuple[Any, list[LedgerPayment]] | None:
    text = pay.description.upper()
    for _key, (portal, rows) in ledgers.items():
        if any(word.upper() in text for word in portal.payhoa_words) or _fold_name(portal.vendor) == _fold_name(pay.payee):
            return portal, rows
    return None


def match_ledgers(pays: list[Payment], ledgers: dict[str, tuple[Any, list[LedgerPayment]]]) -> dict[int, tuple[Any, LedgerPayment | None]]:
    """Each vendor-portal payment's own record in the vendor's ledger, in two passes.

    First an autopay the vendor draws: the same amount recorded up to four days before the bank posts it. Then,
    for what is left, a mailed check the vendor deposits later: up to three weeks after. Among several, the one
    that paid the attached invoice wins, then the nearest. A payment whose vendor ledger covers its date but holds
    no such payment maps to (portal, None).
    """
    found: dict[int, tuple[Any, LedgerPayment | None]] = {}
    ordered = sorted(pays, key=lambda p: (p.day, p.key))
    # Each window runs twice: first only pairs the attachment confirms, so a payment carrying a copy of another
    # invoice cannot take the record its twin's attachment names; then the nearest for the rest.
    for low, high in ((0, 4), (-21, 7)):
        for confirmed in (True, False):
            for pay in ordered:
                if pay.key in found:
                    continue
                hit = _portal_of(pay, ledgers)
                if hit is None:
                    continue
                portal, rows = hit
                attached = {d.invoice.number for d in pay.documents if d.invoice and d.invoice.number}
                candidates = [r for r in rows if not r.used and r.amount_cents == pay.amount_cents and low <= (pay.day - r.day).days <= high
                              and (not confirmed or set(r.invoice_ids) & attached)]
                if not candidates:
                    continue
                best = min(candidates, key=lambda r: abs((pay.day - r.day).days))
                best.used = True
                found[pay.key] = (portal, best)
    for pay in ordered:
        hit = _portal_of(pay, ledgers)
        if pay.key not in found and hit is not None:
            portal, rows = hit
            if rows and rows[0].day <= pay.day <= rows[-1].day:
                found[pay.key] = (portal, None)
    return found


def _fold_name(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.casefold())


def needs_document(pay: Payment) -> bool:
    """An expense paid to someone: not income, not a transfer between the association's accounts, not excluded."""
    if all(r["excluded"] for r in pay.rows):
        return False
    types = {r["categoryType"] for r in pay.rows}
    if "expense" not in types:
        return False
    names = " ".join(f"{r['category']} {r['parentCategory']}" for r in pay.rows).casefold()
    if any(word in pay.description.casefold() for word in NO_DOCUMENT_DESCRIPTIONS):
        return False
    return not any(word in names for word in NO_DOCUMENT)


def category_counts(pays: list[Payment]) -> dict[str, Counter]:
    """How many of each payee's single-category payments carry each category."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for pay in pays:
        if pay.payee and len(pay.rows) == 1:
            counts[pay.payee][pay.rows[0]["category"]] += 1
    return counts


def rare_category(pay: Payment, counts: dict[str, Counter]) -> str:
    """A finding when this payment's category is one the payee's other payments almost never carry.

    A vendor that bills several things (PayHOA: the subscription, lockbox fees, postage) uses several categories
    often; only a category no more than one other payment of this payee carries, beside a category most of them
    carry, is worth a look.
    """
    if not pay.payee or len(pay.rows) != 1:
        return ""
    counter = counts.get(pay.payee)
    if not counter:
        return ""
    mine = pay.rows[0]["category"]
    others = counter.copy()
    others[mine] -= 1
    total = sum(others.values())
    if total < 3:
        return ""
    usual, n = others.most_common(1)[0]
    if usual != mine and others[mine] <= 1 and n / total >= 0.6:
        return f"category {mine}; {n} of {pay.payee}'s other {total} payments are {usual}"
    return ""


def review(data_dir: Path, community: Any, roots: dict, *, formats: tuple[InvoiceFormat, ...] = ()) -> dict[str, Any]:
    """Check every expense payment's attachments; write ``invoice-review.json``."""
    from jason.community.invoice_formats import INVOICE_FORMATS

    source = _payhoa_dir(data_dir) / TRANSACTIONS
    if not source.is_file():
        return {"found": False, "note": "no transactions on disk; run jason invoices --fetch"}
    snap = json.loads(source.read_text(encoding="utf-8"))
    documents = read_documents(data_dir, snap, roots, formats or INVOICE_FORMATS, _name_pattern(community))
    pays = payments(snap, documents)
    returned = {m.group(1): p for p in pays for m in [RETURNED.search(p.description)] if m}
    cancelled = {p.key: returned[pid] for p in pays for pid in re.findall(r"Online Payment\s+(\d+)", p.description)
                 if pid in returned and returned[pid].key != p.key}
    reviewed = [p for p in pays if needs_document(p) and p.key not in cancelled and not p.inflow]
    counts = category_counts(reviewed)
    by_sha: dict[str, list[Payment]] = defaultdict(list)
    by_number: dict[tuple[str, str], list[Payment]] = defaultdict(list)
    for pay in reviewed:
        for doc in pay.documents:
            if doc.sha256:
                by_sha[doc.sha256].append(pay)
            if doc.invoice and doc.invoice.number and pay.payee:
                by_number[(pay.payee, doc.invoice.number)].append(pay)
    banks_of = {p.key: {r["bank"] for r in p.rows} for p in pays}
    ledgers = vendor_ledgers(data_dir, community)
    matched_ledger = match_ledgers(reviewed, ledgers)
    rows: list[dict[str, Any]] = []
    for pay in pays:
        if pay.inflow and needs_document(pay):
            rows.append({"key": pay.key, "date": pay.day.isoformat(), "amountCents": pay.amount_cents, "payee": pay.payee,
                         "description": pay.description[:120], "utility": pay.utility,
                         "note": f"money in: a refund or credit booked against {', '.join(r['category'] for r in pay.rows)}",
                         "categories": [r["category"] for r in pay.rows], "documents": [], "findings": [], "ok": True})
            continue
        if not needs_document(pay):
            continue
        findings: list[str] = []
        if pay.key in cancelled:
            back = cancelled[pay.key]
            rows.append({"key": pay.key, "date": pay.day.isoformat(), "amountCents": pay.amount_cents, "payee": pay.payee,
                         "description": pay.description[:120], "utility": pay.utility,
                         "note": f"returned by the bank on {back.day}; not a payment", "categories": [r["category"] for r in pay.rows],
                         "documents": [], "findings": [], "ok": True})
            continue
        docs = pay.documents
        readable = [d for d in docs if d.invoice is not None]
        findings_note = "utility payment: see jason utilities --payments" if pay.utility else ""
        if pay.utility:
            pass
        elif not docs:
            findings.append("no attachment")
        else:
            if any(not d.path for d in docs):
                findings.append("an attachment is not on disk (PayHOA gave no download link)")
            scans = [d for d in docs if d.kind in ("scan without a text layer", "unreadable text layer")]
            shown = any(d.invoice and d.invoice.shows(pay.amount_cents) for d in readable)
            totals = sum(d.invoice.total_cents or 0 for d in readable if d.invoice)
            tax_bills = [d for d in readable if d.kind == "tax_bill"]
            if tax_bills and not shown:
                findings_note = "a county tax bill: its figures are not in the text layer; jason tax holds the bill"
            elif readable and not shown and totals != pay.amount_cents:
                listed = ", ".join(f"${d.invoice.total_cents / 100:,.2f}" for d in readable if d.invoice and d.invoice.total_cents)
                findings.append(f"no attachment prints the payment's ${pay.amount_cents / 100:,.2f}"
                                + (f" (the invoices ask {listed})" if listed else ""))
            if scans and not readable:
                what = "a scan without a text layer" if scans[0].kind.startswith("scan") else "a PDF whose text layer is glyph codes"
                findings.append(f"the attachment is {what}; the amount is unchecked (an OCR engine would read it)")
            if pay.payee and readable and not any(names_vendor(_doc_text(data_dir, d), pay.payee) for d in readable):
                others = sorted({d.invoice.vendor for d in readable if d.invoice and d.invoice.vendor and d.invoice.vendor != pay.payee})
                if others:
                    findings.append(f"the attachment names {', '.join(others)}, not the payee {pay.payee}")
            for doc in readable:
                inv = doc.invoice
                if inv and inv.invoice_date:
                    if (inv.invoice_date - pay.day).days > 7:
                        findings.append(f"invoice {inv.number or doc.filename} is dated {inv.invoice_date}, after the payment")
                    elif (pay.day - inv.invoice_date).days > 365:
                        findings.append(f"invoice {inv.number or doc.filename} is dated {inv.invoice_date}, over a year before the payment")
            kinds = {d.kind for d in readable}
            if readable and not shown and kinds & {"proposal", "contract", "correspondence", "form"}:
                findings.append("the attachment reads as " + " and ".join(sorted(kinds & {"proposal", "contract", "correspondence", "form"}))
                                + ", not an invoice")
        for doc in docs:
            others = [p for p in by_sha.get(doc.sha256, []) if p.key != pay.key and not (banks_of[p.key] - banks_of[pay.key])] if doc.sha256 else []
            if others and not pay.utility:
                # Same amount within days: maybe paid twice. A month apart: last month's file attached again.
                same = [p for p in others if p.amount_cents == pay.amount_cents and abs((p.day - pay.day).days) <= 10]
                what = "possibly paid twice" if same else "attached to another payment too"
                findings.append(f"{doc.filename}: {what}: " + ", ".join(f"{p.day} ${p.amount_cents / 100:,.2f}" for p in others[:4]))
            if doc.invoice and doc.invoice.number and pay.payee and not pay.utility:
                twins = [p for p in by_number[(pay.payee, doc.invoice.number)] if p.key != pay.key
                         and not any(d.sha256 == doc.sha256 for d in p.documents)]
                if twins:
                    findings.append(f"{pay.payee} invoice {doc.invoice.number} is also attached to "
                                    + ", ".join(f"{p.day} ${p.amount_cents / 100:,.2f}" for p in twins[:4]))
        vendor_record = None
        if pay.key in matched_ledger:
            portal, ledger = matched_ledger[pay.key]
            if ledger is None:
                findings.append(f"{portal.vendor}'s own ledger records no ${pay.amount_cents / 100:,.2f} payment in the days before this one")
            else:
                vendor_record = {"vendor": portal.vendor, "day": ledger.day.isoformat(), "invoiceIds": list(ledger.invoice_ids),
                                 "invoiceFiles": list(ledger.invoice_files)}
                attached = {d.invoice.number for d in docs if d.invoice and d.invoice.number}
                if ledger.invoice_ids and docs and not attached & set(ledger.invoice_ids):
                    where = f" (the vendor's copy: {ledger.invoice_files[0]})" if ledger.invoice_files else ""
                    findings.append(f"{portal.vendor} applied this payment to invoice {', '.join(ledger.invoice_ids)}; the attachment is "
                                    f"invoice {', '.join(sorted(attached)) or 'unread'}{where}")
                elif ledger.invoice_ids and not docs:
                    where = f"; the vendor's copy is {ledger.invoice_files[0]}" if ledger.invoice_files else ""
                    findings[:] = [f for f in findings if f != "no attachment"]
                    findings.append(f"no attachment; {portal.vendor} applied it to invoice {', '.join(ledger.invoice_ids)}{where}")
                # The vendor's ledger settles what a payment paid; a reused copy of another invoice is the wrong file, not a second payment.
                findings[:] = [f for f in findings if " is also attached to " not in f and "possibly paid twice" not in f]
        rare = "" if pay.utility else rare_category(pay, counts)
        if rare:
            findings.append(rare)
        rows.append({
            "key": pay.key, "date": pay.day.isoformat(), "amountCents": pay.amount_cents, "payee": pay.payee,
            "description": pay.description[:120], "utility": pay.utility, "note": findings_note,
            "categories": [r["category"] for r in pay.rows],
            "documents": [{"id": d.attachment_id, "filename": d.filename, "path": data_path(data_dir, d.path),
                           "kind": d.kind, "utility": d.utility,
                           "invoice": None if d.invoice is None else {
                               "vendor": d.invoice.vendor, "number": d.invoice.number,
                               "date": d.invoice.invoice_date.isoformat() if d.invoice.invoice_date else None,
                               "totalCents": d.invoice.total_cents, "method": d.invoice.method + (f" (ocr: {d.ocr})" if d.ocr else ""),
                               "showsPayment": d.invoice.shows(pay.amount_cents)}} for d in docs],
            "vendorLedger": vendor_record,
            "findings": findings,
            "ok": not findings,
        })
    result = {
        "found": True,
        "transactionsSyncedAt": snap.get("syncedAt"),
        "reviewedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary(rows),
        "scorecard": scorecard(pays),
        "payments": rows,
        "caveats": [
            "A payment's amount missing from its attachment is a reason to look: the file may be another invoice, or the "
            "payment may be partial, combined, or net of a credit.",
            "A vendor's usual category is the one 70% or more of its payments carry; a different one can be right.",
            "Utility payments are audited by jason utilities --payments.",
            "Jason changes nothing in PayHOA; the treasurer re-attaches, re-categorizes, or recovers a double payment.",
        ],
    }
    (_payhoa_dir(data_dir) / REVIEW).write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def _doc_text(data_dir: Path, doc: Document) -> str:
    cache = _payhoa_dir(data_dir) / TEXT_CACHE / (f"{doc.sha256}.{doc.ocr}.txt" if doc.ocr else f"{doc.sha256}.txt")
    return cache.read_text(encoding="utf-8") if cache.is_file() else ""


def summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter = Counter()
    for row in rows:
        counter["payments"] += 1
        counter["clean"] += row["ok"]
        for finding in row["findings"]:
            key = re.sub(r"[$\d,.]+", "#", finding.split(":")[0])[:60]
            if finding.startswith("category "):
                key = "category differs from the vendor's usual"
            elif "possibly paid twice" in finding:
                key = "same file on another payment of the same amount"
            elif "attached to another payment too" in finding:
                key = "same file on another payment"
            elif "is also attached to" in finding:
                key = "same invoice number on another payment"
            elif finding.startswith("the attachment is "):
                key = "attachment unreadable (scan or glyph codes)"
            elif finding.startswith("no attachment prints"):
                key = "amount not on the attachment"
            elif finding.startswith("invoice ") and "dated" in finding:
                key = "invoice date after, or long before, the payment"
            elif " applied this payment to invoice " in finding:
                key = "attachment is not the invoice the vendor applied the payment to"
            elif " applied it to invoice " in finding:
                key = "no attachment; the vendor's ledger names the invoice"
            elif "own ledger records no" in finding:
                key = "payment missing from the vendor's own ledger"
            elif finding.startswith("the attachment names"):
                key = "attachment names another vendor"
            counter[key] += 1
    return dict(counter.most_common())


def scorecard(pays: list[Payment]) -> list[dict[str, Any]]:
    """Per payee: how often the reader found an invoice number, a date, a total, and the payment's amount."""
    stats: dict[str, Counter] = defaultdict(Counter)
    for pay in pays:
        if pay.utility or not pay.payee:
            continue
        for doc in pay.documents:
            if doc.invoice is None:
                continue
            s = stats[pay.payee]
            s["invoices"] += 1
            s["number"] += bool(doc.invoice.number)
            s["date"] += bool(doc.invoice.invoice_date)
            s["total"] += doc.invoice.total_cents is not None
            s["totalIsPayment"] += doc.invoice.total_cents == pay.amount_cents
            s["shown"] += doc.invoice.shows(pay.amount_cents)
            s["format"] += doc.invoice.method.startswith("format:")
    rows = []
    for payee, s in stats.items():
        n = s["invoices"]
        rows.append({"payee": payee, "invoices": n, "format": s["format"] > 0,
                     **{k: round(s[k] / n, 2) for k in ("number", "date", "total", "totalIsPayment", "shown")}})
    return sorted(rows, key=lambda r: -r["invoices"])


def load_review(data_dir: Path) -> dict[str, Any] | None:
    path = _payhoa_dir(data_dir) / REVIEW
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


# --- the attachments as document references (docs/console/doc-component.md) ---------------------------------------------

def data_path(data_dir: Path, path: str | Path) -> str:
    """A file's path under the data folder, posix (``transactions/2099/01/invoices/1-a.pdf``); "" for none, or for a
    file outside the folder (a portal's own bill): a loader never carries an absolute path."""
    if not path:
        return ""
    try:
        return Path(path).resolve().relative_to(Path(data_dir).resolve()).as_posix()
    except (OSError, ValueError):
        return ""


_PLACES: dict[str, tuple[tuple[int, int], dict[tuple[int, str], str]]] = {}


def attachment_places(data_dir: Path, store: str = TRANSACTIONS) -> dict[tuple[int, str], str]:
    """Where a stored transactions file's attachments (``transactions.json``, ``utility-transactions.json``) are kept
    under the data folder: ``(payment key, "#<attachment id>")`` and ``(payment key, filename)`` -> the path of the copy
    ``local_attachment`` finds there. The payment key is the parent transaction's id, or the transaction's own. An
    attachment with no copy under the folder has none. Read once a version of the file (the store is large)."""
    source = _payhoa_dir(data_dir) / store
    try:
        stat = source.stat()
    except OSError:
        return {}
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _PLACES.get(str(source.resolve()))
    if cached is not None and cached[0] == stamp:
        return cached[1]
    found: dict[tuple[int, str], str] = {}
    for tx in json.loads(source.read_text(encoding="utf-8")).get("transactions") or []:
        if tx.get("id") is None:
            continue
        key = int(tx.get("parentId") or tx["id"])
        for raw in tx.get("attachments") or []:
            if raw.get("id") is None:
                continue
            rel = data_path(data_dir, local_attachment(data_dir, tx, raw, {}))
            if rel and (Path(data_dir) / rel).is_file():
                found.setdefault((key, f"#{raw['id']}"), rel)
                found.setdefault((key, str(raw.get("filename") or "")), rel)
    _PLACES[str(source.resolve())] = (stamp, found)
    return found


def attachment_ref(data_dir: Path, rel: str, name: str = "") -> dict[str, Any] | None:
    """The ``DocRef`` of an attachment kept under the data folder (``file:transactions/...``), when the evidence opens it
    there (a place ``jason.web.access`` names, a kind the viewer shows); None otherwise."""
    from jason.approvals.docref import file_ref
    from jason.approvals.evidence_documents import file_place

    if not rel or file_place(Path(data_dir), rel) is None:
        return None
    return file_ref(rel, name=name or None, data_dir=data_dir)      # a file: address keeps its path exactly


def document_refs(data_dir: Path, rows: list[dict[str, Any]], *, store: str = TRANSACTIONS,
                  field: str = "documents") -> list[dict[str, Any]]:
    """Each payment row's attachments (``field``) with ``doc``, its ``DocRef``, beside the filename, when jason keeps a
    copy the evidence opens. The path a review recorded is used first; an older review's is found from the stored
    transactions (``store``). Changes ``rows`` in place and returns them."""
    places: dict[tuple[int, str], str] | None = None
    for row in rows:
        try:
            key = int(row.get("key"))
        except (TypeError, ValueError):
            continue
        for doc in row.get(field) or []:
            rel = str(doc.get("path") or "")
            if not rel:
                if places is None:
                    places = attachment_places(data_dir, store)
                rel = (places.get((key, f"#{doc['id']}")) if doc.get("id") is not None else "") \
                    or places.get((key, str(doc.get("filename") or ""))) or ""
            ref = attachment_ref(data_dir, rel, str(doc.get("filename") or ""))
            if ref is not None:
                doc["doc"] = ref
    return rows


def review_lines(result: dict[str, Any], *, limit: int = 60, payee: str = "") -> list[str]:
    if not result.get("found"):
        return [result.get("note", "no review")]
    out = [f"Transactions synced {result['transactionsSyncedAt']}"]
    out.extend(f"  {k}: {v}" for k, v in result["summary"].items())
    out.append("")
    out.append("Reader scorecard (share of invoices where the reader found each field)")
    for row in result["scorecard"][:25]:
        out.append(f"  {row['payee'][:34]:<34} {row['invoices']:>4}  number {row['number']:.0%}  date {row['date']:.0%}  "
                   f"total {row['total']:.0%}  total=payment {row['totalIsPayment']:.0%}  amount shown {row['shown']:.0%}"
                   + ("  (format)" if row["format"] else ""))
    out.append("")
    bare: Counter = Counter(r["payee"] or r["description"][:30] for r in result["payments"] if r["findings"] == ["no attachment"])
    if bare:
        out.append("Payments whose only finding is no attachment, by payee:")
        out.extend(f"  {n:>4}  {name}" for name, n in bare.most_common(12))
        out.append("")
    shown = [r for r in result["payments"] if not r["ok"] and r["findings"] != ["no attachment"]
             and (not payee or payee.casefold() in r["payee"].casefold())]
    for row in list(reversed(shown))[:limit]:
        out.append(f"{row['date']} {row['payee'] or row['description'][:40]} ${row['amountCents'] / 100:,.2f} [{', '.join(row['categories'])}]")
        out.extend(f"    - {f}" for f in row["findings"])
    if len(shown) > limit:
        out.append(f"... {len(shown) - limit} more in data/payhoa/{REVIEW}")
    return out


__all__ = ["fetch", "review", "load_review", "review_lines", "payments", "needs_document", "category_counts", "rare_category",
           "scorecard", "local_attachment", "data_path", "attachment_places", "attachment_ref", "document_refs"]
