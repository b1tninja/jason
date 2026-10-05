"""When a notice is required: a row's condition as data, three answers, and the catalog unchanged with no facts.

Every row, fact, and notice text here is made up, except where a test reads the catalog's own rows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from jason.community.applicability import (
    ALWAYS,
    Acclamation,
    AllOf,
    Answer,
    BoardMeetingKind,
    DirectorQuorum,
    ElectionKind,
    ElectronicVoting,
    Facet,
    Fact,
    Facts,
    FactValue,
    Is,
    MeetingFormat,
    RuleChangeKind,
    RuleScope,
    Source,
    evaluate,
    facts_tested,
)
from jason.community import notice_conditions as conditions
from jason.community.notice_catalog import (REQUIREMENTS, about, applicable, applicable_lines, conditional, line,
                                            requirement)
from jason.community.notice_elements import Status, check, event_facts
from jason.community.notices import Method, NoticeKind, NoticeRequirement, Recipients

DATA = Path(__file__).resolve().parents[1] / "data"
A, N, U = Answer.APPLIES, Answer.DOES_NOT_APPLY, Answer.UNDETERMINED

# Made-up rows: one required only for an election of directors where a made-up standing fact holds, one always.
BALLOT_BOX = NoticeRequirement(
    "ballot-box-notice", "Where the ballot box stands", "CIV 9999", Recipients.ALL_MEMBERS, NoticeKind.GENERAL,
    (Method.GENERAL,), content=("where the ballot box stands",), note="Elections of directors only, and only where a "
    "quorum is required.",
    applies=AllOf(Is(Fact.ELECTION, ElectionKind.DIRECTORS), Is(Fact.DIRECTOR_QUORUM, DirectorQuorum.AT_LEAST_20_PERCENT)))
NEWSLETTER = NoticeRequirement("newsletter", "A newsletter", "CIV 9998", Recipients.ALL_MEMBERS, NoticeKind.GENERAL,
                               (Method.GENERAL,))
ROWS = (BALLOT_BOX, NEWSLETTER)


def _said(*pairs, where="the secretary"):
    return Facts(tuple(FactValue(fact, value, Source.ANSWER, where) for fact, value in pairs))


def _answers(parts):
    return ({r.key for r, _ in parts.applies}, {r.key for r, _ in parts.does_not_apply},
            {r.key for r, _ in parts.undetermined})


# --- A made-up row: required, not required, undetermined ----------------------------------------------------------


def test_a_row_is_required_when_its_condition_holds():
    facts = _said((Fact.ELECTION, ElectionKind.DIRECTORS), (Fact.DIRECTOR_QUORUM, DirectorQuorum.AT_LEAST_20_PERCENT))
    parts = applicable(facts, ROWS)
    assert _answers(parts) == ({"ballot-box-notice", "newsletter"}, set(), set())
    row, verdict = parts.applies[0]
    assert row is BALLOT_BOX and {v.fact for v in verdict.deciding} == {Fact.ELECTION, Fact.DIRECTOR_QUORUM}


def test_a_row_is_not_required_with_the_fact_that_decided_it():
    parts = applicable(_said((Fact.ELECTION, ElectionKind.AMENDMENT)), ROWS)
    assert _answers(parts) == ({"newsletter"}, {"ballot-box-notice"}, set())
    (row, verdict), = parts.does_not_apply
    # One known "no" decides it, whatever the missing quorum fact would say.
    assert [v.describe() for v in verdict.deciding] == [
        "the election: election to approve an amendment of the governing documents (answer, the secretary)"]
    assert not verdict.missing


def test_a_row_is_undetermined_with_the_missing_fact_and_never_not_required():
    parts = applicable(_said((Fact.ELECTION, ElectionKind.DIRECTORS)), ROWS)
    assert _answers(parts) == ({"newsletter"}, set(), {"ballot-box-notice"})
    (_, verdict), = parts.undetermined
    assert verdict.missing == (Fact.DIRECTOR_QUORUM,)
    assert verdict.question() == ("unknown: whether the governing documents require a quorum for an election of "
                                  "directors, and whether it is lower than 20 percent")
    # No facts at all: still a question, and a row with no condition is required whenever its event happens.
    bare = applicable(None, ROWS)
    assert _answers(bare) == ({"newsletter"}, set(), {"ballot-box-notice"})
    assert bare.undetermined[0][1].missing == (Fact.ELECTION, Fact.DIRECTOR_QUORUM)


def test_two_sources_that_disagree_leave_the_row_undetermined():
    facts = _said((Fact.ELECTION, ElectionKind.DIRECTORS), (Fact.DIRECTOR_QUORUM, DirectorQuorum.NONE)).merge(
        Facts.build(profile={Fact.DIRECTOR_QUORUM: DirectorQuorum.AT_LEAST_20_PERCENT}, profile_where="the profile"))
    (_, verdict), = applicable(facts, (BALLOT_BOX,)).undetermined
    assert {v.source for v in verdict.conflicting} == {Source.ANSWER, Source.PROFILE} and not verdict.missing


def test_a_row_about_another_kind_of_event_is_set_aside_not_answered():
    hearing = NoticeRequirement("made-up-meeting", "A meeting", "CIV 9997", Recipients.ALL_MEMBERS, None, (),
                                applies=Is(Fact.MEETING_FORMAT, MeetingFormat.IN_PERSON))
    standing = NoticeRequirement("made-up-standing", "A standing notice", "CIV 9996", Recipients.ALL_MEMBERS, None, (),
                                 applies=Is(Fact.ELECTRONIC_VOTING, ElectronicVoting.OPT_IN))
    rows = (BALLOT_BOX, hearing, standing)
    assert conditional((*rows, NEWSLETTER)) == rows
    kept, aside = about(rows, {Fact.ELECTION})
    assert kept == (BALLOT_BOX, standing) and aside == (hearing,)      # a standing fact's row is about every event
    kept, aside = about(rows, {Fact.BOARD_MEETING})                    # the same kind of event as the meeting's format
    assert kept == (hearing, standing) and aside == (BALLOT_BOX,)
    assert about(rows, ()) == (rows, ())                               # nothing said: every row is asked


def test_the_lines_show_the_three_groups_and_how_to_settle_each():
    said = _said((Fact.ELECTION, ElectionKind.DIRECTORS), where="jason notices --fact")
    text = "\n".join(applicable_lines(said, {Fact.ELECTION}, ROWS))
    assert "1 of 2 notice requirements are required only for some events." in text
    assert "Applies: required when its event happens, on its clock (0)" in text
    assert "Does not apply: not required (0)" in text
    assert "Undetermined: the facts do not say, which is never \"not required\" (1)" in text
    assert ("      unknown: whether the governing documents require a quorum for an election of directors, and whether "
            "it is lower than 20 percent: a standing fact: the profile states it, or jason applies --questions asks a "
            "person") in text
    bare = "\n".join(applicable_lines(None, (), ROWS))
    assert "      unknown: what the election decides (directors, a recall, an assessment, an amendment): say it with " \
           "--fact election=WORD (directors, recall, assessment, amendment, exclusive_use, other)" in bare
    assert "Facts on hand" not in bare


# --- The catalog's own rows ---------------------------------------------------------------------------------------

CONVERTED = {
    "board-meeting": conditions.ORDINARY_BOARD_MEETING,
    "board-meeting-executive": conditions.EXECUTIVE_SESSION_ONLY_MEETING,
    "board-meeting-emergency": conditions.EMERGENCY_BOARD_MEETING,
    "teleconference-meeting": conditions.ENTIRELY_BY_TELECONFERENCE,
    "nomination-procedure": conditions.DIRECTOR_OR_RECALL_ELECTION,
    "acclamation-initial": conditions.ACCLAMATION_KEPT_AVAILABLE,
    "acclamation-reminder": conditions.ACCLAMATION_KEPT_AVAILABLE,
    "nomination-acknowledgment": conditions.ACCLAMATION_KEPT_AVAILABLE,
    "pre-ballot-notice": conditions.DIRECTOR_OR_RECALL_ELECTION,
    "electronic-ballot-notice": conditions.ELECTRONIC_SECRET_BALLOT,
    "electronic-opt-out-notice": conditions.ELECTRONIC_VOTING_OPT_OUT,
    "reconvened-election-meeting": conditions.DIRECTOR_ELECTION,
    "rule-change-proposed": conditions.LISTED_RULE_CHANGE_NOT_EMERGENCY,
    "rule-change-adopted": conditions.LISTED_RULE_CHANGE,
    "rule-change-reversal-results": conditions.LISTED_RULE_CHANGE_NOT_EMERGENCY,
}


def test_the_converted_rows_and_no_others_carry_a_condition():
    assert {r.key: r.applies for r in conditional()} == CONVERTED
    assert all(r.applies is ALWAYS for r in REQUIREMENTS if r.key not in CONVERTED)
    for row in conditional():
        tested = facts_tested(row.applies)
        assert tested and all(f.facet is Facet.EVENT for f in tested), row.key
        assert row.note or row.key in ("acclamation-reminder", "electronic-ballot-notice"), row.key   # the prose stays


def test_with_no_facts_every_conditional_row_is_undetermined_and_the_rest_apply():
    parts = applicable()
    assert not parts.does_not_apply
    assert {r.key for r, _ in parts.undetermined} == set(CONVERTED)
    assert len(parts.applies) == len(REQUIREMENTS) - len(CONVERTED)
    assert all(verdict.question() for _, verdict in parts.undetermined)


def _old_line(r):
    """The catalog's line as ``jason notices --catalog`` wrote it before a row could carry a condition."""
    clock = "; ".join(t.describe() for t in r.timing) or (f"with {r.carried_by}" if r.carried_by else "")
    kind = r.kind.value if r.kind else ", ".join(m.name.lower() for m in r.methods) or "no delivery"
    return f"  {r.key:32} {r.statute:10} {kind:28} {clock}" + ("" if r.verified else "  [unverified]")


