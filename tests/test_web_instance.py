"""The administrator's Instance loaders (``jason.web.extra.instance``: ``/api/instance-service``,
``/api/instance-integrations``, ``/api/instance-schedules``): one of jason's admins only, never the owner view; the
service read from heartbeats (made-up, in tmp_path), the integrations without a credential value, and the schedules
read without creating a store or seeding one. Nothing reaches Google, PayHOA, Keeper, or the network.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import webclient

from jason import scheduler as sc
from jason import serve
from jason.web.extra import instance as inst

ROUTES = {"instance-service": inst.service, "instance-integrations": inst.integrations,
          "instance-schedules": inst.schedules}


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "alpha"
    r.mkdir()
    return r


@pytest.fixture
def app(tmp_path, monkeypatch, root):
    from jason.web.app import create_app

    monkeypatch.setattr(inst, "_profiles", lambda: {"alpha": root})
    monkeypatch.setattr("jason.config.data_dir", lambda env_file=None: root)
    monkeypatch.setattr("jason.integrations.connections.store_path", lambda community, env_file=None: root / "integrations.json")
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, ROUTES, approvals_live=None, extra_writes=False, sign_in=webclient.roster_sign_in(dev=True))


def _admin(app):
    return webclient.sign_in(webclient.client(app), "Ada Admin")


# --- the service -------------------------------------------------------------------------------------------------------

def test_a_community_that_never_served_has_no_heartbeat(app):
    out = _admin(app).get("/api/instance-service").json
    assert out["found"] is False and out["command"] == "jason serve"
    assert [c["state"] for c in out["communities"]] == ["none"]


def test_a_fresh_heartbeat_is_running_and_an_old_one_is_stale(app, root):
    now = datetime.now(timezone.utc)
    serve.write_heartbeat(root, {"profile": "alpha", "state": "running", "pid": 1, "host": "h",
                                 "beat": now.isoformat(timespec="seconds")})
    out = _admin(app).get("/api/instance-service").json
    assert out["found"] is True and out["staleAfterSeconds"] == serve.STALE_AFTER
    assert out["communities"][0]["state"] == "running" and out["communities"][0]["alive"] is True
    old = now - timedelta(seconds=serve.STALE_AFTER + 60)
    serve.write_heartbeat(root, {"profile": "alpha", "state": "running", "pid": 1, "host": "h",
                                 "beat": old.isoformat(timespec="seconds")})
    row = _admin(app).get("/api/instance-service").json["communities"][0]
    assert row["state"] == "stale" and row["said"] == "running" and row["alive"] is False


# --- the integrations --------------------------------------------------------------------------------------------------

def test_the_integrations_carry_names_and_states_and_never_a_value(app):
    out = _admin(app).get("/api/instance-integrations").json
    assert out["found"] is True and out["scope"] == "community" and out["integrations"]
    states = {"not set up", "needs sign-in", "connected", "failing", "paused"}
    assert {r["state"] for r in out["integrations"]} <= states
    assert all(isinstance(r["credentialSet"], (bool, type(None))) for r in out["integrations"])
    assert out["vault"]["asked"] is False and "vault was not asked" in out["vault"]["why"]


def test_the_installation_scope_lists_the_instance_integrations(app):
    out = _admin(app).get("/api/instance-integrations?scope=instance").json
    assert out["scope"] == "instance" and out["community"] == "instance"


def test_the_vault_is_asked_only_on_request(app, monkeypatch):
    from jason.vault.resolver import VaultNames

    calls = []
    monkeypatch.setattr("jason.vault.keeper.vault_names", lambda settings: calls.append(1) or VaultNames(None, "timeout"))
    _admin(app).get("/api/instance-integrations")
    assert calls == []
    out = _admin(app).get("/api/instance-integrations?vault=1").json
    assert calls == [1] and out["vault"] == {"asked": True, "answered": False, "why": "timeout"}


# --- the schedules -----------------------------------------------------------------------------------------------------

def test_schedules_never_seeded_are_said_so_and_no_store_is_created(app, root):
    out = _admin(app).get("/api/instance-schedules").json
    assert out["found"] is False
    assert out["communities"][0]["seeded"] is False and out["communities"][0]["command"] == "jason cadence"
    assert not (root / "jobs.db").exists()


def test_seeded_schedules_are_listed_with_their_floor_and_adoption(app, root):
    sc.seed(root)
    out = _admin(app).get("/api/instance-schedules").json
    comm = out["communities"][0]
    assert out["found"] is True and comm["seeded"] is True and comm["schedules"]
    one = comm["schedules"][0]
    assert {"source", "cadence", "floor", "adopted", "setting", "nextRun"} <= set(one)
    assert all(s["adopted"] is False for s in comm["schedules"])


# --- who may ask -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("key", sorted(ROUTES))
def test_each_route_needs_a_sign_in_and_an_admin(app, key):
    assert webclient.client(app).get(f"/api/{key}").status_code == 401
    for name in ("Lee President", "A Manager"):
        r = webclient.sign_in(webclient.client(app), name).get(f"/api/{key}")
        assert r.status_code == 403
    c = _admin(app)
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert c.get(f"/api/{key}").status_code == 403
    assert _admin(app).get(f"/api/{key}?view=owner").status_code == 403


def test_they_are_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    for key in ROUTES:
        assert key not in OWNER_SOURCES and key not in EXTRA_WRITERS
        assert EXTRA_LOADERS[key] == f"jason.web.extra.instance:{key.split('-')[1]}"
