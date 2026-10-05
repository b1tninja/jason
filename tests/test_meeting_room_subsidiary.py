"""Table, continue, and refer in the meeting room: motions the board votes on, never a disposal without a vote.

Each needs a mover and a second, is voted by roll call under the room's rules (the threshold, the recusal readings), and
when it carries is recorded as a decision whose outcome is the motion's own word, and moves the item on the board's
list. Withdraw is the mover's act before the vote, logged, with no roll call. Made-up directors, items, and folders.
"""

import os

import pytest

os.environ.setdefault("JASON_SPEC_DIR", "/home/user/jason/tests/fixtures/spec")
os.environ["JASON_PROFILE"] = "mystique"

from jason.community.board_items import BoardItem, ItemCategory, ItemStatus
from jason.tasks import board_items, decisions
from jason.tasks import meeting_room as store

DAY = "2026-10-21"
LATER = "2026-11-18"
FIVE = ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"]
CLERK = "S. Clerk"


def _room(tmp_path, present=4):
    att = {n: ("present" if i < present else "absent") for i, n in enumerate(FIVE)}
    store.update(tmp_path, DAY, {"action": "attendance", "attendance": att}, CLERK, directors=FIVE)
    store.update(tmp_path, DAY, {"action": "call_to_order", "chair": "the president"}, CLERK)
    board_items.save(tmp_path, [BoardItem(id="pool-gate", title="Repair the pool gate", summary="The gate sticks.", ask="decide",
                                          category=ItemCategory.SAFETY, status=ItemStatus.ON_AGENDA, meeting=DAY)])


def _move(tmp_path, **body):
    body = {"action": "motion_draft", "itemId": "pool-gate", "title": "Repair the pool gate", "mover": FIVE[0], "second": FIVE[1], **body}
    store.update(tmp_path, DAY, body, CLERK)
    room = store.load(tmp_path, DAY)
    return room["motions"][-1]["id"]


def _roll(tmp_path, motion, *votes):
    for name, vote in zip(FIVE, votes):
        store.update(tmp_path, DAY, {"action": "vote", "motion": motion, "name": name, "vote": vote}, CLERK)
    return store.update(tmp_path, DAY, {"action": "decide", "motion": motion}, CLERK)


def _item(tmp_path):
    return next(i for i in board_items.load(tmp_path) if i.id == "pool-gate")


def test_each_subsidiary_motion_needs_a_mover_and_a_second(tmp_path):
    _room(tmp_path)
    for kind, more in (("table", {}), ("continue", {"meeting": LATER}), ("refer", {"to": "the landscape committee"})):
        with pytest.raises(ValueError, match="two different"):
            _move(tmp_path, kind=kind, second=FIVE[0], **more)
        with pytest.raises(ValueError, match="names a director"):
            _move(tmp_path, kind=kind, mover="", **more)
    with pytest.raises(ValueError, match="kind"):
        _move(tmp_path, kind="postpone indefinitely")
    with pytest.raises(ValueError, match="later meeting by its date"):
        _move(tmp_path, kind="continue")
    with pytest.raises(ValueError, match="after this one"):
        _move(tmp_path, kind="continue", meeting=DAY)
    with pytest.raises(ValueError, match="committee or the person"):
        _move(tmp_path, kind="refer", to="  ")
    assert store.load(tmp_path, DAY)["motions"] == []


