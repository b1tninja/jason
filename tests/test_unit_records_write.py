"""The writes behind a unit's record and the loss packet: validated, attributed, stored, and read back by the views."""

import json

import pytest

from jason.tasks import unit_records_view as view
from jason.tasks import unit_records_write as w
from jason.web.extra import unit_records as web

ENTRY = {"component": "kitchen faucet", "kind": "plumbing fixture", "what": "touchless faucet", "date": "2098-05"}


def test_an_entry_is_validated_attributed_stored_and_private_by_default(tmp_path):
    out = w.add_entry(tmp_path, "7", {**ENTRY, "cost_cents": 41250, "docs": ["drive:abc"]}, by="An Owner")
    assert out["by"] == "An Owner" and out["visibility"] == "private" and out["status"] == "upgrade" and out["id"]
    assert out["cost_cents"] == 41250 and out["docs"] == ["drive:abc"]
    stored = json.loads(next(tmp_path.rglob("entries.json")).read_text(encoding="utf-8"))
    assert [e["id"] for e in stored] == [out["id"]]
    w.add_entry(tmp_path, "7", ENTRY, by="An Owner")
    assert len(json.loads(next(tmp_path.rglob("entries.json")).read_text(encoding="utf-8"))) == 2


@pytest.mark.parametrize("change,message", [
    ({"component": ""}, "component"),
    ({"kind": "napkin"}, "kind is one of"),
    ({"status": "original"}, "records a change"),
    ({"status": "unknown"}, "records a change"),
    ({"status": "sparkly"}, "status is one of"),
    ({"visibility": "everyone"}, "visibility is one of"),
    ({"cost_cents": -5}, "whole cents"),
    ({"cost_cents": 12.5}, "whole cents"),
    ({"date": "last spring"}, "YYYY"),
    ({"docs": "drive:abc"}, "list of evidence addresses"),
])
def test_a_malformed_entry_is_refused(tmp_path, change, message):
    with pytest.raises(ValueError, match=message):
        w.add_entry(tmp_path, "7", {**ENTRY, **change}, by="An Owner")
    assert not list(tmp_path.rglob("entries.json"))


def test_a_record_with_no_person_is_refused_and_a_unit_id_cannot_climb_out(tmp_path):
    with pytest.raises(ValueError, match="who made it"):
        w.add_entry(tmp_path, "7", ENTRY, by="  ")
    with pytest.raises(ValueError):
        w.add_entry(tmp_path, "../..", ENTRY, by="An Owner")


def test_visibility_changes_one_entry_and_is_logged_and_the_view_follows(tmp_path):
    first = w.add_entry(tmp_path, "7", ENTRY, by="An Owner")
    w.add_entry(tmp_path, "7", {**ENTRY, "what": "second"}, by="An Owner")
    out = w.set_visibility(tmp_path, "7", first["id"], "shared", by="An Owner")
    assert out["visibility"] == "shared" and "private to shared by An Owner" in out["visibilityHistory"][0]
    entries, held = view._entries(tmp_path, "7", owner=False)
    assert [e.id for e in entries] == [first["id"]] and held == 1
    with pytest.raises(KeyError):
        w.set_visibility(tmp_path, "7", "nope", "shared", by="An Owner")
    with pytest.raises(ValueError):
        w.set_visibility(tmp_path, "7", first["id"], "world", by="An Owner")


def test_a_confirmation_is_a_person_s_and_replaces_that_step_only(tmp_path):
    one = w.confirm_step(tmp_path, "7", "inc-1", 1, shows=["the faucet is an upgrade"], by="A Manager")
    assert one["confirmed_by"] == "A Manager" and one["confirmed_at"] and one["step"] == 1
    w.confirm_step(tmp_path, "7", "inc-1", 2, shows=["the leak began upstairs"], by="A Manager", note="per the plumber")
    w.confirm_step(tmp_path, "7", "inc-1", 1, shows=["corrected"], by="A Director")
    saved = json.loads(next(tmp_path.rglob("inc-1.json")).read_text(encoding="utf-8"))
    assert saved["steps"]["1"]["shows"] == ["corrected"] and saved["steps"]["1"]["confirmed_by"] == "A Director"
    assert saved["steps"]["2"]["confirmed_by"] == "A Manager" and saved["notes"] == {"2": "per the plumber"}


@pytest.mark.parametrize("step,shows,by,message", [
    (0, ["x"], "A", "from 1 to 5"), (6, ["x"], "A", "from 1 to 5"), (True, ["x"], "A", "from 1 to 5"),
    (1, [], "A", "what the record shows"), (1, ["x"], "", "who made it"),
])
def test_a_bad_confirmation_is_refused(tmp_path, step, shows, by, message):
    with pytest.raises(ValueError, match=message):
        w.confirm_step(tmp_path, "7", "inc-1", step, shows=shows, by=by)


def test_the_web_writers_route_by_key_and_take_the_name_from_the_request_when_no_one_is_signed_in(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "_root", lambda: tmp_path)
    entry = web.write_unit_record("entry", {"unit": "7", "by": "An Owner", **ENTRY})
    assert entry["by"] == "An Owner"
    shared = web.write_unit_record("visibility", {"unit": "7", "id": entry["id"], "visibility": "association", "by": "An Owner"})
    assert shared["visibility"] == "association"
    step = web.write_loss_packet("confirm", {"unit": "7", "incident": "inc-9", "step": 3, "shows": ["on file"], "by": "A Manager"})
    assert step["step"] == 3 and step["incident"] == "inc-9"
    with pytest.raises(KeyError):
        web.write_unit_record("delete", {"unit": "7"})
    with pytest.raises(KeyError):
        web.write_loss_packet("approve", {"unit": "7"})
    with pytest.raises(ValueError, match="who made it"):
        web.write_unit_record("entry", {"unit": "7", **ENTRY})
