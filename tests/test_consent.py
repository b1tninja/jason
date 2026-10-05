"""Consents and releases, read from the made-up contract fixtures and a few made-up sentences."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from jason.community.consent import Consent, Release, consent_of, find_consents, find_releases, release_of
from jason.community.discretion import holds

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"

# Who each fixture's counterparty is, as its sentences name it.
COUNTERPARTY = {
    "08_association_drafted_we.txt": ("you", "Contractor"),
}


def _sentence(fixture: str, contains: str) -> str:
    text = " ".join((FIXTURES / fixture).read_text(encoding="utf-8").split())
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text):
        if contains.lower() in sentence.lower():
            return sentence
    raise AssertionError(f"{contains!r} not in {fixture}")


def _rows(key: str) -> list[tuple[str, dict]]:
    expected = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    return [
        (fixture, row)
        for fixture, entry in expected.items()
        if isinstance(entry, dict)
        for part in ("expect", "open")
        for row in entry.get(part, {}).get(key, [])
    ]


@pytest.mark.parametrize(("fixture", "row"), _rows("consent_release"), ids=lambda v: v if isinstance(v, str) else v["contains"])
def test_fixture_consent_rows(fixture, row):
    c = consent_of(_sentence(fixture, row["contains"]))
    assert c is not None
    assert row["contains"].lower() in c.cue.lower()
    label = "counterparty" if holds(c.holder_words, COUNTERPARTY[fixture]) else "association"
    assert label == row["holder"]


def test_fixture_rows_are_covered():
    assert len(_rows("consent_release")) >= 1


def test_fixture_08_reading():
    c = consent_of(_sentence("08_association_drafted_we.txt", "without our prior written consent"))
    assert c == Consent("without our prior written consent", "our", True, True, "")


def test_fixture_08_finds_one_consent_and_no_release():
    text = (FIXTURES / "08_association_drafted_we.txt").read_text(encoding="utf-8")
    assert [c.holder_words for c in find_consents(text)] == ["our"]
    assert find_releases(text) == ()


def test_fixture_unnamed_approvals():
    later = consent_of(_sentence("03_roof_repair_letterhead.txt", "repaired after approval"))
    assert later is not None and (later.holder_words, later.over, later.written) == ("", "extra work", False)
    client = consent_of(_sentence("05_landscape_signature_block.txt", "to be approved by client"))
    assert client is not None and client.holder_words == "client"
    assert consent_of(_sentence("02_sprinkler_proposal_bullets.txt", "approved tags")) is None


@pytest.mark.parametrize(
    ("sentence", "holder", "written", "prior", "over"),
    [
        ("Contractor may not assign this Agreement without the consent of the other party.",
         "the other party", False, False, "assignment"),
        ("Any change order is subject to the Board's approval.", "the Board", False, False, "extra work"),
        ("Contractor may subcontract the work only with the Association's written approval.",
         "the Association", True, False, "subcontracting"),
        ("No changes to the specifications are permitted unless approved in writing by Owner.",
         "Owner", True, False, "changes"),
        ("Vendor shall not enter any unit without the prior written consent of the Manager.",
         "the Manager", True, True, "entry"),
        ("Extra work must be approved in writing by the Association before it begins.",
         "the Association", True, False, "extra work"),
        ("You will not paint the doors without our prior written consent.", "our", True, True, ""),
        ("Additional visits require the written authorization of Example Property Management, Inc.",
         "Example Property Management, Inc.", True, False, "extra work"),
        ("Contractor shall not substitute materials without prior written approval.", "", True, True, "changes"),
    ],
)
def test_made_up_consents(sentence, holder, written, prior, over):
    c = consent_of(sentence)
    assert c is not None
    assert (c.holder_words, c.written, c.prior, c.over) == (holder, written, prior, over)


@pytest.mark.parametrize(
    "sentence",
    [
        "The Board approved the minutes of the prior meeting.",
        "Contractor shall complete the work at 123 Main St by June 1.",
        "Either party may terminate this Agreement with thirty (30) days written notice.",
        "Technicians will attach approved tags to each device.",
        "The Association consents to service of process by mail.",
        "Payment is due upon completion of the work.",
        # Problem 2: approval of a document accepts it; it gates nothing on anyone's word.
        "Work begins upon approval of this proposal.",
        "Contractor will order materials after approval of the estimate.",
        # Problem 3: a cue followed by a past-tense main verb is history.
        "With the approval of the members, the Association adopted the parking rules.",
        "The Association, with the consent of the members, amended the bylaws.",
        # Problem 1: a lowercase noun before "approval" is not a holder, and nothing else gates.
        "The Board noted general approval of the plan.",
    ],
)
def test_made_up_sentences_that_are_not_consents(sentence):
    assert consent_of(sentence) is None


@pytest.mark.parametrize(
    ("sentence", "holder", "written", "prior", "over"),
    [
        # Problem 1: an unmarked capitalised noun before approval or consent is the holder.
        ("Contractor shall not subcontract without Association approval.", "Association", False, False, "subcontracting"),
        ("Contractor shall not assign this Agreement without Board approval.", "Board", False, False, "assignment"),
        ("Subject to Owner approval, Contractor may substitute materials.", "Owner", False, False, "changes"),
        ("Vendor shall not enter a unit without Example Property Management written consent.",
         "Example Property Management", True, False, "entry"),
        # Near miss: a qualifier is not a holder.
        ("Contractor shall not substitute materials without Prior Written approval.", "", True, True, "changes"),
        # Problem 2: the party follows the object.
        ("Payment is due upon approval of the invoice by the Board.", "the Board", False, False, ""),
        ("Extra work may proceed upon approval of the change order by Owner.", "Owner", False, False, "extra work"),
        # Near miss: a party whose name holds an object word is still a party.
        ("Contractor may not assign without the consent of the Contractor Services Group.",
         "the Contractor Services Group", False, False, "assignment"),
        # Problem 2: a later cue in the same sentence still reads.
        ("Upon approval of this proposal, Contractor shall not subcontract without the Board's consent.",
         "the Board", False, False, "subcontracting"),
        # Problem 3: the possessive is stripped; the words are otherwise as written.
        ("Contractor shall not assign this Agreement without Owner's consent.", "Owner", False, False, "assignment"),
        ("Vendor shall not enter without the Members’ prior written consent.", "the Members", True, True, "entry"),
        # Near miss for the narrative: a present-tense gate after the comma still reads.
        ("With the approval of the Board, Contractor shall replace the gutters.", "the Board", False, False, ""),
        ("Without Board approval, any work performed shall be at Contractor's cost.", "Board", False, False, ""),
    ],
)
def test_holder_problems(sentence, holder, written, prior, over):
    c = consent_of(sentence)
    assert c is not None
    assert (c.holder_words, c.written, c.prior, c.over) == (holder, written, prior, over)


@pytest.mark.parametrize(
    ("sentence", "releasor", "released", "over"),
    [
        ("Owner hereby releases the Association from any liability for damage to personal property.",
         "Owner", "the Association", "liability"),
        ("Contractor waives any claim against the Association arising from delay.",
         "Contractor", "the Association", "claims"),
        ("Each party waives all rights of subrogation against the other party.",
         "Each party", "the other party", "subrogation"),
        ("Vendor shall not hold the Association liable for theft of tools left on site.",
         "Vendor", "the Association", "liability"),
    ],
)
def test_made_up_releases(sentence, releasor, released, over):
    r = release_of(sentence)
    assert r is not None
    assert (r.releasor_words, r.released_words, r.over) == (releasor, released, over)


@pytest.mark.parametrize(
    "sentence",
    [
        "Contractor shall deliver a conditional release of lien with each invoice.",
        "Open the pressure release valve before draining the system.",
        "Contractor will release the hold from the account after payment.",
        "The press release will be posted on the website.",
    ],
)
def test_made_up_sentences_that_are_not_releases(sentence):
    assert release_of(sentence) is None


def test_release_is_its_own_record():
    r = release_of("Owner hereby releases the Association from any liability.")
    assert isinstance(r, Release) and consent_of("Owner hereby releases the Association from any liability.") is None
