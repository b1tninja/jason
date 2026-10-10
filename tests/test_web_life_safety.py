"""The Life safety loader (``jason.web.extra.life_safety``): the systems the profile lists with a standing in words, counts
made here (a part not composed is null, never zero), a part that cannot be read named rather than failing the screen, and
the route open to a signed-in roster person only. Made-up systems, rows, and tmp data; nothing is reached.
"""

from __future__ import annotations

from datetime import date

import pytest
import webclient
from test_inspections import ALARM, ALARM_TEST, ANNUAL, RISERS, _Profile

from jason.web.extra import life_safety as ls

DAY = date(2026, 10, 4)


class Profile(_Profile):
    def vendor_portals(self):
        return ()

    def backflow_program(self):
        return None

    def life_safety_watch(self):
        return ()


def _read(tmp_path, *systems_rows, system="", private=False):
    systems, rows = systems_rows
    return ls.compose(tmp_path, Profile(systems, rows), today=DAY, system=system, private=private)


def test_each_listed_system_is_a_card_with_a_standing_in_words(tmp_path):
    out = _read(tmp_path, (RISERS, ALARM), (ALARM_TEST, ANNUAL))
    assert out["found"] is True and [c["key"] for c in out["systems"]] == ["risers", "alarm"]
    assert {o["obligation"] for c in out["systems"] for o in c["obligations"]} >= {"Alarm test", "Sprinkler annual inspection"}
    allowed = set(ls.STANDING_WORDS.values()) | {ls.NONE_ON_RECORD}
    assert all(o["standing"] in allowed for c in out["systems"] for o in c["obligations"])
    assert all(c["standing"] in allowed for c in out["systems"])


def test_counts_are_made_here_and_the_impairment_counts_are_null_without_the_detail(tmp_path):
    out = _read(tmp_path, (RISERS, ALARM), (ALARM_TEST, ANNUAL))
    summary = out["summary"]
    assert summary["systems"] == 2 and summary["obligations"] == sum(len(c["obligations"]) for c in out["systems"])
    assert summary["openDeficiencies"] == 0 and summary["proposedDeficiencies"] == 0
    assert summary["impairments"] is None and summary["insurerNotTold"] is None       # the detail is P2
    assert out["deficiencies"]["found"] is True and out["deficiencies"]["rows"] == [] and out["banner"] is None
    assert {p["part"] for p in out["notComposed"]} == {"insurer", "vendors", "boardItems"}


def test_a_recorded_impairment_with_no_insurer_notice_raises_the_banner_only_for_a_viewer_who_may_see_it(tmp_path, monkeypatch):
    from jason.tasks import deficiencies as register

    row = {"id": "def-1", "system": "alarm", "buildings": ["A"], "report": {"id": "drive-1", "day": "2026-03-10"},
           "location": "", "device": "Waterflow switch", "comment": "failed", "source": "x",
           "acts": [{"act": "proposed", "at": "t"}, {"act": "confirmed", "by": "P", "at": "t"},
                    {"act": "impairs", "by": "P", "at": "t"}]}
    (tmp_path / "life-safety").mkdir()
    (tmp_path / "life-safety" / "deficiencies.json").write_text(__import__("json").dumps({"deficiencies": [row]}), encoding="utf-8")
    seen = _read(tmp_path, (ALARM,), (ALARM_TEST,), private=True)
    assert seen["summary"]["impairments"] == 1 and seen["summary"]["insurerNotTold"] == 1
    assert seen["banner"]["ids"] == ["def-1"] and "no record shows the insurer was told" in seen["banner"]["sentence"]
    held = _read(tmp_path, (ALARM,), (ALARM_TEST,))
    assert held["banner"] is None and held["summary"]["openDeficiencies"] == 1 and held["deficiencies"]["rows"] == []
    assert register.view(tmp_path)["counts"]["impairments"] == 1


def test_no_listed_system_says_so_and_names_the_method(tmp_path):
    out = _read(tmp_path, (), ())
    assert out["systems"] == [] and "Community.life_safety_systems()" in out["empty"]


def test_one_system_by_key_and_an_unknown_key_is_a_miss_that_lists_the_keys(tmp_path):
    out = _read(tmp_path, (RISERS, ALARM), (ALARM_TEST, ANNUAL), system="alarm")
    assert [c["key"] for c in out["systems"]] == ["alarm"]
    miss = _read(tmp_path, (RISERS, ALARM), (ALARM_TEST, ANNUAL), system="nope")
    assert miss["found"] is False and "risers, alarm" in miss["note"]


