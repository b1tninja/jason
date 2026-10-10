"""One Keeper session per community per process (jason.vault.pool). A fake login stands in for Keeper: no network."""

from __future__ import annotations

import logging
import threading
import time
from types import SimpleNamespace

import pytest

from jason.config import Settings
from jason.secrets import KeeperAuthRequired, VaultSession
from jason.vault import pool

SECRET = "made-up-master-password"


class FakeVault:
    def __init__(self) -> None:
        self.closed = 0
        self.syncs = 0

    def close(self) -> None:
        self.closed += 1

    def sync_down(self) -> None:
        self.syncs += 1


class Net:
    """Counts the logins the fake Keeper saw."""

    def __init__(self) -> None:
        self.logins = 0
        self.fail = False
        self.vaults: list[FakeVault] = []


@pytest.fixture
def net(monkeypatch):
    n = Net()

    def fake_open(self) -> None:
        if self._vault is not None:
            return
        time.sleep(0.005)   # a login takes time: two threads would both get in without the lock
        n.logins += 1
        if n.fail:
            raise KeeperAuthRequired(f"needs sign-in {SECRET}")
        v = FakeVault()
        n.vaults.append(v)
        self._vault = v
        v.sync_down()

    monkeypatch.setattr(VaultSession, "open", fake_open)
    monkeypatch.setattr(VaultSession, "load_record", lambda self, uid: (self.open(), {"uid": uid})[1])
    return n


@pytest.fixture
def clock(monkeypatch):
    now = SimpleNamespace(t=1000.0)
    monkeypatch.setattr(pool, "_clock", lambda: now.t)
    return now


@pytest.fixture
def settings():
    return Settings.load(None) if False else SimpleNamespace(
        keeper_username="u", keeper_password=SECRET, keeper_config="x.json")


def test_two_threads_ten_calls_one_login(net, settings):
    def use():
        for _ in range(5):
            pool.session_for(settings).load_record("UID")

    threads = [threading.Thread(target=use) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert net.logins == 1
    assert pool.stats()["logins"] == 1 and pool.stats()["reuses"] == 9


def test_session_is_lazy(net, settings):
    pool.session_for(settings)
    assert net.logins == 0


def test_idle_timeout_reopens(net, settings, clock, monkeypatch):
    monkeypatch.setenv("JASON_KEEPER_IDLE_SECONDS", "60")
    s = pool.session_for(settings)
    s.load_record("A")
    clock.t += 30
    s.load_record("A")
    assert net.logins == 1
    clock.t += 61
    s.load_record("A")
    assert net.logins == 2 and net.vaults[0].closed == 1
    assert pool.stats()["closes"] == 1


def test_idle_zero_never_closes(net, settings, clock, monkeypatch):
    monkeypatch.setenv("JASON_KEEPER_IDLE_SECONDS", "0")
    s = pool.session_for(settings)
    s.load_record("A")
    clock.t += 10 ** 6
    s.load_record("A")
    assert net.logins == 1


def test_failed_login_is_not_cached_and_is_rate_limited(net, settings, clock, caplog):
    net.fail = True
    s = pool.session_for(settings)
    with pytest.raises(KeeperAuthRequired):
        s.load_record("A")
    assert s._vault is None
    clock.t += 5
    with pytest.raises(KeeperAuthRequired):     # inside the cooldown: no call to Keeper
        s.load_record("A")
    assert net.logins == 1
    net.fail = False
    clock.t += pool.FAILURE_COOLDOWN
    s.load_record("A")                           # tried again, and the error was not kept
    assert net.logins == 2
    assert pool.stats()["failures"] == 1


def test_interactive_retry_is_not_held_back(net, settings, clock):
    net.fail = True
    s = pool.session_for(settings, interactive=True)
    for _ in range(2):
        with pytest.raises(KeeperAuthRequired):
            s.load_record("A")
    assert net.logins == 2


def test_interactive_and_not_are_two_sessions(net, settings):
    assert pool.session_for(settings) is not pool.session_for(settings, interactive=True)


def test_community_guard(net, settings):
    from jason.community.profile import profile_name

    active = profile_name()
    assert pool.session_for(settings, community=active).community == active
    with pytest.raises(pool.CommunityMismatch):
        pool.session_for(settings, community="someone-else")


def test_two_communities_two_sessions(net, settings, monkeypatch):
    monkeypatch.setattr(pool, "_active_community", lambda: "one")
    a = pool.session_for(settings)
    monkeypatch.setattr(pool, "_active_community", lambda: "two")
    b = pool.session_for(settings)
    assert a is not b and (a.community, b.community) == ("one", "two")


def test_with_block_leaves_session_open(net, settings):
    with pool.session_for(settings) as s:
        s.load_record("A")
    with pool.session_for(settings) as s2:
        s2.load_record("A")
    assert s is s2 and net.logins == 1 and net.vaults[0].closed == 0
    s.close()
    assert net.vaults[0].closed == 0


def test_close_all_closes_once(net, settings):
    s = pool.session_for(settings)
    s.load_record("A")
    pool.close_all()
    pool.close_all()
    assert net.vaults[0].closed == 1 and pool.stats()["closes"] == 1
    assert pool.session_for(settings) is not s


def test_refresh_syncs_at_most_once_per_interval(net, settings, clock):
    s = pool.session_for(settings)
    s.refresh(60)
    assert net.vaults[0].syncs == 1          # the login's own sync
    clock.t += 10
    s.refresh(60)
    assert net.vaults[0].syncs == 1
    clock.t += 60
    s.refresh(60)
    assert net.vaults[0].syncs == 2 and net.logins == 1


def test_stats_and_logs_hold_no_secret(net, settings, caplog, clock):
    caplog.set_level(logging.DEBUG)
    net.fail = True
    s = pool.session_for(settings)
    with pytest.raises(KeeperAuthRequired):
        s.load_record("A")
    net.fail = False
    clock.t += 31
    pool.session_for(settings).load_record("A")
    pool.close_all()
    assert set(pool.stats()) == {"logins", "reuses", "closes", "failures"}
    assert all(isinstance(v, int) for v in pool.stats().values())
    assert SECRET not in caplog.text and SECRET not in pool.stats_line() and "UID" not in caplog.text
    assert pool.stats_line() == "Keeper sessions this process: 1 logins, 1 reuses"


def test_simulated_web_session_and_daemon_loop(net, settings, clock):
    """20 web requests, then a 5-minute daemon loop ticking every 10 seconds: one login each, and one in all."""
    for _ in range(20):
        with pool.session_for(settings) as s:
            s.load_record("A")
    assert net.logins == 1
    for _ in range(30):
        clock.t += 10
        pool.session_for(settings).load_record("A")
    assert net.logins == 1
