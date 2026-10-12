"""The PDF splitter's recovery (docs/pdf-splitter-failure-modes.md sections 5 and 6; docs/pdf-splitter.md 6.5): durable writes, a session
that keeps its previous save, exclusive creation, the apply as a two-phase journal with a plan fingerprint, kill-injection at each step,
purge and sweep guards, and ``jason split --doctor``. Fakes only: made-up PDFs, a made-up association, no service."""

import json
import os
import threading
import time

import pytest

from jason import durable
from jason.community import split_gold
from jason.community.split_session import SplitSession
from jason.tasks import record_slots as rs
from jason.tasks import record_upload as up
from jason.tasks import split_doctor as doctor
from jason.tasks import split_journal as sj
from jason.tasks import split_session as ss

from test_record_intake_phase2 import world  # noqa: F401  (a fixture)
from test_split_apply import BY, MIN, _set, kw, open_, pdf  # noqa: F401  (pdf is a fixture)
from test_split_surfaces import _cli


def store_pins(world):
    path = world.spec / "example" / "records.json"
    return json.loads(path.read_text(encoding="utf-8"))["pins"] if path.is_file() else []


def parts_on_disk(world):
    return sorted((world.root / "record-intake" / "example" / "files").glob("*/Part-*.pdf"))


def ready(world, pdf):
    """A draft of five parts: the second fills the minutes slot, the others are held."""
    sid = open_(world, pdf)["session"]["id"]
    _set(world, sid, [1, 4, 6, 10, 11], [(4, "slot", MIN), (4, "period", "2099-06")])
    return sid


# --- durable writes ------------------------------------------------------------------------------------------------------------

def test_a_durable_write_flushes_the_file_before_it_renames_and_keeps_the_previous_version(tmp_path, monkeypatch):
    events = []
    real_fsync, real_replace = os.fsync, os.replace
    monkeypatch.setattr(os, "fsync", lambda fd: (events.append("fsync"), real_fsync(fd))[1])
    monkeypatch.setattr(os, "replace", lambda a, b: (events.append("replace"), real_replace(a, b))[1])
    target = tmp_path / "a" / "store.json"
    durable.durable_write(target, "one")
    assert events.index("fsync") < events.index("replace") and target.read_text() == "one"
    durable.durable_write(target, "two", backup=True)
    assert target.read_text() == "two" and target.with_name("store.json.bak").read_text() == "one"
    assert not [p for p in target.parent.iterdir() if p.name.endswith(".tmp")]


def test_a_replace_that_windows_refuses_is_retried_and_a_failure_leaves_no_temp_file(tmp_path, monkeypatch):
    monkeypatch.setattr(durable.time, "sleep", lambda s: None)
    real = os.replace
    calls = {"n": 0}

    def flaky(a, b):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise PermissionError("held by an indexer")
        return real(a, b)

    monkeypatch.setattr(os, "replace", flaky)
    target = tmp_path / "x.json"
    durable.durable_write(target, "ok")
    assert target.read_text() == "ok" and calls["n"] == 3
    monkeypatch.setattr(os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("always")))
    with pytest.raises(PermissionError):
        durable.durable_write(tmp_path / "y.json", "no")
    assert not (tmp_path / "y.json").exists() and not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_a_create_is_exclusive_and_an_append_is_flushed(tmp_path, monkeypatch):
    path = tmp_path / "c.json"
    assert durable.durable_create(path, "first") is True
    assert durable.durable_create(path, "second") is False and path.read_text() == "first"
    seen = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (seen.append(fd), real(fd))[1])
    durable.durable_append(tmp_path / "log.jsonl", "a\n")
    durable.durable_append(tmp_path / "log.jsonl", "b\n")
    assert (tmp_path / "log.jsonl").read_text() == "a\nb\n" and len(seen) == 2


def test_the_record_slot_store_and_its_history_are_flushed_and_the_store_keeps_a_backup(world, monkeypatch):
    seen = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (seen.append(fd), real(fd))[1])
    rs._write_store("example", lambda d: d["pins"].append({"id": "p-1"}), purpose="test")
    rs._write_store("example", lambda d: d["pins"].append({"id": "p-2"}), purpose="test")
    path = world.spec / "example" / "records.json"
    assert len(seen) >= 2 and [p["id"] for p in json.loads(path.read_text())["pins"]] == ["p-1", "p-2"]
    assert [p["id"] for p in json.loads(path.with_name("records.json.bak").read_text())["pins"]] == ["p-1"]
    before = len(seen)
    rs._append_history(world.root, {"act": "test"})
    assert len(seen) == before + 1


