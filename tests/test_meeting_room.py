"""The meeting room: the store's rules (quorum, two directors, recusal, thresholds, the CIV 4930 paths, the decision
record) and the loader's merge of the meeting, the plan, the room, and the roster."""

import json
import os
import sys
import types

import pytest
import webclient

os.environ.setdefault("JASON_SPEC_DIR", "/home/user/jason/tests/fixtures/spec")
os.environ["JASON_PROFILE"] = "mystique"

from jason.tasks import decisions
from jason.tasks import meeting_room as store

DAY = "2026-10-21"
FIVE = ["D. Okafor", "E. Lind", "F. Marsh", "G. Petrov", "H. Quinn"]


def _room(tmp_path, present=4, directors=FIVE):
    """A room with ``present`` of the directors marked present, called to order."""
    att = {n: ("present" if i < present else "absent") for i, n in enumerate(directors)}
    store.update(tmp_path, DAY, {"action": "attendance", "attendance": att}, "S. Clerk", directors=directors)
    return store.update(tmp_path, DAY, {"action": "call_to_order", "chair": "the president"}, "S. Clerk")


def _motion(tmp_path, **more):
    body = {"action": "motion_draft", "itemId": "landscape", "title": "Renew the landscape contract", "text": "Move to approve the contract.",
            "mover": FIVE[0], "second": FIVE[1], **more}
    room = store.update(tmp_path, DAY, body, "S. Clerk")
    return room["motions"][-1]["id"]


def _vote(tmp_path, motion, **votes):
    for name, v in votes.items():
        store.update(tmp_path, DAY, {"action": "vote", "motion": motion, "name": FIVE[int(name[1:])], "vote": v}, "S. Clerk")


def test_quorum_follows_the_profile_board_rule():
    assert store.quorum(FIVE) == 3          # a majority of five, as the fixture profile's bylaws say
    assert store.quorum(FIVE[:3]) == 2
    assert store.quorum([]) == 0


def test_needed_votes_by_threshold():
    assert store.needed(4, "majority", 5) == 3          # a majority of the four present, a recused director among them or not
    assert store.needed(3, "majority", 5) == 2
    assert store.needed(4, "two-thirds", 5) == 3        # two-thirds of four present
    assert store.needed(3, "two-thirds", 5) == 3        # fewer than two-thirds of the board present: every director
    assert store.needed(0, "majority", 5) == 0


def test_call_to_order_logs_the_roster_and_the_quorum(tmp_path):
    room = _room(tmp_path, present=4)
    assert room["calledToOrder"] and room["present"] if "present" in room else True
    line = room["log"][0]["title"]
    assert "Present: D. Okafor, E. Lind, F. Marsh, G. Petrov." in line and "Absent: H. Quinn." in line and "A quorum was present." in line
    assert room["log"][0]["by"] == "S. Clerk"
    with pytest.raises(ValueError):
        store.update(tmp_path, DAY, {"action": "call_to_order"}, "S. Clerk")
    assert json.loads((tmp_path / "meetings" / f"room-{DAY}.json").read_text())["history"][-1].endswith("call_to_order by S. Clerk")


def test_a_motion_needs_two_different_present_directors_and_a_quorum(tmp_path):
    _room(tmp_path, present=4)
    with pytest.raises(ValueError, match="two different"):
        _motion(tmp_path, second=FIVE[0])
    with pytest.raises(ValueError, match="text"):
        _motion(tmp_path, text="  ")
    with pytest.raises(ValueError, match="present"):
        _motion(tmp_path, second=FIVE[4])           # absent
    with pytest.raises(ValueError, match="not one of the directors"):
        _motion(tmp_path, second="Someone Else")
    mid = _motion(tmp_path)
    assert mid == "m1"
    store.update(tmp_path, DAY, {"action": "attendance", "attendance": {n: "absent" for n in FIVE[2:]}}, "S. Clerk")
    with pytest.raises(ValueError, match="no quorum"):
        _motion(tmp_path)


