"""The chronology and the conflicts of fact: what a set of documents says, quoted, with whose document it is."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from jason.community import chronology as ch
from jason.community import fact_conflicts as fc
from jason.community import passage_index as pi
from jason.community.legal_cases import CaseEvent

TODAY = date(2026, 10, 4)

REPORT = """Inspection Date: 3/5/2099

The technician tested the panel on March 5, 2099 and found that one device failed its test. The next inspection is due on or about September 1, 2099.
The monitoring agreement ran from 1/1/2098 through 12/31/2098. Account 12-3-2099-55 is not a date.
"""
LETTER = """April 2, 2099

Dear Board:

The technician tested the panel on March 5, 2099 and found that one device failed its test. We will repair it by April 30, 2099.
"""
MEMO = "On February 1, 2099 the board met in executive session about the claim.\n"
PAGE = "# Summary\n\nThe report of March 5, 2099 is summarized here for the board's reading before the meeting.\n"

POLICY_A = """Policy Number: 77-0001
Policy Term: 01/01/2099 to 01/01/2100
Insurer: ACME INDEMNITY COMPANY
Total Premium: $1,301.00
Building Limit: $1,750,000
"""
POLICY_B = """Policy Number: 77-0001
Policy Term: 01/01/2099 to 01/01/2100
Insurer: Acme Indemnity Co.
Total Premium: $1,415.00
Building Limit: $1,750,000
"""
POLICY_C = "Policy Number: 88-0002\nPolicy Term: 01/01/2099 to 01/01/2100\nTotal Premium: $900.00\n"
BILL_A = ("The vendor sent Invoice No. 1042, dated March 1, 2099. The board approved Invoice No. 1042 for a total of $500.00.\n"
          "On March 5, 2099 the board approved a payment of $5,000.00 to the roofer for the east stair.\n"
          "SECOND INSTALLMENT DUE 04/10/2099 $8.16 RETURN THIS STUB WITH THE SECOND INSTALLMENT PAYMENT.\n")
BILL_B = ("Our records show Invoice No. 1042 dated March 3, 2099. Invoice No. 1042 has a total of $450.00 after the credit.\n"
          "Invoice No. 1042 lists a deposit of $100.00 and a balance of $350.00.\n"
          "On March 5, 2099 the board approved a payment of $4,500.00 to the roofer for the east stair.\n"
          "SECOND INSTALLMENT DUE 04/10/2099 $12.17 RETURN THIS STUB WITH THE SECOND INSTALLMENT PAYMENT.\n")
TRANSCRIPT = "00:00:01 Speaker 1: We met on March 5th and talked about the roof for an hour.\n"
TRANSCRIPT_NAME = "GMT20990115-173000_Recording.transcript.txt"


class Files:
    """A source that gives each made-up file its own catalog, kind, and flags."""

    catalogs = ("library", "letters", "private", "pages", "case-made-up")

    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows

    def entries(self, data_dir: Path):
        for rel, catalog, standing, kind, confidential, context in self.rows:
            yield pi.IndexFile(data_dir / rel, catalog, standing, kind=kind, confidential=confidential,
                               generated=standing is pi.Standing.PAGE, context=context)


def _write(data: Path, rel: str, text: str) -> None:
    path = data / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    R, P = pi.Standing.RECORD, pi.Standing.PAGE
    rows = [
        ("library/text/101.txt", "library", R, "inspection_report", False, "Fire alarm report.pdf: inspection report"),
        ("letters/letter.md", "letters", R, "correspondence", False, ""),
        ("private/memo.md", "private", R, "executive_session", True, ""),
        ("pages/summary.md", "pages", P, "", False, "jason's report: Summary"),
        ("library/text/201.txt", "library", R, "insurance_policy", False, "Policy A.pdf: insurance policy"),
        ("library/text/202.txt", "library", R, "insurance_policy", False, "Policy B.pdf: insurance policy"),
        ("library/text/203.txt", "library", R, "insurance_policy", False, "Policy C.pdf: insurance policy"),
        ("library/text/204.txt", "library", R, "insurance_policy", True, "Policy D.pdf: insurance policy"),
        ("letters/bill-a.md", "letters", R, "correspondence", False, ""),
        ("letters/bill-b.md", "letters", R, "correspondence", False, ""),
        (f"cases/made-up/files/{TRANSCRIPT_NAME}", "case-made-up", pi.Standing.EVIDENCE, "", True, ""),
    ]
    texts = [REPORT, LETTER, MEMO, PAGE, POLICY_A, POLICY_B, POLICY_C, POLICY_B.replace("1,415.00", "1,999.00"), BILL_A, BILL_B,
             TRANSCRIPT]
    for (rel, *_), text in zip(rows, texts):
        _write(tmp_path, rel, text)
    pi.build(tmp_path, sources=(Files(rows),), kind_of=lambda name: "")
    policy = {"kind": "insurance_policy", "model": "made-up-policy", "confidential": False, "hasText": True}
    fields = {"policy_number": "77-0001", "term_start": "2099-01-01", "term_end": "2100-01-01", "limit": 175000000, "units": 7}
    readings = [
        {**policy, "id": "201", "name": "Policy A.pdf", "fields": {**fields, "carrier": "ACME INDEMNITY COMPANY", "premium": 130100,
                                                                 "declaration": "new"}},
        {**policy, "id": "202", "name": "Policy B.pdf", "fields": {**fields, "carrier": "Acme Indemnity Co.", "premium": 141500,
                                                                 "declaration": "endorsement"}},
        {**policy, "id": "203", "name": "Policy C.pdf", "fields": {**fields, "policy_number": "88-0002", "premium": 90000}},
        {**policy, "id": "204", "name": "Policy D.pdf", "confidential": True, "fields": {**fields, "premium": 199900}},
        {"kind": "inspection_report", "model": "made-up-report", "id": "101", "name": "Fire alarm report.pdf",
         "fields": {"inspection_date": "2099-03-05", "building": 1, "system": "fire alarm", "result": "failed"}},
        {"kind": "correspondence", "model": "letter", "id": "999", "name": "Not in the index.pdf", "fields": {"dated": "2099-01-01"}},
    ]
    _write(tmp_path, "documents/readings.json", json.dumps({"readings": readings}))
    return tmp_path


def _chronology(data: Path, scope: pi.Scope = pi.Scope(), **kw) -> ch.Chronology:
    return ch.chronology(data, scope, "the made-up file", today=TODAY, **kw)


# --- the chronology -----------------------------------------------------------------------------------------------------


def test_events_come_out_in_date_order_with_their_quotes_and_sources(data):
    events = _chronology(data, pi.Scope(catalogs=("library", "pages"), kinds=("inspection_report", ""))).events
    assert [e.day for e in events] == sorted(e.day for e in events) and len({e.day for e in events}) == 3
    tested = next(e for e in events if e.day == date(2099, 3, 5) and e.role is ch.DateRole.ABOUT and e.place.file == "101.txt")
    assert tested.quote == "The technician tested the panel on March 5, 2099 and found that one device failed its test."
    assert tested.written == "March 5, 2099" and tested.rule == "sentence"
    assert (tested.place.catalog, tested.place.standing, tested.place.kind) == ("library", pi.Standing.RECORD, "inspection_report")
    assert tested.place.document == "101.txt (Fire alarm report.pdf: inspection report)" and tested.place.passage == 0
    words = (data / "library/text/101.txt").read_text(encoding="utf-8").split()
    assert words[tested.place.word: tested.place.word + 3] == ["The", "technician", "tested"]       # a person can find it
    assert 'says: "The technician tested the panel' in tested.says() and "happened" not in tested.says()
    # On one day the record comes before a page jason wrote.
    same_day = [e.place.standing for e in events if e.day == date(2099, 3, 5)]
    assert same_day == sorted(same_day, key=ch.STANDING_ORDER.index) and same_day[-1] is pi.Standing.PAGE


def test_a_documents_own_date_is_labeled_apart_from_a_date_it_speaks_about(data):
    events = _chronology(data, pi.Scope(catalogs=("library", "letters"), kinds=("inspection_report", "correspondence"))).events
    head = next(e for e in events if e.place.file == "101.txt" and e.role is ch.DateRole.DOCUMENT)
    assert (head.day, head.label, head.rule, head.quote) == (date(2099, 3, 5), "Inspection Date", "label-line", "Inspection Date: 3/5/2099")
    assert "gives its own date as 3/5/2099" in head.says()
    dateline = next(e for e in events if e.place.file == "letter.md" and e.role is ch.DateRole.DOCUMENT)
    assert (dateline.day, dateline.rule, dateline.quote) == (date(2099, 4, 2), "date-line", "April 2, 2099")
    repair = next(e for e in events if e.day == date(2099, 4, 30))
    assert repair.role is ch.DateRole.ABOUT and repair.document_day == date(2099, 4, 2)       # "the letter of April 2 says"
    assert "dated 2099-04-02 at its head, says:" in repair.says()
    due = next(e for e in events if e.day == date(2099, 9, 1))
    assert due.approximate and due.role is ch.DateRole.ABOUT and "(on or about)" in due.when
    term = next(e for e in events if e.day == date(2098, 1, 1))
    assert term.end == date(2098, 12, 31) and term.written == "1/1/2098 through 12/31/2098"
    assert not any(e.day.year == 2099 and e.day.month == 12 for e in events)                 # the account number is no date


def test_dates_are_read_by_the_existing_readers():
    spans = ch.date_spans("Signed the 17th day of October, 2096; paid 1/2/98; in March 2095; on 23-MAR-2094; may 2093 pass.", today=TODAY)
    assert [(s.day, s.precision) for s in spans] == [
        (date(2096, 10, 17), ch.Precision.DAY), (date(1998, 1, 2), ch.Precision.DAY),
        (date(2095, 3, 1), ch.Precision.MONTH), (date(2094, 3, 23), ch.Precision.DAY)]
    assert ch.date_spans("Parcel 201-12-05-2099-0007 and the thirty-first of May.", today=TODAY) == []
    row = pi.Row("library", pi.Standing.RECORD, "insurance_policy", False, False, "k")
    (term,) = ch.events_of(pi.Passage(Path("policy.txt"), 4, 90, "Policy Term\n04/19/2098 12:01 AM - 04/19/2099 12:01 AM\n"), row, today=TODAY)
    assert (term.day, term.end, term.role) == (date(2098, 4, 19), date(2099, 4, 19), ch.DateRole.ABOUT)


def test_a_header_further_in_is_not_the_documents_date():
    text = "Dear Board:\n\nPlease see the message below, which the manager forwarded to the members of the board.\n" * 9
    passage = pi.Passage(Path("thread.md"), 2, 400, text + "\nSent: Monday, March 4, 2099 3:15 PM\nDue Date: 3/31/2099\n")
    row = pi.Row("mail", pi.Standing.RECORD, "", False, False, "k")
    sent, due = ch.events_of(passage, row, today=TODAY)
    assert (sent.role, sent.label, sent.day) == (ch.DateRole.EMBEDDED, "Sent", date(2099, 3, 4))
    assert (due.role, due.label) == (ch.DateRole.ABOUT, "Due Date")


def test_a_date_in_a_heading_line_is_not_taken_for_the_documents_own():
    row = pi.Row("library", pi.Standing.RECORD, "minutes", False, False, "k")
    text = "MADE-UP ASSOCIATION\nMinutes of 12/17/2098\n\nJan 21, 2099\n\nThe board met by video and approved the prior minutes.\n"
    heading, own = ch.events_of(pi.Passage(Path("minutes.md"), 0, 0, text), row, today=TODAY)
    assert (heading.role, heading.rule, heading.quote) == (ch.DateRole.HEADING, "head-line", "Minutes of 12/17/2098")
    assert (own.role, own.rule, own.day) == (ch.DateRole.DOCUMENT, "date-line", date(2099, 1, 21))
    assert "in a line at its head" in heading.says() and "its own date" not in heading.says()


def test_a_forms_field_carries_its_label_and_a_cell_the_lines_around_it():
    row = pi.Row("library", pi.Standing.RECORD, "inspection_report", False, False, "k")
    text = ("Batteries\nBattery Date\n10/11/2098\nBattery Type\nSealed Lead Acid\n\nCompleted:\nFriday, September 19, 2099\n\n"
            "Water Flow\nVSR\nSep 19, \n2099\nChase\nwater flowed for three minutes before the bell rang\n")
    battery, completed, cell = ch.events_of(pi.Passage(Path("report.txt"), 3, 400, text), row, today=TODAY)
    assert (battery.rule, battery.label, battery.role, battery.quote) == (
        "label-above", "Battery Date", ch.DateRole.ABOUT, "Battery Date 10/11/2098")
    assert (completed.rule, completed.label, completed.quote) == ("label-above", "Completed", "Completed: Friday, September 19, 2099")
    assert (cell.rule, cell.written, cell.quote) == ("date-cell", "Sep 19, 2099", "VSR Sep 19, 2099 Chase")
    # Two reports filled in on one form are two documents: their short statements do not fold.
    other = ch.events_of(pi.Passage(Path("report-8.txt"), 3, 400, text.replace("10/11/2098", "10/11/2097")), row, today=TODAY)
    assert len(ch.fold([battery, completed, cell, *other])) == 6


def test_a_date_only_the_files_name_prints_is_the_names_not_the_documents(data):
    scope = pi.Scope(catalogs=("case-made-up",), confidential_in=("case-made-up",))
    result = _chronology(data, scope)
    (event,) = result.events
    assert (event.role, event.rule, event.day, event.written) == (ch.DateRole.NAME, "file-name", date(2099, 1, 15), "20990115")
    assert event.quote == TRANSCRIPT_NAME and event.place.standing is pi.Standing.EVIDENCE and event.document_day is None
    assert "this is the name, not the document's words" in event.says()
    assert result.partial == 1 and "1 mentions of a month and a day with no year were not placed" in "\n".join(result.lines())
    assert result.confidential and "a date in the file's name, not in its words" in result.markdown(TODAY)
    assert ch.name_spans("Agenda 2099-11-20 final.pdf")[0].day == date(2099, 11, 20) and ch.name_spans("scan 991120.pdf") == []


def test_copies_fold_under_one_event(data):
    events = _chronology(data, pi.Scope(catalogs=("library", "letters"), kinds=("inspection_report", "correspondence"))).events
    tested = [e for e in events if e.quote.startswith("The technician tested the panel")]
    assert len(tested) == 1                                              # one event, and every place that carries it
    assert {tested[0].place.file, *(p.file for p in tested[0].also)} == {"letter.md", "101.txt"}
    assert "also in: " in "\n".join(_chronology(data, pi.Scope(catalogs=("library", "letters"))).lines())
    # Two different letters dated the same day stay two events: a date line folds only with its whole passage's copy.
    row = pi.Row("letters", pi.Standing.RECORD, "", False, False, "k")
    a = ch.events_of(pi.Passage(Path("a.md"), 0, 0, "April 2, 2099\n\nDear Board: the roof leaks over the east stair.\n"), row, today=TODAY)
    b = ch.events_of(pi.Passage(Path("b.md"), 0, 0, "April 2, 2099\n\nDear Owner: your request was approved by the board.\n"), row, today=TODAY)
    assert len(ch.fold([*a, *b])) == 2


def test_a_confidential_files_events_appear_only_when_asked(data):
    assert not any(e.place.file == "memo.md" for e in _chronology(data).events)
    asked = _chronology(data, pi.Scope(confidential_in=("private",)))
    memo = next(e for e in asked.events if e.place.file == "memo.md")
    assert memo.place.confidential and memo.day == date(2099, 2, 1) and asked.confidential
    assert not _chronology(data, pi.Scope(catalogs=("letters",))).confidential


def test_the_specifications_record_is_its_own_source_never_merged(data):
    recorded = (CaseEvent(date(2099, 3, 5), "The inspection took place", "the library's report"),
                CaseEvent(date(2090, 1, 1), "An earlier step"))
    result = _chronology(data, pi.Scope(catalogs=("library",), kinds=("inspection_report",)), recorded=recorded,
                         since=date(2099, 1, 1), until=date(2099, 12, 31))
    assert [r.step for r in result.recorded] == ["The inspection took place"]               # held to the same dates
    assert all(isinstance(e, ch.Event) for e in result.events) and not any("took place" in e.quote for e in result.events)
    assert all(date(2099, 1, 1) <= e.day <= date(2099, 12, 31) for e in result.events) and result.events
    assert result.confidential                                                               # a matter's record is held back
    page = result.markdown(TODAY)
    assert "## The specification's record" in page and "- 2099-03-05: The inspection took place (recorded in: the library's report)" in page
    assert page.index("## What the documents say") < page.index("## The specification's record")
    assert result.as_dict()["recorded"][0]["source"] == "the specification's record"


def test_the_written_page_carries_its_header_and_confidentiality(data):
    open_page = _chronology(data, pi.Scope(catalogs=("library",), kinds=("inspection_report",)))
    assert not (data / "collections").exists()                                               # nothing is written unasked
    path = ch.write_page(data, ch.slug_of(open_page.title), ch.CHRONOLOGY_PAGE, open_page.markdown(TODAY))
    assert path == data / "collections" / "the-made-up-file" / "chronology.md"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Chronology: the made-up file\n")
    assert "- Generated: by jason on 2026-10-04, by rule (no model), from the 1 documents listed under Sources." in text
    assert "- Standing: a summary, not the record." in text and "- Confidential: no." in text
    assert "> The technician tested the panel on March 5, 2099 and found that one device failed its test." in text
    assert "101.txt (Fire alarm report.pdf: inspection report) [library, record, inspection report]" in text
    held = _chronology(data, pi.Scope(confidential_in=("private",))).markdown(TODAY)
    assert "- Confidential: yes. 1 of its sources are held back unless asked; for directors and counsel only." in held


# --- the conflicts of fact ----------------------------------------------------------------------------------------------


def _conflicts(data: Path, scope: pi.Scope = pi.Scope(catalogs=("library",), kinds=("insurance_policy",))) -> fc.ConflictReport:
    return fc.fact_conflicts(data, scope, "the made-up policies", today=TODAY)


def test_two_documents_that_give_different_amounts_for_one_field_are_a_conflict_listing_both(data):
    report = _conflicts(data)
    assert [(c.rule, c.what) for c in report.conflicts] == [(fc.Rule.STORED_FIELD, "premium")]
    conflict = report.conflicts[0]
    assert "policy_number 77-0001" in conflict.subject and "term_start 2099-01-01" in conflict.subject
    assert [side.value for side in conflict.sides] == ["$1,301.00", "$1,415.00"]
    first, second = (side.statements[0] for side in conflict.sides)
    assert (first.quote, first.place.file) == ("Total Premium: $1,301.00", "201.txt")
    assert (second.quote, second.place.file) == ("Total Premium: $1,415.00", "202.txt")
    assert "made-up-policy reader's stored field premium" in first.basis and dict(second.shown) == {"declaration": "endorsement"}
    # The carrier's two spellings are one name, the limit agrees, and another policy number is another subject.
    assert report.readings == 3 and report.subjects == 1 and not report.confidential
    assert "picks neither" in report.markdown(TODAY) or "jason picks neither" in " ".join(report.caveats)


def test_a_confidential_reading_is_compared_only_when_asked(data):
    asked = _conflicts(data, pi.Scope(catalogs=("library",), kinds=("insurance_policy",), confidential_in=("library",)))
    premium = next(c for c in asked.conflicts if c.what == "premium")
    assert [side.value for side in premium.sides] == ["$1,301.00", "$1,415.00", "$1,999.00"]
    assert premium.confidential and asked.confidential and asked.readings == 4
    page = asked.markdown(TODAY)
    assert page.startswith("# Conflicts of fact: the made-up policies\n") and "- Confidential: yes." in page
    assert "- Rule: stored-field" in page and "    > Total Premium: $1,999.00" in page


def test_a_kind_with_no_rule_row_is_not_compared_and_the_report_says_so(data):
    report = fc.fact_conflicts(data, pi.Scope(catalogs=("library",)), "everything", rules=fc.FIELD_RULES[:1], today=TODAY)
    assert report.not_compared == ("inspection_report",)
    assert "Kinds with stored readings and no rule row (not compared): inspection_report" in "\n".join(report.lines())


def test_a_stored_value_the_text_does_not_print_carries_no_quote(data):
    rule = fc.FieldRule((fc.DocumentKind.INSURANCE_POLICY,), ("policy_number",), ("carrier", "units", "premium"), money=("premium",))
    stored = fc.stored_readings(data)
    stored[1]["fields"]["units"] = 9
    stored[1]["fields"]["carrier"] = "Other Mutual"
    report = fc.fact_conflicts(data, pi.Scope(catalogs=("library",), kinds=("insurance_policy",)), "t", rules=(rule,),
                               readings=stored, today=TODAY)
    by_field = {c.what: c for c in report.conflicts}
    assert set(by_field) == {"carrier", "units", "premium"}
    units = [s for side in by_field["units"].sides for s in side.statements]
    assert all(s.quote == "" and "does not print the value" in s.basis for s in units)       # a count is never located
    carrier = by_field["carrier"].sides
    assert carrier[0].statements[0].quote == "Insurer: ACME INDEMNITY COMPANY" and carrier[1].statements[0].quote == ""


def test_a_kind_can_have_several_rows_and_one_difference_is_listed_once(data):
    scope = pi.Scope(catalogs=("library",), kinds=("insurance_policy",))
    stored = [r for r in fc.stored_readings(data) if r["id"] in ("201", "202")]
    for reading in stored:
        reading["fields"].update(coverage="flood", building=2)
    # By what they cover, the building, and the term, and by the policy number and the term: the premium differs once.
    both = fc.fact_conflicts(data, scope, "t", readings=stored, today=TODAY)
    assert [(c.what, len(c.sides)) for c in both.conflicts] == [("premium", 2)] and both.subjects == 1
    # A second policy number for one building and term: found by the first row, which the second row cannot see.
    stored[1]["fields"]["policy_number"] = "77-0009"
    numbered = fc.fact_conflicts(data, scope, "t", readings=stored, today=TODAY)
    assert {c.what for c in numbered.conflicts} == {"policy_number", "premium"}
    number = next(c for c in numbered.conflicts if c.what == "policy_number")
    assert "coverage flood, building 2, term_start 2099-01-01" in number.subject
    assert [side.value for side in number.sides] == ["77-0001", "77-0009"]
    assert number.sides[0].statements[0].quote == "Policy Number: 77-0001" and number.sides[1].statements[0].quote == ""


def test_the_library_id_of_an_index_row_follows_the_documents_copies(tmp_path):
    from jason.tasks import library

    rows = [("library/text/301.txt", "library", pi.Standing.RECORD, "invoice", False, ""),
            ("library/text/303.txt", "library", pi.Standing.RECORD, "invoice", False, "")]
    _write(tmp_path, "library/text/301.txt", "Invoice Date: 3/1/2099\nTotal: $500.00\n")
    _write(tmp_path, "library/text/303.txt", "Invoice Date: 3/1/2099\nTotal: $450.00\n")
    with sqlite3.connect(tmp_path / library.STORE) as conn:
        conn.execute(library.SCHEMA)
        for doc_id, sha in (("301", "aa"), ("302", "aa"), ("303", "bb")):
            conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (doc_id, "payhoa", f"Bills/{doc_id}.pdf", f"{doc_id}.pdf", "invoice", "", "", "NAME", "", 0, "", 1.0,
                          "2026-01-01T00:00:00+00:00", sha))
    conn.close()
    pi.build(tmp_path, sources=(Files(rows),), kind_of=lambda name: "")
    assert fc.library_id(tmp_path / "library/text/301.vision.txt", tmp_path) == "301"
    assert fc.library_id(tmp_path / "letters/301.txt", tmp_path) is None
    invoice = {"kind": "invoice", "model": "invoice", "fields": {"vendor": "Acme Roofing", "number": "1042"}}
    readings = [{**invoice, "id": "302", "fields": {**invoice["fields"], "total_cents": 50000}},       # the reading names the other copy
                {**invoice, "id": "303", "fields": {**invoice["fields"], "total_cents": 45000}}]
    report = fc.fact_conflicts(tmp_path, pi.Scope(), "invoices", readings=readings, today=TODAY)
    assert [(c.what, [s.value for s in c.sides]) for c in report.conflicts] == [("total_cents", ["$500.00", "$450.00"])]
    assert [side.statements[0].place.file for side in report.conflicts[0].sides] == ["301.txt", "303.txt"]


def test_the_text_rules_are_narrow_and_name_themselves(data):
    report = fc.fact_conflicts(data, pi.Scope(catalogs=("letters",)), "the bills", today=TODAY)
    found = {(c.rule, c.subject, c.what): c for c in report.conflicts}
    amount = found[(fc.Rule.IDENTIFIER_AMOUNT, "invoice 1042", 'the amount under "total"')]
    assert [side.value for side in amount.sides] == ["$500.00", "$450.00"]
    assert amount.sides[0].statements[0].quote == "The board approved Invoice No. 1042 for a total of $500.00."
    assert amount.sides[1].statements[0].place.file == "bill-b.md" and amount.sides[1].statements[0].basis == "the text"
    dated = found[(fc.Rule.IDENTIFIER_DATE, "invoice 1042", 'the date after "dated"')]
    assert [side.value for side in dated.sides] == ["2099-03-01", "2099-03-03"]
    # The same sentence about the same day, word for word but for its amount.
    approved = found[(fc.Rule.DATED_STATEMENT_AMOUNT, "a statement about 2099-03-05", "the amount (every other word is the same)")]
    assert [side.value for side in approved.sides] == ["$5,000.00", "$4,500.00"]
    assert approved.sides[1].statements[0].quote == "On March 5, 2099 the board approved a payment of $4,500.00 to the roofer for the east stair."
    # The statement with two amounts is left out, and so is a form's line (a stub is the same words on every bill).
    assert len(report.conflicts) == 3 and not fc.is_prose(BILL_A.splitlines()[2]) and fc.is_prose(BILL_A.splitlines()[1])
    assert fc.masked_words("Unit 12 paid $5.00 on 3/5/2099.", [(13, 18, fc.AMOUNT_MARK), (22, 30, fc.DATE_MARK)]) == (
        "unit", "12", "paid", fc.AMOUNT_MARK, "on", fc.DATE_MARK)
    assert fc.identifiers("Invoice No. 1042 and Policy 5010015467; Check 2099; File: 12; Order 6600; Case No. 24CV000123") == [
        ("invoice", "1042"), ("policy", "5010015467"), ("case", "24CV000123")]


def test_names_and_amounts_are_matched_loosely_and_exactly():
    assert fc.same_text("ACME INDEMNITY COMPANY", "Acme Indemnity Co.") and fc.same_text("Acme Roofing", "ACME ROOFING, INC.")
    assert not fc.same_text("Acme Roofing", "Summit Roofing")
    assert fc.money_pattern(130100).search("Premium 1301.00 due") and not fc.money_pattern(130100).search("Premium 11,301.00")
    assert fc.money_pattern(50000).search("a fee of $500") and not fc.money_pattern(50000).search("500 units")


# --- the commands -------------------------------------------------------------------------------------------------------


def _run(argv: list[str], capsys) -> tuple[int, str]:
    from jason.cli import build_parser

    args = build_parser().parse_args(argv)
    code = args.func(args)
    return code, capsys.readouterr().out


def test_the_commands_scope_by_the_index_flags_and_write_only_when_asked(data, monkeypatch, capsys):
    monkeypatch.setenv("PAYHOA_CATALOG", str(data / "payhoa.db"))
    code, out = _run(["chronology", "--catalog", "library", "--kind", "inspection_report", "--from", "2099-01-01", "--json"], capsys)
    found = json.loads(out)
    assert code == 0 and found["counts"]["events"] == 3 and found["counts"]["from"] == "2099-03-05"
    assert {e["role"] for e in found["events"]} == {"document", "about"} and found["confidential"] is False
    assert not (data / "collections").exists()
    code, out = _run(["chronology", "--confidential", "--to", "2099-02-28"], capsys)
    assert code == 0 and "memo.md" in out and "Note: Each event is what a document says" in out
    code, out = _run(["fact-conflicts", "--catalog", "library", "--kind", "insurance_policy", "--write", "--title", "Flood policies"], capsys)
    assert code == 0 and "1. [stored-field]" in out and "$1,415.00" in out
    page = (data / "collections" / "flood-policies" / "conflicts.md").read_text(encoding="utf-8")
    assert page.startswith("# Conflicts of fact: Flood policies\n") and "- Confidential: no." in page
    assert _run(["chronology", "--standing", "binding"], capsys)[0] == 2
    assert _run(["chronology", "--from", "yesterday"], capsys)[0] == 2


def test_a_case_catalog_named_opens_its_own_files_and_no_other(data):
    import argparse

    from jason.commands.chronology import scope_of

    def flags(**kw) -> argparse.Namespace:
        return argparse.Namespace(**{"catalog": [], "standing": [], "kind": [], "folder": [], "confidential": False, **kw})

    assert scope_of(flags(catalog=["case-made-up", "library"]), data).confidential_in == ("case-made-up",)
    assert scope_of(flags(catalog=["case-made-up"], confidential=True), data).confidential_in == ("case-made-up",)
    # --confidential opens every other catalog's held files and never a case catalog that is not named.
    assert set(scope_of(flags(confidential=True), data).confidential_in) == {"library", "letters", "private", "pages"}
    assert scope_of(flags(), data).confidential_in == ()


def test_naming_a_case_catalog_reads_its_held_files(data, monkeypatch, capsys):
    monkeypatch.setenv("PAYHOA_CATALOG", str(data / "payhoa.db"))
    code, out = _run(["chronology", "--catalog", "case-made-up", "--json"], capsys)
    found = json.loads(out)
    assert code == 0 and found["confidential"] is True and [e["role"] for e in found["events"]] == ["name"]
    code, out = _run(["chronology", "--confidential", "--json"], capsys)
    assert code == 0 and not any(e["catalog"] == "case-made-up" for e in json.loads(out)["events"])
