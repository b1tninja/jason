"""Choosing files from a person's own Google Drive with the Picker's redirect form (docs/google-picker.md): the start route, the
callback, the task that reads each picked file once, and what must never happen. Nothing here reaches Google: the token endpoint
is a fake function and the Drive client is the real ``GoogleDrive`` over an ``httpx.MockTransport`` that records every request.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import webclient

from jason.google.drive import GoogleDrive
from jason.tasks import drive_pick
from jason.web import pick
from jason.web.app import create_app

TOKEN = "ya29.FAKE-ACCESS-TOKEN-for-tests"
CODE = "4/0FAKE-code-for-tests"
SECRET = "GOCSPX-not-a-real-secret"
FOLDER = "application/vnd.google-apps.folder"
DOC = "application/vnd.google-apps.document"


def _pdf(pages: int = 1, tag: str = "") -> bytes:
    import pymupdf

    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"page {i} {tag}")
    return doc.tobytes()


class FakeDriveApi:
    """Google's Drive as an HTTP stub: files by id, every request recorded."""

    def __init__(self):
        self.files: dict[str, dict] = {}
        self.bodies: dict[str, bytes] = {}
        self.requests: list[httpx.Request] = []

    def add(self, fid: str, *, name="Minutes.pdf", mime="application/pdf", data: bytes | None = None, size=None, **meta):
        data = _pdf(1, fid) if data is None and mime == "application/pdf" else (data or b"")
        self.files[fid] = {"id": fid, "name": name, "mimeType": mime, "size": str(len(data) if size is None else size),
                           "modifiedTime": "2026-10-01T10:00:00Z", "capabilities": {"canDownload": True}, **meta}
        self.bodies[fid] = data
        return fid

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        fid = request.url.path.rsplit("/", 1)[-1]
        if request.method != "GET" or fid not in self.files:
            status = 404 if request.method == "GET" else 405
            return httpx.Response(status, json={"error": {"code": status, "message": f"file {fid} not found",
                                                          "errors": [{"reason": "notFound"}]}})
        if request.url.params.get("alt") == "media":
            return httpx.Response(200, content=self.bodies[fid])
        return httpx.Response(200, json=self.files[fid])

    def client(self, token: str) -> GoogleDrive:
        return GoogleDrive(token, http=httpx.Client(transport=httpx.MockTransport(self.handler)))


class World:
    pass


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d=None: tmp_path)
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JASON_LIMIT_PICK_ENABLED", "on")
    w = World()
    w.root, w.api, w.exchanged = tmp_path, FakeDriveApi(), []

    def exchange(client, code, redirect_uri):
        w.exchanged.append((client.client_id, code, redirect_uri))
        if code != CODE:
            raise pick.Refused("Google would not give jason access to the picked files (invalid_grant). Nothing was read.")
        return TOKEN

    deps = pick.PickDeps(exchange=exchange, drive=w.api.client, root=lambda: tmp_path, community=lambda: None)
    dist = tmp_path / "dist"
    dist.mkdir()
    w.app = create_app(dist, {}, approvals_live=None, extra_writes=False, sign_in=webclient.roster_sign_in(), pick_deps=deps)
    w.deps = deps
    w.c = webclient.sign_in(webclient.client(w.app), "A Manager")
    return w


def _start(w, c=None, query="next=%23%2Fsplit&slot=records%2F5200%2Fminutes&purpose=split"):
    c = c or w.c
    r = c.get(f"/auth/google/pick?{query}")
    q = {k: v[0] for k, v in parse_qs(urlsplit(r.headers.get("Location", "")).query).items()}
    return r, q


def _back(w, state, ids, c=None, code=CODE, **extra):
    c = c or w.c
    qs = "&".join([f"state={state}", f"picked_file_ids={','.join(ids)}", f"code={code}"] + [f"{k}={v}" for k, v in extra.items()])
    return c.get(f"/auth/google/pick/callback?{qs}")


def _result(w, r, c=None):
    token = parse_qs(urlsplit(r.headers["Location"]).query)["pick"][0]
    return (c or w.c).post("/api/drive/pick/result", json={"token": token})


def _files(root: Path):
    return [p for p in root.rglob("*") if p.is_file() and "dist" not in p.parts]


