"""How sure the Association is that a return came from its owner (``community.assurance``), and the Google Form channel:
the reference question, the personal link, and the form's requests."""

from jason.community.assurance import Channel, Provenance, assess
from jason.community.form_refs import Channel as Marked
from jason.community.form_refs import make
from jason.community.forms import Assurance

COPY = make("NP", 2027, Marked.EMAIL, membership_id=11, unit_id=22).text
MAILING = make("NP", 2027, Marked.MAIL).text
SENT = {COPY: {"unitId": 22, "membershipId": 11}, MAILING: {"channel": "MAIL"}}
ON_FILE = ["Owner@Example.org"]


def level(p, unit_id=22):
    return assess(p, unit_id=unit_id, on_file=ON_FILE, sent=SENT)


def test_signed_in_is_the_owner_and_needs_no_confirmation():
    a = level(Provenance(Channel.PAYHOA))
    assert a.level is Assurance.SIGNED_IN and not a.confirm


def test_a_reply_from_the_email_on_file_matches():
    assert level(Provenance(Channel.EMAIL, sender="owner@example.org")).level is Assurance.MATCHED
    assert level(Provenance(Channel.EMAIL, sender="someone@else.org")).level is Assurance.LEAD


def test_a_google_answer_with_the_owners_reference_is_a_token_and_with_the_email_on_file_a_match():
    token = level(Provenance(Channel.GOOGLE, sender="new@address.org", reference=COPY))
    assert token.level is Assurance.TOKEN and token.confirm               # told to the address on file first
    assert level(Provenance(Channel.GOOGLE, sender="owner@example.org", reference=COPY)).level is Assurance.MATCHED
    assert level(Provenance(Channel.GOOGLE, sender="owner@example.org", sender_verified=True)).level is Assurance.MATCHED


def test_a_typed_email_alone_only_claims_and_nothing_at_all_is_a_lead():
    assert level(Provenance(Channel.GOOGLE, sender="owner@example.org")).level is Assurance.CLAIMED
    assert level(Provenance(Channel.GOOGLE)).level is Assurance.LEAD


def test_a_reference_for_another_unit_or_never_sent_ties_nothing():
    assert level(Provenance(Channel.GOOGLE, reference=COPY), unit_id=99).level is Assurance.LEAD
    forged = make("NP", 2027, Marked.EMAIL, membership_id=1, unit_id=2).text
    a = level(Provenance(Channel.GOOGLE, reference=forged))
    assert a.level is Assurance.LEAD and "did not send" in a.reasons[0]


def test_paper_and_the_mailing_marker_claim_and_a_misread_reference_still_counts_and_says_so():
    assert level(Provenance(Channel.PAPER, reference=MAILING)).level is Assurance.CLAIMED
    i = COPY.index("-") + 2
    smudged = COPY[:i] + next(c for c in "ACEFHK" if c != COPY[i]) + COPY[i + 1:]
    a = level(Provenance(Channel.PAPER, reference=smudged))
    assert a.level is Assurance.TOKEN and "put right" in a.reasons[0]


def test_the_google_form_carries_the_preamble_the_certification_and_the_reference_question():
    from jason.community.spec import spec_module
    from jason.google.forms import form_requests

    form = spec_module("forms").OWNER_INFO
    reqs = form_requests(form, reference="Reference", values={"RETURN_BY": "Friday, October 23, 2026"})
    description = reqs[0]["updateFormInfo"]["info"]["description"]
    assert "Friday, October 23, 2026" in description and "{RETURN_BY}" not in description and "**" not in description
    items = [r["createItem"]["item"] for r in reqs[1:]]
    titles = [i["title"] for i in items]
    assert titles[-2:] == ["Certification", "Reference"]
    cert = items[-2]["questionItem"]["question"]
    assert cert["required"] and cert["choiceQuestion"]["options"][0]["value"] == form.attestation
    assert any("textItem" in i for i in items)                                # section headings
    assert [r["createItem"]["location"]["index"] for r in reqs[1:]] == list(range(len(items)))


def test_a_personal_link_carries_only_the_reference():
    from urllib.parse import parse_qs, urlparse

    from jason.google.forms import entry_ids, prefill_url

    form = {"responderUri": "https://docs.google.com/forms/d/e/abc/viewform",
            "items": [{"title": "Owner name(s)", "questionItem": {"question": {"questionId": "0a1b"}}},
                      {"title": "Reference", "questionItem": {"question": {"questionId": "2c3d4e5f"}}}]}
    assert entry_ids(form) == {"Owner name(s)": 0x0A1B, "Reference": 0x2C3D4E5F}
    url = prefill_url(form, {"Reference": COPY, "Owner name(s)": ""})
    query = parse_qs(urlparse(url).query)
    assert query == {"usp": ["pp_url"], f"entry.{0x2C3D4E5F}": [COPY]}