def test_with_no_facts_the_catalog_prints_as_before(capsys):
    from jason.cli import build_parser

    assert [line(r) for r in REQUIREMENTS] == [_old_line(r) for r in REQUIREMENTS]
    args = build_parser().parse_args(["notices", "--catalog"])
    assert args.func(args) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:len(REQUIREMENTS)] == [_old_line(r) for r in REQUIREMENTS]
    assert not any("Undetermined" in text or "Applies" in text for text in out)
    for key in ("rule-change-proposed", "pre-ballot-notice", "annual-budget-report"):
        args = build_parser().parse_args(["notices", key, "--catalog"])
        assert args.func(args) == 0
        out = capsys.readouterr().out
        assert "when required" not in out and "element \"" not in out
        row = requirement(key)
        assert out.splitlines()[0].startswith(f"{row.title} [{row.key}; {row.statute}")
        assert f"  {row.note}" in out


@pytest.mark.parametrize("said, applies, not_required", [
    # A rule change on a listed subject, made after notice: all three notices.
    ({Fact.RULE_SCOPE: RuleScope.LISTED_SUBJECT, Fact.RULE_CHANGE: RuleChangeKind.NOTICED},
     {"rule-change-proposed", "rule-change-adopted", "rule-change-reversal-results"}, set()),
    # An emergency rule change: no notice before it, none of a reversal vote; the adopted notice still goes.
    ({Fact.RULE_SCOPE: RuleScope.LISTED_SUBJECT, Fact.RULE_CHANGE: RuleChangeKind.EMERGENCY},
     {"rule-change-adopted"}, {"rule-change-proposed", "rule-change-reversal-results"}),
    # Outside 4355: none of the three, whether or not it is an emergency one.
    ({Fact.RULE_SCOPE: RuleScope.NOT_REACHED},
     set(), {"rule-change-proposed", "rule-change-adopted", "rule-change-reversal-results"}),
    ({Fact.BOARD_MEETING: BoardMeetingKind.ORDINARY}, {"board-meeting"},
     {"board-meeting-executive", "board-meeting-emergency"}),
    ({Fact.BOARD_MEETING: BoardMeetingKind.EXECUTIVE_SESSION_ONLY}, {"board-meeting-executive"},
     {"board-meeting", "board-meeting-emergency"}),
    ({Fact.BOARD_MEETING: BoardMeetingKind.EMERGENCY}, {"board-meeting-emergency"},
     {"board-meeting", "board-meeting-executive"}),
    ({Fact.MEETING_FORMAT: MeetingFormat.ENTIRELY_BY_TELECONFERENCE}, {"teleconference-meeting"}, set()),
    ({Fact.MEETING_FORMAT: MeetingFormat.TELECONFERENCE_WITH_LOCATION}, set(), {"teleconference-meeting"}),
    # An election of directors, acclamation kept available, electronic voting by opt-out.
    ({Fact.ELECTION: ElectionKind.DIRECTORS, Fact.ACCLAMATION: Acclamation.AVAILABLE,
      Fact.ELECTRONIC_VOTING: ElectronicVoting.OPT_OUT},
     {"nomination-procedure", "pre-ballot-notice", "acclamation-initial", "acclamation-reminder",
      "nomination-acknowledgment", "reconvened-election-meeting", "electronic-ballot-notice",
      "electronic-opt-out-notice"}, set()),
    # A recall: the 5115(a) and (b) notices, not the acclamation ones or a reconvened meeting to elect directors.
    ({Fact.ELECTION: ElectionKind.RECALL, Fact.ACCLAMATION: Acclamation.AVAILABLE,
      Fact.ELECTRONIC_VOTING: ElectronicVoting.NONE},
     {"nomination-procedure", "pre-ballot-notice"},
     {"acclamation-initial", "acclamation-reminder", "nomination-acknowledgment", "reconvened-election-meeting",
      "electronic-ballot-notice", "electronic-opt-out-notice"}),
    # An assessment vote is never by electronic secret ballot (5105(i)), though the opt-out deadline's notice stands.
    ({Fact.ELECTION: ElectionKind.ASSESSMENT, Fact.ELECTRONIC_VOTING: ElectronicVoting.OPT_OUT},
     {"electronic-opt-out-notice"},
     {"nomination-procedure", "pre-ballot-notice", "acclamation-initial", "acclamation-reminder",
      "nomination-acknowledgment", "reconvened-election-meeting", "electronic-ballot-notice"}),
    # Opt-in voting: the ballot's notice, not the opt-out deadline's.
    ({Fact.ELECTION: ElectionKind.AMENDMENT, Fact.ELECTRONIC_VOTING: ElectronicVoting.OPT_IN},
     {"electronic-ballot-notice"},
     {"nomination-procedure", "pre-ballot-notice", "acclamation-initial", "acclamation-reminder",
      "nomination-acknowledgment", "reconvened-election-meeting", "electronic-opt-out-notice"}),
    # An association that does not use acclamation owes none of 5103's notices.
    ({Fact.ACCLAMATION: Acclamation.NOT_USED}, set(),
     {"acclamation-initial", "acclamation-reminder", "nomination-acknowledgment"}),
])
def test_the_catalogs_rows_by_the_events_facts(said, applies, not_required):
    facts = _said(*said.items())
    shown, _ = about(conditional(), {f for f in said if f.per_event})
    parts = applicable(facts, shown)
    assert {r.key for r, _ in parts.applies} == applies
    assert {r.key for r, _ in parts.does_not_apply} == not_required


