"""The recorded instruments' models: where a copy's number comes from (the county's stamp, a title company's certification,
the file name), the vision text layer, and the deed, public report, and bond fields read from synthetic text with made-up
parties and numbers."""

from __future__ import annotations

from datetime import date

from jason.community.document_models import ModelContext, Severity, read
from jason.community.models.governing_deeds import NumberSource, layers
from jason.community.symbols import DocumentKind

TODAY = date(2026, 9, 30)
VISION = "--- ocr: ollama-vision ---"   # jason.tasks.library.VISION_MARK


class Stub:
    """A community without facts: the checks that consult the specification stay quiet."""


def ctx(name=""):
    return ModelContext(Stub(), None, TODAY, name, "")


def codes(reading):
    return {f.code: f for f in reading.findings}


def deed(head, body=""):
    return f"""{head}
A.P.N.: 201-1170-099-0023
GRANT DEED
DOCUMENTARY TRANSFER TAX $264.00; CITY TRANSFER TAX $660.00
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged, Pat Sample, a single person
hereby GRANTS to Casey Example, a single person
the real property in the City of Sacramento, described as: SEE EXHIBIT "A"
Dated: May 1, 2019
{body}"""


# Where the number comes from.

def test_title_certification_book_and_short_page():
    text = deed("CERTIFIED TO BE A TRUE COPY\nRECORDED 6/19/2019\nBOOK 2019 0619 PAGE 681\nSERIES NO.\nEXAMPLE TITLE\n"
                "RECORDING REQUESTED BY:\nExample Title Company\nTHIS SPACE FOR RECORDER'S USE ONLY:")
    reading = read(DocumentKind.GRANT_DEED, text, ctx("GD 201906190681.pdf"))
    r = reading.record
    assert (r.number, r.recorded, r.number_source) == ("201906190681", date(2019, 6, 19), NumberSource.CERTIFICATION)
    assert r.recording.certified_copy and reading.complete
    assert not {"number-from-name", "certification-differs", "no-stamp-in-text", "unrecorded-copy"} & set(codes(reading))


def test_certification_year_and_page_takes_the_book_from_its_date():
    text = deed("certified to be a true and exact copy of the original document recorded on 11/7/08 in Sacramento County Official "
                "Records, as Recorder's Instrument No.: 2008-1337\nExample Title Company\nSpace Above This Line for Recorder's Use Only")
    r = read(DocumentKind.GRANT_DEED, text, ctx()).record
    assert (r.number, r.number_source) == ("200811071337", NumberSource.CERTIFICATION)
    # The book as the instrument number and the page on its own line.
    text = deed("CERTIFIED A TRUE COPY OF THE ORIGINAL\nDOCUMENT RECORDED 3/27/12\nAS INSTRUMENT NO. 20120327\nIN BOOK PAGE 3215\n"
                "OFFICIAL RECORDS OF SACRAMENTO COUNTY")
    r = read(DocumentKind.GRANT_DEED, text, ctx("GD 201203273215.pdf")).record
    assert (r.number, r.number_source, r.certification_differs) == ("201203273215", NumberSource.CERTIFICATION, "")


def test_certification_date_vouches_for_the_name_when_its_page_misreads():
    # A vision reading of a handwritten "2013-0920-856" that added a digit: the date and the digits in order agree with the name.
    text = deed("SENT TO SACRAMENTO COUNTY RECORDER'S OFFICE\nCERTIFIED TO BE A TRUE COPY\nRECORDED 9/20/13 INSTRUMENT\n"
                "BOOK PAGE 2013-0920-8576\nEXAMPLE TITLE CO")
    r = read(DocumentKind.GRANT_DEED, text, ctx("GD 201309200856.pdf")).record
    assert (r.number, r.number_source) == ("201309200856", NumberSource.CERTIFICATION_AND_NAME)
    assert not r.certification_differs


def test_certification_that_disagrees_with_the_name_is_kept_for_a_person():
    text = deed("Certified to be a true and exact copy of the original document recorded on 10/22/08 in Sacramento County Official "
                "Records, as Recorder's Instrument No.: 2008-269\nExample Title Company")
    reading = read(DocumentKind.GRANT_DEED, text, ctx("GD 200810170269.pdf"))
    r = reading.record
    assert (r.number, r.number_source) == ("200810170269", NumberSource.NAME)
    assert r.certification_differs == "200810220269"
    assert codes(reading)["certification-differs"].severity is Severity.CHECK
    assert "number-from-name" not in codes(reading)