def test_a_carried_motion_to_table_takes_the_pending_motion_and_records_tabled(tmp_path):
    _room(tmp_path)
    main = _move(tmp_path, text="Move to approve the bid of Vendor A for the gate.")
    sub = _move(tmp_path, kind="table", mover=FIVE[2], second=FIVE[3])
    room = store.load(tmp_path, DAY)
    assert room["motions"][-1] == {**room["motions"][-1], "kind": "table", "appliesTo": main, "text": "Move to table this item."}
    assert room["log"][-1]["title"] == f"Motion to table by {FIVE[2]}, seconded by {FIVE[3]}: Move to table this item."
    # The pending main motion waits: the board decides the motion to table first.
    with pytest.raises(ValueError, match="decides it first"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": main, "name": FIVE[0], "vote": "aye"}, CLERK)
    with pytest.raises(ValueError, match="already on the floor"):
        _move(tmp_path, kind="refer", to="counsel")
    room = _roll(tmp_path, sub, "aye", "aye", "aye", "no")
    by_id = {m["id"]: m for m in room["motions"]}
    assert by_id[sub]["result"] == "carried" and by_id[main]["result"] == "tabled" and by_id[main]["disposedBy"] == sub
    titles = [e["title"] for e in room["log"]]
    assert titles[-2].startswith("Roll call: D. Okafor aye, E. Lind aye, F. Marsh aye, G. Petrov no. Carried, 3–1–0")
    assert titles[-1] == "The item was tabled; it stays on the board's list for a later motion to take it from the table."
    [d] = decisions.for_meeting(tmp_path, DAY)
    assert (d.id, d.outcome, d.kind, d.mover, d.second) == (f"{DAY}--pool-gate--table", "tabled", "table", FIVE[2], FIVE[3])
    # Tabled, the item stays on the list as it was.
    item = _item(tmp_path)
    assert (item.status, item.meeting, item.owner) == (ItemStatus.ON_AGENDA, DAY, "")
    with pytest.raises(ValueError, match="recorded"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": main, "name": FIVE[0], "vote": "aye"}, CLERK)


def test_a_failed_motion_to_table_leaves_the_main_motion_on_the_floor(tmp_path):
    _room(tmp_path)
    main = _move(tmp_path, text="Move to approve the bid of Vendor A for the gate.")
    sub = _move(tmp_path, kind="table")
    room = _roll(tmp_path, sub, "aye", "no", "no", "no")
    by_id = {m["id"]: m for m in room["motions"]}
    assert by_id[sub]["result"] == "failed" and by_id[main]["result"] == ""
    assert not any(t["title"].startswith("The item was tabled") for t in room["log"])
    [d] = decisions.for_meeting(tmp_path, DAY)
    assert (d.outcome, d.kind) == ("denied", "table")
    # Back on the floor, the main motion is voted and recorded under its own id, beside the motion to table.
    _roll(tmp_path, main, "aye", "aye", "aye", "aye")
    assert {x.id: x.outcome for x in decisions.for_meeting(tmp_path, DAY)} == {f"{DAY}--pool-gate--table": "denied", f"{DAY}--pool-gate": "approved"}


def test_continue_sets_the_items_meeting_to_the_named_date(tmp_path):
    _room(tmp_path)
    sub = _move(tmp_path, kind="continue", meeting=LATER)
    room = _roll(tmp_path, sub, "aye", "aye", "aye", "abstain")
    assert room["motions"][-1]["meeting"] == LATER and room["motions"][-1]["appliesTo"] == ""
    assert room["log"][-1]["title"] == f"The item was continued to the meeting of {LATER}."
    item = _item(tmp_path)
    assert item.meeting == LATER and any(f"meeting {DAY} -> {LATER}" in h for h in item.history)
    [d] = decisions.for_meeting(tmp_path, DAY)
    assert (d.outcome, d.kind) == ("continued", "continue") and d.notes.startswith(f"The item was continued to the meeting of {LATER}.")


def test_refer_notes_the_named_committee_as_the_items_owner(tmp_path):
    _room(tmp_path)
    sub = _move(tmp_path, kind="refer", to="the landscape committee", text="Move to refer the gate to the landscape committee.")
    room = _roll(tmp_path, sub, "aye", "aye", "aye", "no")
    assert room["log"][-1]["title"] == "The item was referred to the landscape committee, to report back to the board."
    assert _item(tmp_path).owner == "the landscape committee"
    [d] = decisions.for_meeting(tmp_path, DAY)
    assert (d.outcome, d.motion) == ("referred", "Move to refer the gate to the landscape committee.")


def test_a_failed_referral_moves_nothing(tmp_path):
    _room(tmp_path)
    sub = _move(tmp_path, kind="refer", to="counsel")
    _roll(tmp_path, sub, "no", "no", "aye", "no")
    assert _item(tmp_path).owner == "" and decisions.for_meeting(tmp_path, DAY)[0].outcome == "denied"


def test_the_threshold_decides_a_subsidiary_motion_too(tmp_path):
    # Two-thirds of four present is three: two ayes fail it.
    _room(tmp_path)
    sub = _move(tmp_path, kind="continue", meeting=LATER, threshold="two-thirds")
    room = _roll(tmp_path, sub, "aye", "aye", "no", "abstain")
    assert room["motions"][-1]["result"] == "failed" and room["motions"][-1]["tally"]["needs"] == 3
    assert _item(tmp_path).meeting == DAY


def test_a_held_recusal_reading_holds_the_subsidiary_vote(tmp_path):
    # Four present, one recused, the recusal rule not on file: two ayes and a no carry under one reading and fail under
    # the other, so the vote is held and nothing moves.
    _room(tmp_path)
    sub = _move(tmp_path, kind="refer", to="counsel", recused=[FIVE[3]])
    for name, vote in zip(FIVE[:3], ("aye", "aye", "no")):
        store.update(tmp_path, DAY, {"action": "vote", "motion": sub, "name": name, "vote": vote}, CLERK)
    with pytest.raises(ValueError, match="two readings"):
        store.update(tmp_path, DAY, {"action": "decide", "motion": sub}, CLERK)
    assert store.load(tmp_path, DAY)["motions"][-1]["result"] == "" and _item(tmp_path).owner == ""
    assert decisions.for_meeting(tmp_path, DAY) == []


def test_withdraw_is_the_movers_act_before_the_vote_with_no_roll_call(tmp_path):
    _room(tmp_path)
    main = _move(tmp_path, text="Move to approve the bid of Vendor A for the gate.")
    sub = _move(tmp_path, kind="table")
    with pytest.raises(ValueError, match="decides it first"):
        store.update(tmp_path, DAY, {"action": "withdraw", "motion": main}, CLERK)
    with pytest.raises(ValueError, match="only the mover"):
        store.update(tmp_path, DAY, {"action": "withdraw", "motion": sub, "name": FIVE[1]}, CLERK)
    room = store.update(tmp_path, DAY, {"action": "withdraw", "motion": sub}, CLERK)
    by_id = {m["id"]: m for m in room["motions"]}
    assert by_id[sub]["result"] == store.WITHDRAWN and by_id[sub]["votes"] == {} and by_id[main]["result"] == ""
    assert room["log"][-1]["title"] == f"Motion to table withdrawn by {FIVE[0]}, the mover, before the vote: Move to table this item."
    assert decisions.for_meeting(tmp_path, DAY) == []                       # no vote, no decision
    # Once the roll call has begun, the mover can no longer withdraw.
    store.update(tmp_path, DAY, {"action": "vote", "motion": main, "name": FIVE[0], "vote": "aye"}, CLERK)
    with pytest.raises(ValueError, match="roll call has begun"):
        store.update(tmp_path, DAY, {"action": "withdraw", "motion": main}, CLERK)
    with pytest.raises(ValueError, match="decided"):
        store.update(tmp_path, DAY, {"action": "withdraw", "motion": sub}, CLERK)


def test_in_executive_session_the_motion_and_its_outcome_stay_in_the_executive_record(tmp_path):
    secret = "Hearing, unit 7 (made-up owner Q. Sample)"
    _room(tmp_path)
    store.update(tmp_path, DAY, {"action": "executive_start", "matters": [{"id": "hearing-7", "subject": "member_discipline", "title": secret}]}, CLERK)
    store.update(tmp_path, DAY, {"action": "motion_draft", "itemId": "hearing-7", "title": secret, "kind": "continue", "meeting": LATER,
                                 "mover": FIVE[0], "second": FIVE[1]}, CLERK)
    for name in FIVE[:4]:
        store.update(tmp_path, DAY, {"action": "vote", "motion": "x1", "name": name, "vote": "aye"}, CLERK)
    store.update(tmp_path, DAY, {"action": "decide", "motion": "x1"}, CLERK)
    room = store.update(tmp_path, DAY, {"action": "executive_end"}, CLERK)
    record = store.load_executive(tmp_path, DAY)
    assert record["motions"][0]["result"] == "carried" and record["motions"][0]["kind"] == "continue"
    assert any(e["title"].startswith(f"The item was continued to the meeting of {LATER}.") for e in record["log"])
    assert room["motions"] == []
    open_text = (tmp_path / "meetings" / f"room-{DAY}.json").read_text(encoding="utf-8")
    for word in (secret, "hearing-7", "continued", "Roll call"):
        assert word not in open_text
    [d] = decisions.for_meeting(tmp_path, DAY)
    assert (d.session, d.subject, d.outcome) == ("executive session", "member_discipline", "continued")
    assert decisions.open_only([d]) == []
    # The matter is not on the board's list here: nothing on the list changes, and the executive log says so.
    assert any("not on the board's list (hearing-7)" in e["title"] for e in record["log"])


def test_the_decisions_store_takes_the_new_words():
    assert {"tabled", "continued", "referred"} <= set(decisions.OUTCOMES)
    assert decisions.KINDS == ("", "table", "continue", "refer")
    with pytest.raises(ValueError, match="kind"):
        decisions._validate({"kind": "postpone"})