def test_the_proposed_rule_change_reads_as_the_statute_does():
    row = requirement("rule-change-proposed")
    assert row.applies.describe() == ("the rule change's subject is one listed in 4355(a), except where the rule change "
                                      "is an emergency rule change (4360(d))")
    emergency = evaluate(row.applies, _said((Fact.RULE_CHANGE, RuleChangeKind.EMERGENCY), where="the minutes"))
    assert emergency.answer is N                                           # decided without the rule's subject
    assert [v.describe() for v in emergency.deciding] == [
        "the rule change: an emergency rule change (4360(d)) (answer, the minutes)"]
    noticed = evaluate(row.applies, _said((Fact.RULE_CHANGE, RuleChangeKind.NOTICED)))
    assert noticed.answer is U and noticed.missing == (Fact.RULE_SCOPE,)


# The words each condition rests on, checked against the shelf: a change in the law fails the build.
WORDS = [
    ("CIV 4355", r"Sections 4360 and 4365 only apply to an operating rule that relates to one or more of the following "
                 r"subjects"),
    ("CIV 4355", r"Sections 4360 and 4365 do not apply to the following actions by the board"),
    ("CIV 4360", r"Notice is not required under this subdivision if the board determines that an immediate rule change "
                 r"is necessary"),
    ("CIV 4360", r"it may make an emergency rule change, and no notice is required, as specified in subdivision \(a\)"),
    ("CIV 4365", r"This section does not apply to an emergency rule change made under subdivision \(d\) of Section 4360"),
    ("CIV 4920", r"Except as provided in subdivision \(b\), the association shall give notice of the time and place of a "
                 r"board meeting at least four days before the meeting"),
    ("CIV 4920", r"If a board meeting is an emergency meeting held pursuant to Section 4923, the association is not "
                 r"required to give notice"),
    ("CIV 4920", r"If a nonemergency board meeting is held solely in executive session"),
    ("CIV 4926", r"conducted entirely by teleconference, without any physical location being held open"),
    ("CIV 4926", r"The notice for each meeting conducted under this section includes"),
    ("CIV 5100", r"elections regarding assessments legally requiring a vote, election and removal of directors, "
                 r"amendments to the governing documents, or the grant of exclusive use of common area"),
    ("CIV 5100", r"an election on any topic that is expressly identified in the operating rules"),
    ("CIV 5103", r"the association may, but is not required to, consider the qualified candidates elected by "
                 r"acclamation if all of the following conditions have been met"),
    ("CIV 5103", r"The number of board positions that will be filled at the election"),
    ("CIV 5105", r"to conduct an election by electronic secret ballot, except for an election regarding regular or "
                 r"special assessments"),
    ("CIV 5105", r"For an election operating rule where members are permitted to opt out of voting by electronic "
                 r"secret ballot to vote by written ballot, the association shall provide individual notice"),
    ("CIV 5115", r"This subdivision shall only apply to elections of directors and to recall elections"),
    ("CIV 5115", r"For elections of directors and for recall elections, an association shall provide general notice"),
    ("CIV 5115", r"If the association allows for voting in an election by electronic secret ballot as provided for in "
                 r"Section 5105"),
    ("CIV 5115", r"If the association.s governing documents require a quorum for an election of directors, a statement "
                 r"that the association may call a reconvened meeting"),
    ("CIV 5115", r"This paragraph shall not apply if the governing documents of the association provide for a quorum "
                 r"lower than 20 percent"),
    ("CIV 5115", r"For an election of directors of an association, and in the absence of meeting a quorum"),
    ("CIV 5115", r"in an election to approve an amendment of the governing documents, the text of the proposed "
                 r"amendment shall be delivered to the members with the ballot"),
]


