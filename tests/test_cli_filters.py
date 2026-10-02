"""The optional filters on jason insurance and jason copies."""

from __future__ import annotations

from jason.cli import policy_matches
from jason.tasks.copies import catalog_lines


def _policy(kind: str, number: str, building: int | None = None, prior: tuple[str, ...] = ()) -> dict:
    return {"kind": kind, "number": number, "building": building, "priorNumbers": list(prior)}


def test_a_policy_by_kind_alias_building_or_number() -> None:
    flood2 = _policy("flood", "5010000011", 2, ("5010000096",))
    dando = _policy("directors_and_officers", "1-SKN-CA-01524174-01")
    crime = _policy("fidelity", "4126011561232Y")
    assert policy_matches(flood2, "flood-2") and policy_matches(flood2, "flood building 2") and policy_matches(flood2, "5010000096")
    assert not policy_matches(flood2, "flood-3")
    assert policy_matches(dando, "d&o") and policy_matches(dando, "01524174") and not policy_matches(dando, "master")
    assert policy_matches(crime, "crime") and policy_matches(crime, "fidelity")


RESULT = {
    "copies": 3, "documents": 2, "byChannel": {"email attachment": 3}, "acrossChannels": 0, "sameChannelDuplicates": 0,
    "withPayment": 1, "priority": ["email attachment"], "caveats": [],
    "proposalsAttachedToPayment": [], "proposalsPaidWithoutInvoice": [],
    "proposalsOpen": [{"issuer": "Jensen", "issued": "2024-12-02", "totalCents": 210800, "stage": "proposal", "title": "Quote.pdf",
                       "candidates": []},
                      {"issuer": "E&R", "issued": "2026-06-01", "totalCents": 175000, "stage": "proposal", "title": "Estimate.pdf",
                       "candidates": []}],
    "onSeveralPayments": [{"issuer": "SMUD", "number": "", "issued": "2024-03-28", "totalCents": 25011, "txIds": [1, 2],
                           "title": "bill.pdf", "explained": "paid twice; the next bill shows the credit (...)"},
                          {"issuer": "Philadelphia", "number": "", "issued": "2024-02-05", "totalCents": None, "txIds": [3, 4],
                           "title": "notice.pdf", "explained": ""}],
    "rows": [],
}


def test_the_copies_report_by_section_date_and_what_is_unexplained() -> None:
    proposals = "\n".join(catalog_lines(RESULT, sections={"proposals"}, since="2026-01-01"))
    assert "E&R" in proposals and "Jensen" not in proposals and "more than one live payment" not in proposals
    several = "\n".join(catalog_lines(RESULT, sections={"several"}, only_unexplained=True))
    assert "not explained: 2024-02-05 Philadelphia" in several and "paid twice; the next bill" not in several
