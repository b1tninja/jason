"""The scheduler (docs/scheduler-daemon-design.md, build step 2): the schedules table, its ticks on a fake clock, and
jason cadence. Temporary data folders, no network, no real worker: a job's outcome is written into the queue by hand."""

import json
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from jason import jobs, scheduler as sc, serve
from jason.integrations.registry import Cadence

ZONE = ZoneInfo("America/Los_Angeles")
T0 = datetime(2026, 10, 5, 17, 0, tzinfo=timezone.utc)          # 10:00 Pacific, inside 07-22
ADMIN = "A. Admin"


def _local(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ZONE).astimezone(timezone.utc)


def _jobs(data_dir):
    return jobs.jobs(data_dir, every=True, limit=500)


def _finish(data_dir, job_id, status, summary="", at=None):
    with closing(jobs._connect(data_dir)) as conn, conn:
        conn.execute("UPDATE jobs SET status = ?, finished = ?, summary = ? WHERE id = ?",
                     (status, (at or T0).isoformat(timespec="seconds"), summary, job_id))


def _tick(data_dir, now):
    return sc.tick(data_dir, now=now, zone=ZONE)


@pytest.fixture
def d(tmp_path):
    sc.seed(tmp_path, now=T0)
    return tmp_path


# -- the table -------------------------------------------------------------------------------------------------------------

def test_seeding_writes_a_row_per_registry_source_none_adopted(d):
    rows = {r.key: r for r in sc.schedules(d)}
    assert {"gmail", "drive", "payhoa-catalog", "zoom", "county-secured"} <= set(rows)
    gmail = rows["gmail"]
    assert gmail.argv == ("gmail", "--sync") and gmail.every == "10m" and gmail.window == "07-22"
    assert gmail.outside == "1h" and gmail.floor == "2m" and gmail.setting is sc.Setting.DEFAULT
    assert gmail.integration == "google-workspace" and not gmail.adopted
    assert "not adopted" in sc.held(gmail) and "a person runs it" in sc.held(rows["county-secured"])
    assert _tick(d, T0) == [] and _jobs(d) == []                  # nothing runs until a person adopts it
    assert sc.seed(d, now=T0) == []                               # a second seed changes nothing


def test_an_override_survives_a_registry_reseed(d, monkeypatch):
    sc.set_cadence(d, "gmail", every="30m", by=ADMIN, now=T0, zone=ZONE)
    changed = tuple(Cadence(c.source_key, c.argv, every="20m" if c.source_key in ("gmail", "drive") else c.every,
                            cron=c.cron, window=c.window, outside=c.outside, floor=c.floor, stale_after=c.stale_after,
                            manual=c.manual) for c in sc.cadences())
    monkeypatch.setattr(sc, "cadences", lambda: changed)
    lines = sc.seed(d, now=T0)
    assert any(line.startswith("gmail") and "kept" in line for line in lines)
    gmail, drive = sc.get(d, "gmail"), sc.get(d, "drive")
    assert gmail.every == "30m" and gmail.default_every == "20m" and gmail.setting is sc.Setting.ADMIN
    assert gmail.set_by == ADMIN and gmail.adopted
    assert drive.every == "20m" and drive.setting is sc.Setting.DEFAULT       # a default row follows the registry
    [restored] = sc.restore(d, "gmail", by=ADMIN, now=T0, zone=ZONE)
    assert restored.every == "20m" and restored.setting is sc.Setting.DEFAULT and restored.adopted
    monkeypatch.setattr(sc, "cadences", lambda: tuple(c for c in changed if c.source_key != "zoom"))
    sc.seed(d, now=T0)
    assert sc.get(d, "zoom").retired and "retired" in sc.held(sc.get(d, "zoom"))


def test_a_cadence_faster_than_the_floor_is_refused_with_the_reason(d):
    with pytest.raises(sc.ScheduleRefused, match="floor 2m"):
        sc.set_cadence(d, "gmail", every="1m", by=ADMIN, now=T0, zone=ZONE)
    with pytest.raises(sc.ScheduleRefused, match="floor 6h"):
        sc.set_cadence(d, "payhoa-catalog", cron="0 */2 * * *", by=ADMIN, now=T0, zone=ZONE)
    with pytest.raises(sc.ScheduleRefused, match="--by"):
        sc.set_cadence(d, "gmail", every="1h", by="", now=T0, zone=ZONE)
    with pytest.raises(sc.ScheduleRefused, match="window"):
        sc.set_cadence(d, "gmail", every="1h", window="7am-10pm", by=ADMIN, now=T0, zone=ZONE)
    assert not sc.get(d, "gmail").adopted
    assert any(e["event"] == "refused" and e["by"] == ADMIN for e in sc.decisions(d))
    ok = sc.set_cadence(d, "payhoa-catalog", cron="0 1 * * *", by=ADMIN, now=T0, zone=ZONE)
    assert ok.cron == "0 1 * * *" and ok.adopted


