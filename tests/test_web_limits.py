"""The Limits screens' sources and write (``jason.web.extra.limits_view``: ``GET /api/limits``, ``GET /api/instance-limits``,
``POST /api/write/limits/<scope>``): who may read and who may change, the dry run first, the signed-in person and role in the trail,
refusals in words with the nearest allowed value, and two communities in one process. Made-up roster, tmp data folders, nothing
reaching a network."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import webclient

from jason import limits
from jason.web.extra import limits_view as lv

MB = 1024 * 1024
KEY = "upload.max_bytes"
ALPHA, BETA = SimpleNamespace(slug="alpha", limits=dict), SimpleNamespace(slug="beta", limits=dict)
ROWS = webclient.ROSTER + (("Oscar Owner", "", "oscar@example.org", False),)


@pytest.fixture
def world(tmp_path, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JASON_LIMITS_FILE", str(tmp_path / "home" / "limits.json"))
    for l in limits.all_limits():
        monkeypatch.delenv(l.env_name, raising=False)
    state = SimpleNamespace(current=ALPHA)
    monkeypatch.setattr(lv, "_community", lambda: state.current)
    monkeypatch.setattr(lv, "_data_root", lambda: tmp_path / "data")
    dist = tmp_path / "dist"
    dist.mkdir()
    app = create_app(dist, {"limits": lv.limits, "instance-limits": lv.instance_limits}, approvals_live=None, extra_writes=True,
                     sign_in=webclient.roster_sign_in(ROWS, dev=True))
    return SimpleNamespace(app=app, state=state, tmp=tmp_path)


def as_(world, name):
    return webclient.sign_in(webclient.client(world.app), name, rows=ROWS)


def put(c, scope, **body):
    return c.post(f"/api/write/limits/{scope}", json=body)


def community_trail(slug):
    return limits.read_log("community", community=SimpleNamespace(slug=slug, limits=dict))


# --- reading -----------------------------------------------------------------------------------------------------------------

def test_the_community_screen_is_read_by_officers_managers_and_administrators_and_not_by_an_owner(world):
    assert webclient.client(world.app).get("/api/limits").status_code == 401
    for name in ("Lee President", "A Manager", "Ada Admin", "Tess Two"):
        out = as_(world, name).get("/api/limits").json
        assert out["found"] and out["scope"] == "community" and out["community"] == "alpha"
    assert as_(world, "Oscar Owner").get("/api/limits").status_code == 403
    assert as_(world, "Ada Admin").get("/api/limits?view=owner").status_code == 403


def test_a_row_carries_value_source_range_ceiling_last_change_why_and_when_hit(world):
    limits.set_limits({KEY: "50MB"}, scope="community", reason="The disk is small", by="Ada Admin", dry_run=False, community=ALPHA)
    out = as_(world, "Lee President").get("/api/limits").json
    row = next(r for r in out["limits"] if r["key"] == KEY)
    assert (row["value"], row["words"], row["source"], row["sourceWords"]) == (50 * MB, "50 MB", "community", "this community")
    assert row["minimum"] == 1 * MB and row["maximum"] == 500 * MB and row["ceiling"] == 500 * MB and row["default"] == 100 * MB
    assert "built in 100 MB" in row["rangeWords"] and row["clamped"] is False
    assert row["lastChange"]["by"] == "Ada Admin" and row["lastChange"]["reason"] == "The disk is small"
    assert row["why"] and row["whenHit"] and row["override"] is True and row["overrideMaxWords"] == "250 MB"
    assert {g["kind"] for g in out["groups"]} == {"size", "switch"}
    # read-only for an officer, with the reason in words
    assert out["canChange"] is False and row["editable"] is False and "administrator" in row["readOnlyWhy"]
    assert as_(world, "Ada Admin").get("/api/limits").json["canChange"] is True


def test_a_stored_value_held_to_the_operators_ceiling_is_shown_as_clamped(world):
    folder = world.tmp / "data" / "alpha"
    folder.mkdir(parents=True)
    (folder / "limits.json").write_text(json.dumps({"version": 1, "limits": {KEY: {"value": 400 * MB}}}), encoding="utf-8")
    limits.set_limits({KEY: "200MB"}, scope="instance", reason="Small host", by="Op", dry_run=False, role=limits.ROLE_INSTANCE)
    row = next(r for r in as_(world, "Ada Admin").get("/api/limits").json["limits"] if r["key"] == KEY)
    assert row["clamped"] is True and row["value"] == 200 * MB and "operator's limit is 200 MB" in row["note"]


def test_the_instance_screen_is_one_admin_as_themselves_and_never_the_owner_view(world):
    assert webclient.client(world.app).get("/api/instance-limits").status_code == 401
    for name in ("Lee President", "A Manager", "Oscar Owner"):
        assert as_(world, name).get("/api/instance-limits").status_code == 403
    c = as_(world, "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert c.get("/api/instance-limits").status_code == 403
    assert as_(world, "Ada Admin").get("/api/instance-limits?view=owner").status_code == 403
    out = as_(world, "Ada Admin").get("/api/instance-limits").json
    assert out["scope"] == "instance" and {r["key"] for r in out["limits"]} == {l.key for l in limits.all_limits()}
    row = next(r for r in out["limits"] if r["key"] == KEY)
    assert row["value"] is None and row["topWords"] == "500 MB" and row["editable"] is True and row["why"] and row["whenHit"]


def test_they_are_registered_and_the_screens_are_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    assert EXTRA_LOADERS["limits"] == "jason.web.extra.limits_view:limits"
    assert EXTRA_LOADERS["instance-limits"] == "jason.web.extra.limits_view:instance_limits"
    assert EXTRA_WRITERS["limits"] == "jason.web.extra.limits_view:write"
    assert "limits" not in OWNER_SOURCES and "instance-limits" not in OWNER_SOURCES


# --- writing: roles -----------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("scope", ["community", "instance"])
def test_only_a_signed_in_administrator_changes_a_limit(world, scope):
    body = dict(act="set", changes={KEY: "50MB"}, reason="Because", dryRun=False)
    assert put(webclient.client(world.app), scope, **body).status_code == 401
    for name in ("Lee President", "A Manager", "Tess Two", "Oscar Owner"):
        assert put(as_(world, name), scope, **body).status_code == 403
    c = as_(world, "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert put(c, scope, **body).status_code == 403
    assert limits.value(KEY, community=ALPHA) == 100 * MB and community_trail("alpha") == []
    assert limits.read_log("instance") == []


def test_a_dry_run_is_the_default_and_writes_nothing(world):
    c = as_(world, "Ada Admin")
    out = put(c, "community", act="set", changes={KEY: "50MB"}, reason="The disk is small").json
    assert out["ok"] and out["dryRun"] is True and out["recordedAs"] == {"by": "Ada Admin", "role": "community administrator"}
    assert "50 MB" in out["changes"][0]["words"] and "never removes or hides" in out["changes"][0]["words"]
    assert "A dry run" in out["note"] and "path" not in out and "log" not in out
    assert limits.value(KEY, community=ALPHA) == 100 * MB and community_trail("alpha") == []
    assert not (world.tmp / "data" / "alpha" / "limits.json").exists()


def test_confirming_writes_the_value_and_a_trail_line_with_the_person_role_and_subject(world):
    c = as_(world, "Ada Admin")
    out = put(c, "community", act="set", changes={KEY: "50MB"}, reason="The disk is small", dryRun=False).json
    assert out["ok"] and out["dryRun"] is False and out["changes"][0]["now"] == 50 * MB
    assert limits.value(KEY, community=ALPHA) == 50 * MB
    (line,) = community_trail("alpha")
    assert (line["kind"], line["by"], line["role"], line["via"], line["reason"]) == ("set", "Ada Admin", "community administrator",
                                                                                       "console:google", "The disk is small")
    assert line["who"] == "sub-ada-admin"
    back = put(c, "community", act="reset", keys=[KEY], reason="Back to normal", dryRun=False).json
    assert back["changes"][0]["to"] is None and limits.value(KEY, community=ALPHA) == 100 * MB
    assert community_trail("alpha")[-1]["kind"] == "reset"


def test_the_instance_operator_changes_the_instance_layer_and_a_community_cannot_pass_its_ceiling(world):
    c = as_(world, "Ada Admin")
    out = put(c, "instance", act="set", changes={KEY: "50MB"}, ceiling="200MB", reason="Small host", dryRun=False).json
    assert out["recordedAs"]["role"] == "instance operator"
    assert limits.read_log("instance")[-1]["role"] == "instance operator"
    res = put(c, "community", act="set", changes={KEY: "300MB"}, reason="More room", dryRun=False)
    assert res.status_code == 400
    assert "above the operator's limit of 200 MB" in res.json["error"] and "nearest allowed value is 200 MB" in res.json["error"]
    assert "Nothing was changed" in res.json["error"]
    assert limits.value(KEY, community=ALPHA) == 50 * MB            # unchanged: the instance value, not 300 MB
    assert put(c, "community", act="set", changes={KEY: "150MB"}, reason="More room", dryRun=False).status_code == 200
    assert limits.value(KEY, community=ALPHA) == 150 * MB


def test_refusals_are_in_words_with_the_nearest_allowed_value_and_a_reason_is_required(world):
    c = as_(world, "Ada Admin")
    r = put(c, "community", act="set", changes={KEY: "9GB"}, reason="x", dryRun=False)
    assert r.status_code == 400 and "above 500 MB" in r.json["error"] and "nearest allowed value is 500 MB" in r.json["error"]
    r = put(c, "community", act="set", changes={KEY: "unlimited"}, reason="x")
    assert r.status_code == 400 and "no unlimited" in r.json["error"]
    r = put(c, "community", act="set", changes={KEY: "50MB"}, reason=" ")
    assert r.status_code == 400 and "reason is required" in r.json["error"]
    r = put(c, "community", act="set", changes={"nope.key": "1"}, reason="x")
    assert r.status_code == 400 and "no limit" in r.json["error"]
    assert put(c, "nowhere", act="set", changes={KEY: "50MB"}, reason="x").status_code == 404
    assert put(c, "community", act="delete", reason="x").status_code == 400
    # the applied refusal left a "refused" line and nothing else
    assert {r["kind"] for r in community_trail("alpha")} == {"refused"}
    assert limits.value(KEY, community=ALPHA) == 100 * MB


def test_a_different_name_in_by_is_refused_the_signed_in_name_is_recorded(world):
    c = as_(world, "Ada Admin")
    r = put(c, "community", act="set", changes={KEY: "50MB"}, reason="x", by="Lee President", dryRun=False)
    assert r.status_code == 403 and "signed in as Ada Admin" in r.json["error"]
    assert limits.value(KEY, community=ALPHA) == 100 * MB


# --- two communities in one process ---------------------------------------------------------------------------------------------

def test_two_communities_read_and_write_their_own_and_a_reason_never_crosses(world):
    c = as_(world, "Ada Admin")
    put(c, "community", act="set", changes={KEY: "30MB"}, reason="SENT-alpha reason", dryRun=False)
    world.state.current = BETA
    put(c, "community", act="set", changes={KEY: "60MB"}, reason="SENT-beta reason", dryRun=False)
    beta_files = {p.name: p.read_bytes() for p in (world.tmp / "data" / "beta").iterdir()}
    for who, expect in ((ALPHA, 30 * MB), (BETA, 60 * MB), (ALPHA, 30 * MB)):
        world.state.current = who
        out = as_(world, "Lee President").get("/api/limits").json
        row = next(r for r in out["limits"] if r["key"] == KEY)
        assert out["community"] == who.slug and row["value"] == expect and f"SENT-{who.slug}" in row["lastChange"]["reason"]
        other = "beta" if who is ALPHA else "alpha"
        assert f"SENT-{other}" not in json.dumps(out)
    world.state.current = ALPHA
    put(c, "community", act="set", changes={KEY: "40MB"}, reason="SENT-alpha again", dryRun=False)
    assert {p.name: p.read_bytes() for p in (world.tmp / "data" / "beta").iterdir()} == beta_files       # byte-identical
    instance = as_(world, "Ada Admin").get("/api/instance-limits").text
    assert "SENT-alpha" not in instance and "SENT-beta" not in instance


def test_the_operators_ceiling_binds_both_communities_and_each_reads_its_own_value(world):
    c = as_(world, "Ada Admin")
    put(c, "community", act="set", changes={KEY: "150MB"}, reason="alpha", dryRun=False)
    world.state.current = BETA
    put(c, "community", act="set", changes={KEY: "250MB"}, reason="beta", dryRun=False)
    put(c, "instance", act="set", changes={KEY: "100MB"}, ceiling="200MB", reason="Small host", dryRun=False)
    out = {}
    for who in (ALPHA, BETA):
        world.state.current = who
        out[who.slug] = next(r for r in as_(world, "Lee President").get("/api/limits").json["limits"] if r["key"] == KEY)
    assert out["alpha"]["value"] == 150 * MB and out["alpha"]["clamped"] is False
    assert out["beta"]["value"] == 200 * MB and out["beta"]["clamped"] is True
