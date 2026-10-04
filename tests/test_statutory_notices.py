"""Statutory notices: each found by its opening phrase, its span ending at the notice's end, its statute named."""

from __future__ import annotations

from pathlib import Path

from jason.community.statutory_notices import NOTICES, find_notices

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"

HOME_IMPROVEMENT = """Scope of Work
1. Replace the fence along the east property line.

MECHANICS LIEN WARNING:
Anyone who helps improve your property, but who is not paid, may record what is called a mechanics lien on your property.
A mechanics lien is a claim, like a mortgage or home equity loan, made against your property and recorded with the county recorder.


Information about the Contractors State License Board (CSLB): CSLB is the state consumer protection agency that licenses and regulates construction contractors.
Contact CSLB for information about the licensed contractor you are considering.

Three-Day Right to Cancel
You, the buyer, have the right to cancel this contract within three business days.
If you cancel, the contractor must return to you anything you paid within 10 days of receiving the notice of cancellation.

2. Payment. The Owner shall pay the balance upon completion.
THE DOWNPAYMENT MAY NOT EXCEED $1,000 OR 10 PERCENT OF THE CONTRACT PRICE, WHICHEVER IS LESS.
"""


def spans(text):
    return {n.key: text[s:e] for n, s, e in find_notices(text)}


def test_each_notice_is_found_with_its_statute():
    found = find_notices(HOME_IMPROVEMENT)
    keys = [n.key for n, _, _ in found]
    assert keys == ["mechanics-lien-warning", "cslb-information", "right-to-cancel", "downpayment"]
    authority = {n.key: n.authority for n, _, _ in found}
    assert authority["mechanics-lien-warning"] == "BPC 7159(e)(4)" and authority["cslb-information"] == "BPC 7159(e)(5)"


def test_a_notice_ends_where_its_text_ends():
    s = spans(HOME_IMPROVEMENT)
    assert "recorded with the county recorder" in s["mechanics-lien-warning"]
    assert "Information about the Contractors" not in s["mechanics-lien-warning"]
    assert "notice of cancellation" in s["right-to-cancel"]                 # inside the notice, not a second one
    assert "The Owner shall pay the balance" not in s["right-to-cancel"]    # a numbered section ends it
    assert "notice-of-cancellation" not in s


def test_the_contract_terms_outside_notices_are_left_out():
    text = HOME_IMPROVEMENT
    covered = [(st, en) for _, st, en in find_notices(text)]
    position = text.index("Replace the fence")
    assert not any(st <= position < en for st, en in covered)


def test_fixture_notices_are_found():
    text = (FIXTURES / "03_roof_repair_letterhead.txt").read_text(encoding="utf-8")
    s = spans(text)
    assert set(s) == {"mechanics-lien-notice-to-owner", "cslb-information"}   # its arbitration clause has no statutory heading
    assert "Its purpose is to notify you of persons who may have a right to file a lien" in s["mechanics-lien-notice-to-owner"]
    assert "CSLB is the state consumer protection agency" in s["cslb-information"]
    assert "Signed:" not in s["cslb-information"]


def test_apostrophes_and_spacing_are_tolerated():
    text = "NOTICE TO OWNER\nUnder the California Mechanics’ Lien Law, any contractor who is not paid may record a lien.\n"
    assert [n.key for n, _, _ in find_notices(text)] == ["mechanics-lien-notice-to-owner"]


def test_a_notice_in_capitals_runs_to_its_signature_line():
    text = ("ARBITRATION OF DISPUTES\n"
            "NOTICE: BY INITIALING IN THE SPACE BELOW YOU ARE AGREEING TO HAVE ANY DISPUTE DECIDED BY NEUTRAL ARBITRATION.\n"
            "BY INITIALING YOU ARE GIVING UP YOUR RIGHTS.\n"
            "By: ________ (Owner)\n")
    s = spans(text)
    assert "GIVING UP YOUR RIGHTS" in s["arbitration-of-disputes"] and "(Owner)" not in s["arbitration-of-disputes"]


def test_no_notice_in_an_ordinary_contract():
    text = (FIXTURES / "04_management_agreement.txt").read_text(encoding="utf-8")
    assert find_notices(text) == []


def test_rows_are_well_formed():
    keys = [n.key for n in NOTICES]
    assert len(keys) == len(set(keys))
    assert all(n.opens and n.authority and n.title for n in NOTICES)