def test_a_due_source_is_queued_once_and_not_again_while_its_job_is_pending(d):
    sc.restore(d, "gmail", by=ADMIN, now=T0, zone=ZONE)
    [made] = _tick(d, T0)
    assert made["event"] == "enqueued" and made["command"] == "jason gmail --sync"
    [job] = _jobs(d)
    assert job.argv == ["gmail", "--sync"] and job.job_class is jobs.JobClass.GOOGLE   # an ordinary job, its lane
    assert _tick(d, T0 + timedelta(seconds=45)) == []
    assert _tick(d, T0 + timedelta(minutes=25)) == [] and len(_jobs(d)) == 1          # still queued: coalesced
    _finish(d, job.id, "done", at=T0 + timedelta(minutes=26))
    assert [e["event"] for e in _tick(d, T0 + timedelta(minutes=26))] == ["enqueued"] and len(_jobs(d)) == 2
    assert sc.get(d, "gmail").last_result == "queued"


def test_a_persons_queued_job_for_the_same_command_coalesces(d):
    sc.restore(d, "drive", by=ADMIN, now=T0, zone=ZONE)
    mine = jobs.add(d, ["drive", "--sync"])
    [e] = _tick(d, T0)
    assert e["event"] == "coalesced" and e["job"] == mine.id and len(_jobs(d)) == 1
    with pytest.raises(sc.ScheduleRefused, match="already queued"):
        sc.run_now(d, "drive", by=ADMIN, now=T0)


def test_the_window_is_respected(d):
    sc.set_cadence(d, "calendar", every="30m", window="07-22", by=ADMIN, now=_local(2026, 10, 5, 23), zone=ZONE)
    assert _tick(d, _local(2026, 10, 5, 23)) == [] and _jobs(d) == []
    assert _tick(d, _local(2026, 10, 6, 3)) == []
    nxt = sc.next_runs(d, now=_local(2026, 10, 6, 3), zone=ZONE)
    assert nxt[0]["source"] == "calendar" and nxt[0]["at"] == sc._s(_local(2026, 10, 6, 7))
    [e] = _tick(d, _local(2026, 10, 6, 7, 1))
    assert e["event"] == "catch-up" and len(_jobs(d)) == 1          # the run missed overnight, once, in the window
    # gmail's registry outside cadence: hourly overnight, not every ten minutes.
    sc.restore(d, "gmail", by=ADMIN, now=_local(2026, 10, 6, 23), zone=ZONE)
    _tick(d, _local(2026, 10, 6, 23))
    assert sc._t(sc.get(d, "gmail").next_due) == _local(2026, 10, 7, 0)


def test_a_missed_run_after_downtime_is_one_catch_up_never_a_burst(d):
    sc.restore(d, "payhoa-catalog", by=ADMIN, now=_local(2026, 10, 5, 1), zone=ZONE)   # cron 0 2 * * *
    assert sc._t(sc.get(d, "payhoa-catalog").next_due) == _local(2026, 10, 5, 2)
    back = _local(2026, 10, 8, 10)                                                     # three nights missed
    events = _tick(d, back)
    assert [e["event"] for e in events] == ["catch-up"] and len(_jobs(d)) == 1
    _finish(d, _jobs(d)[0].id, "done", at=back + timedelta(minutes=5))
    assert _tick(d, back + timedelta(minutes=6)) == [] and len(_jobs(d)) == 1
    assert sc._t(sc.get(d, "payhoa-catalog").next_due) == _local(2026, 10, 9, 2)
    assert [e["event"] for e in _tick(d, _local(2026, 10, 9, 2, 1))] == ["enqueued"]


