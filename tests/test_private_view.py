"""The private view (jason.web.access): a time-limited, logged window in which a signed-in person whose office opens P3
sees restricted material. Opening, closing, and expiry with their log lines; who is refused; the reason's rules; what
the window changes (a P3 file, a confidential listing, the evidence's confidential documents, an executive item's
notes, a restricted citation); a window bound to its sign-in; and ``/api/session``'s ``private``. Made-up roster, tmp
data folders, and fake files only; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import webclient

from jason.web import access
from test_approvals import village  # noqa: F401 - fixture
from test_evidence import PDF, web  # noqa: F401 - fixtures
from test_web_access import _app, _served, data, files  # noqa: F401 - fixtures

FILE = "/api/file?path=library/files/Confidential/conf.pdf"
START = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(monkeypatch):
    """The private view's clock, set by the test: ``clock.at`` moves it."""
    class Clock:
        at = START

    c = Clock()
    monkeypatch.setattr(access, "now", lambda: c.at)
    return c


def _log(root: Path) -> list[dict]:
    file = root / "access" / "private.jsonl"
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()] if file.is_file() else []


def _open(c, reason="executive session prep", minutes=None):
    body = {"reason": reason} if minutes is None else {"reason": reason, "minutes": minutes}
    return c.post("/api/private", json=body)


# --- opening, closing, expiry ------------------------------------------------------------------------------------------

