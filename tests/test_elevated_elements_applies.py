"""The inspection of exterior elevated elements (Civil Code 5551): its scope as a condition over the property's facts.
It applies, does not apply, or is undetermined, and an undetermined answer is a question for a person.

Every profile, row, and answer here is made up.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from jason.community import applicability_asks as asks
from jason.community import intake
from jason.community.applicability import (
    ELEVATED_ELEMENTS_INSPECTION,
    Answer,
    CommonInterest,
    ElevatedElements,
    Facet,
    Fact,
    FactValue,
    Source,
    SystemKind,
    facts_tested,
)
from jason.community.life_safety import SUBJECT_FACTS, LifeSafetySystem, applicability_lines, applicable
from jason.community.obligations import Obligation

DATA = Path(__file__).resolve().parents[1] / "data"
INSPECTION = Obligation("Elevated elements inspection", "made-up row", every_years=9, first_due=date(2025, 1, 1),
                        applies=ELEVATED_ELEMENTS_INSPECTION)
ALARM = LifeSafetySystem("alarm", "Fire alarm, building A", SystemKind.FIRE_ALARM)


class _Profile:
    name = "Oak Ridge Owners Association"
    region = ""

    def __init__(self, facts=(), systems=()):
        self._facts, self._systems = tuple(facts), tuple(systems)

    def life_safety_systems(self):
        return self._systems

    def obligations(self):
        return (INSPECTION,)

    def applicability_facts(self):
        return self._facts


def _stated(kind=CommonInterest.CONDOMINIUM, elements=ElevatedElements.ASSOCIATION_RESPONSIBLE, units=12):
    pairs = ((Fact.COMMON_INTEREST, kind, "the declaration, article 1"),
             (Fact.ELEVATED_ELEMENTS, elements, "the declaration, section 5.1"),
             (Fact.ATTACHED_UNITS, units, "the condominium plan"))
    return tuple(FactValue(fact, value, Source.PROFILE, where) for fact, value, where in pairs if value is not None)


def test_the_condition_is_the_sections_three_facts_about_the_property():
    assert facts_tested(ELEVATED_ELEMENTS_INSPECTION) == {Fact.COMMON_INTEREST, Fact.ELEVATED_ELEMENTS, Fact.ATTACHED_UNITS}
    assert all(f.facet is Facet.PROPERTY and f.standing for f in facts_tested(ELEVATED_ELEMENTS_INSPECTION))
    assert not facts_tested(ELEVATED_ELEMENTS_INSPECTION) & SUBJECT_FACTS    # asked of the association, not a system
    assert ELEVATED_ELEMENTS_INSPECTION.describe() == (
        "the development is a condominium and maintenance or repair of exterior elevated elements (5551(a)) is the "
        "association's responsibility (5551(b)(1)) and the most attached multifamily dwelling units in one building is "
        "at least 3")


def test_it_applies_to_a_condominium_with_elements_the_association_maintains():
    result = applicable(_Profile(_stated(), systems=(ALARM,)))
    (finding,) = result.applies
    assert finding.row is INSPECTION and finding.system is None and finding.subject == "the association"
    assert {v.fact for v in finding.verdict.deciding} == {Fact.COMMON_INTEREST, Fact.ELEVATED_ELEMENTS, Fact.ATTACHED_UNITS}
    assert all(v.source is Source.PROFILE and v.where for v in finding.verdict.deciding)
    assert not result.undetermined and not result.unreached()                # never "reaches no listed system"
    assert applicable(_Profile(_stated(units=3))).applies                    # three attached units are enough


@pytest.mark.parametrize("facts, decided_by", [
    (_stated(kind=CommonInterest.PLANNED_DEVELOPMENT), "the development: planned development (profile, the declaration, article 1)"),
    (_stated(elements=ElevatedElements.NONE),
     "maintenance or repair of exterior elevated elements (5551(a)): none that is the association's responsibility "
     "(profile, the declaration, section 5.1)"),
    (_stated(units=2), "the most attached multifamily dwelling units in one building: 2 (profile, the condominium plan)"),
    # One known "no" decides it, whatever the facts not stated would say.
    (_stated(kind=CommonInterest.STOCK_COOPERATIVE, elements=None, units=None),
     "the development: stock cooperative (profile, the declaration, article 1)"),
])
def test_it_does_not_apply_with_the_fact_that_decided_it(facts, decided_by):
    result = applicable(_Profile(facts))
    (finding,) = result.does_not_apply
    assert finding.why() == decided_by and not result.applies and not result.undetermined
    assert any(decided_by in line for line in applicability_lines(result, association=True))


def test_with_no_facts_it_is_undetermined_and_each_fact_is_a_question():
    result = applicable(_Profile())
    (finding,) = result.undetermined
    assert finding.verdict.answer is Answer.UNDETERMINED and not result.does_not_apply
    assert finding.verdict.missing == (Fact.COMMON_INTEREST, Fact.ELEVATED_ELEMENTS, Fact.ATTACHED_UNITS)
    assert "does it have exterior elevated elements for which the association has maintenance or repair responsibility" \
        in finding.question()
    found = asks.questions(result)
    assert [(q.subject, q.key) for q in found] == [("applies:association", "common_interest"),
                                                   ("applies:association", "elevated_elements"),
                                                   ("applies:association", "attached_units")]
    kind, elements, units = found
    assert all(q.waiting == ("Elevated elements inspection",) for q in found)
    assert elements.text().startswith("The association: does it have exterior elevated elements for which the "
                                      "association has maintenance or repair responsibility (Civil Code 5551(a), (b)(1)")
    assert elements.choices() == () and "after a semicolon, the record that states it" in elements.text()
    assert elements.settled_by().startswith("the declaration's maintenance sections and the condominium plan")
    assert units.text().startswith("The association: how many attached multifamily dwelling units does its largest "
                                   "building contain (Civil Code 5551(l))?")
    assert kind.choices() == ("condominium", "planned development", "stock cooperative", "community apartment project")
    # Part known: the rest is still asked, and nothing is read as "does not apply".
    part = applicable(_Profile(_stated(elements=None, units=None)))
    assert part.undetermined[0].verdict.missing == (Fact.ELEVATED_ELEMENTS, Fact.ATTACHED_UNITS)
    assert [q.key for q in asks.questions(part)] == ["elevated_elements", "attached_units"]


def test_a_persons_answers_settle_it():
    profile = _Profile()
    queue = [q.ask() for q in asks.questions(applicable(profile))]
    by_fact = {a.detail["fact"]: a for a in queue}
    intake.answer(queue, by_fact["common_interest"].id, "1", "Pat Example")                    # a choice's number
    intake.answer(queue, by_fact["attached_units"].id, "12; the condominium plan, sheet 3", "Pat Example")
    intake.answer(queue, by_fact["elevated_elements"].id, "the association's responsibility", "Pat Example")
    found = asks.answered(queue)
    assert "no record named" in found.unread[0][1]                          # entered with the record that states it
    assert applicable(profile, answers=found.facts).undetermined[0].verdict.missing == (Fact.ELEVATED_ELEMENTS,)
    intake.answer(queue, by_fact["elevated_elements"].id, "the association's responsibility; declaration 5.1(b)",
                  "Pat Example")
    found = asks.answered(queue)
    result = applicable(profile, answers=found.facts)
    (finding,) = result.applies
    assert {v.source for v in finding.verdict.deciding} == {Source.ANSWER} and not asks.questions(result)
    # An answer of none rules it out, with the answer as the deciding fact.
    intake.answer(queue, by_fact["elevated_elements"].id, "none; declaration 5.1(b): each owner maintains the balcony",
                  "Pat Example")
    (finding,) = applicable(profile, answers=asks.answered(queue).facts).does_not_apply
    assert "none that is the association's responsibility (answer, intake question" in finding.why()


def test_the_active_profiles_row_carries_the_sections_condition():
    from jason.community import community

    active = community()
    rows = [o for o in active.obligations() if "5551" in o.authority]
    assert rows and all(o.applies is ELEVATED_ELEMENTS_INSPECTION for o in rows)
    result = applicable(active, as_of=date(2026, 10, 4))
    findings = [f for f in result.applies + result.does_not_apply + result.undetermined if f.row in rows]
    assert findings and all(f.system is None for f in findings)             # asked of the association, once a row
    assert all(f.question() for f in findings if f.verdict.undetermined)


WORDS = [
    r"the board of an association of a condominium project shall cause a reasonably competent and diligent visual "
    r"inspection",
    r"exterior elevated elements for which the association has maintenance or repair responsibility",
    r"extend beyond the exterior walls of the building",
    r"walking surface elevated more than six feet above ground level",
    r"supported in whole or in substantial part by wood or wood-based products",
    r"This section shall only apply to buildings containing three or more attached multifamily dwelling units",
]


@pytest.mark.parametrize("words", WORDS, ids=[w[:40] for w in WORDS])
def test_the_statute_on_disk_carries_the_words_the_condition_rests_on(words):
    from jason.tasks.export_authorities import authority_text

    text = authority_text(DATA, "CIV 5551").get("text") or ""
    if not text:
        pytest.skip("CIV 5551 is not exported here (jason export-authorities)")
    assert re.search(words, re.sub(r"\s+", " ", text), re.I), (
        f"CIV 5551 no longer reads '{words}'; the law may have changed: read the section and "
        "applicability.ELEVATED_ELEMENTS_INSPECTION")
