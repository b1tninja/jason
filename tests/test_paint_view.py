"""The paint screen's loader and the paint tools: the schedule against a made-up catalog copy, with no network."""

import json
import socket
from datetime import datetime, timezone

import httpx
import pytest

from jason import api
from jason.community.paint import Maker, PaintRow, PaintSchedule, PaintSpec, Surface
from jason.mcp import paint as tools
from jason.mcp.server import tools_for
from jason.tasks import paint_view as pv


def _raw(number, name, hex_, lab, **extra):
    return {
        "colorNumber": number, "name": name, "hex": hex_, "red": 1, "green": 2, "blue": 3, "lrv": 50.0,
        "colorFamilyNames": ["Neutral"], "brandedCollectionNames": [], "isExterior": True, "isInterior": True,
        "archived": False, "ignore": False, "storeStripLocator": "1-C1", "lab": dict(zip("LAB", lab)), **extra,
    }


CATALOG = [
    _raw("1001", "New Name", "#aabbcc", (50, 0, 0), id="a", coordinatingColors={"whiteColorId": "w", "coord1ColorId": "b"},
         similarColors=["b"]),
    _raw("1002", "Near Name", "#aabbcd", (51, 0, 0), id="b"),
    _raw("1003", "Gone Name", "#000000", (10, 0, 0), id="g", archived=True),
    _raw("1004", "Agreeable Gray", "#d1cbc1", (80, 1, 5), id="c"),
    _raw("1005", "Close To Gone", "#010101", (11, 0, 0), id="d"),
    _raw("1006", "White", "#ffffff", (99, 0, 0), id="w"),
]

SCHEDULE = PaintSchedule(
    title="Palette", source="Drive 1890We-MR0jTDX1e2PVf2LwgG7tmQpdGO (Plans/Paint Schedule.png)", prepared="someone, 2017",
    schemes=(1, 2),
    rows=(
        PaintRow(Surface.FIELD, "FIELD", (
            PaintSpec(1, "SW 1004", "Agreeable Grey"),
            PaintSpec(2, "SW 1001", "Old Name"),
        )),
        PaintRow(Surface.TRIM, "TRIM", (PaintSpec(1, "SW 1003", "Gone Name"),)),
        PaintRow(Surface.FASCIA, "FASCIA", (PaintSpec(1, "SW 9999", "Nowhere"),)),
        PaintRow(Surface.ROOF, "ROOF", (PaintSpec(1, "1FACS 0024", "Sage", Maker.OTHER),)),
    ),
)


class Stub:
    def __init__(self, *schedules):
        self._s = schedules

    def paint_schedules(self):
        return self._s


def _brief(year, data_dir=None, found=True):
    if not found:
        return {"found": False, "note": "no reserve study"}
    items = {2027: [{"category": "Painting", "description": "Exterior paint", "costCents": 12345600},
                    {"category": "Roofs", "description": "Roof", "costCents": 1}]}
    return {"found": True, "study": {"preparer": "X"}, "plannedExpenditures": items.get(year, [])}


@pytest.fixture
def offline(monkeypatch):
    """Any socket or HTTP use fails the test."""
    def refuse(*a, **kw):
        raise AssertionError("the paint loaders made a network call")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)


@pytest.fixture
def data(tmp_path):
    folder = tmp_path / "paint"
    folder.mkdir()
    # an old copy: the screen reads it whatever its age and never fetches
    (folder / "sherwin-williams-colors.json").write_text(
        json.dumps({"fetched": datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat(), "colors": CATALOG}), encoding="utf-8")
    return tmp_path


def _colors(out):
    return {(r["label"], c["scheme"]): c for s in out["schedules"] for r in s["rows"] for c in r["colors"]}


def test_view_reads_the_copy_on_disk_with_statuses(data, offline):
    out = pv.view(data, Stub(SCHEDULE), study=_brief)
    assert out["found"] and out["catalog"]["available"] and out["catalogFetched"].startswith("2020-01-01")
    c = _colors(out)
    assert c["FIELD", 1]["status"] == "ok" and c["FIELD", 1]["printedName"] == "Agreeable Grey" and c["FIELD", 1]["name"] == "Agreeable Gray"
    assert c["FIELD", 2]["status"] == "renamed" and c["FIELD", 2]["name"] == "New Name" and c["FIELD", 2]["hex"] == "#AABBCC"
    assert c["TRIM", 1]["status"] == "archived"
    assert c["FASCIA", 1]["status"] == "not found" and "hex" not in c["FASCIA", 1]
    assert c["ROOF", 1]["status"] == "not checked" and c["ROOF", 1]["maker"] == "other"
    s = out["schedules"][0]
    assert s["sourceAddress"] == "drive:1890We-MR0jTDX1e2PVf2LwgG7tmQpdGO" and s["schemes"] == [1, 2] and s["needsAPerson"] == 3
    assert any("number on the schedule governs" in x for x in out["caveats"])


