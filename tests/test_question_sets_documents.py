"""The question sets for insurance declarations, proposals, and invoices: amounts in cents, each reader's field, a
label and its value on separate lines, and a model's "no" that is the gap."""

from __future__ import annotations

import dataclasses

from jason.community.question_sets import INSURANCE_POLICY, INVOICE, PROPOSAL, QUESTION_SETS
from jason.community.questions import AnswerType, Question, Verdict, cents, grounded, judge, rule_value
from jason.community.symbols import DocumentKind

FLOOD_PAGE = """PHILADELPHIA INDEMNITY INSURANCE COMPANY
Policy issued by:
Zero Balance Due - This Is Not A Bill
INVOICE NO.
Date
800175
DEDUCTIBLE
$2,000"""


def _q(qs, key: str) -> Question:
    return next(q for q in qs.questions if q.key == key)


def test_a_dollar_amount_is_read_as_integer_cents() -> None:
    assert cents("$1,234.56") == 123456
    assert cents("10,000") == 1_000_000
    assert cents(2457) == 245700
    assert cents("Total Due $ 3,889.00") == 388900
    assert cents("N/A") is None and cents(None) is None and cents(True) is None


def test_an_amount_answer_is_judged_in_cents_and_a_limit_under_the_law_is_short() -> None:
    q = _q(INSURANCE_POLICY, "property_deductible")
    fields = {"property_deductible": 1_000_000, "building_limit": 3_626_990_500}
    text = "Deductible / Waiting Period 10,000"
    assert judge(q, {"stated": True, "value": "$10,000", "quote": "Deductible / Waiting Period 10,000"}, text,
                 fields)["verdict"] == Verdict.AGREES.value
    gl = _q(INSURANCE_POLICY, "gl_each_occurrence")
    out = judge(gl, {"stated": True, "value": "$300,000", "quote": "Each Occurrence Limit 300,000"},
                "Each Occurrence Limit 300,000", {"each_occurrence": 30_000_000, "general_aggregate": 60_000_000})
    assert out["verdict"] == Verdict.AGREES.value and out["short"].startswith("$300,000.00 is under $500,000.00")
    assert "5800" in out["authority"]


def test_each_reader_names_its_own_field() -> None:
    q = _q(INSURANCE_POLICY, "property_deductible")
    assert rule_value(q, {"deductible": 200_000, "flood_zone": "A99"}) == 200_000             # the flood page
    assert rule_value(q, {"property_deductible": 1_000_000, "deductible": 5}) == 1_000_000    # the package
    assert rule_value(_q(INSURANCE_POLICY, "dno_limit"), {"limit": 175_000_000, "flood_zone": "A99"}) is None
    assert rule_value(_q(INSURANCE_POLICY, "dno_limit"), {"limit": 100_000_000, "claims_made": True}) == 100_000_000


def test_every_field_a_question_names_is_on_a_readers_record() -> None:
    from jason.community.models.contracts_agreements import Proposal
    from jason.community.models.contracts_ins_package import (CrimePolicy, DirectorsAndOfficersPolicy, PackagePolicy,
                                                               UmbrellaEvidence)
    from jason.community.models.contracts_insurance import InsurancePolicy
    from jason.community.models.invoices import FloodPremiumNotice

    records = {DocumentKind.INSURANCE_POLICY: (InsurancePolicy, PackagePolicy, CrimePolicy, DirectorsAndOfficersPolicy,
                                               UmbrellaEvidence),
               DocumentKind.PROPOSAL: (Proposal,), DocumentKind.INVOICE: (FloodPremiumNotice,)}
    for kind, classes in records.items():
        names = {f.name for c in classes for f in dataclasses.fields(c)}
        assert QUESTION_SETS[kind].kind is kind
        for q in QUESTION_SETS[kind].questions:
            for alt in filter(None, q.field.split("|")):
                name, _, when = alt.partition(":")
                assert name in names and (not when or when in names), (kind, q.key, alt)
            assert q.minimum is None or q.answer is AnswerType.AMOUNT


def test_a_label_and_its_value_on_separate_lines_are_grounded_but_a_made_up_quote_is_not() -> None:
    assert grounded("Policy issued by: PHILADELPHIA INDEMNITY INSURANCE COMPANY", FLOOD_PAGE)   # value above the label
    assert grounded("INVOICE NO. 800175", FLOOD_PAGE)
    assert not grounded("Policy issued by: Farmers Insurance Exchange", FLOOD_PAGE)
    assert not grounded("INVOICE NO. 800176", FLOOD_PAGE)


def test_a_models_no_with_nothing_from_the_rules_is_the_gap() -> None:
    q = _q(PROPOSAL, "accepted")
    text = "Customer Acceptance\nx\nSignature\nPrinted Name\nDate"
    out = judge(q, {"stated": True, "value": False, "quote": "Customer Acceptance"}, text, {"accepted_on": None})
    assert out["verdict"] == Verdict.GAP.value and out["lead"].startswith("no acceptance shows")
    assert judge(q, {"stated": True, "value": True, "quote": "Customer Acceptance"}, text,
                 {"accepted_on": "2023-10-20"})["verdict"] == Verdict.AGREES.value


def test_priced_entries_are_compared_as_topics_with_their_amounts() -> None:
    q = _q(PROPOSAL, "work_items")
    text = "CRACK SEAL\n$2,100.00\nSTRIPE\n$2,557.00\nTotal $4,657.00"
    fields = {"items": [{"description": "CRACK SEAL", "amount": 210000}, {"description": "STRIPE", "amount": 255700}]}
    out = judge(q, {"stated": True, "value": ["Crack seal $2,100", "Striping $2,557.00"], "quote": "CRACK SEAL $2,100.00"},
                text, fields)
    assert out["verdict"] == Verdict.AGREES.value and len(out["both"]) == 2


def test_spacing_and_punctuation_in_a_name_are_not_a_difference() -> None:
    q = _q(INVOICE, "vendor")
    assert judge(q, {"stated": True, "value": "Pro Active Pest Control", "quote": "Pro Active Pest Control"},
                 "Pro Active Pest Control\nINVOICE", {"vendor": "ProActive Pest Control"})["verdict"] == "agrees"
