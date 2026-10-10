"""The integrations registry, the connections store, today's states, Status's thresholds from the registry, and
``jason integrations`` (docs/integrations-design.md, build step 1).

Made-up settings, stores, and credentials in tmp_path; no Google, PayHOA, Zoom, Keeper, or network call (a live check
is a fake), and no credential's value in any output.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.integrations import checks
from jason.integrations import connections as cn
from jason.integrations.registry import (
    REGISTRY,
    AuthMethod,
    ConnectionState,
    Scope,
    cadence_for,
    cadences,
    duration,
    integration,
    integration_of,
)
from jason.web.extra import status as st

NOW = datetime(2099, 10, 4, 12, 0, tzinfo=timezone.utc)
SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
FAKE_UID = "fakeRecordUid0123456789abcdefFAKE"               # secret-shaped on purpose: it must never be printed
FAKE_REFRESH = "1//fake-refresh-token-0123456789abcdef"


# --- the registry ------------------------------------------------------------------------------------------------------

def test_keys_are_unique_slugs():
    keys = [i.key for i in REGISTRY]
    assert len(keys) == len(set(keys)) and all(SLUG.match(k) for k in keys)
    sources = [c.source_key for c in cadences()]
    assert len(sources) == len(set(sources))
    for i in REGISTRY:
        caps = [c.key for c in i.capabilities]
        assert len(caps) == len(set(caps)), i.key
        assert i.setup_steps, f"{i.key} has no setup steps"


def test_every_status_source_has_a_cadence_and_an_integration():
    for s in st._sources():
        assert cadence_for(s.key) is not None, s.key
        assert integration_of(s.key) is not None, s.key


def test_the_missing_sources_have_cadences():
    for key in ("calendar", "tasks", "idoxs", "vendor-portals", "permits"):
        assert cadence_for(key) is not None, key
    assert integration_of("permits").key == "accela"
    assert integration_of("vendor-portals").instances                     # its instances are the profile's rows


def test_floors_and_thresholds_hold_against_each_cadence():
    for c in cadences():
        assert c.floor and c.stale_after, c.source_key
        assert c.floor_delta <= c.period, f"{c.source_key}: floor above its default"
        assert c.stale_delta >= c.period, f"{c.source_key}: stale before its next default run"
        assert c.argv and c.argv[0], c.source_key
        assert c.every or c.cron, c.source_key


def test_writes_are_off_by_default_and_marked():
    for i in REGISTRY:
        on = i.default_capabilities()
        assert all(not c.writes for c in i.capabilities if c.key in on)
        assert any(not c.writes for c in i.capabilities), f"{i.key}: no read capability"


def test_google_workspace_is_each_communitys_own_web_client():
    g = integration("google-workspace")
    assert g.scope is Scope.COMMUNITY and g.auth is AuthMethod.OAUTH_WEB
    assert len(g.setup_steps) == 9 and "Internal" in g.setup_steps[3].admin_does
    assert {c.source_key for c in g.sources} == {"drive", "gmail", "calendar", "tasks", "responses-gmail"}
    assert g.rate_limit.source and g.rate_limit.read_on


def test_the_response_checks_are_proposed_cadences_in_the_right_lanes():
    """The check for new responses (docs/responses-design.md, Cadence): proposed, never faster than its floor, a read that
    records nothing, and each on its account's job lane."""
    from jason import jobs

    gmail, payhoa = cadence_for("responses-gmail"), cadence_for("responses-payhoa")
    assert integration_of("responses-gmail").key == "google-workspace" and integration_of("responses-payhoa").key == "payhoa"
    assert gmail.argv == ("responses", "--check", "--channel", "gmail", "--channel", "mail", "--channel", "forms",
                          "--by", "scheduler")
    assert payhoa.argv == ("responses", "--check", "--channel", "payhoa", "--by", "scheduler")
    assert (gmail.every, gmail.window, gmail.outside, gmail.floor, gmail.stale_after) == ("1h", "07-22", "4h", "15m", "1d")
    assert (payhoa.every, payhoa.window, payhoa.outside, payhoa.floor, payhoa.stale_after) == ("2h", "07-22", "", "1h", "1d")
    assert gmail.proposed and payhoa.proposed and not gmail.manual and not payhoa.manual
    assert not {"--yes", "--apply", "--confirm", "--read"} & set(gmail.argv + payhoa.argv)       # a check records nothing
    from jason.cli import build_parser

    for cad in (gmail, payhoa):                                      # the scheduler's command line is one the CLI parses
        parsed = build_parser().parse_args(list(cad.argv))
        assert parsed.command == "responses" and parsed.check and parsed.by == "scheduler"
    assert build_parser().parse_args(list(gmail.argv)).channel == ["gmail", "mail", "forms"]
    assert jobs.job_class(list(gmail.argv)) is jobs.JobClass.GOOGLE
    assert jobs.job_class(list(payhoa.argv)) is jobs.JobClass.PAYHOA
    # the lane follows the channels asked for: PayHOA alone, else Google (Gmail is among them); disk-only acts are local
    assert jobs.job_class(["responses", "--check", "--channel=payhoa"]) is jobs.JobClass.PAYHOA
    assert jobs.job_class(["responses", "--check", "--channel", "payhoa", "--channel", "gmail"]) is jobs.JobClass.GOOGLE
    assert jobs.job_class(["responses", "--check"]) is jobs.JobClass.GOOGLE
    assert jobs.job_class(["responses", "--read", "gmail:abc", "--by", "A"]) is jobs.JobClass.GOOGLE
    for argv in (["responses"], ["responses", "--list", "--new"], ["responses", "--show", "gmail:abc"],
                 ["responses", "--confirm", "gmail:abc", "--by", "A"]):
        assert jobs.job_class(argv) is jobs.JobClass.LOCAL, argv


