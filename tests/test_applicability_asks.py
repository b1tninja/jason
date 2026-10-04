"""Undetermined answers as intake questions, and a person's answers as facts with source ANSWER.

Every system, row, person, and record here is made up ("Oak Ridge", "Pat Example"); none is an association's.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from jason.community import applicability_asks as asks
from jason.community import intake
from jason.community.applicability import (
    AllOf,
    Answer,
    AtLeast,
    CommonInterest,
    Fact,
    InForce,
    InstallationStandard,
    Is,
    Source,
    SystemKind,
)
from jason.community.fire_protection import FIRE_ALARM_SYSTEM, NFPA_25_SPRINKLERS
from jason.community.intake import AskKind, AskStatus
from jason.community.life_safety import LifeSafetySystem, StandardReading, applicable
from jason.community.obligations import Obligation
from jason.tasks import applicability_asks as task
from jason.tasks import intake as intake_task

R13 = InstallationStandard.NFPA_13R
D13 = InstallationStandard.NFPA_13D

RISERS = LifeSafetySystem("risers", "Sprinklers, buildings A and B", SystemKind.FIRE_SPRINKLER, R13,
                          "the installer's letter of May 1, 2010")
CLUBHOUSE = LifeSafetySystem("clubhouse", "Sprinklers, the clubhouse", SystemKind.FIRE_SPRINKLER)
POOL = LifeSafetySystem("pool", "Sprinklers, the pool house", SystemKind.FIRE_SPRINKLER)
ALARM = LifeSafetySystem("alarm", "Fire alarm, buildings A and B", SystemKind.FIRE_ALARM)

ANNUAL = Obligation("Sprinkler annual inspection", "made-up row", every_years=1, applies=NFPA_25_SPRINKLERS)
FIVE_YEAR = Obligation("Sprinkler five-year inspection", "made-up row", every_years=5, applies=NFPA_25_SPRINKLERS)
ALARM_TEST = Obligation("Alarm test", "made-up row", every_months=6, applies=FIRE_ALARM_SYSTEM)
LARGE = Obligation("Alarm test, large developments", "made-up row", every_years=1,
                   applies=AllOf(FIRE_ALARM_SYSTEM, AtLeast(Fact.UNIT_COUNT, 50)))
CONDO = Obligation("Condominium disclosure", "made-up row", every_years=1,
                   applies=Is(Fact.COMMON_INTEREST, CommonInterest.CONDOMINIUM))
ROWS = (ANNUAL, FIVE_YEAR, ALARM_TEST)


class _Profile:
    name = "Oak Ridge Owners Association"
    region = ""

    def __init__(self, systems=(), rows=ROWS, facts=()):
        self._systems, self._rows, self._facts = tuple(systems), tuple(rows), tuple(facts)

    def life_safety_systems(self):
        return self._systems

    def obligations(self):
        return self._rows

    def applicability_facts(self):
        return self._facts


def _answer(question, text, by="Pat Example"):
    """The question filed and answered through the queue's own answer path."""
    queue = [question.ask()]
    intake.answer(queue, question.id, text, by)
    return queue


# --- One question a subject and fact ------------------------------------------------------------------------------


def test_one_question_for_one_missing_fact_however_many_rows_wait():
    result = applicable(_Profile((RISERS, CLUBHOUSE, ALARM)))
    assert len(result.undetermined) == 2                                    # two rows wait on the clubhouse's standard
    (q,) = asks.questions(result)
    assert (q.subject, q.fact, q.system) == ("applies:system:clubhouse", Fact.INSTALLATION_STANDARD, "clubhouse")
    assert q.waiting == ("Sprinkler annual inspection", "Sprinkler five-year inspection")
    assert q.text().startswith("Sprinklers, the clubhouse: which standard was it installed under?")
    assert "NFPA 13R" in q.text() and "the record that states it" in q.text()
    assert q.settled_by().startswith("the approved plans, the building permit, or the installer's record")
    assert q.rules == (NFPA_25_SPRINKLERS.describe(),)