def test_a_recused_director_cannot_vote_and_the_quorum_question_is_not_on_file(tmp_path):
    # Three present, quorum is three; one of them recused. The profile's bylaws do not say whether a recused director
    # counts toward the quorum, and counsel's reading is not on file: the room works the vote both ways.
    _room(tmp_path, present=3)
    mid = _motion(tmp_path, recused=[FIVE[2]])
    assert store.load(tmp_path, DAY)["log"][-1]["title"].endswith(f"is {store.NOT_ON_FILE}.")
    with pytest.raises(ValueError, match="recused"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": mid, "name": FIVE[2], "vote": "aye"}, "S. Clerk")
    with pytest.raises(ValueError, match="not present"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": mid, "name": FIVE[4], "vote": "aye"}, "S. Clerk")
    with pytest.raises(ValueError, match="roll call by name"):
        store.update(tmp_path, DAY, {"action": "decide", "motion": mid}, "S. Clerk")
    _vote(tmp_path, mid, d0="aye", d1="no")
    room = store.with_tallies(store.load(tmp_path, DAY))
    t = room["motions"][0]["tally"]
    assert t["line"] == ("Yes 1 · No 1 · Abstain 0 · Recused 1. Needs 2 yes counting the recused director as present, "
                         "2 yes if not (no quorum). Fails under either reading.")
    assert t["recusal"] == "not on file" and t["readings"]["notCounted"]["quorum"] is False
    room = store.update(tmp_path, DAY, {"action": "decide", "motion": mid}, "S. Clerk")
    assert room["motions"][0]["result"] == "failed" and store.NOT_ON_FILE in room["log"][-1]["title"]
    recorded = decisions.for_meeting(tmp_path, DAY)[0]
    # The recusal is recorded as such: never marked absent, never a no.
    assert recorded.recused == [FIVE[2]] and FIVE[2] not in recorded.votes
    with pytest.raises(ValueError, match="recusing|recused|already"):
        _motion(tmp_path, recused=[FIVE[0]])        # the mover may not be recused


def test_a_vote_the_two_readings_decide_differently_is_held(tmp_path):
    # Four present, one recused, quorum three. Counted as present, a majority of four is three; not counted, a majority
    # of three is two. Two ayes carry under one reading and fail under the other: held, never chosen silently.
    _room(tmp_path, present=4)
    mid = _motion(tmp_path, recused=[FIVE[3]])
    _vote(tmp_path, mid, d0="aye", d1="aye", d2="no")
    t = store.tally(store.load(tmp_path, DAY)["motions"][0], store.load(tmp_path, DAY))
    assert t["state"] == "held" and store.NOT_ON_FILE in t["line"]
    assert (t["readings"]["counted"]["state"], t["readings"]["notCounted"]["state"]) == ("fails", "carries")
    with pytest.raises(ValueError, match="two readings"):
        store.update(tmp_path, DAY, {"action": "decide", "motion": mid}, "S. Clerk")
    assert store.load(tmp_path, DAY)["motions"][0]["result"] == "" and decisions.for_meeting(tmp_path, DAY) == []


def test_the_recusal_rule_on_file_decides_the_count(tmp_path, monkeypatch):
    from jason.community.base import BoardRule, RuleSource, VoteBasis

    _room(tmp_path, present=4)
    mid = _motion(tmp_path, recused=[FIVE[3]])
    _vote(tmp_path, mid, d0="aye", d1="aye", d2="no")
    reading = RuleSource(cite="Bylaws 1.2", counsel="Counsel, letter of 2099-01-01")
    counts = BoardRule(seats=5, minimum=3, maximum=5, vote_basis=VoteBasis.MAJORITY_PRESENT, vote_source=RuleSource("Bylaws 1.2"),
                       interested_in_quorum=True, interested_source=reading)
    room = store.load(tmp_path, DAY)
    t = store.tally(room["motions"][0], room, counts)
    assert (t["state"], t["needs"], t["recusal"]) == ("fails", 3, "counted")
    apart = BoardRule(seats=5, minimum=3, maximum=5, interested_in_quorum=False, interested_source=reading)
    t = store.tally(room["motions"][0], room, apart)
    assert (t["state"], t["needs"], t["recusal"]) == ("carries", 2, "not counted")
    rules = store.board_rules(None, counts)
    assert rules["interested"]["onFile"] and rules["interested"]["label"] == (
        "Counsel, letter of 2099-01-01's reading of Bylaws 1.2, a reading, not the provision's words")
    assert rules["voteBasis"]["basis"] == VoteBasis.MAJORITY_PRESENT.value
    monkeypatch.setattr(store, "_board", lambda: apart)
    room = store.update(tmp_path, DAY, {"action": "decide", "motion": mid}, "S. Clerk")
    assert room["motions"][0]["result"] == "carried"


def test_board_rules_not_on_file_say_so_and_never_fill_in():
    rules = store.board_rules(None, None)
    assert not rules["quorum"]["onFile"] and store.NOT_ON_FILE in rules["quorum"]["label"]
    assert not rules["voteBasis"]["onFile"] and store.NOT_ON_FILE in rules["voteBasis"]["label"]
    assert rules["interested"]["counts"] is None and store.NOT_ON_FILE in rules["interested"]["label"]
    # The fixture profile's bylaws set the quorum and the vote (quoted from the provision named), and leave the
    # recusal question open.
    rules = store.board_rules()
    assert rules["quorum"]["onFile"] and rules["voteBasis"]["onFile"] and rules["voteBasis"]["source"]
    assert not rules["interested"]["onFile"] and store.NOT_ON_FILE in rules["interested"]["label"]


def test_open_forum_has_no_limit_until_the_board_sets_one(tmp_path):
    room = store.with_tallies(store.load(tmp_path, DAY))
    assert room["openForum"]["limitMinutes"] == 0 and room["openForum"]["limitNote"] == store.NO_FORUM_LIMIT
    assert store.empty(DAY)["openForum"]["limitMinutes"] == 0
    _room(tmp_path)
    room = store.update(tmp_path, DAY, {"action": "open_forum", "count": 2, "close": True}, "S. Clerk")
    assert room["log"][-1]["title"] == "Open forum: 2 members spoke; no time limit on record (CIV 4925(b))."
    # A limit a person enters is the room's, credited to them.
    room = store.with_tallies(store.update(tmp_path, DAY, {"action": "open_forum", "limitMinutes": 2}, "S. Clerk"))
    assert room["openForum"]["limitMinutes"] == 2 and room["openForum"]["limitSource"] == "entered in the room"
    assert "limitBy" not in room["openForum"] and store.load(tmp_path, DAY)["openForum"]["limitBy"] == "S. Clerk"
    # A limit stored with no person behind it (an earlier default) is not a limit on record.
    path = tmp_path / "meetings" / f"room-{DAY}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["openForum"] = {"count": 0, "limitMinutes": 3}
    path.write_text(json.dumps(raw), encoding="utf-8")
    assert store.with_tallies(store.load(tmp_path, DAY))["openForum"]["limitMinutes"] == 0


def test_open_forum_follows_the_boards_policy_when_on_file(monkeypatch):
    from jason.community import community
    from jason.community.base import SpeakingLimit

    monkeypatch.setattr(type(community()), "open_forum_limit", lambda self: SpeakingLimit(4, "Resolution 2099-1"))
    rule = store.forum_rule()
    assert rule == {"onFile": True, "minutes": 4, "source": "Resolution 2099-1", "label": "4 minutes each (Resolution 2099-1; CIV 4925(b))."}
    assert store.forum_limit(store.empty(DAY))["minutes"] == 4


def test_two_thirds_threshold_and_the_decision_record(tmp_path):
    _room(tmp_path, present=4)
    mid = _motion(tmp_path, threshold="two-thirds", text="Move to find that the roof leak needs immediate action.")
    _vote(tmp_path, mid, d0="aye", d1="aye", d2="no", d3="abstain")
    t = store.tally(store.load(tmp_path, DAY)["motions"][0], store.load(tmp_path, DAY))
    assert t["needs"] == 3 and t["state"] == "fails"
    _vote(tmp_path, mid, d2="aye")
    room = store.update(tmp_path, DAY, {"action": "decide", "motion": mid}, "S. Clerk")
    m = room["motions"][0]
    assert m["result"] == "carried" and m["tally"] == {"aye": 3, "no": 0, "abstain": 1, "recused": 0, "needs": 3}
    assert "Roll call: D. Okafor aye, E. Lind aye, F. Marsh aye, G. Petrov abstain. Carried, 3–0–1 (two-thirds, 3 needed)." == room["log"][-1]["title"]
    recorded = decisions.for_meeting(tmp_path, DAY)
    assert len(recorded) == 1 and recorded[0].id == f"{DAY}--landscape" and recorded[0].outcome == "approved"
    assert recorded[0].votes == {FIVE[0]: "aye", FIVE[1]: "aye", FIVE[2]: "aye", FIVE[3]: "abstain", FIVE[4]: "absent"}
    assert recorded[0].mover == FIVE[0] and recorded[0].by == "S. Clerk" and "Threshold two-thirds" in recorded[0].notes
    with pytest.raises(ValueError, match="already decided"):
        store.update(tmp_path, DAY, {"action": "decide", "motion": mid}, "S. Clerk")
    with pytest.raises(ValueError, match="recorded"):
        store.update(tmp_path, DAY, {"action": "vote", "motion": mid, "name": FIVE[0], "vote": "no"}, "S. Clerk")
    with pytest.raises(KeyError):
        store.update(tmp_path, DAY, {"action": "vote", "motion": "m9", "name": FIVE[0], "vote": "no"}, "S. Clerk")


def test_off_agenda_takes_only_the_civ_4930_paths(tmp_path):
    _room(tmp_path)
    assert list(store.OFF_AGENDA_PATHS) == ["b", "c", "d1", "d2", "d3"]
    with pytest.raises(ValueError, match="4930"):
        store.update(tmp_path, DAY, {"action": "off_agenda", "path": "vote now"}, "S. Clerk")
    with pytest.raises(ValueError, match="4930"):
        store.update(tmp_path, DAY, {"action": "off_agenda", "path": "a"}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "off_agenda", "path": "c", "topic": "the pool gate"}, "S. Clerk")
    assert room["log"][-1]["title"].startswith("Not on the posted agenda: the pool gate. ") and "CIV 4930(c)" in room["log"][-1]["title"]
    room = store.update(tmp_path, DAY, {"action": "off_agenda", "path": "d2"}, "S. Clerk")
    assert "CIV 4930(d)(2)" in room["log"][-1]["title"] and room["log"][-1]["title"].endswith(store.IDENTIFY_FIRST)


def test_executive_session_polls_admission_suggestions_and_adjournment(tmp_path):
    _room(tmp_path)
    with pytest.raises(ValueError):
        store.update(tmp_path, DAY, {"action": "executive_end"}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "executive_start", "subjects": ["member_discipline"], "note": "a member discipline hearing"}, "S. Clerk")
    assert room["executive"]["active"] and "host pauses the recording" in room["log"][-1]["title"]
    with pytest.raises(ValueError, match="executive"):
        store.update(tmp_path, DAY, {"action": "adjourn"}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "executive_end"}, "S. Clerk")
    assert not room["executive"]["active"] and room["executive"]["endedAt"]
    room = store.update(tmp_path, DAY, {"action": "poll", "question": "Which item would you like to speak on?", "results": {"Budget": 2, "Other": "1"}}, "S. Clerk")
    assert room["polls"][0]["note"] == "member input, not a vote" and room["polls"][0]["results"] == {"Budget": 2, "Other": 1}
    with pytest.raises(ValueError):
        store.update(tmp_path, DAY, {"action": "poll", "question": "", "results": {}}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "admit", "names": ["Owner One", "Owner Two"]}, "S. Clerk")
    assert room["admitted"] == ["Owner One", "Owner Two"] and "The chair decides on anyone unmatched" in room["log"][-1]["title"]
    with pytest.raises(ValueError):
        store.update(tmp_path, DAY, {"action": "admit", "names": []}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "suggest", "who": "a member", "text": "The gate still sticks."}, "S. Clerk")
    before = len(room["log"])
    room = store.update(tmp_path, DAY, {"action": "suggestion_state", "index": 0, "state": "dismissed"}, "S. Clerk")
    assert room["transcriptSuggestions"][0]["state"] == "dismissed" and len(room["log"]) == before
    room = store.update(tmp_path, DAY, {"action": "suggestion_state", "index": 0, "state": "added"}, "S. Clerk")
    assert room["log"][-1]["title"] == "a member: The gate still sticks. (from the transcript, checked by the secretary)"
    with pytest.raises(KeyError):
        store.update(tmp_path, DAY, {"action": "suggestion_state", "index": 5, "state": "added"}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "open_forum", "count": 3, "limitMinutes": 2, "close": True}, "S. Clerk")
    assert room["log"][-1]["title"] == "Open forum: 3 members spoke, 2 minutes each (entered in the room) (CIV 4925(b))."
    room = store.update(tmp_path, DAY, {"action": "go_to", "item": 2, "title": "Approve the minutes"}, "S. Clerk")
    assert room["current"] == 2 and room["log"][-1]["title"] == "Item opened: Approve the minutes"
    room = store.update(tmp_path, DAY, {"action": "adjourn"}, "S. Clerk")
    assert room["adjournedAt"] and "CIV 4950" in room["log"][-1]["title"]
    with pytest.raises(ValueError):
        store.update(tmp_path, DAY, {"action": "adjourn"}, "S. Clerk")


