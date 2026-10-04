"""The Money screens' document references (docs/console/doc-component.md, "Adopting it on a screen"): the invoice
review's and the utility audit's attachments, the treasurer's reports the ledger validation names, each borrowing's 5515
documents, and the latest reserve study. Each loader returns ``DocRef``s the evidence resolves, never an absolute path.
Everything here is made up."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.approvals.evidence import resolve

ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")
INVOICE = "transactions/2099/01/invoices/501-Invoice 77.pdf"
BILL = "transactions/2099/02/invoices/601-Water bill.pdf"


def _no_absolute(value) -> None:
    if isinstance(value, str):
        assert not ABSOLUTE.match(value), value
    elif isinstance(value, dict):
        for v in value.values():
            _no_absolute(v)
    elif isinstance(value, list):
        for v in value:
            _no_absolute(v)


def _library(root: Path, rows) -> None:
    """Library rows: (id, path, name, kind, period, text)."""
    from jason.tasks.library import SCHEMA

    db = root / "library" / "library.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    (root / "library" / "text").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(SCHEMA)
        for doc_id, path, name, kind, period, text in rows:
            conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, "
                         "confidential, evidence, confidence, classified_at, sha256) VALUES "
                         "(?, 'payhoa', ?, ?, ?, 'finance', '', 'name', ?, 0, '', 1.0, '', ?)",
                         (doc_id, path, name, kind, period, f"sha-{doc_id}"))
            file = root / "library" / "files" / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"%PDF-1.4 library")
            (root / "library" / "text" / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    conn.close()


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    payhoa = tmp_path / "payhoa"
    payhoa.mkdir()
    for rel in (INVOICE, BILL):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"%PDF-1.4 attachment")
    (payhoa / "transactions.json").write_text(json.dumps({"vendors": {}, "categories": {}, "transactions": [
        {"id": 500, "transactionDate": "2099-01-05", "attachments": []},
        {"id": 501, "parentId": 500, "transactionDate": "2099-01-05", "attachments": [{"id": 9001, "filename": "Invoice 77.pdf"}]},
        {"id": 502, "transactionDate": "2099-01-09", "attachments": [{"id": 9002, "filename": "Never downloaded.pdf"}]},
    ]}), encoding="utf-8")
    (payhoa / "utility-transactions.json").write_text(json.dumps({"categories": {}, "transactions": [
        {"id": 601, "transactionDate": "2099-02-03", "attachments": [{"id": 9101, "filename": "Water bill.pdf"}]},
    ]}), encoding="utf-8")
    return tmp_path


# --- invoices ---------------------------------------------------------------------------------------------------------------

def test_an_older_review_finds_each_attachment_from_the_stored_transactions(data):
    from jason.tasks.invoice_review import document_refs

    rows = [{"key": 500, "documents": [{"filename": "Invoice 77.pdf", "kind": "invoice"}]},
            {"key": 502, "documents": [{"filename": "Never downloaded.pdf", "kind": ""}]}]
    document_refs(data, rows)
    ref = rows[0]["documents"][0]["doc"]
    assert (ref["address"], ref["name"], ref["kind"], ref["level"]) == (f"file:{INVOICE}", "Invoice 77.pdf", "pdf", "P2")
    assert resolve(ref["address"], data_dir=data)["found"]
    assert "doc" not in rows[1]["documents"][0]                  # no copy on disk: the filename alone, never a guess
    _no_absolute(rows)


def test_a_review_records_the_attachments_path_under_the_data_folder(data):
    from jason.tasks.invoice_review import data_path, document_refs

    assert data_path(data, data / INVOICE) == INVOICE
    assert data_path(data, data.parent / "elsewhere.pdf") == ""   # a portal's own bill, outside the folder
    rows = [{"key": 1, "documents": [{"id": 1, "filename": "Invoice 77.pdf", "path": INVOICE}]}]
    assert document_refs(data, rows)[0]["documents"][0]["doc"]["address"] == f"file:{INVOICE}"


def test_a_file_named_with_two_spaces_in_a_row_is_its_own_ref(data):
    from jason.approvals.evidence import resolve
    from jason.tasks.invoice_review import attachment_ref

    rel = "transactions/2099/01/invoices/503-Two  spaces.pdf"
    (data / rel).write_bytes(b"%PDF-1.4 attachment")
    (data / "transactions/2099/01/invoices/503-Two spaces.pdf").write_bytes(b"%PDF-1.4 another file")
    ref = attachment_ref(data, rel, "Two  spaces.pdf")
    assert ref["address"] == f"file:{rel}" and ref["size"] == len(b"%PDF-1.4 attachment")   # not the one-space file
    assert resolve(ref["address"], data_dir=data)["documents"][0]["size"] == len(b"%PDF-1.4 attachment")


def test_the_invoices_loader_answers_refs(data):
    from jason.web.sources import invoices

    (data / "payhoa" / "invoice-review.json").write_text(json.dumps({
        "found": True, "summary": {}, "scorecard": [], "caveats": [],
        "payments": [{"key": 500, "date": "2099-01-05", "amountCents": 6120, "payee": "Example Vendor", "description": "",
                      "categories": ["Repairs"], "documents": [{"filename": "Invoice 77.pdf", "kind": "invoice"}],
                      "findings": ["no attachment prints the payment's $61.20"], "ok": False}]}), encoding="utf-8")
    out = invoices({})
    ref = out["payments"][0]["documents"][0]["doc"]
    assert resolve(ref["address"], data_dir=data)["found"]
    _no_absolute(out)


# --- utility payments -------------------------------------------------------------------------------------------------------

def test_the_utility_loader_answers_each_attachments_ref(data):
    from jason.web.sources import utility_payments

    (data / "payhoa" / "utility-audit.json").write_text(json.dumps({
        "found": True, "summary": {}, "caveats": [],
        "payments": [{"key": 601, "provider": "water", "date": "2099-02-03", "amountCents": 6120, "rows": [],
                      "attachments": [{"id": 9101, "filename": "Water bill.pdf", "bill": None, "kind": "utility_bill"}],
                      "paid": [], "actualSplit": {}, "expectedSplit": {}, "split": "no bill to split by",
                      "findings": ["no set of bills on disk sums to this payment"], "ok": False}]}), encoding="utf-8")
    out = utility_payments({})
    ref = out["payments"][0]["attachments"][0]["doc"]
    assert (ref["address"], ref["level"]) == (f"file:{BILL}", "P2")
    assert resolve(ref["address"], data_dir=data)["found"]
    _no_absolute(out)


# --- the ledger validation's treasurer's reports ----------------------------------------------------------------------------

def test_each_library_copy_the_validation_names_is_a_library_ref(data):
    from jason.tasks.ledger_reports import library_refs

    _library(data, [("tr0826", "Finance/2099-08 report.pdf", "2099-08 report.pdf", "treasurer_report", "2099-08", "")])
    result = {"found": True,
              "runs": [{"id": 1, "libraryCopies": ["Finance/2099-08 report.pdf"], "libraryIds": ["tr0826"]},
                       {"id": 2, "libraryCopies": [], "libraryIds": []}],
              "balanceChanges": [{"id": "tr0826", "path": "Finance/2099-08 report.pdf", "account": "Operating"}],
              "libraryCopiesNotFromARun": [{"path": "Finance/old.pdf", "period": "2099-07"}]}   # an older run: no id
    library_refs(data, result)
    ref = result["runs"][0]["libraryDocs"][0]
    assert (ref["address"], ref["name"], ref["source"]) == ("library:tr0826", "2099-08 report.pdf", "Library copy")
    assert resolve(ref["address"], data_dir=data)["found"]
    assert result["runs"][1]["libraryDocs"] == []
    assert result["balanceChanges"][0]["doc"]["address"] == "library:tr0826"
    assert "doc" not in result["libraryCopiesNotFromARun"][0]
    _no_absolute(result)


# --- each borrowing's 5515 documents ----------------------------------------------------------------------------------------

def test_each_borrowings_notice_minutes_and_resolution_is_a_library_ref(data):
    from jason.tasks.reserve_transfers import documents

    _library(data, [
        ("ag0215", "Agendas/2099-02-15 agenda.pdf", "2099-02-15 agenda.pdf", "agenda", "2099-02-15",
         "Notice of Intent to Borrow from the reserve"),
        ("mn0215", "Minutes/2099-02-15 minutes.pdf", "2099-02-15 minutes.pdf", "minutes", "2099-02-15",
         "The board resolved to borrow."),
        ("rs0215", "Resolutions/Borrowing resolution.pdf", "Borrowing resolution.pdf", "resolution", "2099-02-15",
         "authorizes $10,000.00"),
    ])
    loan = SimpleNamespace(movement=SimpleNamespace(day=date(2099, 3, 1), cents=1_000_000))
    docs = documents(data, loan)
    for part, doc_id in (("notice", "ag0215"), ("minutes", "mn0215"), ("resolution", "rs0215")):
        ref = docs[part]["doc"]
        assert ref["address"] == f"library:{doc_id}" and ref["level"] == "P0"
        assert resolve(ref["address"], data_dir=data)["found"]
    _no_absolute(docs)


def test_a_minutes_row_read_from_drive_is_a_drive_ref(data):
    from jason.tasks.reserve_transfers import library_doc

    assert library_doc(data, "drive-1ExampleDriveFile01", "Minutes")["address"] == "drive:1ExampleDriveFile01"
    assert library_doc(data, "not an id!", "x") is None


# --- the reserve study ------------------------------------------------------------------------------------------------------

def test_the_latest_study_is_a_card_ref_and_the_reserves_loader_answers_it(data, monkeypatch):
    from jason.tasks import reserves
    from jason.web.sources import reserves as reserves_loader

    folder = data / "reserve-studies"
    folder.mkdir()
    (folder / "Study 2098.pdf").write_bytes(b"%PDF-1.4 old study")
    (folder / "Study 2099.pdf").write_bytes(b"%PDF-1.4 new study")

    def read(path):
        year = 2099 if "2099" in Path(path).name else 2098
        return SimpleNamespace(fiscal_year=year, prepared=date(year - 1, 9, 1), projection=(1,), source=str(path))

    monkeypatch.setattr(reserves, "read_study", read)
    reserves._LATEST.clear()
    ref = reserves.latest_study_ref(data)
    assert (ref["address"], ref["name"], ref["kind"], ref["level"]) == (
        "file:reserve-studies/Study 2099.pdf", "Reserve study, fiscal year 2099", "pdf", "P1")
    assert resolve(ref["address"], data_dir=data)["found"]
    out = reserves_loader({})
    assert out["study"]["address"] == ref["address"]
    _no_absolute(out)


def test_no_study_on_disk_is_no_ref(data):
    from jason.tasks import reserves

    reserves._LATEST.clear()
    assert reserves.latest_study_ref(data) is None