def test_missing_catalog_checks_nothing_and_names_the_command(tmp_path, offline):
    out = pv.view(tmp_path, Stub(SCHEDULE), study=_brief)
    assert out["catalog"]["available"] is False and out["catalog"]["command"] == "jason paint --refresh"
    assert out["catalogFetched"] is None and out["note"]
    assert {c["status"] for c in _colors(out).values()} == {"not checked"}
    assert any(u["part"] == "catalog" for u in out["unavailable"])
    assert not (tmp_path / "paint").exists()            # nothing was fetched or written


def test_no_schedule_is_found_false(data):
    out = pv.view(data, Stub())
    assert out["found"] is False and out["note"]


def test_reserve_dates_are_labeled_and_last_painted_is_never_invented(data, offline):
    reserve = pv.view(data, Stub(SCHEDULE), study=_brief)["reserve"]
    assert reserve["next"] == [{"year": 2027, "description": "Exterior paint", "category": "Painting", "costCents": 12345600,
                                "source": "reserve study"}]
    assert reserve["lastPainted"] == {"source": "needs input"} and "useful life" in reserve["note"]


def test_a_failed_reserve_read_keeps_the_schedule(data, offline):
    def boom(year, data_dir):
        raise RuntimeError("no pdf")

    out = pv.view(data, Stub(SCHEDULE), study=boom)
    assert out["found"] and out["schedules"] and out["reserve"]["next"] == []
    assert "no pdf" in out["reserve"]["reserveNote"] and any(u["part"] == "reserve" for u in out["unavailable"])
    out = pv.view(data, Stub(SCHEDULE), study=lambda year, data_dir: _brief(year, found=False))
    assert out["reserve"]["reserveNote"] == "no reserve study"


def test_color_detail_has_related_colors_offline_and_nearest_for_a_discontinued_one(data, offline):
    stub = Stub(SCHEDULE)
    one = pv.color_detail(data, stub, "SW 1001")
    assert one["found"] and one["name"] == "New Name"
    assert [c["number"] for c in one["coordinating"]] == ["SW1006", "SW1002"] and [c["name"] for c in one["similar"]] == ["Near Name"]
    assert one["usedOn"] == [{"schedule": "Palette", "surface": "FIELD", "scheme": 2, "printedName": "Old Name"}] and "nearest" not in one
    gone = pv.color_detail(data, stub, "1003")
    assert gone["archived"] and gone["nearest"][0]["code"] == "SW 1005" and "SW 1003" not in {n["code"] for n in gone["nearest"]}
    assert pv.color_detail(data, stub, "SW 9999")["found"] is False
    with pytest.raises(ValueError):
        pv.color_detail(data, stub, "")


def test_loaders_are_registered_and_find_the_profile_and_data_dir(data, offline, monkeypatch):
    import jason.community
    import jason.mcp.county as county
    from jason.web.sources import default_loaders

    monkeypatch.setattr(jason.community, "community", lambda: Stub(SCHEDULE))
    monkeypatch.setattr(county, "_data_dir", lambda d: data)
    monkeypatch.setattr(county, "reserve_study", lambda year=0, data_dir=None: _brief(year))
    loaders = default_loaders()
    assert loaders["paint"]({})["schedules"][0]["title"] == "Palette"
    assert loaders["paint-color"]({"code": "SW 1001"})["found"]
    with pytest.raises(ValueError):
        loaders["paint-color"]({})


def test_the_tools_return_the_caveats(data, offline, monkeypatch):
    import jason.community
    import jason.mcp.county as county

    monkeypatch.setattr(jason.community, "community", lambda: Stub(SCHEDULE))
    monkeypatch.setattr(county, "reserve_study", lambda year=0, data_dir=None: _brief(year))
    for out in (tools.paint_colors(data_dir=data), tools.paint_colors("SW 1001", data_dir=data), tools.paint_check(data_dir=data),
                tools.paint_match("SW 1003", data_dir=data)):
        assert any("evidence, not a pin" in c for c in out["caveats"])
        assert any("Screens are not paint" in c for c in out["caveats"])
        assert any("number on the schedule governs" in c for c in out["caveats"])
    check = tools.paint_check(data_dir=data)
    assert [f["status"] for f in check["findings"]] == ["renamed", "archived", "not found"] and check["checked"]
    near = tools.paint_match("SW 1003", count=1, data_dir=data)
    assert near["nearest"][0]["code"] == "SW 1005"
    assert tools.paint_match("SW 9999", data_dir=data)["found"] is False
    assert tools.paint_match("SW 1003", data_dir=data / "nowhere")["catalog"]["available"] is False


def test_the_tools_are_served_and_exported():
    names = {t.__name__ for t in tools_for("governance")}
    assert {"paint_colors", "paint_check", "paint_match"} <= names
    assert api.paint_colors is tools.paint_colors and {"paint_colors", "paint_check", "paint_match"} <= set(api.__all__)


def test_the_api_routes_answer(tmp_path):
    import webclient
    from jason.web.app import create_app

    calls = []
    loaders = {"paint": lambda a: {"found": False}, "paint-color": lambda a: calls.append(dict(a)) or {"code": a.get("code")}}
    c = webclient.client(create_app(tmp_path, loaders, extra_writes=False))
    assert c.get("/api/paint").get_json() == {"found": False}
    assert c.get("/api/paint/color?code=SW%207027").get_json() == {"code": "SW 7027"}
