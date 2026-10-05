"""The paint schedule check and the Sherwin-Williams catalog reader (no network: a mock transport serves the catalog)."""

import json

import httpx
import pytest

from jason.community.paint import FindingKind, Maker, PaintRow, PaintSchedule, PaintSpec, Surface, check, name_key
from jason.sources.sherwin_williams import SherwinWilliams, SherwinWilliamsError, number_of


def _raw(number, name, hex_, lab, **extra):
    return {
        "colorNumber": number, "name": name, "hex": hex_, "red": 1, "green": 2, "blue": 3, "lrv": 50.0,
        "colorFamilyNames": ["Neutral"], "brandedCollectionNames": [], "isExterior": True, "isInterior": True,
        "archived": False, "ignore": False, "storeStripLocator": "1-C1", "lab": dict(zip("LAB", lab)), **extra,
    }


CATALOG = [
    _raw("1001", "Bright Name", "#aabbcc", (50, 0, 0)),
    _raw("1002", "Near Name", "#aabbcd", (51, 0, 0)),
    _raw("1003", "Gone Name", "#000000", (10, 0, 0), archived=True),
    _raw("1004", "Agreeable Gray", "#d1cbc1", (80, 1, 5)),
]


def _client(tmp_path, calls=None):
    def handler(request):
        if calls is not None:
            calls.append(str(request.url))
        assert request.headers["origin"] == "https://www.sherwin-williams.com"
        return httpx.Response(200, json=CATALOG)

    return SherwinWilliams(tmp_path / "paint" / "c.json", http=httpx.Client(transport=httpx.MockTransport(handler)))


def test_number_forms():
    assert {number_of(c) for c in ("SW 7027", "sw7027", "7027", "SW-7027")} == {"7027"}
    with pytest.raises(ValueError):
        number_of("1FACS 0024")


def test_catalog_is_cached(tmp_path):
    calls: list[str] = []
    assert _client(tmp_path, calls).color("SW 1001").name == "Bright Name"
    assert _client(tmp_path, calls).color("1002").hex == "#AABBCD"
    assert len(calls) == 1  # the second client read the week-old copy on disk
    assert json.loads((tmp_path / "paint" / "c.json").read_text())["colors"]


def test_empty_catalog_is_an_error(tmp_path):
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=[])))
    with pytest.raises(SherwinWilliamsError):
        SherwinWilliams(tmp_path / "c.json", http=http).load()


def test_search_and_nearest(tmp_path):
    sw = _client(tmp_path)
    assert [c.number for c in sw.search("grey")] == ["1004"]  # "grey" finds "Gray"
    nearest = sw.nearest(sw.color("1001"))
    assert nearest[0][1].number == "1002" and "1003" not in {c.number for _, c in nearest}  # discontinued left out


def test_check_reports_drift(tmp_path):
    sw = _client(tmp_path)
    schedule = PaintSchedule(
        title="t",
        rows=(
            PaintRow(Surface.FIELD, "FIELD", (
                PaintSpec(1, "SW 1004", "Agreeable Grey"),  # spelling is not a rename
                PaintSpec(2, "SW 1001", "Old Name"),
                PaintSpec(3, "SW 1003", "Gone Name"),
            )),
            PaintRow(Surface.TRIM, "TRIM", (PaintSpec(1, "SW 9999", "Nowhere"),)),
            PaintRow(Surface.ROOF, "ROOF", (PaintSpec(1, "1FACS 0024", "Sage", Maker.OTHER),)),
        ),
    )
    kinds = [f.kind for f in check(schedule, sw)]
    assert kinds == [FindingKind.OK, FindingKind.RENAMED, FindingKind.ARCHIVED, FindingKind.NOT_FOUND, FindingKind.NOT_CHECKED]
    assert name_key("Leap Frog") == name_key("Leapfrog")


def test_default_community_has_no_schedule_but_mystique_has():
    from jason.community import community

    schedules = community().paint_schedules()
    assert schedules and schedules[0].surface(Surface.FIELD)[0].spec(3).code == "SW 6431"


def test_reader_turns_the_models_answer_into_a_schedule(tmp_path):
    from jason.community.paint_reader import differences, read_schedule

    image = tmp_path / "schedule.png"
    image.write_bytes(b"\x89PNG not really")
    answer = {
        "title": "Palette", "prepared": "someone, 2017",
        "rows": [
            {"label": "Stucco Field", "note": "", "colors": [{"scheme": 1, "code": "sw7029", "name": "AGREEABLE GREY"}]},
            {"label": "Tile Roof", "note": "slate", "colors": [{"scheme": 1, "code": "1FACS 0024", "name": "Sage"}]},
            {"label": "Empty", "note": "", "colors": []},
        ],
    }
    seen = {}

    def post(url, body):
        seen.update(body)
        return {"message": {"content": json.dumps(answer)}}

    read = read_schedule(image, post=post)
    assert seen["messages"][0]["images"] and seen["format"]["required"]
    assert [(r.surface, s.code, s.maker) for r, s in read.specs()] == [
        (Surface.FIELD, "SW 7029", Maker.SHERWIN_WILLIAMS), (Surface.ROOF, "1FACS 0024", Maker.OTHER)]
    assert differences(read, read) == ()


def test_related_colors_come_from_the_catalog_on_disk(tmp_path):
    raw = [
        _raw("1001", "A", "#111111", (10, 0, 0), id="a", coordinatingColors={"coord1ColorId": "b", "coord2ColorId": "c", "whiteColorId": "w"},
             similarColors=["b", "missing"]),
        _raw("1002", "B", "#222222", (11, 0, 0), id="b"),
        _raw("1003", "C", "#333333", (12, 0, 0), id="c"),
        _raw("1004", "W", "#FFFFFF", (99, 0, 0), id="w"),
    ]
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=raw)

    sw = SherwinWilliams(tmp_path / "c.json", http=httpx.Client(transport=httpx.MockTransport(handler)))
    related = sw.related("SW 1001")
    assert [c["number"] for c in related["coordinatingColors"]] == ["SW1004", "SW1002", "SW1003"]  # the white first
    assert [c["name"] for c in related["similarColors"]] == ["B"]  # an id the catalog lacks is dropped
    assert calls == ["/prism/v1/colors/sherwin"]  # no per-color call
