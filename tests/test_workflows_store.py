"""The run store (engine doc section 3 and tests 2, 3, 8): durable, torn-tolerant, compare-and-swap, hash-chained."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from jason import locks
from jason.workflows import store
from jason.workflows.types import EventKind as K, RunChanged, WorkflowError
from test_workflows_support import OWNER, data  # noqa: F401 - fixture

DEF = "example-cycle"
SUBJECT = "campaign:EX-2099"


def make(data, **kw):
    return store.create(data, DEF, SUBJECT, by=OWNER, label="Example", detail={"dates": {"answers_by": "2099-10-23"}},
                        at="2099-09-15T09:00:00Z", **kw)


def lines_of(run):
    return run.path.read_text(encoding="utf-8").split("\n")[:-1]


def test_a_run_id_is_opaque_and_stable(data):
    rid = store.run_id(DEF, SUBJECT, "2099-09-15T09:00:00Z")
    assert rid == store.run_id(DEF, SUBJECT, "2099-09-15T09:00:00Z")
    assert rid != store.run_id(DEF, SUBJECT, "2099-09-15T09:00:01Z")
    assert rid.startswith("run-") and len(rid) == 14 and set(rid[4:]) <= set("0123456789abcdef")
    assert "EX" not in rid and "2099" not in rid
    run = make(data)
    assert run.id == rid and run.path == data / "workflows" / DEF / f"{rid}.jsonl"
    with pytest.raises(WorkflowError, match="already exists"):
        make(data)


def test_events_are_lines_with_a_chain(data):
    run = make(data)
    store.append(data, DEF, run.id, K.NOTE, by=OWNER, detail={"text": "hello"}, at="2099-09-15T09:05:00Z")
    store.append(data, DEF, run.id, K.CHECK_RAN, by="jason", step="example-cycle.1", detail={"ok": True}, at="2099-09-15T09:06:00Z")
    run = store.read(data, DEF, run.id)
    raw = lines_of(run)
    rows = [json.loads(l) for l in raw]
    assert [r["n"] for r in rows] == [1, 2, 3] and rows[0]["prev"] == ""
    assert list(rows[0]) == ["n", "kind", "by", "at", "detail", "prev"]          # no step on the opening line
    assert list(rows[2]) == ["n", "kind", "step", "by", "at", "detail", "prev"]
    import hashlib

    assert rows[1]["prev"] == hashlib.sha256(raw[0].encode()).hexdigest()[:12]
    assert rows[2]["prev"] == hashlib.sha256(raw[1].encode()).hexdigest()[:12]
    assert store.verify(run).ok and store.locate(data, run.id) == DEF
    assert store.list_runs(data) == [(DEF, run.id)]


def test_a_torn_last_line_is_dropped_reported_and_appended_after_cleanly(data):
    run = make(data)
    store.append(data, DEF, run.id, K.NOTE, by=OWNER, detail={"text": "one"})
    whole = run.path.read_bytes()
    with open(run.path, "ab") as f:                         # the process died between two appends
        f.write(b'{"n":3,"kind":"note","by":"A. Manager","at":"2099-09-16T0')
    torn = store.read(data, DEF, run.id)
    assert torn.n == 2 and torn.torn.startswith('{"n":3') and not torn.corrupt
    assert store.verify(torn).ok and store.verify(torn).torn
    event = store.append(data, DEF, run.id, K.NOTE, by=OWNER, detail={"text": "two"})
    assert event.n == 3 and event.detail["_torn"].startswith('{"n":3')       # the fragment is kept, not guessed at
    again = store.read(data, DEF, run.id)
    assert again.n == 3 and again.torn == "" and store.verify(again).ok
    assert again.path.read_bytes().startswith(whole)


def test_a_line_that_is_not_an_event_stops_the_appends(data):
    run = make(data)
    with open(run.path, "ab") as f:
        f.write(b"this is not json\n")
    bad = store.read(data, DEF, run.id)
    assert bad.corrupt == 2 and bad.n == 1
    assert not store.verify(bad).ok or bad.corrupt
    with pytest.raises(WorkflowError, match="not an event"):
        store.append(data, DEF, run.id, K.NOTE, by=OWNER)


def test_compare_and_swap_in_one_process(data):
    run = make(data)
    store.append(data, DEF, run.id, K.NOTE, by=OWNER, detail={"text": "a"}, n=2)
    with pytest.raises(RunChanged) as err:
        store.append(data, DEF, run.id, K.NOTE, by="B. Other", detail={"text": "b"}, n=2)
    assert "expected to append n=2" in str(err.value) and "now at n=2" in str(err.value) and "A. Manager" in str(err.value)
    assert (err.value.expected, err.value.actual) == (2, 2)
    assert store.read(data, DEF, run.id).n == 2                                   # nothing was written by the loser


WORKER = """
import sys, time, os
from pathlib import Path
from jason.workflows import store
from jason.workflows.types import EventKind, RunChanged
data, definition, rid, name, go = sys.argv[1:6]
while not Path(go).exists():
    time.sleep(0.005)
