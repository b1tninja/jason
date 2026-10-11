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
ROSTER = webclient.ROSTER + (("Dee Dual", "director, secretary", "dee@example.org", False),)


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
    return create_app(dist, KEYS, approvals_live=None, extra_writes=False, sign_in=webclient.roster_sign_in(ROSTER, dev=True))


def _as(app, name):
    return webclient.sign_in(webclient.client(app), name, rows=ROSTER)


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


# --- a director sees counts only ----------------------------------------------------------------------------------------

FAKES = ("Zelda Fakeman", "Quill Nonesuch", "9001 Pretend Row", "9002 Pretend Row", "Mox Placeholder")


def _rich(monkeypatch):
    """Tool output that names owners and units everywhere the real tools do, with made-up, distinctive names."""
    rows = [{"id": "gmail:a1", "channel": "gmail", "who": FAKES[0], "unit": FAKES[2], "summary": "from " + FAKES[0],
             "attachments": [FAKES[2] + ".pdf"], "state": "new"},
            {"id": "gmail:a2", "channel": "gmail", "who": FAKES[1], "unit": FAKES[3], "summary": "", "attachments": [],
             "state": "new"},
            {"id": "payhoa:a3", "channel": "payhoa", "who": FAKES[4], "unit": FAKES[3], "summary": "", "attachments": [],
             "state": "new"}]
    monkeypatch.setattr("jason.mcp.response_inbox.new_responses", lambda **kw: {
        "found": True, "state": "new", "count": 3, "arrivals": rows, "inbox": {"new": 3}, "checked": [{"channel": "gmail"}],
        "note": "n", "caveats": ["c"]})
    waiting = [{"unit": FAKES[2], "owner": FAKES[0], "channel": "email", "reference": "r1"}]
    monkeypatch.setattr("jason.mcp.response_inbox.outstanding_responses", lambda **kw: {
        "found": True, "requests": [{"request": "info", "sent": 5, "answered": 3, "notResponded": 1, "outstanding": waiting,
                                     "answeredCopies": [{"unit": FAKES[3], "owner": FAKES[1]}],
                                     "neverAsked": [{"unit": FAKES[3], "owner": FAKES[4]}], "neverAskedAnswered": 0}],
        "catalog": {"copies": 5}, "lastCheck": {"ageHours": 2}, "note": "n", "caveats": ["c"]})
    item = {"id": "fu-1", "kind": "review", "due": "2026-10-12", "subject": "gmail:a1", "basis": "proposed policy",
            "what": f"Read the returned form that came by gmail from {FAKES[0]} ({FAKES[2]})", "outstanding": 1,
            "names": [f"{FAKES[0]} ({FAKES[2]})"], "state": "due", "dueNote": "proposed: 3 days", "source": "inbox",
            "command": "jason responses --read gmail:a1 --by NAME"}
    clock = {**item, "id": "fu-2", "kind": "answer-due", "source": "clock", "command": "jason responses --show gmail:a2",
             "what": f"Answer: {FAKES[1]}'s request, 10 business days from receipt", "names": [FAKES[1]]}
    resend = {**item, "id": "fu-3", "kind": "resend", "source": "ledger", "what": "2 members (email outcome read 2026-10-01): resend",
              "names": [FAKES[2], FAKES[3]], "outstanding": 2,
              "command": f'jason owner-info --mail-batch --only "{FAKES[2]}" --only "{FAKES[3]}" --resend (a dry run)'}
    monkeypatch.setattr("jason.mcp.followups.followups", lambda **kw: {
        "found": True, "count": 3, "counts": {"due": 3}, "items": [item, clock, resend], "ages": {"campaigns": {}},
        "note": "n", "caveats": ["c"]})
    monkeypatch.setattr("jason.mcp.followups.campaign_status", lambda **kw: {
        "found": True, "count": 1, "campaigns": [{
            "campaign": "NP27E", "asked": {"total": 5, "byChannel": {"email": 5}},
            "answered": {"answered": 3, "byChannel": {"email": {"answered": 3}}},
            "outstanding": {"count": 1, "owners": [{"unit": FAKES[2], "name": FAKES[0]}], "neverAsked": 4},
            "unreachable": {"count": 1, "owners": [{"unit": FAKES[3], "why": "email bounced"}], "attempts": 2},
            "nextFollowUp": item, "ages": {"catalogHours": 3}, "missing": [], "notes": []}], "note": "n", "caveats": ["c"]})


def _everything(c) -> str:
    return " ".join(c.get(f"/api/{k}").get_data(as_text=True) for k in
                    ("responses?state=all", "outstanding-responses", "campaign-status", "followups"))


