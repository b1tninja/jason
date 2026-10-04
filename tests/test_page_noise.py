"""Page noise: e-signature audit pages, page numbers, and running lines dropped whole; form feeds and first copies kept."""

from __future__ import annotations

from pathlib import Path

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


def test_footer_inside_a_sentence_is_left_alone():
    text = (FIXTURES / "04_management_agreement.txt").read_text(encoding="utf-8")
    clean, removed = strip_noise(text)
    assert "Manager shall have no Page 3 of 22 Version 3.33 BK, Revised 1/1/2022 authority" in clean
    assert removed == []


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
