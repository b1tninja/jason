"""A decision made in executive session (Civil Code 4935(e)) is a restricted record, and so is the route that writes it.
``POST /api/decisions[/<id>]`` is behind the P2 gate (401 signed out, 403 without an office); an executive row, a record
that would replace one, and a body that makes a decision executive open only in the private view, and outside it answer
the 404 a decision that does not exist gets, before the body is read, so the guessable counter id
(``<meeting>--executive-<n>``) is not an existence oracle and no row is echoed. The decision is recorded by the signed-in
account, never the ``by`` the body carries. Everything here is made up."""

from __future__ import annotations

import json

import pytest
import webclient

from jason.tasks import decisions as store

ROWS = webclient.ROSTER + (("Rae Roster", "", "rae@example.org", False),)
DAY = "2026-10-20"
EXEC_ID = f"{DAY}--executive-1"
OPEN_ID = f"{DAY}--reserve-loan"
SECRETS = ("Doe", "settle", "5,000", "member_discipline", "litigation")        # never in an error or an open answer
GONE = {"outcome": "approved"}
HANDLE = "h-0a1b2c3d"


def _seed(root):
    store.record(root, DAY, "Reserve loan", "Move to approve the reserve loan.", item="reserve-loan", votes={"Dana Director": "aye"})
    store.record(root, DAY, "Settlement with Doe", "Move to settle the Doe claim for $5,000.", session=store.EXECUTIVE, subject="litigation",
                 votes={"Dana Director": "aye", "Lee President": "no"}, notes="Doe's counsel offered $5,000")
    assert [d.id for d in store.load(root)] == [OPEN_ID, EXEC_ID]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setattr("jason.config.data_dir", lambda *a, **k: tmp_path)
    _seed(tmp_path)
    return tmp_path


def _app(root, *, configured: bool = True):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    (root / "dist").mkdir(exist_ok=True)
    return create_app(root / "dist", default_loaders(), approvals_live=None, extra_writes=False,
                      sign_in=webclient.roster_sign_in(ROWS, configured=configured))


def _client(app, who=None):
    c = webclient.client(app)
    return webclient.sign_in(c, who, rows=ROWS) if who else c


def _private(c, why="decision review"):
    assert c.post("/api/private", json={"reason": why}).status_code == 200
    return c


def _stored(root):
    return {d.id: d for d in store.load(root)}


def _served(root):
    f = root / "access" / "served.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.is_file() else []


def _no_row(r):
    text = r.get_data(as_text=True)
    for word in SECRETS:
        assert word not in text, word


# --- signed out, and no office ------------------------------------------------------------------------------------------

def test_signed_out_is_401_and_a_person_without_an_office_is_403_for_every_id_alike(root):
    app = _app(root)
    before = (root / "board" / "decisions.json").read_text(encoding="utf-8")
    for who, status in ((None, 401), ("Rae Roster", 403), ("Ada Admin", 403)):           # an admin with no office is not the board
        c = _client(app, who)
        for path in (f"/api/decisions/{EXEC_ID}", f"/api/decisions/{OPEN_ID}", f"/api/decisions/{DAY}--executive-99", "/api/decisions"):
            r = c.post(path, json={**GONE, "by": "Someone", "meeting": DAY, "title": "t", "motion": "m"})
            assert r.status_code == status, (who, path)
            _no_row(r)
    assert (root / "board" / "decisions.json").read_text(encoding="utf-8") == before


# --- an office that opens P2, without the private view -----------------------------------------------------------------