try:
    store.append(data, definition, rid, EventKind.NOTE, by=name, detail={"text": name}, n=2)
    print("won")
except RunChanged as exc:
    print("refused:" + str(exc))
"""


def test_two_processes_appending_at_once_one_wins_and_one_is_refused(data, tmp_path):
    run = make(data)
    go = tmp_path / "go"
    env = dict(os.environ, JASON_LOCK_DIR=str(tmp_path / "locks"))
    procs = [subprocess.Popen([sys.executable, "-c", WORKER, str(data), DEF, run.id, name, str(go)], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for name in ("P. One", "P. Two")]
    time.sleep(1.0)
    go.write_text("go")
    outs = [p.communicate(timeout=60) for p in procs]
    results = sorted(o[0].strip() for o in outs)
    assert all(p.returncode == 0 for p in procs), outs
    assert results[1] == "won" and results[0].startswith("refused:") and "now at n=2" in results[0], results
    final = store.read(data, DEF, run.id)
    assert final.n == 2 and store.verify(final).ok


def test_every_append_holds_the_runs_lock_and_syncs(data, monkeypatch):
    held, synced = [], []
    real_hold, real_fsync = locks.hold, os.fsync

    def spy_hold(resource, key="", **kw):
        held.append((resource, key))
        return real_hold(resource, key, **kw)

    monkeypatch.setattr(locks, "hold", spy_hold)
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real_fsync(fd))[1])
    run = make(data)
    held.clear(), synced.clear()
    store.append(data, DEF, run.id, K.NOTE, by=OWNER)
    assert (locks.Resource.STORE, f"workflows-{run.id}") in held and synced


def test_an_edited_line_is_reported_by_verify_with_its_n(data):
    run = make(data)
    for i in range(3):
        store.append(data, DEF, run.id, K.NOTE, by=OWNER, detail={"text": f"note {i}"})
    run = store.read(data, DEF, run.id)
    assert store.verify(run).ok and run.n == 4
    raw = lines_of(run)
    raw[1] = raw[1].replace("note 0", "note X")                                  # edit the second line (n=2)
    run.path.write_bytes(("\n".join(raw) + "\n").encode("utf-8"))   # bytes: no newline translation
    result = store.verify(store.read(data, DEF, run.id))
    assert not result.ok and result.n == 3 and "n=2" in result.message          # the link after the edit is the one that breaks
    # removing a line is seen as well
    del raw[1]
    run.path.write_bytes(("\n".join(raw) + "\n").encode("utf-8"))   # bytes: no newline translation
    result = store.verify(store.read(data, DEF, run.id))
    assert not result.ok and result.n == 3 and "expected 2" in result.message      # the gap shows at the next line's n


def test_an_edit_of_the_last_line_is_caught_by_the_index_tip(data):
    run = make(data)
    store.append(data, DEF, run.id, K.NOTE, by=OWNER, detail={"text": "last"})
    run = store.read(data, DEF, run.id)
    tip, n = run.tip, run.n
    raw = lines_of(run)
    raw[-1] = raw[-1].replace("last", "LAST")
    run.path.write_bytes(("\n".join(raw) + "\n").encode("utf-8"))   # bytes: no newline translation
    edited = store.read(data, DEF, run.id)
    assert store.verify(edited).ok                                             # the chain alone cannot see the last line
    assert not store.verify(edited, tip=tip, tip_n=n).ok


def test_the_index_is_a_cache_written_atomically_and_rebuilt(data):
    a = make(data)
    b = store.create(data, DEF, "campaign:EX-2100", by=OWNER, label="Next", at="2099-09-16T09:00:00Z")
    store.index_put(data, {"id": a.id, "definition": DEF, "state": "active"})
    store.index_put(data, {"id": b.id, "definition": DEF, "state": "draft"})
    assert sorted(store.index_read(data)) == sorted([a.id, b.id])
    assert not list((data / "workflows").glob("*.tmp"))
    store.index_path(data).unlink()                                            # deleting it loses nothing
    assert store.index_read(data) == {}
    rows = store.reindex(data, lambda run: {"id": run.id, "definition": run.definition, "state": "active", "n": run.n})
    assert sorted(r["id"] for r in rows) == sorted([a.id, b.id]) and sorted(store.index_read(data)) == sorted([a.id, b.id])
    store.index_path(data).write_text("{not json", encoding="utf-8")
    assert store.index_read(data) == {}                                        # a damaged cache reads as empty


def test_reindex_lists_an_unreadable_run_instead_of_dropping_it(data):
    run = make(data)

    def summarize(r):
        raise ValueError("no such definition")

    rows = store.reindex(data, summarize)
    assert rows[0]["id"] == run.id and rows[0]["state"] == "unreadable" and "no such definition" in rows[0]["problem"]
