"""A notice element only some notices need: its condition as data over the event's facts, and three answers.

Every notice and fact here is made up; none is an association's.
"""

from __future__ import annotations

import json

import pytest

from jason.community.applicability import (
    ALWAYS,
    Answer,
    ElectronicVoting,
    Facet,
    Fact,
    Facts,
    FactValue,
    MeetingFormat,
    RuleChangeKind,
    Source,
    facts_tested,
)
from jason.community.notice_catalog import requirement
from jason.community.notice_elements import SIGNS, Sign, Status, check, event_facts, missing
from jason.tasks import notice_templates as nt

ADOPTED = "THE TEXT OF THE RULE CHANGE AS ADOPTED\nRule 1.\n"
EMERGENCY = ADOPTED + "PURPOSE AND EFFECT\nThe purpose is safety.\nThis rule change expires on March 1, 2031.\n"
AGENDA = "Time: 6:30 p.m.\nPlace: by video conference\nAgenda: {AGENDA_ITEMS}\n"


def _said(fact, value, where="the agenda"):
    return Facts((FactValue(fact, value, Source.ANSWER, where),))


def test_a_conditional_sign_has_its_condition_and_its_words():
    conditional = [s for rows in SIGNS.values() for s in rows if s.applies is not ALWAYS]
    assert {s.when for s in conditional} == {
        "an emergency rule change (4360(d))", "a meeting held entirely by teleconference (4926)",
        "an association that uses electronic voting",
        "an association that allows voting by electronic secret ballot (5105)",
        "governing documents that require a quorum for an election of directors, unless one lower than 20 percent "
        "(5115(b)(6))",
        "an election to approve an amendment of the governing documents (5115(g))"}
    for sign in conditional:
        assert facts_tested(sign.applies) and all(f.facet is Facet.EVENT for f in facts_tested(sign.applies))
    for rows in SIGNS.values():
        assert all(not s.when for s in rows if s.applies is ALWAYS)
    with pytest.raises(ValueError):
        Sign("an element", "CIV 9999", when="only sometimes")               # words with no condition
    with pytest.raises(ValueError):
        Sign("an element", "CIV 9999", applies=conditional[0].applies)       # a condition with no words


def test_with_no_event_facts_the_element_is_undetermined_and_names_the_fact():
    unconditional, emergency = check(requirement("rule-change-adopted"), ADOPTED)
    assert unconditional.verdict is None and unconditional.required is True and unconditional.needs() == ""
    # As before the condition was data: checked, missing, and reported with its condition in the catalog's words.
    assert emergency.status is Status.MISSING and emergency.applies == "an emergency rule change (4360(d))"
    assert emergency.condition() == "only for an emergency rule change (4360(d))"
    # And now it says what it would take to know.
    assert emergency.verdict.answer is Answer.UNDETERMINED and emergency.verdict.missing == (Fact.RULE_CHANGE,)
    assert emergency.required is None and emergency.needs() == "unknown: whether the rule change is an emergency one"
    row = json.loads(json.dumps(emergency.row()))
    assert row["applies"] == "an emergency rule change (4360(d))" and row["answer"] == "undetermined"
    assert set(unconditional.row()) == {"requirement", "element", "cite", "status", "where", "applies"}


def test_a_rule_change_made_after_notice_does_not_need_the_emergency_element():
    facts = _said(Fact.RULE_CHANGE, RuleChangeKind.NOTICED, "the minutes of the meeting")
    found = check(requirement("rule-change-adopted"), ADOPTED, facts)
    assert [f.status for f in found] == [Status.PRESENT, Status.NOT_REQUIRED]
    spared = found[1]
    assert spared.required is False and not spared.ok and missing(found) == []
    assert spared.where == "decided by the rule change: made after notice (4360(a)) (answer, the minutes of the meeting)"


def test_an_emergency_rule_change_needs_it_and_a_notice_that_lacks_it_has_a_gap():
    facts = _said(Fact.RULE_CHANGE, RuleChangeKind.EMERGENCY)
    lacking = check(requirement("rule-change-adopted"), ADOPTED, facts)[1]
    assert lacking.status is Status.MISSING and lacking.required is True and lacking.needs() == ""
    assert lacking.condition() == "required here: an emergency rule change (4360(d))"
    carried = check(requirement("rule-change-adopted"), EMERGENCY, facts)[1]
    assert carried.status is Status.PRESENT and carried.required is True


@pytest.mark.parametrize("held, status", [
    (MeetingFormat.ENTIRELY_BY_TELECONFERENCE, Status.MISSING),
    (MeetingFormat.TELECONFERENCE_WITH_LOCATION, Status.NOT_REQUIRED),
    (MeetingFormat.IN_PERSON, Status.NOT_REQUIRED),
])
def test_the_teleconference_element_by_how_the_meeting_is_held(held, status):
    found = check(requirement("board-meeting"), AGENDA, _said(Fact.MEETING_FORMAT, held))
    assert found[2].status is status and all(f.ok for f in found[:2])
    assert check(requirement("board-meeting"), AGENDA)[2].needs() == "unknown: how the meeting is held"


