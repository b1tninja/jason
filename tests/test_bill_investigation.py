"""The bill investigation (``jason.tasks.bill_investigation``): for one unapproved payment, what it is, what every store on
disk holds for its amount, and one recommended step. Made-up snapshot, tax catalog, mail, Gmail headers, library and
ledgers in tmp_path; nothing is reached, and a bank notice is never offered as the bill.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from jason.community.payees import PayeeClass, PayeeRule
from jason.tasks import bill_investigation as inv

NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
TAX = PayeeRule(PayeeClass.COUNTY_TAX, description_contains=("EXAMPLE COUNTY TAX",), note="the county tax collector's ACH line")


class Registry:
    def route(self, tx):
        return None


def tx(ident, amount, desc, day="2026-10-07", **kw):
    return {"id": ident, "amount": amount, "description": desc, "transactionDate": day, "approved": False,
            "attachments": [], **kw}


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.tasks.library.load", lambda d: [])
    monkeypatch.setattr("jason.tasks.mail.load_items", lambda d: {})
    monkeypatch.setattr("jason.tasks.invoice_review.vendor_ledgers", lambda d, c: {})
    return tmp_path


def snapshot(root, txs):
    p = root / "payhoa" / "transactions.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"syncedAt": "2026-10-09T02:10:00+00:00", "transactions": txs}), encoding="utf-8")


def community(*rules):
    return SimpleNamespace(payee_rules=lambda: rules, vendor_portals=lambda: ())


def tax_db(root, total):
    conn = sqlite3.connect(root / "tax.db")
    conn.execute("CREATE TABLE bills (apn TEXT, number TEXT, year INTEGER, total_cents INTEGER, payments_cents INTEGER, "
                 "balance_cents INTEGER, pdf_path TEXT, synced_at TEXT)")
    (root / "bills").mkdir(exist_ok=True)
    (root / "bills" / "b.pdf").write_bytes(b"%PDF")
    conn.execute("INSERT INTO bills VALUES ('123-456-789-0000', 'B1', 2026, ?, 0, ?, 'bills/b.pdf', '2026-10-01T00:00:00+00:00')",
                 (total, total))
    conn.commit()
    conn.close()


def gmail(root, subject, at="2026-10-07T10:00:00+00:00"):
    p = root / "gmail" / "correspondence.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"syncedAt": "2026-10-09T00:00:00+00:00",
                             "messages": [{"subject": subject, "at": at, "threadId": "t1"}]}), encoding="utf-8")


def card(root, ident=1, *, rules=(TAX,), private=False):
    return inv.investigate(root, community(*rules), Registry(), ident, now=NOW, private=private)


def test_a_missing_snapshot_or_transaction_is_a_miss_with_the_command(root):
    assert card(root)["found"] is False and card(root)["command"] == "jason invoices --fetch"
    snapshot(root, [tx(1, 100, "x")])
    assert card(root, 9)["found"] is False and "No transaction 9" in card(root, 9)["reason"]


def test_the_card_says_which_row_selected_the_payee_or_that_none_did(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR"), tx(2, 41200, "ACH SOMEONE")])
    one, two = card(root, 1), card(root, 2)
    assert one["routing"] == {"payeeClass": "county-tax", "source": None, "byRule": "the county tax collector's ACH line"}
    assert two["routing"]["payeeClass"] == "unknown" and two["routing"]["byRule"] is None
    assert two["tried"][0]["note"] == "no row selects this payee: propose one"
    assert "propose a payee row" in two["recommend"]["reason"]
    assert two["recommend"]["action"].startswith("Hold for a person")


def test_the_tax_catalog_finds_the_whole_bill_or_an_installment_and_reports_its_pdf(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    tax_db(root, 72714)                                          # twice the payment: this is one installment
    out = card(root)
    found = [c for c in out["candidates"] if c["kind"] == "tax-catalog"]
    assert len(found) == 1 and found[0]["why"] == "the amount is one installment (half the bill)"
    assert found[0]["hasPdf"] is True and "0000" in found[0]["label"] and "123-456" not in found[0]["label"]
    assert out["recommend"]["action"].startswith("Check tax bill B1")
    assert "lead until you attach it" in out["recommend"]["reason"]


def test_a_bank_notice_is_proof_of_payment_never_the_bill(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    gmail(root, "You sent $363.57 to Example County")
    out = card(root)
    notice = [c for c in out["candidates"] if c["kind"] == "bank-notice"]
    assert len(notice) == 1 and notice[0]["evidence"] == "payment-proof" and notice[0]["confidence"] == "lead"
    assert "proof of payment only" in out["recommend"]["reason"]
    assert out["recommend"]["command"] == "jason sync-tax"                      # the catalog was not read: read it first
    assert not [c for c in out["candidates"] if c["evidence"] == "document"]


def test_an_office_that_does_not_open_p2_sees_no_subject_sender_or_file(root, monkeypatch):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    gmail(root, "You sent $363.57 to Example County")
    monkeypatch.setattr("jason.tasks.mail.load_items", lambda d: {"m1": {
        "mailId": "m1", "kind": "property tax bill", "from": "Example County", "received": "2026-09-20",
        "text": "Amount due $363.57 second installment"}})
    held, shown = card(root), card(root, private=True)
    assert {c["label"] for c in held["candidates"]} == {"a scanned letter names this amount",
                                                        "a message whose subject names this amount"}
    assert not any("doc" in c or "link" in c for c in held["candidates"])
    assert any("Example County" in c["label"] for c in shown["candidates"])
    assert any(c.get("doc", {}).get("id") == "m1" for c in shown["candidates"])


def test_a_message_outside_the_notice_window_or_a_different_amount_is_not_a_lead(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    gmail(root, "You sent $363.57 to Example County", at="2026-08-01T00:00:00+00:00")
    assert not [c for c in card(root)["candidates"] if c["kind"] == "bank-notice"]
    gmail(root, "You sent $363.58 to Example County")
    assert not [c for c in card(root)["candidates"] if c["kind"] == "bank-notice"]
    gmail(root, "Invoice 1,363.57 for the pool")                              # 1,363.57 is not 363.57
    assert not [c for c in card(root)["candidates"] if c["kind"] == "bank-notice"]


def test_the_same_amount_already_attached_elsewhere_is_a_lead_and_never_the_recommendation(root):
    snapshot(root, [tx(1, 5000, "ACH SOMEONE"), tx(2, 5000, "ACH SOMEONE", day="2026-09-30", attachments=[{"id": 4}])])
    out = card(root)
    twin = [c for c in out["candidates"] if c.get("link") == "transaction:2"]
    assert len(twin) == 1 and twin[0]["confidence"] == "lead" and "not this payment's bill" in twin[0]["why"]
    assert not out["recommend"]["action"].startswith("Check")
    assert out["recommend"]["action"].startswith("Hold for a person")


def test_a_recurring_amount_shows_the_nearest_few_and_counts_the_rest(root):
    txs = [tx(1, 5000, "ACH SOMEONE")] + [tx(10 + n, 5000, "ACH SOMEONE", day=f"2026-0{n}-15", attachments=[{"id": n}])
                                           for n in range(1, 9)]
    snapshot(root, txs)
    out = card(root)
    assert len(out["candidates"]) == inv.MAX_PER_SOURCE
    note = next(t for t in out["tried"] if t["source"] == "other attachments of the same amount")["note"]
    assert "3 more of the same amount not shown" in note
    assert [c["link"] for c in out["candidates"]][0] == "transaction:18"      # the nearest in date: August 15


def test_the_library_and_a_vendors_ledger_are_searched_by_amount(root, monkeypatch):
    snapshot(root, [tx(1, 15000, "ACH EXAMPLE ALARM")])
    monkeypatch.setattr("jason.tasks.library.load", lambda d: [
        {"id": "drive-1", "name": "Invoice 77.pdf", "fields": {"amount_due": 150.0, "invoice_date": "2026-10-05"}},
        {"id": "drive-2", "name": "Other.pdf", "fields": {"amount_due": 151.0}},
        {"id": "drive-3", "name": "Secret.pdf", "confidential": True, "fields": {"amount_due": 150.0}}])
    ledger = SimpleNamespace(day=date(2026, 10, 6), amount_cents=15000, invoice_ids=("T9",), invoice_files=("x.pdf",))
    monkeypatch.setattr("jason.tasks.invoice_review.vendor_ledgers", lambda d, c: {"example-alarm": (object(), [ledger])})
    out = card(root, rules=(PayeeRule(PayeeClass.FIELD_VENDOR, description_contains=("EXAMPLE ALARM",)),))
    kinds = {c["kind"]: c for c in out["candidates"]}
    assert kinds["bill"]["label"] == "Invoice 77.pdf" and kinds["bill"]["confidence"] == "exact"
    assert kinds["portal-invoice"]["hasPdf"] is True and "invoice T9" in kinds["portal-invoice"]["why"]
    assert len(out["candidates"]) == 2 and "Secret" not in json.dumps(out)


def test_two_documents_that_fit_attach_neither(root, monkeypatch):
    snapshot(root, [tx(1, 15000, "ACH EXAMPLE")])
    monkeypatch.setattr("jason.tasks.library.load", lambda d: [
        {"id": f"drive-{n}", "name": f"Invoice {n}.pdf", "fields": {"amount_due": 150.0, "invoice_date": "2026-10-05"}}
        for n in (1, 2)])
    out = card(root)
    assert out["recommend"]["action"].startswith("Choose between the documents")
    assert "2 documents" in out["recommend"]["reason"]


def test_a_store_that_is_missing_is_listed_as_not_read_with_its_command(root):
    snapshot(root, [tx(1, 100, "x")])
    tried = {t["source"]: t for t in card(root)["tried"]}
    assert tried["the county tax catalog"]["result"] == "not read"
    assert "jason sync-tax" in tried["the county tax catalog"]["note"]
    assert tried["Gmail headers"]["result"] == "not read" and tried["paper mail"]["result"] == "not read"
    assert tried["the county's or a vendor's own site"]["result"] == "not read"


def test_the_outcomes_are_the_closed_set_a_person_records():
    assert inv.OUTCOMES == ("attached-bill", "attached-receipt-only", "not-our-bill", "waiting-for-mail", "escalated")


def test_a_payment_a_source_owns_is_sent_to_the_dry_run_not_to_a_guess(root):
    class Owned:
        def route(self, tx):
            return SimpleNamespace(name="smud")

    snapshot(root, [tx(1, 6129, "ACH ELECTRIC CO")])
    out = inv.investigate(root, community(), Owned(), 1, now=NOW)
    assert out["routing"]["source"] == "smud" and out["recommend"]["command"] == "jason sync-bills --dry-run"
    assert "smud owns this payment" in out["recommend"]["reason"]
