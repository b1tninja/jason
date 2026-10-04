"""jason.community.life_safety: a profile's systems as facts, and each rule row asked of each system.

Every system, vendor, and row here is made up ("Oak Ridge", "Acme Fire"); none is an association's.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from jason.community.applicability import (
    ALWAYS,
    AllOf,
    Answer,
    AtLeast,
    Except,
    Fact,
    FactValue,
    Facts,
    InForce,
    InstallationStandard,
    Is,
    Not,
    Source,
    SystemKind,
    Work,
    evaluate,
    facts_tested,
)
from jason.community.base import Community
from jason.community.fire_protection import (
    DELIVERABLE_RULES,
    FIRE_ALARM_SYSTEM,
    NFPA_25_SCOPE,
    NFPA_25_SPRINKLERS,
    deliverable_rule,
    deliverables,
)
from jason.community.life_safety import (
    SUBJECT_FACTS,
    LifeSafetySystem,
    StandardReading,
    applicability_lines,
    applicable,
    row_name,
    system_facts,
)
from jason.community.obligations import Obligation

R13 = InstallationStandard.NFPA_13R
D13 = InstallationStandard.NFPA_13D

RISERS = LifeSafetySystem("risers", "Sprinklers, buildings A and B", SystemKind.FIRE_SPRINKLER, R13,
                          "the installer's letter of May 1, 2010", serves=("A", "B"), servicer="Acme Fire",
                          monitor="Acme Alarm")
TOWNHOUSES = LifeSafetySystem("townhouses", "Sprinklers, the townhouses", SystemKind.FIRE_SPRINKLER, D13,
                              "the plan set, sheet FP-1", serves_label="the townhouses")
UNKNOWN = LifeSafetySystem("clubhouse", "Sprinklers, the clubhouse", SystemKind.FIRE_SPRINKLER,
                           serves_label="the clubhouse", note="No plan or installer's record is on file.")
ALARM = LifeSafetySystem("alarm", "Fire alarm, buildings A and B", SystemKind.FIRE_ALARM, servicer="Acme Alarm")

ANNUAL = Obligation("Sprinkler annual inspection", "NFPA 25 (made-up row)", every_years=1, applies=NFPA_25_SPRINKLERS)
FIVE_YEAR = Obligation("Sprinkler five-year inspection", "NFPA 25 (made-up row)", every_years=5, applies=NFPA_25_SPRINKLERS)
ALARM_TEST = Obligation("Alarm test", "NFPA 72 (made-up row)", every_months=6, applies=FIRE_ALARM_SYSTEM)
BUDGET = Obligation("Budget report", "Civil Code 5300", month=12, day=1)
ROWS = (ANNUAL, FIVE_YEAR, ALARM_TEST, BUDGET)


class _Profile:
    """A stand-in for a profile: the four members ``applicable`` reads, ``region`` a property as on ``Community``."""

    def __init__(self, systems=(), rows=ROWS, facts=(), region=""):
        self._systems, self._rows, self._facts, self._region = tuple(systems), tuple(rows), tuple(facts), region

    def life_safety_systems(self):
        return self._systems

    def obligations(self):
        return self._rows

    def applicability_facts(self):
        return self._facts

    @property
    def region(self):
        return self._region


def _names(findings, system=None):
    return [row_name(f.row) for f in findings if system is None or f.system is system]


# --- The record ---------------------------------------------------------------------------------------------------


def test_the_default_is_no_systems():
    assert Community.life_safety_systems(None) == ()  # type: ignore[arg-type]


def test_a_standard_is_entered_with_the_record_that_states_it():
    with pytest.raises(ValueError):
        LifeSafetySystem("x", "X", SystemKind.FIRE_SPRINKLER, R13)
    with pytest.raises(TypeError):
        LifeSafetySystem("x", "X", "fire_sprinkler")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        LifeSafetySystem("x", "X", SystemKind.FIRE_SPRINKLER, "nfpa_13r", "a letter")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LifeSafetySystem("x", "X", SystemKind.FIRE_SPRINKLER, also_stated=(StandardReading(R13, "a letter"),))
    with pytest.raises(ValueError):
        LifeSafetySystem("x", "X", SystemKind.FIRE_SPRINKLER, R13, "a letter", (StandardReading(R13, "the plans"),))
    with pytest.raises(ValueError):
        StandardReading(R13, " ")


def test_served_and_as_dict():
    assert RISERS.served() == "A, B" and TOWNHOUSES.served() == "the townhouses"
    row = json.loads(json.dumps(RISERS.as_dict()))
    assert row["kind"] == "fire_sprinkler" and row["standard"] == "nfpa_13r" and row["servicer"] == "Acme Fire"
    assert UNKNOWN.as_dict()["standard"] is None


def test_a_system_becomes_profile_facts():
    facts = system_facts(RISERS)
    assert [(v.fact, v.value, v.source) for v in facts.values] == [
        (Fact.SYSTEM, SystemKind.FIRE_SPRINKLER, Source.PROFILE), (Fact.INSTALLATION_STANDARD, R13, Source.PROFILE)]
    assert facts.of(Fact.INSTALLATION_STANDARD)[0].where == "the installer's letter of May 1, 2010"
    assert "risers" in facts.of(Fact.SYSTEM)[0].where
    assert Fact.INSTALLATION_STANDARD not in system_facts(UNKNOWN)          # not known: no fact, never a guess


def test_facts_tested_walks_the_whole_condition():
    assert facts_tested(ALWAYS) == frozenset()
    assert facts_tested(NFPA_25_SCOPE) == {Fact.SYSTEM, Fact.INSTALLATION_STANDARD} == SUBJECT_FACTS
    nested = AllOf(Not(Is(Fact.COUNTY, "Example")), Except(AtLeast(Fact.UNIT_COUNT, 3), InForce(date(2025, 1, 1))))
    assert facts_tested(nested) == {Fact.COUNTY, Fact.UNIT_COUNT, Fact.AS_OF}


# --- Each row asked of each system --------------------------------------------------------------------------------


def test_three_groups_by_system():
    result = applicable(_Profile((RISERS, TOWNHOUSES, UNKNOWN, ALARM)))
    assert _names(result.applies, RISERS) == ["Sprinkler annual inspection", "Sprinkler five-year inspection"]
    assert _names(result.does_not_apply, RISERS) == ["Alarm test"]
    assert _names(result.does_not_apply, TOWNHOUSES) == ["Sprinkler annual inspection", "Sprinkler five-year inspection",
                                                         "Alarm test"]
    assert _names(result.applies, ALARM) == ["Alarm test"]
    assert _names(result.does_not_apply, ALARM) == ["Sprinkler annual inspection", "Sprinkler five-year inspection"]
    # A row that names no system is asked of the association once, not of each system.
    assert [(row_name(f.row), f.system) for f in result.applies if f.system is None] == [("Budget report", None)]


def test_does_not_apply_names_the_fact_that_decided_it_and_its_record():
    result = applicable(_Profile((TOWNHOUSES,)))
    annual = next(f for f in result.does_not_apply if f.row is ANNUAL)
    assert [(v.fact, v.value, v.where) for v in annual.verdict.deciding] == [
        (Fact.INSTALLATION_STANDARD, D13, "the plan set, sheet FP-1")]
    assert "NFPA 13D" in annual.why() and "the plan set, sheet FP-1" in annual.why()
    alarm = next(f for f in result.does_not_apply if f.row is ALARM_TEST)
    assert [v.fact for v in alarm.verdict.deciding] == [Fact.SYSTEM]


def test_an_unknown_standard_is_a_question_never_does_not_apply():
    result = applicable(_Profile((UNKNOWN,)))
    assert _names(result.undetermined) == ["Sprinkler annual inspection", "Sprinkler five-year inspection"]
    assert not [f for f in result.does_not_apply if f.row in (ANNUAL, FIVE_YEAR)]
    finding = result.undetermined[0]
    assert finding.verdict.missing == (Fact.INSTALLATION_STANDARD,)
    assert finding.question().startswith("Sprinklers, the clubhouse: which standard was it installed under?")
    # One question, however many rows wait on it.
    (question,) = result.questions()
    assert question.system is UNKNOWN and question.waiting == ("Sprinkler annual inspection", "Sprinkler five-year inspection")
    # The alarm row is decided by the kind alone: no answer about the standard could change it.
    assert _names(result.does_not_apply) == ["Alarm test"]


def test_two_records_that_agree_on_the_answer_stand_and_two_that_do_not_are_a_question():
    same = LifeSafetySystem("b", "Sprinklers, building B", SystemKind.FIRE_SPRINKLER, R13, "an email of June 2, 2015",
                            (StandardReading(InstallationStandard.NFPA_13, "the minutes of July 7, 2015"),))
    result = applicable(_Profile((same,), rows=(ANNUAL,)))
    assert _names(result.applies) == ["Sprinkler annual inspection"] and not result.questions()
    assert {v.value for v in result.applies[0].verdict.deciding if v.fact is Fact.INSTALLATION_STANDARD} == {
        R13, InstallationStandard.NFPA_13}

    split = LifeSafetySystem("c", "Sprinklers, building C", SystemKind.FIRE_SPRINKLER, R13, "an email of June 2, 2015",
                             (StandardReading(D13, "the minutes of July 7, 2015"),))
    result = applicable(_Profile((split,), rows=(ANNUAL,)))
    assert not result.applies and not result.does_not_apply
    (question,) = result.questions()
    assert "the records disagree on the installation standard" in question.text
    assert "an email of June 2, 2015" in question.text and "the minutes of July 7, 2015" in question.text


def test_a_profile_that_lists_no_systems_is_asked_which_it_has():
    result = applicable(_Profile(()))
    assert result.systems == () and not result.does_not_apply
    assert _names(result.undetermined) == ["Sprinkler annual inspection", "Sprinkler five-year inspection", "Alarm test"]
    (question,) = result.questions()
    assert question.text.startswith("Which life safety systems does the association have?") and question.system is None
    assert _names(result.applies) == ["Budget report"]


def test_a_row_that_reaches_no_listed_system_is_shown():
    elevator = Obligation("Elevator permit", "made-up row", every_years=1, applies=Is(Fact.SYSTEM, SystemKind.ELEVATOR))
    result = applicable(_Profile((RISERS, ALARM), rows=(ANNUAL, elevator)))
    assert result.unreached() == (elevator,)
    assert any("Elevator permit" in line for line in applicability_lines(result))
    # One system's part cannot say a row reaches no system: the alarm test reaches the alarm, not the risers.
    part = result.of(RISERS)
    assert part.systems == (RISERS,) and part.unreached() == () and _names(part.applies) == ["Sprinkler annual inspection"]
    assert not any("reach no listed system" in line for line in applicability_lines(part))


def test_the_profiles_own_facts_and_the_date_are_joined():
    units = Obligation("Elevated elements inspection", "made-up row", every_years=9, applies=AtLeast(Fact.UNIT_COUNT, 3))
    later = Obligation("A later rule", "made-up row", every_years=1,
                       applies=AllOf(FIRE_ALARM_SYSTEM, InForce(date(2030, 1, 1))))
    bare = applicable(_Profile((ALARM,), rows=(units, later)), as_of=date(2026, 1, 1))
    assert _names(bare.undetermined) == ["Elevated elements inspection"]            # asked of the association
    assert bare.undetermined[0].question() == "the association: what is the number of units?"
    assert _names(bare.does_not_apply, ALARM) == ["A later rule"]
    known = _Profile((ALARM,), rows=(units, later), facts=(FactValue(Fact.UNIT_COUNT, 12, Source.PROFILE, "the plan"),))
    result = applicable(known, as_of=date(2031, 1, 1))
    assert _names(result.applies) == ["A later rule", "Elevated elements inspection"]
    assert not result.undetermined


def test_rows_other_than_obligations_and_the_json_form():
    result = applicable(_Profile((RISERS, UNKNOWN)), rows=DELIVERABLE_RULES)
    assert not result.applies and not result.does_not_apply                  # the vendor's work is not a profile fact
    assert {f.verdict.missing for f in result.undetermined if f.system is RISERS} == {(Fact.VENDOR_WORK,)}
    data = json.loads(json.dumps(applicable(_Profile((RISERS, TOWNHOUSES, UNKNOWN, ALARM))).as_dict()))
    assert [s["key"] for s in data["systems"]] == ["risers", "townhouses", "clubhouse", "alarm"]
    assert {f["verdict"]["answer"] for f in data["undetermined"]} == {"undetermined"}
    assert data["questions"][0]["system"] == "clubhouse" and data["unreached"] == []


def test_the_lines_show_each_group_and_the_questions():
    text = "\n".join(applicability_lines(applicable(_Profile((RISERS, TOWNHOUSES, UNKNOWN, ALARM))), association=True))
    assert "Sprinklers, buildings A and B (fire sprinkler system)" in text
    assert "standard: NFPA 13R, from the installer's letter of May 1, 2010" in text
    assert "standard: not on record" in text
    assert "decided by the installation standard: NFPA 13D (profile, the plan set, sheet FP-1):" in text
    assert "question: Sprinklers, the clubhouse: which standard was it installed under?" in text
    assert "Questions for a person (1)" in text and "The association" in text and "Budget report" in text


# --- The standards' scopes and the deliverable rules --------------------------------------------------------------


def _subject(kind, standard=None, work=None):
    document = {Fact.SYSTEM: kind}
    if standard:
        document[Fact.INSTALLATION_STANDARD] = standard
    if work is not None:
        document[Fact.VENDOR_WORK] = work
    return Facts.build(document=document, document_where="Oak Ridge agreement")


def test_nfpa_25_reaches_water_based_systems_but_not_13d():
    assert evaluate(NFPA_25_SCOPE, _subject(SystemKind.STANDPIPE, InstallationStandard.NFPA_14)).answer is Answer.APPLIES
    assert evaluate(NFPA_25_SCOPE, _subject(SystemKind.FIRE_SPRINKLER, D13)).answer is Answer.DOES_NOT_APPLY
    assert evaluate(NFPA_25_SCOPE, _subject(SystemKind.FIRE_ALARM)).answer is Answer.DOES_NOT_APPLY
    assert evaluate(NFPA_25_SPRINKLERS, _subject(SystemKind.FIRE_SPRINKLER, R13)).answer is Answer.APPLIES
    assert evaluate(NFPA_25_SPRINKLERS, _subject(SystemKind.STANDPIPE)).answer is Answer.DOES_NOT_APPLY
    assert evaluate(NFPA_25_SPRINKLERS, _subject(SystemKind.FIRE_SPRINKLER)).answer is Answer.UNDETERMINED
    assert NFPA_25_SPRINKLERS.describe() == ("the system is a fire sprinkler system, except where the installation "
                                             "standard is NFPA 13D")


def test_every_deliverable_rule_says_what_it_applies_to():
    for rule in DELIVERABLE_RULES:
        assert rule.applies is not ALWAYS
        assert facts_tested(rule.applies) == {Fact.SYSTEM, Fact.VENDOR_WORK}


def test_deliverables_by_the_subject_and_the_vendors_work():
    keys = lambda pairs: [rule.key for rule, _ in pairs]  # noqa: E731
    tested = deliverables(_subject(SystemKind.FIRE_SPRINKLER, R13, {Work.TEST, Work.MAINTAIN}))
    assert keys(tested.applies) == [r.key for r in DELIVERABLE_RULES] and not tested.undetermined
    # An inspection alone is 904.1's: the forms and the inspection report, not 904.2's testing and maintenance duties.
    # A document that names inspection does not say the vendor does nothing else, so 904.2's rows stay a question.
    inspected = deliverables(_subject(SystemKind.FIRE_SPRINKLER, R13, {Work.INSPECT}))
    assert keys(inspected.applies) == ["aes-forms", "inspection-report"]
    assert "itemized-invoice" in keys(inspected.undetermined) and not inspected.does_not_apply
    # A person's answer that inspection is all the vendor does is complete: 904.2's rows do not apply.
    only = _subject(SystemKind.FIRE_SPRINKLER, R13).merge(
        [FactValue(Fact.VENDOR_WORK, {Work.INSPECT}, Source.ANSWER, "intake question 7")])
    inspected = deliverables(only)
    assert keys(inspected.applies) == ["aes-forms", "inspection-report"]
    assert "itemized-invoice" in keys(inspected.does_not_apply) and not inspected.undetermined
    repaired = deliverables(_subject(SystemKind.FIRE_SPRINKLER, R13, {Work.REPAIR}))
    assert keys(repaired.applies) == ["itemized-invoice", "repair-estimate"]
    # A fire alarm is not a water-based system: no row applies, and the system's kind is the deciding fact.
    alarm = deliverables(_subject(SystemKind.FIRE_ALARM, None, {Work.TEST}))
    assert not alarm.applies and not alarm.undetermined
    assert all([v.fact for v in verdict.deciding] == [Fact.SYSTEM] for _, verdict in alarm.does_not_apply)
    # What the vendor does is not known: a question, never a row dropped.
    unknown = deliverables(_subject(SystemKind.FIRE_SPRINKLER, R13))
    assert len(unknown.undetermined) == len(DELIVERABLE_RULES)
    assert all(verdict.missing == (Fact.VENDOR_WORK,) for _, verdict in unknown.undetermined)


def test_matching_a_quote_is_unchanged_by_the_conditions():
    assert deliverable_rule("Results shall be recorded on form AES 2.1.").key == "aes-forms"
    assert deliverable_rule("We will mow, edge, and blow all turf areas weekly.") is None


# --- Obligations and the active profile ---------------------------------------------------------------------------


def test_an_obligation_applies_always_unless_it_says():
    assert BUDGET.applies is ALWAYS and facts_tested(BUDGET.applies) == frozenset()
    assert ANNUAL.applies is NFPA_25_SPRINKLERS and ANNUAL.cadence() == "every 1 year"


def test_the_active_profiles_systems_and_rows_hold_together():
    from jason.community import community

    active = community()
    result = applicable(active, as_of=date(2026, 10, 4))
    assert result.systems == tuple(active.life_safety_systems()) and result.systems
    assert len({s.key for s in result.systems}) == len(result.systems)
    for system in result.systems:
        assert isinstance(system, LifeSafetySystem)
        assert all(reading.where for reading in system.readings())          # each standard names its record
    asked = {row_name(f.row) for f in result.applies + result.does_not_apply + result.undetermined if f.system}
    assert asked and all(facts_tested(o.applies) & SUBJECT_FACTS for o in active.obligations() if o.name in asked)
    assert all(f.question() for f in result.undetermined)                    # an open answer is always a question
    assert not result.unreached()                                            # every system row reaches a listed system
    # Each fire protection row is asked of the systems, not left to apply to everything.
    fire = [o for o in active.obligations() if "fire" in o.name.lower() or "backflow" in o.name.lower()]
    assert fire and all(o.name in asked for o in fire)


def test_the_command_prints_the_three_groups(capsys):
    from jason.cli import build_parser

    args = build_parser().parse_args(["applies", "--as-of", "2026-10-04"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "what applies to each life safety system, as of 2026-10-04" in out
    assert "  applies (" in out and "  does not apply (" in out and "Questions for a person (" in out
    args = build_parser().parse_args(["applies", "--json"])
    assert args.func(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) >= {"systems", "applies", "doesNotApply", "undetermined", "questions"}
    args = build_parser().parse_args(["applies", "--system", "no-such-system"])
    assert args.func(args) == 2
    capsys.readouterr()
    from jason.community import community

    first = community().life_safety_systems()[0]
    args = build_parser().parse_args(["applies", "--system", first.key])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert first.name in out and "reach no listed system" not in out