def test_an_office_without_the_private_view_changes_an_open_decision_and_gets_404_for_an_executive_one(root):
    c = _client(_app(root), "Pat Example")
    done = c.post(f"/api/decisions/{OPEN_ID}", json={"notes": "Carried 4-1."})
    assert done.status_code == 200 and done.json["notes"] == "Carried 4-1." and done.json["by"] == "Pat Example"
    before = (root / "board" / "decisions.json").read_text(encoding="utf-8")

    shut = c.post(f"/api/decisions/{EXEC_ID}", json={"notes": "x"})
    gone = c.post(f"/api/decisions/{DAY}--executive-99", json={"notes": "x"})
    assert shut.status_code == 404 and gone.status_code == 404
    assert shut.get_data() == gone.get_data()                                          # the same answer: no oracle
    _no_row(shut)
    assert (root / "board" / "decisions.json").read_text(encoding="utf-8") == before
    assert _served(root) == []                                                         # nothing private was opened


def test_the_404_comes_before_the_body_is_read_so_a_bad_body_is_no_oracle(root):
    c = _client(_app(root), "Pat Example")
    for body in ({"outcome": "carried"}, {"votes": "all"}, {}, {"subject": "gossip"}):
        a = c.post(f"/api/decisions/{EXEC_ID}", json=body)
        b = c.post(f"/api/decisions/{DAY}--executive-99", json=body)
        assert a.status_code == b.status_code == 404, body
        assert a.get_data() == b.get_data()
    assert c.post(f"/api/decisions/{OPEN_ID}", json={"outcome": "carried"}).status_code == 400       # an open row is still validated
    assert c.post(f"/api/decisions/{OPEN_ID}", json={}).status_code == 400


def test_a_body_that_makes_a_decision_executive_is_a_404_outside_the_private_view(root):
    c = _client(_app(root), "Pat Example")
    before = (root / "board" / "decisions.json").read_text(encoding="utf-8")
    assert c.post(f"/api/decisions/{OPEN_ID}", json={"session": store.EXECUTIVE}).status_code == 404
    r = c.post("/api/decisions", json={"meeting": DAY, "title": "Another", "motion": "Move to hire.", "session": store.EXECUTIVE, "subject": "personnel"})
    assert r.status_code == 404
    _no_row(r)
    assert (root / "board" / "decisions.json").read_text(encoding="utf-8") == before


def test_recording_over_an_executive_row_by_its_id_is_a_404_and_does_not_echo_it(root):
    c = _client(_app(root), "Pat Example")
    before = (root / "board" / "decisions.json").read_text(encoding="utf-8")
    r = c.post("/api/decisions", json={"meeting": DAY, "title": "t", "motion": "m", "item": "executive-1"})      # the key is the executive row's id
    assert r.status_code == 404
    _no_row(r)
    assert (root / "board" / "decisions.json").read_text(encoding="utf-8") == before
    ok = c.post("/api/decisions", json={"meeting": DAY, "title": "Fence", "motion": "Move to repair the fence.", "item": "fence"})
    assert ok.status_code == 200 and ok.json["id"] == f"{DAY}--fence" and ok.json["by"] == "Pat Example"


# --- the private view --------------------------------------------------------------------------------------------------

def test_in_the_private_view_an_executive_decision_is_changed_and_made_and_each_opening_is_logged(root):
    c = _private(_client(_app(root), "Dana Director"))
    done = c.post(f"/api/decisions/{EXEC_ID}", json={"outcome": "approved"})
    assert done.status_code == 200 and done.json["outcome"] == "approved" and done.json["session"] == store.EXECUTIVE
    assert "Doe" in done.json["motion"]
    made = c.post("/api/decisions", json={"meeting": DAY, "title": "Another", "motion": "Move to hire.", "session": store.EXECUTIVE, "subject": "personnel"})
    assert made.status_code == 200 and made.json["id"] == f"{DAY}--executive-2"
    assert c.post(f"/api/decisions/{DAY}--executive-99", json=GONE).status_code == 404            # still a miss
    served = [x for x in _served(root) if x.get("path") == "board/decisions.json"]
    assert len(served) == 2 and all(x["private"] is True and x["level"] == "P3" and x["reason"] == "decision review" for x in served)