# --- the session: a backup, exclusive creation, a bigger id ----------------------------------------------------------------------

def test_a_damaged_session_file_is_read_from_the_previous_save_and_says_so_and_never_overwrites_a_good_backup(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    assert len(sid) == 16
    ss.act(sid, "mark", {"pages": [4]}, by=BY, **kw(world))                 # a second save: the first is now the .bak
    path = ss.session_file(world.root, sid)
    assert ss._bak(path).is_file()
    previous = json.loads(ss._bak(path).read_text())["version"]
    path.write_bytes(b"")                                                   # a power cut leaves a zero-length file
    got = ss.load(world.root, sid)
    assert got.version == previous and ss.RESTORED_NOTE in got.notes
    assert [s.id for s in ss.sessions(world.root)] == [sid]                 # it still lists
    path.write_bytes(b"{not json")
    ss.save(world.root, got)                                                # saving over the damage...
    assert json.loads(ss._bak(path).read_text())["version"] == previous     # ...does not copy the damage over the good backup
    assert ss.load(world.root, sid).version == previous
    path.write_bytes(b"")
    ss._bak(path).write_bytes(b"")
    with pytest.raises(KeyError):
        ss.load(world.root, sid)


def test_a_colliding_session_id_never_overwrites_a_draft(world, pdf, monkeypatch):
    sid = open_(world, pdf)["session"]["id"]
    before = ss.session_file(world.root, sid).read_bytes()
    clash = SplitSession(sid, ss.load(world.root, sid).source, "draft", "t", "t", BY, 1)
    monkeypatch.setattr(ss, "new_id", lambda: "b" * 16)
    made = ss.create(world.root, clash)
    assert made.id == "b" * 16 and ss.session_file(world.root, sid).read_bytes() == before


def test_two_simultaneous_opens_of_the_same_bytes_make_one_draft(world, pdf):
    results, errors = [], []
    gate = threading.Barrier(2)

    def go():
        try:
            gate.wait(10)
            results.append(open_(world, pdf))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in threads]
    [t.join(120) for t in threads]
    assert not errors and len(results) == 2
    assert len({r["session"]["id"] for r in results}) == 1 and sorted(r["resumed"] for r in results) == [False, True]
    assert len(ss.sessions(world.root)) == 1


