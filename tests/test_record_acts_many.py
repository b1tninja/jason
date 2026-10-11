"""Record intake, phase 4 backend: several files in one pick, the collision's `current` act, and a bound folder's counts from the last
listing. The phase-2 world (a fake Drive that refuses any write, a made-up association, a data folder of its own); nothing reaches Google."""

import json
from types import SimpleNamespace

import pytest

import webclient
from jason.community.symbols import DocumentKind
from jason.tasks import drive_choose as dc
from jason.tasks import record_acts as acts
from jason.tasks import record_slots as rs

from test_record_intake_phase2 import (BY, FILE_A, FILE_B, FILE_C, FOLDER, NAME_A, _app, world)  # noqa: F401  (world is a fixture)

SERIES = "records/5200/minutes"
SEVERAL = "governing/policies-resolutions"
ONE = "records/5200/membership_list"


def kw(world):
    return {"by": BY, "community": world.community, "root": world.root, "profile": "example"}


def pins(world):
    path = world.spec / "example" / "records.json"
    return json.loads(path.read_text(encoding="utf-8"))["pins"] if path.is_file() else []


def history(world):
    path = world.root / "records" / "history.jsonl"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def test_several_files_in_one_pick_are_each_a_pin_and_each_checked_first(world):
    dry = acts.pick_many(SEVERAL, [FILE_A, FILE_B, FILE_A], **kw(world))
    assert dry["dryRun"] is True and dry["counts"] == {"pin": 2, "already": 0, "collision": 0, "duplicate": 1, "refused": 0}
    assert [p["action"] for p in dry["parts"]] == ["pin", "pin", "duplicate"] and pins(world) == []
    done = acts.pick_many(SEVERAL, [FILE_A, FILE_B, FILE_A], dry_run=False, **kw(world))
    assert done["ok"] and len(done["pins"]) == 2 and len({p["ref"] for p in pins(world)}) == 2
    again = acts.pick_many(SEVERAL, [FILE_A, FILE_B], dry_run=False, **kw(world))
    assert [p["action"] for p in again["parts"]] == ["already", "already"] and again["pins"] == [] and len(pins(world)) == 2
    text = history(world)
    assert '"act": "pick-many"' in text and NAME_A not in text and FILE_A not in text      # ids of pins, never a file name or a Drive id
    assert world.drive.writes == []


def test_a_series_needs_a_period_for_each_file_and_a_period_already_held_is_a_collision(world):
    out = acts.pick_many(SERIES, [{"file": FILE_A, "period": "2099-06"}, {"file": FILE_B}, {"file": FILE_C, "period": "2099-07"}],
                         dry_run=False, **kw(world))
    assert [p["action"] for p in out["parts"]] == ["pin", "refused", "pin"] and "name this file's period" in out["parts"][1]["why"]
    assert sorted(p["period"] for p in pins(world)) == ["2099-06", "2099-07"]
    clash = acts.pick_many(SERIES, [{"file": FILE_B, "period": "2099-06"}], dry_run=False, **kw(world))
    assert clash["parts"][0]["action"] == "collision" and clash["pins"] == [] and len(pins(world)) == 2
    bad = acts.pick_many(SERIES, [{"file": FILE_B, "period": "2099-6"}], **kw(world))
    assert bad["parts"][0]["action"] == "refused" and "period is" in bad["parts"][0]["why"]
    shared = acts.pick_many(SERIES, [FILE_B, FILE_C], period="2099-08", dry_run=False, **kw(world))   # one period for two files: the second waits
    assert [p["action"] for p in shared["parts"]] == ["pin", "collision"] and len(pins(world)) == 3