# --- the start ------------------------------------------------------------------------------------------------------------

def test_the_start_sends_the_person_to_the_pickers_redirect_form(world):
    r, q = _start(world)
    assert r.status_code == 302 and r.headers["Location"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert q["client_id"] == "cid" and q["scope"] == "https://www.googleapis.com/auth/drive.file"
    assert q["trigger_onepick"] == "true" and q["prompt"] == "consent" and q["response_type"] == "code"
    assert q["access_type"] == "online" and q["redirect_uri"] == "http://localhost/auth/google/pick/callback"
    assert q["allow_multiple"] == "true" and q["mimetypes"] == "application/pdf"
    assert "allow_folder_selection" not in q and "login_hint" not in q and "hd" not in q
    # the state is in the session and on disk only as a hash
    with world.c.session_transaction() as s:
        assert s["pick"]["state"] == q["state"]
    assert q["state"] not in "".join(p.read_text(encoding="utf-8") + p.name for p in _files(world.root))
    assert len(list((world.root / "drive-picks" / "states").glob("*.json"))) == 1


def test_the_start_is_the_boards_and_off_until_a_person_turns_it_on(world, monkeypatch):
    anon = webclient.client(world.app)
    assert anon.get("/auth/google/pick").status_code == 401
    ada = webclient.sign_in(webclient.client(world.app), "Ada Admin")           # an administrator with no office: not the board's
    assert ada.get("/auth/google/pick").status_code == 403
    assert _start(world, query="purpose=nonsense")[0].status_code == 400
    monkeypatch.setenv("JASON_LIMIT_PICK_ENABLED", "off")
    off = world.c.get("/auth/google/pick")
    assert off.status_code == 403 and b"off for this community" in off.data
    assert not (world.root / "drive-picks").exists()


def test_the_start_wants_the_web_client(world, monkeypatch):
    world.app.extensions["jason_sign_in"] = webclient.roster_sign_in(configured=False)
    r = world.c.get("/auth/google/pick")
    assert r.status_code == 401                                  # no sign-in set up, so no one is signed in to pick


# --- a pick, end to end ----------------------------------------------------------------------------------------------------

def test_a_pick_is_read_once_held_and_the_token_goes_nowhere(world, caplog):
    caplog.set_level(logging.DEBUG)
    a = world.api.add("1AbCdEfGhIjKlMnOpQ", name="Private minutes.pdf")
    b = world.api.add("1ZyXwVuTsRqPoNmLkJ", name="Shared drive deed.pdf", driveId="0ASharedDriveId")
    _, q = _start(world)
    back = _back(world, q["state"], [a, b])
    assert back.status_code == 302 and back.headers["Location"].startswith("/?pick=") and back.headers["Location"].endswith("#/split")
    assert world.exchanged == [("cid", CODE, "http://localhost/auth/google/pick/callback")]
    got = _result(world, back)
    assert got.status_code == 200
    rep = got.json["report"]
    assert got.json["purpose"] == "split" and got.json["slot"] == "records/5200/minutes" and got.json["error"] == ""
    assert rep["counts"] == {"held": 2, "already held": 0, "would hold": 0, "refused": 0}
    assert [r["name"] for r in rep["rows"]] == ["Private minutes.pdf", "Shared drive deed.pdf"]
    assert all(len(r["heldId"]) == 64 and r["pages"] == 1 for r in rep["rows"])
    held = drive_pick.held_path(world.root, rep["rows"][0]["heldId"])
    assert held.read_bytes() == world.api.bodies[a]
    note = drive_pick.provenance(world.root, rep["rows"][0]["heldId"])
    assert note["picks"][0]["by"] == "A Manager" and note["picks"][0]["via"] == "picked via Picker"
    assert len(note["picks"][0]["driveIdHash"]) == 16 and a not in json.dumps(note) and "Private minutes" not in json.dumps(note)

    # read once: the second read finds nothing, and so does another person's
    assert _result(world, back).status_code == 404

    # Drive only ever received reads (metadata, then the bytes), with the token, over Google's host
    assert world.api.requests and all(r.method == "GET" and r.url.host == "www.googleapis.com" for r in world.api.requests)
    assert all(r.headers["Authorization"] == f"Bearer {TOKEN}" for r in world.api.requests)
    assert sum(1 for r in world.api.requests if r.url.params.get("alt") == "media") == 2        # each file's bytes once

    # the token, the code and the secret are in no file, log line, history line, session or redirect
    secrets_ = (TOKEN, CODE, SECRET, "FAKE-ACCESS")
    for p in _files(world.root):
        if p.suffix != ".pdf":
            text = p.read_text(encoding="utf-8", errors="replace")
            assert not any(s in text for s in secrets_), p
            assert a not in text and b not in text, p
    history = (world.root / "records" / "history.jsonl").read_text(encoding="utf-8")
    line = json.loads(history.splitlines()[-1])
    assert line["act"] == "drive-pick" and line["picked"] == 2 and line["held"] == 2 and line["by"] == "A Manager"
    assert "Private minutes" not in history and "Shared drive" not in history
    assert not any(s in caplog.text for s in secrets_) and a not in caplog.text
    with world.c.session_transaction() as s:
        assert not any(x in json.dumps(dict(s)) for x in secrets_)
    assert not any(x in back.headers["Location"] for x in secrets_)
    assert "pick" not in dict(world.c.get("/api/session").json["signedIn"] or {})


def test_the_same_bytes_picked_again_are_already_held(world):
    same = _pdf(1, "same")
    a = world.api.add("1AbCdEfGhIjKlMnOpQ", data=same)
    b = world.api.add("1ZyXwVuTsRqPoNmLkJ", data=same)
    _, q = _start(world)
    rep = _result(world, _back(world, q["state"], [a, b])).json["report"]
    assert rep["counts"]["held"] == 1 and rep["counts"]["already held"] == 1
    assert len(list((world.root / "drive-picks" / "held").glob("*.pdf"))) == 1
    note = drive_pick.provenance(world.root, rep["rows"][0]["heldId"])
    assert len(note["picks"]) == 2


def test_each_refusal_is_in_jasons_words_and_keeps_nothing(world, monkeypatch):
    monkeypatch.setenv("JASON_LIMIT_FETCH_MAX_BYTES", str(1024 * 1024))
    monkeypatch.setenv("JASON_LIMIT_SPLIT_MAX_PAGES", "50")
    folder = world.api.add("1FolderFolderFolder", name="Records", mime=FOLDER, size=0)
    doc = world.api.add("1GoogleDocGoogleDoc", name="Notes", mime=DOC, size=0)
    big = world.api.add("1BigBigBigBigBigBig", data=b"%PDF-1.4 x", size=2 * 1024 * 1024)
    many = world.api.add("1ManyPagesManyPages", data=_pdf(51))
    locked = world.api.add("1LockedLockedLocked", capabilities={"canDownload": False})
    fake = world.api.add("1NotReallyAPdfAtAll", data=b"just some text, not a pdf")
    _, q = _start(world)
    rep = _result(world, _back(world, q["state"], [folder, doc, big, many, locked, fake, "1NoSuchFileNoSuchFile", "short"])).json["report"]
    reasons = [r["reason"] for r in rep["rows"]]
    assert reasons == ["folder", "not_pdf", "too_large", "too_many_pages", "not_readable", "not_pdf", "no_access", "bad_id"]
    assert rep["counts"]["refused"] == 8 and rep["counts"]["held"] == 0
    words = {r["reason"]: r["words"] for r in rep["rows"]}
    assert "folder" in words["folder"] and "PDF" in words["not_pdf"] and "1 MB" in words["too_large"]
    assert "51 pages" in words["too_many_pages"] and "downloading off" in words["not_readable"] or "download" in words["not_readable"]
    assert "cannot open that" in words["no_access"] and "1NoSuchFile" not in words["no_access"]
    assert not (world.root / "drive-picks" / "held").exists() or not list((world.root / "drive-picks" / "held").iterdir())
    # the oversize file was refused from its metadata: its bytes were never fetched
    media = [r for r in world.api.requests if r.url.params.get("alt") == "media"]
    assert all(not r.url.path.endswith(big) for r in media)


def test_the_size_cap_refuses_a_file_whose_size_drive_did_not_say(world, monkeypatch):
    monkeypatch.setenv("JASON_LIMIT_FETCH_MAX_BYTES", str(1024 * 1024))
    odd = world.api.add("1OddSizeOddSizeOddSize", data=b"%PDF-1.4\n" + b"0" * (1100 * 1024))
    world.api.files[odd].pop("size")
    _, q = _start(world)
    row = _result(world, _back(world, q["state"], [odd])).json["report"]["rows"][0]
    assert row["reason"] == "too_large" and not list((world.root / "drive-picks").glob("held/*"))


def test_a_dry_run_reads_metadata_only_and_keeps_nothing(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    report = drive_pick.pick([ok, "1NoSuchFileNoSuchFile"], by="A Manager", drive=world.api.client(TOKEN), root=world.root, dry_run=True)
    assert [r.outcome.value for r in report.rows] == ["would hold", "refused"]
    assert all(r.url.params.get("alt") != "media" for r in world.api.requests)
    assert not (world.root / "drive-picks").exists() and not (world.root / "records").exists()


def test_too_many_picks_are_refused_before_any_read(world):
    with pytest.raises(drive_pick.PickRefused, match="at most"):
        drive_pick.pick([f"1AbCdEfGhIjKlMnOp{i:02d}" for i in range(drive_pick.MAX_FILES + 1)], by="A Manager",
                        drive=world.api.client(TOKEN), root=world.root)
    assert world.api.requests == []


def test_jason_never_picks_in_its_own_name(world):
    with pytest.raises(ValueError, match="never writes in its own name"):
        drive_pick.pick(["1AbCdEfGhIjKlMnOpQ"], by="jason", drive=world.api.client(TOKEN), root=world.root)


# --- the state ------------------------------------------------------------------------------------------------------------

def test_a_state_works_once(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    assert _back(world, q["state"], [ok]).headers["Location"].startswith("/?pick=")
    again = _back(world, q["state"], [ok])
    assert again.status_code == 400 and len(world.exchanged) == 1
    # even with the session value put back by a copied cookie, the disk record is spent
    with world.c.session_transaction() as s:
        s["pick"] = {"state": q["state"]}
    replay = _back(world, q["state"], [ok])
    assert replay.status_code == 400 and b"already used" in replay.data and len(world.exchanged) == 1


def test_a_forged_state_or_none_is_refused(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    assert _back(world, "forged-state", [ok]).status_code == 400
    assert world.exchanged == []
    # the real state was popped by the failed attempt's session read, so it cannot be used either
    assert _back(world, q["state"], [ok]).status_code == 400
    fresh = webclient.sign_in(webclient.client(world.app), "A Manager")
    assert _back(world, q["state"], [ok], c=fresh).status_code == 400            # a state with no session behind it
    assert world.exchanged == []


def test_a_state_that_expired_is_refused(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    f = next((world.root / "drive-picks" / "states").glob("*.json"))
    row = json.loads(f.read_text(encoding="utf-8"))
    row["expires"] = time.time() - 1
    f.write_text(json.dumps(row), encoding="utf-8")
    r = _back(world, q["state"], [ok])
    assert r.status_code == 400 and b"took too long" in r.data and world.exchanged == []


def test_a_state_started_by_another_person_is_refused(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    with world.c.session_transaction() as s:
        pending = dict(s["pick"])
    other = webclient.sign_in(webclient.client(world.app), "Pat Example")
    with other.session_transaction() as s:
        s["pick"] = pending
    r = _back(world, q["state"], [ok], c=other)
    assert r.status_code == 400 and b"someone else" in r.data and world.exchanged == []


def test_a_result_is_for_the_person_who_picked(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    back = _back(world, q["state"], [ok])
    other = webclient.sign_in(webclient.client(world.app), "Pat Example")
    assert _result(world, back, c=other).status_code == 404
    token = parse_qs(urlsplit(back.headers["Location"]).query)["pick"][0]
    # the other person's try consumed it (a result is read once, by whoever asks first and is checked after): it is gone
    assert world.c.post("/api/drive/pick/result", json={"token": token}).status_code == 404
    assert world.c.post("/api/drive/pick/result", json={"token": "../../x"}).status_code == 404


# --- what Google may say ---------------------------------------------------------------------------------------------------

def test_a_cancelled_picker_exchanges_nothing(world):
    _, q = _start(world)
    back = world.c.get(f"/auth/google/pick/callback?state={q['state']}&error=access_denied")
    got = _result(world, back).json
    assert "Nothing was picked" in got["error"] and got["report"] is None
    assert world.exchanged == [] and world.api.requests == []


def test_no_files_picked_exchanges_nothing(world):
    _, q = _start(world)
    back = world.c.get(f"/auth/google/pick/callback?state={q['state']}&code={CODE}")
    assert _result(world, back).json["error"] == "Nothing was picked." and world.exchanged == []


def test_google_refusing_the_code_is_said_without_its_text(world):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    got = _result(world, _back(world, q["state"], [ok], code="4/bad")).json
    assert "would not give jason access" in got["error"] and got["report"] is None and world.api.requests == []


def test_the_switch_turned_off_while_the_picker_was_open_stops_the_read(world, monkeypatch):
    ok = world.api.add("1AbCdEfGhIjKlMnOpQ")
    _, q = _start(world)
    monkeypatch.setenv("JASON_LIMIT_PICK_ENABLED", "off")
    got = _result(world, _back(world, q["state"], [ok])).json
    assert "off for this community" in got["error"] and world.exchanged == [] and world.api.requests == []


def test_the_token_exchange_asks_for_nothing_it_keeps(monkeypatch):
    sent = {}

    def post(url, data=None, timeout=None):
        sent.update(url=url, data=data)
        return httpx.Response(200, json={"access_token": TOKEN, "refresh_token": "1//SHOULD-BE-IGNORED", "scope": pick.SCOPE,
                                         "expires_in": 3599}, headers={"content-type": "application/json"})

    monkeypatch.setattr(httpx, "post", post)
    from jason.web.signin import Client

    assert pick.default_exchange(Client("cid", SECRET), CODE, "http://127.0.0.1:8080/auth/google/pick/callback") == TOKEN
    assert sent["url"] == pick.TOKEN_URL and sent["data"]["grant_type"] == "authorization_code" and "code_verifier" not in sent["data"]
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200, json={"access_token": TOKEN, "scope": "openid"},
                                                                       headers={"content-type": "application/json"}))
    with pytest.raises(pick.Refused, match="Drive file permission"):
        pick.default_exchange(Client("cid", SECRET), CODE, "x")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(400, json={"error": "invalid_grant", "error_description": "Bad " + CODE},
                                                                       headers={"content-type": "application/json"}))
    with pytest.raises(pick.Refused) as exc:
        pick.default_exchange(Client("cid", SECRET), CODE, "x")
    assert CODE not in str(exc.value) and SECRET not in str(exc.value)


# --- after the pick -------------------------------------------------------------------------------------------------------

def test_a_held_copy_opens_as_a_split_draft_and_purges(world):
    from jason.tasks import split_session as ss

    ok = world.api.add("1AbCdEfGhIjKlMnOpQ", data=_pdf(3, "open"))
    _, q = _start(world)
    held_id = _result(world, _back(world, q["state"], [ok])).json["report"]["rows"][0]["heldId"]
    out = ss.open_session({"kind": "held", "id": held_id}, by="A Manager", root=world.root, community=None, profile="test",
                          facts=False, suggest=False)
    assert out["ok"] and out["session"]["source"]["pages"] == 3 and out["session"]["source"]["kind"] == "drive"
    with pytest.raises(ValueError, match="No held copy"):
        ss.open_session({"kind": "held", "id": "0" * 64}, by="A Manager", root=world.root, community=None, profile="test")
    with pytest.raises(ValueError, match="No held copy"):
        ss.open_session({"kind": "held", "id": "../../etc/passwd"}, by="A Manager", root=world.root, community=None, profile="test")
    dry = drive_pick.purge(world.root)
    assert dry == {"dryRun": True, "files": 2, "bytes": dry["bytes"]} and drive_pick.held_path(world.root, held_id)
    assert drive_pick.purge(world.root, dry_run=False)["files"] == 2 and drive_pick.held_path(world.root, held_id) is None


def test_the_limits_are_registered_with_their_words():
    from jason import limits

    on, mins = limits.limit("pick.enabled"), limits.limit("pick.state_minutes")
    assert on.default is False and on.unit == "switch" and (mins.default, mins.minimum, mins.maximum) == (10, 1, 30)
    assert on.why and on.when_hit and mins.why and mins.when_hit
