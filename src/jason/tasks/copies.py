"""Every copy of every invoice and bill the association holds, grouped into documents, with the best copy and the payment.

Collects ``DocumentCopy`` rows from each channel, reading what jason already stores:

- the issuer's portal: the i-doxs and SMUD bills in the utility store (``data/utilities.db``) whose file is a portal
  download, and the vendor portals' invoice PDFs (``data/vendors/<key>/<account>/invoices``);
- email: the PDFs ``jason gmail --files`` saved (``data/gmail/files``);
- PayHOA: each payment's attachments (the utility bills among them from the utility store, the rest read as invoices);
- paper: the scanned letters PostScanMail delivered whose kind is a bill, invoice, or tax bill.

``jason.community.copies.group`` joins the copies that are one document and records the rule; ``best`` chooses the copy
to read by ``Mystique.copy_priority()``. Each document is then matched to a PayHOA payment: the payment a PayHOA copy
hangs on, or a payment to the issuer's PayHOA vendor of the document's amount, from 20 days before it to 90 after.

Every copy stays where it is. The report is ``data/reports/copies.json``; nothing is moved, deleted, or attached.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from jason.community.copies import Channel, DocumentCopy, LogicalDocument, best, group
from jason.community.copies import BEFORE_WORK, fulfilments
from jason.community.incidents import Stage, stage_of
from jason.community.invoices import read_invoice, readable
from jason.tasks.sources import money_in

REPORT = "copies.json"
BILL_KINDS = ("vendor invoice or statement", "utility bill", "property tax bill", "insurance policy, renewal, or invoice")


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _formats() -> tuple:
    from jason.community.invoice_formats import INVOICE_FORMATS

    return INVOICE_FORMATS


def _tx_of_path(path: Path) -> int | None:
    """The PayHOA transaction an attachment file belongs to: the export's "<tx id>-<name>" or the cache's "<tx id>/" folder."""
    parts = path.parts
    if "invoices" in parts:
        head = path.name.split("-", 1)[0]
        return int(head) if head.isdigit() else None
    if "attachments" in parts:
        folder = parts[parts.index("attachments") + 1] if parts.index("attachments") + 1 < len(parts) else ""
        return int(folder) if folder.isdigit() else None
    return None


def _stage(name: str, text: str, *, billed: bool = False) -> Stage | None:
    """A copy's stage by its file name, then its words; a bill jason fetched or found on a payment that names no other
    stage is an invoice."""
    stage = stage_of(name, text)
    if stage is Stage.OTHER:
        return Stage.INVOICE if billed else None
    return stage


def _issuers(community: Any) -> dict[str, str]:
    """PayHOA vendor name -> named sender, for issuers known by their PayHOA name."""
    return {s.payhoa_vendor: s.name for s in community.senders() if s.payhoa_vendor}


def _issuer_of_text(text: str, community: Any) -> str:
    from jason.community.sources import resolve

    named = resolve("", text, tuple(community.senders()))[0]
    return named.name if named else ""


def utility_copies(data_dir: Path, community: Any, roots: dict) -> list[DocumentCopy]:
    """Every stored utility bill, one copy per file: a portal download or a PayHOA attachment."""
    from jason.community.symbols import Utility
    from jason.community.utility_store import UtilityStore

    store_path = Path(data_dir) / "utilities.db"
    if not store_path.is_file():
        return []
    names = {Utility.SMUD: "SMUD", Utility.CITY_OF_SACRAMENTO: "City of Sacramento Department of Utilities"}
    portal_roots = [str(Path(r).resolve()).lower() for r in roots.values()]
    out = []
    with UtilityStore(store_path, readonly=True) as store:
        for bill in store.bills():
            source = Path(bill.source)
            portal = any(str(source.resolve()).lower().startswith(r) for r in portal_roots)
            out.append(DocumentCopy(Channel.ISSUER_PORTAL if portal else Channel.PAYHOA, str(source), issuer=names.get(bill.provider, ""),
                                    number=bill.bill_id if portal else "", account=bill.account, issued=bill.bill_date,
                                    total_cents=bill.payable_cents, sha256=_sha(source) if source.is_file() else "",
                                    payhoa_tx=None if portal else _tx_of_path(source), title=source.name, stage=Stage.INVOICE))
    return out


def portal_invoice_copies(data_dir: Path, community: Any) -> list[DocumentCopy]:
    """The vendor portals' invoice PDFs, read as invoices; the file name is the invoice number."""
    from jason.tasks.utilities import pdf_text

    out = []
    for key_dir in sorted((Path(data_dir) / "vendors").glob("*")):
        issuer = next((s.name for s in community.senders() if key_dir.name.lower() in s.name.lower().replace(" ", "")), key_dir.name)
        for pdf in sorted(key_dir.glob("*/invoices/*.pdf")):
            try:
                text = pdf_text(pdf)
            except Exception:
                text = ""
            inv = read_invoice(text, formats=_formats()) if text else None
            out.append(DocumentCopy(Channel.ISSUER_PORTAL, str(pdf), issuer=issuer, number=pdf.stem,
                                    issued=inv.invoice_date if inv else None, total_cents=inv.total_cents if inv else None,
                                    sha256=_sha(pdf), readable=bool(text and readable(text)), title=pdf.name, stage=Stage.INVOICE))
    return out