def test_every_office_in_the_private_view_reaches_the_executive_row(root):
    for who in ("Sam Secretary", "Lee President", "Vic Vice", "A Manager", "Pat Example"):
        c = _private(_client(_app(root), who))
        assert c.post(f"/api/decisions/{EXEC_ID}", json={"notes": who}).status_code == 200, who


def test_a_person_without_an_office_cannot_open_the_private_view_so_the_row_stays_shut(root):
    c = _client(_app(root), "Rae Roster")
    assert c.post("/api/private", json={"reason": "peek"}).status_code in (401, 403)
    assert c.post(f"/api/decisions/{EXEC_ID}", json=GONE).status_code == 403


# --- loopback with no sign-in set up -----------------------------------------------------------------------------------

def test_where_sign_in_is_not_set_up_an_open_decision_is_written_and_an_executive_one_is_a_404(root):
    c = _client(_app(root, configured=False))
    ok = c.post(f"/api/decisions/{OPEN_ID}", json={"notes": "Carried.", "by": "At The Machine"})
    assert ok.status_code == 200 and ok.json["by"] == "At The Machine"                 # the typed by, as the person at the machine
    before = (root / "board" / "decisions.json").read_text(encoding="utf-8")
    for r in (c.post(f"/api/decisions/{EXEC_ID}", json={"notes": "x"}),
              c.post("/api/decisions", json={"meeting": DAY, "title": "t", "motion": "Move to settle.", "session": store.EXECUTIVE}),
              c.post("/api/decisions", json={"meeting": DAY, "title": "t", "motion": "m", "item": "executive-1"})):
        assert r.status_code == 404
        _no_row(r)
    assert c.post(f"/api/decisions/{DAY}--executive-99", json=GONE).status_code == 404
    assert json.loads((root / "board" / "decisions.json").read_text(encoding="utf-8"))["decisions"][1] == \
        json.loads(before)["decisions"][1]                                             # the executive row is as it was


def test_a_script_outside_a_request_writes_any_decision(root):
    from jason.web.sources import write_decision

    assert write_decision(EXEC_ID, {"notes": "n", "by": "Terminal"})["by"] == "Terminal"
    assert write_decision("", {"meeting": DAY, "title": "t", "motion": "m", "session": store.EXECUTIVE})["id"] == f"{DAY}--executive-2"


# --- who recorded it ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("body", [{"by": ""}, {}, {"by": "Sam Secretary"}, {"by": "sam secretary"}])
def test_the_decision_is_recorded_by_the_signed_in_account_whether_the_body_names_it_or_not(root, body):
    c = _client(_app(root), "Sam Secretary")
    made = c.post("/api/decisions", json={"meeting": DAY, "title": "Fence", "motion": "Move to repair the fence.", "item": "fence", **body})
    assert made.status_code == 200 and made.json["by"] == "Sam Secretary", made.get_data(as_text=True)
    changed = c.post(f"/api/decisions/{OPEN_ID}", json={"notes": "n", **body})
    assert changed.status_code == 200 and changed.json["by"] == "Sam Secretary"
    assert _stored(root)[OPEN_ID].by == "Sam Secretary"


def test_a_body_that_names_another_person_is_refused_and_nothing_is_written(root):
    """The console's own guard (``signin._signed_in``) refuses it for every write; ``gates.recorded_by`` is the second
    line for a caller that reaches the writer without it, and is tested below."""
    c = _client(_app(root), "Sam Secretary")
    before = (root / "board" / "decisions.json").read_text(encoding="utf-8")
    for path, body in (("/api/decisions", {"meeting": DAY, "title": "t", "motion": "m", "by": "Mallory"}),
                       (f"/api/decisions/{OPEN_ID}", {"notes": "n", "by": "Mallory"}),
                       (f"/api/decisions/{EXEC_ID}", {"notes": "n", "by": "Mallory"})):
        r = c.post(path, json=body)
        assert r.status_code == 403 and "Mallory" in r.json["error"] and "Doe" not in r.get_data(as_text=True)
    assert (root / "board" / "decisions.json").read_text(encoding="utf-8") == before