def test_failures_back_off_and_a_success_resets(d):
    sc.restore(d, "gmail", by=ADMIN, now=T0, zone=ZONE)
    _tick(d, T0)
    _finish(d, _jobs(d)[0].id, "failed", "HttpError 503 backendError")
    [e] = _tick(d, T0 + timedelta(minutes=1))
    assert e["event"] == "backoff" and e["failures"] == 1
    row = sc.get(d, "gmail")
    assert row.failures == 1 and sc._t(row.backoff_until) == T0 + timedelta(minutes=6)   # 5 minutes from the outcome
    assert _tick(d, T0 + timedelta(minutes=10)) and len(_jobs(d)) == 2                     # due (10m), backoff past
    _finish(d, _jobs(d)[0].id, "failed", "HttpError 503")
    _tick(d, T0 + timedelta(minutes=11))
    row = sc.get(d, "gmail")
    assert row.failures == 2 and sc._t(row.backoff_until) == T0 + timedelta(minutes=21)    # doubled
    assert _tick(d, T0 + timedelta(minutes=20)) == []
    assert _tick(d, T0 + timedelta(minutes=21)) and len(_jobs(d)) == 3
    _finish(d, _jobs(d)[0].id, "done")
    assert [e["event"] for e in _tick(d, T0 + timedelta(minutes=22))] == ["recovered"]
    row = sc.get(d, "gmail")
    assert row.failures == 0 and row.backoff_until == "" and row.last_result == "done"
    assert sc.backoff(30) == sc.BACKOFF_CAP and sc.backoff(1, "6h") == timedelta(hours=6)


def test_a_retry_after_the_job_printed_is_honoured(d):
    sc.restore(d, "zoom", by=ADMIN, now=_local(2026, 10, 5, 2), zone=ZONE)
    _tick(d, _local(2026, 10, 5, 3))
    _finish(d, _jobs(d)[0].id, "failed", "429 Too Many Requests\nRetry-After: 2026-10-07T00:00:00Z")
    now = _local(2026, 10, 5, 3, 5)
    [e] = _tick(d, now)
    assert sc._t(sc.get(d, "zoom").backoff_until) == datetime(2026, 10, 7, tzinfo=timezone.utc)
    assert sc.retry_after("Retry-After: 120", now) == now + timedelta(seconds=120)
    assert sc.retry_after("retry-after: Wed, 07 Oct 2026 00:00:00 GMT", now) == datetime(2026, 10, 7, tzinfo=timezone.utc)
    assert sc.retry_after("no header", now) is None


def test_a_sign_in_failure_pauses_the_integration_and_no_timer_resumes_it(d):
    sc.restore(d, None, by=ADMIN, now=T0, zone=ZONE)
    _tick(d, T0)
    catalog = sc.run_now(d, "payhoa-catalog", by=ADMIN, now=T0)   # the nightly catalog is not due at 10:00
    _finish(d, catalog.id, "failed", "jason.keeper.KeeperAuthRequired: run jason login at a terminal")
    events = _tick(d, T0 + timedelta(minutes=1))
    paused = {e["source"] for e in events if e["event"] == "paused-sign-in"}
    assert {"payhoa-catalog", "payhoa-ledger", "utility-payments"} <= paused and "gmail" not in paused
    row = sc.get(d, "payhoa-catalog")
    assert row.paused and row.pause_kind is sc.PauseKind.SIGN_IN and "KeeperAuthRequired" in row.paused_why
    count = len([j for j in _jobs(d) if j.job_class is jobs.JobClass.PAYHOA])
    for days in (1, 3, 10):                                    # no timer resumes it
        _tick(d, T0 + timedelta(days=days))
    assert len([j for j in _jobs(d) if j.job_class is jobs.JobClass.PAYHOA]) == count
    assert sc.get(d, "payhoa-catalog").paused and "needs sign-in" in sc.held(sc.get(d, "payhoa-catalog"))
    resumed = sc.resume(d, "payhoa-catalog", by=ADMIN, now=T0 + timedelta(days=10))
    assert {r.key for r in resumed} >= {"payhoa-catalog", "payhoa-ledger"} and not any(r.paused for r in resumed)
    assert sc.get(d, "payhoa-catalog").failures == 0
    later = _tick(d, _local(2026, 10, 16, 2, 1))
    assert any(e["source"] == "payhoa-catalog" and e["event"] in ("enqueued", "catch-up") for e in later)