def test_everything_else_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no action"):
        store.update(tmp_path, DAY, {"action": "delete_everything"}, "S. Clerk")
    with pytest.raises(ValueError, match="by"):
        store.update(tmp_path, DAY, {"action": "set_view", "view": "shared"}, "")
    with pytest.raises(KeyError):
        store.update(tmp_path, "not-a-date", {"action": "set_view", "view": "shared"}, "S. Clerk")
    for action, body in (("set_view", {"view": "tv"}), ("set_mode", {"mode": "ghost"}), ("set_presenter", {"presenter": "me"}),
                         ("attendance", {"name": FIVE[0], "state": "late"}), ("go_to", {"item": "x"}), ("open_forum", {"limitMinutes": 0})):
        with pytest.raises(ValueError):
            store.update(tmp_path, DAY, {"action": action, **body}, "S. Clerk", directors=FIVE)
    room = store.update(tmp_path, DAY, {"action": "set_mode", "mode": "portal"}, "S. Clerk", directors=FIVE)
    room = store.update(tmp_path, DAY, {"action": "set_presenter", "presenter": "chair"}, "S. Clerk")
    room = store.update(tmp_path, DAY, {"action": "set_view", "view": "shared"}, "S. Clerk")
    assert (room["mode"], room["presenter"], room["view"]) == ("portal", "chair", "shared")
    assert store.load(tmp_path, "2026-01-01")["motions"] == []


