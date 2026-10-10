"""Limits (jason.limits) and the record-intake steps that read them: the upload cap, the split's automatic read-back, a repeating
slot filled by a split, and replacing a file in one act. Fakes only: the phase-2 world, made-up PDFs, no Drive, no Keeper."""

import base64
from types import SimpleNamespace

import pytest

import webclient
from jason import jobs, limits
from jason.tasks import record_slots as rs
from jason.tasks import record_upload as up

from test_record_intake_phase2 import BY, FILE_A, world, store, slot_row, quiet_preflight, _app  # noqa: F401
from test_record_intake_phase3 import BYL, MIN, _combined, _pdf, _split, _up

OTHER = "someone else"


# --- the registry ------------------------------------------------------------------------------------------------------------

def test_every_limit_is_a_record_with_its_range_unit_and_words():
    keys = [l.key for l in limits.all_limits()]
    assert keys == ["upload.max_bytes", "fetch.max_bytes", "split.auto_read", "split.thumbnail_cache_bytes", "split.max_pages",
                    "split.max_parts", "split.suggest_enabled", "split.draft_days"] and len(set(keys)) == len(keys)
    for l in limits.all_limits():
        assert l.unit and l.description and l.env_name.startswith("JASON_LIMIT_")
    cap = limits.limit("upload.max_bytes")
    assert (cap.default, cap.minimum, cap.maximum) == (100 * 1024 * 1024, 1024 * 1024, 500 * 1024 * 1024)
    assert limits.limit("split.auto_read").default is True
    with pytest.raises(KeyError):
        limits.limit("nope")


