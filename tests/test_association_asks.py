"""The association's standing facts as questions: raised once where the profile does not state one, answered through
the intake queue, and then deciding the notice rows that waited on it.

Every profile, row, fact, and answer here is made up.
"""

from __future__ import annotations

import json

import pytest

from jason.community import applicability_asks as asks
from jason.community import intake
from jason.community.applicability import (
    Acclamation,
    AllOf,
    Answer,
    DirectorQuorum,
    ElectionKind,
    ElectronicVoting,
    Fact,
    Facts,
    FactValue,
    In,
    Is,
    Source,
    evaluate,
)
from jason.community.life_safety import applicable
from jason.community.notice_catalog import applicable as required
from jason.community.notice_elements import Conditional, conditionals
from jason.community.notices import NoticeRequirement, Recipients
from jason.tasks import applicability_asks as task
from test_profile import small_profile  # noqa: F401 - fixture: the throwaway profile, loaded by name

USED = In(Fact.ELECTRONIC_VOTING, frozenset({ElectronicVoting.OPT_OUT, ElectronicVoting.OPT_IN}), "used")
# Made-up notice rows: two wait on one standing fact, one on a standing fact and an event's, one on an event's alone.
PORTAL = NoticeRequirement("portal-notice", "How to reach the voting portal", "CIV 9999", Recipients.ALL_MEMBERS, None,
                           (), applies=USED)
PORTAL_HELP = NoticeRequirement("portal-help-notice", "Who helps with the voting portal", "CIV 9998",
                                Recipients.ALL_MEMBERS, None, (), applies=USED)
SEATING = NoticeRequirement("seating-notice", "That the board may seat the candidates", "CIV 9997",
                            Recipients.ALL_MEMBERS, None, (),
                            applies=AllOf(Is(Fact.ELECTION, ElectionKind.DIRECTORS),
                                          Is(Fact.ACCLAMATION, Acclamation.AVAILABLE)))
RECALL = NoticeRequirement("recall-notice", "A recall", "CIV 9996", Recipients.ALL_MEMBERS, None, (),
                           applies=Is(Fact.ELECTION, ElectionKind.RECALL))
ROWS = (PORTAL, PORTAL_HELP, SEATING, RECALL)


class _Profile:
    name = "Oak Ridge Owners Association"
    region = ""

    def __init__(self, facts=()):
        self._facts = tuple(facts)

    def life_safety_systems(self):
        return ()

    def obligations(self):
        return ()

    def applicability_facts(self):
        return self._facts


def _questions(profile, queue=()):
    found = asks.answered(queue)
    waiting = task.standing(profile, found, rows=conditionals(ROWS))
    return asks.questions(applicable(profile, answers=found.facts), waiting), found


def _answer(question, text, by="Pat Example"):
    queue = [question.ask()]
    intake.answer(queue, question.id, text, by)
    return queue


# --- Raised once --------------------------------------------------------------------------------------------------


def test_a_standing_fact_the_profile_does_not_state_is_one_question_however_many_rows_wait():
    found, _ = _questions(_Profile())
    assert [(q.subject, q.key) for q in found] == [("applies:association", "electronic_voting"),
                                                   ("applies:association", "acclamation")]
    voting, seating = found
    assert voting.waiting == ("notice portal-notice", "notice portal-help-notice") and voting.system == ""
    assert voting.text().startswith("The association: does an election operating rule allow electronic secret ballots")
    assert "after a semicolon, the record that states it" in voting.text()      # entered with the record
    assert voting.choices() == () and "not used" in voting.values()
    assert "settled by: the election operating rules" in voting.evidence()
    assert seating.waiting == ("notice seating-notice",)
    assert "the board's decision to record" in seating.text()
    # The same ids from run to run, so the queue asks nothing twice.
    assert [q.id for q in _questions(_Profile())[0]] == [q.id for q in found]


def test_a_fact_of_one_event_is_never_asked_in_advance():
    found, _ = _questions(_Profile())
    assert "election" not in {q.key for q in found}                         # what one election decides: its caller says
    assert not any("recall-notice" in name for q in found for name in q.waiting)
    assert Fact.ELECTION.per_event and not Fact.ACCLAMATION.per_event