# -- the loader and the writer ----------------------------------------------------------------------------------------

@pytest.fixture
def fakes(tmp_path, monkeypatch):
    """A fake county module (the data root), a fake ``meeting`` loader, and an agenda plan that can be switched on."""
    saved = {k: sys.modules.get(k) for k in ("jason.mcp", "jason.mcp.county", "jason.web.extra.agenda_plan")}
    county = types.ModuleType("jason.mcp.county")
    county._data_dir = lambda _: tmp_path
    pkg = types.ModuleType("jason.mcp")
    pkg.__path__ = []
    pkg.county = county
    sys.modules["jason.mcp"], sys.modules["jason.mcp.county"] = pkg, county
    import jason.web.sources as sources

    base = {"found": True, "date": DAY, "today": "2026-10-03", "directors": FIVE, "decisions": [], "notes": [],
            "items": [{"id": "landscape", "title": "Renew the landscape contract", "agendaSession": "open session", "ask": "approve a bid", "authority": "CIV 5350"},
                      {"id": "hearing", "title": "Hearing, unit 7", "agendaSession": "executive session"}],
            "commands": {"minutesDraft": f"jason board --minutes {DAY}"}}
    monkeypatch.setattr(sources, "meeting", lambda args: {"found": False, "note": "date is YYYY-MM-DD"} if args.get("date") == "bad" else base)
    plan = types.ModuleType("jason.web.extra.agenda_plan")
    plan.result = {"found": False, "note": "not built yet"}
    plan.agenda_plan = lambda args: plan.result
    sys.modules["jason.web.extra.agenda_plan"] = plan
    try:
        yield types.SimpleNamespace(plan=plan, base=base, root=tmp_path)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_loader_merges_the_meeting_the_room_and_falls_back_without_a_plan(fakes):
    from jason.web.extra.meeting_room import meeting_room, write

    out = meeting_room({"date": DAY})
    assert out["found"] and out["quorum"] == 3 and out["directors"] == FIVE
    assert [i["id"] for i in out["items"]] == ["call", "forum", "landscape", "exec", "adjourn"]
    # No speaking limit on record: open forum gets no allotment, and the room says so rather than assume one.
    assert out["items"][1]["allot"] == 0 and out["room"]["openForum"]["limitNote"] == store.NO_FORUM_LIMIT
    assert out["rules"]["interested"]["onFile"] is False and store.NOT_ON_FILE in out["rules"]["interested"]["label"]
    assert not any("counts toward the quorum and not toward the vote" in c for c in out["caveats"])
    # The executive matter has no 4935 subject named: it is counted, never named by its title, and cannot go executive yet.
    assert out["items"][2]["label"] == "Item 1 · Action" and out["items"][3]["matters"] == [] and out["items"][3]["unnamed"] == 1
    assert out["items"][3]["subjectNote"].startswith("name the 4935 subject first") and "Hearing, unit 7" not in json.dumps(out)
    assert out["executive"] == {"shown": False, "active": False, "note": "Executive session: the record is kept apart (open the private view to see it).", "record": None}
    assert out["plan"] == {"found": False, "count": 0} and "not built yet" in out["notes"]
    assert out["roster"]["count"] == 0 and "roster not synced" in out["roster"]["note"]
    assert [p["path"] for p in out["offAgendaPaths"]] == ["b", "c", "d1", "d2", "d3"]
    assert out["room"]["motions"] == [] and out["room"]["present"] == [] and out["minutesKey"] == f"minutes/{DAY}"
    assert any("jason does not admit" in c for c in out["caveats"]) and out["zoom"]["admitCommand"] == ""
    assert "recordingPause" not in out["zoom"]["commands"] and "Schedule the meeting" in out["zoom"]["note"] and out["zoom"]["meetingId"] is None
    assert meeting_room({"date": "bad"}) == {"found": False, "note": "date is YYYY-MM-DD"}
    # The writer applies an action as the person's act and gives the room back with tallies; the loader then shows it.
    room = write(DAY, {"action": "attendance", "by": "S. Clerk", "directors": FIVE, "attendance": {n: "present" for n in FIVE[:3]}})
    assert room["present"] == FIVE[:3] and room["directors"] == FIVE and "directors" not in room["history"][-1]
    room = write(DAY, {"action": "motion_draft", "by": "S. Clerk", "itemId": "landscape", "title": "Renew", "text": "Move it.", "mover": FIVE[0], "second": FIVE[1]})
    assert room["motions"][0]["tally"]["line"] == "Yes 0 · No 0 · Abstain 0 · Recused 0. Needs 2 yes. Vote open."
    assert meeting_room({"date": DAY})["room"]["motions"][0]["id"] == "m1"
    with pytest.raises(ValueError):
        write(DAY, {"action": "vote", "by": "", "motion": "m1", "name": FIVE[0], "vote": "aye"})
    with pytest.raises(ValueError):
        write(DAY, {"action": "off_agenda", "by": "S. Clerk", "path": "z"})


