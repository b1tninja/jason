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

import hashlib
import json
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

MAIL_DIR = "mailroom"
SEND_LOG = "sent.jsonl"
PREVIEW_DIR = "previews"
# A saved preview older than this is stale: PayHOA's recipients, an owner's address, or the letter itself may have
# moved since a person read it (docs/console/screens/mailroom.md, "States"). The approvals kind holds the same limit.
PREVIEW_MAX_AGE_HOURS = 24
FINGERPRINT_SHOWN = 12                    # hex characters of a fingerprint a person reads and types
MIN_EXPECT = 8                            # the fewest a ``--expect`` may give
PREVIEW_NOT_A_PROMISE = ("a preview is not a promise: this send asks PayHOA for the recipients again. Add --expect "
                         "FINGERPRINT (shown with the preview) to refuse a send that differs from the one you read")
# Seconds to wait before each read of the new batch after a send.
READ_BACK = (1.0, 2.0, 4.0, 8.0)

# PayHOA's Mailroom options, read from its own Mail Options step (captured 2026-10-11). ``mailClass`` is "standard"
# (delivers in 2-3 weeks) or "first class" (5-8 business days); tracking is "certified" or "registered", and PayHOA
# offers it only with first class; an invoice goes only first class and single-sided.
MAIL_CLASSES = {"standard": "standard", "first-class": "first class", "first class": "first class"}
TRACKING = ("certified", "registered")
STANDARD_NOTE = ("standard class is not one of the delivery methods CIV 4040(a)(2) lists (first-class mail, registered or "
                 "certified mail, express mail, overnight delivery): where a provision requires individual delivery and the "
                 "member has given no valid method, use --mail-class first-class (jason cite CIV 4040)")


def default_mail_class(notice: str = "") -> str:
    """The class a letter goes when none is asked for: first class for a notice (``--notice KEY``: the letter is kept as
    the notice's record), standard for any other letter. A person may still ask for standard."""
    return "first-class" if notice else "standard"


def check_options(mail_class: str, *, tracking: str = "", with_invoices: bool = False, double_sided: bool = False) -> str:
    """The PayHOA ``mailClass`` for the options asked, or a ``ValueError`` saying which rule PayHOA's own page applies.
    Tracking needs first class; an invoice needs first class and single-sided printing."""
    if mail_class not in MAIL_CLASSES:
        raise ValueError(f"mail class is one of: {', '.join(sorted({'standard', 'first-class'}))}")
    if tracking and tracking not in TRACKING:
        raise ValueError(f"tracking is one of: {', '.join(TRACKING)}")
    value = MAIL_CLASSES[mail_class]
    if tracking and value == "standard":
        raise ValueError(f"{tracking} mail needs first class (PayHOA offers tracking only with first class)")
    if with_invoices and value == "standard":
        raise ValueError("an invoice can only be sent by first class (PayHOA)")
    if with_invoices and double_sided:
        raise ValueError("an invoice cannot be sent double-sided (PayHOA)")
    return value


@dataclass(frozen=True)
class Options:
    """What a letter is sent with: PayHOA's own values (``mail_class`` is "standard" or "first class", ``color`` "bw" or
    "color"). These are part of a letter's fingerprint."""

    send_to: str = "mailing"
    with_invoices: bool = False
    double_sided: bool = False
    mail_class: str = "standard"
    tracking: str = ""
    color: str = "bw"

    @classmethod
    def build(cls, mail_class: str, *, send_to: str = "mailing", with_invoices: bool = False, double_sided: bool = False,
              tracking: str = "", color: str = "bw") -> "Options":
        """The options asked, after PayHOA's own rules (``check_options``); a ``ValueError`` says which one refuses."""
        value = check_options(mail_class, tracking=tracking, with_invoices=with_invoices, double_sided=double_sided)
        return cls(send_to, with_invoices, double_sided, value, tracking, color)

    @property
    def first_class(self) -> bool:
        return self.mail_class != "standard"

    def as_dict(self) -> dict[str, Any]:
        return {"sendTo": self.send_to, "withInvoices": self.with_invoices, "doubleSided": self.double_sided,
                "mailClass": self.mail_class, "tracking": self.tracking, "color": self.color}

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "Options":
        return cls(str(row.get("sendTo") or "mailing"), bool(row.get("withInvoices")), bool(row.get("doubleSided")),
                   str(row.get("mailClass") or "standard"), str(row.get("tracking") or ""), str(row.get("color") or "bw"))