def _writers(data_dir: Path) -> dict[str, list[str]]:
    """Each stored message's sender domains (the From, or the writer behind a group), by message id."""
    from jason.tasks.gmail import CORRESPONDENCE, _load

    return {m["messageId"]: sorted({a.rsplit("@", 1)[-1] for _n, a, role in m.get("people") or [] if role == "from"})
            for m in _load(data_dir, CORRESPONDENCE).get("messages") or []}


def email_issuer(domains: list[str], writer: list[str], text: str, subject: str, community: Any, *, bill: bool = True) -> str:
    """Who issued an emailed document. The sender it came from counts before the others copied on the message; a
    platform (PayHOA's notices, PostScanMail's scans) only carries another's document, so the document's letterhead, then
    the subject, names the issuer; else it stays unknown."""
    from jason.community.sources import SourceKind
    from jason.tasks.gmail import sender_of

    senders = tuple(community.senders())
    named = sender_of(writer, senders) or sender_of(domains, senders)
    if named is not None and named.kind is not SourceKind.PLATFORM:
        return named.name
    # The words name an issuer only on a bill, proposal, or contract: minutes that approved a vendor's bid are not its.
    if not bill:
        return ""
    return _issuer_of_text(text, community) or _issuer_of_text(subject, community)


def email_copies(data_dir: Path, community: Any, *, ocr: Callable[[Path], str] | None = None) -> list[DocumentCopy]:
    from jason.tasks.gmail import email_files
    from jason.tasks.utilities import pdf_text

    writers = _writers(data_dir)
    out = []
    for f in email_files(data_dir):
        path = Path(data_dir) / f["path"]
        try:
            text = pdf_text(path)
        except Exception:
            text = ""
        if not text.strip() or not readable(text):
            # A scan or a glyph-coded layer: the OCR text a review already cached for the same file, else the engine given.
            from jason.tasks.invoice_review import best_text

            text = best_text(data_dir, path) or (ocr(path) if ocr is not None else text)
        # A billing service (QuickBooks sends from intuit.com) names the vendor only in the subject: "SUMMIT ROOFING -
        # Invoice 905".
        # What the association sent out was not issued by the people it went to (the RCS TC quote mailed to the reserve
        # study preparer as backup): only the document itself can name its issuer.
        outgoing = f.get("direction") == "out"
        inv = read_invoice(text, formats=_formats()) if text else None
        stage = _stage(f["name"], f.get("subject", ""), billed=bool(inv and inv.total_cents))
        issuer = email_issuer([] if outgoing else f.get("domains") or [], [] if outgoing else writers.get(f["messageId"], []),
                              text, f.get("subject", ""), community, bill=stage is not None)
        out.append(DocumentCopy(Channel.EMAIL, f["path"], issuer=issuer, number=inv.number if inv else "",
                                issued=(inv.invoice_date if inv else None) or _day(f["at"]), total_cents=inv.total_cents if inv else None,
                                sha256=f["sha256"], received=_day(f["at"]), readable=bool(text and readable(text)),
                                title=f"{f['name']} ({f.get('subject', '')[:50]})",
                                # By the file's name, then the subject; never the body, whose fine print ("this
                                # agreement", "terms") would make an invoice a contract and keep it from its payment.
                                stage=stage))
    return out


def payhoa_copies(data_dir: Path, community: Any, roots: dict) -> list[DocumentCopy]:
    """PayHOA's attachments that are not utility bills (the utility store reads those), read as invoices."""
    from jason.tasks.invoice_review import read_documents

    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return []
    snap = json.loads(path.read_text(encoding="utf-8"))
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    issuers = _issuers(community)
    from jason.community.invoice_formats import INVOICE_FORMATS

    documents = read_documents(data_dir, snap, roots, INVOICE_FORMATS)
    out = []
    for tx in snap["transactions"]:
        if tx.get("deletedAt"):
            continue
        for raw in tx.get("attachments") or []:
            doc = documents.get(int(raw["id"]))
            if doc is None or doc.utility or raw.get("deletedAt"):
                continue
            inv = doc.invoice
            payee = vendors.get(int(tx.get("vendorId") or 0)) or ""
            issuer = issuers.get(payee, "") or ((_issuer_of_text(inv.vendor, community) or inv.vendor) if inv and inv.vendor else "")
            out.append(DocumentCopy(Channel.PAYHOA, doc.path or f"payhoa attachment {doc.attachment_id}", issuer=issuer,
                                    number=inv.number if inv else "", issued=inv.invoice_date if inv else None,
                                    total_cents=inv.total_cents if inv else None, sha256=doc.sha256, received=_day(tx.get("transactionDate")),
                                    readable=doc.text_chars >= 50, payhoa_tx=int(tx["id"]), title=doc.filename,
                                    stage=_stage(doc.filename or "", "", billed=True)))
    return out