def test_the_id_is_stable_and_differs_by_subject_and_fact():
    first = asks.questions(applicable(_Profile((CLUBHOUSE, POOL), (ANNUAL,))))
    again = asks.questions(applicable(_Profile((POOL, CLUBHOUSE), (FIVE_YEAR, ANNUAL))))
    assert {q.id for q in first} == {q.id for q in again} and len({q.id for q in first}) == 2
    assert first[0].id == intake.ask_id(AskKind.APPLICABILITY, "applies:system:clubhouse", "installation_standard")


def test_a_profile_with_no_systems_gets_the_one_question_of_which_it_has():
    (q,) = asks.questions(applicable(_Profile()))
    assert q.fact is None and q.subject == asks.ASSOCIATION and q.key == asks.SYSTEMS_KEY
    assert q.text().startswith("Which life safety systems does the association have?")
    assert set(q.waiting) == {r.name for r in ROWS} and not q.choices()


def test_a_fact_about_the_development_is_the_associations_whichever_system_asked():
    second = LifeSafetySystem("alarm-b", "Fire alarm, building C", SystemKind.FIRE_ALARM)
    found = asks.questions(applicable(_Profile((ALARM, second), (LARGE, CONDO))))
    assert [(q.subject, q.fact) for q in found] == [(asks.ASSOCIATION, Fact.UNIT_COUNT),
                                                    (asks.ASSOCIATION, Fact.COMMON_INTEREST)]
    assert found[0].waiting == ("Alarm test, large developments",) and found[0].name == "the association"
    assert found[1].choices()[0] == "condominium" and found[0].choices() == ()


def test_the_date_is_never_a_question():
    later = Obligation("A later rule", "made-up row", every_years=1, applies=InForce(date(2030, 1, 1)))
    result = applicable(_Profile((ALARM,), (later,)))                       # no date given: undetermined
    assert result.undetermined and asks.questions(result) == ()


def test_the_question_as_the_queue_holds_it():
    (q,) = asks.questions(applicable(_Profile((CLUBHOUSE,))))
    ask = q.ask()
    assert (ask.id, ask.kind, ask.subject, ask.status) == (q.id, AskKind.APPLICABILITY, q.subject, AskStatus.OPEN)
    assert ask.choices == () and not intake.high_stakes(ask)               # a standard is answered with its record
    assert ask.evidence[0] == "decides: Sprinkler annual inspection; Sprinkler five-year inspection"
    assert any(line.startswith("settled by: ") for line in ask.evidence)
    assert ask.detail == {"fact": "installation_standard", "system": "clubhouse",
                          "subject": "Sprinklers, the clubhouse",
                          "waiting": ["Sprinkler annual inspection", "Sprinkler five-year inspection"],
                          "disagreement": False}
    assert json.loads(json.dumps(q.as_dict()))["decides"] == list(q.waiting)


# --- An answer is a fact with source ANSWER -----------------------------------------------------------------------


def test_an_answer_reaches_the_evaluation_as_a_fact_with_who_and_when():
    profile = _Profile((RISERS, CLUBHOUSE))
    (q,) = asks.questions(applicable(profile))
    found = asks.answered(_answer(q, "NFPA 13R; the 2006 permit, sheet FP-1"))
    (value,) = found.facts["clubhouse"]
    assert (value.fact, value.value, value.source) == (Fact.INSTALLATION_STANDARD, R13, Source.ANSWER)
    assert value.where.startswith(f"intake question {q.id}: Pat Example, 20")
    assert value.where.endswith("; the 2006 permit, sheet FP-1")
    result = applicable(profile, answers=found.facts)
    assert not result.undetermined and asks.questions(result) == ()         # nothing is asked again
    decided = [f for f in result.applies if f.system is CLUBHOUSE]
    assert len(decided) == 2 and all(any(v.source is Source.ANSWER for v in f.verdict.deciding) for f in decided)
    assert not any(v.source is Source.ANSWER for f in result.applies if f.system is RISERS for v in f.verdict.deciding)