def _address_key(text: str) -> str:
    """"123 Main Street" and "123 MAIN ST" as one key."""
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


def printed(pages: int, *, double_sided: bool, first_class: bool = False, color: bool = False,
            tracking: str = "") -> Printed:
    """How a letter of ``pages`` pages prints and what it costs: the address page first, then the letter, one or two
    pages a sheet. Two-sided printing saves paper, not money."""
    from payhoa.pricing import PRICING

    total = pages + ADDRESS_PAGES
    sheets, blank = (total, False) if not double_sided else ((total + 1) // 2, total % 2 == 1)
    return Printed(total, sheets, blank, PRICING.letter(pages, first_class=first_class, color=color,
                                                         certified=tracking == "certified", registered=tracking == "registered"),
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


# -- the preview record and the fingerprint ------------------------------------------------------------------------------
#
# A preview is not a promise: ``send`` asks PayHOA for the recipients again. The preview record is what a person read,
# kept; its fingerprint is a hash over the letter (its sha256), the options, the units, the owners PayHOA names, the
# recipients' addresses and names (inside the hash only), and the total. A later send, or an approval, is checked
# against it. The record holds no name and no address: those stay in PayHOA.

class FingerprintMismatch(ValueError):
    """The letter about to go is not the one that was previewed. Nothing was mailed."""


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def shown(fingerprint: str) -> str:
    """The part of a fingerprint a person reads and types."""
    return fingerprint[:FINGERPRINT_SHOWN]


def recipients_digest(recipients: list[dict[str, Any]]) -> str:
    """One hash over each recipient row: owner, units, name, address, and PayHOA's two flags. A name or an address that
    changes changes it; neither is kept anywhere."""
    rows = [[int(r.get("ownerId") or 0), sorted(int(u) for u in r.get("unitIds") or ()),
             _address_key(str(r.get("name") or "")), _address_key(str(r.get("address") or "")),
             bool(r.get("isIncluded", True)), bool(r.get("isDuplicate"))] for r in recipients]
    return _digest(sorted(rows, key=json.dumps))


def resolution(row: dict[str, Any], send_to: str, unit_keys: dict[int, str]) -> str:
    """How a recipient's address was resolved, in a word and never the address: none, the unit's, the owner's mailing
    address, or a mailing address that is the unit's (PayHOA mails at the unit when an owner has none)."""
    address = str(row.get("address") or "")
    if not address.strip():
        return "no address"
    if send_to == "unit":
        return "unit address"
    first = _address_key(address.splitlines()[0])
    own = {unit_keys.get(int(u)) for u in row.get("unitIds") or ()}
    return "mailing = unit address" if first and first in own else "mailing address"


def fingerprint(*, pdf_sha: str, options: Options, unit_ids: list[int], owner_ids: list[int], recipients: str,
                total_cents: int) -> str:
    """The sha256 over the letter's sha256, the options, the sorted unit ids and included owner ids, the recipients'
    digest, and the total in cents."""
    return _digest({"pdf": pdf_sha, "options": options.as_dict(), "units": sorted(int(u) for u in unit_ids),
                    "owners": sorted(int(o) for o in owner_ids), "recipients": recipients, "totalCents": int(total_cents)})


def describe(pdf: Path, pages: int, options: Options, units: list[dict[str, Any]], recipients: list[dict[str, Any]],
             *, pdf_sha: str | None = None) -> dict[str, Any]:
    """What a letter is, as a preview record keeps it (no name, no address) and its fingerprint. Reads the file for its
    sha256 unless ``pdf_sha`` is given; a missing file has sha256 "" (the letter is gone)."""
    pdf = Path(pdf)
    sha = pdf_sha if pdf_sha is not None else (sha256_file(pdf) if pdf.is_file() else "")
    included = [r for r in recipients if r.get("isIncluded", True)]
    owner_ids = sorted({int(r["ownerId"]) for r in included if r.get("ownerId")})
    run = printed(pages, double_sided=options.double_sided, first_class=options.first_class,
                  color=options.color != "bw", tracking=options.tracking)
    total = run.cents * len(included)
    unit_keys = {int(u["id"]): _address_key(str(u.get("address") or "")) for u in units}
    unit_ids = [int(u["id"]) for u in units]
    digest = recipients_digest(recipients)
    return {
        "pdf": {"name": pdf.name, "path": str(pdf), "sha256": sha, "pages": pages},
        "options": options.as_dict(),
        "units": [{"id": int(u["id"]), "title": str(u.get("address") or "")} for u in units],
        "recipients": [{"ownerId": int(r.get("ownerId") or 0), "unitTitles": str(r.get("unitTitles") or ""),
                        "resolved": resolution(r, options.send_to, unit_keys),
                        "isIncluded": bool(r.get("isIncluded", True)), "isDuplicate": bool(r.get("isDuplicate"))}
                       for r in recipients],
        "printed": {"pages": run.pages, "sheets": run.sheets, "blankBack": run.blank_back, "heavy": run.heavy,
                    "centsEach": run.cents},
        "lettersExpected": len(included), "totalCents": total, "recipientsDigest": digest,
        "fingerprint": fingerprint(pdf_sha=sha, options=options, unit_ids=unit_ids, owner_ids=owner_ids,
                                   recipients=digest, total_cents=total),
    }


def new_preview(facts: dict[str, Any], *, proof: str = "", named: list[str] | None = None,
                missing: list[str] | None = None, by: str = "", notice: str = "", pid: str = "",
                now: datetime | None = None) -> dict[str, Any]:
    """The preview record: ``describe``'s facts with who read it, when, what was typed, and the notice it serves."""
    now = now or datetime.now(timezone.utc)
    return {"id": pid, "read": now.isoformat(timespec="seconds"), "by": by, **facts, "named": list(named or ()),
            "missing": list(missing or ()), "notice": notice, "proof": proof}


def keep_preview(data_dir: Path, prepared: Prepared, options: Options, *, named: list[str] | None = None, by: str = "",
                 notice: str = "") -> tuple[dict[str, Any], dict[str, Any], Path | None]:
    """What ``jason mailroom --pdf`` reads, kept: the letter's facts (``describe``), the preview record built from them,
    and the path it was saved to (beside PayHOA's proof; None when there is no proof to sit beside)."""
    facts = describe(Path(prepared.pdf), prepared.pages, options, prepared.units, prepared.recipients)
    record = new_preview(facts, named=named, missing=prepared.missing, by=by, notice=notice)
    saved = save_preview(data_dir, record, prepared.preview) if prepared.preview else None
    return facts, record, saved


def previews_dir(data_dir: Path) -> Path:
    return Path(data_dir) / MAIL_DIR / PREVIEW_DIR


def save_preview(data_dir: Path, record: dict[str, Any], proof: str | Path) -> Path:
    """Save ``record`` beside PayHOA's proof PDF (``previews/STAMP-STEM.json``); its id is that name."""
    path = Path(proof).with_suffix(".json")
    record["id"], record["proof"] = path.stem, Path(proof).name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return path


def saved_previews(data_dir: Path) -> list[dict[str, Any]]:
    """Every saved preview, newest first."""
    rows = []
    for p in sorted(previews_dir(data_dir).glob("*.json"), reverse=True):
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(row, dict) and row.get("fingerprint"):
            row.setdefault("id", p.stem)
            rows.append(row)
    return rows


def load_preview(data_dir: Path, ref: str) -> dict[str, Any]:
    """A saved preview by its id, a unique prefix of the id, or the first characters (four or more) of its fingerprint.
    ``KeyError`` when none matches; ``ValueError`` when several do."""
    ref = (ref or "").strip().removesuffix(".json")
    rows = saved_previews(data_dir)
    exact = [r for r in rows if r["id"] == ref]
    found = exact or [r for r in rows if r["id"].startswith(ref) or (len(ref) >= 4 and r["fingerprint"].startswith(ref.lower()))]
    if not found:
        raise KeyError(f"no saved preview {ref} (jason mailroom --pdf FILE --units UNITS saves one)")
    if len(found) > 1:
        raise ValueError(f"{ref} names {len(found)} saved previews: " + ", ".join(r["id"] for r in found[:5]))
    return found[0]


def _ids(rows: list[dict[str, Any]], key: str, *, included: bool = False) -> set[int]:
    return {int(r[key]) for r in rows if r.get(key) and (not included or r.get("isIncluded", True))}


def _money(cents: int) -> str:
    return f"${int(cents) / 100:,.2f}"


def changes(saved: dict[str, Any], now: dict[str, Any]) -> list[str]:
    """What differs between a saved preview and the letter as it would go now, each in words (ids and counts, never a
    name or an address). Empty when the fingerprints match."""
    if saved.get("fingerprint") == now.get("fingerprint"):
        return []
    out: list[str] = []
    then, here = saved.get("pdf") or {}, now.get("pdf") or {}
    if not here.get("sha256"):
        out.append("the PDF is gone from " + str(here.get("path") or then.get("path") or "its folder"))
    elif then.get("sha256") != here.get("sha256"):
        out.append(f"the PDF changed (sha256 {str(then.get('sha256'))[:8]} -> {str(here.get('sha256'))[:8]})")
    for key, label in (("sendTo", "send to"), ("withInvoices", "invoices"), ("doubleSided", "double-sided"),
                       ("mailClass", "mail class"), ("tracking", "tracking"), ("color", "color")):
        a, b = (saved.get("options") or {}).get(key), (now.get("options") or {}).get(key)
        if a != b:
            out.append(f"{label} changed ({a or 'none'} -> {b or 'none'})")
    a, b = _ids(saved.get("units") or [], "id"), _ids(now.get("units") or [], "id")
    if a != b:
        out.append(f"the units changed ({len(b - a)} added, {len(a - b)} no longer found: "
                   + ", ".join(str(i) for i in sorted(a ^ b)[:10]) + ")")
    a, b = _ids(saved.get("recipients") or [], "ownerId", included=True), _ids(now.get("recipients") or [], "ownerId", included=True)
    if a != b:
        out.append(f"PayHOA now names different owners ({len(b - a)} added, {len(a - b)} removed: owner ids "
                   + ", ".join(str(i) for i in sorted(a ^ b)[:10]) + ")")
    elif saved.get("recipientsDigest") != now.get("recipientsDigest"):
        out.append("an address, a name, or a flag PayHOA holds for a recipient changed (the same owners)")
    if saved.get("totalCents") != now.get("totalCents"):
        out.append(f"the cost changed ({_money(saved.get('totalCents') or 0)} -> {_money(now.get('totalCents') or 0)}, "
                   f"{saved.get('lettersExpected')} -> {now.get('lettersExpected')} letters)")
    return out or ["the fingerprint differs"]


def age_hours(record: dict[str, Any], now: datetime | None = None) -> float | None:
    try:
        read = datetime.fromisoformat(str(record.get("read")))
    except ValueError:
        return None
    return ((now or datetime.now(timezone.utc)) - read).total_seconds() / 3600


def stale_reasons(saved: dict[str, Any], now_facts: dict[str, Any], *, now: datetime | None = None,
                  check_age: bool = True) -> list[str]:
    """Why a saved preview is no longer the letter that would go: what changed (``changes``) and its age. Empty means
    current. A preview is a read of PayHOA at a time; it is not a promise."""
    out = changes(saved, now_facts)
    hours = age_hours(saved, now) if check_age else None
    if hours is None and check_age:
        out.append("its read time is not recorded")
    elif hours is not None and hours > PREVIEW_MAX_AGE_HOURS:
        out.append(f"read {hours:.0f} hours ago, more than the {PREVIEW_MAX_AGE_HOURS}-hour limit")
    return out


def live_facts(client: Any, org_id: int, data_dir: Path, record: dict[str, Any]) -> tuple[dict[str, Any], Prepared]:
    """The saved preview's letter as it would go now: its file read again, its units found again in the units table, and
    PayHOA asked whom it reaches. Reads only (no proof is drawn, nothing is mailed)."""
    options = Options.from_dict(record.get("options") or {})
    pdf = Path((record.get("pdf") or {}).get("path") or "")
    units, missing = resolve_units(data_dir, [str(u["id"]) for u in record.get("units") or ()], org_id=org_id)
    recipients = client.mail_recipients(org_id, [u.id for u in units], send_to=options.send_to,
                                        sending_invoice=options.with_invoices) if units else []
    pages = page_count(pdf) if pdf.is_file() else int((record.get("pdf") or {}).get("pages") or 0)
    unit_rows = [asdict(u) for u in units]
    facts = describe(pdf, pages, options, unit_rows, recipients)
    proof = previews_dir(data_dir) / str(record.get("proof") or "") if record.get("proof") else None
    return facts, Prepared(str(pdf), pages, options.send_to, unit_rows, recipients, str(proof or ""), missing)


def find_by_fingerprint(data_dir: Path, typed: str) -> dict[str, Any] | None:
    typed = typed.strip().lower()
    return next((r for r in saved_previews(data_dir) if r["fingerprint"].startswith(typed)), None)


def verify_expect(data_dir: Path, facts: dict[str, Any], expect: str) -> None:
    """Refuse (``FingerprintMismatch``) unless the letter as it would go has the fingerprint the person typed (its first
    eight or more hex characters). The refusal names what changed when a saved preview carries the typed fingerprint."""
    typed = (expect or "").strip().lower()
    if len(typed) < MIN_EXPECT or any(c not in "0123456789abcdef" for c in typed):
        raise ValueError(f"--expect is the first {MIN_EXPECT} or more hex characters of the preview's fingerprint")
    if facts["fingerprint"].startswith(typed):
        return
    saved = find_by_fingerprint(data_dir, typed)
    what = ("; ".join(changes(saved, facts)) if saved else
            f"no saved preview carries {typed}, so what changed cannot be named; read the preview again")
    raise FingerprintMismatch(f"this letter is not the one previewed (expected {typed[:FINGERPRINT_SHOWN]}, it would "
                              f"go as {shown(facts['fingerprint'])}): {what}")


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
    n = 1
    while (out / f"{stamp}-{pdf.stem}.pdf").exists() or (out / f"{stamp}-{pdf.stem}.json").exists():
        n += 1                                        # two reads in one second are two previews, never one overwritten
        stamp = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{n}"
    first = next((r for r in recipients if r.get("isIncluded", True)), {})
    preview = client.mail_preview(org_id, pdf, out / f"{stamp}-{pdf.stem}.pdf", unit_ids=[units[0].id],
                                  owner_id=int(first.get("ownerId") or 0), invoice=with_invoices)
    return Prepared(str(pdf), page_count(pdf), send_to, [asdict(u) for u in units], recipients, str(preview), missing)


def send(client: Any, org_id: int, data_dir: Path, prepared: Prepared, *, double_sided: bool = False,
         with_invoices: bool = False, color: str = "bw", mail_class: str = "standard", tracking: str = "",
         by: str = "", expect: str = "", approval: str = "", preview_id: str = "") -> dict[str, Any]:
    """Mail the prepared letter. This prints and mails real letters and charges the association; the CLI calls it only
    with a person's ``--yes``. The new batch is read back and the sending logged in ``data/mailroom/sent.jsonl``, with
    the letter's fingerprint. With ``expect`` (a preview's fingerprint) the letter as it would go now is checked first,
    and a different one is refused (``FingerprintMismatch``) with nothing mailed. A read-back that fails does not lose
    the log line: the letters are mailed, so the line says the batch was not read."""
    if not prepared.owner_ids:
        raise ValueError("PayHOA named no recipient for these units")
    mail_class = check_options(mail_class, tracking=tracking, with_invoices=with_invoices, double_sided=double_sided)
    facts = describe(Path(prepared.pdf), prepared.pages,
                     Options(prepared.send_to, with_invoices, double_sided, mail_class, tracking, color),
                     prepared.units, prepared.recipients)
    if expect:
        verify_expect(data_dir, facts, expect)
    before = {b.get("id") for b in client.mail_pdf_batches(org_id)}
    client.send_mail_pdf(org_id, Path(prepared.pdf), unit_ids=prepared.unit_ids, owner_ids=prepared.owner_ids,
                         num_pages=prepared.pages, send_to=prepared.send_to, mail_class=mail_class, color=color,
                         double_sided=double_sided, include_invoices=with_invoices, tracking=tracking)
    new: list[dict[str, Any]] = []
    letters: list[dict[str, Any]] = []
    read_error = ""
    try:
        for wait in READ_BACK:                        # PayHOA makes the batch a moment after the send returns
            time.sleep(wait)
            new = [b for b in client.mail_pdf_batches(org_id) if b.get("id") not in before]
            if new:
                break
        letters = [{"id": x.get("id"), "communication": x.get("commActivityId"), "costCents": x.get("totalCost"),
                    "status": x.get("status")} for b in new for x in client.mail_batch(org_id, int(b["id"]))]
    except Exception as exc:  # noqa: BLE001 - the letters are mailed; the log still gets its line
        read_error = f"{type(exc).__name__}: {exc}"
    run = printed(prepared.pages, double_sided=double_sided, first_class=mail_class != "standard", color=color != "bw",
                  tracking=tracking)
    record = {"sent": datetime.now(timezone.utc).isoformat(timespec="seconds"), "pdf": prepared.pdf, "pages": prepared.pages,
              "sendTo": prepared.send_to, "units": prepared.unit_ids, "ownerIds": prepared.owner_ids,
              "doubleSided": double_sided, "withInvoices": with_invoices, "color": color, "mailClass": mail_class,
              "tracking": tracking, "by": by, "fingerprint": facts["fingerprint"],
              "guideCents": run.cents, "batches": [_batch(b, "pdf") for b in new], "letters": letters,
              "preview": prepared.preview}
    if preview_id:
        record["previewId"] = preview_id
    if approval:
        record["approval"] = approval
    if read_error:
        record["readBackError"] = read_error
    log = Path(data_dir) / MAIL_DIR / SEND_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return record


def keep_notice(data_dir: Path, key: str, prepared: Prepared, record: dict[str, Any], *, by: str = "") -> dict[str, Any]:
    """A mailed notice kept in ``data/notices/KEY/`` (``jason.tasks.notice_text``): the PDF as mailed and whom it went
    to (unit and owner ids, and the count; no addresses). Called only after ``send``."""
    from jason.tasks import notice_text

    batches = ", ".join(str(b.get("id")) for b in record.get("batches") or ()) or "(not listed yet)"
    plan = {"notice": "", "unitIds": prepared.unit_ids, "emailMembershipIds": [],
            "mail": [{"ownerId": o} for o in prepared.owner_ids],
            "letters": len([r for r in prepared.recipients if r.get("isIncluded", True)]), "secondary": [],
            "sendTo": prepared.send_to, "source": "jason mailroom --pdf --send (PayHOA's recipients for the units)"}
    return notice_text.keep(data_dir, key, kind="letter (PayHOA's Mailroom)",
                            state=f"mailed through PayHOA's Mailroom, batch {batches}, {prepared.pages} pages "
                                  f"(PayHOA adds its address page)", body=Path(prepared.pdf), body_name="letter.pdf",
                            recipients=plan, batch=batches, by=by, source=str(prepared.pdf))


__all__ = ["ADDRESS_PAGES", "FINGERPRINT_SHOWN", "FingerprintMismatch", "MAIL_CLASSES", "MIN_EXPECT", "Options",
           "PREVIEW_MAX_AGE_HOURS", "PREVIEW_NOT_A_PROMISE", "STANDARD_NOTE", "default_mail_class", "TRACKING",
           "check_options", "Charged", "Printed", "Unit", "Prepared", "age_hours", "changes", "charged_letters",
           "describe", "find_by_fingerprint", "fingerprint", "keep_notice", "keep_preview", "letter_history", "live_facts",
           "load_preview", "new_preview", "previews_dir", "price_check", "recipients_digest", "resolution",
           "resolve_units", "save_preview", "saved_previews", "sha256_file", "shown", "stale_reasons", "status",
           "prepare", "send", "page_count", "printed", "verify_expect"]
