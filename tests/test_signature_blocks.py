"""Signature blocks: the fixtures' open "signature" rows, each fixture's blocks, made-up layouts, and near misses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jason.community.signature_blocks import BlockKind, SignatureBlock, iso_date, signature_blocks, signed_by

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _signature_rows() -> list[tuple[str, dict]]:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    rows = []
    for name, entry in expected.items():
        if not isinstance(entry, dict) or name.startswith("_"):
            continue
        merged = {**entry.get("expect", {}), **entry.get("open", {})}
        if "signature" in merged:
            rows.append((name, merged["signature"]))
    return rows


@pytest.mark.parametrize(("name", "row"), _signature_rows())
def test_fixture_signature_rows(name, row):
    signed = signed_by(signature_blocks(_text(name)))
    assert signed, f"{name}: no signed block"
    first = signed[0]
    assert {"signer": first.signer, "title": first.title, "date": first.date} == row


def test_rows_found():
    assert _signature_rows(), "expected.json has no signature row"


def _shape(blocks: list[SignatureBlock]) -> list[tuple]:
    return [(b.party_words, b.signer, b.title, b.date, b.signed, b.kind) for b in blocks]


def test_e_signature_stamp_fills_the_blank_form_and_the_audit_trail_is_not_repeated():
    blocks = signature_blocks(_text("02_sprinkler_proposal_bullets.txt"))
    assert _shape(blocks) == [("", "Example Director", "Board member", "2026-04-16", True, BlockKind.FORM)]
    # The audit trail's "By: Pat Example" is the sender, never a signer.
    assert all(b.signer != "Pat Example" for b in blocks)


def test_unsigned_copies_and_a_certificate_signer():
    blocks = signature_blocks(_text("01_monitoring_second_person.txt"))
    assert _shape(blocks) == [
        ("Customer", "", "", "", False, BlockKind.FORM),
        ("Customer", "", "", "", False, BlockKind.FORM),
        ("", "Example Director", "", "2026-01-02", True, BlockKind.AUDIT),
    ]


def test_letterhead_blanks():
    assert _shape(signature_blocks(_text("03_roof_repair_letterhead.txt"))) == [
        ("Owner or Agent", "", "", "", False, BlockKind.FORM),
        ("Example Home Services", "", "", "", False, BlockKind.FORM),
    ]


def test_role_labels_and_trailing_titles():
    assert _shape(signature_blocks(_text("04_management_agreement.txt"))) == [
        ("Example Community Association", "", "President", "", False, BlockKind.FORM),
        ("Sample Management, Inc.", "", "Chief Executive", "", False, BlockKind.FORM),
    ]


def test_party_line_above_and_bare_title_below():
    blocks = signature_blocks(_text("05_landscape_signature_block.txt"))
    assert _shape(blocks) == [
        ("Example Landscape Services, Inc.", "", "President", "", False, BlockKind.FORM),
        ("", "", "", "", False, BlockKind.FORM),
    ]
    # "Initial ______" is not a signing side.
    assert all("Initial" not in b.party_words for b in blocks)


def test_no_block():
    assert signature_blocks(_text("06_implementation_role_labels.txt")) == []


def test_accepted_with_party_parenthetical():
    assert _shape(signature_blocks(_text("07_paving_extra_work.txt"))) == [("Owner", "", "", "", False, BlockKind.FORM)]


def test_two_sides_on_one_line():
    assert _shape(signature_blocks(_text("08_association_drafted_we.txt"))) == [
        ("Association", "", "", "", False, BlockKind.FORM),
        ("Contractor", "", "", "", False, BlockKind.FORM),
    ]


def test_filled_fields_on_one_line():
    text = "Agreed.\n\nBy: /s/ Jane Example   Name: Jane Example   Title: Treasurer   Date: 04/16/2026\n"
    assert _shape(signature_blocks(text)) == [("", "Jane Example", "Treasurer", "2026-04-16", True, BlockKind.FORM)]


def test_filled_fields_on_lines():
    text = ("Example Roofing, Inc.\nBy: Pat Sample\nName: Pat Sample\nTitle: Owner\nDate: 3/2/26\n\n"
            "Example Community Association\nBy: ______________\nName: ______________\nTitle: ______________\n")
    assert _shape(signature_blocks(text)) == [
        ("Example Roofing, Inc.", "Pat Sample", "Owner", "2026-03-02", True, BlockKind.FORM),
        ("Example Community Association", "", "", "", False, BlockKind.FORM),
    ]


def test_parenthetical_field_names():
    text = "ACCEPTED: Jane Example (signature)  Jane Example (print name)  April 2, 2026 (date)\n"
    assert _shape(signature_blocks(text)) == [("", "Jane Example", "", "2026-04-02", True, BlockKind.FORM)]
    blank = "ACCEPTED: ______________ (signature) ______________ (print name)\n"
    assert _shape(signature_blocks(blank)) == [("", "", "", "", False, BlockKind.FORM)]


def test_printed_name_without_signature_is_unsigned():
    text = "Owner's Signature: ____________  Print Name: Jane Example  Date: ________\n"
    assert _shape(signature_blocks(text)) == [("Owner", "Jane Example", "", "", False, BlockKind.FORM)]


def test_name_and_title_split():
    text = "By: Jane Example\nName & Title: Jane Example, Board President\n"
    assert _shape(signature_blocks(text)) == [("", "Jane Example", "Board President", "", True, BlockKind.FORM)]


def test_stamp_with_no_form_stands_alone():
    text = "Scope as above.\n\nJane Example (Mar 3, 2026 09:15 PST)\n"
    assert _shape(signature_blocks(text)) == [("", "Jane Example", "", "2026-03-03", True, BlockKind.E_SIGNATURE)]


def test_stamp_too_far_from_the_form_does_not_fill_it():
    filler = "\n".join(f"Line {i} of the terms." for i in range(30))
    text = f"Customer signature ____________ Date ______\n{filler}\nJane Example (Mar 3, 2026 09:15 PST)\n"
    assert _shape(signature_blocks(text)) == [
        ("Customer", "", "", "", False, BlockKind.FORM),
        ("", "Jane Example", "", "2026-03-03", True, BlockKind.E_SIGNATURE),
    ]


@pytest.mark.parametrize("text", [
    "The proposal was accepted by the Board at its meeting.\n",
    "This Agreement is signed by both parties and dated as of the date below.\n",
    "Date: 03/01/2026\nRe: Example Proposal\n",
    "Title: Pool Service Proposal\nPrepared for the Board.\n",
    "Name: Example Community Association\nAddress: 123 Main St\n",
    "Initial ______\n",
    "Annual Meeting (Apr 16, 2026)\n",
    "Sincerely,\nEXAMPLE ROOFING, INC.\nPat Sample\nEstimator\n",
])
def test_near_misses(text):
    assert signature_blocks(text) == []


@pytest.mark.parametrize("text", [
    "Prepared By: Sam Estimator\nScope of Work\nDate: 03/01/2026\n",
    "Scope of Work\nPrepared By: Sam Estimator\nDate: 03/01/2026\n",
    "Submitted by: Example Roofing, Inc.\n",
    "Inspected by: J. Smith\n",
    "Sold by: Pat Sample\n",
    "Quoted by: Pat Sample\n",
    "Estimated By: Pat Sample\n",
    "Reviewed by: Pat Sample\n",
    "Approved as to form by: Pat Sample\n",
    "Sent by: Pat Sample\n",
    "Installed by: Example Crew\n",
    "Work at the clubhouse was done by: the crew\n",
])
def test_by_label_that_is_not_a_signature(text):
    assert signature_blocks(text) == []


@pytest.mark.parametrize(("text", "shape"), [
    ("By: Pat Sample\nOwner\n", [("", "Pat Sample", "Owner", "", True, BlockKind.FORM)]),
    ("CONTRACTOR By: Pat Sample\n", [("CONTRACTOR", "Pat Sample", "", "", True, BlockKind.FORM)]),
    ("Customer By: ____________\n", [("Customer", "", "", "", False, BlockKind.FORM)]),
    ("Approved by: Pat Sample\n", [("", "Pat Sample", "", "", True, BlockKind.FORM)]),
])
def test_by_label_near_misses_still_read(text, shape):
    assert _shape(signature_blocks(text)) == shape


def test_printed_name_under_the_signature_is_not_the_title():
    text = "By: Sam Estimator\nSam Estimator\nOwner\n"
    assert _shape(signature_blocks(text)) == [("", "Sam Estimator", "Owner", "", True, BlockKind.FORM)]
    other = "By: Sam Estimator\nTreasurer\n"
    assert _shape(signature_blocks(other)) == [("", "Sam Estimator", "Treasurer", "", True, BlockKind.FORM)]


def test_audit_sender_is_not_a_block():
    text = "Final Audit Report 2026-04-17\nCreated: 2026-04-17\nBy: Pat Example (pat@example.test)\nStatus: Signed\n"
    assert signature_blocks(text) == []


def test_adobe_audit_signer_alone():
    text = ("Terms.\n\nFinal Audit Report 2026-04-17\nDocument e-signed by Jane Example (jane@example.test)\n"
            "Signature Date: 2026-04-17 - 6:11:02 AM GMT - Time Source: server\n")
    assert _shape(signature_blocks(text)) == [("", "Jane Example", "", "2026-04-17", True, BlockKind.AUDIT)]


@pytest.mark.parametrize(("written", "iso"), [
    ("04/16/2026", "2026-04-16"),
    ("4/6/26", "2026-04-06"),
    ("2026-04-16", "2026-04-16"),
    ("Apr 16, 2026", "2026-04-16"),
    ("April 16 2026", "2026-04-16"),
    ("16 April 2026", "2026-04-16"),
    ("13/40/2026", ""),
    ("________", ""),
    ("next Tuesday", ""),
])
def test_iso_date(written, iso):
    assert iso_date(written) == iso