def test_loader_orders_the_plans_included_candidates(fakes):
    from jason.web.extra.meeting_room import meeting_room

    fakes.plan.result = {"found": True, "candidates": [
        {"id": "budget", "title": "2027 budget", "kind": "discussion", "include": True, "order": 2, "motion": "Move to continue.", "allot": 20,
         "packet": [{"id": "f1", "name": "Draft budget", "kind": "sheet"}], "brief": {"question": "Which?", "criteria": [], "options": []}},
        {"id": "minutes", "title": "Approve the minutes", "kind": "consent", "include": True, "order": 1, "facts": ["Draft out since 2026-10-03"]},
        {"id": "trim", "title": "Repaint the trim", "kind": "action", "include": False, "order": 3},
        {"id": "delinq", "title": "Delinquent accounts", "kind": "exec", "session": "executive", "include": True, "order": 4,
         "general": "free text is not the general note", "subject": "assessment_payment"},
    ]}
    out = meeting_room({"date": DAY})
    assert [i["id"] for i in out["items"]] == ["call", "forum", "minutes", "budget", "exec", "adjourn"]
    assert out["items"][2]["label"] == "Item 1 · Consent" and out["items"][2]["facts"] == ["Draft out since 2026-10-03"]
    assert out["items"][3]["packet"][0]["name"] == "Draft budget" and out["items"][3]["brief"]["question"] == "Which?"
    assert out["items"][4]["matters"] == ["a member's payment of assessments"] and out["plan"] == {"found": True, "count": 4}
    assert out["items"][4]["motion"] == "Move to adjourn to executive session to discuss a member's payment of assessments (Civil Code 4935(a), (c))."
    assert out["items"][4]["executiveMatters"] == [{"ref": "1", "subject": "assessment_payment", "general": "a member's payment of assessments", "named": True}]
    assert "Delinquent accounts" not in json.dumps(out) and "delinq" not in json.dumps(out["items"][4])
    fakes.plan.agenda_plan = lambda args: (_ for _ in ()).throw(RuntimeError("boom"))
    out = meeting_room({"date": DAY})
    assert any("agenda plan: RuntimeError" in n for n in out["notes"]) and [i["id"] for i in out["items"]][2] == "landscape"


