"""The reference shelf: a fetched guide, its note and page text, and its own catalog apart from the law and the record."""

from __future__ import annotations

from pathlib import Path

from jason.community.reference_shelf import REFERENCE_WORKS, ReferenceWork, fetch_reference, page_text, work_of
from jason.community.passage_index import SOURCES, Standing


def _pdf(pages: list[str]) -> bytes:
    import io

    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    buffer = io.BytesIO(doc.tobytes())
    return buffer.getvalue()


def test_fetch_writes_the_file_a_note_and_the_text_by_page_and_keeps_what_is_there(tmp_path: Path):
    work = ReferenceWork("A Guide", "https://example.test/guide.pdf", "An Author", "A Publisher", 2014, "a process", "not the law")
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return _pdf(["first page words", "second page words"])

    assert fetch_reference(tmp_path, fetch=fetch, works=(work,)) == ["guide.pdf"]
    assert fetch_reference(tmp_path, fetch=fetch, works=(work,)) == [] and calls == ["https://example.test/guide.pdf"]
    out = tmp_path / "reference"
    note = (out / "guide.pdf.md").read_text(encoding="utf-8")
    assert note.startswith("# A Guide") and "How far to trust it: not the law" in note and "not the association's record" in note
    assert "second page words" in page_text(tmp_path, work, 2) and "first" not in page_text(tmp_path, work, 2)
    assert page_text(tmp_path, work, 9) == ""


def test_a_text_file_lost_after_the_fetch_is_rewritten_without_a_second_request(tmp_path: Path):
    work = ReferenceWork("A Guide", "https://example.test/guide.pdf", "A", "P", 2014, "c", "k")
    fetch_reference(tmp_path, fetch=lambda url: _pdf(["only page"]), works=(work,))
    (tmp_path / "reference" / "guide.txt").unlink()
    assert fetch_reference(tmp_path, fetch=lambda url: (_ for _ in ()).throw(AssertionError("fetched twice")), works=(work,)) == []
    assert "only page" in page_text(tmp_path, work, 1)


def test_the_shelf_is_its_own_catalog_sourced_from_data_reference_and_labelled_as_neither_law_nor_record():
    # The shelf's catalog is the passage index's (AnythingLLM's catalogs were retired October 4, 2026).
    rows = [s for s in SOURCES if s.catalog == "reference"]
    assert [s.folder for s in rows] == ["reference"] and rows[0].standing is Standing.REFERENCE
    assert not rows[0].confidential and "*.pdf.md" in rows[0].exclude      # the title note is not a passage
    others = {s.standing for s in SOURCES if s.catalog in ("authorities", "records")}
    assert Standing.REFERENCE not in others and {Standing.AUTHORITY, Standing.RECORD} <= others


def test_every_work_names_its_author_year_and_how_far_to_trust_it():
    assert REFERENCE_WORKS and work_of("residentialsubdivisionsguide.pdf") is REFERENCE_WORKS[0]
    for work in REFERENCE_WORKS:
        assert work.author and work.year and work.caveat and work.covers and work.filename.endswith(".pdf")
        assert work.url.startswith("https://")
