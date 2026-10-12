"""``POST /api/hearings/<handle>`` writes a member's discipline (Civil Code 4935(b)), and its answer is the whole P3 row.
It opens only in the private view. With no console sign-in set up the private view cannot open, so the route answers as
for a hearing that does not exist (404, nothing echoed); where sign-in is set up, 401 or 403 comes before the handle is
looked up and is the same for every handle, and an opening is logged only when a real row is involved. A real handle and a
missing one are indistinguishable to anyone outside the private view. Everything here is made up."""

from __future__ import annotations

import json

import pytest
import webclient

HANDLE, MISSING = "h-0a1b2c3d", "h-ffffffff"
ADDRESS = "123 Main St #12"
ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
BODY = {"findings": "A $50 fine, waived if the fence is moved.", "decidedOn": "2026-10-20"}
LEAKS = ("Main St", "fence", "s3cret", "zoom.example", "123456789", "$50")


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)
    (tmp_path / "zoom").mkdir()
    row = {"handle": HANDLE, "address": ADDRESS, "building": "4", "start": "2026-10-20T18:00:00-07:00", "noticeBy": "2026-10-10",
           "decisionByIfHeld": "2026-11-03", "violation": "A fence beyond the lot line",
           "zoom": {"id": "123456789", "joinUrl": "https://zoom.example/j/123456789", "passcode": "s3cret"}}
    (tmp_path / "zoom" / "hearings.json").write_text(json.dumps({"hearings": [row]}), encoding="utf-8")
    return tmp_path


def _client(root, who=None, *, configured=True):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    (root / "dist").mkdir(exist_ok=True)
    app = create_app(root / "dist", default_loaders(), approvals_live=None, extra_writes=False,
                     sign_in=webclient.roster_sign_in(ROWS, configured=configured))
    c = webclient.client(app)
    return webclient.sign_in(c, who, rows=ROWS) if who else c


def _private(c):
    assert c.post("/api/private", json={"reason": "hearing review"}).status_code == 200
    return c


def _served(root):
    f = root / "access" / "served.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def _stored(root):
    return json.loads((root / "zoom" / "hearings.json").read_text(encoding="utf-8"))["hearings"][0]


def _quiet(r):
    text = r.get_data(as_text=True)
    for word in LEAKS:
        assert word not in text, word


@pytest.mark.parametrize("who, status", [(None, 401), ("Rae Roster", 403), ("Ada Admin", 403), ("Pat Example", 403)])
def test_outside_the_private_view_a_real_handle_and_a_missing_one_get_the_same_answer(root, who, status):
    c = _client(root, who)
    real, gone = c.post(f"/api/hearings/{HANDLE}", json=BODY), c.post(f"/api/hearings/{MISSING}", json=BODY)
    assert real.status_code == gone.status_code == status
    assert real.get_data() == gone.get_data()
    _quiet(real)
    assert "decision" not in _stored(root) and _served(root) == []


def test_in_the_private_view_a_real_handle_is_written_and_logged_and_a_missing_one_is_404_and_not(root):
    c = _private(_client(root, "Dana Director"))
    gone = c.post(f"/api/hearings/{MISSING}", json=BODY)
    assert gone.status_code == 404 and gone.json == {"error": "no such hearing"}
    assert [x for x in _served(root) if x.get("path") == "zoom/hearings.json"] == []     # a row that is not there is not an opening
    done = c.post(f"/api/hearings/{HANDLE}", json={**BODY, "by": "Dana Director"})
    assert done.status_code == 200 and done.json["handle"] == HANDLE
    assert _stored(root)["decision"]["by"] == "Dana Director"
    assert len([x for x in _served(root) if x.get("path") == "zoom/hearings.json" and x["private"]]) >= 1


def test_where_sign_in_is_not_set_up_the_write_is_the_404_a_missing_hearing_gets_and_echoes_nothing(root):
    c = _client(root, configured=False)
    before = (root / "zoom" / "hearings.json").read_text(encoding="utf-8")
    real, gone = c.post(f"/api/hearings/{HANDLE}", json={**BODY, "by": "At The Machine"}), c.post(f"/api/hearings/{MISSING}", json=BODY)
    assert real.status_code == gone.status_code == 404
    assert real.get_data() == gone.get_data()
    _quiet(real)
    assert c.post(f"/api/hearings/{HANDLE}", json={}).status_code == 404                 # before the body is read
    assert (root / "zoom" / "hearings.json").read_text(encoding="utf-8") == before and _served(root) == []


def test_a_script_outside_a_request_still_records_the_decision(root):
    from jason.web.hearing_rows import write

    write(HANDLE, {**BODY, "by": "Terminal"})
    assert _stored(root)["decision"]["by"] == "Terminal"
