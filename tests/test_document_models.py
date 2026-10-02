"""The document model framework and the SB 326 (Civil Code 5551) balcony report model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    amount_after,
    cents,
    date_after,
    dates_in,
    read,
    register,
    to_plain,
)
from jason.community.symbols import DocumentKind

SB326 = """--- page 1 ---
Lic. 400001
EXTERIOR ELEVATED ELEMENTS
INSPECTION REPORT
SB 326
November 8, 2023
Examination Date
Example Management, Inc
Property Owner
Example Community
Site Name
Order: 01234
--- page 2 ---
81
Units
8
Buildings
3
Stories
Wood Frame
Type of Construction
Immediate Threat to Safety of Occupants:
Deck
24
0
24
24
Landing
0
0
0
0
--- page 3 ---
Nine years from the date of this report.
Re-Inspection
Signed:
EXAMPLE DECK INSPECTION
By   Alex Inspector
Pat Designer
President
Architect
11/17/2023
--- page 4 ---
BLDG 8
Unit 5635
Balcony Deck
None
BLDG 7
Unit 3038
Balcony Deck
Yes
"""


def test_helpers_read_amounts_and_dates():
    assert cents("$1,234.56") == 123456 and cents("(12.00)") == -1200 and cents("no money") is None
    assert amount_after(r"Total Due", "Total Due: $2,750.00 now") == 275000
    assert dates_in("on 11/17/2023 and November 8, 2023") == [date(2023, 11, 17), date(2023, 11, 8)]
    assert date_after("Examination Date:", "Examination Date: 11/8/2023") == date(2023, 11, 8)


def test_a_model_registers_and_reports_missing_fields():
    @dataclass
    class Note:
        subject: str = ""
        day: date | None = None

    class NoteModel(DocumentModel):
        kind = DocumentKind.COMMITTEE_REPORT
        name = "test-note"
        required = ("subject", "day")

        def parse(self, text, context):
            return Note(subject="roof") if text.startswith("NOTE") else None

        def check(self, record, context):
            return [Finding("roof", "roof named", Severity.INFO)]

    model = NoteModel()
    reading = model.read("NOTE: roof", ModelContext())
    assert reading.missing == ("day",) and not reading.complete
    assert [f.code for f in reading.findings] == ["missing-day", "roof"]
    assert model.read("something else", ModelContext()) is None
    assert to_plain(Note("x", date(2024, 1, 2))) == {"subject": "x", "day": "2024-01-02"}


def test_the_sb326_report_model_reads_the_first_page_facts_and_checks_5551():
    reading = read(DocumentKind.ELEVATED_ELEMENT_INSPECTION, SB326, ModelContext(today=date(2026, 9, 29)))
    r = reading.record
    assert (r.inspection_date, r.report_date, r.signer, r.signer_title) == (date(2023, 11, 8), date(2023, 11, 17), "Pat Designer", "Architect")
    assert (r.units, r.buildings, r.elements_total, r.elements_inspected) == (81, 8, 24, 24)
    assert r.next_inspection == date(2032, 11, 17) and len(r.inspected) == 2
    assert (r.immediate_threats, r.units_affected) == (1, 1)
    codes = {f.code: f for f in reading.findings}
    assert codes["immediate-threat"].severity is Severity.PROBLEM and codes["immediate-threat"].authority == "CIV 5551(g)"
    assert {"signer-license-not-in-text", "no-units-with-elements", "no-statistical-sample-certification", "no-random-list",
            "owner-is-manager", "keep-two-cycles"} <= set(codes)
    assert "first-inspection-late" not in codes


def test_the_sb326_model_leaves_other_inspection_reports_alone():
    assert read(DocumentKind.INSPECTION_REPORT, "Fire sprinkler annual inspection report. All systems pass.", ModelContext()) is None or \
        read(DocumentKind.INSPECTION_REPORT, "Fire sprinkler annual inspection report. All systems pass.", ModelContext()).model != "sb326-report"


def test_the_board_quorum_is_a_majority_of_directors_in_office_never_below_two():
    from jason.community import mystique

    board = mystique().board()
    assert (board.seats, board.minimum, board.maximum) == (5, 3, 5)
    assert (board.quorum(), board.quorum(4), board.quorum(3), board.quorum(2)) == (3, 3, 2, 2)
