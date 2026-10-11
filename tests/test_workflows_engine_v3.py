"""The engine's third round (docs/workflows-engine.md, "Engine round three"): a remedy that opens while its failed check stays
failed, item sets supplied while the run goes with per-item needs, branches and clocks and a roll-up, step groups folded into one
row each, business-day clocks against a calendar the readers supply, and a wait that only a person's note ends.

Everything is made up ("A. Manager", "123 Main St", 2099). The first test pins the other half of the promise: the golden log of
round two (tests/test_workflows_engine_v2.py) folds exactly as it did. The last ones are property tests: the fold is
deterministic, replayable, and independent of what it is not given, over many seeded random event streams.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from datetime import date, timedelta

import pytest

from jason.workflows import api, definitions, fold, resume, store
from jason.workflows.types import (
    CheckResult, Choice, ClockBasis, ClockDef, DateSlot, Elapsed, Event, EventKind as K, NotApplicable, Repeat, Role, RunState, SkipRule,
    StepDef, StepGroup, StepKind, StepRefused, StepState as S, Workflow,
)
from test_workflows_engine_v2 import GOLDEN_EXPECTED, GOLDEN_LINES, compact, golden_workflow
from test_workflows_support import FakeReaders, OWNER, SECRETARY, TREASURER, VISITOR, data  # noqa: F401 - data is a fixture

TODAY = date(2099, 9, 21)                       # a Tuesday
AT = "2099-09-15T09:00:00Z"
ROLES = {OWNER: {"manager"}, SECRETARY: {"secretary", "director"}, TREASURER: {"treasurer"}, VISITOR: set()}


def roles_of(by):
    return ROLES.get(by, ())


def test_the_round_two_golden_log_folds_the_same_and_the_new_views_are_empty_for_it():
    events = [Event.from_dict(json.loads(line)) for line in GOLDEN_LINES.strip().splitlines()]
    wf = golden_workflow()
    assert compact(fold.state(events, wf, date(2099, 9, 20), {}, run_id="run-g")) == GOLDEN_EXPECTED["open"]
    assert compact(fold.state(events[:8], wf, date(2099, 9, 20), {}, run_id="run-g")) == GOLDEN_EXPECTED["prefix8"]
    view = fold.state(events, wf, date(2099, 9, 20), {}, run_id="run-g")
    assert view.groups == () and all(s.remedy == "" and s.item_counts == () for s in view.steps)
    assert all(c.item == "" for c in view.clocks) and view.item_sets == {"": ("u1", "u2")}
    # a per-item step that does not name an item set keeps its old roll-up and its old quirk (no listing for a lone item)
    assert view.step("g.11").reason == "1 of 2 items done" and view.step("g.11").items[0] == ("u1", S.DONE)


def new_run(data, key, wf_dates=None, *, subject="campaign:V3-2099", items=(), open_=True, readers=None):
    rid = api.start(data, key, subject, "V3", wf_dates or {}, OWNER, items=items, yes=True, today=TODAY, at=AT)["run"]["id"]
    if open_:
        api.open_run(data, rid, OWNER, readers=readers or FakeReaders(), yes=True, today=TODAY, at="2099-09-15T09:01:00Z")
    return rid


def view_of(data, rid, key, day=TODAY, children=None, **kw):
    run = store.open_run(data, rid)
    return fold.state(list(run.events), definitions.get(key), day, children or {}, run_id=rid, **kw)


@pytest.fixture(autouse=True)
def _clean_registry():
    definitions.reset()
    yield
    definitions.reset()


# --- (1) a remedy -----------------------------------------------------------------------------------------------------------------

REMEDY = "remedy-flow"


def remedy_flow(**over) -> Workflow:
    s = StepDef
    steps = (
        s("r.1", "The roster is complete", StepKind.CHECK, role=Role.JASON, check=lambda view: CheckResult(True, (), "")),
        s("r.2", "Complete the roster", StepKind.PERSON, role=Role.MANAGER, needs=("r.1",), remedy_of="r.1", record="the roster"),
        s("r.3", "Mail the notice", StepKind.PERSON, role=Role.MANAGER, needs=("r.1",)),
        s("r.4", "File the completed roster", StepKind.PERSON, role=Role.MANAGER, needs=("r.2",)),
    )
    base = dict(key=REMEDY, title="Remedy flow", family="example", subject="campaign", steps=steps)
    base.update(over)
    return Workflow(**base)


def test_a_failed_check_blocks_its_dependents_but_not_the_step_that_remedies_it(data):
    definitions.register(remedy_flow())
    readers = FakeReaders()
    readers.checks["r.1"] = CheckResult(False, (), "two owners have no mailing address")
    rid = new_run(data, REMEDY, readers=readers)
    v = view_of(data, rid, REMEDY)
    assert v.state_of("r.1") is S.FAILED and v.step("r.1").reason == "two owners have no mailing address"      # recorded as failed
    assert v.state_of("r.2") is S.NEEDS_PERSON                                  # the remedy is open
    assert v.state_of("r.3") is S.BLOCKED and v.step("r.3").blocked_by == ("r.1",)       # the other dependent is held back
    assert v.state_of("r.4") is S.NOT_STARTED                                   # waits for the remedy
    assert v.step("r.1").remedy == "r.2" and v.step("r.2").remedy == ""
    assert v.current == "r.2" and v.state is RunState.ACTIVE                    # the person is pointed at the remedy, the run is not failed
    # a repeat of the check changes nothing and appends nothing
    assert resume.pending(v, list(store.open_run(data, rid).events), definitions.get(REMEDY), readers) == []


def test_the_remedy_is_done_the_check_still_failed_then_the_check_passes_on_the_next_open(data):
    definitions.register(remedy_flow())
    readers = FakeReaders()
    readers.checks["r.1"] = CheckResult(False, (), "two owners have no mailing address")
    rid = new_run(data, REMEDY, readers=readers)
    api.attest(data, rid, "r.2", OWNER, roles_of=roles_of, record="roster:2099-09", today=TODAY)
    v = view_of(data, rid, REMEDY)
    assert v.state_of("r.2") is S.DONE and v.state_of("r.4") is S.NEEDS_PERSON         # the next step opened through the remedy
    assert v.state_of("r.1") is S.FAILED and v.step("r.1").remedy == ""                  # nobody has resolved the check yet...
    assert v.state is RunState.FAILED and v.current == "r.1"                             # ...so the run says so
    assert v.state_of("r.3") is S.BLOCKED
    # once the check passes (a resume re-reads it), the held-back step opens
    readers.checks["r.1"] = CheckResult(True, (), "")
    again = api.open_run(data, rid, OWNER, readers=readers, yes=True, today=TODAY)
    assert [e["kind"] for e in again["appended"]] == ["check-ran"]
    v = view_of(data, rid, REMEDY)
    assert v.state_of("r.1") is S.DONE and v.state_of("r.3") is S.NEEDS_PERSON and v.state is RunState.ACTIVE
    assert [e.kind for e in store.open_run(data, rid).events].count(K.CHECK_RAN) == 2    # the failure stays in the log


def test_without_the_flag_the_same_failure_blocks_the_next_step(data):
    definitions.register(remedy_flow(steps=tuple(replace(s, remedy_of="") for s in remedy_flow().steps)))
    readers = FakeReaders()
    readers.checks["r.1"] = CheckResult(False, (), "two owners have no mailing address")
    rid = new_run(data, REMEDY, readers=readers)
    v = view_of(data, rid, REMEDY)
    assert v.state_of("r.2") is S.BLOCKED and v.state is RunState.FAILED and v.current == "r.1" and v.step("r.1").remedy == ""


def test_a_remedy_that_is_itself_blocked_by_another_need_stays_blocked(data):
    s = StepDef
    wf = Workflow("rb", "Remedy blocked", "example", "unit", steps=(
        s("b.1", "Facts", StepKind.CHECK, role=Role.JASON, check=lambda v: CheckResult(False, (), "no")),
        s("b.2", "Other check", StepKind.CHECK, role=Role.JASON, check=lambda v: CheckResult(False, (), "no")),
        s("b.3", "Fix", StepKind.PERSON, role=Role.MANAGER, needs=("b.1", "b.2"), remedy_of="b.1")))
    definitions.register(wf)
    rid = new_run(data, "rb")
    v = view_of(data, rid, "rb")
    assert v.state_of("b.3") is S.BLOCKED and v.step("b.3").blocked_by == ("b.2",)     # only the named check is excused


def test_validate_refuses_a_remedy_that_is_not_a_check_it_needs():
    ok = remedy_flow()
    assert definitions.validate(ok) == []

    def codes(**kw):
        wf = replace(ok, steps=tuple(replace(s, **kw) if s.id == "r.4" else s for s in ok.steps))
        return [p.message for p in definitions.validate(wf)]

    assert any("not a step" in m for m in codes(remedy_of="r.9"))
    assert any("needs the check" in m for m in codes(remedy_of="r.1"))                       # r.4 needs r.2, not r.1
    assert any("only a check" in m for m in codes(remedy_of="r.2"))


# --- (2) item sets ----------------------------------------------------------------------------------------------------------------

ITEMS = "item-flow"


class ItemReaders(FakeReaders):
    def __init__(self):
        super().__init__()
        self.by_item: dict[tuple[str, str], CheckResult] = {}
        self.asked: list[tuple[str, str]] = []

    def check(self, step, view, item=""):
        self.asked.append((step.id, item))
        return self.by_item.get((step.id, item)) or super().check(step, view, item)


def item_flow(**over) -> Workflow:
    s = StepDef
    steps = (
        s("i.1", "Read each request", StepKind.CHECK, role=Role.JASON, repeat=Repeat.PER_ITEM, item_set="requests",
          check=lambda view: None),
        s("i.2", "Decide each request", StepKind.PERSON, role=Role.MANAGER, needs=("i.1",), repeat=Repeat.PER_ITEM, item_set="requests",
          item_needs=("i.1",), record="the decision", clock=ClockDef(ClockBasis.PERSON, "due_on", 3, label="reply", per_item=True)),
        s("i.3", "Which way", StepKind.BRANCH, role=Role.MANAGER, needs=("i.2",), repeat=Repeat.PER_ITEM, item_set="requests",
          item_needs=("i.2",), choices=(Choice("grant", ("i.4",)), Choice("deny", ("i.5",)))),
        s("i.4", "Send the grant", StepKind.PERSON, role=Role.MANAGER, needs=("i.3",), repeat=Repeat.PER_ITEM, item_set="requests",
          item_needs=("i.3",)),
        s("i.5", "Send the denial", StepKind.PERSON, role=Role.MANAGER, needs=("i.3",), repeat=Repeat.PER_ITEM, item_set="requests",
          item_needs=("i.3",)),
        s("i.6", "Close the month", StepKind.PERSON, role=Role.MANAGER, needs=("i.4", "i.5")),
    )
    base = dict(key=ITEMS, title="Item flow", family="example", subject="period", steps=steps,
                dates=(DateSlot("due_on", "Reply by", required=False),))
    base.update(over)
    return Workflow(**base)


def test_the_item_flow_is_a_valid_definition():
    assert definitions.validate(item_flow()) == []


def test_a_step_over_an_empty_set_waits_for_items_and_refuses_an_item_it_does_not_have(data):
    definitions.register(item_flow())
    rid = new_run(data, ITEMS)
    v = view_of(data, rid, ITEMS)
    assert v.item_sets == {"": ()} and v.state_of("i.1") is S.WAITING
    assert v.step("i.1").reason == "no items in the set requests yet"
    assert v.state_of("i.2") is S.NOT_STARTED and v.state_of("i.6") is S.NOT_STARTED
    with pytest.raises(StepRefused, match="has no items yet"):
        api.attest(data, rid, "i.2", OWNER, roles_of=roles_of, item="r1", record="x", today=TODAY)


def test_items_are_supplied_by_a_person_with_a_role_as_opaque_ids_and_land_in_the_set_in_order(data):
    definitions.register(item_flow())
    rid = new_run(data, ITEMS)
    with pytest.raises(StepRefused, match="holds no role"):
        api.supply_items(data, rid, "requests", ["r1"], VISITOR, roles_of=roles_of, today=TODAY)
    with pytest.raises(StepRefused, match="engine's own name"):
        api.supply_items(data, rid, "requests", ["r1"], "jason", today=TODAY)
    with pytest.raises(StepRefused, match="no step of item-flow repeats over the set nope"):
        api.supply_items(data, rid, "nope", ["r1"], OWNER, roles_of=roles_of, today=TODAY)
    for bad in ("a.owner@example.com", "123 Main St", "", "x" * 65):
        with pytest.raises(StepRefused, match="is not an item id"):
            api.supply_items(data, rid, "requests", [bad], OWNER, roles_of=roles_of, today=TODAY)
    with pytest.raises(StepRefused, match="no items to supply"):
        api.supply_items(data, rid, "requests", [], OWNER, roles_of=roles_of, today=TODAY)
    n = store.open_run(data, rid).n
    out = api.supply_items(data, rid, "requests", ["req:1", "req:2", "req:1"], OWNER, roles_of=roles_of, today=TODAY,
                           at="2099-09-16T10:00:00Z")
    assert out["event"]["kind"] == "note" and "step" not in out["event"] and out["event"]["n"] == n + 1
    assert out["event"]["detail"]["items_supplied"] == {"set": "requests", "items": ["req:1", "req:2"]}
    assert out["event"]["detail"]["text"] == "supplied 2 items to the set requests"
    assert out["run"]["itemSets"] == {"requests": ["req:1", "req:2"]} and out["run"]["items"] == []
    with pytest.raises(StepRefused, match="already in the set"):
        api.supply_items(data, rid, "requests", ["req:2"], OWNER, roles_of=roles_of, today=TODAY)
    api.supply_items(data, rid, "requests", ["req:2", "req:3"], OWNER, roles_of=roles_of, today=TODAY)
    v = view_of(data, rid, ITEMS)
    assert v.item_sets["requests"] == ("req:1", "req:2", "req:3")
    assert [i for i, _ in v.step("i.2").items] == ["req:1", "req:2", "req:3"]


def test_an_item_waits_only_for_its_own_item_of_the_step_before(data):
    definitions.register(item_flow())
    readers = ItemReaders()
    rid = new_run(data, ITEMS, readers=readers)
    api.supply_items(data, rid, "requests", ["a", "b"], OWNER, roles_of=roles_of, today=TODAY)
    # the per-item check runs for each item on the next open; item b's read fails
    readers.by_item[("i.1", "a")] = CheckResult(True, (), "read")
    readers.by_item[("i.1", "b")] = CheckResult(False, (), "unreadable")
    out = api.open_run(data, rid, OWNER, readers=readers, yes=True, today=TODAY)
    assert sorted((e["step"], e["detail"]["item"], e["detail"]["ok"]) for e in out["appended"]) == [
        ("i.1", "a", True), ("i.1", "b", False)]
    v = view_of(data, rid, ITEMS)
    assert dict(v.step("i.1").items) == {"a": S.DONE, "b": S.FAILED}
    assert dict(v.step("i.2").items) == {"a": S.NEEDS_PERSON, "b": S.BLOCKED}        # a goes on; b is held by its own failed read
    assert v.step("i.2").blocked_by == ()                                            # the roll-up is not blocked: a needs a person
    assert v.state_of("i.2") is S.NEEDS_PERSON
    # an item is acted on by name, and only when its own predecessor is done
    with pytest.raises(StepRefused, match="blocked, not needs a person"):
        api.attest(data, rid, "i.2", OWNER, roles_of=roles_of, item="b", record="x", today=TODAY)
    api.attest(data, rid, "i.2", OWNER, roles_of=roles_of, item="a", record="x", today=TODAY)
    v = view_of(data, rid, ITEMS)
    assert dict(v.step("i.2").items) == {"a": S.DONE, "b": S.BLOCKED}
    assert v.state_of("i.2") is S.BLOCKED                                             # nothing left for a person: held by b
    assert v.step("i.2").item_counts == ((S.DONE, 1), (S.BLOCKED, 1))
    assert v.step("i.2").reason.startswith("1 of 2 items done; blocked by i.1")


def test_a_per_item_branch_skips_the_other_path_for_that_item_alone(data):
    definitions.register(item_flow())
    readers = ItemReaders()
    rid = new_run(data, ITEMS, readers=readers)
    api.supply_items(data, rid, "requests", ["a", "b"], OWNER, roles_of=roles_of, today=TODAY)
    for item in ("a", "b"):
        readers.by_item[("i.1", item)] = CheckResult(True, (), "read")
    api.open_run(data, rid, OWNER, readers=readers, yes=True, today=TODAY)
    for item in ("a", "b"):
        api.attest(data, rid, "i.2", OWNER, roles_of=roles_of, item=item, record=f"decision:{item}", today=TODAY)
    api.attest(data, rid, "i.3", OWNER, roles_of=roles_of, item="a", choice="grant", today=TODAY)
    v = view_of(data, rid, ITEMS)
    assert dict(v.step("i.3").items) == {"a": S.DONE, "b": S.NEEDS_PERSON}
    assert dict(v.step("i.4").items) == {"a": S.NEEDS_PERSON, "b": S.NOT_STARTED}     # a's grant is open; b has not chosen
    assert dict(v.step("i.5").items) == {"a": S.SKIPPED, "b": S.NOT_STARTED}          # the denial is skipped for a alone
    assert "not on the path grant chosen at i.3 for item a" in v.step("i.5").reason or v.step("i.5").reason.startswith("1 of 2")
    api.attest(data, rid, "i.3", OWNER, roles_of=roles_of, item="b", choice="deny", today=TODAY)
    v = view_of(data, rid, ITEMS)
    assert dict(v.step("i.4").items) == {"a": S.NEEDS_PERSON, "b": S.SKIPPED}
    assert dict(v.step("i.5").items) == {"a": S.SKIPPED, "b": S.NEEDS_PERSON}
    api.attest(data, rid, "i.4", OWNER, roles_of=roles_of, item="a", today=TODAY)
    assert view_of(data, rid, ITEMS).state_of("i.4") is S.DONE                         # all items finished (one done, one skipped)
    assert view_of(data, rid, ITEMS).state_of("i.6") is S.NOT_STARTED                  # i.5 is not finished
    api.attest(data, rid, "i.5", OWNER, roles_of=roles_of, item="b", today=TODAY)
    v = view_of(data, rid, ITEMS)
    assert v.state_of("i.5") is S.DONE and v.state_of("i.6") is S.NEEDS_PERSON         # the plain step after them needs both whole


def test_each_item_has_a_clock_from_its_own_dates_before_the_runs(data):
    definitions.register(item_flow())
    rid = new_run(data, ITEMS, {"due_on": "2099-10-01"})
    with pytest.raises(StepRefused, match="need the record"):
        api.supply_items(data, rid, "requests", [{"id": "a", "dates": {"due_on": "2099-09-30"}}], OWNER, roles_of=roles_of, today=TODAY)
    with pytest.raises(StepRefused, match="no date slot sent_on"):
        api.supply_items(data, rid, "requests", [{"id": "a", "dates": {"sent_on": "2099-09-30"}}], OWNER, roles_of=roles_of,
                         record="mail:1", today=TODAY)
    with pytest.raises(StepRefused, match="not YYYY-MM-DD"):
        api.supply_items(data, rid, "requests", [{"id": "a", "dates": {"due_on": "30/09/2099"}}], OWNER, roles_of=roles_of,
                         record="mail:1", today=TODAY)
    out = api.supply_items(data, rid, "requests", ["a", {"id": "b", "dates": {"due_on": "2099-09-30"}}], OWNER, roles_of=roles_of,
                           record="mail:1", today=TODAY)
    clocks = {c["key"]: c for c in out["run"]["clocks"]}
    assert sorted(clocks) == ["i.2[a]", "i.2[b]"] and clocks["i.2[a]"]["item"] == "a" and clocks["i.2[a]"]["step"] == "i.2"
    assert clocks["i.2[a]"]["due"] == "2099-10-04"                                   # the run's date, three days on
    assert clocks["i.2[b]"]["due"] == "2099-10-03"                                   # b's own date, three days on
    # a later supply corrects an item's date (the latest wins), and the earlier event stays
    api.supply_items(data, rid, "requests", [{"id": "b", "dates": {"due_on": "2099-10-10"}}], OWNER, roles_of=roles_of, record="mail:2",
                     today=TODAY)
    v = view_of(data, rid, ITEMS)
    assert {c.key: c.due for c in v.clocks}["i.2[b]"] == "2099-10-13"
    assert sum(1 for e in store.open_run(data, rid).events if e.detail.get("items_supplied")) == 2
    # one item done: its clock is satisfied and the other's is not
    readers = ItemReaders()
    readers.by_item[("i.1", "a")] = CheckResult(True, (), "read")
    api.open_run(data, rid, OWNER, readers=readers, yes=True, today=TODAY)
    api.attest(data, rid, "i.2", OWNER, roles_of=roles_of, item="a", record="decision:a", today=TODAY)
    status = {c.key: c.status for c in view_of(data, rid, ITEMS, date(2099, 10, 5)).clocks}
    assert status == {"i.2[a]": "satisfied", "i.2[b]": "upcoming"}
    assert {c.key: c.status for c in view_of(data, rid, ITEMS, date(2099, 10, 20)).clocks}["i.2[b]"] == "overdue"


def test_a_step_clock_that_is_not_per_item_stays_one_clock(data):
    wf = item_flow(steps=tuple(replace(s, clock=ClockDef(ClockBasis.PERSON, "due_on", 3, label="reply")) if s.id == "i.2" else s
                               for s in item_flow().steps))
    definitions.register(wf)
    rid = new_run(data, ITEMS, {"due_on": "2099-10-01"})
    api.supply_items(data, rid, "requests", ["a", "b"], OWNER, roles_of=roles_of, today=TODAY)
    assert [c.key for c in view_of(data, rid, ITEMS).clocks] == ["i.2"]


def test_the_roll_up_is_the_most_pressing_state_and_a_failed_item_outranks_a_person(data):
    assert fold.rollup([S.DONE, S.DONE]) is S.DONE and fold.rollup([S.DONE, S.SKIPPED]) is S.DONE
    assert fold.rollup([S.SKIPPED, S.SKIPPED]) is S.SKIPPED and fold.rollup([]) is S.NOT_STARTED
    assert fold.rollup([S.DONE, S.WAITING, S.NEEDS_PERSON]) is S.NEEDS_PERSON
    assert fold.rollup([S.WAITING, S.FAILED, S.NEEDS_PERSON, S.DONE]) is S.FAILED
    assert fold.rollup([S.NOT_STARTED, S.BLOCKED]) is S.BLOCKED
    assert fold.rollup([S.READY, S.RUNNING, S.WAITING]) is S.READY


def test_the_old_run_items_work_as_before_and_can_be_added_to(data):
    s = StepDef
    wf = Workflow("old-items", "Old items", "example", "unit", steps=(
        s("o.1", "Letter for each", StepKind.PERSON, role=Role.MANAGER, repeat=Repeat.PER_ITEM),))
    definitions.register(wf)
    rid = new_run(data, "old-items", items=["u1", "u2"])
    api.attest(data, rid, "o.1", OWNER, roles_of=roles_of, item="u1", today=TODAY)
    out = api.supply_items(data, rid, "", ["u3"], OWNER, roles_of=roles_of, today=TODAY)
    assert out["run"]["items"] == ["u1", "u2", "u3"] and out["run"].get("itemSets") is None
    v = view_of(data, rid, "old-items")
    assert dict(v.step("o.1").items) == {"u1": S.DONE, "u2": S.NEEDS_PERSON, "u3": S.NEEDS_PERSON}
    assert v.step("o.1").item_counts == ()                       # a step that names no set keeps its old roll-up


def test_validate_refuses_item_rules_that_cannot_hold():
    ok = item_flow()

    def messages(step_id, **kw):
        wf = replace(ok, steps=tuple(replace(s, **kw) if s.id == step_id else s for s in ok.steps))
        return [p.message for p in definitions.validate(wf)]

    assert any("repeats per item" in m for m in messages("i.6", item_set="requests"))
    assert any("lower-case word" in m for m in messages("i.2", item_set="Requests"))
    assert any("which the step does not need" in m for m in messages("i.2", item_needs=("i.1", "i.5")))
    assert any("does not repeat over the same items" in m for m in messages("i.2", item_set="other"))
    assert any("does not repeat over the same items" in m for m in messages("i.4", item_needs=("i.3", "i.6"), needs=("i.3", "i.6")))
    path = replace(ok.step("i.4"), item_set="other", item_needs=())
    assert any("per-item path" in p.message for p in definitions.validate(
        replace(ok, steps=tuple(path if s.id == "i.4" else s for s in ok.steps))))
    assert any("per-item clock" in m for m in messages("i.6", clock=ClockDef(ClockBasis.PERSON, "due_on", 1, per_item=True)))
    assert any("whole run is not per item" in p.message for p in definitions.validate(
        replace(ok, clocks=(ClockDef(ClockBasis.PERSON, "due_on", 1, per_item=True),))))


# --- (3) step groups --------------------------------------------------------------------------------------------------------------

GROUPS = "group-flow"


def group_flow(**over) -> Workflow:
    s = StepDef
    steps = (
        s("g.1", "Collect", StepKind.PERSON, role=Role.MANAGER, group="intake"),
        s("g.2", "Sort", StepKind.PERSON, role=Role.MANAGER, needs=("g.1",), group="intake", skip=SkipRule()),
        s("g.3", "Decide", StepKind.PERSON, role=Role.MANAGER, needs=("g.2",), group="board"),
        s("g.4", "Announce", StepKind.PERSON, role=Role.MANAGER, needs=("g.3",), group="board"),
        s("g.5", "Close", StepKind.PERSON, role=Role.MANAGER, needs=("g.4",)),
    )
    base = dict(key=GROUPS, title="Group flow", family="example", subject="period", steps=steps,
                groups=(StepGroup("intake", "Intake"),))
    base.update(over)
    return Workflow(**base)


def test_a_group_is_one_row_that_expands_with_the_current_step_and_collapses_when_done_or_not_reached(data):
    wf = group_flow(groups=(StepGroup("intake", "Intake"), StepGroup("board", "The board")))
    assert definitions.validate(wf) == []
    definitions.register(wf)
    rid = new_run(data, GROUPS)

    def groups():
        return {g.key: g for g in view_of(data, rid, GROUPS).groups}

    g = groups()
    assert list(g) == ["intake", "board"]
    assert (g["intake"].title, g["intake"].steps, g["intake"].state, g["intake"].done, g["intake"].total, g["intake"].expanded,
            g["intake"].current) == ("Intake", ("g.1", "g.2"), S.NEEDS_PERSON, 0, 2, True, "g.1")
    assert (g["board"].state, g["board"].expanded, g["board"].current) == (S.NOT_STARTED, False, "")        # not yet reached
    api.attest(data, rid, "g.1", OWNER, roles_of=roles_of, today=TODAY)
    api.skip(data, rid, "g.2", OWNER, roles_of=roles_of, reason="nothing to sort", today=TODAY)
    g = groups()
    assert (g["intake"].state, g["intake"].done, g["intake"].expanded) == (S.DONE, 2, False)                    # collapsed: done
    assert (g["board"].state, g["board"].expanded, g["board"].current) == (S.NEEDS_PERSON, True, "g.3")          # expanded: current
    api.attest(data, rid, "g.3", OWNER, roles_of=roles_of, today=TODAY)
    api.attest(data, rid, "g.4", OWNER, roles_of=roles_of, today=TODAY)
    api.attest(data, rid, "g.5", OWNER, roles_of=roles_of, today=TODAY)
    assert all(not x.expanded and x.state is S.DONE for x in groups().values())                                  # a finished run folds all
    # the steps themselves are what they were, and the readers carry the groups
    shown = api.show(data, rid, today=TODAY)
    assert [x["key"] for x in shown["groups"]] == ["intake", "board"] and shown["groups"][1]["title"] == "The board"
    assert shown["groups"][0]["steps"] == ["g.1", "g.2"] and shown["groups"][0]["done"] == 2


def test_a_group_with_a_failed_step_stays_expanded_and_an_undeclared_group_is_titled_by_its_key(data):
    s = StepDef
    wf = Workflow("gf", "Group fail", "example", "unit", steps=(
        s("f.1", "Read", StepKind.CHECK, role=Role.JASON, group="IN", check=lambda v: CheckResult(False, (), "no")),
        s("f.2", "Then", StepKind.PERSON, role=Role.MANAGER, needs=("f.1",), group="IN"),
        s("f.3", "Later", StepKind.PERSON, role=Role.MANAGER, needs=("f.2",))))
    definitions.register(wf)
    rid = new_run(data, "gf")
    (g,) = view_of(data, rid, "gf").groups
    assert (g.key, g.title, g.state, g.expanded, g.done, g.total) == ("IN", "IN", S.FAILED, True, 0, 2)


def test_a_workflow_with_no_groups_has_none_and_the_dict_does_not_grow(data):
    definitions.register(item_flow())
    rid = new_run(data, ITEMS)
    assert view_of(data, rid, ITEMS).groups == ()
    shown = api.show(data, rid, today=TODAY)
    assert "groups" not in shown and "itemSets" not in shown
    assert all("remedy" not in s and "itemCounts" not in s for s in shown["steps"])
    assert all("item" not in c for c in shown["clocks"])


def test_validate_refuses_a_group_declared_twice_or_a_step_in_an_undeclared_one():
    twice = group_flow(groups=(StepGroup("intake"), StepGroup("intake")))
    assert any("repeats" in p.message for p in definitions.validate(twice))
    assert any("not among the definition's step groups" in p.message for p in definitions.validate(group_flow()))   # g.3 is in "board"
    assert definitions.validate(group_flow(groups=())) == []                                                         # none declared: free


# --- (4) business days ------------------------------------------------------------------------------------------------------------

def test_a_business_day_count_skips_weekends_and_the_holidays_it_is_given():
    fri, mon = date(2099, 9, 18), date(2099, 9, 21)               # Friday, Monday
    assert fold.add_business_days(fri, 1) == mon and fold.add_business_days(fri, 3) == date(2099, 9, 23)
    assert fold.add_business_days(fri, 0) == fri and fold.add_business_days(date(2099, 9, 19), 0) == date(2099, 9, 19)   # 0: itself
    assert fold.add_business_days(date(2099, 9, 19), 1) == mon                                     # from a Saturday the Monday is first
    assert fold.add_business_days(fri, 1, {mon}) == date(2099, 9, 22)                              # Monday a holiday
    assert fold.add_business_days(fri, 2, [mon, date(2099, 9, 22)]) == date(2099, 9, 24)
    assert fold.add_business_days(mon, -1) == fri and fold.add_business_days(mon, -1, {fri}) == date(2099, 9, 17)
    assert fold.add_business_days(date(2099, 12, 30), 5, {date(2099, 12, 31), date(2100, 1, 1)}) == date(2100, 1, 8)
    assert fold.holiday_days(["2099-09-21", date(2099, 9, 22), "not a day", None]) == {mon, date(2099, 9, 22)}


BIZ = "biz-flow"


def biz_flow() -> Workflow:
    return Workflow(BIZ, "Business days", "example", "unit", dates=(DateSlot("received_on", "Received"),), steps=(
        StepDef("b.1", "Reply", StepKind.PERSON, role=Role.MANAGER,
                clock=ClockDef(ClockBasis.LAW, "received_on", 10, cite="EX 5.1", label="reply", business_days=True)),
        StepDef("b.2", "Calendar days, as before", StepKind.PERSON, role=Role.MANAGER,
                clock=ClockDef(ClockBasis.PERSON, "received_on", 10, label="calendar"))))


class Holidays(FakeReaders):
    def __init__(self, days):
        super().__init__()
        self.days = days

    def holidays(self):
        return frozenset(self.days)


def test_a_business_day_clock_is_counted_against_the_calendar_the_readers_supply(data):
    definitions.register(biz_flow())
    rid = new_run(data, BIZ, {"received_on": "2099-09-14"})      # a Monday
    plain = api.show(data, rid, today=TODAY)
    due = {c["key"]: c["due"] for c in plain["clocks"]}
    assert due == {"b.1": "2099-09-28", "b.2": "2099-09-24"}      # ten weekdays on from Monday the 14th is Monday the 28th
    holiday = api.show(data, rid, today=TODAY, readers=Holidays({date(2099, 9, 21)}))
    assert {c["key"]: c["due"] for c in holiday["clocks"]} == {"b.1": "2099-09-29", "b.2": "2099-09-24"}
    assert fold.state(list(store.open_run(data, rid).events), biz_flow(), TODAY, {}, holidays=["2099-09-21"]).clocks[0].due == "2099-09-29"
    # the legal clock is read the same way for the past-law list
    late = api.show(data, rid, today=date(2099, 9, 29), readers=Holidays({date(2099, 9, 21)}))
    assert late["pastLaw"] == [] and api.show(data, rid, today=date(2099, 9, 29))["pastLaw"] == ["b.1"]


def test_readers_default_to_no_holidays_and_a_calendar_that_cannot_be_read_is_none():
    assert resume.Readers().holidays() == frozenset()
    assert resume.children_of([], resume.Readers()).holidays == frozenset()

    class Broken(resume.Readers):
        def holidays(self):
            raise OSError("no calendar")

    assert resume.holidays_of(Broken()) == frozenset()
    assert resume.children_of([], Holidays({date(2099, 9, 21)})).holidays == {date(2099, 9, 21)}
    assert resume.children_of([], object()).holidays == frozenset()           # an object with no such method is a miss


def test_the_store_readers_take_their_holidays_from_the_community(tmp_path):
    from jason.workflows.readers import StoreReaders

    class Named:
        def holidays(self):
            return ("2099-09-21", "not a day")

    assert StoreReaders(tmp_path, community=Named()).holidays() == {date(2099, 9, 21)}
    assert StoreReaders(tmp_path, community=object()).holidays() == frozenset()      # no such fact: weekends only
    from jason.community.base import Community

    assert Community.holidays(None) == ()                       # the base names none


# --- (5) a wait only a note ends --------------------------------------------------------------------------------------------------

NOTE = "note-flow"


def note_flow(**over) -> Workflow:
    s = StepDef
    steps = (
        s("n.1", "Wait for the vendor's reply", StepKind.WAIT, role=Role.MANAGER, ends_by_note=True,
          clock=ClockDef(ClockBasis.COUNTERPARTY, "reply_by", 0, label="reply")),
        s("n.2", "File the reply", StepKind.PERSON, role=Role.MANAGER, needs=("n.1",)),
        s("n.3", "An ordinary wait", StepKind.WAIT, role=Role.MANAGER),
    )
    base = dict(key=NOTE, title="Note flow", family="example", subject="unit", steps=steps,
                dates=(DateSlot("reply_by", "Reply by", required=False),))
    base.update(over)
    return Workflow(**base)


def test_a_wait_that_ends_by_note_is_not_ended_by_a_reader_or_a_date_or_the_engine(data):
    definitions.register(note_flow())
    readers = FakeReaders()
    readers.arrivals["n.1"] = "the vendor's reply"
    readers.arrivals["n.3"] = "an arrival"
    rid = new_run(data, NOTE, {"reply_by": "2099-09-10"}, readers=readers)
    v = view_of(data, rid, NOTE)
    assert v.state_of("n.1") is S.WAITING and v.state_of("n.3") is S.DONE                  # the ordinary wait's reader ended it
    assert v.step("n.1").reason.startswith("for the manager to record a note that it arrived (due 2099-09-10)")
    assert v.state_of("n.2") is S.NOT_STARTED
    assert [(e.step, e.kind) for e in store.open_run(data, rid).events if e.kind is K.ARRIVED] == [("n.3", K.ARRIVED)]
    # a date in the past does not end it either (the wait stays overdue), and a system arrival written by hand is ignored
    store.append(data, NOTE, rid, K.ARRIVED, by="jason", step="n.1", detail={"what": "the reader"})
    assert view_of(data, rid, NOTE, date(2100, 1, 1)).state_of("n.1") is S.WAITING
    assert resume.pending(view_of(data, rid, NOTE), list(store.open_run(data, rid).events), definitions.get(NOTE), readers) == []


def test_only_a_person_who_says_what_arrived_ends_it(data):
    definitions.register(note_flow())
    rid = new_run(data, NOTE)
    with pytest.raises(StepRefused, match="say what"):
        api.arrived(data, rid, "n.1", OWNER, roles_of=roles_of, today=TODAY)
    with pytest.raises(StepRefused, match="say what"):
        api.arrived(data, rid, "n.1", OWNER, roles_of=roles_of, what="   ", today=TODAY)
    with pytest.raises(StepRefused, match="does not hold"):
        api.arrived(data, rid, "n.1", VISITOR, roles_of=roles_of, what="a letter", today=TODAY)
    out = api.arrived(data, rid, "n.1", OWNER, roles_of=roles_of, what="the vendor's letter of 2099-09-18, filed as mail:41", today=TODAY)
    assert out["event"]["detail"] == {"what": "the vendor's letter of 2099-09-18, filed as mail:41"}
    v = view_of(data, rid, NOTE)
    assert v.state_of("n.1") is S.DONE and v.step("n.1").by == OWNER and v.state_of("n.2") is S.NEEDS_PERSON
    # an ordinary wait keeps its old act: no words needed
    assert api.arrived(data, rid, "n.3", OWNER, roles_of=roles_of, today=TODAY)["event"]["detail"] == {"what": "An ordinary wait"}


def test_validate_refuses_a_note_wait_that_names_a_check_or_a_date_or_is_not_a_wait():
    ok = note_flow()
    assert definitions.validate(ok) == []

    def messages(**kw):
        return [p.message for p in definitions.validate(replace(ok, steps=(replace(ok.steps[0], **kw), *ok.steps[1:])))]

    assert any("names no check" in m for m in messages(check=lambda v: None))
    assert any("not ended by a date" in m for m in messages(elapsed=Elapsed.ENDS))
    assert any("is for a wait step" in m for m in messages(kind=StepKind.PERSON))


# --- the dry resume, and a second open -------------------------------------------------------------------------------------------

def test_a_dry_resume_reads_the_new_features_and_appends_nothing_and_a_second_open_is_a_no_op(data):
    s = StepDef
    wf = Workflow("mix", "Mix", "example", "unit", steps=(
        s("m.1", "Facts", StepKind.CHECK, role=Role.JASON, check=lambda v: None),
        s("m.2", "Fix the facts", StepKind.PERSON, role=Role.MANAGER, needs=("m.1",), remedy_of="m.1"),
        s("m.3", "Read each", StepKind.CHECK, role=Role.JASON, repeat=Repeat.PER_ITEM, item_set="things", check=lambda v: None),
        s("m.4", "Vendor reply", StepKind.WAIT, role=Role.MANAGER, ends_by_note=True)))
    definitions.register(wf)
    readers = ItemReaders()
    readers.checks["m.1"] = CheckResult(False, (), "short")
    rid = new_run(data, "mix", readers=readers)
    api.supply_items(data, rid, "things", ["t1", "t2"], OWNER, roles_of=roles_of, today=TODAY)
    readers.by_item[("m.3", "t1")] = CheckResult(True, (), "")
    readers.by_item[("m.3", "t2")] = CheckResult(True, (), "")
    run = store.open_run(data, rid)
    n = run.n
    def dry():
        run_ = store.open_run(data, rid)
        view_ = fold.state(list(run_.events), wf, TODAY, resume.children_of(list(run_.events), readers), run_id=rid)
        return resume.pending(view_, list(run_.events), wf, readers)

    would = dry()                                                         # the dry resume: it reads, and writes nothing
    assert store.open_run(data, rid).n == n
    assert sorted((a.step, a.detail.get("item", "")) for a in would) == [("m.3", "t1"), ("m.3", "t2")]
    first = api.open_run(data, rid, OWNER, readers=readers, yes=True, today=TODAY)
    assert len(first["appended"]) == 2
    second = api.open_run(data, rid, OWNER, readers=readers, yes=True, today=TODAY)
    assert second["appended"] == [] and dry() == []


# --- property tests: the fold is deterministic and replayable --------------------------------------------------------------------

def rich_flow() -> Workflow:
    s = StepDef
    steps = (
        s("p.1", "Read each", StepKind.CHECK, role=Role.JASON, repeat=Repeat.PER_ITEM, item_set="things", check=lambda v: None,
          group="intake"),
        s("p.2", "Decide each", StepKind.PERSON, role=Role.MANAGER, needs=("p.1",), repeat=Repeat.PER_ITEM, item_set="things",
          item_needs=("p.1",), group="intake", skip=SkipRule(), na=NotApplicable(),
          clock=ClockDef(ClockBasis.PERSON, "due_on", 2, per_item=True, business_days=True)),
        s("p.3", "Which way", StepKind.BRANCH, role=Role.MANAGER, needs=("p.2",), repeat=Repeat.PER_ITEM, item_set="things",
          item_needs=("p.2",), group="intake", choices=(Choice("a", ("p.4",)), Choice("b", ("p.5",)))),
        s("p.4", "Path a", StepKind.PERSON, role=Role.MANAGER, needs=("p.3",), repeat=Repeat.PER_ITEM, item_set="things",
          item_needs=("p.3",), group="work"),
        s("p.5", "Path b", StepKind.PERSON, role=Role.MANAGER, needs=("p.3",), repeat=Repeat.PER_ITEM, item_set="things",
          item_needs=("p.3",), group="work"),
        s("p.6", "Wait for a note", StepKind.WAIT, role=Role.MANAGER, ends_by_note=True, group="work"),
        s("p.7", "Facts", StepKind.CHECK, role=Role.JASON, check=lambda v: None),
        s("p.8", "Fix", StepKind.PERSON, role=Role.MANAGER, needs=("p.7",), remedy_of="p.7"),
        s("p.9", "After", StepKind.PERSON, role=Role.MANAGER, needs=("p.8", "p.4", "p.5", "p.6"),
          clock=ClockDef(ClockBasis.LAW, "due_on", 3, cite="EX 1.1", business_days=True)),
    )
    return Workflow("rich", "Rich", "example", "unit", steps=steps, dates=(DateSlot("due_on", "Due", required=False),),
                    groups=(StepGroup("intake", "Intake"),))


THINGS = ("t1", "t2", "t3", "t9")


def random_events(rng: random.Random, length: int) -> list[Event]:
    """A plausible and an implausible log alike: every event kind the fold reads, for steps it has and one it lacks, for items
    it has and ones it does not, in any order. The fold must read all of it the same way every time."""
    rows: list[Event] = [Event(1, K.OPENED, OWNER, AT, detail={"definition": "rich", "subject": "unit:1", "label": "R",
                                                                "dates": {"due_on": "2099-09-30"},
                                                                **({"draft": True} if rng.random() < 0.2 else {})})]
    step_ids = [f"p.{i}" for i in range(1, 10)] + ["p.99"]
    if rng.random() < 0.8:                       # most logs begin by naming some items
        rows.append(Event(2, K.NOTE, OWNER, AT, detail={"items_supplied": {"set": "things", "items": list(THINGS[:rng.randrange(1, 4)])}}))
    for n in range(len(rows) + 1, length + len(rows) + 1):
        if rng.random() < 0.55:                  # and then mostly walk the happy path, in an order that is not quite right
            item = rng.choice(THINGS[:3])
            kind, step, detail, by = rng.choice([
                (K.CHECK_RAN, "p.1", {"ok": True, "evidence": [], "item": item}, "jason"),
                (K.CHECK_RAN, "p.1", {"ok": False, "message": "no", "item": item}, "jason"),
                (K.ATTESTED, "p.2", {"item": item, "record": "r"}, OWNER),
                (K.NOT_APPLICABLE, "p.2", {"item": item, "reason": "x", "record": "y"}, OWNER),
                (K.ATTESTED, "p.3", {"item": item, "choice": rng.choice(["a", "b"])}, OWNER),
                (K.ATTESTED, "p.4", {"item": item}, OWNER),
                (K.ATTESTED, "p.5", {"item": item}, OWNER),
                (K.ARRIVED, "p.6", {"what": "a letter"}, rng.choice([OWNER, "jason"])),
                (K.CHECK_RAN, "p.7", {"ok": rng.random() < 0.5, "message": "no", "evidence": []}, "jason"),
                (K.ATTESTED, "p.8", {}, OWNER), (K.ATTESTED, "p.9", {}, OWNER),
                (K.REOPENED, rng.choice(["p.2", "p.3", "p.8"]), {"item": item, "reason": "again"}, OWNER)])
            rows.append(Event(n, kind, by, f"2099-09-15T09:{n % 60:02d}:00Z", step=step, detail=detail))
            continue
        kind = rng.choice([K.CHECK_RAN, K.ATTESTED, K.ARRIVED, K.SKIPPED, K.NOT_APPLICABLE, K.REOPENED, K.NOTE, K.NOTE, K.NOTE,
                           K.DATE_SET, K.PAUSED, K.RESUMED, K.CHANGED, K.SPAWNED, K.WAITED, K.CANCELLED if rng.random() < 0.05 else K.NOTE])
        step, detail = rng.choice(step_ids), {}
        item = rng.choice(THINGS + ("",))
        if item:
            detail["item"] = item
        if kind is K.CHECK_RAN:
            detail.update({"ok": rng.random() < 0.6, "evidence": [f"store:x@{rng.randrange(3)}"], "message": "m"})
        elif kind is K.ATTESTED and rng.random() < 0.5:
            detail["choice"] = rng.choice(["a", "b", "c"])
        elif kind is K.NOTE:
            if rng.random() < 0.7:
                entries = [rng.choice([*THINGS[:3], {"id": rng.choice(THINGS), "dates": {"due_on": f"2099-10-{rng.randrange(1, 29):02d}"}},
                                       {"id": "bad", "dates": {"nope": "2099-01-01"}}, 7, {}]) for _ in range(rng.randrange(0, 4))]
                detail["items_supplied"] = {"set": rng.choice(["things", "things", "other", ""]), "items": entries}
                step = ""
            else:
                detail["text"] = "a note"
        elif kind is K.DATE_SET:
            detail.update({"slot": rng.choice(["due_on", "ghost"]), "day": rng.choice(["2099-10-05", "2099-11-02", "bad"])})
            step = ""
        elif kind in (K.PAUSED, K.CANCELLED):
            detail["reason"] = "r"
            step = ""
        elif kind is K.RESUMED:
            step = ""
        elif kind is K.SPAWNED:
            detail["child"] = f"run-{rng.randrange(3)}"
        by = rng.choice(["jason", OWNER, SECRETARY])
        rows.append(Event(n, kind, by, f"2099-09-15T09:{n % 60:02d}:00Z", step=step, detail=detail))
    return rows


def plain(v) -> dict:
    """A view as plain data, for a comparison that says what differs."""
    return json.loads(json.dumps(v, default=lambda o: (o.value if hasattr(o, "value") else dict(o.__dict__) if hasattr(o, "__dict__")
                                                       else sorted(o) if isinstance(o, (set, frozenset)) else str(o)), sort_keys=True))


SEEDS = range(150)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_fold_is_deterministic_and_never_fails_on_any_log(seed):
    rng = random.Random(seed)
    events = random_events(rng, rng.randrange(0, 45))
    wf = rich_flow()
    day = date(2099, 9, 1) + timedelta(days=rng.randrange(0, 120))
    first = fold.state(events, wf, day, {"run-0": "done", "run-1": "cancelled"}, run_id="run-p")
    assert fold.state(list(events), wf, day, {"run-0": "done", "run-1": "cancelled"}, run_id="run-p") == first
    # a log read back from its stored lines folds the same
    again = [Event.from_dict(json.loads(json.dumps(e.to_dict()))) for e in events]
    assert fold.state(again, wf, day, {"run-1": "cancelled", "run-0": "done"}, run_id="run-p") == first       # key order is nothing
    # the calendar as a set, a list, or text is one calendar
    cal = ["2099-09-21", "2099-10-12"]
    base = fold.state(events, wf, day, {}, run_id="run-p", holidays=cal)
    assert fold.state(events, wf, day, {}, run_id="run-p", holidays=frozenset(map(date.fromisoformat, cal))) == base
    assert fold.state(events, wf, day, {}, run_id="run-p", holidays=reversed(cal)) == base


@pytest.mark.parametrize("seed", SEEDS)
def test_a_prefix_gives_the_earlier_view_and_what_a_later_event_adds_never_changes_it(seed):
    rng = random.Random(1000 + seed)
    events = random_events(rng, rng.randrange(1, 40))
    wf = rich_flow()
    day = date(2099, 10, 1)
    full = fold.state(events, wf, day, {}, run_id="run-p")
    for cut in sorted({rng.randrange(1, len(events) + 1) for _ in range(4)}):
        earlier = fold.state(events[:cut], wf, day, {}, run_id="run-p")
        assert earlier.n == cut
        # item sets only grow, in the order they were given
        for name, items in earlier.item_sets.items():
            assert full.item_sets[name][:len(items)] == items
        # the dates a run has are those of its prefix, until a later date-set changes one
        assert set(earlier.dates) <= set(full.dates)
        # the groups are the same rows (the definition's), whatever the log says
        assert [g.key for g in earlier.groups] == [g.key for g in full.groups] == ["intake", "work"]
        assert [s.id for s in earlier.steps] == [s.id for s in full.steps]


@pytest.mark.parametrize("seed", SEEDS)
def test_supplying_what_is_already_there_changes_nothing_but_the_count(seed):
    rng = random.Random(2000 + seed)
    events = random_events(rng, rng.randrange(2, 40))
    supplies = [i for i, e in enumerate(events) if e.detail.get("items_supplied")]
    if not supplies:
        return
    at = rng.choice(supplies)
    doubled = events[:at + 1] + [replace(events[at], n=0)] + events[at + 1:]
    doubled = [replace(e, n=i + 1) for i, e in enumerate(doubled)]
    wf = rich_flow()
    a = fold.state(events, wf, date(2099, 10, 1), {}, run_id="run-p")
    b = fold.state(doubled, wf, date(2099, 10, 1), {}, run_id="run-p")
    strip = lambda v: {k: x for k, x in plain(v).items() if k not in ("n", "updated")}    # noqa: E731
    assert strip(a) == strip(b)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_states_do_not_depend_on_the_day_except_through_clocks_and_nothing_reads_the_wall_clock(seed):
    rng = random.Random(3000 + seed)
    events = random_events(rng, rng.randrange(1, 40))
    wf = rich_flow()
    early = fold.state(events, wf, date(2099, 9, 1), {}, run_id="run-p")
    late = fold.state(events, wf, date(2101, 1, 1), {}, run_id="run-p")
    assert [(s.id, s.state, s.items, s.reason) for s in early.steps] == [(s.id, s.state, s.items, s.reason) for s in late.steps]
    assert [(c.key, c.due) for c in early.clocks] == [(c.key, c.due) for c in late.clocks]            # when it is due is the log's
    assert early.state is late.state or {early.state, late.state} <= {RunState.ACTIVE, RunState.WAITING, RunState.FAILED}
    assert [(g.key, g.state, g.done, g.expanded) for g in early.groups] == [(g.key, g.state, g.done, g.expanded) for g in late.groups]


@pytest.mark.parametrize("seed", range(60))
def test_every_failed_check_with_an_open_remedy_leaves_the_run_unfailed_and_never_the_current_step(seed):
    rng = random.Random(4000 + seed)
    events = random_events(rng, rng.randrange(1, 40))
    v = fold.state(events, rich_flow(), date(2099, 10, 1), {}, run_id="run-p")
    held = [s for s in v.steps if s.state is S.FAILED and s.remedy]
    for s in held:
        assert v.current != s.id and v.step(s.remedy).state in (S.READY, S.RUNNING, S.WAITING, S.NEEDS_PERSON)
    if v.state is RunState.FAILED:
        assert any(s.state is S.FAILED and not s.remedy for s in v.steps)
    # a roll-up of a step with items is one of its items' states, or done/skipped when all are finished
    for s in v.steps:
        if s.items and v.step(s.id).item_counts:
            states = [st for _, st in s.items]
            assert s.state in set(states) | {S.DONE, S.SKIPPED}
            assert dict(s.item_counts) == {st: states.count(st) for st in set(states)}


@pytest.mark.parametrize("seed", range(40))
def test_the_roll_up_does_not_care_about_order_and_a_failure_always_shows(seed):
    rng = random.Random(5000 + seed)
    states = [rng.choice(list(S)) for _ in range(rng.randrange(1, 8))]
    shuffled = list(states)
    rng.shuffle(shuffled)
    assert fold.rollup(states) is fold.rollup(shuffled)
    assert fold.rollup([*states, S.FAILED]) is S.FAILED


@pytest.mark.parametrize("seed", range(60))
def test_business_day_arithmetic_is_consistent(seed):
    rng = random.Random(6000 + seed)
    base = date(2099, 1, 1) + timedelta(days=rng.randrange(0, 365))
    holidays = {base + timedelta(days=rng.randrange(-30, 60)) for _ in range(rng.randrange(0, 12))}
    n, m = rng.randrange(0, 25), rng.randrange(0, 25)
    landed = fold.add_business_days(base, n, holidays)
    assert (n == 0 and landed == base) or fold.is_business_day(landed, holidays)
    assert landed >= base and fold.add_business_days(base, n + 1, holidays) > landed                 # strictly later each day
    assert fold.add_business_days(landed, m, holidays) == fold.add_business_days(base, n + m, holidays)       # counting in two goes
    if fold.is_business_day(base, holidays) and n:
        assert fold.add_business_days(landed, -n, holidays) == base                                  # and back again
    between = [base + timedelta(days=i) for i in range(1, (landed - base).days + 1)]
    assert sum(1 for d in between if fold.is_business_day(d, holidays)) == n


# --- the web layer reads a run that uses them -------------------------------------------------------------------------------------

from test_web_work import app, as_, page, world  # noqa: E402,F401 - fixtures


def test_the_run_page_reads_item_sets_per_item_clocks_groups_and_a_remedy_without_breaking(app, world):
    definitions.register(item_flow(groups=(StepGroup("intake", "Intake"),)))
    definitions.register(remedy_flow())
    rid = api.start(world, ITEMS, "period:2099-09", "Items", {"due_on": "2099-10-01"}, "A Manager", yes=True,
                    today=date(2099, 9, 20), at=AT)["run"]["id"]
    api.open_run(world, rid, "A Manager", readers=FakeReaders(), yes=True, today=date(2099, 9, 20))
    api.supply_items(world, rid, "requests", ["req:1", "req:2"], "A Manager", roles_of=lambda by: ["manager"], today=date(2099, 9, 20))
    body = page(app, "A Manager", rid, ITEMS)
    steps = {s["id"]: s for s in body["steps"]}
    assert steps["i.2"]["state"] and steps["i.6"]["state"] == "not started"
    assert {c["key"] for c in body["clocks"]} >= {"i.2[req:1]", "i.2[req:2]"}
    readers = FakeReaders()
    readers.checks["r.1"] = CheckResult(False, (), "short")
    rid2 = api.start(world, REMEDY, "campaign:R-2099", "Remedy", {}, "A Manager", today=date(2099, 9, 20), at=AT)["run"]["id"]
    api.open_run(world, rid2, "A Manager", readers=readers, today=date(2099, 9, 20))
    other = {s["id"]: s for s in page(app, "A Manager", rid2, REMEDY)["steps"]}      # the page's own dry resume re-reads the check
    assert set(other) == {"r.1", "r.2", "r.3", "r.4"}
