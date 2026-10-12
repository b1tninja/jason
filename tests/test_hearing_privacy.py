"""A hearing is a member's discipline (CIV 4935(b)): its record is P3 (``zoom/hearings.json``, ``zoom/hearings/*``). The
console lists a hearing by a general title and an opaque handle; the unit, the Zoom link, the grounds, the notice, and the
findings only in the private view, logged. The day-and-address key is never in a URL or the open rows. Everything here
is made up."""

from __future__ import annotations

import json

import pytest
import webclient

from jason.tasks import hearing_decisions as hd

ADDRESS = "123 Main St #12"
SLUG = "123-main-st-12"
KEY = f"2026-10-20|{SLUG}"
ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
OFFICES = ("Dana Director", "Sam Secretary", "Pat Example", "Lee President", "Vic Vice", "A Manager")


def _seed(root, *, rows=None, migrated=True):
    (root / "zoom" / "hearings").mkdir(parents=True)
    (root / "zoom" / "hearings" / f"2026-10-20-{SLUG}.md").write_text("Notice of hearing", encoding="utf-8")
    base = {"address": ADDRESS, "building": "4", "start": "2026-10-20T18:00:00-07:00", "noticeBy": "2026-10-10", "noticeOn": "2026-10-05",
            "decisionByIfHeld": "2026-11-03", "violation": "A fence beyond the lot line", "problems": ["no meeting day for 123 Main St"],
            "zoom": {"id": "123456789", "joinUrl": "https://zoom.example/j/123456789", "passcode": "s3cret"},
            "notice": f"hearings/2026-10-20-{SLUG}.md", "noticeDoc": None}
    (root / "zoom" / "hearings.json").write_text(json.dumps({"hearings": rows or [base]}), encoding="utf-8")
    if migrated:
        hd.mint_handles(root, write=True)                  # a hearing saved today has its handle; a reader never gives one


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)
    _seed(tmp_path)
    return tmp_path


def _app(root, **kw):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    (root / "dist").mkdir(exist_ok=True)
    return create_app(root / "dist", default_loaders(), approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(ROWS), **kw)


def _client(app, who=None):
    c = webclient.client(app)
    return webclient.sign_in(c, who, rows=ROWS) if who else c


def _private(c, why="hearing review"):
    assert c.post("/api/private", json={"reason": why}).status_code == 200
    return c


def _served(root):
    f = root / "access" / "served.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def _every_string(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _every_string(v)
    elif isinstance(value, list):
        for v in value:
            yield from _every_string(v)


# --- who may read ---------------------------------------------------------------------------------------------------

def test_signed_out_is_401_and_a_person_without_an_office_is_403(root):
    app = _app(root)
    assert _client(app).get("/api/hearings").status_code == 401
    assert _client(app, "Rae Roster").get("/api/hearings").status_code == 403
    assert _client(app, "Ada Admin").get("/api/hearings").status_code == 403           # an admin with no office
    assert _client(app).post("/api/hearings/h-00000000", json={}).status_code in (401, 403)


def test_a_board_member_without_the_private_view_reads_the_clock_and_a_general_title(root):
    r = _client(_app(root), "A Manager").get("/api/hearings")
    assert r.status_code == 200 and r.json["held"] is True
    (row,) = r.json["hearings"]
    assert row["held"] is True and row["handle"].startswith("h-") and "member discipline" in row["title"]
    assert row["noticeBy"] == "2026-10-10" and row["start"].startswith("2026-10-20") and row["scheduled"] is True
    assert row["problemCount"] == 1 and row["decision"] is None
    assert [s["key"] for s in row["stages"]] == ["noticeBy", "hearing", "decisionBy"]
    assert "key" not in row and "address" not in row and "noticeRefs" not in row and "zoom" not in row
    text = " ".join(_every_string(r.json)).lower()
    for leak in ("main st", "main-st", SLUG, KEY.lower(), "fence", "s3cret", "zoom.example", "hearings/2026", "123456789"):
        assert leak not in text, leak
    assert _served(root) == []                                                         # nothing private was opened


