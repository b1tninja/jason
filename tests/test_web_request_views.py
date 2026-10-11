"""The requests area's loaders (``jason.web.extra.request_views``): signed in with an office that opens owners' names and
units (P2), never the owner view, and an arrival's reading, keyed answers, and acts held back unless the viewer may see an
owner's private material (P3) in the private view, each opening logged. The tools underneath are stubbed with made-up
rows: their own tests (test_mcp_response_inbox, test_followups) cover the readings.
"""

from __future__ import annotations

import pytest
import webclient

from jason.web import access
from jason.web.extra import request_views as rv

KEYS = {"responses": rv.responses, "response": rv.response, "outstanding-responses": rv.outstanding,
        "campaign-status": rv.campaign, "followups": rv.followups, "form-library": rv.form_library}
ARRIVAL = {"id": "gmail:abc", "who": "Pat Example", "unit": "101 Example Way", "state": "new"}


@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    monkeypatch.setattr("jason.mcp.response_inbox.new_responses", lambda **kw: {"found": True, "arrivals": [ARRIVAL], "kw": kw})
    monkeypatch.setattr("jason.mcp.response_inbox.outstanding_responses", lambda **kw: {"found": True, "kw": kw})
    monkeypatch.setattr("jason.mcp.followups.campaign_status", lambda **kw: {"found": True, "kw": kw})
    monkeypatch.setattr("jason.mcp.followups.followups", lambda **kw: {"found": True, "kw": kw})
    monkeypatch.setattr("jason.mcp.response_inbox.response", lambda id, **kw: (
        {"found": True, "arrival": ARRIVAL, "reading": {"fields": [1]}, "keyed": {"answers": {"x": "y"}}, "acts": [{"by": "A"}]}
        if id == "gmail:abc" else {"found": False, "reason": "no such arrival"}))
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, KEYS, approvals_live=None, extra_writes=False, sign_in=webclient.roster_sign_in(dev=True))


def _as(app, name):
    return webclient.sign_in(webclient.client(app), name)


@pytest.mark.parametrize("key", sorted(KEYS))
def test_a_sign_in_and_an_office_are_needed_and_the_owner_view_is_refused(app, key):
    assert webclient.client(app).get(f"/api/{key}").status_code == 401
    assert _as(app, "Ada Admin").get(f"/api/{key}").status_code == 403         # no office, so no owners' names
    assert _as(app, "Pat Example").get(f"/api/{key}?view=owner").status_code == 403


def test_an_office_that_opens_owners_names_reads_the_lists(app):
    c = _as(app, "Pat Example")
    assert c.get("/api/responses?state=all&channel=gmail&days=7").json["kw"] == {
        "request": "", "channel": "gmail", "unit": "", "state": "all", "days": 7}
    assert c.get("/api/followups?days=oops&kind=remind").json["kw"]["days"] == 30
    assert c.get("/api/campaign-status?code=NP27E").json["kw"] == {"code": "NP27E"}
    assert c.get("/api/outstanding-responses").status_code == 200


def test_an_arrivals_own_words_are_held_back_outside_the_private_view(app, monkeypatch):
    served = []
    monkeypatch.setattr(access, "served", lambda *a, **k: served.append(k))
    for name in ("Pat Example", "Lee President"):
        out = _as(app, name).get("/api/response?id=gmail:abc").json
        assert out["held"] is True and out["reading"] is None and out["keyed"] is None and out["acts"] == []
        assert out["arrival"]["who"] == "Pat Example" and "private view" in out["heldWhy"]
    assert served == []


def test_in_the_private_view_the_president_opens_it_and_it_is_logged(app, monkeypatch):
    served = []
    monkeypatch.setattr(access, "private_window", lambda: {"id": "w", "reason": "reviewing"})
    monkeypatch.setattr(access, "served", lambda viewer, level, **k: served.append((viewer.name, level.value, k)))
    out = _as(app, "Lee President").get("/api/response?id=gmail:abc").json
    assert out["held"] is False and out["reading"] == {"fields": [1]} and out["acts"] == [{"by": "A"}]
    assert served == [("Lee President", "P3", {"address": "api/response/gmail:abc"})]
    treasurer = _as(app, "Pat Example").get("/api/response?id=gmail:abc").json         # the treasurer's office never opens P3
    assert treasurer["held"] is True


def test_an_opening_that_cannot_be_logged_is_not_served(app, monkeypatch):
    def fail(*a, **k):
        raise OSError("disk")

    monkeypatch.setattr(access, "private_window", lambda: {"id": "w", "reason": "reviewing"})
    monkeypatch.setattr(access, "served", fail)
    assert _as(app, "Lee President").get("/api/response?id=gmail:abc").json["held"] is True


def test_a_missing_arrival_is_a_miss_not_an_error(app):
    out = _as(app, "Pat Example").get("/api/response?id=gmail:nope")
    assert out.status_code == 200 and out.json["found"] is False


def test_the_form_library_lists_the_forms_with_their_status_and_filters_by_tier(app):
    c = _as(app, "Pat Example")
    out = c.get("/api/form-library").json
    assert out["found"] is True and out["forms"] and {"key", "status", "findings"} <= set(out["forms"][0])
    state = c.get("/api/form-library?tier=state").json
    assert {f["tier"] for f in state["forms"]} <= {"state"}
    assert c.get("/api/form-library?tier=nope").status_code == 400


def test_they_are_registered_and_no_owner_source_and_no_writer():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    for key in KEYS:
        assert key not in OWNER_SOURCES and key not in EXTRA_WRITERS
        assert EXTRA_LOADERS[key].startswith("jason.web.extra.request_views:")
