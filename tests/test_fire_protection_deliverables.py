"""Title 19 deliverables: a term promising one is matched to the rule that requires it."""

from __future__ import annotations

from jason.community.fire_protection import DELIVERABLE_RULES, deliverable_rule


def key(quote):
    rule = deliverable_rule(quote)
    return rule.key if rule else None


def test_report_to_the_fire_authority():
    assert key("The contractor shall provide a written report of the test results to the owner and the local fire "
               "authority having jurisdiction.") == "report-to-owner-and-fire-authority"
    assert deliverable_rule("Send a copy of each report to the fire department within 10 days.").authority == "19 CCR 904.2(j)"


def test_aes_forms_and_inspection_reports():
    assert key("T.E.F.S.C. shall utilize the new Inspection Testing & Maintenance Reports (annex B).") == "aes-forms"
    assert key("Results shall be recorded on form AES 2.1.") == "aes-forms"
    assert key("Inspection reports shall be filled out and shall indicate the condition of the system.") == "inspection-report"


def test_invoice_estimate_tag_and_notice():
    assert key("You will deliver an itemized invoice after each visit.") == "itemized-invoice"
    assert key("An invoice showing the work performed and parts replaced will be provided.") == "itemized-invoice"
    assert key("A written estimate shall be given before any repairs are made.") == "repair-estimate"
    assert key("Systems shall be properly tagged with the date and technician once all deficiencies are corrected.") == "service-tag"
    assert key("The contractor shall contact the fire department before testing the system.") == "notice-to-fire-authority"


def test_unrelated_terms_match_nothing():
    assert deliverable_rule("Association shall pay Manager a monthly fee of $1,500.") is None
    assert deliverable_rule("We will mow, edge, and blow all turf areas weekly.") is None
    assert deliverable_rule("") is None


def test_rows_are_well_formed():
    keys = [r.key for r in DELIVERABLE_RULES]
    assert len(keys) == len(set(keys))
    assert all(r.authority.startswith("19 CCR") and r.recipient and r.when for r in DELIVERABLE_RULES)
