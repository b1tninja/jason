"""People's own Google Tasks and calendar events, read beside what jason tracks (made-up titles only)."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from jason.community.board_items import BoardItem, ItemCategory
from jason.community.people_tasks import Kind, PeopleTaskRule, Tracker, normal_title
from jason.community.schedule import Anchor, Assignment, Role, Trigger, anchors_for, occurrences, policy_renewals
from jason.tasks import attention, board_items, people_tasks as pt
from jason.tasks.attention import Urgency

ON = date(2026, 10, 2)
FIXTURE = Path(__file__).parent / "fixtures" / "people" / "google-read.json"


def _raw():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _community(rules=None, assignments=None):
    monthly = Assignment("monthly-review", "Monthly review", Role.TREASURER, ("CIV 5500",), Trigger.CADENCE,
                         every_months=1, day=15)
    widget = Assignment("widget-renewal", "The widget license renewed", Role.SECRETARY, ("bylaws#9.9",),
                        Trigger.CADENCE, every_months=12, month=3, day=1)
    meetings = Assignment("board-meetings", "The board's meetings", Role.BOARD, ("CIV 4900",), Trigger.ANCHORED,
                          anchor=Anchor.BOARD_MEETING)
    default_rules = (
        PeopleTaskRule("old-report", r"old report", "a report no longer required", retire="the rule was withdrawn"),
        PeopleTaskRule("widget", r"widget", "the widget license", Tracker.ASSIGNMENT, "widget-renewal", recurring=True),
    )
    return SimpleNamespace(assignments=lambda: assignments if assignments is not None else (monthly, widget, meetings),
                           obligations=lambda: (), people_task_rules=lambda: default_rules if rules is None else rules)


def _store(tmp_path, raw=None):
    path = pt.store_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw or _raw()), encoding="utf-8")
    board_items.save(tmp_path, [BoardItem("lobby-bulb", "Replace the lobby bulb", "s", "a", ItemCategory.GOVERNANCE)])


def test_titles_fold_for_comparing():
    assert normal_title("Trim the hedges!") == normal_title("trim  THE hedges") == "trim the hedges"


def test_jason_own_items_and_task_mirrors_are_left_out(tmp_path):
    _store(tmp_path)
    r = pt.classify(_community(), tmp_path, on=ON)
    titles = {i.title for i in r.found}
    assert "Our own" not in titles and "Due: Monthly review" not in titles          # a marker; a schedule role list
    assert "Monthly review (treasurer)" not in titles                               # jason's private key
    assert "Due: Monthly review (treasurer)" not in titles                          # a title only jason gives
    assert r.left == {"jason's own tasks": 2, "jason's own events": 2, "calendar mirrors of tasks": 1}


def test_items_are_matched_and_classified(tmp_path):
    _store(tmp_path)
    r = pt.classify(_community(), tmp_path, on=ON)
    by = {i.title: i for i in r.found}
    # a rule row to an assignment jason keeps
    assert by["Renew widget license"].kind is Kind.COVERED and by["Renew widget license"].match.ref == "widget-renewal"
    # an assignment's own title; a register item's title; the calendar policy's words
    assert by["Monthly review"].match.how == "assignment title"
    assert by["Replace the lobby bulb"].match.tracker is Tracker.BOARD_ITEM
    meeting = by["Regular Meeting of the Board of Directors"]
    assert meeting.kind is Kind.COVERED and meeting.match.ref == "board-meetings" and meeting.open
    # a calendar series no rule fits recurs; a title that comes back in different months recurs
    assert by["Pool opening"].kind is Kind.RECURRING and by["Pool opening"].series
    assert by["Trim the hedges!"].kind is Kind.RECURRING and by["Trim the hedges!"].repeats
    # the rest is a one-off; a past event is not current
    assert by["Meet the auditor"].kind is Kind.ONE_OFF and by["Meet the auditor"].open
    assert not by["Old event"].open
    counts = r.counts()
    assert counts["covered"] == 5 and counts["untracked recurring"] == 2 and counts["one-off"] == 4
    assert counts["stale"] == 4 and counts["undated"] == 2 and counts["retire"] == 1


def test_stale_tasks_are_oldest_first_and_a_retired_duty_is_proposed_closed(tmp_path):
    _store(tmp_path)
    r = pt.classify(_community(), tmp_path, on=ON)
    assert [i.title for i in r.stale()] == ["File the old report", "Renew widget license", "Trim the hedges!",
                                            "Call the plumber"]
    old = next(i for i in r.found if i.title == "File the old report")
    assert old.stale and old.retire == "the rule was withdrawn" and old.kind is Kind.ONE_OFF


def test_a_rule_naming_something_jason_does_not_keep_is_a_miss_said_so(tmp_path):
    _store(tmp_path)
    rules = (PeopleTaskRule("widget", r"widget", "the widget license", Tracker.ASSIGNMENT, "no-such-row", recurring=True),)
    r = pt.classify(_community(rules=rules), tmp_path, on=ON)
    widget = next(i for i in r.found if i.title == "Renew widget license")
    assert widget.kind is Kind.RECURRING and not widget.match.valid
    assert any(n.startswith("Rules that name something jason does not keep") and "widget" in n for n in r.notes)


def test_proposals_gather_untracked_recurring_items_and_private_drops_titles(tmp_path):
    _store(tmp_path)
    r = pt.classify(_community(), tmp_path, on=ON)
    keys = {p["key"] for p in r.proposals()}
    assert keys == {"pool opening", "trim the hedges"}
    shared = json.dumps(r.as_dict(private=True))
    assert "123 Main St" not in shared and "Paint the fence" not in shared and "My Tasks" not in shared
    assert "123 Main St" in json.dumps(r.as_dict())


def test_no_store_is_an_empty_reading_not_an_error(tmp_path):
    r = pt.classify(_community(), tmp_path, on=ON)
    assert r.found == [] and "--read-google" in r.notes[0]
    s = attention.people_section(_community(), tmp_path, ON)
    assert s.available and s.items == [] and "--read-google" in s.summary


def test_the_attention_section_lists_stale_tasks_and_proposals(tmp_path):
    _store(tmp_path)
    s = attention.people_section(_community(), tmp_path, ON, private=True)
    stale = [i for i in s.ordered() if i.urgency is Urgency.OPEN]
    assert [i.due for i in stale] == sorted(i.due for i in stale) and len(stale) == 4
    assert any("propose closing it: the rule was withdrawn" in i.text for i in stale)
    assert sum(1 for i in s.items if i.text.startswith("propose a clock")) == 2
    assert all("123 Main St" not in i.text and "plumber" not in i.text for i in s.items)
    assert s.counts["stale"] == 4 and s.command == "jason schedule --people"
    assert "people" in attention.SECTIONS


def test_the_attention_section_caps_stale_tasks(tmp_path):
    raw = _raw()
    raw["tasklists"][0]["tasks"] = [{"title": f"Chore {n}", "due": f"2025-0{1 + n % 9}-0{1 + n % 9}T00:00:00.000Z",
                                     "status": "needsAction"} for n in range(14)]
    _store(tmp_path, raw)
    s = attention.people_section(_community(rules=()), tmp_path, ON)
    open_ = [i for i in s.items if i.urgency is Urgency.OPEN]
    assert len(open_) == attention.STALE_SHOWN
    assert any(i.text.startswith("4 more stale open tasks") for i in s.items)


def test_read_google_keeps_both_parts_and_a_refused_part_as_its_error(tmp_path):
    from jason.google.errors import GoogleError

    class Calendar:
        def events(self, calendar_id, time_min, time_max):
            yield {"id": "e1", "summary": "Pool opening", "start": {"date": "2026-05-01"}, "creator": {"email": "x"}}

    class Tasks:
        def task_lists(self):
            raise GoogleError("HTTP 403 GET users/@me/lists: insufficient scope")

    out = pt.read_google(Calendar(), Tasks(), tmp_path, today=ON)
    stored = pt.load(tmp_path)
    assert stored["calendars"][0]["events"][0] == {"id": "e1", "summary": "Pool opening", "start": {"date": "2026-05-01"}}
    assert "insufficient scope" in out["tasks_error"] and stored["read"]
    assert "Google Tasks was not read" in " ".join(pt.classify(_community(), tmp_path, on=ON).notes)


# --- The new clocks -----------------------------------------------------------------------------------------------------

def test_each_insurance_policy_renewal_is_an_anchor_and_a_shared_day_is_one():
    policies = (SimpleNamespace(renewal=date(2027, 9, 28)), SimpleNamespace(renewal=date(2027, 9, 28)),
                SimpleNamespace(renewal=date(2026, 12, 3)), SimpleNamespace(renewal=None))
    community = SimpleNamespace(insurance=lambda: SimpleNamespace(policies=policies))
    start, end = date(2026, 10, 1), date(2027, 9, 30)
    assert policy_renewals(community, start, end) == [date(2026, 12, 3), date(2027, 9, 28)]
    bound = Assignment("bound", "Bound", Role.TREASURER, ("CIV 5810",), Trigger.ANCHORED,
                       anchor=Anchor.POLICY_RENEWAL, offset_days=-45)
    assert occurrences(bound, start, end, anchors_for(community, start, end)) == [date(2026, 10, 19), date(2027, 8, 14)]
    assert policy_renewals(SimpleNamespace(insurance=lambda: None), start, end) == []
    assert policy_renewals(SimpleNamespace(), start, end) == []


def test_a_biennial_cadence_falls_in_its_years_only():
    a = Assignment("si", "Statement", Role.SECRETARY, ("CIV 5405",), Trigger.CADENCE, every_months=24, month=5, day=31,
                   from_year=2027)
    assert occurrences(a, date(2026, 1, 1), date(2030, 12, 31)) == [date(2027, 5, 31), date(2029, 5, 31)]
    assert "every 2 years by May 31" in a.cadence()


def test_a_conditional_row_overdue_is_not_a_legal_clock(tmp_path):
    a = Assignment("cond", "A conditional resolution", Role.TREASURER, ("CIV 5500",), Trigger.CADENCE, every_months=12,
                   month=9, day=15, applies_if="the association files the other form")
    s = attention.schedule_section(SimpleNamespace(assignments=lambda: (a,)), tmp_path, ON)
    item = next(i for i in s.items if "conditional" in i.text)
    assert item.urgency is Urgency.OVERDUE and "only if the association files the other form" in item.text