def test_status_reads_the_responses_checks_from_the_inboxs_channels(tmp_path):
    """Status shows the two sources by the inbox's own stamp (the newest channel check that succeeded), and a channel whose
    last try failed is an error that check logged. Nothing is called."""
    root = tmp_path / "data"
    assert [s.key for s in st.SOURCES if s.key.startswith("responses-")] == ["responses-gmail", "responses-payhoa"]
    tok = tmp_path / "t.json"
    tok.write_text("{}", encoding="utf-8")
    settings = SimpleNamespace(google_oauth_token_file=tok, smud_db=None)
    rows = {r["key"]: r for r in st.source_rows(root, settings=settings, now=NOW)}
    assert rows["responses-gmail"]["standing"] == st.NEVER_READ and rows["responses-payhoa"]["lastRead"] == ""
    (root / "responses").mkdir(parents=True)
    (root / "responses" / "inbox.json").write_text(json.dumps({"version": 1, "arrivals": {}, "channels": {
        "gmail": {"lastOk": "2099-10-04T11:00:00+00:00", "lastTried": "2099-10-04T11:00:00+00:00", "ended": "ok"},
        "mail": {"lastOk": "2099-10-04T11:30:00+00:00", "lastTried": "2099-10-04T11:30:00+00:00", "ended": "ok"},
        "forms": {"lastTried": "2099-10-04T11:30:00+00:00", "ended": "skipped", "reason": "no request"},
        "payhoa": {"lastOk": "2099-10-01T09:00:00+00:00", "lastTried": "2099-10-04T11:45:00+00:00", "ended": "sign-in",
                   "reason": "KeeperAuthRequired: sign in"}}}), encoding="utf-8")
    rows = {r["key"]: r for r in st.source_rows(root, settings=settings, now=NOW)}
    assert rows["responses-gmail"]["lastRead"] == "2099-10-04T11:30:00+00:00" and rows["responses-gmail"]["standing"] == st.CURRENT
    assert rows["responses-payhoa"]["lastRead"] == "2099-10-01T09:00:00+00:00" and rows["responses-payhoa"]["standing"] == st.STALE
    assert rows["responses-gmail"]["staleAfter"] == "1d" and rows["responses-payhoa"]["staleAfter"] == "1d"
    read = st.SOURCES[[s.key for s in st.SOURCES].index("responses-payhoa")].read(root)
    assert read.errors == ("payhoa: KeeperAuthRequired: sign in",) and read.error_at == "2099-10-04T11:45:00+00:00"
    assert st.SOURCES[[s.key for s in st.SOURCES].index("responses-gmail")].read(root).errors == ()