@pytest.mark.parametrize("section, words", WORDS, ids=[f"{s} {w[:40]}" for s, w in WORDS])
def test_the_statute_on_disk_carries_the_words_a_condition_rests_on(section, words):
    from jason.tasks.export_authorities import authority_text

    text = authority_text(DATA, section).get("text") or ""
    if not text:
        pytest.skip(f"{section} is not exported here (jason export-authorities)")
    assert re.search(words, re.sub(r"\s+", " ", text), re.I), (
        f"{section} no longer reads '{words}'; the law may have changed: read the section and the condition written "
        "from it (jason.community.notice_conditions)")


# --- Conditional elements of the election notices ------------------------------------------------------------------

PRE_BALLOT = ("Ballots must be returned by mail or by hand to the inspector of elections at 123 Main St by 5 p.m.\n"
              "The ballots will be counted at the meeting. Date: May 1. Time: 6 p.m. Place: the clubhouse.\n"
              "Candidates: Pat Example and Lee Sample.\n")


@pytest.mark.parametrize("quorum, status", [
    (DirectorQuorum.AT_LEAST_20_PERCENT, Status.MISSING),
    (DirectorQuorum.BELOW_20_PERCENT, Status.NOT_REQUIRED),
    (DirectorQuorum.NONE, Status.NOT_REQUIRED),
])
def test_the_quorum_statement_by_what_the_documents_require(quorum, status):
    facts = _said((Fact.DIRECTOR_QUORUM, quorum), (Fact.ELECTRONIC_VOTING, ElectronicVoting.NONE))
    found = {f.element: f for f in check(requirement("pre-ballot-notice"), PRE_BALLOT, facts)}
    statement = found["if the documents require a quorum: the statement about a reconvened meeting at a 20 percent quorum"]
    assert statement.status is status
    electronic = found["for electronic voting: when electronic ballots are due and preliminary instructions"]
    assert electronic.status is Status.NOT_REQUIRED
    assert all(f.ok for f in found.values() if f.verdict is None)          # the made-up notice carries the rest
    carried = check(requirement("pre-ballot-notice"), PRE_BALLOT + "If the quorum is not reached, a reconvened meeting "
                    "may be held at which the quorum is 20 percent of the members.\n", facts)
    assert next(f for f in carried if f.element == statement.element).ok is (status is Status.MISSING)