def test_recorded_by_is_the_account_in_a_request_and_the_typed_by_only_where_sign_in_is_not_set_up(root):
    from jason.web import gates

    assert gates.recorded_by({"by": "Terminal"}) == "Terminal" and gates.recorded_by({}) == ""         # outside a request
    seen = []
    app = _app(root)
    app.add_url_rule("/t/by", "t_by", lambda: (seen.append(gates.recorded_by({"by": "Mallory"})) or "ok"), methods=["GET"])
    assert _client(app, "Sam Secretary").get("/t/by").status_code == 200 and seen == ["Sam Secretary"]    # whatever the body says
    assert _client(app).get("/t/by").status_code == 401                                                  # signed out where it is set up
    off = _app(root, configured=False)
    off.add_url_rule("/t/by", "t_by", lambda: (seen.append(gates.recorded_by({"by": "At The Machine"})) or "ok"), methods=["GET"])
    assert _client(off).get("/t/by").status_code == 200 and seen[-1] == "At The Machine"


# --- the hearing writer takes its `by` from the account too ------------------------------------------------------------

def _hearing(root):
    (root / "zoom").mkdir(exist_ok=True)
    row = {"handle": HANDLE, "address": "123 Main St #12", "building": "4", "start": "2026-10-20T18:00:00-07:00", "noticeBy": "2026-10-10",
           "decisionByIfHeld": "2026-11-03", "violation": "A fence beyond the lot line"}
    (root / "zoom" / "hearings.json").write_text(json.dumps({"hearings": [row]}), encoding="utf-8")


@pytest.mark.parametrize("by", ["", None])
def test_a_hearing_decision_is_recorded_by_the_signed_in_account(root, by):
    from jason.tasks import hearing_decisions as hd

    _hearing(root)
    c = _private(_client(_app(root), "Sam Secretary"))
    handle = HANDLE
    body = {"findings": "No fine.", "decidedOn": "2026-10-20"}
    if by is not None:
        body["by"] = by
    done = c.post(f"/api/hearings/{handle}", json=body)
    assert done.status_code == 200, done.get_data(as_text=True)
    assert hd.load(root)[0]["decision"]["by"] == "Sam Secretary"


def test_a_hearing_decision_that_names_another_person_is_refused_and_nothing_is_written(root):
    from jason.tasks import hearing_decisions as hd

    _hearing(root)
    c = _private(_client(_app(root), "Sam Secretary"))
    handle = HANDLE
    r = c.post(f"/api/hearings/{handle}", json={"findings": "No fine.", "decidedOn": "2026-10-20", "by": "Mallory"})
    assert r.status_code == 403 and "decision" not in hd.load(root)[0]


# --- the place ---------------------------------------------------------------------------------------------------------

def test_the_decision_store_is_p3_by_path_and_its_key_is_never_served(root):
    from jason.web.access import Level, level_of_path, may_see, Viewer

    assert level_of_path("board/decisions.json", root) is Level.P3
    assert level_of_path("board/decisions.key", root) is Level.P4
    assert level_of_path("board/decisions.json.bak", root) is Level.P3
    legacy = store.Decision(id=f"{DAY}--settle-the-doe-claim", meeting=DAY, title="t", motion="m", session=store.EXECUTIVE)
    assert store.handle(root, legacy).startswith(f"{DAY}--held-")                      # a row recorded before opaque ids: keyed
    assert (root / "board" / "decisions.key").is_file()
    director = Viewer("Dana Director", frozenset({"director"}), account="Dana Director")
    assert may_see(director, Level.P4, private=True)[0] is False
    assert level_of_path("board/minutes-2026-10-20.md", root) is Level.P1               # its neighbours keep their places
