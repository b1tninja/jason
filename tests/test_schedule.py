from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.base import MeetingSchedule
from jason.community.schedule import (Adoption, Anchor, Assignment, Role, Trigger, anchors_for, covering,
                                      occurrences)
from jason.tasks import schedule as task


def _a(key="k", **kw):
    fields = dict(title="T", role=Role.TREASURER, covers=("bylaws#9.6", "collection-policy", "notice:board-meeting"),
                  trigger=Trigger.CADENCE, every_months=1, day=15)
    fields.update(kw)
    return Assignment(key, **fields)


def test_an_assignment_covers_a_section_its_subsections_and_a_whole_document():
    a = _a()
    assert a.covers_ref("bylaws#9.6") and a.covers_ref("bylaws#9.6(a)") and a.covers_ref("collection-policy#6")
    assert a.covers_ref("notice:board-meeting")
    assert not a.covers_ref("bylaws#9.60") and not a.covers_ref("notice:board-meeting-executive")
    assert covering("bylaws#9.6(b)", (a, _a("other", covers=("ccrs#7",)))) == [a]


def test_cadences_and_anchored_clocks():
    start, end = date(2026, 1, 1), date(2026, 12, 31)
    assert len(occurrences(_a(), start, end)) == 12
    assert occurrences(_a(every_months=3, day=0), start, end) == [date(2026, 1, 31), date(2026, 4, 30),
                                                                  date(2026, 7, 31), date(2026, 10, 31)]
    assert occurrences(_a(every_months=12, month=10, day=1), start, end) == [date(2026, 10, 1)]
    community = SimpleNamespace(meeting_schedule=lambda: MeetingSchedule(1, 3, "7:00 pm", "Zoom", annual_month=11),
                                fiscal_year_end=lambda: (12, 31))
    anchors = anchors_for(community, start, end)
    assert anchors[Anchor.BOARD_MEETING][0] == date(2026, 1, 20)          # the third Tuesday
    assert anchors[Anchor.ANNUAL_MEETING] == [date(2026, 11, 17)]
    notice = _a(trigger=Trigger.ANCHORED, anchor=Anchor.BOARD_MEETING, offset_days=-4)
    assert occurrences(notice, start, end, anchors)[0] == date(2026, 1, 16)
    assert occurrences(_a(trigger=Trigger.EVENT, handled_by="x"), start, end, anchors) == []
    assert _a(trigger=Trigger.ANCHORED, anchor=Anchor.FISCAL_YEAR_END, offset_days=-30).cadence() == \
        "30 days before the fiscal year's end"


def test_the_agenda_marks_done_overdue_and_soon(tmp_path):
    community = SimpleNamespace(assignments=lambda: (_a(), _a("gone", adoption=Adoption.NOT_APPLICABLE)))
    task.record_done(tmp_path, "k", date(2026, 9, 15), date(2026, 9, 16), "A Person", "minutes 2026-09-15 item 4")
    with pytest.raises(ValueError):
        task.record_done(tmp_path, "k", date(2026, 10, 15), date(2026, 10, 15), "", "")
    found = task.agenda(community, tmp_path, start=date(2026, 9, 1), end=date(2026, 11, 30), today=date(2026, 10, 10))
    assert [(o.due.isoformat(), o.standing) for o in found] == [
        ("2026-09-15", "done"), ("2026-10-15", "due soon"), ("2026-11-15", "upcoming")]


def test_coverage_finds_the_unowned_and_the_unscheduled(tmp_path, monkeypatch):
    refs = [("bylaws#9.6(a)", "review quarterly", True), ("ccrs#7.8", "owners inspect", True),
            ("notice:board-meeting", "notice", True), ("bylaws#1.2", "purpose", False)]
    monkeypatch.setattr(task, "_refs", lambda c, d: refs)
    rows = (_a(covers=("bylaws#9.6", "notice:board-meeting")),
            _a("standing", covers=("ccrs#7",), trigger=Trigger.STANDING))
    community = SimpleNamespace(assignments=lambda: rows)
    covered, uncovered = task.coverage(community, tmp_path)
    assert [r for r, *_ in covered] == ["bylaws#9.6(a)", "ccrs#7.8", "notice:board-meeting"]
    assert uncovered == [("bylaws#1.2", "purpose")]
    assert [r for r, *_ in task.unscheduled(community, tmp_path)] == ["ccrs#7.8"]


def test_the_profile_owns_and_schedules_every_duty_it_knows():
    from jason.community import community

    rows = community().assignments()
    assert len({a.key for a in rows}) == len(rows)
    assert all(a.handled_by for a in rows if a.trigger is Trigger.EVENT)