def test_with_no_facts_the_election_elements_are_undetermined_and_name_the_fact():
    found = check(requirement("pre-ballot-notice"), PRE_BALLOT)
    needs = [f.needs() for f in found if f.verdict is not None]
    assert needs == ["unknown: whether an election rule allows electronic secret ballots",
                     "unknown: whether the governing documents require a quorum for an election of directors, and "
                     "whether it is lower than 20 percent"]
    amendment = check(requirement("ballots"), "", _said((Fact.ELECTION, ElectionKind.DIRECTORS)))[-1]
    assert amendment.status is Status.NOT_REQUIRED
    needed = check(requirement("ballots"), "The text of the proposed amendment is enclosed.",
                   _said((Fact.ELECTION, ElectionKind.AMENDMENT)))[-1]
    assert needed.status is Status.PRESENT and needed.required is True


# --- The command ----------------------------------------------------------------------------------------------------


def test_the_command_sorts_the_catalog_by_the_facts_said(capsys):
    from jason.cli import build_parser

    args = build_parser().parse_args(["notices", "--catalog", "--fact", "election=amendment"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "  the election: election to approve an amendment of the governing documents (answer, jason notices --fact)" in out
    not_required = out.split("Does not apply: not required (")[1].split("Undetermined")[0]
    assert "nomination-procedure" in not_required and "pre-ballot-notice" in not_required
    assert "decided by the election: election to approve an amendment of the governing documents" in not_required
    assert "Set aside (7): each turns on another kind of event" in out and "rule-change-proposed" in out
    args = build_parser().parse_args(["notices", "nomination-procedure", "--catalog", "--fact", "election=recall"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "  when required: applies: the election is an election of directors or a recall election (5115(a), (b))" in out
    assert "    decided by the election: recall election (answer, jason notices --fact)" in out
    args = build_parser().parse_args(["notices", "annual-budget-report", "--catalog", "--required"])
    assert args.func(args) == 0
    assert "  when required: always (the row carries no condition" in capsys.readouterr().out
    args = build_parser().parse_args(["notices", "--catalog", "--fact", "election=coronation"])
    assert args.func(args) == 2
    assert "election: 'coronation' is not one of: directors, recall" in capsys.readouterr().err
    assert event_facts(["acclamation=available"]).values[0].value is Acclamation.AVAILABLE