def test_the_private_view_shows_the_unit_the_notice_and_the_grounds_and_is_logged(root):
    c = _private(_client(_app(root), "Dana Director"))
    r = c.get("/api/hearings")
    assert r.status_code == 200 and r.json["held"] is False
    (row,) = r.json["hearings"]
    assert row["address"] == ADDRESS and row["violation"].startswith("A fence") and row["held"] is False and "key" not in row
    assert row["handle"].startswith("h-") and row["noticeRefs"]
    served = [x for x in _served(root) if x.get("path") == "zoom/hearings.json"]
    assert served and served[-1]["private"] is True and served[-1]["level"] == "P3" and served[-1]["reason"] == "hearing review"


def test_every_board_office_sees_the_same_fields_in_the_private_view(root):
    seen = {}
    for who in OFFICES:
        c = _private(_client(_app(root), who))
        (row,) = c.get("/api/hearings").json["hearings"]
        seen[who] = sorted(row)
    assert len({tuple(v) for v in seen.values()}) == 1 and "address" in seen["Dana Director"]


def test_a_script_outside_a_request_sees_the_whole_row(root):
    from jason.web.hearing_rows import hearings

    (row,) = hearings({})["hearings"]
    assert row["address"] == ADDRESS and row["handle"].startswith("h-")


# --- the handle ------------------------------------------------------------------------------------------------------

def test_the_handle_is_stored_beside_the_key_and_says_nothing_of_the_day_or_address(root):
    app = _app(root)
    first = _client(app, "A Manager").get("/api/hearings").json["hearings"][0]["handle"]
    again = _client(app, "Sam Secretary").get("/api/hearings").json["hearings"][0]["handle"]
    assert first == again
    stored = json.loads((root / "zoom" / "hearings.json").read_text(encoding="utf-8"))["hearings"][0]
    assert stored["handle"] == first and hd.key_of(stored) == KEY and stored["address"] == ADDRESS     # the key is as it was
    assert "2026" not in first and "main" not in first and len(first) == 10
    assert hd.new_handle() != hd.new_handle()
    assert hd.key_for_handle(root, first) == KEY
    with pytest.raises(KeyError):
        hd.key_for_handle(root, KEY)                                                   # the key is not a handle
    with pytest.raises(KeyError):
        hd.key_for_handle(root, "")


def test_two_hearings_have_two_handles_and_a_decision_keeps_its_handle(root):
    other = {"address": "9 Elm St", "start": "2026-11-10T18:00:00-08:00", "noticeBy": "2026-10-31", "decisionByIfHeld": "2026-11-24"}
    rows = json.loads((root / "zoom" / "hearings.json").read_text(encoding="utf-8"))["hearings"] + [other]
    (root / "zoom" / "hearings.json").write_text(json.dumps({"hearings": rows}), encoding="utf-8")
    assert hd.mint_handles(root, write=True)["minted"] == 1                            # the first already has its handle
    got = hd.load(root)
    assert len({r["handle"] for r in got}) == 2
    before = {hd.key_of(r): r["handle"] for r in got}
    hd.record(root, KEY, findings="No fine.", decided_on="2026-10-20", by="Secretary")
    assert {hd.key_of(r): r["handle"] for r in hd.load(root)} == before


def _tree(root):
    import hashlib

    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_read_writes_nothing_and_a_hearing_without_a_handle_has_no_console_row(tmp_path, monkeypatch):
    """The lesson of a read-only reader that writes: a GET must leave the data folder as it found it."""
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)
    _seed(tmp_path, migrated=False)
    app = _app(tmp_path)
    before = _tree(tmp_path)
    for who, private in (("A Manager", False), ("Dana Director", True)):
        c = _client(app, who)
        if private:
            _private(c)
        before = _tree(tmp_path)                                                       # the sign-in and the private view's log are not the reader
        for _ in range(2):
            r = c.get("/api/hearings")
            assert r.status_code == 200 and r.json["hearings"] == [] and r.json["unmigrated"] == 1
        after = {k: v for k, v in _tree(tmp_path).items() if not k.startswith("access")}
        assert after == {k: v for k, v in before.items() if not k.startswith("access")}
    assert "handle" not in hd.load(tmp_path)[0] and hd.unmigrated(tmp_path) == 1
    from jason.tasks import rule_records

    rule_records.links(tmp_path)
    assert "handle" not in hd.load(tmp_path)[0]                                        # the rule records' links read too
    assert hd.mint_handles(tmp_path, write=True)["minted"] == 1
    assert _client(app, "A Manager").get("/api/hearings").json["hearings"][0]["handle"].startswith("h-")