def paper_copies(data_dir: Path, community: Any) -> list[DocumentCopy]:
    from jason.tasks.mail import load_items, mail_dir

    out = []
    for row in load_items(data_dir).values():
        if row.get("kind") not in BILL_KINDS or (row.get("source") or {}).get("misdirected"):
            continue
        text_file = mail_dir(data_dir) / row["mailId"] / "text.txt"
        text = text_file.read_text(encoding="utf-8") if text_file.is_file() else ""
        inv = read_invoice(text, formats=_formats()) if text else None
        received = _day(row.get("received"))
        # A letter is a bill copy only when it reads as one: an amount, or a number. The City's backflow test notices
        # are sorted with its bills but carry neither.
        if inv is None or not (inv.total_cents or inv.number):
            continue
        # A date after the letter arrived is a due or expiration date, not the date it was issued.
        issued = inv.invoice_date if inv.invoice_date and received and inv.invoice_date <= received + timedelta(days=3) else None
        facts = row.get("facts") or {}
        accounts = facts.get("accounts") or facts.get("policies") or []
        pdf = next(iter(sorted((mail_dir(data_dir) / row["mailId"]).glob("*.pdf"))), None)
        out.append(DocumentCopy(Channel.PAPER, str(pdf or text_file), issuer=(row.get("source") or {}).get("name") or "",
                                number=inv.number, account=accounts[0] if accounts else "",
                                issued=issued, total_cents=inv.total_cents,
                                sha256=_sha(pdf) if pdf else "", received=received,
                                readable=bool(text and readable(text)), title=f"mail {row['mailId']}",
                                stage=Stage.INVOICE))
    return out


_PAYMENT_NUMBER = re.compile(r"ONLINE PAYMENT (\d{8,})")


def returned_payments(snap: dict[str, Any]) -> dict[int, str]:
    """PayHOA payments the bank returned: the "CREDIT RETURN: ONLINE PAYMENT <n>" line names the payment it undoes.
    Returns {transaction id: the return's date}."""
    returns: dict[str, str] = {}
    for t in snap.get("transactions", []):
        text = str(t.get("description") or "").upper()
        if "CREDIT RETURN" in text and not t.get("deletedAt"):
            m = _PAYMENT_NUMBER.search(text)
            if m:
                returns[m.group(1)] = str(t.get("transactionDate") or "")[:10]
    found = {}
    for t in snap.get("transactions", []):
        text = str(t.get("description") or "").upper()
        m = _PAYMENT_NUMBER.search(text)
        if m and "CREDIT RETURN" not in text and m.group(1) in returns:
            found[int(t["id"])] = returns[m.group(1)]
    return found


def _payments(data_dir: Path) -> tuple[list[dict[str, Any]], dict[int, str], dict[int, int]]:
    """Live payments (not returned, not money in), the returned ones, and each split line's parent payment."""
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return [], {}, {}
    snap = json.loads(path.read_text(encoding="utf-8"))
    vendors = {int(k): v for k, v in snap.get("vendors", {}).items()}
    returned = returned_payments(snap)
    live = [{"id": int(t["id"]), "date": _day(t["transactionDate"]), "amountCents": int(t.get("amount") or 0),
             "vendor": vendors.get(int(t.get("vendorId") or 0)) or "", "description": str(t.get("description") or "")}
            for t in snap["transactions"] if not t.get("deletedAt") and not money_in(t) and int(t.get("amount") or 0) > 0
            and int(t["id"]) not in returned]
    parent_of = {int(t["id"]): int(t["parentId"]) for t in snap["transactions"] if t.get("parentId")}
    # A transfer between the association's accounts (a reserve reimbursing operating) carries the invoice as backup.
    for t in snap["transactions"]:
        if "TRANSFER TO" in str(t.get("description") or "").upper() or "TRANSFER FROM" in str(t.get("description") or "").upper():
            parent_of[int(t["id"])] = -int(t["id"])
    return live, returned, parent_of


