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
    full = d.view(tmp_path)
    assert full["counts"] == {"proposed": 0, "open": 1, "cleared": 0, "impairments": 1, "insurerNotTold": 1}
    assert full["rows"][0]["impairmentOpen"] is True
    held = d.view(tmp_path, detail=False)
    assert held["counts"] == full["counts"] and held["rows"] == [] and "P2" in held["held"]
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
