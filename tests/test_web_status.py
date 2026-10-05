"""The administrator's Status loader (``jason.web.extra.status``, ``GET /api/status``): one of jason's admins only, never
the owner view; each source's last read from its own store's stamp (made-up stores in tmp_path), a standing word only
where the records say it (no threshold invented), failures from a made-up job queue, and sign-ins masked. Nothing
reaches Google, PayHOA, Keeper, or the network, and nothing is written.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import webclient

from jason.web.extra import status as st

NOW = datetime(2099, 10, 4, 12, 0, tzinfo=timezone.utc)
NO_GATES = {"found": True, "stage": "start", "progress": {}, "gates": [
    {"stage": "start", "title": "Sign-in and sources", "open": True, "opensWhen": "", "waiting": [], "checks": []}]}


def _gates(root, settings):
    return NO_GATES


def _row(out: dict, key: str) -> dict:
    return next(s for s in out["sources"] if s["key"] == key)


def _write_json(root: Path, rel: str, body: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")


def _jobs_db(root: Path, rows: list[tuple]) -> None:
    """A made-up queue: (argv, status, finished, summary), in the queue's own schema."""
    from jason import jobs

    conn = sqlite3.connect(root / "jobs.db")
    conn.execute(jobs._SCHEMA)
    for argv, status, finished, summary in rows:
        conn.execute("INSERT INTO jobs (argv, job_class, status, writes, created, finished, summary) "
                     "VALUES (?, 'local', ?, 0, ?, ?, ?)", (json.dumps(argv), status, finished, finished, summary))
    conn.commit()
    conn.close()


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "data"
    r.mkdir()
    return r


def _token(tmp_path: Path, present: bool = True) -> SimpleNamespace:
    token = tmp_path / "google-token.json"
    if present:
        token.write_text("{}", encoding="utf-8")
    return SimpleNamespace(google_oauth_token_file=token, smud_db=None)


# --- each source's last read, from its own store ------------------------------------------------------------------------

def test_each_source_reads_its_own_stamp(root, tmp_path):
    _write_json(root, "drive/files.json", {"syncedAt": "2099-10-03T06:10:00+00:00", "files": []})
    _write_json(root, "gmail/correspondence.json", {"syncedAt": "2099-10-02T06:12:00+00:00", "messages": []})
    _write_json(root, "payhoa/reconciliations.json", {"fetchedAt": "2099-09-30T02:00:00+00:00", "reconciliations": []})
    _write_json(root, "payhoa/finance-2098.json", {"year": 2098, "syncedAt": "2098-12-31T00:00:00+00:00"})
    _write_json(root, "payhoa/finance-2099.json", {"year": 2099, "syncedAt": "2099-10-01T00:00:00+00:00"})
    conn = sqlite3.connect(root / "payhoa.db")
    conn.execute("CREATE TABLE units (id INTEGER, synced_at TEXT NOT NULL)")
    conn.execute("CREATE TABLE people (id INTEGER, synced_at TEXT NOT NULL)")
    conn.executemany("INSERT INTO units VALUES (?, ?)", [(1, "2099-09-01T00:00:00+00:00"), (2, "2099-09-02T00:00:00+00:00")])
    conn.execute("INSERT INTO people VALUES (1, '2099-09-03T00:00:00+00:00')")
    conn.commit()
    conn.close()
    tax = sqlite3.connect(root / "tax.db")
    tax.execute("CREATE TABLE sync_runs (id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, errors_json TEXT)")
    tax.execute("INSERT INTO sync_runs (started_at, finished_at, errors_json) VALUES ('2099-09-20T01:00:00+00:00', "
                "'2099-09-20T01:05:00+00:00', '[]')")
    tax.execute("INSERT INTO sync_runs (started_at, finished_at, errors_json) VALUES ('2099-09-27T01:00:00+00:00', "
                "'2099-09-27T01:09:00+00:00', '[\"parcel 000-0000-000-0000: timed out\"]')")
    tax.commit()
    tax.close()

    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    assert _row(out, "drive")["lastRead"] == "2099-10-03T06:10:00+00:00"
    assert _row(out, "gmail")["lastRead"] == "2099-10-02T06:12:00+00:00"
    assert _row(out, "payhoa-reconciliations")["lastRead"] == "2099-09-30T02:00:00+00:00"
    assert _row(out, "payhoa-budget")["lastRead"] == "2099-10-01T00:00:00+00:00"           # the newest year's stamp
    assert _row(out, "payhoa-catalog")["lastRead"] == "2099-09-03T00:00:00+00:00"          # the newest across tables
    assert _row(out, "county-tax")["lastRead"] == "2099-09-27T01:09:00+00:00"              # the newest finished run
    assert _row(out, "drive")["ageSeconds"] == int((NOW - datetime(2099, 10, 3, 6, 10, tzinfo=timezone.utc)).total_seconds())
    # A sync run that logged errors is a failure, masked, with its fix.
    [sync] = [f for f in out["failures"] if f["kind"] == "sync"]
    assert sync["source"] == "county-tax" and "1 error" in sync["title"] and sync["fix"] == "jason sync-tax"
    assert out["asOf"] == "2099-10-04T12:00:00+00:00" and out["gates"] == NO_GATES