def _described(payment: dict[str, Any], words: tuple[str, ...]) -> bool:
    """A payment with no PayHOA vendor whose bank description names the issuer ("Online Payment ... To Flock Group Inc")."""
    if payment.get("vendor") or not words:
        return False
    text = " ".join(re.sub(r"[^A-Z0-9]+", " ", str(payment.get("description") or "").upper()).split())
    return any(f" {w} " in f" {text} " for w in (" ".join(re.sub(r"[^A-Z0-9]+", " ", w.upper()).split()) for w in words) if w)


def incoming(data_dir: Path) -> set[int]:
    """PayHOA transactions that brought money in (a deposited claim check, a transfer in): a document attached to one
    is its backup, not a second payment."""
    from jason.tasks.sources import money_in

    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return set()
    return {int(t["id"]) for t in json.loads(path.read_text(encoding="utf-8"))["transactions"] if money_in(t)}


def _payment(doc: LogicalDocument, payments: list[dict[str, Any]], vendor_of: dict[str, str],
             returned: dict[int, str] | None = None, parent_of: dict[int, int] | None = None,
             words_of: dict[str, tuple[str, ...]] | None = None, money_in: set[int] | None = None) -> dict[str, Any] | None:
    returned, parent_of, words_of, money_in = returned or {}, parent_of or {}, words_of or {}, money_in or set()
    attached = sorted({c.payhoa_tx for c in doc.copies if c.payhoa_tx})
    if attached:
        deposits = [t for t in attached if t in money_in]
        live = [t for t in attached if t not in returned and t not in money_in]
        found: dict[str, Any] = {"txIds": live or attached, "how": "attached"}
        if deposits:
            # The Vitesse claim check deposited on August 5, 2026 and check 9993 paying it out the next day.
            found["deposits"] = deposits
        if len(live) < len(attached):
            found["returned"] = {str(t): returned[t] for t in attached if t in returned}
        # The split lines of one payment (a bill split by budget line) are one payment; a transfer carrying the invoice
        # as backup (marked with a negative parent) is not a second payment.
        transfers = [t for t in live if parent_of.get(t, 0) < 0]
        if transfers:
            found["backupOnTransfers"] = transfers
        if len({parent_of.get(t, t) for t in live if t not in transfers}) > 1:
            found["onSeveralPayments"] = True
        return found
    # A quote or bid is not paid; the invoice that followed it is (``fulfilments``).
    if doc.before_work:
        return None
    vendor = vendor_of.get(doc.issuer)
    words = words_of.get(doc.issuer, ())
    # A copy with no date of its own (a letter) is anchored on when it arrived.
    anchor = doc.issued or min((c.received for c in doc.copies if c.received), default=None)
    if not (vendor or words) or not doc.total_cents or not anchor:
        return None
    lo, hi = anchor - timedelta(days=45 if not doc.issued else 20), anchor + timedelta(days=90)
    hits = [p for p in payments if ((vendor and p["vendor"] == vendor) or _described(p, words))
            and p["amountCents"] == doc.total_cents and p["date"] and lo <= p["date"] <= hi]
    if not hits:
        return None
    if len(hits) == 1:
        return {"txIds": [hits[0]["id"]], "how": "amount and date", "date": hits[0]["date"].isoformat()}
    # A bill of the same amount every month: the nearest payment on or after the bill, else the nearest before it.
    after = sorted((p for p in hits if p["date"] >= anchor), key=lambda p: p["date"])
    nearest = after[0] if after else max(hits, key=lambda p: p["date"])
    return {"txIds": [nearest["id"]], "how": "nearest of several by amount", "date": nearest["date"].isoformat(),
            "others": [p["id"] for p in hits if p is not nearest]}


# How far a payment may be from a proposal's amount and still be named as a candidate for it.
NEAR_SHARE = 0.10
PAIR_SHARE = 0.01


