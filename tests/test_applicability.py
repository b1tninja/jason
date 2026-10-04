"""jason.community.applicability: facets, conditions, the three-valued evaluate, and the facts' sources.

Every row and fact here is made up ("Oak Ridge", "Example County"); none is an association's.
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from datetime import date

import pytest

from jason.community.applicability import (
    ALWAYS,
    WATER_BASED_FIRE_PROTECTION,
    AllOf,
    Answer,
    AnyOf,
    AtLeast,
    Below,
    CommonInterest,
    Except,
    Fact,
    Facts,
    FactValue,
    In,
    InForce,
    InstallationStandard,
    Is,
    Not,
    PartyRole,
    Source,
    SystemKind,
    Work,
    condition_from_dict,
    evaluate,
    partition,
    profile_facts,
)
from jason.community.base import Community
from jason.community.statutory_terms import Prior
from jason.community.symbols import DocumentKind

A, N, U = Answer.APPLIES, Answer.DOES_NOT_APPLY, Answer.UNDETERMINED

# "Applies to water-based fire protection systems, except those installed under NFPA 13D."
WATER_BASED_NOT_13D = Except(
    In(Fact.SYSTEM, WATER_BASED_FIRE_PROTECTION, "a water-based fire protection system"),
    Is(Fact.INSTALLATION_STANDARD, InstallationStandard.NFPA_13D),
)


def _facts(**document) -> Facts:
    return Facts.build(document={Fact[k.upper()]: v for k, v in document.items()}, document_where="Oak Ridge proposal")


# --- The 13 / 13R / 13D exclusion ---------------------------------------------------------------------------------


@pytest.mark.parametrize("standard, answer", [
    (InstallationStandard.NFPA_13, A),
    (InstallationStandard.NFPA_13R, A),
    (InstallationStandard.NFPA_13D, N),
])
def test_water_based_except_13d(standard, answer):
    verdict = evaluate(WATER_BASED_NOT_13D, _facts(system=SystemKind.FIRE_SPRINKLER, installation_standard=standard))
    assert verdict.answer is answer
    assert verdict.condition is WATER_BASED_NOT_13D
    assert all(v.source is Source.DOCUMENT for v in verdict.deciding)
    if answer is N:  # the exclusion decided it, and the verdict names that fact
        assert [v.fact for v in verdict.deciding] == [Fact.INSTALLATION_STANDARD]
        assert verdict.deciding[0].value is InstallationStandard.NFPA_13D
    else:
        assert {v.fact for v in verdict.deciding} == {Fact.SYSTEM, Fact.INSTALLATION_STANDARD}


def test_not_water_based_does_not_apply_whatever_the_standard():
    verdict = evaluate(WATER_BASED_NOT_13D, _facts(system=SystemKind.FIRE_ALARM))
    assert verdict.answer is N  # a known false part decides it; the missing standard could not change that
    assert [v.fact for v in verdict.deciding] == [Fact.SYSTEM]
    assert verdict.missing == ()


def test_sprinkler_with_no_standard_is_undetermined_and_names_it():
    verdict = evaluate(WATER_BASED_NOT_13D, _facts(system=SystemKind.FIRE_SPRINKLER))
    assert verdict.answer is U
    assert verdict.missing == (Fact.INSTALLATION_STANDARD,)
    assert [v.fact for v in verdict.deciding] == [Fact.SYSTEM]  # known so far
    assert "the installation standard" in verdict.question()
    assert "missing: the installation standard" in verdict.explain()


def test_nothing_known_is_undetermined_never_does_not_apply():
    verdict = evaluate(WATER_BASED_NOT_13D, Facts())
    assert verdict.answer is U
    assert set(verdict.missing) == {Fact.SYSTEM, Fact.INSTALLATION_STANDARD}


def test_profile_supplies_what_the_document_leaves_out():
    facts = Facts.build(document={Fact.SYSTEM: SystemKind.FIRE_SPRINKLER},
                        profile={Fact.INSTALLATION_STANDARD: InstallationStandard.NFPA_13R},
                        profile_where="Community.applicability_facts()")
    verdict = evaluate(WATER_BASED_NOT_13D, facts)
    assert verdict.answer is A
    sources = {v.fact: v.source for v in verdict.deciding}
    assert sources == {Fact.SYSTEM: Source.DOCUMENT, Fact.INSTALLATION_STANDARD: Source.PROFILE}


# --- Sources that disagree ----------------------------------------------------------------------------------------


def test_sources_that_agree_on_the_answer_decide_it():
    # 13 from the document, 13R from the profile: different values, but neither is 13D, so the answer stands.
    facts = Facts.build(document={Fact.SYSTEM: SystemKind.FIRE_SPRINKLER,
                                  Fact.INSTALLATION_STANDARD: InstallationStandard.NFPA_13},
                        profile={Fact.INSTALLATION_STANDARD: InstallationStandard.NFPA_13R})
    assert evaluate(WATER_BASED_NOT_13D, facts).answer is A


def test_sources_that_disagree_on_the_answer_are_undetermined():
    facts = Facts.build(document={Fact.SYSTEM: SystemKind.FIRE_SPRINKLER,
                                  Fact.INSTALLATION_STANDARD: InstallationStandard.NFPA_13D},
                        profile={Fact.INSTALLATION_STANDARD: InstallationStandard.NFPA_13R})
    verdict = evaluate(WATER_BASED_NOT_13D, facts)
    assert verdict.answer is U
    assert {v.source for v in verdict.conflicting} == {Source.DOCUMENT, Source.PROFILE}
    assert "sources disagree" in verdict.question()


# --- Kleene logic, exhaustively -----------------------------------------------------------------------------------

# One leaf per operand: Fact.CITY / COUNTY / WATER_PURVEYOR "is yes". Present as "yes" -> applies, present as "no" ->
# does not apply, absent -> undetermined.
_LEAVES = (Is(Fact.CITY, "yes"), Is(Fact.COUNTY, "yes"), Is(Fact.WATER_PURVEYOR, "yes"))
_RANK = {N: 0, U: 1, A: 2}


def _facts_for(values: tuple[Answer, ...]) -> Facts:
    rows = [FactValue(leaf.fact, "yes" if v is A else "no", Source.DOCUMENT)
            for leaf, v in zip(_LEAVES, values) if v is not U]
    return Facts(tuple(rows))


@pytest.mark.parametrize("n", [1, 2, 3])
def test_kleene_and_or_not_exhaustive(n):
    leaves = _LEAVES[:n]
    for values in itertools.product((A, N, U), repeat=n):
        facts = _facts_for(values)
        assert [evaluate(leaf, facts).answer for leaf in leaves] == list(values)
        expected_and = min(values, key=_RANK.get)
        expected_or = max(values, key=_RANK.get)
        assert evaluate(AllOf(*leaves), facts).answer is expected_and, values
        assert evaluate(AnyOf(*leaves), facts).answer is expected_or, values
        flip = {A: N, N: A, U: U}
        assert evaluate(Not(AllOf(*leaves)), facts).answer is flip[expected_and]
        # De Morgan holds in Kleene logic.
        assert evaluate(Not(AnyOf(*leaves)), facts).answer is evaluate(AllOf(*(Not(l) for l in leaves)), facts).answer
        # Except(base, *unless) answers as AllOf(base, Not(AnyOf(*unless))).
        if n > 1:
            assert evaluate(Except(leaves[0], *leaves[1:]), facts).answer is \
                evaluate(AllOf(leaves[0], Not(AnyOf(*leaves[1:]))), facts).answer


def test_kleene_records_what_decided_and_what_is_missing():
    city, county = _LEAVES[:2]
    facts = _facts_for((N, U))
    verdict = evaluate(AllOf(city, county), facts)
    assert verdict.answer is N and [v.fact for v in verdict.deciding] == [Fact.CITY] and verdict.missing == ()
    verdict = evaluate(AnyOf(city, county), facts)
    assert verdict.answer is U and verdict.missing == (Fact.COUNTY,)
    assert [v.fact for v in verdict.deciding] == [Fact.CITY]
    verdict = evaluate(Not(county), facts)
    assert verdict.answer is U and verdict.missing == (Fact.COUNTY,)


def test_double_negation_and_always():
    leaf = _LEAVES[0]
    for value in (A, N, U):
        facts = _facts_for((value,))
        assert evaluate(Not(Not(leaf)), facts).answer is value
    assert evaluate(ALWAYS, Facts()).answer is A
    assert evaluate(Not(ALWAYS), Facts()).answer is N


# --- Other facets -------------------------------------------------------------------------------------------------


def test_many_valued_facts_and_license_classes():
    cond = AllOf(In(Fact.VENDOR_WORK, {Work.INSPECT, Work.TEST, Work.MAINTAIN}), Is(Fact.LICENSE_CLASS, "C-16"))
    facts = Facts.build(document={Fact.VENDOR_WORK: [Work.TEST, Work.REPAIR], Fact.LICENSE_CLASS: ("c-16", "C-36")})
    assert evaluate(cond, facts).answer is A  # a license code compares without case
    facts = Facts.build(document={Fact.VENDOR_WORK: [Work.INSTALL], Fact.LICENSE_CLASS: ["C-16"]})
    assert evaluate(cond, facts).answer is N


def test_amount_and_unit_count():
    cond = AllOf(AtLeast(Fact.AMOUNT, 50_000), Below(Fact.UNIT_COUNT, 25))
    assert evaluate(cond, Facts.build(document={Fact.AMOUNT: 50_000}, profile={Fact.UNIT_COUNT: 12})).answer is A
    assert evaluate(cond, Facts.build(document={Fact.AMOUNT: 49_999}, profile={Fact.UNIT_COUNT: 12})).answer is N
    verdict = evaluate(cond, Facts.build(document={Fact.AMOUNT: 50_000}))
    assert verdict.answer is U and verdict.missing == (Fact.UNIT_COUNT,)


def test_buyer_missing_is_undetermined():
    # A consumer rule that reaches a contract only where an owner is the buyer: the reader did not say who bought.
    cond = AllOf(Is(Fact.DOCUMENT_KIND, DocumentKind.CONTRACT), Is(Fact.BUYER, PartyRole.OWNER))
    verdict = evaluate(cond, Facts.build(document={Fact.DOCUMENT_KIND: DocumentKind.CONTRACT}))
    assert verdict.answer is U and verdict.missing == (Fact.BUYER,)
    answered = Facts.build(document={Fact.DOCUMENT_KIND: DocumentKind.CONTRACT}).merge(
        [FactValue(Fact.BUYER, PartyRole.ASSOCIATION, Source.ANSWER, "intake question 7")])
    verdict = evaluate(cond, answered)
    assert verdict.answer is N and verdict.deciding[0].source is Source.ANSWER


def test_in_force_reuses_prior():
    prior = Prior(15, date(2025, 6, 30), "Stats. 2025, Ch. 22")
    old, new = InForce.before(prior), InForce.since(prior)
    for day, expect_old in ((date(2024, 5, 1), True), (date(2025, 6, 29), True), (date(2025, 6, 30), False)):
        facts = Facts.build(as_of=day)
        assert evaluate(old, facts).answer is (A if expect_old else N)
        assert evaluate(new, facts).answer is (N if expect_old else A)
        assert evaluate(old, facts).deciding[0].source is Source.TIME
    verdict = evaluate(old, Facts())
    assert verdict.answer is U and verdict.missing == (Fact.AS_OF,)
    window = InForce(date(2020, 1, 1), date(2021, 1, 1))
    assert evaluate(window, Facts.build(as_of=date(2020, 7, 1))).answer is A
    assert evaluate(window, Facts.build(as_of=date(2021, 1, 1))).answer is N
    with pytest.raises(ValueError):
        InForce()


def test_wrong_type_is_an_error_not_a_miss():
    with pytest.raises(TypeError):
        Is(Fact.INSTALLATION_STANDARD, "13D")
    with pytest.raises(TypeError):
        FactValue(Fact.UNIT_COUNT, "12", Source.PROFILE)
    with pytest.raises(TypeError):
        AtLeast(Fact.CITY, 3)
    with pytest.raises(TypeError):
        FactValue(Fact.AMOUNT, True, Source.DOCUMENT)


# --- describe(), hashing, and the JSON form -----------------------------------------------------------------------


def test_describe_reads_as_the_text_does():
    assert WATER_BASED_NOT_13D.describe() == (
        "the system is a water-based fire protection system, except where the installation standard is NFPA 13D")
    assert Is(Fact.SYSTEM, SystemKind.FIRE_ALARM).describe() == "the system is a fire alarm system"
    assert Not(Is(Fact.COMMON_INTEREST, CommonInterest.CONDOMINIUM)).describe() == "the development is not a condominium"
    assert Is(Fact.VENDOR_WORK, Work.MAINTAIN).describe() == "the vendor's kinds of work include maintenance"
    assert AtLeast(Fact.AMOUNT, 50_000).describe() == "the amount is at least $500.00"
    assert AllOf(Is(Fact.STATE, "ca"), AnyOf(Is(Fact.CITY, "Oak Ridge"), Is(Fact.CITY, "Elm Falls"))).describe() == (
        "the state is ca and (the city is Oak Ridge or the city is Elm Falls)")
    assert In(Fact.SYSTEM, {SystemKind.ROOF, SystemKind.ELEVATOR}).describe() == "the system is one of: elevator, roof"
    assert InForce(None, date(2025, 6, 30), "until Stats. 2025").describe() == (
        "the date is before 2025-06-30 (until Stats. 2025)")
    assert Not(AnyOf(Is(Fact.CITY, "a"), Is(Fact.CITY, "b"))).describe() == "neither the city is a nor the city is b"


def test_conditions_are_hashable_and_equal_by_value():
    twin = Except(In(Fact.SYSTEM, set(WATER_BASED_FIRE_PROTECTION), "a water-based fire protection system"),
                  Is(Fact.INSTALLATION_STANDARD, InstallationStandard.NFPA_13D))
    assert twin == WATER_BASED_NOT_13D and hash(twin) == hash(WATER_BASED_NOT_13D)
    assert len({WATER_BASED_NOT_13D, twin, ALWAYS}) == 2


@pytest.mark.parametrize("condition", [
    WATER_BASED_NOT_13D,
    ALWAYS,
    AllOf(AtLeast(Fact.AMOUNT, 50_000), Not(Is(Fact.BUYER, PartyRole.ASSOCIATION)), InForce(date(2020, 1, 1), None, "x")),
    AnyOf(Is(Fact.DOCUMENT_KIND, DocumentKind.PROPOSAL), Below(Fact.UNIT_COUNT, 10), Is(Fact.LICENSE_CLASS, "C-16")),
])
def test_json_round_trip(condition):
    data = json.loads(json.dumps(condition.as_dict()))
    assert condition_from_dict(data) == condition


def test_json_unknown_word_is_an_error():
    with pytest.raises(ValueError):
        condition_from_dict({"is": ["installation_standard", "nfpa_99"]})
    with pytest.raises(ValueError):
        condition_from_dict({"maybe": []})


def test_verdict_as_dict_names_sources():
    verdict = evaluate(WATER_BASED_NOT_13D, _facts(system=SystemKind.FIRE_SPRINKLER))
    data = json.loads(json.dumps(verdict.as_dict()))
    assert data["answer"] == "undetermined"
    assert data["missing"] == ["installation_standard"]
    assert data["deciding"][0] == {"fact": "system", "value": "fire_sprinkler", "source": "document",
                                   "where": "Oak Ridge proposal"}


# --- Rows, partitions, and the profile ----------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    key: str
    applies: object = None


def test_partition_keeps_undetermined_rows():
    rows = (_Row("annual inspection", WATER_BASED_NOT_13D), _Row("alarm test", Is(Fact.SYSTEM, SystemKind.FIRE_ALARM)),
            _Row("any system"), _Row("high-rise only", AtLeast(Fact.UNIT_COUNT, 100)))
    parts = partition(rows, _facts(system=SystemKind.FIRE_SPRINKLER, installation_standard=InstallationStandard.NFPA_13R))
    assert [r.key for r, _ in parts.applies] == ["annual inspection", "any system"]
    assert [r.key for r, _ in parts.does_not_apply] == ["alarm test"]
    assert [(r.key, v.missing) for r, v in parts.undetermined] == [("high-rise only", (Fact.UNIT_COUNT,))]


class _Profile:
    def __init__(self, facts=(), region=""):
        self._facts, self._region = facts, region

    def applicability_facts(self):
        return self._facts

    def region(self):
        return self._region


def test_community_default_is_empty():
    assert Community.applicability_facts(None) == ()  # type: ignore[arg-type]
    assert profile_facts(_Profile()) == ()


def test_profile_facts_read_region_unless_given():
    facts = profile_facts(_Profile(region="ca/example"))
    assert [(v.fact, v.value, v.source) for v in facts] == [
        (Fact.STATE, "ca", Source.PROFILE), (Fact.COUNTY, "example", Source.PROFILE)]
    given = (FactValue(Fact.COUNTY, "other", Source.PROFILE, "spec"),)
    facts = profile_facts(_Profile(given, "ca/example"))
    assert [(v.fact, v.value) for v in facts] == [(Fact.COUNTY, "other"), (Fact.STATE, "ca")]
    verdict = evaluate(Is(Fact.COUNTY, "Example"), Facts.build(profile=profile_facts(_Profile(region="ca/example"))))
    assert verdict.answer is A


def test_profile_facts_read_region_as_the_property_it_is_on_a_profile():
    """``Community.region`` is a property. A stand-in with a method hid a call on a string, so this reads a real one."""
    from jason.community import community

    class _Stated(_Profile):
        region = property(lambda self: "ca/example")

    assert [(v.fact, v.value) for v in profile_facts(_Stated())] == [(Fact.STATE, "ca"), (Fact.COUNTY, "example")]
    assert isinstance(type(community()).region, property)
    assert all(v.source is Source.PROFILE for v in profile_facts(community()))


def test_every_fact_has_a_facet_and_noun():
    for fact in Fact:
        assert fact.facet and fact.noun