def test_a_part_that_cannot_be_read_is_named_and_the_rest_stands(tmp_path, monkeypatch):
    import sys
    import types

    broken = types.ModuleType("jason.tasks.backflow")

    def boom(*a, **k):
        raise RuntimeError("store unreadable")

    broken.view = broken.watchlist = boom
    monkeypatch.setitem(sys.modules, "jason.tasks.backflow", broken)
    monkeypatch.setattr("jason.tasks.backflow", broken, raising=False)
    out = _read(tmp_path, (RISERS,), (ANNUAL,))
    assert out["backflow"] == {"found": False, "note": "not read: RuntimeError"} and out["systems"]


def test_a_profile_without_an_obligation_row_is_none_on_record(tmp_path):
    out = _read(tmp_path, (RISERS,), ())
    assert out["systems"][0]["standing"] == ls.NONE_ON_RECORD


@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    monkeypatch.setattr("jason.community.community", lambda: Profile((RISERS,), (ANNUAL,)))
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {"life-safety": ls.life_safety}, approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(dev=True))


def test_the_route_needs_a_sign_in_and_is_no_owner_source(app):
    assert webclient.client(app).get("/api/life-safety").status_code == 401
    assert webclient.sign_in(webclient.client(app), "Pat Example").get("/api/life-safety?view=owner").status_code == 403
    out = webclient.sign_in(webclient.client(app), "Pat Example").get("/api/life-safety").json
    assert out["found"] is True and out["systems"][0]["key"] == "risers"


def test_it_is_registered_and_no_owner_source():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS

    assert "life-safety" not in OWNER_SOURCES
    assert EXTRA_LOADERS["life-safety"] == "jason.web.extra.life_safety:life_safety"


# --- the register's writer --------------------------------------------------------------------------------------------

@pytest.fixture
def wapp(tmp_path, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    monkeypatch.setattr("jason.community.community", lambda: Profile((RISERS, ALARM), ()))
    monkeypatch.setattr("jason.tasks.deficiencies._library", lambda d: (
        {"id": "drive-1", "name": "r.pdf", "kind": "inspection_report", "model": "m", "hasText": True, "confidential": False,
         "fields": {"inspection_date": "2026-03-10", "system": "fire alarm", "building": "A", "result": "failed",
                    "deficiencies": [{"location": "Riser", "device": "Switch", "comment": "failed", "status": "Open"}]}},))
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {}, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(dev=True))


def test_the_register_is_written_in_the_signers_name_and_a_body_by_is_not_trusted(wapp, tmp_path):
    c = webclient.sign_in(webclient.client(wapp), "Pat Example")
    added = c.post("/api/write/life-safety/propose", json={"act": "propose"}).json
    assert added["added"] == 1
    ident = added["ids"][0]
    assert c.post(f"/api/write/life-safety/{ident}", json={"act": "confirm", "by": "Somebody Else"}).status_code == 403
    resp = c.post(f"/api/write/life-safety/{ident}", json={"act": "confirm"})
    assert resp.status_code == 200, resp.json
    row = resp.json
    assert row["standing"] == "open" and row["confirmed"]["by"] == "Pat Example"
    assert c.post(f"/api/write/life-safety/{ident}", json={"act": "impairs", "value": "yes"}).status_code == 400
    assert c.post(f"/api/write/life-safety/{ident}", json={"act": "impairs", "value": True}).json["impairmentOpen"] is True
    assert c.post(f"/api/write/life-safety/{ident}", json={"act": "nope"}).status_code == 400


def test_nobody_without_an_office_and_no_admin_viewing_as_someone_writes(wapp):
    assert webclient.client(wapp).post("/api/write/life-safety/propose", json={"act": "propose"}).status_code == 401
    assert webclient.sign_in(webclient.client(wapp), "Ada Admin").post(
        "/api/write/life-safety/propose", json={"act": "propose"}).status_code == 403
    c = webclient.sign_in(webclient.client(wapp), "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert c.post("/api/write/life-safety/propose", json={"act": "propose"}).status_code in (403, 405)


def test_the_writer_is_registered():
    from jason.web.sources import EXTRA_WRITERS

    assert EXTRA_WRITERS["life-safety"] == "jason.web.extra.life_safety:write"
