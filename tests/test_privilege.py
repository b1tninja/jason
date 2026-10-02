"""Privilege leads: counsel, the insurer, the other side, and documents sent through counsel."""

from __future__ import annotations

import pytest

from jason.community import mystique
from jason.community.privilege import PrivilegeKind as P, classify

M = mystique()
PARTIES, RULES = M.privilege_parties(), M.privilege_name_rules()


@pytest.mark.parametrize("name,domains,communication,kind", [
    ("Mystique Community Association Mail - Re: tender", ["berdingweil.com"], True, P.ATTORNEY_CLIENT),
    ("Defense counsel's initial case analysis.pdf", ["fmglaw.com"], True, P.WORK_PRODUCT),
    ("MGSkinner Acknowledgement Letter.pdf", ["esis.com"], True, P.INSURER_DEFENSE),
    ("Natomas Urgent Care RECORD.pdf", ["fmglaw.com"], False, P.TRANSMITTED),          # records do not become privileged
    ("Photos of Dog Attack.zip", ["athensadmin.com"], False, P.TRANSMITTED),
    ("Demand-letter.pdf", ["amb.law", "fmglaw.com"], True, P.NOT_PRIVILEGED),          # the other side on the thread
    ("ROA 1. Complaint", ["berdingweil.com"], False, P.NOT_PRIVILEGED),                # a court filing, whoever sent it
    ("Notice of Violation - 1234 Sample Walk", [], False, P.NOT_PRIVILEGED),       # the association's letter to the owner
    ("Regular Meeting of the Board of Directors's transcript (1).txt", [], False, P.REVIEW),
    ("Owner renewal letter", ["csaa.com"], True, P.NOT_PRIVILEGED),
    ("Pool schedule.pdf", [], False, P.NONE_FOUND),
])
def test_the_strongest_call_the_parties_and_name_support(name, domains, communication, kind) -> None:
    assert classify(name, domains, PARTIES, RULES, communication=communication).kind is kind


def test_counsel_is_always_for_review_and_the_label_stays_short() -> None:
    call = classify("Mystique Community Association Mail - Re: tender", ["berdingweil.com"], PARTIES, RULES)
    assert call.review and call.label() == "attorney-client: berdingweil.com; review"
    sent = classify("Medical records.pdf", ["fmglaw.com"], PARTIES, RULES, communication=False)
    assert sent.label() == "sent through counsel: via fmglaw.com; review" and "forwarding email" in sent.note