def test_the_source_is_default_then_community_then_instance_then_env(tmp_path, monkeypatch):
    monkeypatch.delenv("JASON_LIMIT_UPLOAD_MAX_BYTES", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("JASON_LIMIT_UPLOAD_MAX_BYTES=3000000\n", encoding="utf-8")
    monkeypatch.setenv("JASON_ENV", str(tmp_path / "absent.env"))
    cap = limits.limit("upload.max_bytes")
    assert cap.effective().source == "default" and cap.effective().value == 100 * 1024 * 1024
    community = SimpleNamespace(limits=lambda: {"upload.max_bytes": 5_000_000})
    got = cap.effective(community=community)
    assert (got.source, got.value) == ("community", 5_000_000)
    got = cap.effective(SimpleNamespace(env_path=env_file), community)
    assert (got.source, got.value) == ("instance", 3_000_000)
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", "2000000")
    got = cap.effective(SimpleNamespace(env_path=env_file), community)
    assert (got.source, got.value, got.raw) == ("env", 2_000_000, "2000000")


def test_a_value_outside_the_range_is_held_to_it_and_an_unreadable_one_is_skipped(monkeypatch):
    cap = limits.limit("upload.max_bytes")
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", "9999999999")
    got = cap.effective()
    assert got.value == 500 * 1024 * 1024 and got.clamped is True and got.source == "env"
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", "1")
    assert cap.effective().value == 1024 * 1024
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", "lots")
    assert cap.effective().source == "default"
    monkeypatch.setenv("JASON_LIMIT_SPLIT_AUTO_READ", "off")
    assert limits.limit("split.auto_read").effective().value is False
    monkeypatch.setenv("JASON_LIMIT_SPLIT_AUTO_READ", "maybe")
    assert limits.limit("split.auto_read").effective().source == "default"
    broken = SimpleNamespace(limits=lambda: 1 / 0)
    assert cap.effective(community=broken).source == "default"


def test_the_listing_is_read_only_and_the_command_prints_it(capsys, monkeypatch):
    from jason.commands import limits as cmd

    monkeypatch.setenv("JASON_LIMIT_SPLIT_AUTO_READ", "no")
    rows = limits.listing()
    assert {r["key"] for r in rows} == {l.key for l in limits.all_limits()} and len(rows) == 8
    assert next(r for r in rows if r["key"] == "split.auto_read")["source"] == "env"
    assert cmd.cmd_limits(SimpleNamespace(key="", json=False)) == 0
    text = capsys.readouterr().out
    assert "upload.max_bytes = " in text and "split.auto_read = False  [env]" in text
    assert cmd.cmd_limits(SimpleNamespace(key="nope", json=False)) == 2


# --- the upload cap ----------------------------------------------------------------------------------------------------------

def test_the_upload_cap_is_100_mb_unless_set_and_a_community_can_move_it(world, monkeypatch):
    monkeypatch.delenv("JASON_LIMIT_UPLOAD_MAX_BYTES", raising=False)
    assert up.cap_for() == 100 * 1024 * 1024
    big = b"%PDF-" + b"x" * (30 * 1024 * 1024)                               # over the old 25 MB cap, under the new one
    assert up.check("Big.pdf", big)[1] == "a PDF"
    world.community.limits = lambda: {"upload.max_bytes": 2 * 1024 * 1024}
    with pytest.raises(ValueError, match="the limit is 2 MB"):
        _up(world, data=b"%PDF-" + b"x" * (3 * 1024 * 1024))
    # a key document's slot is held to the key documents' own reading of the limit as well
    assert up.cap_for(SimpleNamespace(key_document="bylaws"), world.community) == 2 * 1024 * 1024
    world.community.limits = lambda: {"upload.max_bytes": 300 * 1024 * 1024}
    assert up.cap_for(SimpleNamespace(key_document="bylaws"), world.community) == 100 * 1024 * 1024       # the writer's own reading wins
    assert up.cap_for(SimpleNamespace(key_document=""), world.community) == 300 * 1024 * 1024


# --- the split reads its parts back -----------------------------------------------------------------------------------------

def _read_jobs(world):
    return [j for j in jobs.jobs(world.root, every=True) if j.argv[:2] == ["records", "--read"]]


def test_a_confirmed_split_queues_a_read_back_job_for_each_new_part_in_the_persons_name(world, monkeypatch):
    monkeypatch.delenv("JASON_LIMIT_SPLIT_AUTO_READ", raising=False)
    pin = _combined(world)
    out = _split(world, pin, ["s2=" + MIN + "@2099-06", "s3=governing/operating-rules"])
    assert out["autoRead"] is True and len(out["queued"]) == 2
    queued = _read_jobs(world)
    assert len(queued) == 2 and all("--yes" in j.argv and BY in j.argv for j in queued)
    assert {out["queued"][0]["pin"], out["queued"][1]["pin"]} == {m["pin"] for m in out["filled"]}
    assert all(j.confirmed_by == BY for j in queued)
    assert "queued" in out["reading"]


def test_a_dry_run_and_a_collision_queue_nothing_and_the_limit_can_turn_it_off(world, monkeypatch):
    pin = _combined(world)
    _split(world, pin, ["s2=" + MIN + "@2099-06"], dry_run=True)
    assert _read_jobs(world) == []
    monkeypatch.setenv("JASON_LIMIT_SPLIT_AUTO_READ", "false")
    out = _split(world, pin, ["s2=" + MIN + "@2099-06"])
    assert out["autoRead"] is False and "queued" not in out and "split.auto_read" in out["reading"]
    assert _read_jobs(world) == []


def test_the_console_split_queues_too(world, monkeypatch):
    monkeypatch.delenv("JASON_LIMIT_SPLIT_AUTO_READ", raising=False)
    c = webclient.client(_app(world, monkeypatch))
    pin = _combined(world)
    done = c.post("/api/write/records/" + BYL, json={"act": "split", "pin": pin, "by": BY, "parts": [{"segment": "s2", "slot": MIN, "period": "2099-06"}]})
    assert done.status_code == 200 and len(done.json["queued"]) == 1 and len(_read_jobs(world)) == 1


# --- a repeating slot filled by a split ------------------------------------------------------------------------------------

AMEND = "governing/amendments"


def test_a_part_text_may_name_a_recording_number_after_a_hash(world):
    assert up._parse_part("s2=" + AMEND + "#2099-0000123") == {"segment": "s2", "slot": AMEND, "period": "", "entry": "2099-0000123"}
    assert up._parse_part("s2=" + MIN + "@2099-06#7")["period"] == "2099-06" and up._parse_part("s2=" + MIN + "@2099-06#7")["entry"] == "7"
    assert up._parse_part({"segment": "s1", "slot": AMEND, "entry": " 9 "})["entry"] == "9"


def test_a_split_fills_a_repeating_row_by_its_recording_number_and_each_number_is_its_own_place(world):
    pin = _combined(world)
    with pytest.raises(ValueError, match="recording number"):
        _split(world, pin, ["s2=" + AMEND])
    with pytest.raises(ValueError, match="not a repeating row|takes no instrument"):
        _split(world, pin, ["s2=" + MIN + "@2099-06#5"])
    out = _split(world, pin, ["s2=" + AMEND + "#2099-0000123", "s3=" + AMEND + "#2099-0000124"])
    assert [r["action"] for r in out["parts"]] == ["fill", "fill"] and out["parts"][0]["entry"] == "2099-0000123"
    assert all(m["pin"].startswith("k-") for m in out["filled"])
    from jason.tasks import key_documents as kd

    entries = kd.KeyDocumentStore(world.root, "example").load()["entries"]
    assert {"amendments/2099-0000123", "amendments/2099-0000124"} <= set(entries)
    # the same number again is a collision; a different number is not
    pin2 = pin
    again = _split(world, pin2, ["s1=" + AMEND + "#2099-0000123"])
    assert again["parts"][0]["action"] == "collision" and again["filled"] == []
    other = _split(world, pin2, ["s1=" + AMEND + "#2099-0000125"])
    assert other["parts"][0]["action"] == "fill"


# --- replace -----------------------------------------------------------------------------------------------------------------

def _replace(world, slot=MIN, **kw):
    kw.setdefault("dry_run", False)
    kw.setdefault("read", False)
    kw.setdefault("period", "2099-06" if slot == MIN else "")
    return up.replace(slot, by=BY, community=world.community, root=world.root, profile="example", **kw)


def _active(world, slot):
    return [h["pin"] for h in slot_row(world, slot)["holders"]]


def test_a_dry_run_shows_both_halves_and_writes_nothing(world):
    old = _up(world, data=_pdf(1))["pin"]
    new_bytes = _pdf(2)
    out = _replace(world, data=new_bytes, name="New.pdf", dry_run=True)
    assert out["dryRun"] is True and out["would"]["old"] == old
    assert out["would"]["new"]["act"] == "upload" and out["would"]["unpin"]["act"] == "unpin" and out["would"]["unpin"]["pin"] == old
    assert _active(world, MIN) == [old] and len(store(world)["pins"]) == 1


def test_replace_pins_the_new_file_then_unpins_the_old_and_history_keeps_both(world):
    old = _up(world, data=_pdf(1))["pin"]
    out = _replace(world, data=_pdf(2), name="New.pdf")
    assert out["ok"] and out["replaced"] == old and out["pin"] != old and out["unpinned"]["pin"] == old
    assert _active(world, MIN) == [out["pin"]]
    rows = {p["id"]: p for p in store(world)["pins"]}
    assert rows[old]["unpinned"]["by"] == BY and rows[out["pin"]]["unpinned"] is None            # kept, marked, not deleted
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    assert '"act": "replace"' in history and old in history and "New.pdf" not in history
    kept_files = list((world.root / "record-intake" / "example" / "files").glob("*/*"))
    assert len(kept_files) == 2                                                                  # the old bytes stay too


def test_replace_with_the_same_file_or_with_nothing_to_replace_is_refused(world):
    with pytest.raises(ValueError, match="no pin of a person's to replace"):
        _replace(world, data=_pdf(2), name="New.pdf")
    data = _pdf(1)
    _up(world, data=data)
    with pytest.raises(ValueError, match="already holds"):
        _replace(world, data=data, name="Same.pdf")
    with pytest.raises(ValueError, match="new file"):
        _replace(world)
    with pytest.raises(ValueError, match="not both"):
        _replace(world, data=_pdf(2), name="x.pdf", file="library:9001")
    assert len(_active(world, MIN)) == 1


def test_a_pin_a_person_kept_is_not_replaced_without_force(world):
    old = _up(world, data=_pdf(1))["pin"]
    # a keep is made on a pick jason reads as another kind; the store holds who and why, which is all replace reads
    rs._write_store("example", lambda d: d.setdefault("keeps", []).append(
        {"pin": old, "by": OTHER, "at": "2099-06-01T00:00:00", "reason": "the board confirmed this one"}), purpose="test: keep")
    with pytest.raises(ValueError, match="kept by " + OTHER):
        _replace(world, data=_pdf(2), name="New.pdf")
    with pytest.raises(ValueError, match="kept by"):
        _replace(world, data=_pdf(2), name="New.pdf", dry_run=True)
    assert _active(world, MIN) == [old]
    out = _replace(world, data=_pdf(2), name="New.pdf", force=True)
    assert out["ok"] and out["replaced"] == old


def test_replace_picks_a_library_file_in_place_of_an_upload(world):
    old = _up(world, data=_pdf(1))["pin"]
    out = _replace(world, file="library:9001")
    assert out["ok"] and out["unpinned"]["pin"] == old and _active(world, MIN) == [out["pin"]]
    with pytest.raises(ValueError, match="already holds"):
        _replace(world, file="library:9001")


def test_a_slot_with_two_pins_needs_the_old_one_named_and_a_hidden_slot_is_refused(world):
    one = _up(world, data=_pdf(1), period="2099-06")["pin"]
    two = _up(world, data=_pdf(2), period="2099-07")["pin"]
    with pytest.raises(ValueError, match="name the old one"):
        _replace(world, data=_pdf(3), name="N.pdf")
    out = _replace(world, data=_pdf(3), name="N.pdf", pin=two, period="2099-07")
    assert out["replaced"] == two and one in _active(world, MIN) and two not in _active(world, MIN)
    with pytest.raises(ValueError, match="no active pin"):
        _replace(world, data=_pdf(4), name="O.pdf", pin="p-nope")
    with pytest.raises(ValueError, match="who"):
        up.replace(MIN, by="", data=_pdf(5), name="P.pdf", dry_run=False, community=world.community, root=world.root, profile="example")


def test_the_console_replaces_in_one_act_and_queues_the_read(world, monkeypatch):
    c = webclient.client(_app(world, monkeypatch))
    old = _up(world, data=_pdf(1))["pin"]
    url = "/api/write/records/" + MIN
    body = {"act": "replace", "pin": old, "name": "New.pdf", "base64": base64.b64encode(_pdf(2)).decode(), "period": "2099-06", "by": BY}
    plan = c.post(url, json={**body, "dryRun": True})
    assert plan.status_code == 200 and plan.json["dryRun"] is True and plan.json["would"]["old"] == old
    done = c.post(url, json=body)
    assert done.status_code == 200 and done.json["replaced"] == old and done.json["queued"] is True and done.json["pin"] != old
    assert c.post(url, json={**body, "path": "C:/x.pdf"}).status_code == 400
    assert c.post(url, json={"act": "replace", "by": BY}).status_code == 400
    assert world.drive.calls == []


def test_the_command_replaces_with_a_path_and_prints_both_halves(world, capsys):
    import argparse

    from jason.commands import record_slots as cmd

    old = _up(world, data=_pdf(1))["pin"]
    path = world.tmp / "Newer.pdf"
    path.write_bytes(_pdf(2))
    args = argparse.Namespace(replace=MIN, file=str(path), pin="", period="2099-06", entry="", note="", force=False, yes=False, by=BY,
                              no_ocr=True, resolve=False, json=False)
    assert cmd._replace(args, None, world.community, world.root, True, lambda x: "") == 0
    assert f"would pin the new file and unpin {old}" in capsys.readouterr().out
    assert _active(world, MIN) == [old]