@pytest.mark.parametrize("words", ["nfpa_13d; the plan set", "NFPA 13D; the plan set", "nfpa 13d ;the plan set"])
def test_an_answer_is_read_by_word_or_label(words):
    (q,) = asks.questions(applicable(_Profile((CLUBHOUSE,))))
    found = asks.answered(_answer(q, words))
    assert found.facts["clubhouse"][0].value is D13 and not found.unread
    result = applicable(_Profile((CLUBHOUSE,), (ANNUAL, FIVE_YEAR)), answers=found.facts)
    assert [f.verdict.answer for f in result.does_not_apply] == [Answer.DOES_NOT_APPLY] * 2
    assert not result.applies and not result.undetermined


def test_a_standard_without_its_record_or_outside_the_set_is_not_read():
    profile = _Profile((CLUBHOUSE,))
    (q,) = asks.questions(applicable(profile))
    for words, why in (("NFPA 13R", "no record named"), ("13; the permit", "not one of: NFPA 13, NFPA 13R")):
        found = asks.answered(_answer(q, words))
        assert not found.facts and not found.used
        ((ask, reason),) = found.unread
        assert ask.id == q.id and why in reason
        result = applicable(profile, answers=found.facts)
        assert len(result.undetermined) == 2                                # a miss stays a miss


def test_a_choice_by_number_and_a_number_fact():
    profile = _Profile((ALARM,), (LARGE, CONDO))
    count, kind = asks.questions(applicable(profile))
    queue = [count.ask(), kind.ask()]
    intake.answer(queue, kind.id, "2", "Pat Example")                       # the second choice, by its number
    intake.answer(queue, count.id, "1,204; the condominium plan", "Pat Example")
    found = asks.answered(queue)
    values = {v.fact: v for v in found.facts[None]}
    assert values[Fact.COMMON_INTEREST].value is CommonInterest.PLANNED_DEVELOPMENT
    assert values[Fact.COMMON_INTEREST].where.endswith("; no record named")
    assert values[Fact.UNIT_COUNT].value == 1204
    result = applicable(profile, answers=found.facts)
    assert [f.row.name for f in result.applies] == ["Alarm test, large developments"]
    assert [f.row.name for f in result.does_not_apply] == ["Condominium disclosure"]


def test_a_dismissed_or_open_question_gives_no_fact():
    (q,) = asks.questions(applicable(_Profile((CLUBHOUSE,))))
    assert not asks.answered([q.ask()]).facts
    found = asks.answered(_answer(q, "dismiss"))
    assert not found.facts and [a.id for a in found.dismissed] == [q.id]


def test_which_systems_there_are_is_noted_never_a_fact():
    (q,) = asks.questions(applicable(_Profile()))
    queue = _answer(q, "A wet sprinkler system in each building and one fire alarm panel")
    found = asks.answered(queue)
    assert not found.facts and [a.id for a in found.noted] == [q.id]
    ok, note = asks.applied_note(queue[0])
    assert ok and "Community.life_safety_systems()" in note
    lines = asks.question_lines(asks.questions(applicable(_Profile())), queue, found)
    assert "noted for the specification" in lines[1]


def test_a_fact_that_waits_for_a_second_person(monkeypatch):
    monkeypatch.setattr(asks, "CONFIRMED", frozenset({Fact.INSTALLATION_STANDARD}))
    (q,) = asks.questions(applicable(_Profile((CLUBHOUSE,))))
    queue = _answer(q, "NFPA 13R; the permit")
    assert intake.high_stakes(queue[0])
    found = asks.answered(queue)
    assert not found.facts and [a.id for a in found.waiting] == [q.id]
    intake.confirm(queue, q.id, "Lee Example")
    assert asks.answered(queue).facts["clubhouse"][0].value is R13


# --- Disagreement: jason picks neither ----------------------------------------------------------------------------


