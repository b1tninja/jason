"""PayHOA's Mailroom: letters printed and mailed by USPS through Lob, read and, with a person's yes, sent.

``status`` reads whether the Mailroom can send and every mailing PayHOA has made (custom PDFs and invoices), with
cost, sent, failed, and cancelled counts. ``prepare`` resolves the units a letter goes to (by street address or
PayHOA unit id), asks PayHOA whom each letter reaches and at which address, and saves PayHOA's own preview of the
printed letter; nothing is mailed. ``send`` mails the prepared letter: it prints and mails real letters and charges
the association's account, so the CLI runs it only with ``--send --yes``, after the preview, and logs each sending
under ``data/mailroom``. A letter still processing can be cancelled (``cancel``).

jason never mails on its own initiative: a letter goes out only when a person asks for that letter, to those units.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAIL_DIR = "mailroom"
SEND_LOG = "sent.jsonl"
# Seconds to wait before each read of the new batch after a send.
READ_BACK = (1.0, 2.0, 4.0, 8.0)


def _address_key(text: str) -> str:
    """"3024 Macon Drive" and "3024 MACON DR" as one key."""
    t = re.sub(r"[^\w\s]", " ", (text or "").upper())
    t = re.sub(r"\bDRIVE\b", "DR", re.sub(r"\bLANE\b", "LN", t))
    return " ".join(t.split())


@dataclass(frozen=True)
class Unit:
    id: int
    address: str


def resolve_units(data_dir: Path, wanted: list[str], *, org_id: int | None = None) -> tuple[list[Unit], list[str]]:
    """The PayHOA units named by street address or unit id ("all" is every unit), from ``data/payhoa.db``; and the
    names that matched no unit (a miss stays a miss)."""
    db = Path(data_dir) / "payhoa.db"
    with sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT org_id, id, address_line1 FROM units").fetchall()
    units = [Unit(int(i), str(a or "")) for o, i, a in rows if org_id is None or int(o) == int(org_id)]
    if [w.strip().lower() for w in wanted] == ["all"]:
        return sorted(units, key=lambda u: u.address), []
    by_id = {str(u.id): u for u in units}
    by_address = {_address_key(u.address): u for u in units}
    found: list[Unit] = []
    missing: list[str] = []
    for name in (w.strip() for w in wanted if w.strip()):
        unit = by_id.get(name) or by_address.get(_address_key(name))
        if unit is None:
            missing.append(name)
        elif unit not in found:
            found.append(unit)
    return found, missing


def status(client: Any, org_id: int, data_dir: Path, *, year: int | None = None) -> dict[str, Any]:
    """Whether the Mailroom can send, and every mailing PayHOA has made; saved under ``data/mailroom/status.json``."""
    year = year or datetime.now().year
    pdf_batches = client.mail_pdf_batches(org_id)
    invoice_batches = client.mail_invoice_batches(org_id)
    result = {
        "read": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "verify": client.mail_verify(org_id),
        "counts": client.paper_mail_counts(org_id, start_date=f"{year}-01-01", end_date=f"{year}-12-31"),
        "pdfBatches": [_batch(b, "pdf") for b in pdf_batches],
        "invoiceBatches": [_batch(b, "invoice") for b in invoice_batches],
    }
    out = Path(data_dir) / MAIL_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def _batch(b: dict[str, Any], kind: str) -> dict[str, Any]:
    try:
        options = json.loads(b.get("mailOptions") or "{}")
    except (TypeError, json.JSONDecodeError):
        options = {}
    return {"id": b.get("id"), "kind": kind, "created": b.get("createdAt"), "costCents": int(b.get("totalCost") or 0),
            "sent": b.get("sentCount"), "failed": b.get("failedCount"), "cancelled": b.get("cancelledCount"),
            "certified": bool(options.get("is_certified_mail")), "color": bool(options.get("is_colored_mail")),
            "standard": bool(options.get("is_standard_mail")), "twoSided": bool(options.get("two_sided")),
            "pages": options.get("num_pages"), "sendTo": options.get("send_to"), "completed": b.get("batchCompleted"),
            "cancelledAt": b.get("batchCancelled")}


@dataclass
class Prepared:
    """A letter ready to mail: the file, its pages, the units, whom PayHOA says it reaches, and the preview."""

    pdf: str
    pages: int
    send_to: str
    units: list[dict[str, Any]]
    recipients: list[dict[str, Any]]
    preview: str
    missing: list[str] = field(default_factory=list)

    @property
    def owner_ids(self) -> list[int]:
        return sorted({int(r["ownerId"]) for r in self.recipients if r.get("isIncluded", True) and r.get("ownerId")})

    @property
    def unit_ids(self) -> list[int]:
        return [int(u["id"]) for u in self.units]


def page_count(pdf: Path) -> int:
    import pymupdf

    with pymupdf.open(str(pdf)) as doc:
        return doc.page_count


# PayHOA puts its own address page in front of a PDF letter (Lob's proof of the October 1, 2026 test letter showed it),
# prints and bills it; its preview leaves it out. Prices: ``payhoa.pricing``.
ADDRESS_PAGES = 1


@dataclass(frozen=True)
class Printed:
    pages: int           # as printed and billed, the address page first
    sheets: int
    blank_back: bool     # double-sided, the last sheet's back is empty (costs nothing: billing is by page)
    cents: int           # one letter, standard black and white, by PayHOA's pricing guide
    heavy: bool          # six pages or more: the extra postage


def printed(pages: int, *, double_sided: bool, first_class: bool = False, color: bool = False) -> Printed:
    """How a letter of ``pages`` pages prints and what it costs: the address page first, then the letter, one or two
    pages a sheet. Two-sided printing saves paper, not money."""
    from payhoa.pricing import PRICING

    total = pages + ADDRESS_PAGES
    sheets, blank = (total, False) if not double_sided else ((total + 1) // 2, total % 2 == 1)
    return Printed(total, sheets, blank, PRICING.letter(pages, first_class=first_class, color=color),
                   total >= PRICING.heavy_from)


# -- what a letter costs: PayHOA's pricing guide, checked against what it charged ---------------------------------------

PRICE_CHECK = "price-check.json"


@dataclass(frozen=True)
class Charged:
    """One letter PayHOA charged for, beside what its pricing guide says that letter costs."""

    id: int
    kind: str
    created: str
    pages: int
    first_class: bool
    color: bool
    two_sided: bool
    charged: int         # cents
    guide: int           # cents, with the address page billed
    guide_without_cover: int

    @property
    def matches(self) -> str:
        if self.charged == self.guide:
            return "guide"
        if self.charged == self.guide_without_cover:
            return "guide, address page not billed"
        return "differs"


def charged_letters(letters: list[dict[str, Any]], kind: str = "pdf") -> list[Charged]:
    """Every letter that was charged (``mail_letters`` rows, not cancelled, uncertified, unregistered, its pages known),
    with the guide's price for the same options."""
    from payhoa.pricing import PRICING

    rows = []
    for x in letters:
        try:
            options = json.loads(x.get("mailOptions") or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        pages, cost = options.get("num_pages"), int(x.get("totalCost") or 0)
        if not pages or not cost or x.get("cancelledAt") or options.get("is_certified_mail") \
                or options.get("is_registered_mail"):
            continue
        first, color = not options.get("is_standard_mail"), bool(options.get("is_colored_mail"))
        rows.append(Charged(int(x["id"]), kind, str(x.get("createdAt") or "")[:10], int(pages), first, color,
                            bool(options.get("two_sided")), cost,
                            PRICING.letter(int(pages), first_class=first, color=color),
                            PRICING.letter(int(pages), first_class=first, color=color, cover=False)))
    return rows


def price_check(client: Any, org_id: int, data_dir: Path, *, kinds: tuple[str, ...] = ("pdf", "violation")) -> dict[str, Any]:
    """Each kind's charged letters against the guide, grouped by option set, pages, and month; saved under
    ``data/mailroom/price-check.json``. Reads only."""
    groups: dict[tuple, dict[str, Any]] = {}
    for kind in kinds:
        for c in charged_letters(client.mail_letters(org_id, kind), kind):
            key = (c.kind, c.created[:7], c.pages, c.first_class, c.color, c.two_sided, c.charged)
            g = groups.setdefault(key, {"kind": c.kind, "month": c.created[:7], "pages": c.pages,
                                        "firstClass": c.first_class, "color": c.color, "twoSided": c.two_sided,
                                        "charged": c.charged, "guide": c.guide, "matches": c.matches, "letters": 0})
            g["letters"] += 1
    result = {"read": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "groups": sorted(groups.values(), key=lambda g: (g["month"], g["kind"], g["pages"]))}
    out = Path(data_dir) / MAIL_DIR / PRICE_CHECK
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def letter_history(client: Any, org_id: int, activity_id: int) -> list[dict[str, Any]]:
    """One letter's postal events, oldest first (``mail_events``)."""
    return sorted(client.mail_events(org_id, activity_id), key=lambda e: str(e.get("createdAt") or ""))


def prepare(client: Any, org_id: int, data_dir: Path, pdf: Path, wanted: list[str], *, send_to: str = "mailing",
            with_invoices: bool = False) -> Prepared:
    """Resolve the units, ask PayHOA whom each letter reaches, and save PayHOA's preview of the printed letter."""
    pdf = Path(pdf)
    if not pdf.is_file():
        raise FileNotFoundError(pdf)
    units, missing = resolve_units(data_dir, wanted, org_id=org_id)
    if not units:
        raise ValueError(f"no unit matched {', '.join(wanted)}")
    recipients = client.mail_recipients(org_id, [u.id for u in units], send_to=send_to, sending_invoice=with_invoices)
    out = Path(data_dir) / MAIL_DIR / "previews"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    first = next((r for r in recipients if r.get("isIncluded", True)), {})
    preview = client.mail_preview(org_id, pdf, out / f"{stamp}-{pdf.stem}.pdf", unit_ids=[units[0].id],
                                  owner_id=int(first.get("ownerId") or 0), invoice=with_invoices)
    return Prepared(str(pdf), page_count(pdf), send_to, [asdict(u) for u in units], recipients, str(preview), missing)


def send(client: Any, org_id: int, data_dir: Path, prepared: Prepared, *, double_sided: bool = False,
         with_invoices: bool = False, color: str = "bw", mail_class: str = "standard") -> dict[str, Any]:
    """Mail the prepared letter. This prints and mails real letters and charges the association; the CLI calls it only
    with a person's ``--yes``. The new batch is read back and the sending logged in ``data/mailroom/sent.jsonl``."""
    if not prepared.owner_ids:
        raise ValueError("PayHOA named no recipient for these units")
    before = {b.get("id") for b in client.mail_pdf_batches(org_id)}
    client.send_mail_pdf(org_id, Path(prepared.pdf), unit_ids=prepared.unit_ids, owner_ids=prepared.owner_ids,
                         num_pages=prepared.pages, send_to=prepared.send_to, mail_class=mail_class, color=color,
                         double_sided=double_sided, include_invoices=with_invoices)
    new: list[dict[str, Any]] = []
    for wait in READ_BACK:                            # PayHOA makes the batch a moment after the send returns
        time.sleep(wait)
        new = [b for b in client.mail_pdf_batches(org_id) if b.get("id") not in before]
        if new:
            break
    letters = [{"id": x.get("id"), "communication": x.get("commActivityId"), "costCents": x.get("totalCost"),
                "status": x.get("status")} for b in new for x in client.mail_batch(org_id, int(b["id"]))]
    run = printed(prepared.pages, double_sided=double_sided, first_class=mail_class != "standard", color=color != "bw")
    record = {"sent": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pdf": prepared.pdf, "pages": prepared.pages,
              "sendTo": prepared.send_to, "units": prepared.unit_ids, "ownerIds": prepared.owner_ids,
              "doubleSided": double_sided, "withInvoices": with_invoices, "color": color, "mailClass": mail_class,
              "guideCents": run.cents, "batches": [_batch(b, "pdf") for b in new], "letters": letters,
              "preview": prepared.preview}
    log = Path(data_dir) / MAIL_DIR / SEND_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


__all__ = ["ADDRESS_PAGES", "Charged", "Printed", "Unit", "Prepared", "charged_letters", "letter_history",
           "price_check", "resolve_units", "status", "prepare", "send", "page_count", "printed"]