def test_a_director_alone_reads_counts_and_no_owner_name_or_unit(app, monkeypatch):
    _rich(monkeypatch)
    c = _as(app, "Dana Director")
    text = _everything(c)
    assert not [f for f in FAKES if f in text]
    got = c.get("/api/responses?state=all").json
    assert got["countsOnly"] is True and "countsOnlyWhy" in got and "arrivals" not in got
    assert got["count"] == 3 and got["inbox"] == {"new": 3} and got["byChannel"] == {"gmail": 2, "payhoa": 1}
    assert got["checked"] == [{"channel": "gmail"}] and got["caveats"] == ["c"]
    out = c.get("/api/outstanding-responses").json
    [req] = out["requests"]
    assert out["countsOnly"] is True and req["sent"] == 5 and req["answered"] == 3 and req["notResponded"] == 1
    assert req["outstandingCount"] == 1 and req["neverAskedCount"] == 1 and "outstanding" not in req and "neverAsked" not in req
    [camp] = c.get("/api/campaign-status").json["campaigns"]
    assert camp["outstanding"] == {"count": 1, "neverAskedCount": 4} and camp["unreachable"] == {"count": 1, "attempts": 2}
    assert camp["asked"]["total"] == 5 and camp["nextFollowUp"]["due"] == "2026-10-12" and "names" not in camp["nextFollowUp"]
    fu = c.get("/api/followups").json
    assert fu["countsOnly"] is True and [i["outstanding"] for i in fu["items"]] == [1, 1, 2]
    assert all("names" not in i and i["state"] == "due" and i["basis"] and i["command"] for i in fu["items"])
    assert fu["items"][0]["what"] == "Read a returned form that came in"
    assert fu["items"][1]["what"] == "Answer: a request, 10 business days from receipt"
    assert fu["items"][2]["command"] == "jason owner-info --mail-batch --resend (a dry run)"


@pytest.mark.parametrize("name", ["Pat Example", "Lee President", "A Manager", "Sam Secretary", "Dee Dual", "Tess Two"])
def test_every_other_office_still_reads_the_names(app, monkeypatch, name):
    _rich(monkeypatch)
    c = _as(app, name)
    assert c.get("/api/responses?state=all").json["arrivals"][0]["who"] == FAKES[0]
    [req] = c.get("/api/outstanding-responses").json["requests"]
    assert req["outstanding"][0]["owner"] == FAKES[0] and req["neverAsked"] and "countsOnly" not in req
    [camp] = c.get("/api/campaign-status").json["campaigns"]
    assert camp["outstanding"]["owners"][0]["name"] == FAKES[0] and camp["unreachable"]["owners"]
    first = c.get("/api/followups").json["items"][0]
    assert FAKES[0] in first["what"] and first["names"]
    assert "countsOnly" not in c.get("/api/followups").json


def test_one_arrival_is_refused_to_a_director_alone_and_open_to_a_director_who_is_also_secretary(app):
    plain = _as(app, "Dana Director").get("/api/response?id=gmail:abc")
    assert plain.status_code == 403 and "counts only" in plain.json["error"]
    assert _as(app, "Dee Dual").get("/api/response?id=gmail:abc").status_code == 200


def test_an_admin_viewing_as_a_director_is_counts_only_and_as_a_treasurer_is_not(app, monkeypatch):
    _rich(monkeypatch)
    c = _as(app, "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Dana Director", "role": "director"}
    assert c.get("/api/responses?state=all").json["countsOnly"] is True
    assert c.get("/api/response?id=gmail:abc").status_code == 403
    assert not [f for f in FAKES if f in _everything(c)]
    with c.session_transaction() as s:
        s["acting"] = {"name": "", "role": "director"}                  # the office alone
    assert c.get("/api/campaign-status").json["countsOnly"] is True
    with c.session_transaction() as s:
        s["acting"] = {"name": "Pat Example", "role": "treasurer"}
    assert c.get("/api/responses?state=all").json["arrivals"][0]["who"] == FAKES[0]


def test_counts_only_is_one_test_of_the_offices():
    viewer = lambda *o: access.Viewer("x", frozenset(o))  # noqa: E731
    assert access.counts_only(viewer("director")) is True
    for offices in ((), ("director", "secretary"), ("treasurer",), ("manager", "director"), ("president",)):
        assert access.counts_only(viewer(*offices)) is False


def test_the_last_scrub_drops_an_owner_key_the_shaping_missed():
    stray = {"found": True, "count": 2, "neverAskedCount": 1, "outstanding": 3,
             "deep": [{"unit": "9001 Pretend Row", "kept": 1, "owners": ["x"], "neverAsked": ["y"], "outstanding": ["z"]}],
             "unreachableOwners": [], "names": ["n"], "who": "w", "summary": "s", "attachments": ["a"], "units": ["u"]}
    assert rv.counts_scrub(stray) == {"found": True, "count": 2, "neverAskedCount": 1, "outstanding": 3, "deep": [{"kept": 1}]}


def test_they_are_registered_and_no_owner_source_and_no_writer():
    from jason.web.extra.owner_view import OWNER_SOURCES
    from jason.web.sources import EXTRA_LOADERS, EXTRA_WRITERS

    for key in KEYS:
        assert key not in OWNER_SOURCES and key not in EXTRA_WRITERS
        assert EXTRA_LOADERS[key].startswith("jason.web.extra.request_views:")


def test_a_persons_own_followup_shows_a_director_that_it_exists_not_its_words():
    row = {"source": "person", "kind": "manual", "what": "Call B. Owner at 456 Oak Ln about the gate", "why": "Owner asked on Oct 2",
           "state": "upcoming", "due": "2026-10-20", "command": "", "basis": "person"}
    shown = rv._item(row)
    assert shown["what"] == "A follow-up a person added" and shown["why"] == ""
    assert shown["due"] == "2026-10-20" and shown["state"] == "upcoming" and shown["kind"] == "manual"
    assert "Oak Ln" not in str(shown) and "B. Owner" not in str(shown)
