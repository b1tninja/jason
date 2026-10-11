"""The county tax collector as a bill source (``jason.sources.county_tax``): a payment to the collector gets the tax bill its
receipt paid, through a chain in which every link must be unique. Made-up payment, receipts, catalog and PDFs in tmp_path; the
attach engine runs against a fake PayHOA that records uploads.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from jason.community.payees import PayeeClass, PayeeRule
from jason.sources.county_tax import CountyTaxBillSource
from jason.sources.attach import attach_bills
from jason.sources.registry import BillSourceRegistry
from jason.sources.types import BillNeed
from jason.tasks import tax_receipts as tr

APN = "000-0000-000-0000"
TAX = PayeeRule(PayeeClass.COUNTY_TAX, description_contains=("EXAMPLE COUNTY TAX",))
COMMUNITY = SimpleNamespace(payee_rules=lambda: (TAX,), bank_accounts=lambda: (SimpleNamespace(suffix="1234"),))
DAY = date(2026, 10, 7)


def catalog(root, *bills):
    conn = sqlite3.connect(root / "tax.db")
    conn.execute("CREATE TABLE bills (apn TEXT, number TEXT, year INTEGER, pdf_path TEXT)")
    for number, year, pdf in bills:
        if pdf:
            (root / "bills").mkdir(exist_ok=True)
            (root / "bills" / f"{number}.pdf").write_bytes(b"%PDF-1.4 fake")
        conn.execute("INSERT INTO bills VALUES (?, ?, ?, ?)", (APN, number, year, f"bills/{number}.pdf" if pdf else ""))
    conn.commit()
    conn.close()


def receipt(confirmation="W1", total="363.57", posted="2026-10-07T10:00:00Z", last4="1234", items=None):
    items = items if items is not None else [{"amount": total, "details": {"external_id": "B1", "custom_parameters": {"tax_rate_year": "2026"},
                                                                          "description": f"Parcel # {APN}"}, "path": "/x?installment=1"}]
    return {"confirmationNumber": confirmation, "postedDatetime": posted, "tender": {"type": "bank", "summary": f"Checking ending in {last4}"},
            "transactions": [{"fee": "0.00", "items": items}]}


def keep(root, *docs):
    rows, _ = tr.receipts_from_list(list(docs))
    tr.import_receipts(root, rows, by="Pat Example", now=datetime(2026, 10, 9, tzinfo=timezone.utc))


def need(amount=36357, around=DAY, tx=1):
    return BillNeed(amount_cents=amount, around=around, window_days=7, transaction_id=tx)


def source(root):
    return CountyTaxBillSource(root, COMMUNITY)


def test_it_owns_only_the_collectors_payments(tmp_path):
    s = source(tmp_path)
    assert s.matches_transaction({"description": "ACH EXAMPLE COUNTY TAX COLLECTOR"}) is True
    assert s.matches_transaction({"description": "ACH CITY OF EXAMPLE"}) is False
    assert CountyTaxBillSource(tmp_path, SimpleNamespace()).matches_transaction({"description": "EXAMPLE COUNTY TAX"}) is False


def test_the_receipt_names_the_one_bill_and_its_pdf_is_the_attachment(tmp_path):
    catalog(tmp_path, ("B1", 2026, True))
    keep(tmp_path, receipt())
    found = source(tmp_path).find_cached(need())
    assert len(found) == 1 and found[0].has_pdf and found[0].account_number == APN
    assert found[0].bill_id.startswith("B1 (receipt W1)") and found[0].bill_date == DAY and found[0].amount_cents == 36357
    assert source(tmp_path).resolve([need()]) == {need().key: found[0]}


@pytest.mark.parametrize("what", ["other amount", "outside the window", "another account", "no receipts"])
def test_each_link_must_hold_or_there_is_no_match(tmp_path, what):
    catalog(tmp_path, ("B1", 2026, True))
    if what != "no receipts":
        keep(tmp_path, receipt(total="363.58" if what == "other amount" else "363.57",
                               posted="2026-09-01T10:00:00Z" if what == "outside the window" else "2026-10-07T10:00:00Z",
                               last4="9999" if what == "another account" else "1234"))
    assert source(tmp_path).find_cached(need()) == []


def test_a_fee_on_top_of_the_total_still_matches(tmp_path):
    catalog(tmp_path, ("B1", 2026, True))
    doc = receipt(total="363.57")
    doc["transactions"][0]["fee"] = "3.00"
    keep(tmp_path, doc)
    assert len(source(tmp_path).find_cached(need(amount=36657))) == 1


def test_a_receipt_that_paid_two_bills_is_no_match_a_person_decides(tmp_path):
    catalog(tmp_path, ("B1", 2026, True), ("B2", 2025, True))
    two = [{"amount": "200.00", "details": {"external_id": "B1", "description": f"Parcel # {APN}"}},
           {"amount": "163.57", "details": {"external_id": "B2", "description": f"Parcel # {APN}"}}]
    keep(tmp_path, receipt(items=two))
    assert source(tmp_path).find_cached(need()) == []


def test_a_parcel_with_one_bill_row_is_not_enough_when_neither_number_nor_year_agrees(tmp_path):
    catalog(tmp_path, ("B9", 2024, True))
    keep(tmp_path, receipt())                         # the receipt names B1 / 2026; the catalog has only B9 / 2024
    assert source(tmp_path).find_cached(need()) == []


def test_without_the_pdf_it_is_found_but_not_resolved_and_cannot_be_fetched(tmp_path):
    catalog(tmp_path, ("B1", 2026, False))
    keep(tmp_path, receipt())
    s = source(tmp_path)
    found = s.find_cached(need())
    assert len(found) == 1 and not found[0].has_pdf and s.resolve([need()]) == {}
    with pytest.raises(LookupError, match="county-tax --import-bill"):
        s.ensure_pdf(found[0])


def test_two_payments_do_not_share_one_receipt(tmp_path):
    catalog(tmp_path, ("B1", 2026, True))
    keep(tmp_path, receipt())
    got = source(tmp_path).resolve([need(tx=1), need(tx=2)])
    assert len(got) == 1


class FakePayhoa:
    def __init__(self, txs):
        self.txs, self.uploads, self.approved = txs, [], []

    def iter_transactions(self, org_id, reviewed=False):
        yield from self.txs

    def get_transaction(self, org_id, tx_id):
        return next(t for t in self.txs if t["id"] == tx_id)

    def upload_attachment(self, org_id, tx_id, path):
        self.uploads.append((tx_id, path.name))
        return {"url": "x"}

    def update_transaction(self, org_id, tx_id, **kw):
        self.approved.append(tx_id)


def test_the_attach_engine_uploads_the_bill_through_the_receipt_and_never_approves_by_itself(tmp_path):
    catalog(tmp_path, ("B1", 2026, True))
    keep(tmp_path, receipt())
    tx = {"id": 7, "amount": 36357, "transactionDate": "2026-10-07", "description": "ACH EXAMPLE COUNTY TAX COLLECTOR",
          "approved": False, "attachments": []}
    client = FakePayhoa([tx])
    registry = BillSourceRegistry([source(tmp_path)])
    dry = attach_bills(client, registry, org_id=7, dry_run=True)
    assert [r.status for r in dry.results] == ["matched"] and client.uploads == []
    live = attach_bills(client, registry, org_id=7, dry_run=False)
    assert [r.status for r in live.results] == ["uploaded"] and client.uploads == [(7, "B1.pdf")] and client.approved == []


def test_it_is_in_the_offline_routing_registry_last(tmp_path):
    from jason.sources.offline import routing_registry

    c = SimpleNamespace(vendor_portals=lambda: (), payee_rules=lambda: (TAX,), bank_accounts=lambda: ())
    reg = routing_registry(c, None, tmp_path)
    assert [s.name for s in reg.sources] == ["smud", "idoxs", "county-tax"]
