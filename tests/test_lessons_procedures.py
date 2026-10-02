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