def test_a_store_that_is_not_there_is_never_read_and_is_not_created(root, tmp_path):
    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    assert {s["standing"] for s in out["sources"]} == {st.NEVER_READ}
    assert all(s["lastRead"] == "" and s["ageSeconds"] is None for s in out["sources"])
    assert list(root.iterdir()) == []                                                     # nothing written
    assert out["failures"] == [] and out["signIns"] == []


def test_no_threshold_is_invented(root, tmp_path):
    """A source that declares no threshold shows its age and no word: not current, not stale, however old."""
    _write_json(root, "zoom/meetings.json", {"syncedAt": "2001-01-01T00:00:00+00:00", "meetings": []})
    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    zoom = _row(out, "zoom")
    assert zoom["standing"] == "" and zoom["staleAfterDays"] is None and zoom["ageSeconds"] > 0
    assert all(s.stale_after_days is None for s in st.SOURCES)                            # none declares one yet


def test_a_declared_threshold_says_current_or_stale(root):
    _write_json(root, "zoom/meetings.json", {"syncedAt": "2099-10-01T12:00:00+00:00"})
    declared = st.Source("zoom", "Zoom", "meetings", st.json_stamp("zoom/meetings.json", "syncedAt"), "jason zoom",
                         stale_after_days=2, stale_source="a made-up declaration")
    row = st.source_row(declared, root, jobs=[], refreshes=[], now=NOW)
    assert row["standing"] == st.STALE and row["staleSource"] == "a made-up declaration"
    fresh = st.source_row(declared, root, jobs=[], refreshes=[], now=datetime(2099, 10, 2, tzinfo=timezone.utc))
    assert fresh["standing"] == st.CURRENT


# --- failures from the job queue -----------------------------------------------------------------------------------------

def test_failed_jobs_set_the_standing_and_list_as_failures(root, tmp_path):
    _write_json(root, "drive/files.json", {"syncedAt": "2099-10-01T00:00:00+00:00"})
    _write_json(root, "zoom/meetings.json", {"syncedAt": "2099-10-01T00:00:00+00:00"})
    _write_json(root, "mail/items.json", {"syncedAt": "2099-10-03T00:00:00+00:00"})
    _jobs_db(root, [
        (["drive", "--sync"], "failed", "2099-10-02T02:00:00+00:00", "listing\nHttpError 500 from the sample API"),
        (["zoom"], "failed", "2099-10-02T03:00:00+00:00", "KeeperAuthRequired: sign in at a terminal"),
        (["mail"], "failed", "2099-10-02T04:00:00+00:00", "failed before its last read"),        # older than the read
        (["gmail", "--sync"], "done", "2099-10-02T05:00:00+00:00", "ok"),
        (["outlines", "--model"], "failed", "2099-10-02T06:00:00+00:00", "write to pat@example.org failed"),
    ])
    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    drive = _row(out, "drive")
    assert drive["standing"] == st.FAILED and "HttpError 500" in drive["note"] and drive["fix"] == "jason drive --sync"
    assert drive["lastJob"]["status"] == "failed" and drive["lastJob"]["command"] == "jason drive --sync"
    zoom = _row(out, "zoom")
    assert zoom["standing"] == st.NOT_SIGNED_IN and zoom["fix"] == "jason login"
    assert _row(out, "mail")["standing"] == ""                     # read since the failure: the read stands
    assert _row(out, "gmail")["lastJob"]["status"] == "done"
    jobs = [f for f in out["failures"] if f["kind"] == "job"]
    assert [f["job"] for f in jobs] == [5, 3, 2, 1]                # newest first; a job with no source still listed
    assert jobs[0]["source"] == "" and "[email]" in jobs[0]["detail"] and "example.org" not in json.dumps(out)