def test_an_older_eight_digit_session_id_is_still_read(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    old = sid[:8]
    ss.session_file(world.root, sid).rename(ss.session_file(world.root, sid).with_name(old + ".json"))
    data = json.loads(ss.session_file(world.root, old).read_text())
    data["id"] = old
    ss.session_file(world.root, old).write_text(json.dumps(data))
    assert ss.load(world.root, old).id == old and ss.ID_FORM.match(old)


# --- the plan fingerprint --------------------------------------------------------------------------------------------------------

def test_apply_refuses_a_plan_the_draft_has_moved_past_and_writes_nothing(world, pdf):
    sid = ready(world, pdf)
    fp = ss.review(sid, **kw(world))["planFingerprint"]
    assert ss.apply(sid, by=BY, **kw(world))["planFingerprint"] == fp                        # the dry run says the same
    ss.act(sid, "mark", {"pages": [8]}, by=BY, **kw(world))                                   # another tab moves a boundary
    with pytest.raises(ss.PlanChanged, match="Nothing was written") as err:
        ss.apply(sid, by=BY, confirm=True, expect=fp, **kw(world))
    assert err.value.review["planFingerprint"] != fp and 8 in [x["start"] for x in err.value.review["parts"]]
    assert not store_pins(world) and not parts_on_disk(world) and sj.read(world.root, sid) == []
    assert ss.load(world.root, sid).status == "draft"
    with pytest.raises(ss.PlanChanged):
        ss.apply(sid, by=BY, confirm=True, expect="0" * 32, **kw(world))
    out = ss.apply(sid, by=BY, confirm=True, expect=err.value.review["planFingerprint"], **kw(world))
    assert out["ok"] and out["planFingerprint"] == err.value.review["planFingerprint"]


def test_the_fingerprint_follows_the_choices_and_the_slots_state(world, pdf):
    sid = ready(world, pdf)
    a = ss.review(sid, **kw(world))
    assert a["planFingerprint"] == ss.review(sid, **kw(world))["planFingerprint"]
    assert a["planFingerprint"] != ss.review(sid, drop=[2], **kw(world))["planFingerprint"]
    assert a["planFingerprint"] != ss.review(sid, filing="held", **kw(world))["planFingerprint"]
    assert a["planInputs"] == ss.review(sid, **kw(world))["planInputs"]
    # a slot filled after the review changes the full fingerprint (a collision now) and not the inputs
    rs._write_store("example", lambda d: d["pins"].append({"id": "p-x", "slot": MIN, "kind": "file", "ref": "x", "period": "2099-06",
                                                          "unpinned": None}), purpose="test")
    b = ss.review(sid, **kw(world))
    assert b["planFingerprint"] != a["planFingerprint"] and b["planInputs"] == a["planInputs"]
    assert b["collisions"] == [MIN]


def test_an_apply_without_a_fingerprint_still_works_and_plans_inside_the_lock(world, pdf):
    sid = ready(world, pdf)
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert out["ok"] and len(out["filled"]) == 1 and out["planFingerprint"] and out["resumed"] is False
    s = ss.load(world.root, sid)
    assert s.confirmed["boundaries"] == "1,4,6,10,11" and s.status == "applied"          # the boundaries recorded are the ones cut from


# --- the journal on a clean apply ------------------------------------------------------------------------------------------------

def test_a_clean_apply_journals_intent_parts_commit_and_queue_in_order_and_names_no_file(world, pdf):
    sid = ready(world, pdf)
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    events = sj.read(world.root, sid)
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "intent" and kinds[-2:] == ["commit", "queued"] and kinds.count("part") == 5 and kinds.count("placing") == 5
    assert [e["n"] for e in events] == list(range(1, len(events) + 1))
    intent = events[0]["detail"]
    planned_pin = next(p["pin"] for p in intent["parts"] if p["action"] == "fill")
    assert planned_pin == out["filled"][0]["pin"] and planned_pin in [p["id"] for p in store_pins(world)]   # the pin id was chosen first
    assert intent["fingerprint"] == out["planFingerprint"] and intent["args"]["filing"] == ""
    text = sj.journal_file(world.root, sid).read_text()
    assert "numbered.pdf" not in text and str(world.tmp) not in text
    st = sj.state(world.root, sid)
    assert st["state"] == "clean" and st["committed"] and st["queued"]
    history = (world.root / "records" / "history.jsonl").read_text()
    assert '"apply": "' + events[0]["apply"] in history


def test_a_torn_last_journal_line_is_dropped_and_the_next_event_repairs_the_tail(world, pdf):
    sid = ready(world, pdf)
    ss.apply(sid, by=BY, confirm=True, **kw(world))
    path = sj.journal_file(world.root, sid)
    whole = len(sj.read(world.root, sid))
    with open(path, "ab") as fh:
        fh.write(b'{"n": 99, "prev": "abc", "kin')
    assert len(sj.read(world.root, sid)) == whole
    sj.append(world.root, sid, "abort", "a-x", BY, {"reason": "test"})
    events = sj.read(world.root, sid)
    assert len(events) == whole + 1 and events[-1]["n"] == whole + 1


# --- kill injection: a crash between steps ---------------------------------------------------------------------------------------

POINTS = ["after_intent", "before_place:1", "after_place:1", "after_part:1", "after_place:2", "after_part:2", "after_place:3",
          "before_session_save", "after_session_save", "after_commit", "after_queue", "after_history"]


def assert_finished_once(world, sid, planned_pin):
    s = ss.load(world.root, sid)
    assert s.status == "applied" and s.applied["partial"] is False
    in_slot = [p for p in store_pins(world) if p["slot"] == MIN and not p.get("unpinned")]
    assert [p["id"] for p in in_slot] == [planned_pin]                                  # one pin, the one chosen before anything was written
    assert len(parts_on_disk(world)) == 5                                               # every part once, none twice
    assert [m["pin"] for m in s.applied["parts"] if m.get("pin")] == [planned_pin]
    assert not [m for m in s.applied["parts"] if m.get("action") == "collision"]        # its own pin is never a collision with itself
    st = sj.state(world.root, sid)
    assert st["state"] == "clean" and ss.pending_apply(world.root, sid) is None


@pytest.mark.parametrize("point", POINTS)
def test_a_kill_at_every_step_leaves_a_state_a_person_can_finish(world, pdf, monkeypatch, point):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", f"split.apply:{point}")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    committed_in_session = ss.load(world.root, sid).status == "applied"
    pend = ss.pending_apply(world.root, sid)
    if committed_in_session:
        assert pend is None                                                            # after the session save: nothing to ask
    else:
        assert pend is not None and pend["apply"]
        assert ss.listing(world.root)[0]["unfinishedApply"]["choices"] == ["finish", "rollback"]
    # a person finishes it (dry run first: it says what it would do)
    left = sj.state(world.root, sid)
    complete = left["state"] == "clean" and left["queued"]                            # a kill after the last journal line has nothing left
    got: dict = {"ok": True}
    if not complete:
        dry = ss.recover(sid, "finish", by=BY, **kw(world))
        assert dry["dryRun"] is True
        got = ss.recover(sid, "finish", by=BY, confirm=True, **kw(world))
        assert got["ok"] is True
    intents = [e["detail"] for e in sj.read(world.root, sid) if e["kind"] == "intent"]
    assert len(intents) == (2 if point == "after_intent" else 1)                       # an apply that wrote nothing is begun again, not resumed
    planned_pin = next(p["pin"] for p in intents[-1]["parts"] if p["action"] == "fill")
    assert_finished_once(world, sid, planned_pin)
    if not committed_in_session and point != "after_intent":
        assert got["resumed"] is True and len(got["filled"]) == 1 and got["filled"][0]["pin"] == planned_pin
    # the jobs are queued once, after the commit
    from jason import jobs

    reads = [j for j in jobs.jobs(world.root, every=True, limit=100) if "--read" in j.argv]
    assert len(reads) == 1 and reads[0].argv[reads[0].argv.index("--pin") + 1] == planned_pin
    kinds = [e["kind"] for e in sj.read(world.root, sid)]
    assert kinds.index("commit") < kinds.index("queued")


def test_the_orphan_pin_after_a_kill_between_the_pin_and_the_session_is_adopted_not_a_collision(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_place:2")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    pins = [p for p in store_pins(world) if p["slot"] == MIN]
    assert len(pins) == 1                                                              # the pin is in the store ...
    assert pins[0]["id"] not in [m.get("pin") for m in (ss.load(world.root, sid).applied.get("parts") or ())]   # ... and the session does not know it
    assert [f["id"] for f in doctor.diagnose(world.root, **{"profile": "example"})["findings"] if f["check"] == "DR-14"] == [f"DR-14:{sid}"]
    again = ss.apply(sid, by=BY, confirm=True, **kw(world))                           # the same choices run again: a resume
    assert again["resumed"] is True and again["filled"][0]["pin"] == pins[0]["id"] and again["skipped"] == []
    assert len([p for p in store_pins(world) if p["slot"] == MIN]) == 1


def test_different_choices_are_refused_while_an_apply_is_unfinished_and_nothing_is_written(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_part:2")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    before = len(parts_on_disk(world))
    with pytest.raises(ss.PlanChanged, match="did not finish"):
        ss.apply(sid, by=BY, confirm=True, filing="held", **kw(world))
    assert len(parts_on_disk(world)) == before
    assert ss.pending_apply(world.root, sid) is not None


def test_a_background_job_never_finishes_or_rolls_back_an_apply(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_part:2")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    with pytest.raises(ValueError, match="names who made it"):
        ss.recover(sid, "finish", by="", confirm=True, **kw(world))
    with pytest.raises(ValueError, match="never writes in its own name"):
        ss.recover(sid, "rollback", by="jason", confirm=True, **kw(world))
    assert ss.pending_apply(world.root, sid) is not None
    # nothing but a person's act touches it: open, list, review, and the doctor leave it as it is
    open_(world, pdf)
    ss.listing(world.root)
    doctor.diagnose(world.root, profile="example")
    assert ss.pending_apply(world.root, sid) is not None


def test_an_apply_cut_short_after_its_intent_wrote_nothing_and_a_new_apply_just_goes_on(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_intent")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    assert not store_pins(world) and not parts_on_disk(world) and ss.load(world.root, sid).status == "draft"
    out = ss.apply(sid, by=BY, confirm=True, filing="held", **kw(world))             # even with other choices: nothing was visible
    assert out["ok"] and out["resumed"] is False and len(out["held"]) == 5
    kinds = [e["kind"] for e in sj.read(world.root, sid)]
    assert kinds.count("intent") == 2 and "abort" in kinds


def test_a_part_that_fails_leaves_the_apply_unfinished_and_the_same_choices_resume_it(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    real = up.keep_held
    calls = {"n": 0}

    def flaky(root, profile, data, name):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("the disk went away")
        return real(root, profile, data, name)

    monkeypatch.setattr(up, "keep_held", flaky)
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert out["ok"] is False and out["failed"] and out["unfinishedApply"]["choices"] == ["finish", "rollback"]
    assert [e["kind"] for e in sj.read(world.root, sid)].count("failed") == 1
    monkeypatch.setattr(up, "keep_held", real)
    done = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert done["ok"] and done["resumed"] is True and len(parts_on_disk(world)) == 5
    assert len([p for p in store_pins(world) if p["slot"] == MIN]) == 1


# --- a slot taken while the apply runs -------------------------------------------------------------------------------------------

def test_a_slot_taken_during_the_apply_is_a_collision_not_a_second_pin(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    real = up._keep

    def keep(root, profile, name, data):
        got = real(root, profile, name, data)
        if name.startswith("Part-2-"):                                                   # someone pins that slot while the part is cut
            rs._write_store(profile, lambda d: d["pins"].append({"id": "p-other", "slot": MIN, "kind": "file", "ref": "elsewhere.pdf",
                                                                 "period": "2099-06", "unpinned": None}), purpose="test")
        return got

    monkeypatch.setattr(up, "_keep", keep)
    out = ss.apply(sid, by=BY, confirm=True, **kw(world))
    assert out["ok"] and out["filled"] == []
    assert [p["id"] for p in store_pins(world) if p["slot"] == MIN] == ["p-other"]       # never two pins in a slot that holds one
    assert len(out["collided"]) == 1 and "while this was being written" in out["collided"][0]["why"]
    held = next(m for m in out["held"] if m["segment"] == "s2")
    assert (world.root / held["ref"]).is_file()                                          # the part was kept, as a held file
    assert ss.load(world.root, sid).status == "applied"


def test_write_part_is_idempotent_by_pin_id(world, pdf):
    sid = ready(world, pdf)
    row = {"segment": "s2", "pages": (4, 5), "slot": MIN, "period": "2099-06", "entry": ""}
    data = up.cut_pages(pdf, [(4, 5)])
    kwargs = dict(by=BY, why="t", source_pin="session:x", label="Part-2-pages-4-5.pdf", pin_id="p-fixed01")
    first = up.write_part(world.root, "example", world.community, dict(row), data, **kwargs)
    again = up.write_part(world.root, "example", world.community, dict(row), data, **kwargs)
    assert first["pin"] == again["pin"] == "p-fixed01" and again.get("adopted") is True
    assert len([p for p in store_pins(world) if p["slot"] == MIN]) == 1
    other = up.write_part(world.root, "example", world.community, dict(row), data, **{**kwargs, "pin_id": "p-fixed02"})
    assert other["collided"] is True and "pin" in other and other["pin"] == ""


# --- rollback ------------------------------------------------------------------------------------------------------------------

def test_rolling_back_unpins_what_the_apply_pinned_and_puts_the_draft_back(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_part:2")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    assert ss.recover(sid, "rollback", by=BY, **kw(world))["dryRun"] is True
    assert ss.pending_apply(world.root, sid) is not None                                # the dry run changed nothing
    out = ss.recover(sid, "rollback", by=BY, confirm=True, **kw(world))
    assert out["rolledBack"] and len(out["unpinned"]) == 1 and out["heldFilesKept"]
    pins = [p for p in store_pins(world) if p["slot"] == MIN]
    assert len(pins) == 1 and pins[0]["unpinned"]["by"] == BY                            # kept in the record, marked unpinned
    s = ss.load(world.root, sid)
    assert s.status == "draft" and s.applied == {} and s.confirmed == {}
    assert sj.state(world.root, sid)["state"] == "clean" and sj.read(world.root, sid)[-1]["kind"] == "abort"
    assert ss.pending_apply(world.root, sid) is None and len(parts_on_disk(world)) >= 2   # nothing was deleted
    again = ss.apply(sid, by=BY, confirm=True, keep_copies=True, **kw(world))           # and it can be applied afresh
    assert again["ok"] and len(again["filled"]) == 1
    assert len([p for p in store_pins(world) if p["slot"] == MIN and not p.get("unpinned")]) == 1


def test_a_committed_apply_whose_jobs_were_not_queued_is_queued_once_by_a_person(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_session_save")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    assert [f["id"] for f in doctor.diagnose(world.root, profile="example")["findings"]] == [f"DR-19:{sid}"]   # applied, not unfinished
    out = ss.recover(sid, "finish", by=BY, confirm=True, **kw(world))
    assert out["settled"] and out["requeued"] and len(out["queued"]) == 1
    again = ss.recover  # a second time there is nothing to settle
    with pytest.raises(ValueError, match="no unfinished apply"):
        again(sid, "finish", by=BY, confirm=True, **kw(world))
    assert ss.requeue_after_commit(world.root, sid, BY)["requeued"] is False


# --- purge and the sweep -------------------------------------------------------------------------------------------------------

def test_purge_refuses_a_session_with_an_unfinished_apply_or_a_confirmed_one_with_no_commit(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_part:1")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    with pytest.raises(ValueError, match="did not finish"):
        ss.purge(sid=sid, dry_run=False, by=BY, root=world.root, community=world.community)
    out = ss.purge(all_drafts=True, dry_run=False, by=BY, root=world.root, community=world.community)
    assert out["removed"] == [] and out["refused"][0]["id"] == sid
    assert ss.session_file(world.root, sid).is_file() and ss.source_file(world.root, ss.load(world.root, sid).source.sha256).is_file()
    # a confirmed session with no journal (an apply from before the journal) is held back the same way
    sj.journal_file(world.root, sid).unlink()
    with pytest.raises(ValueError, match="no commit"):
        ss.purge(sid=sid, dry_run=False, by=BY, root=world.root, community=world.community)


def test_purge_leaves_a_copy_an_open_has_just_made_and_takes_the_locks(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    sha_ = ss.load(world.root, sid).source.sha256
    other = world.tmp / "other.pdf"
    other.write_bytes(split_gold.letters(3).pdf)
    found = ss._resolve({"kind": "path", "path": str(other)}, world.root)
    fresh, _size = ss._ingest(world.root, found)                  # an open has made its copy but not yet saved its session
    assert ss.source_file(world.root, fresh).is_file()
    ss.purge(sid=sid, dry_run=False, by=BY, root=world.root, community=world.community)
    assert not ss.source_file(world.root, sha_).exists()          # the purged draft's own copy goes ...
    assert ss.source_file(world.root, fresh).is_file()            # ... the young copy of a file no session has yet stays


def _old_draft(world, n, days=100):
    other = world.tmp / f"letters{n}.pdf"
    other.write_bytes(split_gold.letters(n).pdf)
    sid = ss.open_session({"kind": "path", "path": str(other)}, by=BY, **kw(world))["session"]["id"]
    return sid


def _age(world, sid, days):
    from datetime import datetime, timedelta, timezone

    s = ss.load(world.root, sid)
    s.updated = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    ss.save(world.root, s)


def test_the_sweep_refuses_a_clock_that_moved_backwards_and_remembers_the_last_sweep(world, pdf):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    ok = ss.sweep(dry_run=False, root=world.root, community=world.community, today=now + timedelta(days=400))
    assert ok["ok"] and (world.root / "split" / "sweep.json").is_file()
    sid = open_(world, pdf)["session"]["id"]
    _age(world, sid, 100)
    refused = ss.sweep(dry_run=False, root=world.root, community=world.community, today=now)
    assert refused["ok"] is False and "clock looks wrong" in refused["refused"] and refused["removed"] == []
    assert ss.session_file(world.root, sid).is_file()
    assert ss.sweep(root=world.root, community=world.community, today=now)["refused"]            # a dry run says so too
    assert ss.sweep(dry_run=False, root=world.root, community=world.community, today=now + timedelta(days=400))["removed"] == [sid]


def test_the_sweep_refuses_to_remove_more_than_half_the_drafts_at_once(world):
    sids = [_old_draft(world, n) for n in range(2, 8)]                                          # six drafts ...
    for sid in sids:
        _age(world, sid, 100)                                                                    # ... all older than the retention
    out = ss.sweep(dry_run=False, root=world.root, community=world.community)
    assert out["ok"] is False and "more than half" in out["refused"] and len(ss.sessions(world.root)) == 6
    [_old_draft(world, n) for n in range(8, 14)]                                                 # six newer drafts: 6 of 12 is not over half
    assert len(ss.sessions(world.root)) == 12
    more = _old_draft(world, 14)
    _age(world, more, 100)                                                                       # 7 old of 13 is over half still
    assert ss.sweep(dry_run=False, root=world.root, community=world.community)["ok"] is False
    assert all(ss.session_file(world.root, s).is_file() for s in sids)


def test_the_sweep_skips_a_draft_whose_apply_did_not_finish(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    sj.append(world.root, sid, "intent", "a-1", BY, {"parts": [], "inputs": "x", "fingerprint": "y"})
    _age(world, sid, 100)
    out = ss.sweep(dry_run=False, root=world.root, community=world.community)
    assert out["removed"] == [] and out["kept"][0]["id"] == sid and ss.session_file(world.root, sid).is_file()


# --- jason split --doctor ------------------------------------------------------------------------------------------------------

def snapshot(root):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file())


def mess(world, pdf):
    """A data folder with one of each kind of inconsistency the doctor knows."""
    live = open_(world, pdf)["session"]
    split = world.root / "split"
    old = time.time() - 3 * 86400
    tmp = split / "sessions" / "zz.json.1234.abcdef.tmp"
    tmp.write_text("x")
    orphan = split / "sources" / "ab" / ("ab" + "0" * 62 + ".pdf")
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"%PDF-1.4 orphan")
    for p in (tmp, orphan):
        os.utime(p, (old, old))
    twin = json.loads(ss.session_file(world.root, live["id"]).read_text())
    twin["id"] = "c" * 16
    ss.session_file(world.root, "c" * 16).write_text(json.dumps(twin))                            # two live drafts on one file's bytes
    rs._write_store("example", lambda d: d["pins"].extend([
        {"id": "p-nofile", "slot": MIN, "kind": "file", "ref": "record-intake/example/files/00/gone.pdf", "period": "2099-06",
         "splitFrom": f"session:{live['id']}", "unpinned": None}]), purpose="test")                  # a pin whose file is gone
    loose = world.root / "record-intake" / "example" / "files" / "abcd" / "Part-9-pages-1-2.pdf"
    loose.parent.mkdir(parents=True)
    loose.write_bytes(b"%PDF-1.4 loose")                                                              # a part file nothing refers to
    up.queue_read(world.root, MIN, "p-gone0001", BY)                                                  # a job for a pin that is not there
    return live["id"]


def test_the_doctor_lists_each_inconsistent_state_by_id_and_class_and_changes_nothing(world, pdf):
    sid = mess(world, pdf)
    before = snapshot(world.root) + snapshot(world.spec)
    report = doctor.diagnose(world.root, profile="example")
    assert snapshot(world.root) + snapshot(world.spec) == before                                    # read only, down to the modification times
    found = {f["check"]: f for f in report["findings"]}
    assert set(found) >= {"DR-03", "DR-06", "DR-10", "DR-11", "DR-12", "DR-16"}
    assert found["DR-06"]["class"] == "A" and found["DR-03"]["class"] == "A" and found["DR-12"]["class"] == "B"
    assert found["DR-10"]["class"] == "C" and found["DR-11"]["class"] == "D" and found["DR-16"]["class"] == "C"
    assert found["DR-11"]["id"] == "DR-11:p-nofile" and found["DR-11"]["session"] == sid
    assert not report["clean"] and report["counts"]["A"] == 2
    text = json.dumps(report)
    assert "numbered.pdf" not in text and str(world.tmp) not in text and "gone.pdf" not in text    # no file name, no path


def test_a_clean_store_has_no_findings(world, pdf):
    open_(world, pdf)
    assert doctor.diagnose(world.root, profile="example")["clean"] is True


def test_fix_safe_repairs_only_scratch_caches_and_dead_jobs_and_leaves_every_record(world, pdf):
    from jason import jobs

    sid = mess(world, pdf)
    pins_before = store_pins(world)
    dry = doctor.fix("safe", by=BY, root=world.root, profile="example")
    assert dry["dryRun"] is True and {f["class"] for f in dry["would"]["findings"]} <= {"A", "B"}
    assert (world.root / "split" / "sessions" / "zz.json.1234.abcdef.tmp").exists()                # a dry run changed nothing
    named = doctor.fix(["DR-11:p-nofile", "DR-06"], by=BY, confirm=True, root=world.root, profile="example")
    assert named["refused"] == ["DR-11:p-nofile"] and [d["id"] for d in named["fixed"]] == ["DR-06"]
    done = doctor.fix("safe", by=BY, confirm=True, root=world.root, profile="example")
    assert {d["id"] for d in done["fixed"]} == {"DR-03", "DR-12"}
    assert not list((world.root / "split" / "sources" / "ab").glob("*.pdf"))
    assert store_pins(world) == pins_before                                                         # no pin was touched
    assert ss.session_file(world.root, sid).is_file() and ss.session_file(world.root, "c" * 16).is_file()
    assert (world.root / "record-intake" / "example" / "files" / "abcd" / "Part-9-pages-1-2.pdf").is_file()   # no part file was removed
    assert [j.status.value for j in jobs.jobs(world.root, every=True) if "p-gone0001" in j.argv] == ["cancelled"]
    after = {f["check"] for f in doctor.diagnose(world.root, profile="example")["findings"]}
    assert after == {"DR-09", "DR-10", "DR-11", "DR-16"}
    history = (world.root / "records" / "history.jsonl").read_text()
    assert '"act": "split-doctor"' in history and "gone.pdf" not in history


def test_the_doctor_names_an_unfinished_apply_and_fix_safe_does_not_touch_it(world, pdf, monkeypatch):
    sid = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_part:2")
    with pytest.raises(sj.Killed):
        ss.apply(sid, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    report = doctor.diagnose(world.root, profile="example")
    one = next(f for f in report["findings"] if f["check"] == "DR-14")
    assert one["class"] == "C" and "--finish" in one["fix"] and one["session"] == sid
    doctor.fix("safe", by=BY, confirm=True, root=world.root, profile="example")
    assert ss.pending_apply(world.root, sid) is not None


def test_a_damaged_session_and_a_missing_copy_are_reported(world, pdf):
    sid = open_(world, pdf)["session"]["id"]
    sha_ = ss.load(world.root, sid).source.sha256
    ss.source_file(world.root, sha_).unlink()
    ss.session_file(world.root, "d" * 16).write_text("{broken")
    found = {f["check"]: f for f in doctor.diagnose(world.root, profile="example")["findings"]}
    assert found["DR-02"]["class"] == "D" and found["DR-01"]["id"] == "DR-01:" + "d" * 16 and found["DR-01"]["class"] == "C"


def test_the_command_lists_findings_with_exit_one_fixes_with_yes_and_finishes_or_rolls_back(world, pdf, monkeypatch, capsys):
    sid = mess(world, pdf)
    assert _cli(world, monkeypatch, "--doctor") == 1
    out = capsys.readouterr().out
    assert "DR-06" in out and "read only: nothing was changed" in out and "numbered.pdf" not in out
    assert _cli(world, monkeypatch, "--doctor", "--json") == 1
    assert json.loads(capsys.readouterr().out)["findings"]
    assert _cli(world, monkeypatch, "--doctor", "--fix", "safe") == 0 and "A dry run" in capsys.readouterr().out
    assert _cli(world, monkeypatch, "--doctor", "--fix", "safe", "--yes") == 2                       # --yes needs --by
    capsys.readouterr()
    assert _cli(world, monkeypatch, "--doctor", "--fix", "safe", "--yes", "--by", BY) == 0
    assert "repaired DR-03" in capsys.readouterr().out


def test_the_command_finishes_an_unfinished_apply_only_with_yes_and_a_name(world, pdf, monkeypatch, capsys):
    ready_id = ready(world, pdf)
    monkeypatch.setenv("JASON_FAULT", "split.apply:after_part:2")
    with pytest.raises(sj.Killed):
        ss.apply(ready_id, by=BY, confirm=True, **kw(world))
    monkeypatch.delenv("JASON_FAULT")
    assert _cli(world, monkeypatch, ready_id, "--finish") == 0 and "A dry run" in capsys.readouterr().out
    assert _cli(world, monkeypatch, ready_id, "--finish", "--yes", "--by", BY) == 0
    assert "wrote 1 files into slots" in capsys.readouterr().out and ss.load(world.root, ready_id).status == "applied"


def test_the_command_refuses_a_stale_fingerprint_and_prints_the_new_one(world, pdf, monkeypatch, capsys):
    sid = ready(world, pdf)
    assert _cli(world, monkeypatch, sid, "--review") == 0
    shown = capsys.readouterr().out
    fp = shown.split("plan fingerprint ")[1].split()[0]
    ss.act(sid, "mark", {"pages": [8]}, by=BY, **kw(world))
    assert _cli(world, monkeypatch, sid, "--apply", "--yes", "--by", BY, "--expect", fp) == 1
    err = capsys.readouterr().err
    assert "Nothing was written" in err and "fingerprint" in err and not store_pins(world)