def test_a_profile_that_states_the_fact_is_not_asked():
    stated = _Profile((FactValue(Fact.ELECTRONIC_VOTING, ElectronicVoting.NONE, Source.PROFILE, "Election Rules 4.2"),
                       FactValue(Fact.ACCLAMATION, Acclamation.NOT_USED, Source.PROFILE, "the board's resolution")))
    found, _ = _questions(stated)
    assert found == ()
    parts = required(task.association_facts(stated), ROWS)
    assert {r.key for r, _ in parts.does_not_apply} == {"portal-notice", "portal-help-notice", "seating-notice"}
    assert {r.key for r, _ in parts.undetermined} == {"recall-notice"}      # its event's fact is still its caller's


# --- Answered, and then deciding the row ----------------------------------------------------------------------------


def test_an_answer_becomes_a_fact_and_decides_the_rows_that_waited():
    profile = _Profile()
    (voting, _), _ = _questions(profile)
    before = required(task.association_facts(profile), ROWS)
    assert {r.key for r, _ in before.undetermined} == {r.key for r in ROWS}
    queue = _answer(voting, "used, with members opting out; Election Rules 4.2")
    after, found = _questions(profile, queue)
    assert [q.key for q in after] == ["acclamation"]                        # asked once, answered, not asked again
    (value,) = found.facts[None]
    assert value.fact is Fact.ELECTRONIC_VOTING and value.value is ElectronicVoting.OPT_OUT
    assert value.source is Source.ANSWER and "Pat Example" in value.where and value.where.endswith("; Election Rules 4.2")
    facts = task.association_facts(profile, found=found)
    parts = required(facts, ROWS)
    assert {r.key for r, _ in parts.applies} == {"portal-notice", "portal-help-notice"}
    (verdict,) = {v for r, v in parts.applies if r is PORTAL}
    assert [v.source for v in verdict.deciding] == [Source.ANSWER]
    assert asks.applied_note(queue[0]) == (True, f"a fact for jason applies: {value.describe()}")


def test_an_answer_of_none_rules_the_rows_out_with_the_answer_as_the_deciding_fact():
    profile = _Profile()
    (voting, _), _ = _questions(profile)
    _, found = _questions(profile, _answer(voting, "not used; no election rule mentions it (Election Rules, whole)"))
    (row, verdict), *_ = required(task.association_facts(profile, found=found), (PORTAL,)).does_not_apply
    assert row is PORTAL and verdict.deciding[0].source is Source.ANSWER


def test_an_answer_with_no_record_is_not_read_and_the_row_stays_undetermined():
    profile = _Profile()
    (voting, _), _ = _questions(profile)
    queue = _answer(voting, "not used")
    after, found = _questions(profile, queue)
    assert not found.facts and "no record named" in found.unread[0][1]
    assert [q.key for q in after] == ["electronic_voting", "acclamation"]   # still a question
    assert evaluate(PORTAL.applies, task.association_facts(profile, found=found)).answer is Answer.UNDETERMINED
    ok, why = asks.applied_note(queue[0])
    assert not ok and "no record named" in why


def test_an_answer_that_disagrees_with_the_profile_settles_nothing():
    profile = _Profile((FactValue(Fact.ELECTRONIC_VOTING, ElectronicVoting.NONE, Source.PROFILE, "the specification"),))
    bare = _Profile()
    (voting, _), _ = _questions(bare)
    queue = _answer(voting, "used, with members opting in; Election Rules 4.2")
    after, found = _questions(profile, queue)
    again = next(q for q in after if q.key == "electronic_voting")
    assert again.disagreement and len(again.stated) == 2 and again.id == voting.id
    assert "jason picks neither" in again.text()
    verdict = evaluate(PORTAL.applies, task.association_facts(profile, found=found))
    assert verdict.answer is Answer.UNDETERMINED and {v.source for v in verdict.conflicting} == {Source.PROFILE, Source.ANSWER}