def test_no_stamp_takes_the_name_and_says_so():
    text = deed("RECORDING REQUESTED BY\nExample Title Company\n_____ Space Above This Line for Recorder's Use Only _____")
    reading = read(DocumentKind.GRANT_DEED, text, ctx("GD 201905071257.pdf"))
    r = reading.record
    assert (r.number, r.recorded, r.number_source) == ("201905071257", date(2019, 5, 7), NumberSource.NAME)
    found = codes(reading)
    assert found["number-from-name"].severity is Severity.CHECK and "blank recorder's box" in found["number-from-name"].message
    assert "unrecorded-copy" not in found
    # Without a number in the name, a miss stays a miss.
    bare = read(DocumentKind.GRANT_DEED, text, ctx("deed.pdf"))
    assert not bare.record.number and "unrecorded-copy" in codes(bare)


def test_county_stamp_wins_over_certification_and_name():
    text = deed("Sacramento County Recorder\nDoc # 202607210743 Fees $20.00\n7/21/2026 12:26:20 PM Taxes $1,578.50\n"
                "CERTIFIED TO BE A TRUE COPY RECORDED 1/2/2026 BOOK 20260102 PAGE 0001")
    r = read(DocumentKind.GRANT_DEED, text, ctx("GD 202607210743.pdf")).record
    assert (r.number, r.recorded, r.number_source) == ("202607210743", date(2026, 7, 21), NumberSource.STAMP)


def test_deed_date_forms():
    base = deed("RECORDING REQUESTED BY\nExample Title")
    for printed, expected in (("Dated: 10/25/07", date(2007, 10, 25)), ("Dated: January 21st 2008", date(2008, 1, 21)),
                              ("Grant Deed - continued Date: 01/05/2012", date(2012, 1, 5))):
        r = read(DocumentKind.GRANT_DEED, base.replace("Dated: May 1, 2019", printed), ctx()).record
        assert r.dated == expected, printed
    trust = base.replace("Dated: May 1, 2019", "the Example Family Trust Dated 17 January 2006")
    assert read(DocumentKind.GRANT_DEED, trust, ctx()).record.dated is None


def test_recorded_before_dated():
    text = deed("RECORDING REQUESTED BY\nExample Title Company").replace("May 1, 2019", "December 29, 2021")
    reading = read(DocumentKind.GRANT_DEED, text, ctx("GD 202102240825.pdf"))
    assert codes(reading)["recorded-before-dated"].severity is Severity.CHECK


# The vision layer.

VISION_PAGE = """RECORDING REQUESTED BY:
Example Title Company of Sacramento
CERTIFIED TO BE A TRUE COPY
RECORDED 2/22/18
BOOK 20180222 PAGE 1332
THIS SPACE FOR RECORDER'S USE ONLY:
AP#: 201-1170-099-0012 GRANT DEED
DOCUMENTARY TRANSFER TAX is $278.30
CITY TRANSFER TAX $694.41
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged,
Pat Sample, a single person
hereby GRANT(s) to:
Casey Example, a single person
the real property in the City of Sacramento
DATED: February 20, 2018
"""

OLD_TEXT = """RECORDING REQUESTED BY:
Exarnple Title Cornpany of Sacrarnento
CERTIFIED T0 BE A TRUE C0PY RECORDED ~/~~/18 BOOK 2O18O222 PAGE l332
A.P.N.: 2014170-099-0012 GRANT DEED
DOCUMENTARY TRANSFER TAX $278.30 CITY TRANSFER TAX $6941.41
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged, Pat Sarnple, a single person
hereby GRANTS to Casey Exarnple, a single person
EXHIBIT A: UNIT 12, BUILDING 5, CONDOMINIUM PLAN
"""


def test_vision_layer_is_split_from_the_old_text_and_preferred():
    text = f"{VISION}\n{VISION_PAGE}\n\n{OLD_TEXT}"
    vision, rest = layers(text)
    assert vision.startswith("RECORDING REQUESTED BY") and "2014170" not in vision and rest.startswith("RECORDING REQUESTED BY:\nExarnple")
    r = read(DocumentKind.GRANT_DEED, text, ctx("GD 201802221332.pdf")).record
    assert r.number == "201802221332" and r.number_source is NumberSource.STAMP
    assert r.apns == ("201-1170-099-0012",)                       # not the old layer's slip as a second parcel
    assert (r.county_tax_cents, r.city_tax_cents) == (27_830, 69_441)  # the old layer's "$6941.41" is not taken
    assert r.grantee == "Casey Example, a single person"
    assert layers(OLD_TEXT) == ("", OLD_TEXT)


def test_city_tax_prices_a_deed_between_county_steps():
    # $694.41 is $252,513; the county's 55 cents per $500 or fraction rounds that up to 506 steps, $278.30.
    reading = read(DocumentKind.GRANT_DEED, f"{VISION}\n{VISION_PAGE}", ctx("GD 201802221332.pdf"))
    assert reading.record.consideration_cents == 25_251_300
    assert "transfer-taxes-disagree" not in codes(reading)