def test_api_meeting_room_write_route(fakes):
    from jason.web.app import create_app

    c = webclient.client(create_app(fakes.root, {}, board_writer=None, canvas_writer=None, decision_writer=None, request_writer=None,
                                    owner_info_writer=None, hearing_writer=None, extra_writes=True))
    assert "meeting-room" in c.get("/api/health").json["writes"]
    r = c.post(f"/api/write/meeting-room/{DAY}", json={"action": "set_view", "view": "shared", "by": "S. Clerk"})
    assert r.status_code == 200 and r.json["view"] == "shared"
    assert c.post(f"/api/write/meeting-room/{DAY}", json={"action": "set_view", "view": "tv", "by": "S. Clerk"}).status_code == 400
    assert c.post("/api/write/meeting-room/nope", json={"action": "set_view", "view": "shared", "by": "S. Clerk"}).status_code == 404


def test_a_scheduled_meeting_adds_the_recording_and_caption_commands(tmp_path):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from jason.tasks.zoom import save_board_meeting
    from jason.web.extra import meeting_room as mod
    from jason.zoom.models import BoardMeetingPlan, BoardMeetingPolicy

    policy = BoardMeetingPolicy(timezone="America/Los_Angeles", topic="Sample Commons board meeting")
    save_board_meeting(tmp_path, BoardMeetingPlan(start=datetime(2026, 10, 21, 19, 0, tzinfo=ZoneInfo(policy.timezone)), policy=policy,
                                                  zoom={"id": 85550001111, "joinUrl": "https://zoom.us/j/1", "passcode": "1", "dialIn": []}))
    z = mod._zoom(tmp_path, "2026-10-21")
    assert z["meetingId"] == 85550001111
    assert z["commands"]["recordingPause"] == "jason zoom --recording pause --meeting-id 85550001111 --yes"
    assert z["commands"]["caption"].startswith('jason zoom --caption "<the answer>" --meeting-id 85550001111 --yes')
    assert "seen by everyone" in z["note"]
    assert mod._zoom(tmp_path, "2026-11-18")["meetingId"] is None