def test_a_connection_needing_sign_in_pauses_and_a_persons_good_check_resumes(d):
    sc.restore(d, "gmail", by=ADMIN, now=T0, zone=ZONE)

    def connection(state, check, at):
        (d / "integrations.json").write_text(json.dumps({"community": "x", "connections": [
            {"community": "x", "integration": "google-workspace", "state": state, "lastChecked": sc._s(at),
             "lastCheck": check}]}), encoding="utf-8")
    connection("needs sign-in", "failed: GoogleAuthRequired", T0 - timedelta(minutes=1))
    events = _tick(d, T0)
    assert any(e["event"] == "paused-sign-in" and e["source"] == "gmail" for e in events) and _jobs(d) == []
    assert _tick(d, T0 + timedelta(hours=5)) == [] and _jobs(d) == []
    connection("connected", "ok: drive root listed", T0 + timedelta(hours=6))      # a person signed in and checked
    events = _tick(d, T0 + timedelta(hours=6, minutes=1))
    assert [e["event"] for e in events if e["source"] == "gmail"] == ["resumed", "catch-up"]
    assert not sc.get(d, "gmail").paused and len(_jobs(d)) == 1


def test_a_person_pause_and_resume_are_recorded(d):
    sc.restore(d, "gmail", by=ADMIN, now=T0, zone=ZONE)
    with pytest.raises(sc.ScheduleRefused, match="--why"):
        sc.pause(d, "gmail", why="", by=ADMIN)
    row = sc.pause(d, "gmail", why="mailbox migration", by=ADMIN, now=T0)
    assert row.paused and row.pause_kind is sc.PauseKind.PERSON and row.paused_by == ADMIN
    assert _tick(d, T0) == [] and _jobs(d) == []
    sc.resume(d, "gmail", by="B. Board", now=T0 + timedelta(hours=1))
    assert sc.get(d, "gmail").resumed_by == "B. Board"
    assert [e["event"] for e in sc.decisions(d) if e["source"] == "gmail"][-2:] == ["paused", "resumed"]


def test_a_cadence_that_writes_is_never_scheduled(d, monkeypatch):
    writer = Cadence("owner-push", ("owner-info", "--apply", "--yes"), every="1h")
    monkeypatch.setattr(sc, "cadences", lambda: (writer,))
    sc.seed(d, now=T0)
    row = sc.get(d, "owner-push")
    assert "writes (--yes)" in row.refused and "refused" in sc.held(row)
    for call in (lambda: sc.restore(d, "owner-push", by=ADMIN, now=T0),
                 lambda: sc.set_cadence(d, "owner-push", every="2h", by=ADMIN, now=T0),
                 lambda: sc.run_now(d, "owner-push", by=ADMIN, now=T0)):
        with pytest.raises(sc.ScheduleRefused, match="writes"):
            call()
    sc.restore(d, None, by=ADMIN, now=T0)                      # --restore-all passes it by
    assert not sc.get(d, "owner-push").adopted and _tick(d, T0 + timedelta(hours=2)) == [] and _jobs(d) == []


def test_cron_reads_in_the_zone_and_matches_either_day():
    weekly = sc.Cron.parse("0 4 5 * 1")                        # Mondays and the 5th
    fires = [f.astimezone(ZONE).date().isoformat() for f, _ in zip(weekly.fires(_local(2026, 10, 1, 0), ZONE), range(4))]
    assert fires == ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
    assert sc.Cron.parse("0 2 * * *").next_after(_local(2026, 10, 5, 3), ZONE) == _local(2026, 10, 6, 2)
    assert sc.Cron.parse("*/15 * * * *").shortest_gap(ZONE, T0) == timedelta(minutes=15)
    assert sc.Cron.parse("0 9 * * 0").next_after(_local(2026, 10, 5, 0), ZONE) == _local(2026, 10, 11, 9)
    with pytest.raises(sc.ScheduleRefused):
        sc.Cron.parse("0 2 * *")
    with pytest.raises(sc.ScheduleRefused):
        sc.Cron.parse("0 2 * * MON")


def test_each_registry_read_takes_its_accounts_lane():
    lane = {"google-workspace": jobs.JobClass.GOOGLE, "payhoa": jobs.JobClass.PAYHOA}
    for c in sc.cadences():
        integ = sc.integration_of(c.source_key)
        if integ.key in lane:
            assert jobs.job_class(list(c.argv)) is lane[integ.key], c.source_key
    assert jobs.job_class(["sync-tax"]) is jobs.JobClass.COUNTY


def test_jitter_stays_small():
    import random

    row = sc.Schedule("x", "i", ("x",), every="10m", floor="2m")
    for seed in range(20):
        at = sc.next_due(row, T0, ZONE, random.Random(seed))
        assert T0 + timedelta(minutes=10) <= at <= T0 + timedelta(minutes=11)