def test_statute_in_the_tax_blank_is_an_exempt_deed():
    text = deed("RECORDING REQUESTED BY\nExample Homes").replace("DOCUMENTARY TRANSFER TAX $264.00; CITY TRANSFER TAX $660.00",
                                                                 "DOCUMENTARY TRANSFER TAX IS $ 119.11")
    r = read(DocumentKind.GRANT_DEED, text, ctx("GD 200709281731.pdf")).record
    assert r.exempt and r.county_tax_cents is None and r.consideration_cents is None


def test_county_tax_slip_names_what_the_city_tax_computes():
    text = deed("RECORDING REQUESTED BY\nExample Title").replace("$264.00; CITY TRANSFER TAX $660.00", "$387 .20 City Transfer Tax: $968.00")
    reading = read(DocumentKind.GRANT_DEED, text, ctx("GD 202111301835.pdf"))
    found = codes(reading)["county-tax-not-a-step"]
    assert "$387.20" in found.message and found.authority == "R&T 11911"


# The deed's other fields.

RECEIVER_DEED = """SPACE ABOVE THIS LINE FOR RECORDER'S USE
GRANT DEED
DOCUMENTARY TRANSFER TAX $0.00
FOR A VALUABLE CONSIDERATION, receipt of which is hereby acknowledged, ALEX EXAMPLE ("Receiver"), COURT-APPOINTED RECEIVER ON
BEHALF OF THE PROPERTY OWNED BY EXAMPLE HOMES LLC, A DELAWARE LIMITED LIABILITY COMPANY IN THE MATTER OF EXAMPLE BANK V. EXAMPLE
HOMES, LLC, Superior Court Case No. 00-0000 ("Grantor"), does hereby grant to SAMPLEVILLE COMMUNITY ASSOCIATION, a California
nonprofit mutual benefit corporation ("Grantee"), the real property in the City of Sacramento described on Exhibit "A".
(This document is being re-recorded to correct the legal description of the Grant Deed recorded October 12, 2010 Instrument No. 20101012)
APN: 201-1170-022-000 I through 20 I-1170-022-0004; 201·1170-023-0001 THROUGH 201-1170-023-0003
"""


def test_receiver_deed_parties_ranges_and_rerecording():
    reading = read(DocumentKind.GRANT_DEED, RECEIVER_DEED, ctx("GD 201103180727.pdf"))
    r = reading.record
    assert r.grantor.startswith("ALEX EXAMPLE") and r.grantor.endswith("A DELAWARE LIMITED LIABILITY COMPANY")
    assert r.grantee == "SAMPLEVILLE COMMUNITY ASSOCIATION, a California nonprofit mutual benefit corporation"
    assert r.apns == tuple(f"201-1170-022-{n:04d}" for n in range(1, 5)) + tuple(f"201-1170-023-{n:04d}" for n in range(1, 4))
    assert (r.corrects, r.corrects_recorded) == ("legal description", date(2010, 10, 12))
    assert codes(reading)["re-recorded"].severity is Severity.INFO


PLAN_CITED = deed("RECORDING REQUESTED BY\nExample Title", """EXHIBIT A
Unit 12 as depicted, described and defined in the Condominium Plan for Sampleville recorded September 12, 2007, In 6ook 20070912,
Page 757 of Official Records ("Plan"), and in the restated Declaration of Covenants, Conditions and Restrictions, recorded
September 20, 2007, In Book 20070920, Page 938, of Official Records.""")


def test_plan_and_declaration_citations_are_not_crossed():
    r = read(DocumentKind.GRANT_DEED, PLAN_CITED, ctx("GD 201209211820.pdf")).record
    assert (r.plan_cited, r.declaration_cited) == ("200709120757", "200709200938")
    garbled = PLAN_CITED.replace("In 6ook 20070912,\nPage 757", "In ~~~ 2OO7O9-l2 pg 7S7")
    r = read(DocumentKind.GRANT_DEED, garbled, ctx("GD 201209211820.pdf")).record
    assert r.declaration_cited == "200709200938" and r.plan_cited == ""   # the plan's number did not read: a miss, not the CC&Rs


def test_plan_number_through_scan_slips_when_its_date_agrees():
    text = deed("RECORDING REQUESTED BY\nExample Title", "Unit 3 in the Condominium Plan for Sampleville Buildings 1, 2, 4, 5, 6, and 7, "
                "recor\"Cled January 16, 2019, as Document No-. 20t901161002 of Official Records (\"Plan\")")
    assert read(DocumentKind.GRANT_DEED, text, ctx()).record.plan_cited == "201901161002"
    wrong_day = text.replace("January 16", "January 17")
    assert read(DocumentKind.GRANT_DEED, wrong_day, ctx()).record.plan_cited == ""