def test_rate_limits_say_where_or_none_published():
    for i in REGISTRY:
        r = i.rate_limit
        assert r.published
        assert bool(r.source) == bool(r.read_on), i.key
        assert r.polite == (not r.source)


def test_cadences_by_scope():
    assert {c.source_key for c in cadences(Scope.INSTANCE)} == {"county-tax", "county-secured", "county-land", "county-land-full"}
    assert set(cadences(Scope.COMMUNITY)) | set(cadences(Scope.INSTANCE)) == set(cadences())
    with pytest.raises(KeyError, match="known"):
        integration("nope")


def test_durations():
    assert duration("10m") == timedelta(minutes=10) and duration("2h") == timedelta(hours=2)
    assert duration("") is None
    with pytest.raises(ValueError):
        duration("soon")


def test_the_registry_names_no_association():
    from jason.community import community
    from jason.community.profile import profile_name

    text = Path(cn.__file__).with_name("registry.py").read_text(encoding="utf-8").lower()
    terms = {profile_name()} | {p.key for p in community().vendor_portals()} | {p.vendor for p in community().vendor_portals()}
    assert not [t for t in terms if t and t.lower() in text]


def test_vault_paths_follow_the_scheme():
    assert cn.vault_path("oakview", "payhoa", "login") == "jason/community/oakview/payhoa/login"
    assert cn.vault_path(cn.INSTANCE, "instance-sign-in", "oauth-client") == \
        "jason/instance/instance/instance-sign-in/oauth-client"
    assert cn.default_vault_path(integration("vendor-portals"), "oakview") == "jason/community/oakview/vendor-portals/"
    assert cn.default_vault_path(integration("law-library"), cn.INSTANCE) == ""
    paths = pytest.importorskip("jason.vault.paths")                       # the vault's own scheme, when it is built
    assert paths.vault_path("oakview", "payhoa", "login") == cn.vault_path("oakview", "payhoa", "login")


# --- the connections store ---------------------------------------------------------------------------------------------

def _conn(**over) -> cn.Connection:
    base = dict(community="oakview", integration="zoom", account="board@example.com", capabilities=("meetings-read",),
                vault_path="jason/community/oakview/zoom/app", state=ConnectionState.CONNECTED,
                connected_by="A. Admin", connected_at="2099-10-01T00:00:00+00:00",
                overrides=(cn.ScheduleOverride("zoom", every="6h", by="A. Admin", at="2099-10-02T00:00:00+00:00",
                                               why="the board asked"),))
    base.update(over)
    return cn.Connection(**base)


def test_connections_round_trip_under_the_store_lock(tmp_path, monkeypatch):
    import jason.locks as locks

    held = []
    real = locks.hold

    def spy(resource, key="", **kw):
        held.append((resource, key))
        return real(resource, key, **kw)

    monkeypatch.setattr(locks, "hold", spy)
    path = tmp_path / "oakview" / cn.FILE
    rows = [_conn(), _conn(integration="payhoa", state=ConnectionState.PAUSED, note="paused by A. Admin: billing")]
    cn.save("oakview", rows, path, now=NOW)
    assert (locks.Resource.STORE, "integrations-oakview") in held
    back = cn.load("oakview", path)
    assert back == {"zoom": rows[0], "payhoa": rows[1]}
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["updatedAt"] == "2099-10-04T12:00:00+00:00" and body["connections"][1]["state"] == "connected"
    assert cn.load("oakview", tmp_path / "none.json") == {}