def test_an_answer_that_disagrees_with_the_profile_leaves_the_row_undetermined_with_both():
    profile = _Profile((RISERS,), (ANNUAL,))
    assert not asks.questions(applicable(profile))                          # the profile states 13R: nothing to ask
    # A person answers 13D for the same system (the question was filed before the profile stated the standard).
    earlier = asks.FactQuestion("applies:system:risers", Fact.INSTALLATION_STANDARD, "risers", RISERS.name)
    queue = _answer(earlier, "NFPA 13D; the plan set, sheet FP-1")
    found = asks.answered(queue)
    result = applicable(profile, answers=found.facts)
    (finding,) = result.undetermined
    assert not result.applies and not result.does_not_apply
    assert {(v.source, v.value) for v in finding.verdict.conflicting} == {(Source.PROFILE, R13), (Source.ANSWER, D13)}
    (q,) = asks.questions(result)
    assert q.id == earlier.id and q.disagreement and len(q.stated) == 2      # the same question, now a disagreement
    assert any("NFPA 13R (profile, the installer's letter of May 1, 2010)" == s for s in q.stated)
    assert any(s.startswith("NFPA 13D (answer, intake question ") for s in q.stated)
    assert "jason picks neither" in q.text()
    lines = asks.question_lines((q,), queue, found)
    assert "the sources disagree, so it is not settled" in lines[1]


def test_an_answer_that_agrees_on_the_outcome_stands_beside_the_profile():
    # 13 from a person, 13R from the profile: different values, neither is 13D, so the row applies under both.
    earlier = asks.FactQuestion("applies:system:risers", Fact.INSTALLATION_STANDARD, "risers", RISERS.name)
    found = asks.answered(_answer(earlier, "NFPA 13; the permit"))
    result = applicable(_Profile((RISERS,), (ANNUAL,)), answers=found.facts)
    assert [f.verdict.answer for f in result.applies] == [Answer.APPLIES] and not result.undetermined


def test_two_records_that_disagree_are_one_question_and_an_answer_does_not_settle_them():
    both = LifeSafetySystem("lobby", "Sprinklers, the lobby", SystemKind.FIRE_SPRINKLER, R13, "the permit",
                            (StandardReading(D13, "the plan set"),))
    profile = _Profile((both,), (ANNUAL, FIVE_YEAR))
    (q,) = asks.questions(applicable(profile))
    assert q.disagreement and q.stated == ("NFPA 13R (profile, the permit)", "NFPA 13D (profile, the plan set)")
    found = asks.answered(_answer(q, "NFPA 13R; the permit"))
    result = applicable(profile, answers=found.facts)
    assert len(result.undetermined) == 2                                    # the specification still states both
    (still,) = asks.questions(result)
    assert still.id == q.id and len(still.stated) == 3


# --- The queue: filing is a person's command, and nothing is asked twice ------------------------------------------


def test_filing_keeps_answers_and_asks_nothing_twice(tmp_path):
    profile = _Profile((CLUBHOUSE, POOL))
    result, found = task.evaluate(profile, tmp_path)
    assert not found.used and not intake.store_path(tmp_path).exists()      # reading files nothing
    first = asks.questions(result)
    assert task.file_questions(tmp_path, first) == {"new": 2, "kept": 0, "stale": 0}
    assert [a.kind for a in task.stored(tmp_path)] == [AskKind.APPLICABILITY] * 2

    queue = intake.load(tmp_path)
    clubhouse = next(q for q in first if q.system == "clubhouse")
    intake.answer(queue, clubhouse.id, "NFPA 13R; the 2006 permit", "Pat Example")
    intake.save(tmp_path, queue)

    result, found = task.evaluate(profile, tmp_path)
    again = asks.questions(result)
    assert [q.system for q in again] == ["pool"]                            # the answered one is not asked again
    assert [a.id for a, _ in found.used] == [clubhouse.id]
    assert task.file_questions(tmp_path, again) == {"new": 0, "kept": 1, "stale": 0}
    kept = {a.id: a for a in intake.load(tmp_path)}
    assert kept[clubhouse.id].status is AskStatus.ANSWERED and kept[clubhouse.id].answered_by == "Pat Example"

    # The profile now states the pool house's standard: its open question is no longer asked, and goes stale.
    stated = LifeSafetySystem("pool", "Sprinklers, the pool house", SystemKind.FIRE_SPRINKLER, R13, "the permit")
    result, _ = task.evaluate(_Profile((CLUBHOUSE, stated)), tmp_path)
    assert task.file_questions(tmp_path, asks.questions(result)) == {"new": 0, "kept": 0, "stale": 1}
    assert {a.status for a in intake.load(tmp_path)} == {AskStatus.ANSWERED, AskStatus.STALE}


