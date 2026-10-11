"""A made-up Mailroom world for tests: two units on Example Rd, owners with made-up names, a PDF letter, and a fake PayHOA
client that records what it is asked to mail. Nothing here is an association's; nothing reaches PayHOA."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pymupdf

import jason.tasks.mailroom as mailroom

ORG = 1
ADDRESSES = {101: "123 Example Rd", 102: "125 Example Rd"}
OWNERS = {101: ("A. Owner", 1101), 102: ("B. Owner", 1102)}


def make_data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    with sqlite3.connect(data / "payhoa.db") as conn:
        conn.execute("CREATE TABLE units (org_id, id, label, balance, past_due_balance, address_line1, city, state, "
                     "postal_code, raw_json, synced_at)")
        conn.executemany("INSERT INTO units (org_id, id, address_line1) VALUES (?, ?, ?)",
                         [(ORG, i, a) for i, a in ADDRESSES.items()])
    return data


def make_letter(tmp_path: Path, pages: int = 2, name: str = "") -> Path:
    """A PDF of ``pages`` blank pages. Made once for a name: pymupdf saves different bytes each time, and a fingerprint
    holds the file's sha256."""
    path = tmp_path / (name or f"notice-{pages}.pdf")
    if not path.exists():
        doc = pymupdf.open()
        for _ in range(pages):
            doc.new_page()
        doc.save(path)
    return path


class FakeMailClient:
    """PayHOA's Mailroom as far as jason asks. ``rows`` are the recipient rows it answers; change them to move an owner."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.batches = [{"id": 1, "totalCost": 145, "mailOptions": "{}"}]
        self.rows = {u: {"unitIds": [u], "ownerId": OWNERS[u][1], "unitTitles": ADDRESSES[u], "name": OWNERS[u][0],
                         "address": f"{ADDRESSES[u]}\nExample City, CA 95000", "isIncluded": True, "isDuplicate": False}
                     for u in ADDRESSES}
        self.recipient_calls = 0

    def mail_recipients(self, org_id, unit_ids, *, send_to, sending_invoice):
        self.recipient_calls += 1
        return [dict(self.rows[u]) for u in unit_ids if u in self.rows]

    def mail_preview(self, org_id, pdf, dest, *, unit_ids, owner_id, invoice):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"%PDF-preview")
        return Path(dest)

    def send_mail_pdf(self, org_id, pdf, **kw):
        self.sent.append(kw)
        self.batches.append({"id": 2, "totalCost": 290, "sentCount": len(kw["owner_ids"]),
                             "mailOptions": json.dumps({"num_pages": kw["num_pages"]})})
        return []

    def mail_pdf_batches(self, org_id):
        return list(self.batches)

    def mail_batch(self, org_id, batch_id):
        return [{"id": 7, "commActivityId": 70, "totalCost": 145, "status": "processing"},
                {"id": 8, "commActivityId": 80, "totalCost": 145, "status": "processing"}]


def options(**kw) -> mailroom.Options:
    return mailroom.Options.build(kw.pop("mail_class", "first-class"), **kw)


def kept(tmp_path: Path, client: FakeMailClient | None = None, *, pages: int = 2, wanted=("123 Example Rd", "125 Example Rd"),
         by: str = "A. Manager", notice: str = "", pdf: Path | None = None, **opts):
    """Prepare a letter the way ``jason mailroom --pdf`` does and keep the preview record. Returns the data folder, the
    client, the prepared letter, and the saved record."""
    data = make_data(tmp_path) if not (tmp_path / "data").exists() else tmp_path / "data"
    client = client or FakeMailClient()
    pdf = pdf or make_letter(tmp_path, pages)
    prepared = mailroom.prepare(client, ORG, data, pdf, list(wanted), send_to=opts.get("send_to", "mailing"),
                                with_invoices=opts.get("with_invoices", False))
    facts, record, path = mailroom.keep_preview(data, prepared, options(**opts), named=list(wanted), by=by, notice=notice)
    return SimpleNamespace(data=data, client=client, prepared=prepared, record=record, path=path, facts=facts, pdf=pdf)

