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


# --- the county's payment receipts (data/tax/receipts.json) --------------------------------------------------------

def receipts(root, *rows, now=datetime(2026, 10, 9, 8, tzinfo=timezone.utc)):
    from jason.tasks import tax_receipts as tr

    docs = []
    for conf, posted, amounts, four in rows:
        docs.append(tr.parse_receipt({
            "confirmationNumber": conf, "postedDatetime": posted,
            "tender": {"type": "bank", "name": "Example Bank - Operating", "summary": f"Checking ending in {four}"},
            "billing": {"name": "Example Association", "email": "billing@example.test"},
            "transactions": [{"fee": "0.00", "items": [
                {"amount": a, "path": "/Example/v0/items/x?installment=second-installment",
                 "details": {"display_name": "2026 Secured Annual Bill #B1", "external_id": "B1",
                             "description": "Parcel #123-456-789-0000\nSitus Address: 123 Main St",
                             "custom_parameters": {"tax_rate_year": "2026"}}} for a in amounts]}]}))
    tr.import_receipts(root, docs, by="Pat", now=now)


def accounts(*suffixes):
    return SimpleNamespace(payee_rules=lambda: (TAX,), vendor_portals=lambda: (),
                           bank_accounts=lambda: tuple(SimpleNamespace(suffix=s) for s in suffixes))


def test_a_receipt_for_the_amount_inside_the_window_is_exact_proof_and_names_the_bill(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    tax_db(root, 72714)
    receipts(root, ("W0000000001", "2026-10-06T15:00:00Z", ("363.57",), "1234"))
    out = card(root)
    proof = [c for c in out["candidates"] if c["kind"] == "receipt"]
    assert len(proof) == 1 and proof[0]["confidence"] == "exact" and proof[0]["evidence"] == "payment-proof"
    assert proof[0]["label"] == "county receipt W0000000001" and proof[0]["date"] == "2026-10-06"
    assert proof[0]["bills"] == ["tax bill B1 (2026), parcel ending 0000"]
    # the catalog's own match and the receipt's bill are one candidate, not two documents
    docs = [c for c in out["candidates"] if c["evidence"] == "document"]
    assert len(docs) == 1 and docs[0]["hasPdf"] is True and "W0000000001 paid it" in docs[0]["why"]
    assert out["recommend"]["action"].startswith("Check tax bill B1")
    tried = next(t for t in out["tried"] if t["source"] == "county payment receipts")
    assert tried["result"] == "exact" and tried["readAt"].startswith("2026-10-09")


def test_the_receipt_names_the_bill_even_when_the_catalog_matches_no_amount(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    tax_db(root, 99999)                                              # neither the whole bill nor half of it
    receipts(root, ("W0000000001", "2026-10-06T15:00:00Z", ("363.57",), "1234"))
    out = card(root)
    docs = [c for c in out["candidates"] if c["evidence"] == "document"]
    assert len(docs) == 1 and docs[0]["why"] == "the county's receipt W0000000001 paid this bill" and docs[0]["confidence"] == "exact"
    assert out["recommend"]["action"].startswith("Check tax bill B1")


def test_a_receipt_for_a_bill_with_no_pdf_asks_for_the_pdf(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    receipts(root, ("W0000000001", "2026-10-06T15:00:00Z", ("363.57",), "1234"))
    out = card(root)
    assert [c["kind"] for c in out["candidates"]] == ["receipt"]
    assert out["recommend"]["command"] == "jason county-tax --import-bill"
    assert "proves this payment and names the bill" in out["recommend"]["reason"]


def test_the_amount_alone_is_near_and_a_date_outside_the_window_is_not_exact(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    receipts(root, ("W0000000001", "2026-09-01T15:00:00Z", ("363.57",), "1234"),
             ("W0000000002", "2026-10-07T15:00:00Z", ("363.58",), "1234"))        # one a month early, one a cent off
    out = card(root)
    proof = [c for c in out["candidates"] if c["kind"] == "receipt"]
    assert [(c["label"], c["confidence"]) for c in proof] == [("county receipt W0000000001", "near")]
    assert "outside the window" in proof[0]["why"]
    assert not out["recommend"]["command"] == "jason county-tax --import-bill"


def test_a_tender_that_is_not_one_of_the_associations_accounts_is_near(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    receipts(root, ("W0000000001", "2026-10-06T15:00:00Z", ("363.57",), "1234"),
             ("W0000000002", "2026-10-06T15:00:00Z", ("363.57",), "9999"))
    out = inv.investigate(root, accounts("1234", "5678"), Registry(), 1, now=NOW)
    by = {c["label"]: c["confidence"] for c in out["candidates"] if c["kind"] == "receipt"}
    assert by == {"county receipt W0000000001": "exact", "county receipt W0000000002": "near"}
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR", bankLast4="9999")])      # the snapshot says which
    again = inv.investigate(root, accounts("1234"), Registry(), 1, now=NOW)
    by = {c["label"]: c["confidence"] for c in again["candidates"] if c["kind"] == "receipt"}
    assert by == {"county receipt W0000000001": "near", "county receipt W0000000002": "exact"}


def test_the_tender_last_four_is_held_back_unless_private_and_no_contact_detail_is_ever_shown(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    receipts(root, ("W0000000001", "2026-10-06T15:00:00Z", ("363.57",), "1234"))
    held, shown = card(root), card(root, private=True)
    assert "1234" not in json.dumps(held) and "tender" not in held["candidates"][0]
    assert shown["candidates"][0]["tender"] == "bank ending 1234"
    for body in (held, shown):
        text = json.dumps(body)
        assert "Example Association" not in text and "billing@example.test" not in text and "123 Main St" not in text
        assert "123-456-789" not in text                                           # a parcel is its last four


def test_a_receipt_is_never_offered_as_the_bill_and_the_store_is_capped(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    receipts(root, *[(f"W000000000{n}", f"2026-10-0{n}T15:00:00Z", ("363.57",), "1234") for n in range(1, 8)])
    out = card(root)
    proofs = [c for c in out["candidates"] if c["kind"] == "receipt"]
    assert len(proofs) == inv.MAX_PER_SOURCE and not [c for c in out["candidates"] if c["evidence"] == "document"]
    assert "2 more of the same amount not shown" in next(t for t in out["tried"] if t["source"] == "county payment receipts")["note"]


def test_no_receipts_on_disk_is_listed_as_not_read_with_the_command(root):
    snapshot(root, [tx(1, 36357, "ACH EXAMPLE COUNTY TAX COLLECTOR")])
    tried = next(t for t in card(root)["tried"] if t["source"] == "county payment receipts")
    assert tried["result"] == "not read" and "jason county-tax --import-receipts" in tried["note"]