# --- the writer ------------------------------------------------------------------------------------------------------

BODY = {"findings": "A $50 fine, waived if the fence is moved by December 1.", "decidedOn": "2026-10-20", "by": "Sam Secretary"}


def test_recording_a_decision_needs_the_private_view_and_goes_by_handle(root):
    app = _app(root)
    c = _client(app, "Sam Secretary")
    handle = c.get("/api/hearings").json["hearings"][0]["handle"]
    assert _client(app).post(f"/api/hearings/{handle}", json=BODY).status_code == 401
    assert _client(app, "Rae Roster").post(f"/api/hearings/{handle}", json=BODY).status_code == 403
    refused = c.post(f"/api/hearings/{handle}", json=BODY)
    assert refused.status_code == 403 and "private view" in refused.json["error"]
    assert "decision" not in hd.load(root)[0]                                          # nothing was written

    _private(c)
    done = c.post(f"/api/hearings/{handle}", json=BODY)
    assert done.status_code == 200 and done.json["handle"] == handle and done.json["address"] == ADDRESS
    assert done.json["decision"]["noticeDueBy"] == "2026-11-03" and any(s["key"] == "noticeDueBy" for s in done.json["stages"])
    assert hd.load(root)[0]["decision"]["findings"] == BODY["findings"]
    assert any(x.get("path") == "zoom/hearings.json" and x["private"] for x in _served(root))

    assert c.post(f"/api/hearings/{handle}", json={**BODY, "decidedOn": "2026-10-01"}).status_code == 400
    assert c.post("/api/hearings/h-ffffffff", json=BODY).status_code == 404
    assert c.post(f"/api/hearings/{KEY}", json=BODY).status_code == 404                # the day-and-address key names nothing
    assert c.post(f"/api/hearings/{SLUG}", json=BODY).status_code == 404


def test_a_recorded_decision_stays_out_of_the_open_rows_but_its_dates_show(root):
    c = _private(_client(_app(root), "Sam Secretary"))
    handle = c.get("/api/hearings").json["hearings"][0]["handle"]
    assert c.post(f"/api/hearings/{handle}", json=BODY).status_code == 200
    r = _client(_app(root), "Pat Example").get("/api/hearings")
    (row,) = r.json["hearings"]
    assert sorted(row["decision"]) == ["decidedOn", "noticeDueBy", "recorded"]
    text = " ".join(_every_string(r.json))
    assert "fence" not in text and "Sam Secretary" not in text and "$50" not in text


def test_where_sign_in_is_not_set_up_the_private_view_cannot_open_so_the_rows_are_held(root):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    (root / "dist").mkdir(exist_ok=True)
    app = create_app(root / "dist", default_loaders(), approvals_live=None, extra_writes=False,
                     sign_in=webclient.roster_sign_in(ROWS, configured=False))
    r = webclient.client(app).get("/api/hearings")
    assert r.status_code == 200 and r.json["held"] is True and "address" not in r.json["hearings"][0]


# --- the place ---------------------------------------------------------------------------------------------------------

def test_the_hearing_store_and_its_notices_are_p3_by_path(root):
    from jason.web.access import Level, level_of_path

    assert level_of_path("zoom/hearings.json", root) is Level.P3
    assert level_of_path(f"zoom/hearings/2026-10-20-{SLUG}.md", root) is Level.P3
