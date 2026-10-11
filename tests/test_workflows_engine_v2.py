"""The engine's second round (docs/workflows-engine.md, section 10, "Engine limits found"): steps several roles may act on, a
not-applicable outcome that is not a skip, dates set after the start, a step that waits on its child runs, the ``provider``
clock basis, and the ``developer`` and ``reviewer`` roles.

Everything is made up ("A. Manager", "123 Main St", 2099). The first test is the one that matters most: a log written before
any of this existed, kept here as the lines it was stored as, folds to exactly what it folded to then.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from jason.workflows import api, definitions, fold, store
from jason.workflows.api import view_dict
from jason.workflows.steps import may_act
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, DateTiming, Event, EventKind, GateVerdict, NotApplicable, OFFICES, Repeat, Role,
    RunState, SkipRule, StepAsk, StepDef, StepKind, StepRefused, StepState as S, Workflow, followup_basis,
)
from test_workflows_support import FakeReaders, OWNER, SECRETARY, TREASURER, VISITOR, data  # noqa: F401 - data is a fixture

TODAY = date(2099, 9, 20)
DEVELOPER = "D. Developer"
ROLES = {OWNER: {"manager"}, SECRETARY: {"secretary", "director"}, TREASURER: {"treasurer"}, VISITOR: set(),
         DEVELOPER: {"developer"}}


def roles_of(by):
    return ROLES.get(by, ())


# --- the golden log -------------------------------------------------------------------------------------------------------------
# These lines are a run as the engine stored it before this round: no ``not-applicable`` or ``date-set`` event, no step with
# several roles, a child run on a step that does not wait for it. The expected views below were taken from the engine of that
# day (``fold.state`` over these events), and must not change.

GOLDEN_LINES = """
{"n":1,"kind":"opened","by":"A. Manager","at":"2099-09-15T09:01:00Z","detail":{"definition":"golden","subject":"campaign:G","label":"Golden","items":["u1","u2"],"dates":{"answers_by":"2099-10-23","closes_on":"2099-11-01"},"draft":true},"prev":""}
{"n":2,"kind":"resumed","by":"A. Manager","at":"2099-09-15T09:02:00Z","detail":{"activated":true},"prev":"54979e4ac90f"}
{"n":3,"kind":"check-ran","step":"g.1","by":"jason","at":"2099-09-15T09:03:00Z","detail":{"ok":true,"evidence":["store:facts@a1"]},"prev":"fbb00141a009"}
{"n":4,"kind":"attested","step":"g.2","by":"A. Manager","at":"2099-09-15T09:04:00Z","detail":{"what":"Send the notice","record":"notice-1","evidence":["store:notices@n1"]},"prev":"15f83fc22aed"}
{"n":5,"kind":"plan-made","step":"g.3","by":"jason","at":"2099-09-15T09:05:00Z","detail":{"approval":"ap-1","key":"k"},"prev":"0b06e10cb1e9"}
{"n":6,"kind":"approval-decided","step":"g.3","by":"jason","at":"2099-09-15T09:06:00Z","detail":{"status":"approved"},"prev":"25ed8afa7053"}
{"n":7,"kind":"applied","step":"g.3","by":"jason","at":"2099-09-15T09:07:00Z","detail":{"approval":"ap-1"},"prev":"c27448eaf2b0"}
{"n":8,"kind":"job-queued","step":"g.4","by":"jason","at":"2099-09-15T09:08:00Z","detail":{"job":"job-1"},"prev":"92f0a9aedee9"}
{"n":9,"kind":"job-finished","step":"g.4","by":"jason","at":"2099-09-15T09:09:00Z","detail":{"ok":true},"prev":"cb1ea204564b"}
{"n":10,"kind":"waited","step":"g.5","by":"jason","at":"2099-09-15T09:10:00Z","detail":{"until":"2099-10-23"},"prev":"744ede443d79"}
{"n":11,"kind":"arrived","step":"g.5","by":"A. Manager","at":"2099-09-15T09:11:00Z","detail":{"what":"answer"},"prev":"b090c4354c73"}
{"n":12,"kind":"decided","step":"g.6","by":"S. Placeholder","at":"2099-09-15T09:12:00Z","detail":{"motion":"m","outcome":"tabled","record":"min-1"},"prev":"f32e9ef25e43"}
{"n":13,"kind":"decided","step":"g.6","by":"S. Placeholder","at":"2099-09-15T09:13:00Z","detail":{"motion":"m","outcome":"adopted","record":"min-2"},"prev":"b683a300adab"}
{"n":14,"kind":"attested","step":"g.7","by":"S. Placeholder","at":"2099-09-15T09:14:00Z","detail":{"choice":"renew","what":"chose renew"},"prev":"29501cb79abc"}
{"n":15,"kind":"spawned","step":"g.10","by":"A. Manager","at":"2099-09-15T09:15:00Z","detail":{"child":"run-c1","definition":"child-def"},"prev":"870b843df5ca"}
{"n":16,"kind":"spawned","step":"g.10","by":"A. Manager","at":"2099-09-15T09:16:00Z","detail":{"child":"run-c2","definition":"child-def"},"prev":"1eb27751aebc"}
{"n":17,"kind":"attested","step":"g.11","by":"A. Manager","at":"2099-09-15T09:17:00Z","detail":{"item":"u1","what":"Letter","record":"r-u1"},"prev":"243a8fe9db43"}
{"n":18,"kind":"skipped","step":"g.12","by":"A. Manager","at":"2099-09-15T09:18:00Z","detail":{"reason":"not needed"},"prev":"ef8a514cdec3"}
{"n":19,"kind":"attested","step":"g.13","by":"A. Manager","at":"2099-09-15T09:19:00Z","detail":{"what":"x","record":"r13"},"prev":"0935c2e61732"}
{"n":20,"kind":"reopened","step":"g.13","by":"A. Manager","at":"2099-09-15T09:20:00Z","detail":{"reason":"redo"},"prev":"c28a95365f79"}
{"n":21,"kind":"attested","step":"g.14","by":"A. Manager","at":"2099-09-15T09:21:00Z","detail":{"choice":"yes","what":"chose yes"},"prev":"f59a7fea7d82"}
{"n":22,"kind":"spawned","step":"g.14","by":"A. Manager","at":"2099-09-15T09:22:00Z","detail":{"child":"run-c3","definition":"child-def"},"prev":"6ce6ce38bcc8"}
{"n":23,"kind":"changed","step":"g.2","by":"jason","at":"2099-09-15T09:23:00Z","detail":{"differences":[{"address":"store:notices","was":"n1","now":"n2"}],"evidence":["store:notices@n2"]},"prev":"8dfdc9c090a9"}
{"n":24,"kind":"note","by":"A. Manager","at":"2099-09-15T09:24:00Z","detail":{"text":"a note"},"prev":"330e7f48cb12"}
{"n":25,"kind":"paused","by":"A. Manager","at":"2099-09-15T09:25:00Z","detail":{"reason":"hold"},"prev":"634dfed7c962"}
{"n":26,"kind":"resumed","by":"A. Manager","at":"2099-09-15T09:26:00Z","detail":{},"prev":"eceecf044e7e"}
{"n":27,"kind":"note","step":"g.15","by":"A. Manager","at":"2099-09-15T09:27:00Z","detail":{"text":"replaced","supersedes":"g.15"},"prev":"a41803cddadb"}
"""

GOLDEN_EXPECTED = {'c2_unfinished': {'children': ['run-c1', 'run-c2', 'run-c3'],
                   'clocks': [['run.0', 'overdue', -30, '2099-11-01'], ['g.5', 'satisfied', -39, '2099-10-23']],
                   'current': 'g.8',
                   'dates': {'answers_by': '2099-10-23', 'closes_on': '2099-11-01'},
                   'links': [['approval', 'ap-1', 'g.3'],
                             ['job', 'job-1', 'g.4'],
                             ['run', 'run-c1', 'g.10'],
                             ['run', 'run-c2', 'g.10'],
                             ['run', 'run-c3', 'g.14']],
                   'n': 27,
                   'pastLaw': [],
                   'state': 'active',
                   'steps': {'g.1': ['done', '', 'jason', '', [], '', ['store:facts@a1'], []],
                             'g.10': ['waiting', 'child run run-c2 is not finished', '', '', [], '', [], []],
                             'g.11': ['needs a person',
                                      '1 of 2 items done',
                                      '',
                                      '',
                                      [['u1', 'done'], ['u2', 'needs a person']],
                                      '',
                                      [],
                                      []],
                             'g.12': ['skipped', 'not needed', 'A. Manager', '', [], '', [], []],
                             'g.13': ['needs a person', '', '', '', [], '', [], []],
                             'g.14': ['done', '', 'A. Manager', '', [], 'yes', [], []],
                             'g.15': ['superseded', 'replaced by a re-plan', '', '', [], '', [], []],
                             'g.2': ['done',
                                     '',
                                     'A. Manager',
                                     'notice-1',
                                     [],
                                     '',
                                     ['store:notices@n2'],
                                     [{'address': 'store:notices', 'now': 'n2', 'was': 'n1'}]],
                             'g.3': ['done', '', 'jason', '', [], '', [], []],
                             'g.4': ['done', '', 'jason', '', [], '', [], []],
                             'g.5': ['done', '', 'A. Manager', '', [], '', [], []],
                             'g.6': ['done', '', 'S. Placeholder', 'min-2', [], '', [], []],
                             'g.7': ['done', '', 'S. Placeholder', '', [], 'renew', [], []],
                             'g.8': ['needs a person', '', '', '', [], '', [], []],
                             'g.9': ['skipped', 'not on the path renew chosen at g.7', 'jason', '', [], '', [], []]}},
 'children_done': {'children': ['run-c1', 'run-c2', 'run-c3'],
                   'clocks': [['run.0', 'upcoming', 2, '2099-11-01'], ['g.5', 'satisfied', -7, '2099-10-23']],
                   'current': 'g.8',
                   'dates': {'answers_by': '2099-10-23', 'closes_on': '2099-11-01'},
                   'links': [['approval', 'ap-1', 'g.3'],
                             ['job', 'job-1', 'g.4'],
                             ['run', 'run-c1', 'g.10'],
                             ['run', 'run-c2', 'g.10'],
                             ['run', 'run-c3', 'g.14']],
                   'n': 27,
                   'pastLaw': [],
                   'state': 'active',
                   'steps': {'g.1': ['done', '', 'jason', '', [], '', ['store:facts@a1'], []],
                             'g.10': ['done', 'child run run-c2 is cancelled', 'A. Manager', '', [], '', [], []],
                             'g.11': ['needs a person',
                                      '1 of 2 items done',
                                      '',
                                      '',
                                      [['u1', 'done'], ['u2', 'needs a person']],
                                      '',
                                      [],
                                      []],
                             'g.12': ['skipped', 'not needed', 'A. Manager', '', [], '', [], []],
                             'g.13': ['needs a person', '', '', '', [], '', [], []],
                             'g.14': ['done', '', 'A. Manager', '', [], 'yes', [], []],
                             'g.15': ['superseded', 'replaced by a re-plan', '', '', [], '', [], []],
                             'g.2': ['done',
                                     '',
                                     'A. Manager',
                                     'notice-1',
                                     [],
                                     '',
                                     ['store:notices@n2'],
                                     [{'address': 'store:notices', 'now': 'n2', 'was': 'n1'}]],
                             'g.3': ['done', '', 'jason', '', [], '', [], []],
                             'g.4': ['done', '', 'jason', '', [], '', [], []],
                             'g.5': ['done', '', 'A. Manager', '', [], '', [], []],
                             'g.6': ['done', '', 'S. Placeholder', 'min-2', [], '', [], []],
                             'g.7': ['done', '', 'S. Placeholder', '', [], 'renew', [], []],
                             'g.8': ['needs a person', '', '', '', [], '', [], []],
                             'g.9': ['skipped', 'not on the path renew chosen at g.7', 'jason', '', [], '', [], []]}},
 'open': {'children': ['run-c1', 'run-c2', 'run-c3'],
          'clocks': [['run.0', 'upcoming', 42, '2099-11-01'], ['g.5', 'satisfied', 33, '2099-10-23']],
          'current': 'g.8',
          'dates': {'answers_by': '2099-10-23', 'closes_on': '2099-11-01'},
          'links': [['approval', 'ap-1', 'g.3'],
                    ['job', 'job-1', 'g.4'],
                    ['run', 'run-c1', 'g.10'],
                    ['run', 'run-c2', 'g.10'],
                    ['run', 'run-c3', 'g.14']],
          'n': 27,
          'pastLaw': [],
          'state': 'active',
          'steps': {'g.1': ['done', '', 'jason', '', [], '', ['store:facts@a1'], []],
                    'g.10': ['waiting', 'child run run-c2 is not finished', '', '', [], '', [], []],
                    'g.11': ['needs a person',
                             '1 of 2 items done',
                             '',
                             '',
                             [['u1', 'done'], ['u2', 'needs a person']],
                             '',
                             [],
                             []],
                    'g.12': ['skipped', 'not needed', 'A. Manager', '', [], '', [], []],
                    'g.13': ['needs a person', '', '', '', [], '', [], []],
                    'g.14': ['done', '', 'A. Manager', '', [], 'yes', [], []],
                    'g.15': ['superseded', 'replaced by a re-plan', '', '', [], '', [], []],
                    'g.2': ['done',
                            '',
                            'A. Manager',
                            'notice-1',
                            [],
                            '',
                            ['store:notices@n2'],
                            [{'address': 'store:notices', 'now': 'n2', 'was': 'n1'}]],
                    'g.3': ['done', '', 'jason', '', [], '', [], []],
                    'g.4': ['done', '', 'jason', '', [], '', [], []],
                    'g.5': ['done', '', 'A. Manager', '', [], '', [], []],
                    'g.6': ['done', '', 'S. Placeholder', 'min-2', [], '', [], []],
                    'g.7': ['done', '', 'S. Placeholder', '', [], 'renew', [], []],
                    'g.8': ['needs a person', '', '', '', [], '', [], []],
                    'g.9': ['skipped', 'not on the path renew chosen at g.7', 'jason', '', [], '', [], []]}},
 'prefix8': {'children': [],
             'clocks': [['run.0', 'upcoming', 42, '2099-11-01'], ['g.5', 'upcoming', 33, '2099-10-23']],
             'current': 'g.4',
             'dates': {'answers_by': '2099-10-23', 'closes_on': '2099-11-01'},
             'links': [['approval', 'ap-1', 'g.3'], ['job', 'job-1', 'g.4']],
             'n': 8,
             'pastLaw': [],
             'state': 'active',
             'steps': {'g.1': ['done', '', 'jason', '', [], '', ['store:facts@a1'], []],
                       'g.10': ['needs a person', '', '', '', [], '', [], []],
                       'g.11': ['needs a person',
                                '0 of 2 items done',
                                '',
                                '',
                                [['u1', 'needs a person'], ['u2', 'needs a person']],
                                '',
                                [],
                                []],
                       'g.12': ['needs a person', '', '', '', [], '', [], []],
                       'g.13': ['needs a person', '', '', '', [], '', [], []],
                       'g.14': ['needs a person', '', '', '', [], '', [], []],
                       'g.15': ['needs a person', '', '', '', [], '', [], []],
                       'g.2': ['done', '', 'A. Manager', 'notice-1', [], '', ['store:notices@n1'], []],
                       'g.3': ['done', '', 'jason', '', [], '', [], []],
                       'g.4': ['running', 'queued', '', '', [], '', [], []],
                       'g.5': ['not started', '', '', '', [], '', [], []],
                       'g.6': ['not started', '', '', '', [], '', [], []],
                       'g.7': ['not started', '', '', '', [], '', [], []],
                       'g.8': ['not started', '', '', '', [], '', [], []],
                       'g.9': ['not started', '', '', '', [], '', [], []]}}}


def golden_workflow() -> Workflow:
    s = StepDef
    steps = (
        s("g.1", "Read the facts", StepKind.CHECK, role=Role.JASON, evidence=("store:facts",)),
        s("g.2", "Send the notice", StepKind.PERSON, role=Role.MANAGER, needs=("g.1",), record="the sent notice",
          skip=SkipRule((Role.MANAGER,)), evidence=("store:notices",)),
        s("g.3", "Apply the tags", StepKind.PLAN, role=Role.MANAGER, needs=("g.2",), plan_kind="example-plan"),
        s("g.4", "Build the report", StepKind.JOB, role=Role.JASON, needs=("g.3",), job="example-report"),
        s("g.5", "Wait for the answer", StepKind.WAIT, role=Role.MANAGER, needs=("g.4",),
          clock=ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 123.4"), legal=True),
        s("g.6", "The board decides", StepKind.DECISION, role=Role.SECRETARY, needs=("g.5",), record="the minutes"),
        s("g.7", "Choose a path", StepKind.BRANCH, role=Role.SECRETARY, needs=("g.6",),
          choices=(Choice("renew", ("g.8",)), Choice("none", ("g.9",)))),
        s("g.8", "Renew", StepKind.PERSON, role=Role.MANAGER, needs=("g.7",)),
        s("g.9", "Close out", StepKind.PERSON, role=Role.MANAGER, needs=("g.7",)),
        s("g.10", "Start the child run", StepKind.PERSON, role=Role.MANAGER, spawns="child-def"),
        s("g.11", "Letter for each item", StepKind.PERSON, role=Role.MANAGER, repeat=Repeat.PER_ITEM, skip=SkipRule()),
        s("g.12", "Optional step", StepKind.PERSON, role=Role.MANAGER, skip=SkipRule((Role.MANAGER, Role.SECRETARY))),
        s("g.13", "Reopened step", StepKind.PERSON, role=Role.MANAGER),
        s("g.14", "Spawning branch", StepKind.BRANCH, role=Role.MANAGER, spawns="child-def",
          choices=(Choice("yes", ()), Choice("no", ()))),
        s("g.15", "Superseded step", StepKind.PERSON, role=Role.MANAGER),
    )
    return Workflow("golden", "Golden", "example", "campaign", steps,
                    dates=(DateSlot("answers_by", "Answers by"), DateSlot("closes_on", "Closes", after="answers_by"),
                           DateSlot("extra_on", "Extra", required=False)),
                    clocks=(ClockDef(ClockBasis.PERSON, "closes_on", 0, label="closes"),))


def compact(v) -> dict:
    return {
        "state": v.state.value, "current": v.current, "n": v.n, "children": list(v.children), "pastLaw": list(v.past_law),
        "dates": dict(v.dates),
        "steps": {s.id: [s.state.value, s.reason, s.by, s.record, [[i, st.value] for i, st in s.items], s.choice,
                         list(s.evidence), [dict(c) for c in s.changed]] for s in v.steps},
        "clocks": [[c.key, c.status, c.days, c.due] for c in v.clocks],
        "links": [[link.kind, link.address, link.step] for link in v.links],
    }


def test_a_log_written_before_this_round_folds_identically(data):
    rid = "run-golden"
    file = store.path(data, "golden", rid)
    file.parent.mkdir(parents=True)
    file.write_bytes((GOLDEN_LINES.strip("\n") + "\n").encode("utf-8"))
    run = store.read(data, "golden", rid)
    assert run.n == 27 and not run.torn and not run.corrupt
    events = list(run.events)
    wf = golden_workflow()
    assert definitions.validate(wf, plan_kinds={"example-plan"}, jobs={"example-report"}) == []
    day = date(2099, 9, 20)
    assert compact(fold.state(events, wf, day, {}, run_id=rid)) == GOLDEN_EXPECTED["open"]
    assert compact(fold.state(events, wf, date(2099, 10, 30), {"run-c1": "done", "run-c2": "cancelled", "run-c3": "running"},
                              run_id=rid)) == GOLDEN_EXPECTED["children_done"]
    assert compact(fold.state(events, wf, date(2099, 12, 1), {"run-c1": "done"}, run_id=rid)) == GOLDEN_EXPECTED["c2_unfinished"]
    assert compact(fold.state(events[:8], wf, day, {}, run_id=rid)) == GOLDEN_EXPECTED["prefix8"]
    # what the new fold adds is neutral for an old log: no step is not-applicable, each step's roles are its one role
    view = fold.state(events, wf, day, {}, run_id=rid)
    assert not any(s.na for s in view.steps)
    assert all(s.roles == (wf.step(s.id).role,) for s in view.steps)
    assert [d.name for d in view.date_slots if d.settable] == ["extra_on"]       # an optional slot is now settable
    # a spawn on a step that does not wait for its child behaves as it did: the last child decides, a branch never waits
    assert view.step("g.10").children == ("run-c1", "run-c2")
    assert view.state_of("g.10") is S.WAITING and view.state_of("g.14") is S.DONE


def test_the_old_run_json_keeps_every_key_it_had(data):
    definitions.reset()
    try:
        definitions.register(golden_workflow(), plan_kinds={"example-plan"}, jobs={"example-report"})
        rid = "run-golden"
        file = store.path(data, "golden", rid)
        file.parent.mkdir(parents=True)
        file.write_bytes((GOLDEN_LINES.strip("\n") + "\n").encode("utf-8"))
        shown = api.show(data, rid, today=date(2099, 9, 20), readers=FakeReaders())
    finally:
        definitions.reset()
    for key in ("id", "definition", "subject", "label", "owner", "opened", "state", "current", "n", "updated", "dates", "items",
                "parent", "pausedReason", "cancelledReason", "steps", "clocks", "links", "orphans", "children", "pastLaw"):
        assert key in shown, key
    for key in ("id", "title", "kind", "role", "state", "reason", "by", "at", "record", "blockedBy", "changed", "items", "choice"):
        assert key in shown["steps"][0], key
    assert shown["steps"][0]["roles"] == ["jason"] and shown["steps"][0]["na"] is False


# --- a definition that uses all of it -------------------------------------------------------------------------------------------

V2 = "v2-flow"
SUBJECT = "campaign:V2-2099"
START = {"answers_by": "2099-10-23", "fixed_on": "2099-09-01"}
AT = "2099-09-15T09:00:00Z"


def v2(**over) -> Workflow:
    s = StepDef
    steps = (
        s("v2.1", "Either office reports", StepKind.PERSON, role=Role.MANAGER, roles=(Role.TREASURER,), record="the report",
          skip=SkipRule(), na=NotApplicable()),
        s("v2.2", "The legal step that may not apply", StepKind.PERSON, role=Role.MANAGER, needs=("v2.1",),
          clock=ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 1.2", label="the answer"),
          na=NotApplicable(roles=(Role.SECRETARY, Role.MANAGER))),
        s("v2.3", "After the legal step", StepKind.PERSON, role=Role.MANAGER, needs=("v2.2",),
          clock=ClockDef(ClockBasis.PROVIDER, "recorded_on", 30, label="the provider's report")),
        s("v2.4", "A person step that waits for its children", StepKind.PERSON, role=Role.MANAGER, spawns="v2-child",
          waits_on_child=True),
        s("v2.5", "A branch that waits for its children", StepKind.BRANCH, role=Role.MANAGER, spawns="v2-child",
          waits_on_child=True, choices=(Choice("go", ("v2.7",)), Choice("stop", ("v2.8",)))),
        s("v2.6", "A spawn that does not wait", StepKind.PERSON, role=Role.MANAGER, spawns="v2-child"),
        s("v2.7", "The go path", StepKind.PERSON, role=Role.MANAGER, needs=("v2.5",)),
        s("v2.8", "The stop path", StepKind.PERSON, role=Role.MANAGER, needs=("v2.5",)),
        s("v2.9", "A wait either office ends", StepKind.WAIT, role=Role.MANAGER, roles=(Role.TREASURER,)),
    )
    base = dict(
        key=V2, title="V2 flow", family="example", subject="campaign", steps=steps,
        dates=(DateSlot("answers_by", "Answers by"), DateSlot("fixed_on", "Fixed on"),
               DateSlot("reply_on", "Reply on", required=False),
               DateSlot("recorded_on", "Recorded on", late=True, timing=DateTiming.PAST),
               DateSlot("visit_on", "Visit on", late=True, timing=DateTiming.FUTURE, roles=(Role.SECRETARY,)),
               DateSlot("closes_on", "Closes on", late=True, after="visit_on")))
    base.update(over)
    return Workflow(**base)


@pytest.fixture
def flow(data):
    definitions.reset()
    wf = definitions.register(v2())
    yield wf
    definitions.reset()


def new_run(data, *, dates=None, open_=True, by=OWNER, subject=SUBJECT):
    rid = api.start(data, V2, subject, "V2", START if dates is None else dates, by, yes=True, today=TODAY, at=AT)["run"]["id"]
    if open_:
        api.open_run(data, rid, by, readers=FakeReaders(), yes=True, today=TODAY, at="2099-09-15T09:01:00Z")
    return rid


def view(data, rid, day=TODAY, children=None):
    run = store.open_run(data, rid)
    return fold.state(list(run.events), definitions.get(V2), day, children or {}, run_id=rid)


def kinds(data, rid):
    return [e.kind for e in store.open_run(data, rid).events]


# --- (1) several roles ----------------------------------------------------------------------------------------------------------

def test_validate_wants_roles_that_are_roles_each_once_and_not_the_primary():
    ok = Workflow("w", "W", "f", "unit", steps=(StepDef("w.1", "Do it", StepKind.PERSON, role=Role.MANAGER, roles=(Role.TREASURER,)),))
    assert definitions.validate(ok) == []

    def problems(**kw):
        wf = Workflow("w", "W", "f", "unit", steps=(StepDef("w.1", "Do it", StepKind.PERSON, **kw),))
        return [p.message for p in definitions.validate(wf)]

    assert any("repeats" in m for m in problems(role=Role.MANAGER, roles=(Role.TREASURER, Role.TREASURER)))
    assert any("primary" in m for m in problems(role=Role.MANAGER, roles=(Role.MANAGER,)))
    assert any("is not a Role" in m for m in problems(role=Role.MANAGER, roles=("treasurer",)))
    assert any("not jason's" in m for m in problems(role=Role.MANAGER, roles=(Role.JASON,)))
    decision = Workflow("w", "W", "f", "unit", steps=(StepDef("w.1", "Decide", StepKind.DECISION, role=Role.SECRETARY, roles=(Role.ANYONE,)),))
    assert any("decision" in p.message for p in definitions.validate(decision))


def test_every_role_of_a_step_may_act_and_the_primary_stays_the_one_listed(data, flow):
    rid = new_run(data)
    sv = view(data, rid).step("v2.1")
    assert sv.role is Role.MANAGER and sv.roles == (Role.MANAGER, Role.TREASURER)
    assert flow.step("v2.1").acting_roles == (Role.MANAGER, Role.TREASURER)
    assert replace(flow.step("v2.1"), roles=(Role.TREASURER, Role.MANAGER)).acting_roles == (Role.MANAGER, Role.TREASURER)
    shown = api.show(data, rid, today=TODAY)
    assert shown["steps"][0]["role"] == "manager" and shown["steps"][0]["roles"] == ["manager", "treasurer"]
    with pytest.raises(StepRefused, match=r"does not hold a role that v2\.1 needs \(manager or treasurer\)"):
        api.attest(data, rid, "v2.1", VISITOR, roles_of=roles_of, record="the report", today=TODAY)
    with pytest.raises(StepRefused, match="does not hold a role"):
        api.attest(data, rid, "v2.1", SECRETARY, roles_of=roles_of, record="the report", today=TODAY)
    done = api.attest(data, rid, "v2.1", TREASURER, roles_of=roles_of, record="the report", today=TODAY)
    assert done["run"]["steps"][0]["state"] == "done" and done["run"]["steps"][0]["by"] == TREASURER
    assert may_act(flow.step("v2.1"), OWNER, roles_of) and not may_act(flow.step("v2.1"), VISITOR, roles_of)


def test_a_single_role_step_keeps_its_old_refusal_words(data, flow):
    rid = new_run(data)
    api.attest(data, rid, "v2.1", OWNER, roles_of=roles_of, record="r", today=TODAY)
    with pytest.raises(StepRefused) as caught:
        api.attest(data, rid, "v2.4", VISITOR, roles_of=roles_of, today=TODAY)
    assert str(caught.value) == "V. Visitor does not hold the manager role that v2.4 needs"


def test_a_skip_with_no_roles_of_its_own_is_open_to_every_role_of_the_step_and_reopen_and_arrived_too(data, flow):
    rid = new_run(data)
    with pytest.raises(StepRefused, match="only manager, treasurer"):
        api.skip(data, rid, "v2.1", SECRETARY, roles_of=roles_of, reason="not needed", today=TODAY)
    api.skip(data, rid, "v2.1", TREASURER, roles_of=roles_of, reason="not needed", today=TODAY)
    reopened = api.reopen(data, rid, "v2.1", TREASURER, roles_of=roles_of, reason="needed after all", today=TODAY)
    assert reopened["run"]["steps"][0]["state"] == "needs a person"
    with pytest.raises(StepRefused, match="does not hold a role"):
        api.arrived(data, rid, "v2.9", VISITOR, roles_of=roles_of, today=TODAY)
    api.arrived(data, rid, "v2.9", TREASURER, roles_of=roles_of, what="it came", today=TODAY)
    assert view(data, rid).state_of("v2.9") is S.DONE


def test_a_run_is_in_the_dock_of_every_role_of_its_current_step(data, flow):
    from jason.web.extra import office_view

    rid = new_run(data)
    assert api.show(data, rid, today=TODAY)["current"] == "v2.1"
    assert [(r["id"], r["office"]) for r in office_view.runs_for(data, ["treasurer"])] == [(rid, "treasurer")]
    assert [(r["id"], r["office"]) for r in office_view.runs_for(data, ["manager", "treasurer"])] == [(rid, "manager")]
    assert office_view.runs_for(data, ["secretary"]) == []


# --- (2) not applicable ---------------------------------------------------------------------------------------------------------

def test_a_legal_step_may_declare_not_applicable_but_still_has_no_skip():
    legal = StepDef("w.1", "Answer", StepKind.PERSON, role=Role.MANAGER, clock=ClockDef(ClockBasis.LAW, "d", 0, cite="EX 1"),
                    na=NotApplicable())
    wf = Workflow("w", "W", "f", "unit", steps=(legal,), dates=(DateSlot("d"),))
    assert definitions.validate(wf) == []
    bad = replace(legal, skip=SkipRule())
    assert [p.code for p in definitions.validate(replace(wf, steps=(bad,)))] == ["legal-skip"]
    branch = StepDef("w.1", "Choose", StepKind.BRANCH, role=Role.MANAGER, choices=(Choice("a"),), na=NotApplicable())
    assert [p.code for p in definitions.validate(Workflow("w", "W", "f", "unit", steps=(branch,)))] == ["na"]
    odd = StepDef("w.1", "Do", StepKind.PERSON, role=Role.MANAGER, na=NotApplicable(roles=(Role.JASON, Role.JASON)))
    assert any(p.code == "na" for p in definitions.validate(Workflow("w", "W", "f", "unit", steps=(odd,))))


def test_not_applicable_needs_a_person_a_reason_and_a_record_and_a_step_that_declares_it(data, flow):
    rid = new_run(data)
    api.attest(data, rid, "v2.1", OWNER, roles_of=roles_of, record="r", today=TODAY)
    with pytest.raises(StepRefused, match="gives no not-applicable outcome"):
        api.not_applicable(data, rid, "v2.4", OWNER, roles_of=roles_of, reason="x", record="y", today=TODAY)
    with pytest.raises(StepRefused, match="may not record v2.2 as not applicable: only secretary, manager"):
        api.not_applicable(data, rid, "v2.2", TREASURER, roles_of=roles_of, reason="x", record="y", today=TODAY)
    with pytest.raises(StepRefused, match="needs a reason"):
        api.not_applicable(data, rid, "v2.2", OWNER, roles_of=roles_of, record="the notice of 123 Main St", today=TODAY)
    with pytest.raises(StepRefused, match="needs the record"):
        api.not_applicable(data, rid, "v2.2", OWNER, roles_of=roles_of, reason="no answer is owed", today=TODAY)
    with pytest.raises(StepRefused, match="engine's own name"):
        api.not_applicable(data, rid, "v2.2", "jason", reason="x", record="y", today=TODAY)
    n = store.open_run(data, rid).n
    assert kinds(data, rid)[-1] is not EventKind.NOT_APPLICABLE and n == store.open_run(data, rid).n
    # a declaration may ask for less
    lax = replace(flow.step("v2.2"), na=NotApplicable(reason_required=False, record_required=False))
    from jason.workflows import steps as steps_mod

    act = steps_mod.na_act(replace(flow, steps=tuple(lax if s.id == "v2.2" else s for s in flow.steps)),
                           view(data, rid), "v2.2", by=OWNER, roles_of=roles_of)
    assert act.kind is EventKind.NOT_APPLICABLE and act.detail == {}


def test_not_applicable_makes_the_legal_step_done_not_skipped_and_the_clock_says_so(data, flow):
    rid = new_run(data)
    api.attest(data, rid, "v2.1", OWNER, roles_of=roles_of, record="r", today=TODAY)
    before = view(data, rid, date(2099, 11, 1))
    assert before.past_law == ("v2.2",) and before.state_of("v2.3") is S.NOT_STARTED
    with pytest.raises(StepRefused, match="legal step"):                         # it is still not a skip
        api.skip(data, rid, "v2.2", OWNER, roles_of=roles_of, reason="x", today=TODAY)
    out = api.not_applicable(data, rid, "v2.2", SECRETARY, roles_of=roles_of, reason="the answer is owed only on request",
                             record="minutes:2099-09-12#4", today=TODAY, at="2099-09-16T10:00:00Z")
    assert out["event"]["kind"] == "not-applicable" and out["event"]["by"] == SECRETARY
    assert out["event"]["detail"] == {"reason": "the answer is owed only on request", "record": "minutes:2099-09-12#4"}
    sv = out["run"]["steps"][1]
    assert sv["state"] == "done" and sv["na"] is True and sv["by"] == SECRETARY and sv["record"] == "minutes:2099-09-12#4"
    assert sv["reason"] == "recorded as not applicable by S. Placeholder: the answer is owed only on request"
    # it satisfies a needs, so the next step is open; it is not in the skipped column
    assert out["run"]["steps"][2]["state"] == "needs a person"
    assert SKIPPED not in kinds(data, rid)
    # the clock is neither dropped nor read as met
    for day, status in ((TODAY, "not applicable, recorded"), (date(2099, 11, 1), "not applicable, recorded")):
        clock = [c for c in view(data, rid, day).clocks if c.key == "v2.2"][0]
        assert clock.status == status and clock.basis is ClockBasis.LAW and clock.due == "2099-10-23" and clock.cite == "EX 1.2"
    assert view(data, rid, date(2099, 11, 1)).past_law == ()                     # and no follow-up opens for it
    # a person may take it back: the clock runs again
    api.reopen(data, rid, "v2.2", OWNER, roles_of=roles_of, reason="it does apply", today=TODAY)
    back = view(data, rid, date(2099, 11, 1))
    assert back.state_of("v2.2") is S.NEEDS_PERSON and not back.step("v2.2").na and back.past_law == ("v2.2",)


SKIPPED = EventKind.SKIPPED


def test_a_per_item_not_applicable_is_one_item_and_the_step_reads_na_only_when_every_done_item_is(data):
    s = StepDef("p.1", "A letter for each", StepKind.PERSON, role=Role.MANAGER, repeat=Repeat.PER_ITEM, na=NotApplicable())
    wf = Workflow("per", "Per", "f", "unit", steps=(s,))
    definitions.reset()
    definitions.register(wf)
    try:
        rid = api.start(data, "per", "unit:1", "Per", {}, OWNER, items=["a", "b"], today=TODAY, at=AT)["run"]["id"]
        api.open_run(data, rid, OWNER, readers=FakeReaders(), today=TODAY)
        with pytest.raises(StepRefused, match="item by item"):
            api.not_applicable(data, rid, "p.1", OWNER, roles_of=roles_of, reason="x", record="y", today=TODAY)
        api.not_applicable(data, rid, "p.1", OWNER, roles_of=roles_of, reason="x", record="y", item="a", today=TODAY)
        api.not_applicable(data, rid, "p.1", OWNER, roles_of=roles_of, reason="x", record="y", item="b", today=TODAY)
        run = store.open_run(data, rid)
        v = fold.state(list(run.events), wf, TODAY, {}, run_id=rid)
        assert v.state is RunState.DONE and v.step("p.1").na is True
    finally:
        definitions.reset()


def test_a_gate_is_asked_about_a_not_applicable_record_as_about_a_skip(data, flow):
    rid = new_run(data)
    asked: list[StepAsk] = []

    def refusing(ask):
        asked.append(ask)
        return GateVerdict(("because a gate says so",))

    n = store.open_run(data, rid).n
    with pytest.raises(StepRefused, match="because a gate says so"):
        api.not_applicable(data, rid, "v2.1", OWNER, roles_of=roles_of, reason="x", record="y", today=TODAY, gates=refusing)
    with pytest.raises(StepRefused, match="because a gate says so"):
        api.skip(data, rid, "v2.1", OWNER, roles_of=roles_of, reason="x", today=TODAY, gates=refusing)
    assert store.open_run(data, rid).n == n
    assert [(a.act, a.step, a.role, a.step_roles, a.roles) for a in asked] == [
        ("na", "v2.1", "manager", ("manager", "treasurer"), ("manager",)),
        ("skip", "v2.1", "manager", ("manager", "treasurer"), ("manager",))]
    assert "y" in asked[0].texts and "x" in asked[0].texts

    def two_people(ask):
        return GateVerdict(("a different person confirms",) if ask.first_by and ask.first_by == ask.by else (), True)

    first = api.not_applicable(data, rid, "v2.1", OWNER, roles_of=roles_of, reason="x", record="y", today=TODAY, gates=two_people)
    assert first["event"]["kind"] == "note" and first["event"]["detail"]["first_of_two"] == "na"
    assert first["event"]["detail"]["text"] == "recorded as not applicable as the first of two; a second, different person confirms"
    assert view(data, rid).state_of("v2.1") is S.NEEDS_PERSON and api.pending_first(store.open_run(data, rid).events, "v2.1", "na") == OWNER
    with pytest.raises(StepRefused, match="different person"):
        api.not_applicable(data, rid, "v2.1", OWNER, roles_of=roles_of, reason="x", record="y", today=TODAY, gates=two_people)
    second = api.not_applicable(data, rid, "v2.1", TREASURER, roles_of=roles_of, reason="x", record="y", today=TODAY, gates=two_people)
    assert second["event"]["kind"] == "not-applicable" and second["event"]["detail"]["confirms"] == OWNER
    assert api.pending_first(store.open_run(data, rid).events, "v2.1", "na") == ""


# --- (2) the controls' gates ----------------------------------------------------------------------------------------------------

def test_the_step_gates_count_every_role_of_a_step_when_a_second_person_is_asked():
    from controls_support import adopted, roster
    from jason.community.base import OfficerRole as R
    from jason.controls import effective
    from jason.controls.types import Scope, ScopeKind

    two = adopted("second-person-confirmation", {"required": True}, scope=Scope(ScopeKind.KIND, "v2.1"), key="two")
    one = roster(R.MANAGER, R.SECRETARY)
    alone = effective.step_gates(V2, "v2.1", "manager", controls=[two], roster=one, today=date(2099, 12, 1))
    assert alone.refusals[0].endswith("the roster lacks a second manager")
    both = effective.step_gates(V2, "v2.1", "manager", controls=[two], roster=roster(R.MANAGER, R.TREASURER), today=date(2099, 12, 1),
                                step_roles=("manager", "treasurer"))
    assert both.refusals == ()
    still = effective.step_gates(V2, "v2.1", "manager", controls=[two], roster=one, today=date(2099, 12, 1),
                                 step_roles=("manager", "treasurer"))
    assert still.refusals[0].endswith("the roster lacks a second manager or treasurer")
    # the run page's rows take the roles as a third item, and the two-item form still works
    from jason.controls import view as cview

    assert cview.step_controls.__doc__ and "every role that may act" in cview.step_controls.__doc__


def test_an_adopted_control_binds_a_not_applicable_record_as_it_binds_a_skip(seated, flow_in):
    from jason.controls.types import Scope, ScopeKind
    from jason.tasks import decisions

    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, Scope(ScopeKind.KIND, "v2.1"))
    rid = api.start(seated, V2, SUBJECT, "V2", START, GMANAGER, yes=True, today=GTODAY, at=AT)["run"]["id"]
    api.open_run(seated, rid, GMANAGER, readers=FakeReaders(), yes=True, today=GTODAY)
    with pytest.raises(StepRefused, match="resolution on record"):
        api.not_applicable(seated, rid, "v2.1", GMANAGER, roles_of=groles_of, reason="x", record="no id here", today=GTODAY)
    with pytest.raises(StepRefused, match="resolution on record"):
        api.skip(seated, rid, "v2.1", GMANAGER, roles_of=groles_of, reason="x", today=GTODAY)
    d = decisions.record(seated, "2099-09-01", "The example", "Approve the example", outcome="approved")
    out = api.not_applicable(seated, rid, "v2.1", GMANAGER, roles_of=groles_of, reason="x", record=f"see {d.id}", today=GTODAY)
    assert out["event"]["kind"] == "not-applicable"


# --- (3) a date set after the start ---------------------------------------------------------------------------------------------

def test_validate_refuses_a_slot_twice_and_a_bad_timing_or_roles():
    wf = Workflow("w", "W", "f", "unit", steps=(StepDef("w.1", "Do it", StepKind.PERSON),),
                  dates=(DateSlot("a"), DateSlot("a"), DateSlot("b", timing="past"), DateSlot("c", roles=("manager",))))
    assert sorted(p.code for p in definitions.validate(wf)) == ["date", "date", "date"]


def test_a_late_slot_is_not_asked_at_the_start_but_a_fixed_one_still_is(data, flow):
    assert flow.check_dates(START) == []
    assert flow.check_dates({"answers_by": "2099-10-23"}) == ["date fixed_on is required"]
    rid = new_run(data)
    v = view(data, rid)
    assert [c.status for c in v.clocks if c.key == "v2.3"] == ["undated"]
    by_name = {d.name: d for d in v.date_slots}
    assert [n for n, d in by_name.items() if d.settable] == ["reply_on", "recorded_on", "visit_on", "closes_on"]
    assert by_name["fixed_on"].settable is False and by_name["answers_by"].settable is False
    shown = api.show(data, rid, today=TODAY)
    assert shown["openSlots"] == ["reply_on", "recorded_on", "visit_on", "closes_on"]
    assert {d["name"]: d["value"] for d in shown["dateSlots"]}["fixed_on"] == "2099-09-01"


def test_a_late_date_is_set_once_with_a_record_and_the_clocks_follow(data, flow):
    rid = new_run(data)
    with pytest.raises(StepRefused, match="needs the record"):
        api.set_date(data, rid, "recorded_on", "2099-09-10", OWNER, roles_of=roles_of, today=TODAY)
    out = api.set_date(data, rid, "recorded_on", "2099-09-10", OWNER, roles_of=roles_of, record="recorder:2099-123456",
                       today=TODAY, at="2099-09-16T10:00:00Z")
    assert out["event"]["kind"] == "date-set" and "step" not in out["event"]               # a date belongs to the run, not a step
    assert out["event"]["detail"] == {"slot": "recorded_on", "day": "2099-09-10", "record": "recorder:2099-123456"}
    assert out["run"]["dates"]["recorded_on"] == "2099-09-10"
    clock = [c for c in out["run"]["clocks"] if c["key"] == "v2.3"][0]
    assert clock["due"] == "2099-10-10" and clock["basis"] == "provider" and clock["status"] == "upcoming"
    slot = {d["name"]: d for d in out["run"]["dateSlots"]}["recorded_on"]
    assert slot["value"] == "2099-09-10" and slot["setBy"] == OWNER and slot["record"] == "recorder:2099-123456" and slot["sets"] == 1
    assert slot["correction"] is True and "recorded_on" in out["run"]["openSlots"]
    # the earlier view, from the earlier prefix, is untouched: the fold is pure
    run = store.open_run(data, rid)
    earlier = fold.state(list(run.events)[:-1], flow, TODAY, {})
    assert "recorded_on" not in earlier.dates and [c.status for c in earlier.clocks if c.key == "v2.3"] == ["undated"]


def test_a_second_set_is_a_correction_that_needs_a_reason_and_the_latest_wins(data, flow):
    rid = new_run(data)
    api.set_date(data, rid, "recorded_on", "2099-09-10", OWNER, roles_of=roles_of, record="recorder:1", today=TODAY)
    with pytest.raises(StepRefused, match="already 2099-09-10: correcting it needs a reason"):
        api.set_date(data, rid, "recorded_on", "2099-09-12", OWNER, roles_of=roles_of, record="recorder:2", today=TODAY)
    out = api.set_date(data, rid, "recorded_on", "2099-09-12", OWNER, roles_of=roles_of, record="recorder:2",
                       reason="the first was the day it was filed, not recorded", today=TODAY)
    assert out["event"]["detail"]["was"] == "2099-09-10" and out["run"]["dates"]["recorded_on"] == "2099-09-12"
    assert [c for c in out["run"]["clocks"] if c["key"] == "v2.3"][0]["due"] == "2099-10-12"
    assert kinds(data, rid).count(EventKind.DATE_SET) == 2                       # append-only: both stay
    assert {d["name"]: d for d in out["run"]["dateSlots"]}["recorded_on"]["sets"] == 2
    # an optional slot given at the start is corrected the same way
    rid2 = new_run(data, dates={**START, "reply_on": "2099-09-30"}, subject="campaign:V2-2100")
    with pytest.raises(StepRefused, match="correcting it needs a reason"):
        api.set_date(data, rid2, "reply_on", "2099-10-01", OWNER, roles_of=roles_of, record="mail:1", today=TODAY)
    assert api.set_date(data, rid2, "reply_on", "2099-10-01", OWNER, roles_of=roles_of, record="mail:1", reason="it moved",
                        today=TODAY)["run"]["dates"]["reply_on"] == "2099-10-01"


def test_a_date_set_is_refused_for_an_undeclared_fixed_malformed_or_out_of_rule_slot(data, flow):
    rid = new_run(data)

    def refuse(slot, day, match, by=OWNER):
        with pytest.raises(StepRefused, match=match):
            api.set_date(data, rid, slot, day, by, roles_of=roles_of, record="r", today=TODAY)

    refuse("nope", "2099-09-10", "no date slot nope")
    refuse("fixed_on", "2099-09-02", "fixed when the run starts")
    refuse("answers_by", "2099-10-30", "fixed when the run starts")
    refuse("recorded_on", "10/09/2099", "not YYYY-MM-DD")
    refuse("recorded_on", "2099-09-21", "in the future; this slot takes a day that has come")      # the past rule
    refuse("visit_on", "2099-09-19", "in the past; this slot takes a day that has not come", by=SECRETARY)  # the future rule
    refuse("visit_on", "2099-10-01", "may not set date visit_on: only secretary")                   # the slot names its roles
    api.set_date(data, rid, "reply_on", "2099-12-31", OWNER, roles_of=roles_of, record="r", today=TODAY)   # no rule: any day
    api.set_date(data, rid, "reply_on", "2000-01-01", OWNER, roles_of=roles_of, record="r", reason="typo", today=TODAY)
    # order with the slot it comes after, and the slots that come after it
    api.set_date(data, rid, "visit_on", "2099-10-01", SECRETARY, roles_of=roles_of, record="r", today=TODAY)
    refuse("closes_on", "2099-09-30", "comes before visit_on")
    api.set_date(data, rid, "closes_on", "2099-10-05", OWNER, roles_of=roles_of, record="r", today=TODAY)
    with pytest.raises(StepRefused, match="would come before visit_on"):
        api.set_date(data, rid, "visit_on", "2099-10-09", SECRETARY, roles_of=roles_of, record="r", reason="moved", today=TODAY)
    with pytest.raises(StepRefused, match="engine's own name"):
        api.set_date(data, rid, "recorded_on", "2099-09-10", "scheduler", record="r", today=TODAY)


def test_a_date_is_not_set_on_a_finished_run(data, flow):
    rid = new_run(data)
    api.cancel(data, rid, OWNER, roles_of=roles_of, reason="no longer needed", yes=True, today=TODAY)
    with pytest.raises(StepRefused, match="the run is cancelled"):
        api.set_date(data, rid, "recorded_on", "2099-09-10", OWNER, roles_of=roles_of, record="r", today=TODAY)
    assert view(data, rid).date_slots and not any(d.settable for d in view(data, rid).date_slots)


def test_a_date_set_for_a_slot_the_definition_lacks_is_ignored_by_the_fold(data, flow):
    rid = new_run(data)
    store.append(data, V2, rid, EventKind.DATE_SET, by=OWNER, detail={"slot": "ghost", "day": "2099-01-01", "record": "r"})
    store.append(data, V2, rid, EventKind.DATE_SET, by=OWNER, detail={"slot": "recorded_on", "day": "not a day", "record": "r"})
    assert "ghost" not in view(data, rid).dates and "recorded_on" not in view(data, rid).dates


def test_a_date_set_can_make_a_law_clock_past(data, flow):
    law = Workflow("late-law", "Late law", "f", "unit", steps=(
        StepDef("l.1", "Answer", StepKind.PERSON, role=Role.MANAGER, clock=ClockDef(ClockBasis.LAW, "served_on", 30, cite="EX 9.9")),),
        dates=(DateSlot("served_on", late=True, timing=DateTiming.PAST),))
    definitions.register(law)
    rid = api.start(data, "late-law", "unit:1", "Late", {}, OWNER, yes=True, today=TODAY, at=AT)["run"]["id"]
    api.open_run(data, rid, OWNER, yes=True, today=TODAY)
    assert api.show(data, rid, today=date(2099, 12, 1))["pastLaw"] == []         # undated: no clock yet
    api.set_date(data, rid, "served_on", "2099-09-01", OWNER, roles_of=roles_of, record="proof of service", today=TODAY)
    assert api.show(data, rid, today=date(2099, 12, 1))["pastLaw"] == ["l.1"]


# --- (4) a step that waits on its child runs ------------------------------------------------------------------------------------

def test_waits_on_child_needs_a_spawn():
    wf = Workflow("w", "W", "f", "unit", steps=(StepDef("w.1", "Do it", StepKind.PERSON, waits_on_child=True),))
    assert [p.code for p in definitions.validate(wf)] == ["waits"]
    assert definitions.validate(replace(wf, steps=(replace(wf.steps[0], spawns="x"),)), workflows={"x"}) == []


def test_a_step_that_waits_has_several_children_and_is_done_only_when_all_are_finished(data, flow):
    rid = new_run(data)
    api.spawned(data, rid, "v2.4", OWNER, child="run-aaaaaaaaaa", today=TODAY)
    api.spawned(data, rid, "v2.4", OWNER, child="run-bbbbbbbbbb", definition="v2-child", today=TODAY)
    with pytest.raises(StepRefused, match="already recorded"):
        api.spawned(data, rid, "v2.4", OWNER, child="run-aaaaaaaaaa", today=TODAY)
    with pytest.raises(StepRefused, match="does not spawn"):
        api.spawned(data, rid, "v2.1", OWNER, child="run-cccccccccc", today=TODAY)
    with pytest.raises(StepRefused, match="spawns v2-child, not other"):
        api.spawned(data, rid, "v2.4", OWNER, child="run-cccccccccc", definition="other", today=TODAY)
    v = view(data, rid)
    assert v.children == ("run-aaaaaaaaaa", "run-bbbbbbbbbb") and v.step("v2.4").children == v.children
    assert v.state_of("v2.4") is S.WAITING
    assert v.step("v2.4").reason == "0 of 2 child runs finished; waiting on run-aaaaaaaaaa, run-bbbbbbbbbb"
    one = view(data, rid, children={"run-aaaaaaaaaa": "done", "run-bbbbbbbbbb": "running"})
    assert one.step("v2.4").reason == "1 of 2 child runs finished; waiting on run-bbbbbbbbbb" and one.state_of("v2.4") is S.WAITING
    # a person cannot attest what waits; once the children are finished, the step is the person's again
    with pytest.raises(StepRefused, match="waiting"):
        api.attest(data, rid, "v2.4", OWNER, roles_of=roles_of, today=TODAY)
    fin = FakeReaders()
    fin.children = {"run-aaaaaaaaaa": "done", "run-bbbbbbbbbb": "cancelled"}
    api.attest(data, rid, "v2.4", OWNER, roles_of=roles_of, readers=fin, today=TODAY)
    shown = api.show(data, rid, today=TODAY, readers=fin)
    step = [s for s in shown["steps"] if s["id"] == "v2.4"][0]
    assert step["state"] == "done" and step["reason"] == "all 2 child runs finished" and step["by"] == OWNER
    assert step["children"] == ["run-aaaaaaaaaa", "run-bbbbbbbbbb"]
    # a child that was not finished again (a missing reading) makes the step wait again: not done until all are
    assert api.show(data, rid, today=TODAY)["steps"][3]["state"] == "waiting"


def test_a_person_step_done_before_its_child_starts_waits_once_one_is_spawned(data, flow):
    rid = new_run(data)
    api.attest(data, rid, "v2.4", OWNER, roles_of=roles_of, today=TODAY)
    assert view(data, rid).state_of("v2.4") is S.DONE                            # no child yet: nothing to wait for
    api.spawned(data, rid, "v2.4", OWNER, child="run-aaaaaaaaaa", today=TODAY)
    assert view(data, rid).state_of("v2.4") is S.WAITING
    assert view(data, rid, children={"run-aaaaaaaaaa": "cancelled"}).step("v2.4").reason == "child run run-aaaaaaaaaa is cancelled"
    assert view(data, rid, children={"run-aaaaaaaaaa": "done"}).state_of("v2.4") is S.DONE
    # reopening keeps what the step spawned
    finished = FakeReaders()
    finished.children = {"run-aaaaaaaaaa": "done"}
    api.reopen(data, rid, "v2.4", OWNER, roles_of=roles_of, reason="redo", readers=finished, today=TODAY)
    again = view(data, rid, children={"run-aaaaaaaaaa": "done"})
    assert again.state_of("v2.4") is S.NEEDS_PERSON and again.step("v2.4").children == ("run-aaaaaaaaaa",)


def test_a_branch_that_waits_records_its_choice_then_waits(data, flow):
    rid = new_run(data)
    out = api.attest(data, rid, "v2.5", OWNER, roles_of=roles_of, choice="go", today=TODAY)
    assert [s for s in out["run"]["steps"] if s["id"] == "v2.5"][0]["state"] == "done"
    api.spawned(data, rid, "v2.5", OWNER, child="run-aaaaaaaaaa", today=TODAY)
    v = view(data, rid)
    assert v.state_of("v2.5") is S.WAITING and v.step("v2.5").choice == "go"
    assert v.state_of("v2.8") is S.SKIPPED                                       # the chosen path is already known
    assert v.state_of("v2.7") is S.NOT_STARTED                                   # but the path waits for the branch to be done
    finished = view(data, rid, children={"run-aaaaaaaaaa": "done"})
    assert finished.state_of("v2.5") is S.DONE and finished.state_of("v2.7") is S.NEEDS_PERSON


def test_a_step_without_the_flag_behaves_as_before(data, flow):
    rid = new_run(data)
    api.spawned(data, rid, "v2.6", OWNER, child="run-aaaaaaaaaa", today=TODAY)
    api.spawned(data, rid, "v2.6", OWNER, child="run-bbbbbbbbbb", today=TODAY)
    v = view(data, rid)
    assert v.state_of("v2.6") is S.WAITING and v.step("v2.6").reason == "child run run-bbbbbbbbbb is not finished"   # the last decides
    assert view(data, rid, children={"run-bbbbbbbbbb": "done"}).state_of("v2.6") is S.DONE                      # done by the child alone


# --- (5) the provider basis, and two roles --------------------------------------------------------------------------------------

def test_the_provider_basis_is_a_clock_basis_with_the_counterparty_handling():
    assert ClockBasis("provider") is ClockBasis.PROVIDER
    assert followup_basis(ClockBasis.PROVIDER) is None
    assert StepDef("w.1", "t", StepKind.PERSON, clock=ClockDef(ClockBasis.PROVIDER, "d", 0)).is_legal is False
    from jason.web.extra import work

    assert work.BASIS_WORDS["provider"] == "PROVIDER"
    assert work._basis(ClockDef(ClockBasis.PROVIDER, "d", 0)) == {"basis": "provider", "basisLabel": "PROVIDER", "legal": False,
                                                                 "proposed": False}


def test_developer_and_reviewer_are_roles_that_are_not_offices(data):
    assert Role.parse("Developer") is Role.DEVELOPER and Role.parse("reviewer") is Role.REVIEWER
    assert Role.DEVELOPER not in OFFICES and Role.REVIEWER not in OFFICES and Role.MANAGER in OFFICES
    wf = Workflow("dev", "Dev", "f", "unit", steps=(
        StepDef("d.1", "The developer delivers", StepKind.PERSON, role=Role.DEVELOPER, roles=(Role.REVIEWER,), record="the delivery"),))
    assert definitions.validate(wf) == []
    definitions.reset()
    definitions.register(wf)
    try:
        rid = api.start(data, "dev", "unit:1", "Dev", {}, OWNER, today=TODAY, at=AT)["run"]["id"]
        api.open_run(data, rid, OWNER, today=TODAY)
        with pytest.raises(StepRefused, match="does not hold a role"):
            api.attest(data, rid, "d.1", OWNER, roles_of=roles_of, record="r", today=TODAY)
        done = api.attest(data, rid, "d.1", DEVELOPER, roles_of=roles_of, record="r", today=TODAY)
        assert done["run"]["state"] == "done" and done["run"]["steps"][0]["roles"] == ["developer", "reviewer"]
    finally:
        definitions.reset()


# --- the terminal ---------------------------------------------------------------------------------------------------------------

from test_workflow_cli import ASOF, run  # noqa: E402,F401 - the parser fixture
from test_workflows_support import example  # noqa: E402,F401 - the fixture ``run`` asks for


def cli_start(run):
    dates = [x for k, v in START.items() for x in ("--date", f"{k}={v}")]
    code, out, err = run("--start", V2, "--subject", SUBJECT, "--label", "V2", *dates, "--by", OWNER, "--yes", "--json", *ASOF)
    assert code == 0, err
    rid = json.loads(out)["run"]["id"]
    code, out, err = run("--open", rid, "--by", OWNER, "--yes", *ASOF)
    assert code == 0, err
    return rid


def test_the_terminal_records_a_step_as_not_applicable(run, flow):
    rid = cli_start(run)
    code, out, err = run("--na", rid, "v2.1", "--reason", "nothing to report", "--record", "minutes:2099-09-12#4", "--by", TREASURER, *ASOF)
    assert code == 0, err
    assert "not-applicable v2.1 by T. Treasurer" in out and "reason=nothing to report" in out
    code, out, err = run("--show", rid, *ASOF)
    assert code == 0 and "(not applicable)" in out and "manager/treasurer" in out
    code, out, err = run("--na", rid, "v2.4", "--reason", "x", "--record", "y", "--by", OWNER, *ASOF)
    assert code == 2 and "gives no not-applicable outcome" in err
    code, out, err = run("--na", rid, "v2.2", "--reason", "x", "--by", OWNER, *ASOF)
    assert code == 2 and "needs the record" in err
    code, out, err = run("--na", rid, "v2.2", "--reason", "x", "--record", "y", *ASOF)
    assert code == 2 and "needs --by" in err


def test_the_terminal_sets_a_date_after_the_start(run, flow):
    rid = cli_start(run)
    code, out, err = run("--set-date", rid, "recorded_on=2099-09-10", "--record", "recorder:2099-1", "--by", OWNER, *ASOF)
    assert code == 0, err
    assert "date-set" in out and "slot=recorded_on" in out and "day=2099-09-10" in out
    code, out, err = run("--show", rid, *ASOF)
    assert "recorded_on 2099-09-10" in out and "dates a person may set (--set-date)" in out
    assert "recorded_on (now 2099-09-10; a correction needs a reason)" in out
    code, out, err = run("--set-date", rid, "recorded_on=2099-09-11", "--record", "r", "--by", OWNER, *ASOF)
    assert code == 2 and "correcting it needs a reason" in err
    code, out, err = run("--set-date", rid, "recorded_on=2099-09-11", "--record", "r", "--reason", "typo", "--by", OWNER, *ASOF)
    assert code == 0, err
    code, out, err = run("--set-date", rid, "fixed_on=2099-09-02", "--record", "r", "--by", OWNER, *ASOF)
    assert code == 2 and "fixed when the run starts" in err
    code, out, err = run("--set-date", rid, "recorded_on", "--record", "r", "--by", OWNER, *ASOF)
    assert code == 2 and "SLOT=YYYY-MM-DD" in err
    code, out, err = run("--set-date", rid, "recorded_on=2099-09-10", "--record", "r", *ASOF)
    assert code == 2 and "needs --by" in err
    code, out, err = run("--na", rid, "v2.1", "--set-date", rid, "x=2099-01-01", "--by", OWNER)
    assert code == 2 and "one act at a time" in err


# --- the web layer --------------------------------------------------------------------------------------------------------------

from test_web_work import app, as_, page, post, world  # noqa: E402,F401 - fixtures

SIGNERS = ("A Manager", "Pat Example", "Sam Secretary")


def web_run(world_root):
    definitions.register(v2())
    rid = api.start(world_root, V2, SUBJECT, "V2", START, "A Manager", yes=True, today=TODAY, at=AT)["run"]["id"]
    api.open_run(world_root, rid, "A Manager", readers=FakeReaders(), yes=True, today=TODAY)
    return rid


def test_the_run_page_lists_the_roles_the_na_outcome_and_the_dates_open_to_set(app, world):
    rid = web_run(world)
    body = page(app, "A Manager", rid, V2)
    run_ = body["run"]
    assert run_["openSlots"] == ["reply_on", "recorded_on", "visit_on", "closes_on"]
    slots = {d["name"]: d for d in run_["dateSlots"]}
    assert slots["recorded_on"]["late"] is True and slots["recorded_on"]["timing"] == "past" and slots["recorded_on"]["value"] is None
    assert slots["visit_on"]["roles"] == ["secretary"] and slots["fixed_on"]["settable"] is False
    assert run_["acts"]["setDate"]["offered"] is True and run_["acts"]["setDate"]["slots"] == ["reply_on", "recorded_on", "closes_on"]
    secretary = page(app, "Sam Secretary", rid, V2)["run"]["acts"]["setDate"]["slots"]
    assert secretary == ["reply_on", "recorded_on", "visit_on", "closes_on"] or "visit_on" in secretary
    steps = {s["id"]: s for s in body["steps"]}
    assert steps["v2.1"]["roles"] == ["manager", "treasurer"] and steps["v2.1"]["role"] == "manager"
    assert steps["v2.1"]["naOutcome"] == {"roles": ["manager", "treasurer"], "reasonRequired": True, "recordRequired": True}
    assert steps["v2.2"]["naOutcome"]["roles"] == ["secretary", "manager"] and steps["v2.2"]["skip"] is None
    assert "na" in steps["v2.1"]["acts"] and steps["v2.4"].get("naOutcome") is None and "na" not in steps["v2.4"]["notOffered"]
    assert steps["v2.4"]["waitsOnChild"] is True and steps["v2.6"]["waitsOnChild"] is False
    treasurer = {s["id"]: s for s in page(app, "Pat Example", rid, V2)["steps"]}
    assert "attest" in treasurer["v2.1"]["acts"] and treasurer["v2.1"]["yours"] is True
    assert "Only the secretary, the manager may record this step as not applicable." in treasurer["v2.2"]["notOffered"]["na"]
    d = as_(app, "A Manager").get(f"/api/work-definitions?key={V2}").json["definition"]
    assert d["steps"][0]["roles"] == ["manager", "treasurer"] and d["steps"][1]["naOutcome"]["roles"] == ["secretary", "manager"]
    assert {x["name"]: x["late"] for x in d["dates"]}["recorded_on"] is True


def test_the_writer_records_na_and_a_date_in_the_signers_own_name(app, world):
    rid = web_run(world)
    c = as_(app, "A Manager")
    r = post(c, f"{V2}/{rid}", {"act": "attest", "step": "v2.1", "record": "the report"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    r = post(as_(app, "Pat Example"), f"{V2}/{rid}", {"act": "na", "step": "v2.2", "reason": "x", "record": "y"})
    assert r.status_code == 403 and "may not record v2.2 as not applicable" in r.json["error"]
    r = post(as_(app, "Sam Secretary"), f"{V2}/{rid}", {"act": "na", "step": "v2.2", "reason": "no answer is owed", "record": "minutes:1"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.json["event"]["kind"] == "not-applicable"
    assert r.json["event"]["text"] == "Step 2, The legal step that may not apply recorded as not applicable by Sam Secretary: no answer is owed (minutes:1)"
    step = {s["id"]: s for s in r.json["run"]["steps"]}["v2.2"]
    assert step["state"] == "done" and step["na"] is True and step["reason"].startswith("recorded as not applicable by Sam Secretary")
    r = post(c, f"{V2}/{rid}", {"act": "na", "step": "v2.2", "reason": "x", "record": "y"})
    assert r.status_code == 400 and "already done" in r.json["error"]
    r = post(c, f"{V2}/{rid}", {"act": "set-date", "slot": "visit_on", "day": "2099-10-01", "record": "r"})
    assert r.status_code == 403 and "may not set date visit_on" in r.json["error"]
    r = post(c, f"{V2}/{rid}", {"act": "set-date", "slot": "recorded_on", "day": "2099-09-10"})
    assert r.status_code == 400 and "needs the record" in r.json["error"]
    r = post(c, f"{V2}/{rid}", {"act": "set-date", "slot": "recorded_on", "day": "2099-09-30", "record": "r"})
    assert r.status_code == 400 and "in the future" in r.json["error"]
    r = post(c, f"{V2}/{rid}", {"act": "set-date", "slot": "recorded_on", "day": "2099-09-10", "record": "recorder:1"})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.json["event"]["text"] == "A Manager set date recorded_on to 2099-09-10 (recorder:1)"
    assert r.json["run"]["run"]["dates"]["recorded_on"] == "2099-09-10"
    r = post(c, f"{V2}/{rid}", {"act": "set-date", "slot": "recorded_on", "day": "2099-09-11", "record": "recorder:2", "reason": "typo"})
    assert r.status_code == 200
    assert r.json["event"]["text"] == "A Manager set date recorded_on to 2099-09-11, correcting 2099-09-10: typo (recorder:2)"
    r = post(c, f"{V2}/{rid}", {"act": "set-date", "day": "2099-09-10", "record": "r"})
    assert r.status_code == 400 and "slot is required" in r.json["error"]
    r = post(c, f"{V2}/{rid}", {"act": "teleport"})
    assert r.status_code == 400 and "na, set-date" in r.json["error"]
    history = [h["text"] for h in page(app, "A Manager", rid, V2)["history"]]
    assert any("recorded as not applicable by Sam Secretary" in t for t in history)


# --- the real controls, in the world of test_controls_step_gates -------------------------------------------------------------------

from test_controls_step_gates import MANAGER as GMANAGER, adopt, roles_of as groles_of, seated  # noqa: E402,F401
from test_web_work import TODAY as GTODAY  # noqa: E402


@pytest.fixture
def flow_in(seated):
    definitions.register(v2())
    yield


def test_the_run_page_shows_the_controls_on_a_step_that_can_be_recorded_not_applicable(seated, flow_in):
    from jason.controls.types import Scope, ScopeKind
    from jason.workflows.types import Workflow  # noqa: F401
    from jason.web.extra import work

    adopt(seated, "res", "contract-authorization", {"resolution_first": True}, Scope(ScopeKind.KIND, "v2.2"))
    rid = api.start(seated, V2, SUBJECT, "V2", START, GMANAGER, yes=True, today=GTODAY, at=AT)["run"]["id"]
    api.open_run(seated, rid, GMANAGER, readers=FakeReaders(), yes=True, today=GTODAY)
    body = work.compose_run(seated, V2, rid, work.Who(GMANAGER, frozenset({"manager"})), GTODAY, readers=FakeReaders())
    rows = {s["id"]: s.get("controls") for s in body["steps"]}
    assert rows["v2.2"] and rows["v2.2"][0]["gate"] == "resolution"             # v2.2 has no skip rule: only its na outcome reaches the gate
    assert rows["v2.1"] is None
