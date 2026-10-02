from datetime import date
from pathlib import Path

from jason.community.governing import Supersession
from jason.community.readings import DocumentKindGuess, Reader, Relation, numbers_on_disk, proposed_supersessions, read_document

MODERN = """RECORDING REQUESTED BY: AND WHEN RECORDED, MAIL TO: INMAN LAW GROUP, LLP
Sacramento County Donna Allred, Clerk/Recorder Doc# 202003021215 Fees 3/2/2020 3:19:40 PM Taxes SUB Electronic PCOR Titles 2 Paid Pages 6
AMENDED AND RESTATED DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR MYSTIQUE, PHASE 4
If this document contains any restriction based on race ... $205.00 $0.00 $0.00 $205.00
This Amended and Restated Declaration of Annexation and Reservation of Easements for Mystique, Phase 4 (the "Declaration") is made by Watt Communities at Mystique, LLC, a California limited liability company ("Declarant") in reference to the following facts:
RECITALS
A. Declarant is the record owner of that certain real property (the "Annexed Property"): Association Common Area designated A.C.A. 7, Condominium Common Area designated C.C.A. 7, Units 48 through 57 inclusive, as depicted, described and defined in the Condominium Plan for Mystique Buildings 1, 2, 4, 5, 6, and 7, Recorded January 16, 2019, as Document No. 201901161002, of Official Records.
D. The Development was previously encumbered with that certain Declaration of Annexation and Reservation of Easements for Mystique, Phase 4, which Recorded on May 22, 2019, as Document No. 201905221469, in the Official Records of Sacramento County (the "Prior Declaration of Annexation"). Pursuant to Section 4, Declarant may rescind the Prior Declaration of Annexation. Upon the Recording of this Declaration of Annexation, the Prior Declaration of Annexation is hereby rescinded and superseded.
Later the easement over A.C.A. 3 and A.C.A. 8 is reserved.
"""

OLD = """RECORDING REQUESTED BY, AND BOO!{ 2007 1 1217 PAGE 1310 WHEN RECORDED, MAIL TO: Check Number 0386
Monday, DEC 17, 2007 2:29:26 PM Ttl Pd $18.00 Nbr-0005194964
DECLARATION OF ANNEXATION AND RESERVATION OF EASEMENTS FOR MYSTIQUE, PHASE 2
This Declaration of Annexation and Reservation of Easements for Mystique, Phase 2 (the "Declaration") is made by WL Homes, LLC, a Delaware limited liability company doing business as John Laing Homes ("Declarant") in reference to the following facts:
RECITALS A. Declarant is the record owner: Association Common Area designated A.C.A. 3, Condominium Common Area designated C.C.A. 3, Units 21 through 32 inclusive.
"""

UNRECORDED = """RECORDING REQUESTED BY: MYSTIQUE COMMUNITY ASSOCIATION (SPACE ABOVE THIS LINE FOR RECORDER'S USE)
SECOND AMENDMENT TO RESTATED DECLARATION OF COVENANTS, CONDITIONS AND RESTRICTIONS FOR MYSTIQUE
NOTICE If this document contains any restriction ...
RECITALS A. With respect to that certain RESTATED DECLARATION OF COVENANTS, CONDITIONS AND RESTRICTIONS FOR MYSTIQUE, recorded on September 20, 2007, as Document No. 200709200938, in the Official Records (the "2007 Declaration");
B. As amended by that First Amendment to the Restated Declaration Of Covenants, Conditions And Restrictions For Mystique, recorded on January 17, 2020 as Document No. 202001170712, in the Official Records (the "First Amendment");
C. Annexed to the Development by the Amended and Restated Declaration of Annexation and Reservation of Easements for Mystique, Phase 3, recorded on December 20, 2019, as Document No. 201912201433, in the Official Records. This instrument replaced and rescinded the previous instrument recorded as Declaration of Annexation and Reservation of Easements for Mystique, Phase 3, recorded on January 16, 2019, as Document No. 201901161003, in the Official Records;
Section 7.3 is hereby amended to read as follows. Section 12.1 is deleted.
"""


def test_the_modern_stamp_title_phase_declarant_annexed_property_and_rescission_are_read():
    reading = Reader().read(MODERN, "Annexation - Phase 4.pdf.md")
    assert reading.number == "202003021215" and reading.stamp.recorded == date(2020, 3, 2) and reading.stamp.pages == 6 and reading.stamp.titles == 2 and reading.stamp.fees_cents == 20500
    assert reading.kind is DocumentKindGuess.ANNEXATION and reading.phase == 4
    assert reading.title.startswith("AMENDED AND RESTATED DECLARATION OF ANNEXATION")
    assert reading.declarant.startswith("Watt Communities at Mystique, LLC")
    assert (reading.annexed.first_unit, reading.annexed.last_unit) == (48, 57)
    assert reading.annexed.association_common_areas == (7,) and reading.annexed.condominium_common_areas == (7,)
    by_number = {c.number: c for c in reading.citations}
    assert by_number["201901161002"].relation is Relation.PLAN and by_number["201901161002"].recorded == date(2019, 1, 16)
    assert by_number["201905221469"].relation is Relation.RESCINDS and by_number["201905221469"].recorded == date(2019, 5, 22)
    assert [c.number for c in reading.supersedes] == ["201905221469"]


def test_an_old_stamp_is_rebuilt_from_the_printed_date_when_ocr_breaks_the_book():
    reading = Reader().read(OLD, "Annexation - Phase 2.pdf.md")
    assert reading.number == "200712171310" and reading.stamp.recorded == date(2007, 12, 17)
    assert reading.phase == 2 and reading.declarant.startswith("WL Homes, LLC")
    assert (reading.annexed.first_unit, reading.annexed.last_unit) == (21, 32) and reading.annexed.association_common_areas == (3,)


def test_an_unrecorded_copy_is_flagged_and_its_recitals_still_relate_the_instruments():
    reading = Reader().read(UNRECORDED, "CCRs - 2nd Amendment.md")
    assert reading.number == "" and reading.stamp.unrecorded_copy and reading.kind is DocumentKindGuess.AMENDMENT
    assert reading.phase is None  # the recitals name every phase; the title names none
    relations = {c.number: c.relation for c in reading.citations}
    assert relations["200709200938"] is Relation.RELIES_ON
    assert relations["202001170712"] is Relation.AMENDS
    assert relations["201912201433"] is Relation.ANNEXES_UNDER
    assert relations["201901161003"] is Relation.RESCINDS
    assert reading.sections == ("7.3", "12.1")


def test_proposals_and_numbers_on_disk(tmp_path: Path):
    modern = tmp_path / "phase4.md"
    modern.write_text(MODERN, encoding="utf-8")
    draft = tmp_path / "second.md"
    draft.write_text(UNRECORDED, encoding="utf-8")
    readings = (read_document(modern), read_document(draft))
    assert numbers_on_disk(readings) == {"202003021215": modern}
    proposals = proposed_supersessions(readings, (Supersession("201905221469", "202003021215", phase=4),))
    assert [(p.number, p.superseded_by, p.pinned) for p in proposals] == [("201905221469", "202003021215", True)]
    # The unrecorded draft states a rescission too, but it has no number of its own to propose from.
    assert proposed_supersessions(readings[1:], ()) == ()
    assert not read_document(draft).readable or read_document(draft).text_length > 400
