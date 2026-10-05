import re
from pathlib import Path

from jason.community.lessons import LESSONS, Area, Status, for_area, lessons
from jason.community.procedures import PROCEDURES, find, lines, procedures


def test_lessons_and_procedures_are_each_named_once():
    assert len({l.key for l in LESSONS}) == len(LESSONS)
    assert len({p.key for p in PROCEDURES}) == len(PROCEDURES)


def test_a_fixed_lesson_names_its_guard_and_every_lesson_says_what_changes():
    for lesson in LESSONS:
        assert lesson.what and lesson.why and lesson.change, lesson.key
        if lesson.status is Status.FIXED:
            assert lesson.guards, f"{lesson.key} is fixed but names no guard"


def test_every_lesson_a_step_names_exists():
    known = {l.key for l in lessons()}
    for proc in PROCEDURES:
        for step in proc.steps:
            for key in step.lessons:
                assert key in known, f"{proc.key} names an unknown lesson {key}"


def _subcommands() -> set[str]:
    import argparse

    from jason.cli import build_parser

    parser = build_parser()
    return {name for action in parser._actions if isinstance(action, argparse._SubParsersAction)
            for name in action.choices}


def test_every_jason_command_a_step_names_is_a_command_the_parser_has():
    """A step's command is what a person types next year: ``jason WORD`` must be a subcommand the CLI registers."""
    known = _subcommands()
    assert "sop" in known
    for proc in PROCEDURES:
        for step in proc.steps:
            for name in re.findall(r"(?<![\w-])jason ([a-z][a-z0-9-]*)", step.command):
                assert name in known, f"{proc.key}: step names a command the CLI lacks: jason {name}"


def test_every_procedure_and_doc_a_step_refers_to_exists():
    """A ``procedure KEY`` reference names a procedure here, and a ``docs/...md`` reference a page on disk."""
    root = Path(__file__).resolve().parents[1]
    keys = {p.key for p in PROCEDURES}
    for proc in PROCEDURES:
        for ref in proc.refs + tuple(r for step in proc.steps for r in step.refs):
            if ref.startswith("procedure "):
                assert ref.split(" ", 1)[1] in keys, f"{proc.key} refers to an unknown procedure: {ref}"
            elif ref.startswith("docs/"):
                page = ref.split(" (", 1)[0]
                assert (root / page).is_file(), f"{proc.key} refers to a page not on disk: {page}"


def test_the_election_rule_change_and_board_meeting_procedures_say_the_events_facts():
    """Each of the three runs the catalog with the event's facts before its first notice, and names the lesson that
    put the conditions into data, so an undetermined row is answered rather than read as not required."""
    for key, fact in (("election", "election="), ("rule-change", "rule_scope="), ("board-packet", "board_meeting=")):
        proc = find(key)
        assert proc is not None, key
        steps = [s for s in proc.steps if "jason notices --catalog --fact" in s.command and fact in s.command]
        assert steps, f"{key} has no step that runs jason notices --catalog --fact {fact}WORD"
        assert "a-condition-kept-as-prose-cannot-be-asked" in steps[0].lessons
        assert "undetermined" in steps[0].do or "undetermined" in steps[0].check


def test_a_community_adds_its_own_lessons_and_procedures():
    from jason.community.lessons import Lesson
    from jason.community.procedures import Procedure, Step
    from datetime import date

    class Community:
        def lessons(self):
            return (Lesson("ours", date(2026, 10, 2), (Area.MAILROOM,), "w", "y", "c", Status.DECISION),)

        def procedures(self):
            return (Procedure("our-task", "Ours", "now", (Area.MAILROOM,), "p", (Step("do it"),)),)

    community = Community()
    assert [l.key for l in for_area(Area.MAILROOM, community, open_only=True)][-1] == "ours"
    assert find("our-task", community) is not None and len(procedures(community)) == len(PROCEDURES) + 1
    printed = "\n".join(lines(find("mailroom-letter", community), community))
    assert "1. Keep the PDF to four pages" in printed and "**ours** (decision)" in printed
