"""The guidance record on a person step (``Support``: enables, reminds, guides), its validators, the pure nudge bands, the claim note,
the composed guide / enable / nudge, and the six worked examples (docs/workflows/person-steps.md, sections 4 to 7).

Made-up definitions ("example-cycle"), people, and dates (2099) in a tmp data folder; nothing reaches Google, Keeper, or PayHOA.
(``tests/test_workflows_support.py`` is the shared fakes module of the engine tests; this file is the record's own.)
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from test_workflows_support import (
    C1, C2, C3, C4, C5, C6, DATES, FakeReaders, OWNER, SECRETARY, TREASURER, data, example, example_cycle, roles_of,
)

from jason.tasks import step_guide
from jason.workflows import api, definitions, guide, guide_reads, nudge, store
from jason.workflows.types import (
    Check, Cite, ClockBasis, ClockDef, Cmd, Enables, Guides, LookAt, Reminds, Repeat, Role, StepKind, Support, Visibility, Workflow,
)

TODAY = date(2099, 9, 20)
OPENED = "2099-09-20T09:00:00Z"
LEGAL_CLOCK = ClockDef(ClockBasis.LAW, "answers_by", 0, cite="EX 123.4")
KW = dict(plan_kinds={"example-plan"}, jobs={"example-report"})


def with_support(step_id: str, support: Support | None, **over) -> Workflow:
    base = example_cycle()
    steps = tuple(replace(s, support=support, **over) if s.id == step_id else s for s in base.steps)
    return example_cycle(steps=steps)


def problems(wf: Workflow, **registries) -> list[str]:
    return [f"{p.code}: {p.message}" for p in definitions.validate(wf, **KW, **registries)]


def has(found: list[str], needle: str) -> bool:
    return any(needle in line for line in found)


# --- the record, and a step with none -------------------------------------------------------------------------------------------

def test_a_step_with_no_support_is_as_it_was():
    wf = example_cycle()
    assert all(s.support is None for s in wf.steps)
    assert problems(wf) == []
    assert Support() == Support(Enables(), Reminds(), Guides())              # every part has an empty default
    assert guide.authored(wf.step(C2)) == () and guide.coverage_words(wf.step(C2)) == "derived"


def test_a_claim_is_a_note_and_leaves_the_fold_alone(data, example):
    """No event-format change: the note carries ``claim`` like supply carries ``items_supplied``, and the run folds as it did."""
    rid = api.start(data, "example-cycle", "campaign:EX-2099", "Example cycle 2099", DATES, OWNER, yes=True, today=TODAY)["run"]["id"]
    api.open_run(data, rid, OWNER, readers=FakeReaders(), yes=True, today=TODAY)
    before = api.show(data, rid, today=TODAY, readers=FakeReaders())
    out = api.claim(data, rid, C2, OWNER, roles_of=roles_of, readers=FakeReaders(), today=TODAY)
    event = out["event"]
    assert event["kind"] == "note" and event["step"] == C2 and event["detail"]["claim"] is True and event["by"] == OWNER
    after = api.show(data, rid, today=TODAY, readers=FakeReaders())
    assert [(s["id"], s["state"], s["reason"]) for s in after["steps"]] == [(s["id"], s["state"], s["reason"]) for s in before["steps"]]
    assert after["n"] == before["n"] + 1 and after["state"] == before["state"]
    assert api.verify(data, rid)["ok"]


# --- the validators -------------------------------------------------------------------------------------------------------------

BAD = [
    ("a check step has no person to guide", C1, Support(guides=Guides(instruction="Look.")), "no person to guide"),
    ("a section number in the words", C2, Support(guides=Guides(instruction="Send it as CIV 4920 says.")), "section number"),
    ("an address", C2, Support(guides=Guides(instruction="Write to a.owner@example.org.")), "an address or handle"),
    ("a link", C2, Support(guides=Guides(instruction="Open https://example.org/form.")), "a link"),
    ("an amount", C2, Support(guides=Guides(instruction="Pay $40.")), "an amount"),
    ("a phone number", C2, Support(guides=Guides(blocked="Call 555-123-4567.")), "a phone number"),
    ("a placeholder that is not one of the four", C2, Support(guides=Guides(commands=(Cmd("example notice --send FILE"),))), "placeholder FILE"),
    ("a lesson that does not exist", C2, Support(guides=Guides(lessons=("no-such-lesson",))), "does not exist"),
    ("a guide read that is not registered", C2, Support(guides=Guides(look_at=(LookAt("Things", "no-such-read"),))), "not a registered guide read"),
    ("a cite that is neither", C2, Support(guides=Guides(cites=(Cite("the statute"),))), "neither a shelf key"),
    ("an ask that is not an office", C2, Support(guides=Guides(ask=(Role.ANYONE,))), "ask names an office"),
    ("an escalate_to that is not an office", C2, Support(reminds=Reminds(escalate_to=Role.JASON)), "escalate_to is an office"),
    ("a lead below its floor", C2, Support(reminds=Reminds(lead_days=-1)), "lead_days is a whole number"),
    ("a per-item reminder on a step that does not repeat", C2, Support(reminds=Reminds(per_item=True)), "per_item is for a step"),
    ("a required item with nothing to point to", C6, Support(guides=Guides(checklist=(Check("Looked", required=True),))), None),
    ("too many checklist items", C2, Support(guides=Guides(checklist=tuple(Check(f"Item {i}") for i in range(9)))), "at most 8 checklist"),
    ("too many look-at reads", C2, Support(guides=Guides(look_at=tuple(LookAt(f"Thing {i}", "responses-new") for i in range(4)))), "at most 3 look-at"),
    ("an integration jason does not know", C2, Support(enables=Enables(integrations=("nowhere",))), "not one jason knows"),
]


@pytest.mark.parametrize("what, step_id, support, needle", BAD, ids=[b[0] for b in BAD])
def test_the_validator_refuses(what, step_id, support, needle):
    wf = with_support(step_id, support)
    if what.startswith("a required item"):
        wf = with_support(step_id, support, record="")
        needle = "needs a record or a done_when"
    found = problems(wf, reads=guide_reads.names(), lessons={"real-lesson"}, integrations={"payhoa"})
    assert has(found, needle), (what, found)


def test_a_legal_step_is_never_snoozable_and_escalates_the_day_it_falls():
    base = replace(example_cycle().step(C2), clock=LEGAL_CLOCK, legal=True, skip=None)
    wf = example_cycle(steps=tuple(base if s.id == C2 else s for s in example_cycle().steps))
    assert problems(wf) == []

    def bad(reminds):
        steps = tuple(replace(base, support=Support(reminds=reminds)) if s.id == C2 else s for s in example_cycle().steps)
        return problems(example_cycle(steps=steps))

    assert has(bad(Reminds(snoozable=True)), "never snoozable")
    assert has(bad(Reminds(escalate_after_hours=24)), "escalates the day it falls")
    assert bad(Reminds(snoozable=False, escalate_after_hours=0, lead_days=30)) == []


def test_a_cite_the_shelf_cannot_resolve_fails_validate_and_a_missing_shelf_is_a_skip():
    wf = with_support(C2, Support(guides=Guides(cites=(Cite("EX 999.9", reading="A reading."),))))
    assert has(problems(wf, resolve_law=lambda cite: False), "does not resolve on the authorities shelf")
    assert problems(wf, resolve_law=lambda cite: None) == []
    assert problems(wf) == []


def test_held_guidance_carries_no_address_and_a_public_title_no_digit():
    base = example_cycle()
    held = example_cycle(key="example-held", visibility=Visibility.HELD, held_title="A member's matter", steps=tuple(
        replace(s, public_title=(s.id == C2), support=Support(guides=Guides(instruction="Send notice 2 today.", blocked="Ask a@b.")) if s.id == C2 else None)
        for s in base.steps))
    found = problems(held)
    assert has(found, "carries a digit") and has(found, "an address or handle")


def test_from_mapping_turns_words_into_symbols_and_refuses_an_unknown_field():
    got = guide.from_mapping({"guides": {"instruction": "Do it.", "ask": ["manager", "president"], "checklist": [{"text": "A", "required": True}],
                                          "cites": [{"key": "CIV 9999(a)", "reading": "A reading."}], "look_at": [{"label": "L", "read": "responses-new"}]},
                              "reminds": {"escalate_to": "president", "lead_days": 3}, "enables": {"second_person": True}})
    assert got.guides.ask == (Role.MANAGER, Role.PRESIDENT) and got.reminds.escalate_to is Role.PRESIDENT and got.enables.second_person is True
    assert got.guides.checklist[0] == Check("A", True) and got.guides.look_at[0].read == "responses-new"
    for bad, word in (({"guides": {"bogus": 1}}, "bogus"), ({"bogus": {}}, "bogus"), ({"reminds": {"lead": 1}}, "lead"),
                      ({"guides": {"ask": ["wizard"]}}, "not a role"), ({"guides": {"checklist": [{"text": "A", "color": 1}]}}, "color")):
        with pytest.raises(ValueError, match=word):
            guide.from_mapping(bad)


# --- fill and derive ------------------------------------------------------------------------------------------------------------

def test_a_command_is_filled_from_the_name_and_the_run_and_the_rest_is_marked():
    text, left = guide.fill_command("jason responses --read ID --by NAME", name="A. Manager", run="run-1")
    assert text == 'jason responses --read ID --by "A. Manager"' and left == ["ID"]
    text, left = guide.fill_command("jason workflow --show RUN --by NAME", name="Ann", run="run-9")
    assert text == "jason workflow --show run-9 --by Ann" and left == []
    assert guide.fill_command("jason sop KEY", name="Ann")[1] == ["KEY"]                # KEY and ID are always the person's
    assert guide.placeholders("jason notice --send --yes") == []


def test_every_part_falls_back_to_what_the_step_already_holds():
    class Proc:
        steps = (type("S", (), {"do": "Do the thing well.", "check": "Look at the thing first.", "lessons": ("a-lesson",)})(),)

    sd = replace(example_cycle().step(C2), sop="example-procedure#1")
    spec = guide.spec(sd, Proc())
    assert spec.instruction == "Do the thing well." and spec.checklist == (Check("Look at the thing first."),) and spec.lessons == ("a-lesson",)
    assert spec.commands == (Cmd("example notice --send"),) and spec.done_when == "Done when you can point to: the sent-notice reference."
    assert spec.evidence == ("store:notices",) and spec.ask == (Role.MANAGER, Role.PRESIDENT)   # the step's own roles, then the escalation office
    bare = guide.spec(example_cycle().step(C2))
    assert bare.instruction == "Send the example notice to 123 Main St" and bare.checklist == ()                      # the title, no procedure
    assert bare.not_applicable == "This step has no not-applicable outcome; it may be skipped with a reason."
    legal = guide.spec(replace(example_cycle().step(C5), kind=StepKind.PERSON))
    assert legal.cites == (Cite("EX 123.4"),) and legal.not_applicable == guide.NOT_APPLICABLE_NONE         # a law clock's cite
    assert guide.authored(replace(sd, support=Support(guides=Guides(instruction="x", checklist=(Check("y"),))))) == ("instruction", "checklist")


# --- the nudge: pure ------------------------------------------------------------------------------------------------------------

def legal_def() -> Workflow:
    base = example_cycle()
    c2 = replace(base.step(C2), clock=LEGAL_CLOCK, legal=True, skip=None)
    return example_cycle(steps=tuple(c2 if s.id == C2 else s for s in base.steps))


def run_of(data, wf, *, open_=True):
    definitions.reset()
    definitions.register(wf, **KW)
    rid = api.start(data, wf.key, "campaign:EX-2099", "Example cycle 2099", DATES, OWNER, yes=True, today=TODAY, at=OPENED)["run"]["id"]
    if open_:
        api.open_run(data, rid, OWNER, readers=FakeReaders(), yes=True, today=TODAY, at=OPENED)
    return rid


def nudge_at(data, wf, rid, day, step_id=C2, **kw):
    events, view = step_guide.folded(data, wf, rid, day, FakeReaders())
    return nudge.step_nudge(wf, wf.step(step_id), view, day, claims=nudge.claims_of(events), **kw)


@pytest.mark.parametrize("day, band, word", [
    (date(2099, 10, 1), nudge.Band.QUIET, ""),                    # 22 days out: nothing is shown
    (date(2099, 10, 9), nudge.Band.SOON, "due soon"),            # 14 days: the proposed lead
    (date(2099, 10, 22), nudge.Band.SOON, "due soon"),
    (date(2099, 10, 23), nudge.Band.LEGAL, "LEGAL"),             # the day it falls
    (date(2099, 10, 29), nudge.Band.LEGAL, "LEGAL"),             # and past it
])
def test_a_legal_clock_is_legal_the_day_it_falls_and_never_before(data, day, band, word):
    wf = legal_def()
    n = nudge_at(data, wf, run_of(data, wf), day)
    assert (n.band, n.word) == (band, word)
    assert n.legal is (n.due != "") and (n.basis_label == "LEGAL" or not n.due)
    assert not n.snoozable
    if band is nudge.Band.LEGAL:
        assert n.escalated_to == nudge.BOARD                      # the whole board, the same day
    else:
        assert n.escalated_to == ""


def test_a_clock_that_is_not_the_laws_is_late_then_seen_by_the_escalation_office_after_the_delay(data):
    base = example_cycle()
    c2 = replace(base.step(C2), clock=ClockDef(ClockBasis.DOCUMENTS, "answers_by", 0, cite="the example document"))
    wf = example_cycle(steps=tuple(c2 if s.id == C2 else s for s in base.steps))
    rid = run_of(data, wf)
    one = nudge_at(data, wf, rid, date(2099, 10, 24))             # one day late
    assert one.band is nudge.Band.LATE and one.word == "OVERDUE" and one.days == -1 and one.escalated_to == ""
    three = nudge_at(data, wf, rid, date(2099, 10, 26))           # three days late: 72 hours, the proposed delay
    assert three.escalated_to == "president" and "proposed, not the law's" in three.escalated_why
    own = replace(c2, support=Support(reminds=Reminds(escalate_to=Role.TREASURER, escalate_after_hours=24)))
    wf2 = example_cycle(steps=tuple(own if s.id == C2 else s for s in base.steps))
    assert nudge_at(data, wf2, run_of(data, wf2), date(2099, 10, 25)).escalated_to == "treasurer"


def test_open_a_while_is_for_a_step_with_no_clock_and_the_numbers_are_proposals(data):
    wf = example_cycle()
    rid = run_of(data, wf)
    assert nudge_at(data, wf, rid, date(2099, 9, 22)).band is nudge.Band.QUIET
    stale = nudge_at(data, wf, rid, date(2099, 9, 30))
    assert stale.band is nudge.Band.STALE and stale.word == "open" and stale.after_hours == nudge.DEFAULTS.after_hours == 168
    quick = replace(wf.step(C2), support=Support(reminds=Reminds(after_hours=24)))
    wf2 = example_cycle(steps=tuple(quick if s.id == C2 else s for s in wf.steps))
    assert nudge_at(data, wf2, run_of(data, wf2), date(2099, 9, 22)).band is nudge.Band.STALE
    d = step_guide.nudge_dict(stale)
    assert d["numbers"]["note"] == "proposed, not the law's" and d["numbers"]["adopted"] is False
    assert (nudge.DEFAULTS.lead_days, nudge.DEFAULTS.after_hours, nudge.DEFAULTS.escalate_after_hours) == (14, 168, 72)


def test_nothing_is_nudged_for_a_step_not_ready_a_draft_a_pause_or_a_step_that_is_over(data):
    wf = legal_def()
    late = date(2099, 10, 29)
    draft = run_of(data, wf, open_=False)
    assert nudge_at(data, wf, draft, late).band is nudge.Band.QUIET                       # a draft: no clock runs
    api.open_run(data, draft, OWNER, readers=FakeReaders(), yes=True, today=TODAY)
    assert nudge_at(data, wf, draft, late).band is nudge.Band.LEGAL
    assert nudge_at(data, wf, draft, late, step_id=C6).band is nudge.Band.QUIET           # not ready (the decision waits on step 5)
    api.pause(data, draft, OWNER, reason="waiting", readers=FakeReaders(), today=TODAY)
    assert nudge_at(data, wf, draft, late).band is nudge.Band.QUIET
    api.resume_run(data, draft, OWNER, readers=FakeReaders(), today=TODAY)
    api.attest(data, draft, C2, OWNER, roles_of=roles_of, record="notice-1", readers=FakeReaders(), today=TODAY)
    assert nudge_at(data, wf, draft, late).band is nudge.Band.QUIET                       # done


def test_the_nudge_is_pure_and_a_prefix_of_the_events_gives_the_earlier_line(data):
    wf = legal_def()
    rid = run_of(data, wf)
    events, view = step_guide.folded(data, wf, rid, date(2099, 10, 23), FakeReaders())
    a = nudge.step_nudge(wf, wf.step(C2), view, date(2099, 10, 23))
    b = nudge.step_nudge(wf, wf.step(C2), view, date(2099, 10, 23))
    assert a == b
    from jason.workflows import fold

    run = store.read(data, wf.key, rid)
    early = fold.state(list(run.events)[:2], wf, date(2099, 10, 1), {}, run_id=rid)
    assert nudge.step_nudge(wf, wf.step(C2), early, date(2099, 10, 1)).band is nudge.Band.QUIET
    assert nudge.step_nudge(wf, wf.step(C2), view, date(2099, 10, 1)) == nudge.step_nudge(wf, wf.step(C2), view, date(2099, 10, 1))


def test_a_vacant_office_escalates_at_once_and_says_so(data):
    wf = example_cycle()
    rid = run_of(data, wf)
    n = nudge_at(data, wf, rid, date(2099, 9, 21), vacant={"manager"})
    assert n.escalated_to == "president" and n.escalated_why == "No one holds the manager office"
    assert nudge_at(data, wf, rid, date(2099, 9, 21), vacant=set()).escalated_to == ""


def test_a_per_item_step_is_one_line_with_a_count(data):
    base = example_cycle()
    c2 = replace(base.step(C2), repeat=Repeat.PER_ITEM,
                 clock=ClockDef(ClockBasis.DOCUMENTS, "answers_by", 0, cite="d", per_item=True))
    wf = example_cycle(steps=tuple(c2 if s.id == C2 else s for s in base.steps))
    definitions.reset()
    definitions.register(wf, **KW)
    rid = api.start(data, wf.key, "campaign:EX-2099", "Example cycle 2099", DATES, OWNER, items=["i-1", "i-2", "i-3"], yes=True, today=TODAY)["run"]["id"]
    api.open_run(data, rid, OWNER, readers=FakeReaders(), yes=True, today=TODAY)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="r", item="i-1", readers=FakeReaders(), today=TODAY)
    n = nudge_at(data, wf, rid, date(2099, 10, 24))
    assert n.items == {"total": 3, "notDone": 2, "earliest": "2099-10-23"} and n.band is nudge.Band.LATE
    rows = nudge.run_nudges(wf, step_guide.folded(data, wf, rid, date(2099, 10, 24), FakeReaders())[1], date(2099, 10, 24))
    assert len([1 for sd, _ in rows if sd.id == C2]) == 1


def test_an_unset_settable_date_with_a_clock_reading_it_needs_a_date_not_late(data):
    from jason.workflows.types import DateSlot

    base = example_cycle()
    c2 = replace(base.step(C2), clock=ClockDef(ClockBasis.PERSON, "review_on", 0, label="the review"))
    wf = example_cycle(steps=tuple(c2 if s.id == C2 else s for s in base.steps),
                       dates=(*base.dates, DateSlot("review_on", "Review day", required=False)))
    rid = run_of(data, wf)
    n = nudge_at(data, wf, rid, date(2099, 12, 1))
    assert n.band is nudge.Band.DATE and n.word == "needs a date" and n.due == "" and n.days is None
    api.set_date(data, rid, "review_on", "2099-12-15", OWNER, roles_of=roles_of, record="the calendar", readers=FakeReaders(), today=TODAY)
    assert nudge_at(data, wf, rid, date(2099, 12, 1)).band is nudge.Band.SOON


# --- claims ---------------------------------------------------------------------------------------------------------------------

def test_a_claim_names_who_is_on_it_changes_nothing_else_and_ends_with_the_step(data, example):
    rid = api.start(data, "example-cycle", "campaign:EX-2099", "Example cycle 2099", DATES, OWNER, yes=True, today=TODAY)["run"]["id"]
    api.open_run(data, rid, OWNER, readers=FakeReaders(), yes=True, today=TODAY)
    kw = dict(roles_of=roles_of, readers=FakeReaders(), today=TODAY)
    with pytest.raises(Exception, match="does not hold the manager role"):
        api.claim(data, rid, C2, TREASURER, **kw)                                       # a claim is for a person who may act on the step
    with pytest.raises(Exception, match="nothing to release"):
        api.claim(data, rid, C2, OWNER, release=True, **kw)
    n = api.show(data, rid, today=TODAY, readers=FakeReaders())["n"]
    dry = api.claim(data, rid, C2, OWNER, dry_run=True, **kw)
    assert dry["dryRun"] and dry["text"] == f"{OWNER} is on it" and api.show(data, rid, today=TODAY, readers=FakeReaders())["n"] == n
    api.claim(data, rid, C2, OWNER, at="2099-09-18T10:00:00Z", **kw)
    with pytest.raises(Exception, match="already on"):
        api.claim(data, rid, C2, OWNER, **kw)
    events = store.read(data, "example-cycle", rid).events
    assert nudge.claims_of(events)[C2] == nudge.Claim(OWNER, "2099-09-18T10:00:00Z")
    n = nudge_at(data, example_cycle(), rid, date(2099, 9, 21))
    assert n.claim and n.claim.by == OWNER and not n.claim_stale
    assert nudge_at(data, example_cycle(), rid, date(2099, 10, 1)).claim_stale                        # claimed, still open past the threshold
    with pytest.raises(Exception, match="only A. Manager lets it go"):
        api.claim(data, rid, C2, SECRETARY, release=True, roles_of=lambda by: ("manager",) if by == SECRETARY else (), readers=FakeReaders(), today=TODAY)
    api.claim(data, rid, C2, OWNER, release=True, **kw)
    assert C2 not in nudge.claims_of(store.read(data, "example-cycle", rid).events)
    api.claim(data, rid, C2, OWNER, **kw)
    api.attest(data, rid, C2, OWNER, record="notice-1", **kw)
    assert C2 not in nudge.claims_of(store.read(data, "example-cycle", rid).events)                  # it ends when the step ends
    with pytest.raises(Exception, match="not waiting on a person"):
        api.claim(data, rid, C2, OWNER, **kw)
    with pytest.raises(Exception, match="a claim is for a step a person does"):
        api.claim(data, rid, C4, OWNER, **kw)


# --- the composed enable states -------------------------------------------------------------------------------------------------

HOLDERS = step_guide.Holders((("manager", OWNER), ("secretary", SECRETARY), ("treasurer", TREASURER)))
MANAGER = step_guide.Person(OWNER, frozenset({"manager"}))
OTHER = step_guide.Person(TREASURER, frozenset({"treasurer"}))


def enable_for(data, wf, rid, who, step_id=C2, **kw):
    events, view = step_guide.folded(data, wf, rid, TODAY, FakeReaders())
    return step_guide.enable_dict(wf, wf.step(step_id), view.step(step_id), view, who, HOLDERS, **kw)


def test_the_enable_state_is_the_first_that_applies_in_the_orders_of_the_page(data):
    wf = example_cycle()
    rid = run_of(data, wf, open_=False)
    assert enable_for(data, wf, rid, MANAGER)["state"] == "draft"
    assert enable_for(data, wf, rid, MANAGER, acting_as="Ada Admin")["state"] == "viewing as"          # viewing as precedes the run's state
    assert enable_for(data, wf, rid, MANAGER, acting_as="Ada Admin")["word"] == "Viewing as Ada Admin (admin view): go back to yourself first."
    api.open_run(data, rid, OWNER, readers=FakeReaders(), yes=True, today=TODAY)
    ready = enable_for(data, wf, rid, MANAGER)
    assert ready["state"] == "ready" and ready["word"] == "Yours: you hold the manager office. Nothing is missing." and ready["missing"] == []
    assert [h["office"] for h in ready["holders"]] == ["manager"] and ready["holders"][0]["names"] == [OWNER]
    assert ready["holders"][0]["backup"] == {"office": "president", "names": [], "basis": "proposed, not the law's"}
    no = enable_for(data, wf, rid, OTHER)
    assert no["state"] == "not yours" and no["word"] == "Waiting on the manager." and "Only the manager can do this" in no["detail"]
    assert "You are the treasurer." in no["detail"]
    ahead = enable_for(data, wf, rid, step_guide.Person(SECRETARY, frozenset({"secretary"})), step_id=C6)
    assert ahead["state"] == "not ready" and ahead["word"] == "Waits on step 5: Wait for the Example Alarm answer."
    assert ahead["waitsOn"]["id"] == C5
    api.pause(data, rid, OWNER, reason="holiday", readers=FakeReaders(), today=TODAY)
    assert enable_for(data, wf, rid, MANAGER)["state"] == "paused"
    api.resume_run(data, rid, OWNER, readers=FakeReaders(), today=TODAY)
    api.attest(data, rid, C2, OWNER, roles_of=roles_of, record="notice-1", readers=FakeReaders(), today=TODAY)
    done = enable_for(data, wf, rid, MANAGER)
    assert done["state"] == "done" and done["word"].startswith(f"Done by {OWNER} on ")
    api.cancel(data, rid, OWNER, roles_of=lambda by: ("manager",), reason="test", yes=True, readers=FakeReaders(), today=TODAY)
    assert enable_for(data, wf, rid, MANAGER, step_id=C3)["state"] in ("closed", "done")


def test_integration_second_person_and_terminal_states_in_that_order(data):
    cmds = (Cmd("example notice --send", terminal_only=True),)
    wf = with_support(C2, Support(enables=Enables(integrations=("example",), second_person=True), guides=Guides(commands=cmds)))
    rid = run_of(data, wf)
    absent = enable_for(data, wf, rid, MANAGER, integrations={"example": "needs sign-in"}, integration_names={"example": "The Example"})
    assert absent["state"] == "needs an integration" and absent["word"] == "Needs The Example signed in."
    assert absent["missing"][0]["fix"] == "jason integrations check example --live" and "credential" not in str(absent)
    second = enable_for(data, wf, rid, MANAGER, integrations={"example": "ok"})
    assert second["state"] == "needs a second person" and second["word"] == "Needs a second person: the manager or another director."
    assert second["terminalOnly"] is True
    gated = enable_for(data, wf, rid, OTHER, step_id=C2, controls=[{"gate": "second", "state": "in force", "firstBy": OWNER}])
    assert gated["state"] == "not yours"                                                                  # not yours precedes the gates
    term = with_support(C2, Support(guides=Guides(commands=cmds)))
    assert enable_for(data, term, run_of(data, term), MANAGER)["state"] == "terminal only"
    assert enable_for(data, term, run_of(data, term), MANAGER)["word"] == "A person does this at a terminal."
    unknown = enable_for(data, wf, rid, MANAGER, integrations={})
    assert unknown["state"] == "needs a second person"                                                    # an integration nobody recorded is not a refusal


def test_an_unnamed_roster_is_unknown_not_vacant_and_an_empty_office_is_vacant(data):
    wf = example_cycle()
    rid = run_of(data, wf)
    events, view = step_guide.folded(data, wf, rid, TODAY, FakeReaders())
    empty = step_guide.Holders(())
    assert empty.vacant({"manager"}) == frozenset()
    row = step_guide.holders_of(wf.step(C2), view, step_guide.Holders((("secretary", SECRETARY),)), None)[0]
    assert row["vacant"] is True and row["names"] == []


# --- the composed guide ---------------------------------------------------------------------------------------------------------

def test_the_guide_has_every_section_in_order_and_recites_nothing_it_does_not_hold(data):
    cite = Cite("EX 123.4", reading="The answer comes in before the cycle closes.")
    wf = with_support(C2, Support(guides=Guides(
        instruction="Send it.", look_at=(LookAt("Things that arrived", "no-such-read"),), checklist=(Check("Sent", required=True),),
        commands=(Cmd("example notice --send --by NAME"),), cites=(cite,), lessons=("form-link-needs-unit",), ask=(Role.MANAGER, Role.PRESIDENT))))
    rid = run_of(data, wf)
    events, view = step_guide.folded(data, wf, rid, TODAY, FakeReaders())
    g = step_guide.guide_dict(data, wf, wf.step(C2), view, view.step(C2), day=TODAY, readers=FakeReaders(), roster=HOLDERS, who=MANAGER,
                              name=OWNER, run_id=rid)
    assert g["instruction"] == "Send it." and g["authored"] == ["instruction", "rule", "checklist", "look-at", "commands", "ask", "lessons"]
    read = g["lookAt"][0]
    assert read["unavailable"].startswith("the read 'no-such-read' is not registered") and read["count"] is None      # never "nothing to look at"
    evidence = g["lookAt"][1]
    assert evidence["kind"] == "evidence" and evidence["count"] == 1 and evidence["of"] == 1 and evidence["rows"] == ["store:notices"]
    rule = g["rule"][0]
    assert rule["missing"] == "The words of EX 123.4 are not on the shelf here." and rule["words"] == "" and rule["reading"] == cite.reading
    assert rule["command"] == "jason export-authorities" and rule["readingLabel"] == "jason's reading"
    assert g["commands"][0]["text"] == f'example notice --send --by "{OWNER}"' and g["commands"][0]["fillIn"] == []
    assert g["lessons"] == [{"key": "form-link-needs-unit", "status": "fixed"}]
    assert [a["office"] for a in g["ask"]] == ["manager", "president"] and g["ask"][0]["names"] == [OWNER]
    assert g["notApplicable"] and g["blocked"] == guide.BLOCKED_STANDING and g["doneWhen"].startswith("Done when you can point to")


def test_a_cite_on_the_shelf_is_recited_whole_with_the_caveat_and_the_read_through_held_off(data, monkeypatch):
    shelf = data / "authorities" / "EX"
    shelf.mkdir(parents=True)
    monkeypatch.setattr("jason.community.law_text.quoted", lambda cite, root, day: __import__("types").SimpleNamespace(
        citation=cite, text=__import__("types").SimpleNamespace(words="The operative words, whole.", source="the session publication", digest="abc123abc123"),
        held=(1,), several=False, note="", caveats=(), label=lambda d: ""))
    seen = []
    from jason.tasks import statute_fetch

    real = statute_fetch.enabled
    monkeypatch.setattr("jason.tasks.step_guide._read_only", lambda: (seen.append(real()), statute_fetch.disabled())[1])
    out = step_guide.recite_cite(data, Cite("EX 123.4", reading="A reading."), TODAY)
    assert out["words"] == "The operative words, whole." and out["missing"] == "" and out["version"] == "the words in force on 2099-09-20"
    assert out["restatement"].startswith("jason's consolidated text is not an official restatement") and out["reading"] == "A reading."
    assert statute_fetch.enabled() is real()                                                           # held off only inside the block


def test_the_text_of_a_guide_follows_the_panels_order(data):
    wf = with_support(C2, Support(guides=Guides(instruction="Send it.", checklist=(Check("Sent", required=True),), ask=(Role.MANAGER,))))
    rid = run_of(data, wf)
    events, view = step_guide.folded(data, wf, rid, TODAY, FakeReaders())
    g = step_guide.guide_dict(data, wf, wf.step(C2), view, view.step(C2), day=TODAY, readers=FakeReaders(), roster=HOLDERS, who=MANAGER, name=OWNER, run_id=rid)
    nd = step_guide.nudge_dict(nudge.step_nudge(wf, wf.step(C2), view, TODAY))
    en = step_guide.enable_dict(wf, wf.step(C2), view.step(C2), view, MANAGER, HOLDERS)
    text = "\n".join(step_guide.text_lines("Send", 2, 6, g, en, nd))
    order = [text.index(h) for h in ("Do this", "Look at", "Check before you go on", "The command", "Done when", "If you are blocked",
                                     "If it does not apply", "Ask", )]
    assert order == sorted(order) and "Yours: you hold the manager office. Nothing is missing." in text


# --- the six worked examples ----------------------------------------------------------------------------------------------------

def test_six_person_steps_across_four_families_carry_guidance_that_validates_against_every_registry(tmp_path):
    from jason.community import lessons as lessons_mod
    from jason.integrations.registry import REGISTRY
    from jason.workflows.definitions_general import register_general

    definitions.reset()
    try:
        wfs = register_general(None, integrations={i.key for i in REGISTRY})
        marked = [(w.family, s) for w in wfs for s in w.steps if s.support is not None]
        assert len(marked) == 6 and len({fam for fam, _ in marked}) >= 3
        for fam, s in marked:
            assert s.kind in (StepKind.PERSON, StepKind.DECISION), s.id
            assert guide.authored(s), s.id
            for key in s.support.guides.lessons:
                assert lessons_mod.lesson(key) is not None, (s.id, key)
        by = {s.id: s for _, s in marked}
        senders = by["owner-info-cycle.12"].support
        assert senders.enables.second_person is True and senders.guides.commands[0].terminal_only and senders.reminds.snoozable is False
        read = by["owner-info-cycle.17"].support.guides
        assert [l.read for l in read.look_at] == ["responses-new", "responses-unconfirmed"] and read.cites[0].key == "CIV 4041(b)(1)"
        assert by["board-meeting.12"].is_legal and by["board-meeting.12"].support.guides.cites[0].key == "CIV 4920(a)"
        assert by["mailroom-letter.3"].support.reminds.per_item and by["backflow-annual.7"].support.reminds.per_item
    finally:
        definitions.reset()


def test_the_guide_reads_count_the_inbox_and_say_so_when_they_cannot_read(data, monkeypatch):
    class NoStore:
        pass

    base = example_cycle()
    wf = with_support(C2, Support(guides=Guides(look_at=(LookAt("Arrived", "responses-new"),))))
    rid = run_of(data, wf)
    events, view = step_guide.folded(data, wf, rid, TODAY, FakeReaders())
    looked = guide_reads.run_read("responses-new", NoStore(), view, wf.step(C2), (), today=TODAY)
    assert looked.count is None and "AttributeError" in looked.unavailable and looked.as_of == "2099-09-20"
    assert guide_reads.run_read("nope", NoStore(), view, wf.step(C2)).unavailable == "the read 'nope' is not registered"
    assert base.step(C2).support is None


def test_the_composer_and_the_guide_import_no_client_and_send_nothing():
    import ast
    from pathlib import Path

    banned = ("smtplib", "imaplib", "requests", "httpx", "urllib", "socket", "payhoa", "jason.google", "jason.zoom", "jason.payhoa_tx",
              "jason.payhoa_session", "subprocess", "webbrowser")
    for path in (Path(step_guide.__file__), Path(nudge.__file__), Path(guide.__file__), Path(guide_reads.__file__)):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for name in names:
                assert not any(name == b or name.startswith(b + ".") for b in banned), f"{path.name} imports {name}"