def test_an_offline_run_is_not_a_refresh(root, tmp_path):
    _jobs_db(root, [(["zoom", "--offline"], "failed", "2099-10-02T03:00:00+00:00", "nothing on disk")])
    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    assert _row(out, "zoom")["standing"] == st.NEVER_READ and _row(out, "zoom")["lastJob"] is None


def test_a_google_source_with_no_token_is_not_signed_in(root, tmp_path):
    _write_json(root, "gmail/correspondence.json", {"syncedAt": "2099-10-01T00:00:00+00:00"})
    gmail = _row(st.status_of(root, settings=_token(tmp_path, present=False), now=NOW, gate_view=_gates), "gmail")
    assert gmail["standing"] == st.NOT_SIGNED_IN and gmail["fix"] == "jason gmail --sync --interactive"


def test_a_refresh_that_failed_at_sign_in_speaks_for_its_source(root, tmp_path):
    _write_json(root, "payhoa/transactions.json", {"syncedAt": "2099-10-01T00:00:00+00:00"})
    log = root / "evidence" / "refreshes.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("\n".join(json.dumps(r) for r in (
        {"at": "2099-10-02T00:00:00+00:00", "system": "PayHOA", "ok": False, "address": "payhoa://x",
         "error": "Keeper is not signed in; run `jason login` in a terminal, then refresh again."},
        {"at": "2099-10-02T01:00:00+00:00", "system": "Google Drive", "ok": False, "address": "drive://y",
         "error": "Google Drive could not be read: Timeout"},
    )), encoding="utf-8")
    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    assert _row(out, "payhoa-transactions")["standing"] == st.NOT_SIGNED_IN
    assert _row(out, "drive")["standing"] == st.NEVER_READ          # one record's timeout is not the source failing
    assert [f["name"] for f in out["failures"] if f["kind"] == "refresh"] == ["Google Drive", "PayHOA"]


def test_sign_ins_are_newest_first_without_email_or_sub(root, tmp_path):
    log = root / "web" / "sign-ins.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text("\n".join(json.dumps(r) for r in (
        {"at": "2099-10-01T08:00:00+00:00", "event": "signed in", "name": "Ada Admin", "role": "admin",
         "email": "ada@example.org", "sub": "123", "provider": "community"},
        {"at": "2099-10-02T08:00:00+00:00", "event": "refused", "why": "nobody@example.org is not on the roster"},
    )), encoding="utf-8")
    out = st.status_of(root, settings=_token(tmp_path), now=NOW, gate_view=_gates)
    assert [s["event"] for s in out["signIns"]] == ["refused", "signed in"]
    assert out["signIns"][0]["why"] == "[email] is not on the roster"
    assert "example.org" not in json.dumps(out["signIns"]) and "sub" not in out["signIns"][1]


# --- the route: one of jason's admins only -------------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch, root):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: Path(d) if d is not None else root)
    monkeypatch.setattr(st, "gates", _gates)
    monkeypatch.setattr(st, "_settings", lambda: _token(tmp_path))
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {"status": st.status}, approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(dev=True))


def test_the_route_needs_a_sign_in(app):
    r = webclient.client(app).get("/api/status")
    assert r.status_code == 401


def test_the_route_refuses_anyone_but_an_admin(app):
    for name in ("Lee President", "A Manager", "Tess Two"):
        r = webclient.sign_in(webclient.client(app), name).get("/api/status")
        assert r.status_code == 403 and r.json["error"] == st.REFUSED


def test_the_route_answers_an_admin(app, root):
    _write_json(root, "drive/files.json", {"syncedAt": "2099-10-03T06:10:00+00:00"})
    r = webclient.sign_in(webclient.client(app), "Ada Admin").get("/api/status")
    assert r.status_code == 200, r.json
    assert _row(r.json, "drive")["lastRead"] == "2099-10-03T06:10:00+00:00"
    assert r.json["gates"] == NO_GATES and r.json["asOf"]


def test_the_route_refuses_an_admin_viewing_as_someone_else(app):
    c = webclient.sign_in(webclient.client(app), "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    r = c.get("/api/status")
    assert r.status_code == 403 and "Viewing as Pat Example" in r.json["error"]


def test_the_owner_view_is_refused(app):
    r = webclient.sign_in(webclient.client(app), "Ada Admin").get("/api/status?view=owner")
    assert r.status_code == 403 and r.json["ownerView"] is True


def test_status_is_no_owner_source_and_is_registered():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    assert "status" not in OWNER_SOURCES and "status" not in EXTRA_WRITERS
    assert EXTRA_LOADERS["status"] == "jason.web.extra.status:status"
