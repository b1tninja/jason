"""Page noise: e-signature audit pages, page numbers, and running lines dropped whole; form feeds and first copies kept."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community.page_noise import strip_noise

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def kinds(removed):
    return {r["kind"]: r for r in removed}


def test_docusign_certificate_page_is_dropped_with_nothing_before_it():
    text = (FIXTURES / "01_monitoring_second_person.txt").read_text(encoding="utf-8")
    clean, removed = strip_noise(text)
    assert "Certificate Pages: 5" not in clean and "Envelope Id" not in clean
    assert "We will provide you a written inspection report" in clean
    assert "In no event shall our liability exceed" in clean
    audit = kinds(removed)["esign-audit"]
    assert audit["text"].startswith("Certificate Of Completion") and audit["count"] >= 5


def test_adobe_final_audit_report_and_its_title_line_are_dropped():
    text = (FIXTURES / "02_sprinkler_proposal_bullets.txt").read_text(encoding="utf-8")
    clean, removed = strip_noise(text)
    assert "Transaction ID" not in clean and "Final Audit Report" not in clean
    assert "Fire Sprinkler Inspection Proposal (2026)\n" not in clean
    assert "Example Director (Apr 16, 2026 23:11 PDT)" in clean       # the signature itself stays
    assert "T.E.F.S.C. shall utilize" in clean


def test_audit_heading_without_markers_is_kept():
    text = "1. Services.\nCertificate of Completion\nThe contractor shall deliver a certificate of completion.\n"
    clean, removed = strip_noise(text)
    assert clean == text and removed == []


def test_page_numbers_go_and_are_grouped_by_shape():
    text = (FIXTURES / "03_roof_repair_letterhead.txt").read_text(encoding="utf-8")
    clean, removed = strip_noise(text)
    assert "Page 2 of 4" not in clean and "Page 4 of 4" not in clean
    pages = kinds(removed)["page-number"]
    assert pages["count"] == 3 and pages["text"] == "Page 2 of 4"


def test_form_footer_inside_a_sentence_is_cut_and_the_sentence_joined():
    text = (FIXTURES / "04_management_agreement.txt").read_text(encoding="utf-8")
    clean, removed = strip_noise(text)
    assert "Manager shall have no authority to execute or enter into contracts" in clean
    assert "Version 3.33" not in clean and "Page 3 of 22" not in clean
    assert removed == [{"kind": "form-footer", "text": "Page 3 of 22 Version 3.33 BK, Revised 1/1/2022", "count": 1,
                        "row": "page-then-stamp"}]
    assert clean.count("\n") == text.count("\n")


def test_running_header_on_each_page_is_kept_once_and_form_feeds_survive():
    header = "Sample Alarm Services, Inc. | C10 600001 | www.samplealarm.example"
    pages = [f"{header}\nSection {i}. The customer shall pay the fee.\nPage {i} of 3" for i in (1, 2, 3)]
    clean, removed = strip_noise("\f".join(pages))
    assert clean.count("\f") == 2
    assert clean.count(header) == 1 and clean.startswith(header)
    assert clean.count("The customer shall pay the fee.") == 3        # a line with a term is never a running line
    found = kinds(removed)
    assert found["repeated-line"]["count"] == 2 and found["page-number"]["count"] == 3


def test_a_line_repeated_twice_is_not_a_running_line():
    text = "Customer: Example Community Association\nTerms\nCustomer: Example Community Association\n"
    clean, removed = strip_noise(text)
    assert clean == text and removed == []


# --- Form footers: a page count with the form's version or revision stamp, cut wherever it sits ----------------------


def _expected_noise():
    data = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    for name, row in data.items():
        if name.startswith("_"):
            continue
        for words in {**row.get("expect", {}), **row.get("open", {})}.get("noise_excluded", []):
            yield name, words


@pytest.mark.parametrize("name,words", list(_expected_noise()))
def test_expected_noise_rows_are_stripped(name, words):
    clean, _ = strip_noise((FIXTURES / name).read_text(encoding="utf-8"))
    assert " ".join(words.split()).lower() not in " ".join(clean.split()).lower()


def test_form_footer_and_its_repeats_go_on_their_own_lines_and_inside_sentences():
    footer = "Page {} of 3 Version 2.1 XY, Revised 3/15/2024"
    text = "\f".join([
        f"1. The contractor shall clean the gutters.\n{footer.format(1)}",
        f"2. The contractor shall {footer.format(2)} haul away debris.\n",
        f"{footer.format(3)}\n3. The owner shall pay on receipt.",
    ])
    clean, removed = strip_noise(text)
    assert "Version 2.1" not in clean and "Revised 3/15/2024" not in clean
    assert "2. The contractor shall haul away debris." in clean
    assert clean.count("\f") == 2
    footers = kinds(removed)["form-footer"]
    assert footers["count"] == 3 and footers["text"] == footer.format(1)


def test_stamp_before_the_page_count_is_cut_too():
    text = "Rev. 4 AB, Revised 01/2023 Page 2 of 9\nThe vendor shall carry insurance.\n"
    clean, removed = strip_noise(text)
    assert clean == "The vendor shall carry insurance.\n"
    assert kinds(removed)["form-footer"]["row"] == "stamp-then-page"


def test_footer_cut_keeps_indent_and_the_following_word():
    clean, _ = strip_noise("    Page 1 of 2 Version 1.0 the Board shall meet.")
    assert clean == "    the Board shall meet."      # a lowercase word after the version is not a form code


@pytest.mark.parametrize("text", [
    "The rules were adopted and as revised on 1/1/2022 by the Board remain in force.\n",
    "Version 2 of the reserve study is attached as Exhibit B.\n",
    "The form was Revised 1/1/2022 and Version 3.33 is current.\n",
    "See Page 3 of 22 of the reserve study for the component list.\n",
    "Exhibit A, Page 3 of 22, lists the version of the plans revised by the architect.\n",
])
def test_version_or_revision_in_contract_words_is_kept(text):
    clean, removed = strip_noise(text)
    assert clean == text and removed == []


def test_a_plans_revision_cited_in_a_sentence_is_kept():
    text = "The fee schedule (see Page 2 of 5 Rev. 3 of the attached plans) applies.\n"
    assert strip_noise(text)[0] == text


def test_a_sentence_opening_after_a_footer_keeps_its_first_word():
    clean, removed = strip_noise("Page 1 of 2 Version 1.0 A contractor shall keep the site clean.\n")
    assert clean.strip() == "A contractor shall keep the site clean." and removed