def proposal_payments(doc: LogicalDocument, payments: list[dict[str, Any]], vendor_of: dict[str, str],
                      words_of: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """PayHOA payments that may pay a proposal no invoice on file followed: to the same vendor (its PayHOA vendor, or its
    words in a vendorless payment's description), on or after the proposal within a year. One of the same amount is
    ``paid``, the nearest after the proposal; otherwise payments within 10%, and pairs within 1% of it (a deposit and a
    final bill), are ``candidates`` for a person to confirm. A monthly fee can match a bid's amount by chance."""
    vendor, words = vendor_of.get(doc.issuer), words_of.get(doc.issuer, ())
    if not (vendor or words) or not doc.total_cents or not doc.issued:
        return {}
    start, want = doc.issued, doc.total_cents
    pool = sorted((p for p in payments if p["date"] and start <= p["date"] <= start + timedelta(days=365)
                   and ((vendor and p["vendor"] == vendor) or _described(p, words))), key=lambda p: p["date"])
    exact = [p for p in pool if p["amountCents"] == want]
    if exact:
        p = exact[0]
        return {"paid": {"txIds": [p["id"]], "how": "same vendor and amount after the proposal", "date": p["date"].isoformat()},
                **({"others": [q["id"] for q in exact[1:]]} if len(exact) > 1 else {})}
    near = [{"txIds": [p["id"]], "how": "within 10% of the proposal", "date": p["date"].isoformat(), "amountCents": p["amountCents"]}
            for p in pool if abs(p["amountCents"] - want) <= NEAR_SHARE * want]
    pairs = [{"txIds": [a["id"], b["id"]], "how": "two payments that sum to the proposal",
              "date": b["date"].isoformat(), "amountCents": a["amountCents"] + b["amountCents"]}
             for i, a in enumerate(pool) for b in pool[i + 1:] if abs(a["amountCents"] + b["amountCents"] - want) <= PAIR_SHARE * want]
    return {"candidates": (near + pairs)[:6]} if near or pairs else {}


def audit_notes(data_dir: Path) -> dict[int, list[str]]:
    """What jason's other audits already say about a PayHOA payment, by transaction id: the utility payment audit
    (``jason utilities --payments``: paid twice, and the credit on the next bill) and each vendor portal's verification
    (``jason vendors --verify``: the invoice the vendor applied the payment to, against the one attached)."""
    notes: dict[int, list[str]] = {}
    audit = Path(data_dir) / "payhoa" / "utility-audit.json"
    if audit.is_file():
        for p in json.loads(audit.read_text(encoding="utf-8")).get("payments") or []:
            said = [f for f in p.get("findings") or [] if f.startswith(("paid twice", "evidence", "same amount as"))
                    or "did not pay" in f or "do not include the bill" in f]
            for row in p.get("rows") or [{"txId": p.get("key")}]:
                if said and row.get("txId"):
                    notes.setdefault(int(row["txId"]), []).extend(f"utility audit: {f}" for f in said)
    for verification in sorted((Path(data_dir) / "vendors").glob("*/verification.json")):
        for p in json.loads(verification.read_text(encoding="utf-8")).get("payments") or []:
            said = [f for f in p.get("findings") or [] if "applied this payment" in f]
            if said and p.get("transactionId"):
                notes.setdefault(int(p["transactionId"]), []).extend(f"{verification.parent.name} portal: {f}" for f in said)
    return notes


def next_bill_credit(data_dir: Path, account: str, issued: date | None, amount_cents: int | None) -> str:
    """When a utility bill was paid twice: the account's next bill in the utility store, if it asked for less than its
    charges by at least the bill's amount (the second payment's credit). When the next bill on file came more than 45
    days later, a month's bill is missing between them and the credit paid it: any remainder shows on the bill on file
    (SMUD, April 2024: $250.11 paid twice, the April bill not on file, the May bill $5.92 less than its charges). Returns
    the evidence, or ""."""
    import sqlite3

    store = Path(data_dir) / "utilities.db"
    if not (account and issued and amount_cents) or not store.is_file():
        return ""
    with sqlite3.connect(store) as db:
        row = db.execute("select bill_date, total_cents, due_cents from bills where account = ? and bill_date > ? "
                         "and due_cents is not null order by bill_date limit 1", (account, issued.isoformat())).fetchone()
    if row and row[1] - row[2] >= amount_cents:
        return f"the {row[0]} bill asked ${row[2] / 100:,.2f} against ${row[1] / 100:,.2f} of charges"
    if row and row[1] > row[2] and (date.fromisoformat(row[0]) - issued).days > 45:
        return (f"no bill on file between; the {row[0]} bill asked ${row[2] / 100:,.2f} against ${row[1] / 100:,.2f} of "
                "charges, the rest of the credit after it paid the missing month")
    return ""


def _explain(tx_ids: list[int], parent_of: dict[int, int], notes: dict[int, list[str]],
             by_id: dict[int, dict[str, Any]] | None = None, total_cents: int | None = None, credit: str = "",
             title: str = "", stage: str | None = None) -> str:
    """Why one document hangs on several payments, when jason's audits already say, or when the payments themselves
    show a recurring bill: every one of the document's amount, at least 20 days apart."""
    said = [n for t in tx_ids for n in notes.get(t, [])]
    if any("paid twice" in n for n in said):
        return "paid twice, per the utility audit (the next bill shows the credit)"
    # The bills on file outrank the audit's "no credit" reading, which missed a month's bill absent from the store.
    if credit:
        return f"paid twice; the next bill shows the credit ({credit})"
    if any("same amount as" in n for n in said):
        return ("two payments of the same amount with no credit after, per the utility audit: the second may have paid an "
                "older balance; check the account history")
    if any("did not pay" in n or "do not include the bill" in n for n in said):
        return "attached to the wrong payment, per the utility audit (the bill of another month)"
    if any("applied this payment" in n and "attached:" in n for n in said):
        return "attached to the wrong payment, per the vendor's portal (the vendor applied the payment to another invoice)"
    if len({parent_of.get(t, t) for t in tx_ids}) < len(tx_ids):
        return "split lines of one payment"
    found = [(by_id or {}).get(t) for t in tx_ids]
    # A vendor that asks a deposit before ordering materials is paid twice for one job: the deposit, then the balance
    # (Industrial Door Company, July 2026: the deposit request hangs on both payments).
    if len(tx_ids) == 2 and re.search(r"\bdeposit\b", title, re.I):
        return "a deposit and the balance of one job"
    # A quote for work in parts, each part paid when done: RCS TC's mulch quote (job 1 in May 2025, job 2 in October,
    # larger by the June quote) hangs on both payments.
    if stage in {s.value for s in BEFORE_WORK} and all(found) and len(found) > 1:
        days = sorted(p["date"] for p in found if p["date"])
        if len(days) == len(found) and all((b - a).days >= 20 for a, b in zip(days, days[1:])):
            return "one quote for several jobs, each paid when done"
    # One letter or bill paid in parts: the City's two false alarm fines ($404 and $467) on one $871 notice.
    if total_cents and all(found) and len(found) > 1 and sum(p["amountCents"] for p in found) == total_cents:
        return "one bill paid in parts (the payments add up to it)"
    # A metered bill moves by a cent or two month to month ($1.49, $1.50).
    if total_cents and all(p and p["date"] and abs(p["amountCents"] - total_cents) <= max(5, total_cents // 50) for p in found):
        days = sorted(p["date"] for p in found)
        if all((b - a).days >= 20 for a, b in zip(days, days[1:])):
            return "a recurring bill of the same amount attached to several months' payments (each month's own bill is missing)"
    return ""


def _copy_row(c: DocumentCopy) -> dict[str, Any]:
    return {"channel": c.channel.value, "ref": c.ref, "title": c.title, "number": c.number, "account": c.account,
            "issued": c.issued.isoformat() if c.issued else None, "totalCents": c.total_cents, "received": c.received.isoformat() if c.received else None,
            "sha256": c.sha256[:16], "readable": c.readable, "payhoaTx": c.payhoa_tx}


def catalog(data_dir: Path, community: Any, roots: dict, *, include_payhoa: bool = True, ocr: Callable[[Path], str] | None = None,
            log: Callable[[str], None] | None = None) -> dict[str, Any]:
    say = log or (lambda _m: None)
    copies: list[DocumentCopy] = []
    for name, collect in (("utility store", lambda: utility_copies(data_dir, community, roots)),
                          ("vendor portals", lambda: portal_invoice_copies(data_dir, community)),
                          ("email", lambda: email_copies(data_dir, community, ocr=ocr)),
                          ("PayHOA attachments", (lambda: payhoa_copies(data_dir, community, roots)) if include_payhoa else (lambda: [])),
                          ("paper mail", lambda: paper_copies(data_dir, community))):
        found = collect()
        say(f"{name}: {len(found)} copies")
        copies.extend(found)
    documents = group(copies)
    priority = tuple(community.copy_priority())
    payments, returned, parent_of = _payments(data_dir)
    notes = audit_notes(data_dir)
    deposits_in = incoming(data_dir)
    by_id = {p["id"]: p for p in payments}
    vendor_of = {s.name: s.payhoa_vendor for s in community.senders() if s.payhoa_vendor}
    words_of = {s.name: tuple(s.words) for s in community.senders()}
    rows = []
    for doc in documents:
        chosen = best(doc, priority)
        pay = _payment(doc, payments, vendor_of, returned, parent_of, words_of, deposits_in)
        rows.append({"issuer": doc.issuer, "number": doc.number, "issued": doc.issued.isoformat() if doc.issued else None,
                     "totalCents": doc.total_cents, "stage": doc.stage.value if doc.stage else None,
                     "channels": [c.value for c in doc.channels], "copies": len(doc.copies),
                     "best": _copy_row(chosen), "others": [_copy_row(c) for c in doc.copies if c is not chosen],
                     "joins": [{"a": a, "b": b, "rule": rule.value} for a, b, rule in doc.joins], "payment": pay})
    # A proposal and the invoice that followed it: the invoice's payment is the proposal's.
    for i, (j, how) in fulfilments(documents).items():
        inv = rows[j]
        rows[i]["invoice"] = {"number": inv["number"], "issued": inv["issued"], "totalCents": inv["totalCents"], "how": how.value,
                              "title": inv["best"]["title"], "payment": inv["payment"]}
        inv["proposal"] = {"number": rows[i]["number"], "issued": rows[i]["issued"], "totalCents": rows[i]["totalCents"],
                           "stage": rows[i]["stage"], "title": rows[i]["best"]["title"]}
    # A proposal no invoice on file followed may still have been paid: PayHOA's payments to the vendor after it.
    for doc, row in zip(documents, rows):
        if doc.before_work and not row.get("invoice") and not row["payment"]:
            row.update(proposal_payments(doc, payments, vendor_of, words_of))
    rows.sort(key=lambda r: (r["issued"] or "", r["issuer"]), reverse=True)
    before = [r for r in rows if r["stage"] in {s.value for s in BEFORE_WORK}]
    by_channel: dict[str, int] = {}
    for c in copies:
        by_channel[c.channel.value] = by_channel.get(c.channel.value, 0) + 1
    multi = [r for r in rows if len(r["channels"]) > 1]
    result = {
        "found": bool(copies),
        "copies": len(copies),
        "documents": len(rows),
        "byChannel": by_channel,
        "acrossChannels": len(multi),
        "sameChannelDuplicates": sum(1 for r in rows if r["copies"] > len(r["channels"])),
        "withPayment": sum(1 for r in rows if r["payment"]),
        "proposals": len(before),
        "proposalsInvoiced": sum(1 for r in before if r.get("invoice")),
        # Paid on the estimate: a person attached the proposal itself to the payment as its backup.
        "proposalsAttachedToPayment": [{"issuer": r["issuer"], "issued": r["issued"], "totalCents": r["totalCents"],
                                        "title": r["best"]["title"], "txIds": r["payment"]["txIds"]}
                                       for r in before if r["payment"] and not r.get("invoice")],
        "proposalsPaidWithoutInvoice": [{"issuer": r["issuer"], "issued": r["issued"], "totalCents": r["totalCents"],
                                         "title": r["best"]["title"], "paid": r["paid"]} for r in before if r.get("paid")],
        "proposalsOpen": [{"issuer": r["issuer"], "issued": r["issued"], "totalCents": r["totalCents"], "stage": r["stage"],
                           "title": r["best"]["title"], "candidates": r.get("candidates") or []}
                          for r in before if not r.get("invoice") and not r.get("paid") and not r["payment"] and r["issuer"] and r["totalCents"]],
        "onSeveralPayments": [{"issuer": r["issuer"], "number": r["number"], "issued": r["issued"], "totalCents": r["totalCents"],
                               "txIds": r["payment"]["txIds"], "title": r["best"]["title"],
                               "explained": _explain(r["payment"]["txIds"], parent_of, notes, by_id, r["totalCents"],
                                                     credit=next_bill_credit(data_dir, r["best"]["account"] or next(
                                                         (o["account"] for o in r["others"] if o["account"]), ""),
                                                         _day(r["issued"]), r["totalCents"]),
                                                     title=r["best"]["title"], stage=r.get("stage")),
                               "notes": [n for t in r["payment"]["txIds"] for n in notes.get(t, [])][:4]}
                              for r in rows if r["payment"] and r["payment"].get("onSeveralPayments")],
        "priority": [c.value for c in priority],
        "rows": rows,
        "caveats": [
            "Every copy stays where it is; a document's best copy is only the one to read.",
            "A join records its rule; a document number read by OCR can be wrong, so a join on it is a reading.",
            "A payment matched by amount and date is a candidate; one a PayHOA copy hangs on is what a person attached.",
            "A proposal is not paid; the invoice that followed it is. A proposal with no invoice was declined, is still open, "
            "or was billed in parts; whether the board accepted it is in the minutes, not here.",
            "A proposal paid with no invoice on file matched a PayHOA payment to the vendor of the same amount after it; a "
            "candidate within 10%, or two payments that sum to it, is for a person to confirm.",
        ],
    }
    out = Path(data_dir) / "reports" / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def _money(cents: int | None) -> str:
    return f"${cents / 100:,.2f}" if cents else "-"


def catalog_lines(result: dict[str, Any], *, limit: int = 30, issuer: str = "", sections: set[str] | None = None,
                  since: str = "", only_unexplained: bool = False) -> list[str]:
    """The report; ``sections`` limits it to "proposals", "several", or "documents", ``since`` to documents issued on or
    after a date, ``only_unexplained`` the several-payments part to what no audit explains."""
    sections = sections or {"proposals", "several", "documents"}

    def recent(row: dict[str, Any]) -> bool:
        return not since or (row.get("issued") or "") >= since

    out = [f"{result['copies']} copies of {result['documents']} documents ("
           + ", ".join(f"{k} {n}" for k, n in sorted(result["byChannel"].items(), key=lambda kv: -kv[1])) + ")",
           f"  across channels: {result['acrossChannels']}; duplicates within one channel: {result['sameChannelDuplicates']}; "
           f"matched to a PayHOA payment: {result['withPayment']}",
           f"  proposals, estimates, and contracts: {result.get('proposals', 0)}; followed by their invoice: "
           f"{result.get('proposalsInvoiced', 0)}; paid with the proposal attached: {len(result.get('proposalsAttachedToPayment') or [])}; "
           f"paid with no invoice on file: {len(result.get('proposalsPaidWithoutInvoice') or [])}; "
           f"no invoice or payment found: {len(result.get('proposalsOpen') or [])}",
           "  best copy by: " + " > ".join(result["priority"]), ""]
    if "proposals" in sections and (result.get("proposalsPaidWithoutInvoice") or result.get("proposalsOpen")):
        out.append("Proposals with no invoice on file:")
        for p in [p for p in result.get("proposalsAttachedToPayment") or [] if recent(p)]:
            out.append(f"  {p['issued']} {p['issuer']} {_money(p['totalCents'])}: paid with the proposal attached "
                       f"(payment {', '.join(map(str, p['txIds']))}) - {p['title'][:50]}")
        for p in [p for p in result.get("proposalsPaidWithoutInvoice") or [] if recent(p)]:
            out.append(f"  {p['issued']} {p['issuer']} {_money(p['totalCents'])}: paid {p['paid']['date']} "
                       f"(payment {', '.join(map(str, p['paid']['txIds']))}, {p['paid']['how']}) - {p['title'][:50]}")
        for p in [p for p in result.get("proposalsOpen") or [] if recent(p)]:
            cands = "; ".join(f"{c['how']}: ${c['amountCents'] / 100:,.2f} on {c['date']} (payment {', '.join(map(str, c['txIds']))})"
                              for c in p["candidates"][:2])
            out.append(f"  {p['issued']} {p['issuer']} {_money(p['totalCents'])} [{p['stage']}]: "
                       + (f"candidates: {cands}" if cands else "no invoice or payment found") + f" - {p['title'][:50]}")
        out.append("")
    if "several" in sections and result.get("onSeveralPayments"):
        several = [d for d in result["onSeveralPayments"] if recent(d)]
        unexplained = [d for d in several if not d.get("explained")]
        out.append(f"Documents attached to more than one live payment ({len(several)}; {len(several) - len(unexplained)} explained by "
                   "jason's other audits): a double payment, a split, a wrong attachment, or a transfer that carries the invoice as backup")
        counts: dict[str, int] = {}
        for d in several:
            if d.get("explained"):
                why = d["explained"].split(" (")[0] if d["explained"].startswith("paid twice; the next bill") else d["explained"]
                counts[why] = counts.get(why, 0) + 1
        for why, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            if not only_unexplained:
                out.append(f"  {n} {why}")
        for d in sorted(unexplained, key=lambda d: -(d["totalCents"] or 0))[:15]:
            total = f"${d['totalCents'] / 100:,.2f}" if d["totalCents"] else "-"
            out.append(f"  not explained: {d['issued'] or '-'} {d['issuer'] or '-'} {d['number'] or ''} {total}: payments "
                       f"{', '.join(str(t) for t in d['txIds'])} ({d['title'][:40]})")
        out.append("")
    shown = 0
    for r in result["rows"] if "documents" in sections else []:
        if not recent(r):
            continue
        if issuer and issuer.lower() not in r["issuer"].lower():
            continue
        if not issuer and len(r["channels"]) < 2:
            continue
        total = f"${r['totalCents'] / 100:,.2f}" if r["totalCents"] else "-"
        pay = r["payment"]
        paid = f"; payment {pay['how']} {', '.join(str(t) for t in pay['txIds'][:3])}" if pay else "; no payment found"
        if r.get("invoice"):
            inv = r["invoice"]
            paid = f"; invoiced {inv['issued']} {inv['number'] or ''} ({inv['how'].split(',')[0]})" + (
                f", paid {', '.join(str(t) for t in inv['payment']['txIds'][:3])}" if inv.get("payment") else ", invoice not matched to a payment")
        stage = f" [{r['stage']}]" if r.get("stage") and r["stage"] != "invoice" else ""
        out.append(f"{r['issued'] or '-'} {r['issuer'] or '(no issuer)'} {r['number'] or ''} {total}{stage}: {' + '.join(r['channels'])}{paid}")
        out.append(f"  best: {r['best']['channel']} {r['best']['title'][:70]}")
        for j in r["joins"][:2]:
            out.append(f"  joined: {j['rule']}")
        shown += 1
        if shown >= limit:
            break
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["catalog", "catalog_lines", "utility_copies", "portal_invoice_copies", "email_copies", "payhoa_copies", "paper_copies"]