def test_open_close_and_the_log(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    r = _open(c)
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    p = r.json["private"]
    assert p["open"] is True and p["reason"] == "executive session prep" and p["mayOpen"] is True
    assert p["until"] == (START + timedelta(minutes=30)).isoformat() and len(p["id"]) == 8     # 30 by default
    [opened] = _log(files)
    assert opened == {"at": START.isoformat(), "event": "opened", "id": p["id"], "by": "Dana Director",
                      "reason": "executive session prep", "minutes": 30}
    shut = c.delete("/api/private")
    assert shut.status_code == 200 and shut.json["private"]["open"] is False
    assert [(x["event"], x["id"], x["by"], x["reason"]) for x in _log(files)][1] == (
        "closed", p["id"], "Dana Director", "executive session prep")
    assert c.get(FILE).status_code == 403


@pytest.mark.parametrize("minutes", [15, 30, 60])
def test_the_window_lasts_the_minutes_chosen(files, clock, minutes):
    c = webclient.sign_in(webclient.client(_app(files)), "A Manager")
    assert _open(c, minutes=minutes).json["private"]["until"] == (START + timedelta(minutes=minutes)).isoformat()
    assert _log(files)[-1]["minutes"] == minutes


def test_it_expires_and_the_next_request_logs_it(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    wid = _open(c, minutes=15).json["private"]["id"]
    clock.at = START + timedelta(minutes=14, seconds=59)
    assert c.get(FILE).status_code == 200
    clock.at = START + timedelta(minutes=15)
    r = c.get(FILE)
    assert r.status_code == 403 and "only in the private view" in r.json["error"]
    assert [(x["event"], x["id"]) for x in _log(files)] == [("opened", wid), ("expired", wid)]
    assert c.get("/api/session").json["private"]["open"] is False
    assert len(_log(files)) == 2                                                             # logged once


def test_opening_again_closes_the_first(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "A Manager")
    first = _open(c, "budget review").json["private"]["id"]
    second = _open(c, "records request").json["private"]["id"]
    assert first != second
    assert [(x["event"], x["id"]) for x in _log(files)] == [("opened", first), ("closed", first), ("opened", second)]


# --- who is refused ------------------------------------------------------------------------------------------------------

def test_the_treasurer_alone_is_refused_with_the_reason(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Pat Example")
    r = _open(c)
    assert r.status_code == 403 and r.json["error"] == (
        "The treasurer's office doesn't open executive-session and other restricted material (P3).")
    assert _log(files) == []
    s = c.get("/api/session").json["private"]
    assert s["mayOpen"] is False and s["why"] == r.json["error"] and s["open"] is False
    tess = webclient.sign_in(webclient.client(_app(files)), "Tess Two")                  # secretary too: may
    assert _open(tess).status_code == 200


def test_an_admin_with_no_office_is_refused(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Ada Admin")
    r = _open(c)
    assert r.status_code == 403 and "An admin with no office or manager role doesn't" in r.json["error"]
    assert c.get("/api/session").json["private"]["mayOpen"] is False and _log(files) == []


def test_viewing_as_someone_else_is_refused(files, clock):
    c = webclient.sign_in(webclient.client(_app(files, sign_in=webclient.roster_sign_in(dev=True))), "Ada Admin")
    with c.session_transaction() as s:
        s["acting"] = {"name": "Dana Director", "role": "director"}
    r = _open(c)
    assert r.status_code == 403 and "admin view" in r.json["error"] and _log(files) == []
    s = c.get("/api/session").json["private"]
    assert s["mayOpen"] is False and "admin view" in s["why"]


def test_signed_out_is_401_and_the_session_says_sign_in(files, clock):
    c = webclient.client(_app(files))
    r = _open(c)
    assert r.status_code == 401 and r.json["signIn"] == "/auth/google"
    s = c.get("/api/session").json["private"]
    assert s == {"open": False, "until": "", "reason": "", "id": "", "mayOpen": False,
                 "why": "Sign in with Google to open the private view.", "minutes": [15, 30, 60], "default": 30}


def test_it_needs_the_token_in_its_header(files, clock):
    app = _app(files)
    c = webclient.sign_in(webclient.client(app, token=False), "Dana Director")
    c.set_cookie("jason_token", app.config["JASON_TOKEN"])                              # the cookie alone: not enough
    assert _open(c).status_code == 403 and _log(files) == []


@pytest.mark.parametrize("reason, why", [
    ("", "Say why"), ("   ", "Say why"), (None, "Say why"),
    ("the PIN is 4321", "looks like a secret"), ("token abcDEF1234567890xyzQ", "looks like a secret"),
    ("x" * 121, "120 characters at most"),
])
def test_a_reason_is_required_short_and_never_a_secret(files, clock, reason, why):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    r = c.post("/api/private", json={"reason": reason})
    assert r.status_code == 400 and why in r.json["error"]
    assert _log(files) == [] and c.get(FILE).status_code == 403


@pytest.mark.parametrize("minutes", [0, 5, 45, 90, "thirty", True, 30.5])
def test_minutes_are_15_30_or_60(files, clock, minutes):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    r = _open(c, minutes=minutes)
    assert r.status_code == 400 and "15, 30, or 60" in r.json["error"] and _log(files) == []


def test_contact_details_in_a_reason_are_masked_in_the_log(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    assert _open(c, "call back ana@example.com").status_code == 200
    assert "ana@example.com" not in json.dumps(_log(files))


# --- what the window opens ----------------------------------------------------------------------------------------------

def test_a_p3_file_403_before_200_during_with_the_window_in_the_log(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Sam Secretary")
    assert c.get(FILE).status_code == 403
    wid = _open(c, "minutes of the executive session").json["private"]["id"]
    ok = c.get(FILE)
    assert ok.status_code == 200 and ok.data.startswith(b"%PDF")
    [line] = _served(files)
    assert (line["level"], line["private"], line["privateId"], line["reason"]) == (
        "P3", True, wid, "minutes of the executive session")


def test_the_window_is_not_inherited_by_another_sign_in(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    wid = _open(c).json["private"]["id"]
    webclient.sign_in(c, "Dana Director", sub="another-google-account")                # the same name, another sub
    assert c.get(FILE).status_code == 403
    assert c.get("/api/session").json["private"]["open"] is False
    assert (_log(files)[-1]["event"], _log(files)[-1]["id"], _log(files)[-1]["why"]) == ("closed", wid, "another sign-in")
    webclient.sign_in(c, "Dana Director")                                              # back: it stays closed
    assert c.get(FILE).status_code == 403


def test_signing_out_closes_it(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    wid = _open(c).json["private"]["id"]
    assert c.post("/auth/signout").status_code == 200
    assert (_log(files)[-1]["event"], _log(files)[-1]["id"], _log(files)[-1]["why"]) == ("closed", wid, "signed out")
    webclient.sign_in(c, "Dana Director")
    assert c.get(FILE).status_code == 403


def test_the_window_is_not_open_while_an_admin_views_as_someone_and_counts_again_after(files, clock):
    rows = webclient.ROSTER + (("Olive Officer", "director", "olive@example.org", True),)   # an admin with an office
    c = webclient.client(_app(files, sign_in=webclient.roster_sign_in(rows, dev=True)))
    webclient.sign_in(c, "Olive Officer", rows=rows)
    assert _open(c).status_code == 200
    with c.session_transaction() as s:
        s["acting"] = {"name": "Dana Director", "role": "director"}
    assert c.get("/api/session").json["private"]["open"] is False
    assert c.get(FILE).status_code == 403                                                # not for a view as Dana
    with c.session_transaction() as s:
        s.pop("acting")
    assert c.get(FILE).status_code == 200


def test_the_session_reports_the_window(files, clock):
    c = webclient.sign_in(webclient.client(_app(files)), "A Manager")
    before = c.get("/api/session").json["private"]
    assert before == {"open": False, "until": "", "reason": "", "id": "", "mayOpen": True, "why": "",
                      "minutes": [15, 30, 60], "default": 30}
    wid = _open(c, "records request", 60).json["private"]["id"]
    during = c.get("/api/session")
    assert during.headers["Cache-Control"] == "no-store"
    assert {k: during.json["private"][k] for k in ("open", "id", "reason", "until")} == {
        "open": True, "id": wid, "reason": "records request", "until": (START + timedelta(hours=1)).isoformat()}
    assert "sub" not in during.json["private"]                                           # the binding stays inside


def test_the_library_is_held_back_before_and_shown_during(data, clock, monkeypatch):
    from jason.web.sources import library

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: data)
    c = webclient.sign_in(webclient.client(_app(data, loaders={"library": library})), "Lee President")
    held = c.get("/api/library?confidential=1").json
    assert held["heldBack"] == 2 and len(held["rows"]) == 1
    wid = _open(c, "records request").json["private"]["id"]
    shown = c.get("/api/library?confidential=1").json
    assert "heldBack" not in shown and len(shown["rows"]) == 3
    line = _served(data)[-1]
    assert (line["path"], line["privateId"], line["reason"]) == ("api/library?confidential=1", wid, "records request")


# --- the evidence ---------------------------------------------------------------------------------------------------------

@pytest.fixture
def confidential(web, monkeypatch):
    """A citation whose links name an open library file and a confidential one, and executive and open board items."""
    from jason.community.board_items import BoardItem, ItemCategory, Session
    from jason.tasks.board_items import save
    from jason.tasks.library import SCHEMA

    root = web.data_dir
    (root / "library" / "files" / "Governing").mkdir(parents=True)
    (root / "library" / "files" / "Governing" / "Declaration.pdf").write_bytes(PDF)
    (root / "library" / "files" / "Governing" / "Private.pdf").write_bytes(PDF)
    with sqlite3.connect(root / "library" / "library.db") as conn:
        conn.execute(SCHEMA)
        conn.executemany("INSERT INTO documents (id, path, name, confidential) VALUES (?, ?, ?, ?)",
                         [("d1", "Governing/Declaration.pdf", "Declaration.pdf", 0),
                          ("d2", "Governing/Private.pdf", "Private.pdf", 1)])
    got = {"found": True, "citation": "Declaration § 6.2", "text": "6.2 Example words.", "inForce": "the base",
           "links": [{"what": "the library file", "library": "Governing/Declaration.pdf"},
                     {"what": "a restricted file", "library": "Governing/Private.pdf"}]}
    web.asked = []

    def resolve(expression, **kw):
        web.asked.append(kw.get("private", False))
        return dict(got)
    monkeypatch.setattr("jason.tasks.cite.resolve", resolve)
    save(root, [BoardItem("example-plan", "A payment plan", "Owner X owes.", "decide", ItemCategory.COLLECTIONS,
                          session=Session.EXECUTIVE, notes="Offered twelve months.")])
    return web


def _documents(c) -> list[dict]:
    return c.get("/api/evidence?address=decl%236.2").json["documents"]


def test_evidence_lists_the_confidential_documents_only_in_the_window(confidential, clock):
    c = confidential.c
    assert [d["id"] for d in _documents(c)] == ["section", "library:d1"]
    assert confidential.asked == [False]                                                  # no restricted book
    assert c.post("/api/evidence/view", json={"address": "decl#6.2", "document": "library:d2"}).status_code == 404
    _open(c, "executive session prep")
    docs = _documents(c)
    assert [d["id"] for d in docs] == ["section", "library:d1", "library:d2"]
    assert {k: docs[2][k] for k in ("level", "note")} == {"level": "P3", "note": "Confidential: shown in the private view"}
    assert "level" not in docs[1]
    assert confidential.asked[-1] is True                                                 # cite.resolve(private=True)


def test_a_confidential_document_is_viewed_in_the_window_and_logged_p3(confidential, clock):
    c = confidential.c
    wid = _open(c, "executive session prep").json["private"]["id"]
    r = c.post("/api/evidence/view", json={"address": "decl#6.2", "document": "library:d2"})
    assert r.status_code == 200 and r.json["level"] == "P3" and r.json["url"]
    line = _served(confidential.data_dir / "letters")[-1]
    assert (line["level"], line["document"], line["privateId"]) == ("P3", "library:d2", wid)
    assert c.get(r.json["url"]).status_code == 200
    c.delete("/api/private")
    assert c.get(r.json["url"]).status_code == 403                                       # the link needs the window too


def test_the_treasurer_does_not_see_confidential_evidence(confidential, clock):
    t = webclient.sign_in(webclient.client(confidential.app), "Pat Example")
    assert _open(t).status_code == 403
    assert [d["id"] for d in _documents(t)] == ["section", "library:d1"]


def test_an_executive_items_summary_and_notes_come_back_in_the_window(confidential, clock):
    c = confidential.c

    def fields():
        got = c.get("/api/evidence?address=board-item:example-plan").json
        src = got["sources"][0]
        return {f["name"]: f["value"] for f in src["fields"]}, src["note"], got

    held, note, got = fields()
    assert "Summary" not in held and "Notes" not in held and "held back" in note
    # Labeled by its 4935 subject (none planned here), never its title; no line in the access log.
    assert got["label"] == "Board item: An executive-session matter" and got["held"] is True and "level" not in got
    assert "A payment plan" not in json.dumps(got) and held["Title"] == "An executive-session matter"
    assert _served(confidential.data_dir / "letters") == []
    _open(c)
    shown, note, got = fields()
    assert shown["Summary"] == "Owner X owes." and shown["Notes"] == "Offered twelve months."
    assert note == "Executive session: shown in the private view."
    assert got["label"] == "Board item example-plan: A payment plan" and got["level"] == "P3"
    line = _served(confidential.data_dir / "letters")[-1]
    assert (line["address"], line["level"], line["private"]) == ("board-item:example-plan", "P3", True)