# -- jason cadence -------------------------------------------------------------------------------------------------------

@pytest.fixture
def cli(tmp_path, monkeypatch):
    from jason.cli import build_parser

    monkeypatch.setattr(serve, "profile_names", lambda: ["mystique", "other"])
    monkeypatch.setattr(serve, "profile_data_dir", lambda name, env=None: tmp_path / name)
    monkeypatch.setattr(sc, "zone_of", lambda name: "America/Los_Angeles")

    def jason(*argv):
        args = build_parser().parse_args(["cadence", *argv])
        return args.func(args)
    return jason


def test_jason_cadence_lists_changes_and_records(cli, tmp_path, capsys):
    assert cli() == 0
    out = capsys.readouterr().out
    assert "gmail: jason gmail --sync" in out and "not adopted" in out and "floor 2m" in out
    assert cli("gmail", "--every", "1m", "--by", ADMIN) == 2 and "floor 2m" in capsys.readouterr().err
    assert cli("gmail", "--every", "30m", "--window", "08-20", "--by", ADMIN) == 0
    assert "changed by A. Admin" in capsys.readouterr().out
    assert cli("--restore", "drive", "--by", ADMIN) == 0
    assert cli("--pause", "drive", "--why", "testing", "--by", ADMIN) == 0
    assert cli("--resume", "drive") == 2 and "--by" in capsys.readouterr().err
    assert cli("--resume", "drive", "--by", ADMIN) == 0
    assert cli("--run-now", "zoom", "--by", ADMIN) == 0 and "queued as job 1" in capsys.readouterr().out
    assert cli("--run-now", "county-secured", "--by", ADMIN) == 2
    capsys.readouterr()
    assert cli("--json", "--community", "other") == 0
    assert all(not r["adopted"] for r in json.loads(capsys.readouterr().out)["schedules"])   # another community's table
    assert cli("--json") == 0
    rows = {r["source"]: r for r in json.loads(capsys.readouterr().out)["schedules"]}
    assert rows["gmail"]["every"] == "30m" and rows["gmail"]["window"] == "08-20" and rows["gmail"]["setBy"] == ADMIN
    assert rows["drive"]["adopted"] and rows["drive"]["paused"] is None and rows["zoom"]["lastJob"] == 1
    assert rows["drive"]["nextRun"] and not rows["calendar"]["nextRun"]
    assert cli("nosuch", "--every", "1h", "--by", ADMIN) == 2 and "no source" in capsys.readouterr().err


# -- in jason serve --------------------------------------------------------------------------------------------------------

def test_the_heartbeat_lists_the_next_runs(tmp_path):
    data = tmp_path / "a"
    sc.seed(data, now=T0)
    sc.restore(data, "gmail", by=ADMIN, now=T0, zone=ZONE)
    sc.restore(data, "payhoa-catalog", by=ADMIN, now=T0, zone=ZONE)
    stop = threading.Event()

    def schedule(profile, data_dir, stop_, state):
        sc.run(profile, data_dir, stop_, state, every=0.05, zone="America/Los_Angeles", clock=lambda: T0,
               log=lambda s: None)
    loop = threading.Thread(target=serve.run, args=({"a": data},),
                            kwargs={"schedule": schedule, "beat": 0.05, "tick": 0.02, "log": lambda s: None, "stop": stop})
    loop.start()
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not (serve.read_heartbeat(data) or {}).get("schedules"):
            time.sleep(0.02)
        beat = serve.read_heartbeat(data)
        assert beat["scheduler"] and beat["schedulerRunning"] and beat["schedulerZone"] == "America/Los_Angeles"
        assert [s["source"] for s in beat["schedules"]] == ["gmail", "payhoa-catalog"]
        lines = serve.status_lines([{**serve.judge(beat), "profile": "a"}])
        assert any("scheduler on" in line for line in lines)
        assert any(line.strip().startswith("next") and "payhoa-catalog" in line for line in lines)
        assert [j.argv for j in _jobs(data)] == [["gmail", "--sync"]]      # the scheduler queued it; no worker ran
    finally:
        stop.set()
        loop.join(timeout=10)
    assert not loop.is_alive() and serve.read_heartbeat(data)["state"] == "stopped"


def test_serve_refuses_only_when_every_part_is_off(tmp_path):
    with pytest.raises(serve.ServeRefused, match="--no-scheduler"):
        serve.run({"a": tmp_path / "a"})