def test_filing_leaves_the_other_questions_in_the_queue_alone(tmp_path):
    other = intake.Ask("abc", AskKind.CLASSIFY, "library:Example.pdf", "Which kind?")
    intake.save(tmp_path, [other])
    task.file_questions(tmp_path, asks.questions(applicable(_Profile((CLUBHOUSE,)))))
    kept = intake.load(tmp_path)
    assert [a.id for a in kept][0] == "abc" and kept[0].status is AskStatus.OPEN and len(kept) == 2


def test_apply_marks_a_read_answer_applied_and_refuses_one_it_cannot_read(tmp_path):
    first = asks.questions(applicable(_Profile((CLUBHOUSE, POOL))))
    queue = [q.ask() for q in first]
    intake.answer(queue, first[0].id, "NFPA 13R; the 2006 permit", "Pat Example")
    intake.answer(queue, first[1].id, "the usual one", "Pat Example")
    refused: list = []
    done = intake_task.apply(queue, tmp_path, refused=refused)
    assert [a.id for a in done] == [first[0].id] and done[0].status is AskStatus.APPLIED
    assert done[0].applied_to.startswith("a fact for jason applies: the installation standard: NFPA 13R (answer, ")
    ((ask, why),) = refused
    assert ask.id == first[1].id and why.startswith("not read as the installation standard: not one of: ")
    assert asks.answered(queue).facts["clubhouse"][0].value is R13          # an applied answer is still the fact


def test_the_lines_show_each_questions_state_and_the_answers_in_use():
    profile = _Profile((CLUBHOUSE, POOL))
    first = asks.questions(applicable(profile))
    queue = [first[0].ask()]
    intake.answer(queue, first[0].id, "NFPA 13R; the 2006 permit", "Pat Example")
    found = asks.answered(queue)
    text = "\n".join(asks.question_lines(asks.questions(applicable(profile, answers=found.facts)), queue, found))
    assert "Questions for a person (1)" in text and "applies:system:pool installation_standard (not filed)" in text
    assert "decides: Sprinkler annual inspection; Sprinkler five-year inspection" in text
    assert "Answers in use (1)" in text and "Sprinklers, the clubhouse: the installation standard: NFPA 13R (answer," in text


def test_the_queues_ranking_and_listing_take_the_new_kind(tmp_path):
    from jason.community.intake_rank import rank
    from jason.mcp.governance import answer_intake_question, intake_questions
    from jason.tasks.onboarding_session import unblocks_for

    (q,) = asks.questions(applicable(_Profile((CLUBHOUSE,))))
    ask = q.ask()
    unblocks = unblocks_for(ask, status={}, groups={}, gate_results=(), cited={})
    assert [r.ask.id for r in rank([ask], {ask.id: unblocks})] == [q.id]
    task.file_questions(tmp_path, (q,))
    listed = intake_questions(kind="applicability", data_dir=tmp_path)
    assert listed["count"] == 1 and listed["questions"][0]["id"] == q.id
    done = answer_intake_question(q.id, "NFPA 13R; the 2006 permit", "Pat Example", data_dir=tmp_path)
    assert done["status"] == "answered" and "highStakes" not in done
    assert task.answers(tmp_path).facts["clubhouse"][0].source is Source.ANSWER


# --- The command --------------------------------------------------------------------------------------------------


def test_the_command_lists_and_files_only_when_asked(tmp_path, monkeypatch, capsys):
    from jason.cli import build_parser

    monkeypatch.delenv("PAYHOA_CATALOG", raising=False)
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    args = build_parser().parse_args(["applies", "--questions", "--as-of", "2026-10-04"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "the questions the undetermined answers raise, as of 2026-10-04" in out and "Questions for a person (" in out
    assert not intake.store_path(tmp_path).exists()                         # listing files nothing
    args = build_parser().parse_args(["applies", "--questions", "--json"])
    assert args.func(args) == 0
    listed = json.loads(capsys.readouterr().out)["questions"]
    args = build_parser().parse_args(["applies", "--file-questions"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert f"filed {len(listed)} questions" in out
    assert {a.id for a in intake.load(tmp_path)} == {q["id"] for q in listed} if listed else not intake.load(tmp_path)
