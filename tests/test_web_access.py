"""Who may open a file or a document from the console (jason.web.access): the rule rows for each office and level, each
path's level under data/ (closed when no row places it), ``/api/file`` signed in or not, ``/api/library``'s
confidential rows held back, and the evidence document routes bound to the signed-in account. Made-up roster, tmp
data folders, and fake files only; nothing reaches Google, Keeper, or PayHOA.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest
import webclient

from jason.web.access import (HELD_BACK, NOT_SET_UP, SEE_RULES, SIGN_IN, Level, Viewer, level_of_path, may_see)
from test_approvals import village  # noqa: F401 - fixture
from test_evidence import ADDRESS, _request_folder, _views, web  # noqa: F401 - fixtures

P0, P1, P2, P3, P4 = Level.P0, Level.P1, Level.P2, Level.P3, Level.P4


def _viewer(role: str, *, admin: bool = False) -> Viewer:
    offices = frozenset(r.strip() for r in role.split(",") if r.strip() and r.strip() != "admin")
    return Viewer("Someone", offices, admin, "Someone", "sub")


# --- the rule rows ----------------------------------------------------------------------------------------------------

def test_the_rules_are_rows_one_an_office():
    assert {r.holder for r in SEE_RULES} == {"anyone on the roster", "manager", "president", "vice president",
                                             "director", "secretary", "treasurer"}
    assert all(P4 not in r.open | r.private for r in SEE_RULES)                          # P4 is never served


@pytest.mark.parametrize("role", ["manager", "president", "vice president", "director", "secretary", "treasurer"])
def test_every_office_opens_p0_to_p2(role):
    for level in (P0, P1, P2):
        assert may_see(_viewer(role), level) == (True, "")


@pytest.mark.parametrize("role, private_p3", [("manager", True), ("president", True), ("vice president", True),
                                              ("director", True), ("secretary", True), ("treasurer", False)])
def test_p3_only_in_the_private_view_and_never_for_the_treasurer_alone(role, private_p3):
    ok, why = may_see(_viewer(role), P3)
    assert not ok and "only in the private view" in why if private_p3 else not ok
    assert may_see(_viewer(role), P3, private=True)[0] is private_p3


def test_the_treasurer_says_why():
    assert may_see(_viewer("treasurer"), P3, private=True) == (
        False, "The treasurer's office doesn't open executive-session and other restricted material (P3).")


def test_a_person_holding_two_offices_gets_the_union():
    assert may_see(_viewer("secretary, treasurer"), P3, private=True) == (True, "")
    assert may_see(_viewer("treasurer"), P3, private=True)[0] is False


def test_an_admin_with_no_office_opens_p0_and_p1_only():
    admin = _viewer("admin", admin=True)
    assert may_see(admin, P1) == (True, "")
    ok, why = may_see(admin, P2)
    assert not ok and why == ("An admin with no office or manager role doesn't open contact details and members' "
                              "submissions (P2).")
    assert may_see(admin, P3, private=True)[0] is False


def test_p4_is_never_served():
    assert may_see(_viewer("manager"), P4, private=True) == (False, "Secrets (P4) are never served.")


# --- each path's level -------------------------------------------------------------------------------------------------

def _library(root: Path, rows) -> None:
    from jason.tasks.library import SCHEMA

    db = root / "library" / "library.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(SCHEMA)
        for doc_id, path, confidential, sha in rows:
            conn.execute("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, "
                         "confidential, evidence, confidence, classified_at, sha256) VALUES "
                         "(?, 'payhoa', ?, ?, 'minutes', '', 'minutes', 'name', '2026-01', ?, '', 1.0, '', ?)",
                         (doc_id, path, Path(path).name, int(confidential), sha))
    conn.close()


@pytest.fixture
def data(tmp_path):
    """A made-up data folder: library rows (one confidential, one an open copy of a confidential file), Zoom meetings
    (an executive session, a confidential hearing, an open board meeting), and a Drive file the holdings flag."""
    _library(tmp_path, [("lib-open", "Minutes/open.pdf", False, "aaa"), ("lib-conf", "Confidential/conf.pdf", True, "bbb"),
                        ("lib-copy", "Email/copy-of-conf.pdf", False, "bbb"), ("lib-doc", "Board/flagged.pdf", True, "ccc")])
    zoom = tmp_path / "zoom"
    zoom.mkdir()
    (zoom / "meetings.json").write_text(json.dumps({"meetings": [
        {"folder": "meetings/2026-09-01-exec", "kind": "executive session", "confidential": False},
        {"folder": "meetings/2026-09-02-hear", "kind": "hearing", "confidential": True},
        {"folder": "meetings/2026-09-03-open", "kind": "board meeting", "confidential": False}]}), encoding="utf-8")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "holdings.json").write_text(json.dumps({"rows": [
        {"id": "d1", "confidential": True, "elsewhere": [{"channel": "Gmail", "where": "governing/secret.md"}]},
        {"id": "d2", "confidential": False, "elsewhere": [{"channel": "Gmail", "where": "governing/ccrs.md"}]}]}),
        encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("rel, level", [
    ("spec/mystique.json", P3), ("cases/sample-24cv000123/complaint.pdf", P3), ("access/admins.json", P3),
    ("legal/x.pdf", P3),
    ("library/files/Minutes/open.pdf", P0), ("library/files/Confidential/conf.pdf", P3),
    ("library/files/Email/copy-of-conf.pdf", P3),                   # an open copy of a confidential file
    ("library/files/Unknown/new.pdf", P2),                          # not in the library's index: closed
    ("library/text/lib-open.txt", P0), ("library/text/lib-conf.txt", P3),
    ("zoom/meetings/2026-09-01-exec/audio.m4a", P3), ("zoom/meetings/2026-09-02-hear/transcript.txt", P3),
    ("zoom/meetings/2026-09-03-open/audio.m4a", P1), ("zoom/meetings/2026-01-01-unknown/audio.m4a", P2),
    ("payhoa-files/requests/620/lease.pdf", P2), ("forms/abc123/responses.json", P2), ("gmail/files/a.pdf", P2),
    ("mail/106090/scan.pdf", P2), ("mailroom/previews/letter.pdf", P2),
    ("photos/a.png", P1), ("drafts/notice.md", P1), ("board/minutes-draft-2026-09-15.md", P1),
    ("authorities/CIV/4041.md", P0), ("reader/decl/index.html", P0), ("artifacts/site-docs/page.pdf", P0),
    ("governing/ccrs.md", P0), ("governing/secret.md", P3),        # the holdings flag it
    ("payhoa-files/documents/Minutes/open.pdf", P0), ("payhoa-files/documents/Board/flagged.pdf", P3),
    ("board/agenda-2026-10-20.md", P2), ("somewhere-new/file.pdf", P2), ("loose.txt", P2),   # unplaced: closed
    ("../outside.txt", P4), ("photos/../spec/x.json", P3),
])
def test_level_of_path(data, rel, level):
    assert level_of_path(rel, data) is level


def test_a_library_that_cannot_be_read_is_closed(tmp_path):
    (tmp_path / "library").mkdir()
    (tmp_path / "library" / "library.db").write_bytes(b"not a database")
    assert level_of_path("library/files/x.pdf", tmp_path) is P2
    assert level_of_path("payhoa-files/documents/x.pdf", tmp_path) is P2


# --- /api/file ---------------------------------------------------------------------------------------------------------

def _files(data: Path) -> None:
    for rel, body in (("photos/a.png", b"\x89PNG\r\n\x1a\n"), ("library/files/Confidential/conf.pdf", b"%PDF-1.4\n"),
                      ("library/files/Minutes/open.pdf", b"%PDF-1.4\n"), ("mail/106090/scan.pdf", b"%PDF-1.4\n")):
        (data / rel).parent.mkdir(parents=True, exist_ok=True)
        (data / rel).write_bytes(body)


@pytest.fixture
def files(data, monkeypatch):
    _files(data)
    fake = type(sys)("jason.mcp.county")
    fake._data_dir = lambda _: data
    monkeypatch.setitem(sys.modules, "jason.mcp.county", fake)
    return data


def _app(tmp_path, **kw):
    from jason.web.app import create_app

    dist = tmp_path / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "index.html").write_text("<!doctype html><html><head></head><body></body></html>", encoding="utf-8")
    loaders = kw.pop("loaders", {})
    return create_app(dist, loaders, approvals_live=None, sign_in=kw.pop("sign_in", webclient.roster_sign_in()), **kw)


def _served(data: Path) -> list[dict]:
    log = data / "access" / "served.jsonl"
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []


def test_a_file_needs_a_sign_in_json_for_a_fetch(files):
    c = webclient.client(_app(files))
    r = c.get("/api/file?path=photos/a.png", headers={"Accept": "*/*"})
    assert r.status_code == 401 and r.json == {"error": SIGN_IN, "signIn": "/auth/google"}
    assert r.headers["Cache-Control"] == "no-store" and _served(files) == []


@pytest.mark.parametrize("headers", [{"Sec-Fetch-Mode": "navigate"},
                                     {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}])
def test_a_file_needs_a_sign_in_a_page_for_a_navigation(files, headers):
    r = webclient.client(_app(files)).get("/api/file?path=photos/a.png", headers=headers)
    assert r.status_code == 401 and r.mimetype == "text/html"
    page = r.get_data(as_text=True)
    assert SIGN_IN in page and 'href="/auth/google"' in page and "Sign in with Google" in page
    assert "<script" not in page and "http" not in page.replace("http-equiv", "")          # nothing external
    assert r.headers["Content-Security-Policy"].startswith("default-src 'none'")


def test_without_sign_in_set_up_nothing_opens(files):
    c = webclient.sign_in(webclient.client(_app(files, sign_in=webclient.roster_sign_in(configured=False))))
    r = c.get("/api/file?path=photos/a.png")
    assert r.status_code == 401 and r.json["error"] == NOT_SET_UP


def test_a_file_is_served_signed_in_and_logged(files):
    c = webclient.sign_in(webclient.client(_app(files)), "Pat Example")
    r = c.get("/api/file?path=photos/a.png")
    assert r.status_code == 200 and r.data.startswith(b"\x89PNG")
    assert r.headers["Content-Security-Policy"] == "sandbox" and r.headers["Cache-Control"] == "no-store"
    [line] = _served(files)
    assert {k: line[k] for k in ("by", "path", "level", "private")} == {
        "by": "Pat Example", "path": "photos/a.png", "level": "P1", "private": False}
    assert "as" not in line and "reason" not in line
    assert c.get("/api/file?path=nothing.png").status_code == 404 and c.get("/api/file?path=../x.png").status_code == 404


def test_an_office_that_does_not_open_the_level_gets_403_with_the_reason(files):
    c = webclient.sign_in(webclient.client(_app(files)), "Ada Admin")
    r = c.get("/api/file?path=mail/106090/scan.pdf")
    assert r.status_code == 403 and "An admin with no office or manager role doesn't open" in r.json["error"]
    assert c.get("/api/file?path=photos/a.png").status_code == 200                      # P1: anyone on the roster
    t = webclient.sign_in(webclient.client(_app(files)), "Pat Example")
    r = t.get("/api/file?path=library/files/Confidential/conf.pdf&private=1&reason=board+review")
    assert r.status_code == 403 and r.json["error"] == (
        "The treasurer's office doesn't open executive-session and other restricted material (P3).")
    assert [x["by"] for x in _served(files)] == ["Ada Admin"]                            # refusals are not served


def test_a_confidential_library_file_needs_the_private_view_and_a_reason(files):
    c = webclient.sign_in(webclient.client(_app(files)), "Dana Director")
    url = "/api/file?path=library/files/Confidential/conf.pdf"
    plain = c.get(url)
    assert plain.status_code == 403 and "only in the private view" in plain.json["error"]
    assert c.get(url + "&private=1").status_code == 403                                  # no reason: not the private view
    assert c.get(url + "&private=1&reason=+").status_code == 403
    ok = c.get(url + "&private=1&reason=executive+session+item+3")
    assert ok.status_code == 200 and ok.data.startswith(b"%PDF")
    [line] = _served(files)
    assert line["level"] == "P3" and line["private"] is True and line["reason"] == "executive session item 3"
    assert c.get("/api/file?path=library/files/Minutes/open.pdf").status_code == 200    # the open one: P0


def test_an_admin_viewing_as_a_director_is_judged_as_the_director_and_both_are_logged(files):
    c = webclient.sign_in(webclient.client(_app(files, sign_in=webclient.roster_sign_in(dev=True))), "Ada Admin")
    assert c.get("/api/file?path=mail/106090/scan.pdf").status_code == 403              # as herself
    with c.session_transaction() as s:
        s["acting"] = {"name": "Dana Director", "role": "director"}
    assert c.get("/api/file?path=mail/106090/scan.pdf").status_code == 200
    line = _served(files)[-1]
    assert line["by"] == "Ada Admin" and line["as"] == "Dana Director" and line["level"] == "P2"
    with c.session_transaction() as s:
        s["acting"] = {"name": "", "role": "treasurer"}
    r = c.get("/api/file?path=library/files/Confidential/conf.pdf&private=1&reason=check")
    assert r.status_code == 403 and r.json["error"].startswith("The treasurer's office doesn't open")


def test_a_person_taken_off_the_roster_is_signed_out(files):
    rows = [r for r in webclient.ROSTER if r[0] != "Pat Example"]
    c = webclient.client(_app(files, sign_in=webclient.roster_sign_in(rows)))
    webclient.sign_in(c, "Pat Example")
    r = c.get("/api/file?path=photos/a.png")
    assert r.status_code == 401 and "no longer on the roster" in r.json["error"]
    assert c.get("/api/session").json["signedIn"] is None


# --- /api/library?confidential=1 --------------------------------------------------------------------------------------

def test_the_librarys_confidential_rows_are_held_back_without_the_private_view(data, monkeypatch):
    from jason.web.sources import library

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: data)
    app = _app(data, loaders={"library": library})
    anyone = webclient.client(app)
    r = anyone.get("/api/library?confidential=1")
    assert r.status_code == 200
    assert {row["path"] for row in r.json["rows"]} == {"Minutes/open.pdf"}
    assert r.json["heldBack"] == 2 and r.json["note"] == HELD_BACK.format(n=2) == (
        "2 held back (confidential); open the private view to see them.")
    assert r.json["heldBackWhy"] == SIGN_IN
    treasurer = webclient.sign_in(webclient.client(app), "Pat Example").get("/api/library?confidential=1&reason=x")
    assert treasurer.json["heldBack"] == 2 and "treasurer" in treasurer.json["heldBackWhy"]
    manager = webclient.sign_in(webclient.client(app), "A Manager")
    assert manager.get("/api/library?confidential=1").json["heldBack"] == 2               # no reason given
    shown = manager.get("/api/library?confidential=1&reason=records+request")
    assert "heldBack" not in shown.json and len(shown.json["rows"]) == 3
    assert _served(data)[-1]["path"] == "api/library?confidential=1" and _served(data)[-1]["reason"] == "records request"
    assert anyone.get("/api/library").json["heldBackConfidential"] == 2                 # the plain listing, unchanged


# --- the evidence document routes -------------------------------------------------------------------------------------

def test_a_view_needs_a_sign_in_whatever_the_body_says(web):
    _request_folder(web.data_dir)
    r = webclient.client(web.app).post("/api/evidence/view", json={"address": ADDRESS, "document": "submission",
                                                                    "by": "A Manager"})
    assert r.status_code == 401 and r.json["signIn"] == "/auth/google" and _views(web.data_dir) == []


def test_the_view_goes_under_the_signed_in_name_not_the_bodys(web):
    _request_folder(web.data_dir)
    r = web.c.post("/api/evidence/view", json={"address": ADDRESS, "document": "submission", "by": "a manager"})
    assert r.status_code == 200 and _views(web.data_dir)[-1]["by"] == "A Manager"
    assert r.json["caveats"][0] == "Unmasked: shown because A Manager asked; this view is logged."
    other = web.c.post("/api/evidence/view", json={"address": ADDRESS, "document": "submission", "by": "Pat Example"})
    assert other.status_code == 403 and len(_views(web.data_dir)) == 1                  # never another's name
    line = _served(web.data_dir / "letters")[-1]
    assert (line["by"], line["address"], line["level"], line["document"]) == ("A Manager", ADDRESS, "P2", "submission")


def test_an_admin_with_no_office_does_not_view_a_request(web):
    _request_folder(web.data_dir)
    admin = webclient.sign_in(webclient.client(web.app), "Ada Admin")
    r = admin.post("/api/evidence/view", json={"address": ADDRESS, "document": "submission"})
    assert r.status_code == 403 and "admin with no office" in r.json["error"] and _views(web.data_dir) == []
    assert admin.post("/api/evidence/refresh", json={"address": ADDRESS}).status_code == 403


def test_a_document_link_is_bound_to_the_sign_in_that_opened_it(web):
    _request_folder(web.data_dir)
    r = web.c.post("/api/evidence/view", json={"address": ADDRESS, "document": "1002_plan.pdf"})
    assert r.status_code == 200 and r.json["url"]
    url = r.json["url"]
    assert web.c.get(url).status_code == 200
    assert webclient.sign_in(web.app.test_client(), "A Manager").get(url).status_code == 200   # same account, a frame
    other = webclient.sign_in(web.app.test_client(), "Dana Director").get(url)
    assert other.status_code == 403 and "another sign-in" in other.json["error"]
    stolen = webclient.sign_in(web.app.test_client(), "A Manager", sub="another-google-account").get(url)
    assert stolen.status_code == 403
    assert web.app.test_client().get(url).status_code == 401                            # no one signed in