# The other recorded kinds share the copy's number.

CERTIFIED_PLAN = """Certified to be a true and correct
copy of original document recorded
9-12-2007, in Book
20070912, page 757
of Official Records.
Example Title Company
CONDOMINIUM PLAN
FOR
SAMPLEVILLE
SURVEYOR'S STATEMENT
"""


def test_condominium_plan_reads_the_certification():
    reading = read(DocumentKind.CONDOMINIUM_PLAN, CERTIFIED_PLAN, ctx("Condominium Plan 200709120757.PDF"))
    assert reading is not None
    rec = reading.record.recording
    assert (rec.number, rec.recorded, rec.source) == ("200709120757", date(2007, 9, 12), "certification")


# Public reports.

REPORT = """Department of Real Estate
FINAL SUBDIVISION PUBLIC REPORT
In the matter of the application of EXAMPLE COMMUNITIES LLC, FILE NO.: 999006SA-F00
ISSUED: AUGUST 5, 2020
EXPIRES: AUGUST 4, 2025
Real Estate
Under the built-out budget, monthly assessment against each condominium unit will be $168.15. Under the 6th phase budget, the
monthly assessment per interest is $173.35. Of these amounts, the monthly contributions toward long-term reserves are not to be used
to pay for current management, maintenance and operating expenses are $15.25 and $18.20, respectively. Your Condominium Unit will
also be subject to a Cost Center budget. Under the Cost Center built-out budget, monthly assessment against each condominium unit
will be $116.60. Under the 6th phase Cost Center budget, the monthly assessment per interest is $116.90. Of these amounts, the
monthly contributions toward long-term reserves are not to be used to pay for current management, maintenance and operating
expenses are $54.75 and $54.85, respectively.
"""


def test_public_report_reserve_contributions_by_budget():
    r = read(DocumentKind.DRE_REPORT, REPORT, ctx("999006SA-F00.pdf")).record
    assert (r.built_out_assessment_cents, r.phase_assessment_cents) == (16_815, 17_335)
    assert (r.built_out_reserve_cents, r.phase_reserve_cents) == (1_525, 1_820)
    assert (r.cost_center_assessment_cents, r.cost_center_phase_assessment_cents) == (11_660, 11_690)
    assert (r.cost_center_reserve_cents, r.cost_center_phase_reserve_cents) == (5_475, 5_485)


# A mechanic's lien release bond.

BOND = """SPACE DIRECTLY ABOVE RESERVED FOR RECORDER'S USE
BOND FOR RELEASE OF MECHANIC'S LIEN
That we, Example Builders LLC as Principal and Example Surety Company, a corporation organized and existing under the laws of the
State of Ohio, as Surety, are held and firmly bound unto Example Lumber Company, Inc. Obligee, in the sum of One Thousand Five
Hundred & 00/100 lawful money. WHEREAS a claim of mechanic's lien in the amount of One Thousand & 00/100 ($1,000.00) was recorded
in the office of the County Recorder of Sacramento County, State of California, on March 1, 2022.
"""


def test_release_bond_keeps_the_names_recording_date():
    reading = read(DocumentKind.RECORDED_LIEN, BOND, ctx("BOND FOR RELEASE OF LIEN 202205031077.pdf"))
    r = reading.record
    assert (r.document_number, r.recorded, r.document_number_from_name) == ("202205031077", date(2022, 5, 3), True)
    assert "document-number-from-name" in codes(reading)


def test_layers_split_at_the_librarys_end_marker():
    from jason.community.models.governing_deeds import layers

    text = "--- ocr: ollama-vision ---\nDoc# 202001170712\nGRANT DEED\n--- end ocr: ollama-vision ---\n\nDoc# 2O2OO117O712\nGRANT DEED\npage 2"
    assert layers(text) == ("Doc# 202001170712\nGRANT DEED\n", "Doc# 2O2OO117O712\nGRANT DEED\npage 2")
    assert layers("GRANT DEED") == ("", "GRANT DEED")


def test_a_vision_readings_table_layout_gives_the_public_reports_subdivider():
    text = ("STATE OF CALIFORNIA\nDEPARTMENT OF REAL ESTATE\nSUBDIVISION PUBLIC REPORT\nSUBDIVISION INFORMATION | For DRE Use Only\n"
            "NAME OF SUBDIVIDER (SELLER) | DRE FILE NUMBER\nExample Homes LLC, a California limited liability company | 100000SA-S00\n"
            "TRACT OR MAP NAME AND NUMBER | ISSUANCE DATE\nExample Tract | March 20, 2020\n")
    reading = read(DocumentKind.DRE_REPORT, text, ctx("100000SA-S00.pdf"))
    assert reading is not None and reading.record.subdivider == "Example Homes LLC"