def test_the_general_catalogs_standing_facts():
    found = asks.questions(applicable(_Profile()), task.standing(_Profile(), asks.Answered({})))
    by_key = {q.key: q for q in found}
    assert set(by_key) == {"electronic_voting", "acclamation", "director_quorum"}
    assert all(q.subject == "applies:association" for q in found)
    assert "notice electronic-opt-out-notice" in by_key["electronic_voting"].waiting
    assert any(name.startswith("notice annual-policy-statement: electronic voting") for name in by_key["electronic_voting"].waiting)
    assert by_key["acclamation"].waiting == ("notice acclamation-initial", "notice acclamation-reminder",
                                             "notice nomination-acknowledgment")
    assert by_key["director_quorum"].waiting == (
        "notice pre-ballot-notice: if the documents require a quorum: the statement about a reconvened meeting at a 20 "
        "percent quorum",)
    assert by_key["director_quorum"].settled_by() == "the bylaws' quorum section, or the election operating rules"
    assert conditionals((PORTAL, RECALL)) == (Conditional("notice portal-notice", USED, "CIV 9999"),
                                              Conditional("notice recall-notice", RECALL.applies, "CIV 9996"))


# --- The commands ---------------------------------------------------------------------------------------------------


@pytest.fixture
def oak_ridge(tmp_path, monkeypatch, small_profile):
    """A data folder of its own, with the throwaway profile of tests/test_profile.py as the active one: a real
    ``Community`` that states no applicability fact."""
    from jason.community import community

    assert community().applicability_facts() == () and community().name == "Small Community Association"
    from jason.config import default_data_dir

    monkeypatch.delenv("PAYHOA_CATALOG", raising=False)
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "data"))
    data = default_data_dir()                       # a second profile's own folder under the data root
    data.mkdir(parents=True)
    return data


def _run(*argv):
    from jason.cli import build_parser

    args = build_parser().parse_args(list(argv))
    return args.func(args)


def test_the_command_lists_files_and_reads_the_answer(oak_ridge, capsys):
    assert _run("applies", "--questions", "--json") == 0
    listed = {q["fact"]: q for q in json.loads(capsys.readouterr().out)["questions"]}
    assert set(listed) == {"electronic_voting", "acclamation", "director_quorum"}
    assert all(q["subject"] == "applies:association" and not q["filed"] for q in listed.values())
    assert not intake.store_path(oak_ridge).exists()                        # listing files nothing
    assert _run("applies", "--file-questions") == 0
    assert "filed 3 questions" in capsys.readouterr().out
    # Before the answer: undetermined, never "not required".
    assert _run("notices", "--catalog", "--fact", "election=directors") == 0
    out = capsys.readouterr().out
    assert "acclamation-initial" in out.split("Undetermined")[1].split("Set aside")[0]
    # A person answers through the queue's own path.
    assert _run("intake", "--answer", listed["acclamation"]["id"], "not used; board resolution 2031-04", "--by",
                "Pat Example") == 0
    capsys.readouterr()
    assert _run("notices", "--catalog", "--fact", "election=directors") == 0
    out = capsys.readouterr().out
    not_required = out.split("Does not apply: not required (")[1].split("Undetermined")[0]
    assert "acclamation-initial" in not_required and "acclamation-reminder" in not_required
    assert "decided by seating by acclamation: not used (answer, intake question" in not_required
    assert "board resolution 2031-04" in not_required
    # And it is not asked again.
    assert _run("applies", "--questions", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    state = {q["fact"]: q["status"] for q in data["questions"]}
    assert "acclamation" not in state and set(state) == {"electronic_voting", "director_quorum"}
    assert [a["fact"] for a in data["answersInUse"]] == ["acclamation"]


def test_the_notice_check_reads_the_answer_too(oak_ridge, capsys):
    assert _run("applies", "--file-questions") == 0
    capsys.readouterr()
    voting = next(a for a in intake.load(oak_ridge) if a.detail["fact"] == "electronic_voting")
    assert _run("intake", "--answer", voting.id, "not used; Election Rules, read whole", "--by", "Pat Example") == 0
    notice = oak_ridge / "statement.md"
    notice.write_text("The annual policy statement.\n", encoding="utf-8")
    assert _run("notice-check", "--file", str(notice), "--requirement", "annual-policy-statement", "--no-law") == 0
    out = capsys.readouterr().out
    assert "    does not apply: electronic voting opt-in or opt-out procedures (5105(i)(1)(D)), if used" in out
    assert "decided by electronic voting: not used (answer, intake question" in out
