"""The deficiency register (``jason.tasks.deficiencies``): rows proposed once from a report's reading, a person's
confirmation, impairment, clearing record, and insurer notice, appended with who and when and never edited. Made-up
systems and readings in tmp_path; nothing is reached.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from test_inspections import ALARM, RISERS, _Profile

from jason.tasks import deficiencies as d

FOUND = "2026-03-10"
TODAY = date(2026, 10, 11)


def reading(ident, day, *, result="failed", items=(), open_count=0, confidential=False, system="fire alarm", building="A"):
    return {"id": ident, "name": f"Report {ident}.pdf", "kind": "inspection_report", "model": "made-up-reader",
            "hasText": True, "confidential": confidential,
            "fields": {"inspection_date": day, "system": system, "building": building, "result": result,
                       "deficiencies": list(items), "open_deficiencies": open_count}}


OPEN = {"location": "Riser room", "device": "Waterflow switch", "comment": "Failed to transmit", "status": "Open"}
DONE = {"location": "Lobby", "device": "Horn", "comment": "Replaced", "status": "Resolved"}


@pytest.fixture
def lib(monkeypatch):
    rows = [reading("drive-1", FOUND, items=[OPEN, DONE]),
            reading("drive-2", "2026-06-01", result="passed"),
            reading("drive-3", "2026-02-01", result="passed", system="fire alarm"),
            reading("drive-4", "2026-04-01", items=[OPEN], confidential=True)]
    monkeypatch.setattr(d, "_library", lambda data_dir: tuple(rows))
    return rows


@pytest.fixture
def profile():
    return _Profile((RISERS, ALARM), ())


@pytest.fixture(autouse=True)
def _made_up_community(monkeypatch, profile):
    """The board item names the system through the active profile: use the made-up one, never the real profile."""
    monkeypatch.setattr(d, "_active_community", lambda: profile)


def test_an_open_deficiency_is_proposed_once_and_a_resolved_or_confidential_one_is_not(tmp_path, lib, profile):
    added = d.propose(tmp_path, profile, now="2026-10-04T00:00:00+00:00")
    assert len(added) == 1 and added[0]["comment"] == "Failed to transmit" and added[0]["system"] == "alarm"
    assert d.state_of(added[0])["standing"] == "proposed"
    assert d.propose(tmp_path, profile) == []                       # a second run adds nothing
    assert [r["id"] for r in d.load(tmp_path)] == [added[0]["id"]]


def test_a_report_that_counts_open_deficiencies_without_listing_them_says_so(tmp_path, monkeypatch, profile):
    monkeypatch.setattr(d, "_library", lambda data_dir: (reading("drive-9", FOUND, open_count=2),))
    row = d.propose(tmp_path, profile)[0]
    assert "counts 2 open deficiencies; its items were not read" in row["comment"]


def test_a_contact_in_a_report_is_masked(tmp_path, monkeypatch, profile):
    item = dict(OPEN, comment="Call pat@example.org or 916-555-0100")
    monkeypatch.setattr(d, "_library", lambda data_dir: (reading("drive-9", FOUND, items=[item]),))
    row = d.propose(tmp_path, profile)[0]
    assert "pat@example.org" not in row["comment"] and "916-555-0100" not in row["comment"]


def test_every_act_names_who_and_a_proposed_row_cannot_be_cleared_first(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    with pytest.raises(ValueError, match="who is recording"):
        d.confirm(tmp_path, ident, by=" ")
    with pytest.raises(ValueError, match="only proposed"):
        d.set_impairs(tmp_path, ident, True, by="Pat Example")
    with pytest.raises(ValueError, match="only proposed"):
        d.clear(tmp_path, ident, record="drive-2", kind="later passing report", on="2026-06-02", by="Pat Example")
    d.confirm(tmp_path, ident, by="Pat Example", now="2026-10-04T01:00:00+00:00")
    row = d.load(tmp_path)[0]
    assert [a["act"] for a in row["acts"]] == ["proposed", "confirmed"] and row["acts"][1]["by"] == "Pat Example"
    d.confirm(tmp_path, ident, by="Someone Else")                  # confirming again changes nothing
    assert len(d.load(tmp_path)[0]["acts"]) == 2


def test_impairment_is_a_persons_word_and_the_latest_word_wins(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    d.confirm(tmp_path, ident, by="Pat Example")
    assert d.state_of(d.load(tmp_path)[0])["impairs"] is None
    d.set_impairs(tmp_path, ident, True, by="Pat Example")
    s = d.state_of(d.load(tmp_path)[0])
    assert s["impairs"] is True and s["impairmentOpen"] and s["insurerNotTold"]
    d.set_impairs(tmp_path, ident, False, by="Lee President")
    assert d.state_of(d.load(tmp_path)[0])["impairs"] is False
    assert len(d.load(tmp_path)[0]["acts"]) == 4                  # the first word is still there


def test_the_insurer_notice_clears_the_flag_and_records_what_a_person_did(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    d.confirm(tmp_path, ident, by="Pat Example")
    d.set_impairs(tmp_path, ident, True, by="Pat Example")
    with pytest.raises(ValueError, match="not words"):
        d.insurer_told(tmp_path, ident, record="the email to the agent", on="2026-10-02", by="Pat Example")
    with pytest.raises(ValueError, match="future"):
        d.insurer_told(tmp_path, ident, record="gmail:abc", on="2999-01-01", by="Pat Example")
    d.insurer_told(tmp_path, ident, record="gmail:abc", on="2026-10-02", by="Pat Example", today=date(2026, 10, 4))
    s = d.state_of(d.load(tmp_path)[0])
    assert s["impairmentOpen"] is True and s["insurerNotTold"] is False
    assert s["insurerTold"]["inLibrary"] is False and s["insurerTold"]["record"] == "gmail:abc"


def test_a_deficiency_is_cleared_only_by_a_record_in_the_library(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    d.confirm(tmp_path, ident, by="Pat Example")
    with pytest.raises(ValueError, match="kind is one of"):
        d.clear(tmp_path, ident, record="drive-2", kind="subject line", on="2026-06-02", by="Pat Example")
    with pytest.raises(ValueError, match="not in the library"):
        d.clear(tmp_path, ident, record="drive-404", kind="invoice line items", on="2026-06-02", by="Pat Example")
    with pytest.raises(ValueError, match="not after the report"):
        d.clear(tmp_path, ident, record="drive-3", kind="later passing report", on="2026-06-02", by="Pat Example")
    with pytest.raises(ValueError, match="does not read as a passing"):
        d.clear(tmp_path, ident, record="drive-1", kind="later passing report", on="2026-06-02", by="Pat Example")
    d.clear(tmp_path, ident, record="drive-2", kind="later passing report", on="2026-06-02", by="Pat Example")
    s = d.state_of(d.load(tmp_path)[0])
    assert s["standing"] == "cleared" and s["cleared"]["record"] == "drive-2" and not s["impairmentOpen"]


def test_the_view_gives_counts_and_withholds_the_detail_from_a_viewer_who_may_not_see_it(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    d.confirm(tmp_path, ident, by="Pat Example")
    d.set_impairs(tmp_path, ident, True, by="Pat Example")
    full = d.view(tmp_path, today=TODAY)
    assert full["counts"] == {"proposed": 0, "open": 1, "cleared": 0, "impairments": 1, "insurerNotTold": 1, "urgent": 1,
                              "overdueDeadlines": 0}
    assert full["rows"][0]["impairmentOpen"] is True
    held = d.view(tmp_path, detail=False, today=TODAY)
    # what reveals an impairment is null, never a bare zero, for a viewer without P2
    assert held["counts"] == {**full["counts"], "impairments": None, "insurerNotTold": None, "urgent": None}
    assert held["rows"] == [] and "P2" in held["held"]
    assert d.view(tmp_path, system="risers")["counts"]["open"] == 0


def test_the_store_is_one_file_under_life_safety(tmp_path, lib, profile):
    d.propose(tmp_path, profile)
    assert json.loads((tmp_path / "life-safety" / "deficiencies.json").read_text(encoding="utf-8"))["deficiencies"]


def test_the_command_lists_confirms_and_refuses_without_a_name(tmp_path, lib, profile, monkeypatch, capsys):
    import argparse

    from jason.commands import life_safety as cmd

    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: tmp_path)
    monkeypatch.setattr("jason.community.community", lambda: profile)

    def run(**kw):
        base = dict(list=False, system=None, json=False, propose=False, confirm=None, impairs=None, value=None, cleared=None,
                    insurer_told=None, record=None, kind=None, on=None, by="")
        return cmd.cmd_life_safety(argparse.Namespace(**{**base, **kw}))

    assert run(propose=True) == 0 and "1 proposed" in capsys.readouterr().out
    ident = d.load(tmp_path)[0]["id"]
    assert run(confirm=ident) == 2 and "who is recording" in capsys.readouterr().err
    assert run(confirm=ident, by="Pat Example") == 0
    capsys.readouterr()
    assert run(impairs=ident, value="maybe", by="Pat Example") == 2
    assert run() == 0 and "1 open" in capsys.readouterr().out
    assert run(confirm=ident, propose=True, by="x") == 2


# --- severity, deadline, and the board item ---------------------------------------------------------------------------

from jason.community.board_items import ItemCategory, ItemStatus, Priority  # noqa: E402
from jason.tasks import board_items  # noqa: E402


def item_of(tmp_path, ident):
    found = [i for i in board_items.load(tmp_path) if i.id == d.item_id(ident)]
    assert len(found) <= 1                                         # never a duplicate
    return found[0] if found else None


@pytest.fixture
def confirmed(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    d.confirm(tmp_path, ident, by="Pat Example", now="2026-10-04T01:00:00+00:00", today=TODAY)
    return ident


def test_confirming_makes_one_proposed_board_item_with_a_proposed_priority(tmp_path, confirmed):
    ident = confirmed
    item = item_of(tmp_path, ident)
    assert item.category is ItemCategory.SAFETY and item.status is ItemStatus.PROPOSED and item.source == d.ITEM_SOURCE
    assert item.priority is Priority.NORMAL and item.due is None and item.ask == d.ITEM_ASK
    assert "priority proposed: normal" in item.summary and "jason's proposal, not a legal standard" in item.summary
    assert "Waterflow switch" in item.title and "Fire alarm, buildings A and B" in item.title
    assert "Failed to transmit" in item.summary and "Confirmed by Pat Example" in item.summary
    assert item.authority.startswith("Inspection report: Report drive-1.pdf") and item.evidence[0] == "Drive: Report drive-1.pdf"
    assert d.confirm(tmp_path, ident, by="Someone Else", today=TODAY)["boardItem"]["ok"] is True
    assert item_of(tmp_path, ident) is not None and len(board_items.load(tmp_path)) == 1


def test_a_proposed_row_has_no_board_item(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    assert d.sync_board_items(tmp_path, today=TODAY)["items"] == [] and board_items.load(tmp_path) == []
    assert item_of(tmp_path, ident) is None


def test_the_proposed_priority_is_one_rule():
    base = {"insurerNotTold": False, "impairmentOpen": False, "deadline": None, "cleared": None}
    assert d.proposed_priority(base, TODAY)[0] is Priority.NORMAL
    assert d.proposed_priority({**base, "impairmentOpen": True}, TODAY)[0] is Priority.HIGH
    assert d.proposed_priority({**base, "impairmentOpen": True, "insurerNotTold": True}, TODAY)[0] is Priority.URGENT
    near = {**base, "deadline": "2026-10-25"}                      # 14 days: inside jason's window
    assert d.proposed_priority(near, TODAY)[0] is Priority.HIGH
    assert d.proposed_priority({**base, "deadline": "2026-10-26"}, TODAY)[0] is Priority.NORMAL    # 15 days: outside
    assert d.proposed_priority({**near, "impairmentOpen": True}, TODAY)[0] is Priority.URGENT
    assert d.proposed_priority({**near, "impairmentOpen": True, "insurerNotTold": True}, TODAY)[0] is Priority.URGENT
    assert d.proposed_priority({**base, "deadline": "2026-10-01"}, TODAY)[0] is Priority.HIGH      # overdue
    assert d.proposed_priority({**near, "cleared": {"on": "x"}}, TODAY)[0] is Priority.NORMAL      # a cleared one presses no deadline
    assert d.DEADLINE_WINDOW_DAYS == 14


def test_an_impairment_with_no_insurer_notice_is_urgent_and_the_notice_lowers_the_proposal(tmp_path, confirmed):
    d.set_impairs(tmp_path, confirmed, True, by="Pat Example", today=TODAY)
    item = item_of(tmp_path, confirmed)
    assert item.priority is Priority.URGENT and "priority proposed: urgent" in item.summary
    assert "No record shows the insurer was told" in item.summary
    d.insurer_told(tmp_path, confirmed, record="gmail:abc", on="2026-10-02", by="Pat Example", today=TODAY)
    item = item_of(tmp_path, confirmed)
    assert item.priority is Priority.HIGH and "The insurer was told on 2026-10-02" in item.summary
    d.set_impairs(tmp_path, confirmed, False, by="Pat Example", today=TODAY)
    assert item_of(tmp_path, confirmed).priority is Priority.NORMAL


def test_a_persons_severity_replaces_the_proposal_and_is_never_raised_by_a_deadline(tmp_path, confirmed):
    d.set_impairs(tmp_path, confirmed, True, by="Pat Example", today=TODAY)
    with pytest.raises(ValueError, match="value is one of"):
        d.set_severity(tmp_path, confirmed, "critical", by="Pat Example", today=TODAY)
    row = d.set_severity(tmp_path, confirmed, "normal", by="Lee President", today=TODAY)
    assert d.state_of(row)["severity"] == "normal" and row["boardItem"]["ok"] is True
    item = item_of(tmp_path, confirmed)
    assert item.priority is Priority.NORMAL and "priority: normal, set by Lee President" in item.summary
    assert "priority proposed" not in item.summary
    d.set_deadline(tmp_path, confirmed, day="2026-10-12", basis="insurer", by="Pat Example", today=TODAY)
    assert item_of(tmp_path, confirmed).priority is Priority.NORMAL          # a near deadline does not raise a person's word
    d.set_severity(tmp_path, confirmed, "high", by="Pat Example", today=TODAY)  # the latest word wins
    assert item_of(tmp_path, confirmed).priority is Priority.HIGH


def test_a_near_deadline_raises_the_proposal_one_step_and_is_the_due_date(tmp_path, confirmed):
    row = d.set_deadline(tmp_path, confirmed, day="2026-10-20", basis="insurer", record="gmail:abc", by="Pat Example", today=TODAY)
    act = d.state_of(row)["deadlineBy"]
    assert act["basis"] == "insurer" and act["record"] == "gmail:abc" and act["by"] == "Pat Example"
    item = item_of(tmp_path, confirmed)
    assert item.due == date(2026, 10, 20) and item.priority is Priority.HIGH
    assert "default window of 14 days (not the law's)" in item.summary
    assert "Deadline 2026-10-20, set by insurer" in item.summary and "deadline per insurer, record gmail:abc" in item.authority
    d.set_deadline(tmp_path, confirmed, day="2026-12-31", basis="vendor", by="Pat Example", today=TODAY)   # the latest wins
    item = item_of(tmp_path, confirmed)
    assert item.due == date(2026, 12, 31) and item.priority is Priority.NORMAL


def test_a_deadline_is_a_persons_dated_word_and_bad_ones_are_refused(tmp_path, confirmed):
    def go(**kw):
        return d.set_deadline(tmp_path, confirmed, **{"day": "2026-11-01", "basis": "person", "by": "Pat Example", "today": TODAY, **kw})

    with pytest.raises(ValueError, match="who is recording"):
        go(by=" ")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        go(day="next week")
    with pytest.raises(ValueError, match="more than a year"):
        go(day="2025-10-10")
    with pytest.raises(ValueError, match="basis is one of"):
        go(basis="jason")
    with pytest.raises(ValueError, match="not words"):
        go(record="the agent's email")
    assert d.state_of(d.load(tmp_path)[0])["deadline"] is None            # nothing was recorded
    go(day="2025-10-11")                                                  # a year back to the day: overdue, real
    assert d.state_of(d.load(tmp_path)[0])["deadline"] == "2025-10-11"
    with pytest.raises(ValueError, match="who is recording"):
        d.set_severity(tmp_path, confirmed, "high", by="", today=TODAY)


def test_severity_and_deadline_need_a_confirmed_row(tmp_path, lib, profile):
    ident = d.propose(tmp_path, profile)[0]["id"]
    with pytest.raises(ValueError, match="only proposed"):
        d.set_severity(tmp_path, ident, "high", by="Pat Example", today=TODAY)
    with pytest.raises(ValueError, match="only proposed"):
        d.set_deadline(tmp_path, ident, day="2026-11-01", basis="person", by="Pat Example", today=TODAY)


def test_a_later_act_refreshes_the_same_item_and_keeps_what_the_board_set(tmp_path, confirmed):
    board_items.set_fields(tmp_path, d.item_id(confirmed), status="in progress", owner="Treasurer", meeting="2026-11-17",
                           notes="Vendor asked for a quote", today=TODAY)
    d.set_impairs(tmp_path, confirmed, True, by="Pat Example", today=TODAY)
    d.set_deadline(tmp_path, confirmed, day="2026-10-15", basis="authority", by="Pat Example", today=TODAY)
    assert len(board_items.load(tmp_path)) == 1
    item = item_of(tmp_path, confirmed)
    assert item.priority is Priority.URGENT and item.due == date(2026, 10, 15)               # jason's fields refreshed
    assert (item.status, item.owner, item.meeting, item.notes) == (ItemStatus.IN_PROGRESS, "Treasurer", "2026-11-17",
                                                                   "Vendor asked for a quote")   # the board's kept


def test_clearing_refreshes_the_summary_and_closes_nothing(tmp_path, confirmed):
    d.set_impairs(tmp_path, confirmed, True, by="Pat Example", today=TODAY)
    row = d.clear(tmp_path, confirmed, record="drive-2", kind="later passing report", on="2026-06-02", by="Pat Example", today=TODAY)
    assert row["boardItem"]["ok"] is True
    item = item_of(tmp_path, confirmed)
    assert item.status is ItemStatus.PROPOSED and "cleared by drive-2 on 2026-06-02" in item.summary
    assert "the board closes this item" in item.summary and item.priority is Priority.NORMAL


def test_a_cleared_row_with_no_item_gets_none(tmp_path, confirmed):
    (tmp_path / "board" / "items.json").unlink()                      # the item is gone (a failed write earlier, say)
    d.clear(tmp_path, confirmed, record="drive-2", kind="later passing report", on="2026-06-02", by="Pat Example", today=TODAY)
    assert board_items.load(tmp_path) == []


def test_a_failure_writing_the_board_item_leaves_the_act_recorded_and_says_so(tmp_path, lib, profile, monkeypatch):
    ident = d.propose(tmp_path, profile)[0]["id"]

    def boom(*a, **k):
        raise OSError("disk full")

    with monkeypatch.context() as m:
        m.setattr(board_items, "propose", boom)
        row = d.confirm(tmp_path, ident, by="Pat Example", today=TODAY)
    assert row["boardItem"]["ok"] is False and "disk full" in row["boardItem"]["why"]
    assert d.state_of(d.load(tmp_path)[0])["standing"] == "open"          # the act stands
    assert any("NOT written (OSError: disk full)" in line for line in d.lines([row]))
    assert d.sync_board_items(tmp_path, today=TODAY)["added"] == [d.item_id(ident)]    # a later sync repairs it


def _row(ident, day, acts, system="alarm"):
    return {"id": ident, "system": system, "buildings": ["A"], "report": {"id": "drive-1", "name": "r.pdf", "day": day, "where": "Drive"},
            "location": "", "device": f"Device {ident}", "comment": "failed", "source": "x",
            "acts": [{"act": "proposed", "at": "t"}, *acts]}


def _act(name, **kw):
    return {"act": name, "by": "Pat Example", "at": "2026-10-01T00:00:00+00:00", **kw}


def _store(tmp_path, rows):
    (tmp_path / "life-safety").mkdir()
    (tmp_path / "life-safety" / "deficiencies.json").write_text(json.dumps({"deficiencies": rows}), encoding="utf-8")


def test_the_view_sorts_by_priority_then_deadline_then_found_and_counts_are_right(tmp_path):
    confirmed_ = [_act("confirmed")]
    _store(tmp_path, [
        _row("def-c", "2026-01-01", confirmed_),
        _row("def-a", "2026-02-01", confirmed_ + [_act("deadline", date="2026-12-01", basis="vendor")]),
        _row("def-d", "2026-03-01", confirmed_ + [_act("deadline", date="2026-11-20", basis="documents")]),
        _row("def-g", "2026-04-01", confirmed_ + [_act("deadline", date="2026-10-01", basis="insurer")]),    # overdue
        _row("def-b", "2026-05-01", confirmed_ + [_act("impairs")]),                                       # urgent
        _row("def-e", "2026-06-01", []),                                                                   # only proposed
        _row("def-z", "2026-07-01", confirmed_ + [_act("cleared", record="drive-2", kind="other record", on="2026-09-01")])])
    d.sync_board_items(tmp_path, today=TODAY)
    out = d.view(tmp_path, today=TODAY)
    assert [r["id"] for r in out["rows"]] == ["def-b", "def-g", "def-d", "def-a", "def-c", "def-e", "def-z"]
    assert out["counts"] == {"proposed": 1, "open": 5, "cleared": 1, "impairments": 1, "insurerNotTold": 1, "urgent": 1,
                             "overdueDeadlines": 1}
    by_id = {r["id"]: r for r in out["rows"]}
    assert by_id["def-b"]["priority"]["value"] == "urgent" and by_id["def-b"]["priority"]["proposed"] is True
    assert by_id["def-g"]["priority"]["value"] == "high" and by_id["def-g"]["deadline"] == "2026-10-01"
    assert by_id["def-c"]["severity"] is None and by_id["def-c"]["deadline"] is None
    assert by_id["def-b"]["boardItem"] == {"id": "life-safety-def-b", "status": "proposed"}
    assert by_id["def-e"]["boardItem"] is None


def test_a_persons_severity_in_the_view_is_not_proposed(tmp_path):
    _store(tmp_path, [_row("def-a", "2026-02-01", [_act("confirmed"), _act("severity", value="urgent")])])
    out = d.view(tmp_path, today=TODAY)
    assert out["rows"][0]["priority"]["proposed"] is False and out["rows"][0]["severity"] == "urgent" and out["counts"]["urgent"] == 1
    assert d.view(tmp_path, detail=False, today=TODAY)["counts"]["urgent"] is None


def test_the_command_records_severity_and_deadline_and_lists_them(tmp_path, confirmed, profile, monkeypatch, capsys):
    import argparse

    from jason.commands import life_safety as cmd

    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: tmp_path)
    monkeypatch.setattr("jason.community.community", lambda: profile)

    def run(**kw):
        base = dict(list=False, system=None, json=False, propose=False, confirm=None, impairs=None, value=None, cleared=None,
                    insurer_told=None, severity=None, deadline=None, date=None, basis=None, record=None, kind=None, on=None, by="")
        return cmd.cmd_life_safety(argparse.Namespace(**{**base, **kw}))

    capsys.readouterr()
    assert run(severity=confirmed, value="high") == 2 and "who is recording" in capsys.readouterr().err
    assert run(severity=confirmed, value="yes", by="Pat Example") == 2
    assert run(severity=confirmed, value="high", by="Pat Example") == 0
    assert "high" in capsys.readouterr().out
    assert run(deadline=confirmed, date="2999-01-01", basis="person", by="Pat Example") == 0
    assert "deadline 2999-01-01 (person)" in capsys.readouterr().out
    assert run(deadline=confirmed, date="soon", basis="person", by="Pat Example") == 2
    assert run(deadline=confirmed, severity=confirmed, by="x") == 2
    capsys.readouterr()
    assert run() == 0
    listing = capsys.readouterr().out
    assert "0 urgent" in listing and "past a recorded deadline" in listing
