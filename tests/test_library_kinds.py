"""The document kinds shelf: every kind on its shelf, counts by method, held files counted and never named."""

import sqlite3

import pytest

from jason.community.symbols import DocumentCategory, DocumentKind
from jason.tasks import library_kinds as lk

COLUMNS = "id, source, path, name, kind, category, records, method, period, confidential, evidence, confidence, classified_at, sha256"


def _store(tmp_path, rows):
    folder = tmp_path / "library"
    folder.mkdir()
    con = sqlite3.connect(folder / "library.db")
    con.execute(f"CREATE TABLE documents ({COLUMNS})")
    for i, (kind, name, method, period, held) in enumerate(rows):
        con.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (str(i), "payhoa", f"Folder/{name}", name, kind, "", "", method, period, int(held), "rule says so", 1.0,
                     "2099-10-01T09:00:00", f"sha{i}"))
    con.commit()
    con.close()


ROWS = [
    ("minutes", "Minutes 2099-01.pdf", "NAME", "2099-01", False),
    ("minutes", "Minutes 2099-02.pdf", "CONTENT", "2099-02", False),
    ("bank_statement", "Statement 2099-09.pdf", "NAME", "2099-09", True),
    ("bank_statement", "Statement 2099-08.pdf", "NAME", "2099-08", True),
    ("", "scan0001.pdf", "NONE", "", False),
    ("declaration", "Declaration.pdf", "PERSON", "2099", False),
]


def test_the_shelf_lists_every_kind_in_the_shelves_fixed_order(tmp_path):
    _store(tmp_path, ROWS)
    data = lk.shelf(tmp_path)
    assert data["found"] is True
    assert [s["shelf"] for s in data["shelves"]] == [c.value for c in DocumentCategory if any(s["shelf"] == c.value for s in data["shelves"])]
    listed = {k["kind"] for s in data["shelves"] for k in s["kinds"]}
    assert listed == {k.value for k in DocumentKind}
    assert data["total"] == 6 and data["unclassified"] == 1
    assert data["kindsTotal"] == len(DocumentKind) and data["kindsWithFiles"] == 3


def test_a_kind_with_no_files_is_a_gap_and_one_with_a_record_names_its_citation(tmp_path):
    _store(tmp_path, ROWS)
    kinds = {k["kind"]: k for s in lk.shelf(tmp_path)["shelves"] for k in s["kinds"]}
    gap = kinds["tax_return"]
    assert gap["files"] == 0 and gap["newest"] is None
    assert gap["record"] == {"citation": "CIV 5200(a)(6)", "label": "Tax return"}
    assert kinds["minutes"]["files"] == 2 and kinds["minutes"]["newest"] == "2099-02"
    assert kinds["minutes"]["methods"] == {"name": 1, "content": 1, "agenda": 0, "model": 0, "person": 0, "none": 0}
    assert kinds["declaration"]["methods"]["person"] == 1


def test_held_files_are_counted_and_never_named(tmp_path):
    _store(tmp_path, ROWS)
    summary = {k["kind"]: k for s in lk.shelf(tmp_path)["shelves"] for k in s["kinds"]}["bank_statement"]
    assert summary["files"] == 2 and summary["held"] == 2
    detail = lk.kind_detail(tmp_path, "bank_statement")
    assert detail["files"] == [] and detail["heldBack"] == 2 and detail["summary"]["files"] == 2
    assert "Statement" not in str(detail)
    shown = lk.kind_detail(tmp_path, "bank statement", include_held=True)
    assert [f["name"] for f in shown["files"]] == ["Statement 2099-09.pdf", "Statement 2099-08.pdf"]


def test_a_kind_page_lists_files_newest_first_with_the_method_as_a_word(tmp_path):
    _store(tmp_path, ROWS)
    files = lk.kind_detail(tmp_path, "minutes")["files"]
    assert [f["period"] for f in files] == ["2099-02", "2099-01"]
    assert [f["methodWord"] for f in files] == ["by its text", "by name or folder"]


def test_unclassified_is_its_own_page_and_a_miss_stays_a_miss(tmp_path):
    _store(tmp_path, ROWS)
    detail = lk.kind_detail(tmp_path, "unclassified")
    assert detail["summary"]["label"] == "No kind yet" and detail["summary"]["files"] == 1
    assert [f["name"] for f in detail["files"]] == ["scan0001.pdf"] and detail["files"][0]["method"] == "none"


def test_a_word_that_is_not_a_kind_is_refused_and_no_store_is_not_found(tmp_path):
    with pytest.raises(ValueError):
        lk.kind_detail(tmp_path, "napkin")
    assert lk.shelf(tmp_path)["found"] is False