def test_a_word_that_is_no_state_is_refused(tmp_path):
    path = tmp_path / cn.FILE
    path.write_text(json.dumps({"connections": [{"integration": "zoom", "state": "great"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a connection state"):
        cn.load("oakview", path)
    with pytest.raises(ValueError, match="not 'oakview'"):
        cn.save("oakview", [_conn(community="elmwood")], tmp_path / "x.json")


def test_a_check_is_recorded_and_a_pause_kept(tmp_path):
    path = tmp_path / cn.FILE
    zoom = integration("zoom")
    row = cn.record_check("oakview", zoom, ok=True, words="listed one meeting", state=ConnectionState.CONNECTED,
                          path=path, now=NOW, by="A. Admin")
    assert row.state is ConnectionState.CONNECTED and row.connected_by == "A. Admin" and row.last_check.startswith("ok")
    assert row.vault_path == "jason/community/oakview/zoom/app" and row.capabilities == zoom.default_capabilities()
    later = NOW + timedelta(days=1)
    row = cn.record_check("oakview", zoom, ok=False, words="ZoomAuthError: 401", state=ConnectionState.NEEDS_SIGN_IN,
                          path=path, now=later, by="B. Admin")
    assert row.state is ConnectionState.NEEDS_SIGN_IN and row.connected_by == "A. Admin"     # the first connection kept
    cn.save("oakview", [replace(row, state=ConnectionState.PAUSED, note="paused")], path)
    row = cn.record_check("oakview", zoom, ok=True, words="ok", state=ConnectionState.CONNECTED, path=path)
    assert row.state is ConnectionState.PAUSED                                                  # a pause is a person's


def test_two_writers_do_not_lose_each_others_rows(tmp_path):
    path = tmp_path / cn.FILE
    keys = ["zoom", "payhoa", "postscanmail", "accela"]

    def write(key):
        cn.record_check("oakview", integration(key), ok=True, words="ok", state=ConnectionState.CONNECTED, path=path)

    threads = [threading.Thread(target=write, args=(k,)) for k in keys]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(cn.load("oakview", path)) == set(keys)


# --- today's state -----------------------------------------------------------------------------------------------------

def _settings(tmp_path: Path, *, keeper=True, token=True, uids=("payhoa", "zoom", "google_oauth")) -> SimpleNamespace:
    tmp_path.mkdir(parents=True, exist_ok=True)
    kc = tmp_path / "keeper-config.json"
    if keeper:
        kc.write_text("{}", encoding="utf-8")
    tok = tmp_path / "google-token.json"
    if token:
        tok.write_text(json.dumps({"refresh_token": FAKE_REFRESH}), encoding="utf-8")
    found = {f"{u}_record_uid": FAKE_UID for u in uids}
    return SimpleNamespace(keeper_config=kc, google_oauth_token_file=tok, google_oauth_client_file=None,
                           smud_db=None, lawlibrary_home=tmp_path / "law",
                           record_uid=lambda name: found.get(f"{name.lower()}_record_uid", ""))


def _status_row(key: str, standing: str = "", last: str = "", note: str = "") -> dict:
    return {"key": key, "name": key, "standing": standing, "lastRead": last, "note": note}


def test_state_follows_what_exists(tmp_path):
    zoom = integration("zoom")
    s = _settings(tmp_path)
    state = lambda **kw: cn.state_of(zoom, community="oakview", **kw).state   # noqa: E731

    assert state(settings=_settings(tmp_path / "a", uids=())) is ConnectionState.NOT_SET_UP
    (tmp_path / "b").mkdir()
    assert state(settings=_settings(tmp_path / "b", keeper=False)) is ConnectionState.NEEDS_SIGN_IN
    assert state(settings=s) is ConnectionState.NOT_SET_UP                                  # set, nothing read yet
    assert state(settings=s, rows=[_status_row("zoom", st.CURRENT, "2099-10-03T00:00:00+00:00")]) \
        is ConnectionState.CONNECTED
    assert state(settings=s, rows=[_status_row("zoom", st.STALE, "2099-09-01T00:00:00+00:00")]) \
        is ConnectionState.CONNECTED                                                         # stale is the source's word
    assert state(settings=s, rows=[_status_row("zoom", st.FAILED, "2099-10-01T00:00:00+00:00", "failed")]) \
        is ConnectionState.FAILING
    assert state(settings=s, rows=[_status_row("zoom", st.NOT_SIGNED_IN, "", "jason login")]) \
        is ConnectionState.NEEDS_SIGN_IN
    paused = cn.Connection("oakview", "zoom", state=ConnectionState.PAUSED, note="paused by A. Admin")
    assert state(settings=s, connection=paused) is ConnectionState.PAUSED
    failed = cn.Connection("oakview", "zoom", last_checked="2099-10-04T00:00:00+00:00", last_check="failed: timed out")
    assert state(settings=s, connection=failed, rows=[_status_row("zoom", st.CURRENT, "2099-10-03T00:00:00+00:00")]) \
        is ConnectionState.FAILING
    signed_out = replace(failed, last_check="failed: KeeperAuthRequired: run jason login")
    assert state(settings=s, connection=signed_out) is ConnectionState.NEEDS_SIGN_IN


def test_google_needs_its_token(tmp_path):
    g = integration("google-workspace")
    (tmp_path / "a").mkdir()
    reading = cn.state_of(g, community="oakview", settings=_settings(tmp_path / "a", token=False))
    assert reading.state is ConnectionState.NEEDS_SIGN_IN and "Google token" in reading.why
    (tmp_path / "b").mkdir()
    ok = cn.state_of(g, community="oakview", settings=_settings(tmp_path / "b"),
                     rows=[_status_row("drive", st.CURRENT, "2099-10-04T11:00:00+00:00")])
    assert ok.state is ConnectionState.CONNECTED and ok.configured


def test_an_integration_checked_from_disk_is_connected_when_found(tmp_path):
    law = integration("law-library")
    s = _settings(tmp_path)
    assert cn.state_of(law, community=cn.INSTANCE, settings=s).state is ConnectionState.NOT_SET_UP
    (tmp_path / "law").mkdir()
    assert cn.state_of(law, community=cn.INSTANCE, settings=s).state is ConnectionState.CONNECTED
    # One with a live check is not connected until it has run.
    assert cn.state_of(integration("local-models"), community=cn.INSTANCE, settings=s).state \
        is ConnectionState.NOT_SET_UP


def test_readings_read_the_status_rows_from_disk(tmp_path):
    root = tmp_path / "data"
    (root / "zoom").mkdir(parents=True)
    (root / "zoom" / "meetings.json").write_text(json.dumps({"syncedAt": "2099-10-03T03:00:00+00:00"}),
                                                 encoding="utf-8")
    got = {r.integration.key: r for r in cn.readings("oakview", scope=Scope.COMMUNITY, settings=_settings(tmp_path),
                                                    root=root, now=NOW, path=tmp_path / cn.FILE)}
    assert got["zoom"].state is ConnectionState.CONNECTED
    assert got["zoom"].sources[0]["standing"] == st.CURRENT                                  # 33 h old, stale after 2 d
    assert got["postscanmail"].state is ConnectionState.NOT_SET_UP


def test_an_override_faster_than_the_floor_is_refused():
    zoom = integration("zoom")
    assert cn.below_floor(zoom, cn.ScheduleOverride("zoom", every="30m"))
    assert not cn.below_floor(zoom, cn.ScheduleOverride("zoom", every="6h"))


# --- Status, with the registry's thresholds ----------------------------------------------------------------------------

def test_status_sources_carry_their_integrations_threshold(tmp_path):
    for s in st.SOURCES:
        cad = cadence_for(s.key)
        assert s.stale_after_days == cad.stale_after_days and integration_of(s.key).name in s.stale_source
    root = tmp_path / "data"
    (root / "zoom").mkdir(parents=True)
    (root / "zoom" / "meetings.json").write_text(json.dumps({"syncedAt": "2099-10-01T12:00:00+00:00"}), encoding="utf-8")
    (root / "gmail").mkdir()
    (root / "gmail" / "correspondence.json").write_text(json.dumps({"syncedAt": "2099-10-04T11:30:00+00:00"}),
                                                        encoding="utf-8")
    tok = tmp_path / "t.json"
    tok.write_text("{}", encoding="utf-8")
    rows = {r["key"]: r for r in st.source_rows(root, settings=SimpleNamespace(google_oauth_token_file=tok, smud_db=None),
                                                now=NOW)}
    assert rows["zoom"]["standing"] == st.STALE and rows["zoom"]["staleAfter"] == "2d"      # three days old
    assert rows["gmail"]["standing"] == st.CURRENT and rows["gmail"]["staleAfter"] == "1h"  # half an hour old
    assert "Zoom" in rows["zoom"]["staleSource"]


# --- the command -------------------------------------------------------------------------------------------------------

@pytest.fixture
def env(tmp_path, monkeypatch):
    """A made-up .env: a data folder, a vault login, a Google token, and record UIDs shaped like secrets."""
    import os

    for k in [k for k in os.environ if k.lower().endswith("_record_uid")]:
        monkeypatch.delenv(k)
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("JASON_DATA_DIR", str(data))
    (tmp_path / "keeper.json").write_text("{}", encoding="utf-8")
    (tmp_path / "token.json").write_text(json.dumps({"refresh_token": FAKE_REFRESH}), encoding="utf-8")
    (data / "zoom").mkdir()
    (data / "zoom" / "meetings.json").write_text(json.dumps({"syncedAt": "2099-10-03T03:00:00+00:00"}), encoding="utf-8")
    path = tmp_path / ".env"
    path.write_text("\n".join([
        f"PAYHOA_CATALOG={data / 'payhoa.db'}", f"KEEPER_CONFIG_PATH={tmp_path / 'keeper.json'}",
        f"GOOGLE_OAUTH_TOKEN_FILE={tmp_path / 'token.json'}", f"LAWLIBRARY_HOME={tmp_path / 'law'}",
        f"payhoa_record_uid={FAKE_UID}", f"zoom_record_uid={FAKE_UID}", f"google_oauth_record_uid={FAKE_UID}",
        "keeper_password=fake-master-password-do-not-print",
    ]) + "\n", encoding="utf-8")
    return SimpleNamespace(path=path, data=data)


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    from jason.cli import main

    with pytest.raises(SystemExit) as done:
        main(argv)
    out = capsys.readouterr()
    return int(done.value.code or 0), out.out, out.err


def _no_secret(text: str) -> None:
    assert FAKE_UID not in text and FAKE_REFRESH not in text and "fake-master-password" not in text
    assert not checks.SECRET_SHAPED.search(text), checks.SECRET_SHAPED.search(text)


def test_list_shows_states_and_never_a_value(env, capsys):
    code, out, _ = _run(["integrations", "list", "--env", str(env.path)], capsys)
    assert code == 0 and "zoom  Zoom  [connected]" in out and "credential: set" in out
    assert "payhoa  PayHOA  [not set up]" in out and "nothing read yet" in out
    assert "jason/community/mystique/zoom/app" in out and "stale after 2d" in out
    _no_secret(out)
    code, out, _ = _run(["integrations", "list", "--env", str(env.path), "--json"], capsys)
    body = json.loads(out)
    assert {r["key"] for r in body["integrations"]} == {i.key for i in REGISTRY if i.scope is Scope.COMMUNITY}
    zoom = next(r for r in body["integrations"] if r["key"] == "zoom")
    assert zoom["state"] == "connected" and zoom["credentialSet"] is True
    assert zoom["cadences"][0]["lastRead"] == "2099-10-03T03:00:00+00:00"
    _no_secret(out)


def test_list_the_installations(env, capsys):
    code, out, _ = _run(["integrations", "list", "--instance", "--env", str(env.path), "--json"], capsys)
    body = json.loads(out)
    assert code == 0 and body["community"] == "instance"
    assert {r["key"] for r in body["integrations"]} == {i.key for i in REGISTRY if i.scope is Scope.INSTANCE}
    vault = next(r for r in body["integrations"] if r["key"] == "vault")
    assert vault["state"] == "connected"
    _no_secret(out)


def test_another_community_is_read_as_the_active_profile(env, capsys):
    from jason.cli import main

    with pytest.raises(SystemExit) as done:
        main(["integrations", "list", "--community", "elmwood", "--env", str(env.path)])
    assert "JASON_PROFILE=elmwood" in str(done.value.code)


def test_check_from_disk_and_live(env, capsys, monkeypatch):
    from jason.commands import integrations as cmd

    code, out, _ = _run(["integrations", "check", "zoom", "--env", str(env.path)], capsys)
    assert code == 0 and "[connected]" in out and "--live" in out
    _no_secret(out)
    code, _, err = _run(["integrations", "check", "nope", "--env", str(env.path)], capsys)
    assert code == 2 and "known" in err
    code, _, err = _run(["integrations", "check", "postscanmail", "--live", "--env", str(env.path)], capsys)
    assert code == 2 and "no live check" in err

    monkeypatch.setattr(cmd, "at_terminal", lambda: False)
    code, _, err = _run(["integrations", "check", "zoom", "--live", "--env", str(env.path)], capsys)
    assert code == 2 and "terminal" in err

    monkeypatch.setattr(cmd, "at_terminal", lambda: True)
    calls = []
    monkeypatch.setitem(checks.LIVE, "zoom", lambda agent: calls.append(agent) or "listed one meeting")
    code, out, _ = _run(["integrations", "check", "zoom", "--live", "--by", "A. Admin", "--env", str(env.path)], capsys)
    assert code == 0 and "ok: listed one meeting" in out and calls
    stored = cn.load("mystique", env.data / cn.FILE)["zoom"]
    assert stored.state is ConnectionState.CONNECTED and stored.connected_by == "A. Admin"

    def refused(agent):
        raise RuntimeError(f"KeeperAuthRequired: run jason login (token {FAKE_REFRESH}, key {FAKE_UID})")

    monkeypatch.setitem(checks.LIVE, "zoom", refused)
    code, out, _ = _run(["integrations", "check", "zoom", "--live", "--env", str(env.path)], capsys)
    assert code == 1 and "needs sign-in" in out
    _no_secret(out)
    _no_secret(json.dumps(cn.load("mystique", env.data / cn.FILE)["zoom"].to_json()))


def test_every_command_a_setup_step_names_exists_in_the_parser():
    """A setup dialog tells the administrator to run a command; one that the parser lacks sends them nowhere
    (lesson setup-steps-name-commands-that-do-not-exist). `jason integrations` takes list and check only today."""
    from jason.cli import build_parser

    sub = next(a for a in build_parser()._actions if getattr(a, "choices", None) and "responses" in a.choices)
    for integration in REGISTRY:
        for step in integration.setup_steps:
            # a command is "jason NAME" followed by a flag or a placeholder (or a subcommand and one); "jason reads" is prose
            for m in re.finditer(r"jason ([a-z][a-z-]*)(?:(?= -| [A-Z])| ([a-z][a-z-]*)(?= -| [A-Z]))", step.admin_does):
                command, rest = m.group(1), (m.group(2) or "")
                assert command in sub.choices, f"{integration.key}: {step.title}: jason {command} is not a command"
            for sub_name in re.findall(r"jason integrations ([a-z][a-z-]*)", step.admin_does):
                assert sub_name in {"list", "check"}, f"{integration.key}: jason integrations {sub_name} does not exist"
