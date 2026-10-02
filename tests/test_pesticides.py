"""Pesticide products: the registration number, EPA's and California's records, and the safety data sheet reading."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from jason.community.pesticides import EpaNumber, Registration, names_product, read_sds, sds_sections

SDS = """Safety Data Sheet
SECTION 1: IDENTIFICATION
Product Name:
Dominion 2L
EPA Registration No.: 53883-229
FOR MEDICAL EMERGENCIES CONTACT: Safety Call 1-866-897-8050
SECTION 2: HAZARD(S) IDENTIFICATION
Signal Word:
WARNING
Hazard Statement(s):
H302
Harmful if swallowed.
H400
Very toxic to aquatic life.
Precautionary Statement(s):
Prevention: wear gloves.
SECTION 4: FIRST AID MEASURES
IF SWALLOWED:
Call a poison control center or doctor immediately for treatment advice.
IF ON SKIN:
Rinse skin immediately with plenty of water for 15 to 20 minutes.
SECTION 12: ECOLOGICAL INFORMATION
This product is highly toxic to aquatic invertebrates. This product is highly toxic to bees exposed to direct treatment.
SECTION 15: REGULATORY INFORMATION
CALIFORNIA PROPOSITION 65: none listed
Revision Date: October 30, 2024
"""


def test_registration_numbers_keep_epa_and_california_apart() -> None:
    alpine = EpaNumber.parse("499-561-ZA")
    assert (alpine.epa, alpine.california, alpine.key) == ("499-561", "499-561-ZA", "499-561")
    assert EpaNumber.parse("EPA Reg. No. 499- 561-ZA").california == "499-561-ZA"
    assert EpaNumber.parse("53883-118-73220").epa == "53883-118"
    exempt = EpaNumber.parse("EPA EXEMPT")
    assert exempt.exempt and not exempt.registered and exempt.key == "epa-exempt"
    assert not EpaNumber.parse("N/A").registered


def test_ppls_record_takes_the_newest_label_by_its_accepted_date() -> None:
    item = {"eparegno": "101563-143", "productname": "SUSPEND POLYZONE", "product_status": "Active", "signal_word": "Caution ",
            "rup_yn": "N", "companyinfo": [{"name": "ENVU"}], "active_ingredients": [{"active_ing": "Deltamethrin", "active_ing_percent": "4.75"}],
            "altbrandnames": [{"altbrandname": "SUSPEND POLYZONE  "}],
            "pdffiles": [{"pdffile": "101563-00143-20240101.pdf", "pdffile_accepted_date": "January 1, 2014"},
                         {"pdffile": "000432-01514-20160920.pdf", "pdffile_accepted_date": "September 20, 2016"}]}
    reg = Registration.from_ppls(item)
    assert reg.label_file == "000432-01514-20160920.pdf" and reg.label_date == date(2016, 9, 20)
    assert reg.signal_word == "Caution" and not reg.restricted_use and reg.brand_names == ("SUSPEND POLYZONE",)


def test_the_sds_reading_gives_what_a_board_needs() -> None:
    assert sorted(sds_sections(SDS)) == [1, 2, 4, 12, 15]
    reading = read_sds(SDS)
    assert reading.product == "Dominion 2L" and reading.revised == "October 30, 2024" and reading.signal_word == "Warning"
    assert reading.hazards == (("H302", "Harmful if swallowed."), ("H400", "Very toxic to aquatic life."))
    assert reading.first_aid["swallowed"].startswith("Call a poison control center")
    assert "1-866-897-8050" in reading.emergency
    assert any("bees" in e for e in reading.ecology) and reading.prop65.startswith("CALIFORNIA PROPOSITION 65")
    unclassified = read_sds("1. Identification\nProduct Name: Selontra\n2. Hazards Identification\nNo need for classification "
                            "according to GHS criteria for this product.\n")
    assert unclassified.signal_word == "Not classified"
    assert names_product("Dominion 2L", "DOMINION FOR GENERAL PEST") and not names_product("Termidor NY", "TERMIDOR SC")


def test_fetch_product_records_both_registrations_and_keeps_the_right_sheet(tmp_path: Path) -> None:
    pymupdf = pytest.importorskip("pymupdf")
    from jason.tasks.pesticides import fetch_product

    doc = pymupdf.open()
    page = doc.new_page()
    y = 40
    for line in SDS.splitlines():
        page.insert_text((40, y), line, fontsize=8)
        y += 10
    sds_pdf = doc.tobytes()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "ordspub.epa.gov" in url:
            return httpx.Response(200, json={"items": [{"eparegno": "53883-229", "productname": "IMI 2 LB", "product_status": "Active",
                                                        "signal_word": "Caution", "rup_yn": "N", "pdffiles": [
                                                            {"pdffile": "053883-00229-20240425.pdf", "pdffile_accepted_date": "April 25, 2024"}]}]})
        if "calpestsearch" in url:
            return httpx.Response(200, json=[{"registrationnumber": "53883-229-AA", "name": "DOMINION 2L", "status": "Active",
                                              "firstregistrationdate": "2012-01-01T00:00:00"}])
        if url.endswith(".pdf"):
            return httpx.Response(200, content=sds_pdf if "MSDS" in url else b"%PDF-1.4 label")
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        record, downloaded, _present, problems = fetch_product(http, tmp_path, "DOMINION FOR GENERAL PEST", "53883-229")
    assert problems == [] and downloaded == 3
    assert record["registration"]["name"] == "IMI 2 LB" and record["californiaRegistration"]["number"] == "53883-229-AA"
    assert record["sds"]["product"] == "Dominion 2L" and record["labelFile"] == "label-epa-2024-04-25.pdf"
    assert json.loads((tmp_path / "53883-229" / "product.json").read_text(encoding="utf-8"))["sdsFile"] == "sds.pdf"
