"""The Mailroom task: units resolve by address or id; preparing previews and mails nothing; sending logs the batch."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pymupdf

from jason.tasks.mailroom import prepare, resolve_units, send, status


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    with sqlite3.connect(data / "payhoa.db") as conn:
        conn.execute("CREATE TABLE units (org_id, id, label, balance, past_due_balance, address_line1, city, state, postal_code, raw_json, synced_at)")
        conn.executemany("INSERT INTO units (org_id, id, address_line1) VALUES (?, ?, ?)",
                         [(1, 101, "3024 MACON DR"), (1, 102, "5627 WHIMSICAL LN"), (2, 999, "3024 MACON DR")])
    return data


class FakeClient:
    def __init__(self):
        self.sent, self.batches = [], [{"id": 1, "totalCost": 145, "mailOptions": "{}"}]

    def mail_recipients(self, org_id, unit_ids, *, send_to, sending_invoice):
        return [{"unitIds": [u], "ownerId": u + 1000, "unitTitles": f"unit {u}", "address": "A\nB", "isIncluded": True} for u in unit_ids]

    def mail_preview(self, org_id, pdf, dest, *, unit_ids, owner_id, invoice):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"%PDF-preview")
        return Path(dest)

    def send_mail_pdf(self, org_id, pdf, **kw):
        self.sent.append(kw)
        self.batches.append({"id": 2, "totalCost": 290, "sentCount": 2, "mailOptions": json.dumps({"num_pages": 2})})
        return []

    def mail_pdf_batches(self, org_id):
        return list(self.batches)

    def mail_batch(self, org_id, batch_id):
        return [{"id": 7, "commActivityId": 70, "totalCost": 145, "status": "processing"},
                {"id": 8, "commActivityId": 80, "totalCost": 145, "status": "processing"}]

    def mail_invoice_batches(self, org_id):
        return []

    def mail_verify(self, org_id):
        return {"hasAddress": True, "hasPayment": True}

    def paper_mail_counts(self, org_id, *, start_date, end_date):
        return {"letters": 5}


def _letter(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    path = tmp_path / "notice.pdf"
    doc.save(path)
    return path


def test_units_resolve_by_address_or_id_within_the_organization(tmp_path: Path):
    data = _data(tmp_path)
    units, missing = resolve_units(data, ["3024 Macon Drive", "102", "1 Nowhere St"], org_id=1)
    assert [u.id for u in units] == [101, 102] and missing == ["1 Nowhere St"]
    assert [u.id for u in resolve_units(data, ["all"], org_id=1)[0]] == [101, 102]


def test_preparing_previews_and_mails_nothing_then_sending_logs_the_batch(tmp_path: Path, monkeypatch):
    import jason.tasks.mailroom as mailroom

    monkeypatch.setattr(mailroom, "READ_BACK", (0.0,))
    data, client = _data(tmp_path), FakeClient()
    prepared = prepare(client, 1, data, _letter(tmp_path), ["3024 Macon Dr", "5627 Whimsical Ln"])
    assert prepared.pages == 2 and prepared.unit_ids == [101, 102] and prepared.owner_ids == [1101, 1102]
    assert Path(prepared.preview).read_bytes() == b"%PDF-preview" and client.sent == []
    record = send(client, 1, data, prepared, double_sided=True)
    assert client.sent[0]["unit_ids"] == [101, 102] and client.sent[0]["owner_ids"] == [1101, 1102]
    assert client.sent[0]["num_pages"] == 2 and client.sent[0]["double_sided"] is True
    assert [b["id"] for b in record["batches"]] == [2] and record["batches"][0]["costCents"] == 290
    assert [x["communication"] for x in record["letters"]] == [70, 80] and record["guideCents"] == 145   # 3 billed pages
    assert json.loads((data / "mailroom" / "sent.jsonl").read_text(encoding="utf-8").splitlines()[0])["units"] == [101, 102]
    assert status(client, 1, data)["verify"]["hasPayment"]


def test_the_address_page_is_printed_and_billed_and_a_sixth_page_costs_postage():
    from jason.tasks.mailroom import printed

    four = printed(4, double_sided=True)              # the owner-information packet: 4 pages and the address page
    assert (four.pages, four.sheets, four.blank_back, four.cents, four.heavy) == (5, 3, True, 185, False)
    five = printed(5, double_sided=True)              # one page more fills the blank back and costs $2.45
    assert (five.pages, five.sheets, five.blank_back, five.cents, five.heavy) == (6, 3, False, 430, True)
    assert printed(4, double_sided=False).cents == 185                                 # two sides save paper, not money


def test_charged_letters_are_checked_against_the_pricing_guide():
    import json

    from jason.tasks.mailroom import charged_letters

    def letter(id, created, pages, cost, *, standard=True, color=False, cancelled=None, certified=False):
        return {"id": id, "createdAt": created, "totalCost": cost, "cancelledAt": cancelled,
                "mailOptions": json.dumps({"num_pages": pages, "is_standard_mail": standard, "is_colored_mail": color,
                                           "is_certified_mail": certified, "two_sided": True})}

    rows = charged_letters([
        letter(1, "2026-09-03 10:00:00", 3, 185, standard=False),            # first class: 125 + 3 x 20
        letter(2, "2026-07-14 10:00:00", 4, 305, standard=False, color=True),  # + 5 pages of color
        letter(3, "2025-11-30 10:00:00", 60, 1510),                          # billed before the address page was
        letter(4, "2026-10-01 20:53:09", 4, 185, cancelled="2026-10-01"),    # cancelled: not a charge
        letter(5, "2024-09-08 05:02:46", 5, 1550, standard=False, color=True, certified=True),
        letter(6, "2026-01-01 00:00:00", 2, 999),
    ])
    assert [(r.id, r.matches) for r in rows] == [(1, "guide"), (2, "guide"), (3, "guide, address page not billed"),
                                                 (6, "differs")]