def test_a_slot_that_holds_one_takes_one_and_a_filled_one_is_a_collision(world):
    with pytest.raises(ValueError, match="holds one file"):
        acts.pick_many(ONE, [FILE_A, FILE_B], **kw(world))
    first = acts.pick_many(ONE, [FILE_A], dry_run=False, **kw(world))
    assert first["counts"]["pin"] == 1
    second = acts.pick_many(ONE, [FILE_B], dry_run=False, **kw(world))
    assert second["parts"][0]["action"] == "collision" and len(pins(world)) == 1
    with pytest.raises(ValueError, match="at most 100"):
        acts.pick_many(SEVERAL, [FILE_A] * 101, **kw(world))
    with pytest.raises(ValueError, match="at least one"):
        acts.pick_many(SEVERAL, [], **kw(world))
    with pytest.raises(ValueError, match="person"):
        acts.pick_many(SEVERAL, [FILE_A], by="jason", community=world.community, root=world.root, profile="example")


def two_holders(world):
    a = rs.pick(ONE, FILE_A, dry_run=False, **kw(world))["pin"]
    b = rs.pick(ONE, FILE_B, dry_run=False, **kw(world))["pin"]
    return a, b


def test_current_says_which_holder_stands_unpins_the_other_and_keeps_the_reason_out_of_the_history(world):
    a, b = two_holders(world)
    assert any(c.collisions for c in rs.compute(world.community, world.root, "example") if c.slot.key == ONE)
    with pytest.raises(ValueError, match="reason"):
        acts.current(ONE, pin=a, reason="", **kw(world))
    with pytest.raises(ValueError, match="name the pin"):
        acts.current(ONE, pin="p-nope", reason="the signed copy", **kw(world))
    dry = acts.current(ONE, pin=a, reason="the signed copy", **kw(world))
    assert dry["dryRun"] and dry["would"]["unpins"] == [b] and len(pins(world)) == 2 and not acts.currents("example")
    done = acts.current(ONE, pin=a, reason="the signed copy", dry_run=False, **kw(world))
    assert done["ok"] and done["unpinned"] == [b] and done["stillTwo"] is False and done["patch"] is None
    assert not [c for c in rs.compute(world.community, world.root, "example") if c.slot.key == ONE and c.collisions]
    row = acts.currents("example", ONE)[0]
    assert row["pin"] == a and row["superseded"] == [b] and row["by"] == BY and row["reason"] == "the signed copy"
    text = history(world)
    assert '"act": "current"' in text and "the signed copy" not in text and NAME_A not in text
    with pytest.raises(ValueError, match="no two holders"):
        acts.current(ONE, pin=a, reason="again", **kw(world))


def test_a_holder_the_specification_pins_comes_back_as_a_patch_and_the_slot_keeps_showing_two(world):
    world.community.pins = lambda: (SimpleNamespace(kind=DocumentKind.MEMBERSHIP_LIST, drive_id=FILE_C, title="Specification copy"),)
    mine = rs.pick(ONE, FILE_A, dry_run=False, **kw(world))["pin"]
    coded = next(c for c in rs.compute(world.community, world.root, "example") if c.slot.key == ONE).collisions[0]["holders"]
    code_pin = next(h["pin"] for h in coded if h["origin"] == "specification")
    done = acts.current(ONE, pin=mine, reason="the board adopted this one", dry_run=False, **kw(world))
    assert done["stillTwo"] is True and code_pin in done["patch"]["text"] and "applies it; jason edits nothing" in done["patch"]["text"]
    assert done["unpinned"] == [] and any(c.collisions for c in rs.compute(world.community, world.root, "example") if c.slot.key == ONE)


def test_a_bound_folders_counts_come_from_the_last_listing_and_never_call_drive(world):
    bound = acts.bind(SERIES, FOLDER, dry_run=False, **kw(world))
    before = dc.binding_counts(SERIES, community=world.community, root=world.root, profile="example")
    assert before["bindings"][0]["listed"] is False and "has not been listed" in before["bindings"][0]["note"]
    assert world.drive.calls == [] and bound["binding"] == before["bindings"][0]["binding"]
    listed = dc.bound_files(world.drive, FOLDER, SERIES, community=world.community, root=world.root, profile="example")
    calls = len(world.drive.calls)
    rs.pick(SERIES, FILE_A, period="2099-06", dry_run=False, **kw(world))
    card = dc.binding_counts(SERIES, community=world.community, root=world.root, profile="example")["bindings"][0]
    assert len(world.drive.calls) == calls                                           # counting asked Google nothing
    assert card["listed"] and card["files"] == listed["counts"]["files"] == 3
    assert (card["here"], card["elsewhere"], card["nowhere"]) == (listed["counts"]["here"], listed["counts"]["elsewhere"], listed["counts"]["nowhere"])
    assert card["pinned"] == 1 and card["read"] == 0 and card["notPinned"] == 2 and card["more"] is False
    raw = (world.root / "records" / "binding-listings.json").read_text(encoding="utf-8")
    assert NAME_A not in raw and "Secret" not in raw                                  # ids and fits, no name
    assert dc.binding_counts(ONE, community=world.community, root=world.root, profile="example")["bindings"] == []