def test_electronic_voting_may_be_the_profiles_fact():
    stated = Facts.build(profile={Fact.ELECTRONIC_VOTING: ElectronicVoting.NONE},
                         profile_where="Community.applicability_facts()")
    by_element = {f.element: f for f in check(requirement("annual-policy-statement"), "", stated)}
    voting = by_element["electronic voting opt-in or opt-out procedures (5105(i)(1)(D)), if used"]
    assert voting.status is Status.NOT_REQUIRED and "(profile, Community.applicability_facts())" in voting.where
    for rule in (ElectronicVoting.OPT_OUT, ElectronicVoting.OPT_IN):
        found = check(requirement("annual-policy-statement"), "", Facts.build(profile={Fact.ELECTRONIC_VOTING: rule}))
        assert next(f for f in found if f.element == voting.element).required is True


def test_event_facts_from_a_persons_words():
    facts = event_facts(["meeting_format=entirely_by_teleconference", " rule_change = emergency "], where="--event")
    assert [(v.fact, v.value, v.source, v.where) for v in facts.values] == [
        (Fact.MEETING_FORMAT, MeetingFormat.ENTIRELY_BY_TELECONFERENCE, Source.ANSWER, "--event"),
        (Fact.RULE_CHANGE, RuleChangeKind.EMERGENCY, Source.ANSWER, "--event")]
    with pytest.raises(ValueError, match="not a fact about the event; one of: meeting_format, rule_change, electronic_voting"):
        event_facts(["unit_count=12"])
    with pytest.raises(ValueError, match="rule_change: 'urgent' is not one of: noticed, emergency"):
        event_facts(["rule_change=urgent"])


def test_the_report_reads_as_before_without_facts_and_says_what_the_facts_decide():
    (base,) = nt.check_all(("rule-change-adopted",))
    line = next(x for x in nt.report_lines([base], law=False) if "emergency rule change: its text" in x)
    assert line == ("- **missing** (only for an emergency rule change (4360(d))): for an emergency rule change: its "
                    "text, purpose and effect, and the date it expires (it lasts at most 120 days) (CIV 4360(c), (d))")
    (base,) = nt.check_all(("rule-change-adopted",), _said(Fact.RULE_CHANGE, RuleChangeKind.NOTICED, "the minutes"))
    line = next(x for x in nt.report_lines([base], law=False) if "emergency rule change: its text" in x)
    assert line.startswith("- **does not apply**: for an emergency rule change:")
    assert line.endswith("; decided by the rule change: made after notice (4360(a)) (answer, the minutes)")
    (base,) = nt.check_all(("rule-change-adopted",), _said(Fact.RULE_CHANGE, RuleChangeKind.EMERGENCY))
    line = next(x for x in nt.report_lines([base], law=False) if "emergency rule change: its text" in x)
    assert line.startswith("- **missing** (required here: an emergency rule change (4360(d))): ")


def test_the_command_takes_the_events_facts(tmp_path, monkeypatch, capsys):
    from jason.cli import build_parser

    monkeypatch.delenv("PAYHOA_CATALOG", raising=False)
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    notice = tmp_path / "notice.md"
    notice.write_text(ADOPTED, encoding="utf-8")
    common = ["notice-check", "--file", str(notice), "--requirement", "rule-change-adopted", "--no-law"]
    assert (lambda a: a.func(a))(build_parser().parse_args(common)) == 0
    out = capsys.readouterr().out
    assert "rule-change-adopted: 1 of 2 elements shown" in out
    assert "    missing (only for an emergency rule change (4360(d))): for an emergency rule change" in out
    assert "      undetermined: unknown: whether the rule change is an emergency one (say it with --event rule_change=WORD)" in out
    assert (lambda a: a.func(a))(build_parser().parse_args(common + ["--event", "rule_change=noticed"])) == 0
    out = capsys.readouterr().out
    assert "rule-change-adopted: 1 of 2 elements shown, 1 that do not apply" in out
    assert "    does not apply: for an emergency rule change" in out and "    missing" not in out
    assert (lambda a: a.func(a))(build_parser().parse_args(common + ["--event", "rule_change=emergency"])) == 0
    assert "    missing (required here: an emergency rule change (4360(d))): " in capsys.readouterr().out
    assert (lambda a: a.func(a))(build_parser().parse_args(common + ["--event", "rule_change=urgent"])) == 2
    assert "is not one of: noticed, emergency" in capsys.readouterr().err
    assert not (tmp_path / "reports").exists()                              # a file check writes nothing
