"""County payment receipts (``jason.tasks.tax_receipts``) and ``jason county-tax``: a saved receipt is trimmed to what the
bill investigation needs, kept once by its confirmation number, and a bill PDF a person saved is filed where the tax sync
files its own. Made-up documents only; nothing is reached.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pytest

from jason.commands import county_tax as cmd
from jason.community.tax import TaxAccount, TaxBill
from jason.community.tax_store import TaxStore
from jason.tasks import tax_receipts as tr

APN = "000-0000-000-0000"
NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)

# Values the trim must drop: none may appear anywhere in what is stored.
DROPPED = ("Example Association", "123 Main St", "5550100", "billing@example.test", "Example Bank - Operating",
           "okta|fake-user", "FAKE-AUTH-CODE", "Situs Address", "Anytown", "90000")


def receipt(conf="W0000000001", posted="2026-10-07T15:20:27Z", amounts=("363.57",), apn=APN, tender="Checking ending in 1234",
            fee="0.00"):
    return {
        "id": conf, "confirmationNumber": conf, "postedDatetime": posted, "client": "example", "site": "example",
        "userId": "okta|fake-user", "contactPreference": "email",
        "tender": {"type": "bank", "name": "Example Bank - Operating", "summary": tender},
        "billing": {"name": "Example Association", "address1": "123 Main St", "address2": "", "city": "Anytown",
                    "state": "XX", "postalCode": "90000", "country": "US", "phone": "5550100",
                    "email": "billing@example.test"},
        "delivery": {"name": "", "address1": "", "city": ""},
        "immediateProcessorDetails": {"authorizationCode": "FAKE-AUTH-CODE", "terminalNumber": ""},
        "transactions": [{"id": "t-1", "delayed": False, "fee": fee, "items": [
            {"id": "", "path": f"/Example/v0/items/example:items:{n}?installment=second-installment", "quantity": 1,
             "amount": amount,
             "details": {"display_name": "2025 Secured Annual Bill #2025000001", "external_id": "2025000001",
                         "description": f"Bill #2025000001 Due: 04/10/2026 - 2nd Installment\nParcel #{apn}\n"
                                        "Situs Address: 123 Main St",
                         "custom_parameters": {"tax_rate_year": "2025"}}}
            for n, amount in enumerate(amounts)]}],
    }


def test_a_receipt_is_trimmed_to_what_the_investigation_needs():
    out = tr.parse_receipt(receipt(amounts=("363.57", "1,000.05")))
    assert out == {"confirmation": "W0000000001", "postedAt": "2026-10-07T15:20:27Z", "totalCents": 136362, "feeCents": 0,
                   "tenderType": "bank", "tenderLast4": "1234",
                   "items": [{"amountCents": 36357, "apn": APN, "bill": "2025000001",
                              "billName": "2025 Secured Annual Bill #2025000001", "year": 2025, "installment": "second-installment"},
                             {"amountCents": 100005, "apn": APN, "bill": "2025000001",
                              "billName": "2025 Secured Annual Bill #2025000001", "year": 2025, "installment": "second-installment"}]}
    text = json.dumps(out)
    assert not [d for d in DROPPED if d in text]


def test_what_is_stored_holds_no_contact_detail_and_only_the_last_four(tmp_path):
    tr.import_receipts(tmp_path, [tr.parse_receipt(receipt())], by="Pat", now=NOW)
    stored = (tmp_path / "tax" / "receipts.json").read_text(encoding="utf-8")
    assert not [d for d in DROPPED if d in stored]
    assert "1234" in stored and "Checking ending" not in stored


def test_cents_are_exact_whatever_the_print():
    assert [tr.cents(v) for v in ("7.00", "$1,234.50", 7, "0.07", "0.1", "", None, "n/a", True)] == [700, 123450, 700, 7, 10,
                                                                                                    None, None, None, None]
    out = tr.parse_receipt(receipt(amounts=("0.10", "0.20"), fee="0.05"))
    assert out["totalCents"] == 30 and out["feeCents"] == 5          # 0.1 + 0.2 as cents, with no float


def test_the_last_four_comes_from_a_field_or_the_summary_and_never_the_name():
    doc = receipt()
    assert tr.parse_receipt(doc)["tenderLast4"] == "1234"
    doc["tender"] = {"type": "bank", "name": "Example Bank - Operating", "last4": "98765"}
    assert tr.parse_receipt(doc)["tenderLast4"] == "8765"
    doc["tender"] = {"type": "card", "name": "Example Card"}
    out = tr.parse_receipt(doc)
    assert out["tenderLast4"] == "" and "Example" not in json.dumps(out)


def test_the_list_response_and_the_per_receipt_response_both_read():
    one, skipped = tr.receipts_from_list(receipt("W0000000002"))
    assert [r["confirmation"] for r in one] == ["W0000000002"] and skipped == 0
    many, skipped = tr.receipts_from_list({"page": 1, "perPage": 10, "total": 3, "totalPages": 1,
                                           "results": [receipt("W0000000003"), {"note": "no confirmation"}, receipt("W0000000004")]})
    assert [r["confirmation"] for r in many] == ["W0000000003", "W0000000004"] and skipped == 1
    assert tr.receipts_from_list({"page": 1, "total": 0, "results": None}) == ([], 0)      # a count-only page
    assert [r["confirmation"] for r in tr.receipts_from_list([receipt("W0000000005")])[0]] == ["W0000000005"]
    with pytest.raises(ValueError):
        tr.receipts_from_list("not a receipt")
    with pytest.raises(ValueError):
        tr.parse_receipt({"postedDatetime": "2026-10-07T00:00:00Z"})


def test_an_import_is_append_only_and_idempotent_by_confirmation_number(tmp_path):
    first = tr.import_receipts(tmp_path, [tr.parse_receipt(receipt())], by="Pat", now=NOW)
    assert len(first["added"]) == 1 and first["added"][0]["by"] == "Pat" and first["added"][0]["importedAt"].startswith("2026-10-10")
    before = (tmp_path / "tax" / "receipts.json").read_text(encoding="utf-8")
    later = datetime(2026, 10, 12, tzinfo=timezone.utc)
    again = tr.import_receipts(tmp_path, [tr.parse_receipt(receipt(amounts=("1.00",)))], by="Lee", now=later)
    assert again["added"] == [] and len(again["already"]) == 1
    assert (tmp_path / "tax" / "receipts.json").read_text(encoding="utf-8") == before        # the row is not touched
    third = tr.import_receipts(tmp_path, [tr.parse_receipt(receipt("W0000000009"))], by="Lee", now=later)
    held = tr.load(tmp_path)
    assert [r["confirmation"] for r in held] == ["W0000000001", "W0000000009"] and len(third["added"]) == 1
    head = json.loads((tmp_path / "tax" / "receipts.json").read_text(encoding="utf-8"))
    assert head["importedAt"].startswith("2026-10-12") and held[0]["by"] == "Pat" and held[1]["by"] == "Lee"


def test_an_import_names_who(tmp_path):
    with pytest.raises(ValueError, match="--by"):
        tr.import_receipts(tmp_path, [tr.parse_receipt(receipt())], by=" ")
    assert not (tmp_path / "tax" / "receipts.json").exists()


def test_a_list_shows_a_parcel_by_its_last_four_characters(tmp_path):
    tr.import_receipts(tmp_path, [tr.parse_receipt(receipt())], by="Pat", now=NOW)
    line = tr.lines(tr.load(tmp_path))[0]
    assert "parcel ending 0000 $363.57" in line and "bank ending 1234" in line and "000-0000-000" not in line


def test_the_live_reader_is_not_built():
    with pytest.raises(tr.NeedsSignIn, match="sign-in at a terminal"):
        tr.read_live_receipts()


# --- the command ------------------------------------------------------------------------------------------------------

@pytest.fixture
def where(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: tmp_path)
    monkeypatch.setattr(cmd, "_tax_paths", lambda args: (tmp_path / "tax.db", tmp_path / "tax-bills"))
    return tmp_path


def run(**kw):
    base = dict(env=None, list=False, json=False, import_receipts=None, import_bill=None, apn=None, year=None, bill=None, by="")
    return cmd.cmd_county_tax(argparse.Namespace(**{**base, **kw}))


def catalog(root, *numbers):
    with TaxStore(root / "tax.db") as store:
        store.upsert(TaxAccount(apn=APN, address="123 Main St", path="p",
                                bills=tuple(TaxBill(number=n, name="", year=2025, total_cents=72714) for n in numbers)))


def test_the_command_imports_a_saved_receipt_and_lists_it(where, capsys, tmp_path):
    saved = tmp_path / "saved.json"
    saved.write_text(json.dumps(receipt()), encoding="utf-8")
    assert run(import_receipts=str(saved)) == 2                       # who is required
    assert run(import_receipts=str(saved), by="Pat") == 0
    assert "1 receipts added, 0 already held" in capsys.readouterr().out
    assert run(import_receipts=str(saved), by="Pat") == 0
    assert "0 receipts added, 1 already held" in capsys.readouterr().out
    assert run(list=True) == 0
    out = capsys.readouterr().out
    assert "1 receipts held." in out and "parcel ending 0000" in out and "000-0000-000" not in out
    assert run(list=True, json=True) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["receipts"][0]["items"][0]["apn"] == "0000" and body["bills"] == []


def test_the_command_refuses_a_file_with_no_receipt(where, capsys, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"results": None}), encoding="utf-8")
    assert run(import_receipts=str(bad), by="Pat") == 2
    assert "no receipt with a confirmation number" in capsys.readouterr().err
    assert run(import_receipts=str(tmp_path / "missing.json"), by="Pat") == 2


def test_a_bill_pdf_is_filed_where_the_sync_files_its_own_and_recorded_on_the_row(where, capsys, tmp_path):
    catalog(where, "2025000001")
    pdf = tmp_path / "downloaded.pdf"
    pdf.write_bytes(b"%PDF-1.4 made up")
    assert run(import_bill=str(pdf), apn=APN, year=2025, by="Pat") == 0
    dest = where / "tax-bills" / APN / "2025-2025000001.pdf"
    assert dest.read_bytes() == pdf.read_bytes() and "recorded on the stored bill" in capsys.readouterr().out
    with TaxStore(where / "tax.db") as store:
        bill = store.get(APN).bills[0]
    assert bill.pdf_path == str(dest) and len(bill.pdf_sha256) == 64
    log = [json.loads(l) for l in (where / "tax" / "bill-imports.jsonl").read_text(encoding="utf-8").splitlines()]
    assert log[0]["by"] == "Pat" and log[0]["bill"] == "2025000001" and log[0]["recordedOnRow"] is True
    assert run(import_bill=str(pdf), apn=APN, year=2025, by="Pat") == 0               # again: the same file, nothing changes
    other = tmp_path / "other.pdf"
    other.write_bytes(b"%PDF-1.4 a different bill")
    assert run(import_bill=str(other), apn=APN, year=2025, by="Pat") == 2             # never replaces a filed bill
    assert dest.read_bytes() == pdf.read_bytes()
    assert run(list=True) == 0
    assert "1 of 1 stored bills have a PDF." in capsys.readouterr().out


def test_a_bill_import_needs_a_pdf_a_bill_and_a_name(where, capsys, tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    text = tmp_path / "t.pdf"
    text.write_bytes(b"not a pdf")
    assert run(import_bill=str(pdf), apn=APN, year=2025) == 2                          # no --by
    assert run(import_bill=str(text), apn=APN, year=2025, by="Pat") == 2
    assert "is not a PDF" in capsys.readouterr().err
    assert run(import_bill=str(pdf), apn=APN, year=2025, by="Pat") == 2               # no catalog, no --bill
    assert "run `jason sync-tax` first" in capsys.readouterr().err
    catalog(where, "2025000001", "2025000002")
    assert run(import_bill=str(pdf), apn=APN, year=2025, by="Pat") == 2               # two that year: choose
    assert "choose with --bill" in capsys.readouterr().err
    assert run(import_bill=str(pdf), apn=APN, year=2025, bill="2025000002", by="Pat") == 0
    assert (where / "tax-bills" / APN / "2025-2025000002.pdf").is_file()


def test_a_bill_with_no_row_is_filed_for_the_sync_to_find(where, capsys, tmp_path):
    pdf = tmp_path / "d.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    assert run(import_bill=str(pdf), apn=APN, year=2024, bill="2024000009", by="Pat") == 0
    assert (where / "tax-bills" / APN / "2024-2024000009.pdf").is_file()
    assert "will find the file" in capsys.readouterr().out and not (where / "tax.db").exists()