def test_the_console_routes_take_several_files_settle_a_collision_and_count_a_binding(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    url = "/api/write/records/" + SEVERAL
    dry = c.post(url, json={"act": "pick", "files": [FILE_A, FILE_B], "by": BY, "dryRun": True})
    assert dry.status_code == 200 and dry.json["counts"]["pin"] == 2 and pins(world) == []
    wet = c.post(url, json={"act": "pick", "files": [FILE_A, FILE_B], "by": BY})
    assert wet.status_code == 200 and len(wet.json["pins"]) == 2 and wet.json["parts"][0]["action"] == "pin"
    assert c.post(url, json={"act": "pick", "file": FILE_A, "files": [FILE_B], "by": BY}).status_code == 400
    a, b = two_holders(world)
    refused = c.post("/api/write/records/" + ONE, json={"act": "current", "pin": a, "by": BY})
    assert refused.status_code == 400 and "reason" in json.dumps(refused.json)
    done = c.post("/api/write/records/" + ONE, json={"act": "current", "pin": a, "note": "the signed copy", "by": BY})
    assert done.status_code == 200 and done.json["unpinned"] == [b] and done.json["pin"] == a
    acts.bind(SERIES, FOLDER, dry_run=False, **kw(world))
    got = c.get("/api/record-bindings?key=" + SERIES)
    assert got.status_code == 200 and got.json["bindings"][0]["listed"] is False
    assert c.get("/api/record-bindings").status_code == 400
    assert c.get("/api/record-bindings?key=" + SERIES + "&view=owner").status_code == 403


def _cli(world, monkeypatch, *argv):
    import argparse

    from jason.commands import record_slots as command

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    command.register(sub, lambda p: (p.add_argument("--interactive", action="store_true"), p.add_argument("--data-dir", default=None)), lambda a: None)
    args = parser.parse_args(["records", *argv])
    monkeypatch.setattr(command, "_community", lambda: world.community)
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda a: world.root)
    return args.func(args)


def test_the_commands_pick_several_settle_a_collision_and_count_a_binding(world, monkeypatch, capsys):
    assert _cli(world, monkeypatch, "--pick", SEVERAL, "--file", FILE_A, "--also", FILE_B, "--by", BY) == 0
    out = capsys.readouterr().out
    assert "dry run: would pin 2 of 2 files" in out and pins(world) == []
    assert _cli(world, monkeypatch, "--pick", SEVERAL, "--file", FILE_A, "--also", FILE_B, "--by", BY, "--yes") == 0
    assert "pinned 2 of 2 files" in capsys.readouterr().out and len(pins(world)) == 2
    a, b = two_holders(world)
    assert _cli(world, monkeypatch, "--current", ONE, "--pin", a, "--reason", "the signed copy", "--by", BY) == 0
    assert "dry run: would write" in capsys.readouterr().out
    assert _cli(world, monkeypatch, "--current", ONE, "--pin", a, "--reason", "the signed copy", "--by", BY, "--yes") == 0
    assert acts.currents("example", ONE)[0]["pin"] == a
    acts.bind(SERIES, FOLDER, dry_run=False, **kw(world))
    assert _cli(world, monkeypatch, "--bindings", SERIES) == 0
    assert "not listed yet" in capsys.readouterr().out
