"""The splitter and a confidential file (docs/pdf-splitter.md, section 8, "Confidential files"): no page text before the private view,
a flag that fails closed, pictures a browser must ask about, a duplicate check that never switches off silently, and logs and cache
paths with no file names. Made-up PDFs and a made-up library; no service."""

import argparse
import base64
import json
import logging
import re
import sqlite3

import pytest

import webclient
from jason.community import split_gold
from jason.tasks import record_slots as rs
from jason.tasks import split_mask
from jason.tasks import split_session as ss
from jason.tasks import split_thumbs as th
from jason.tasks.library import SCHEMA

BY = "A Manager"
TITLE = "SECRETTITLE"
KIND = "secretkind"
LIB_NAME = "Held Statement.pdf"


@pytest.fixture
def world(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "library" / "files").mkdir(parents=True)
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda given=None: root)
    monkeypatch.setattr(rs, "_profile", lambda profile, community=None: profile or "example")
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(split_gold.numbered().pdf)
    (root / "library" / "files" / LIB_NAME).write_bytes(pdf.read_bytes())
    return type("W", (), {"root": root, "tmp": tmp_path, "pdf": pdf, "db": root / "library" / "library.db"})()


def _library(world, confidential):
    with sqlite3.connect(world.db) as conn:
        conn.execute(SCHEMA)
        conn.execute("INSERT OR REPLACE INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence, sha256)"
                     " VALUES ('9001','payhoa',?,?,'bank_statement','financial','enhanced','NAME','2099-06',?,'','')",
                     (LIB_NAME, LIB_NAME, 1 if confidential else 0))


def _flag(world, confidential):
    with sqlite3.connect(world.db) as conn:
        conn.execute("UPDATE documents SET confidential = ? WHERE id = '9001'", (1 if confidential else 0,))


def _open(world, confidential):
    _library(world, confidential)
    session = ss.open_session({"kind": "library", "id": "9001"}, by=BY, root=world.root)["session"]
    sid = session["id"]
    ss.act(sid, "label", {"page": 1, "field": "title", "value": TITLE}, by=BY, root=world.root)
    ss.act(sid, "label", {"page": 1, "field": "kind", "value": KIND}, by=BY, root=world.root)
    return sid


def _break(world):
    world.db.write_bytes(b"this is not a database" * 100)          # a library that cannot be read


def _app(world):
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    return create_app(world.tmp, default_loaders(), sign_in=webclient.roster_sign_in(required=False))


def _signed(world):
    c = webclient.client(_app(world))
    webclient.sign_in(c, BY)
    return c


def _needles(world, sid):
    """Every word the pages' text gave: the facts' header, footer, title, date, the suggestions' reasons, and the labels."""
    s = ss.load(world.root, sid)
    found = {TITLE, KIND}
    for f in ss.read_facts(world.root, s.source.sha256):
        found |= {f.header, f.footer, f.title, f.date}
    for g in s.suggestions:
        found.add(g.why)
        found |= {x.said for x in g.signals}
    return {n for n in found if n and len(n) >= 6}


def _cli(world, monkeypatch, capsys, *argv):
    from jason.commands import split as command

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    command.register(sub, lambda p: p.add_argument("--interactive", action="store_true"), lambda a: None)
    args = parser.parse_args(["split", *argv])
    assert args.func(args) == 0
    return capsys.readouterr().out


def _outputs(world, sid, monkeypatch, capsys, c):
    """Everything a reader of the session is given, as text: the console's loaders and writes, the command, and the tool."""
    from jason.mcp.split import split_suggestions

    url = f"/api/split-session?id={sid}"
    out = {
        "loader": c.get(url + "&facts=1-13&review=1&flags=1").get_data(as_text=True),
        "loader-plain": c.get(url).get_data(as_text=True),
        "list": c.get("/api/split-sessions").get_data(as_text=True),
        "review": c.post(f"/api/write/split/{sid}", json={"act": "review", "by": BY}).get_data(as_text=True),
        "apply-dry": c.post(f"/api/write/split/{sid}", json={"act": "apply", "by": BY}).get_data(as_text=True),
        "suggest": c.post(f"/api/write/split/{sid}", json={"act": "suggest", "by": BY}).get_data(as_text=True),
        "mark": c.post(f"/api/write/split/{sid}", json={"act": "mark", "pages": [4], "by": BY, "dryRun": True}).get_data(as_text=True),
        "mcp": json.dumps([split_suggestions(session=sid), split_suggestions(library_id="library:9001"), split_suggestions()], default=str),
        "cli-json": _cli(world, monkeypatch, capsys, sid, "--review", "--flags", "--json"),
        "cli-apply": _cli(world, monkeypatch, capsys, sid, "--apply", "--json"),
        "cli-list": _cli(world, monkeypatch, capsys, "--list", "--json"),
        "cli-text": _cli(world, monkeypatch, capsys, sid),
        "python": json.dumps([ss.view_of(world.root, ss.load(world.root, sid)), ss.facts_view(world.root, sid, 1, 13)], default=str),
    }
    return out


# --- (1) no page text before the private view ----------------------------------------------------------------------------------------

def test_every_reader_of_a_confidential_session_gets_numbers_states_and_codes_and_no_page_text(world, monkeypatch, capsys):
    sid = _open(world, True)
    needles = _needles(world, sid)
    assert len(needles) >= 4                                                       # the made-up pages did give titles, footers, and reasons
    c = _signed(world)
    for where, text in _outputs(world, sid, monkeypatch, capsys, c).items():
        for needle in needles:
            assert needle not in text, f"{where} carries page text: {needle!r}"
        assert LIB_NAME not in text and "Held Statement" not in text, where
    facts = c.get(f"/api/split-session?id={sid}&facts=1-13").json
    assert facts["confidential"] is True and facts["masked"]["text"] == "withheld" and "private view" in facts["confidentialWhy"]
    row = facts["facts"][3]
    assert row["n"] == 4 and row["words"] > 0 and "header" not in row and "title" not in row and "phash" not in row and "lqip" not in row
    assert all(g["why"] == "" and set(x) == {"signal", "weight"} for g in facts["suggestions"] for x in g["signals"])
    assert all("title" not in g["labels"] and "kind" not in g["labels"] for g in facts["segments"])


def test_the_same_readers_carry_the_text_when_the_file_is_not_confidential_and_when_the_private_view_is_open(world, monkeypatch, capsys):
    sid = _open(world, False)
    needles = _needles(world, sid)
    c = _signed(world)
    out = _outputs(world, sid, monkeypatch, capsys, c)
    for where in ("loader", "review", "mcp", "cli-text"):
        assert any(n in out[where] for n in needles), f"{where} should carry the text of a file that is not confidential"
    # a file flagged since: masked again; then the private view opens it
    _flag(world, True)
    masked = c.get(f"/api/split-session?id={sid}&facts=1-13&review=1").get_data(as_text=True)
    assert not any(n in masked for n in needles)
    assert c.post("/api/private", json={"reason": "board review"}).status_code == 200
    opened = c.get(f"/api/split-session?id={sid}&facts=1-13&review=1").get_data(as_text=True)
    assert any(n in opened for n in needles) and "masked" not in json.loads(opened)


def test_one_masking_function_names_what_it_withholds_and_never_changes_its_argument():
    view = {"suggestions": [{"id": "g2", "page": 2, "why": "Page 2. the heading", "signals": [{"signal": "title", "weight": 1.0, "said": "x"}]}],
            "segments": [{"key": "s1", "labels": {"title": "T", "kind": "k", "slot": "A", "period": "2099"}}]}
    held = split_mask.session_view(view, True)
    assert held["suggestions"][0]["why"] == "" and held["suggestions"][0]["signals"] == [{"signal": "title", "weight": 1.0}]
    assert held["segments"][0]["labels"] == {"slot": "A", "period": "2099"} and view["suggestions"][0]["why"] == "Page 2. the heading"
    assert split_mask.session_view(view, False) is view
    assert split_mask.facts([{"n": 1, "header": "h", "words": 4}], True) == [{"n": 1, "words": 4}]
    assert split_mask.review({"parts": [{"segment": "s1", "title": "T", "kind": "k", "count": 3}]}, True)["parts"] == [{"segment": "s1", "count": 3}]
    assert split_mask.hide_text(split_mask.Standing(False), False) is False
    assert split_mask.hide_text(split_mask.Standing(True), False) is True and split_mask.hide_text(split_mask.Standing(True), True) is False


# --- (2) the flag fails closed --------------------------------------------------------------------------------------------------------

def test_a_library_that_cannot_be_read_makes_the_file_confidential_and_says_so(world):
    sid = _open(world, False)
    session = ss.load(world.root, sid)
    assert ss.standing(world.root, session) == split_mask.Standing(False)
    _break(world)
    st = ss.standing(world.root, session)
    assert st.confidential is True and st.known is False and "could not be read just now" in st.why and "Try again" in st.why
    assert session.source.confidential is False                                    # the flag from the time it was opened is not trusted
    view = ss.view_of(world.root, session)
    assert view["masked"]["known"] is False and all(g["why"] == "" for g in view["suggestions"])
    assert ss.listing(world.root)[0]["confidential"] is True and ss.listing(world.root)[0]["label"] == "a confidential file"
    assert "header" not in ss.facts_view(world.root, sid, 1, 3)["facts"][0]


def test_the_flag_is_read_again_on_every_request_and_once_within_one(world, monkeypatch):
    sid = _open(world, False)
    c = _signed(world)
    calls = []
    real = ss._library_row

    def counted(root, doc_id):
        calls.append(doc_id)
        return real(root, doc_id)

    monkeypatch.setattr(ss, "_library_row", counted)
    assert c.get(f"/api/split-session?id={sid}&facts=1-3&review=1").json["confidential"] is False
    assert len(calls) == 1                                                         # the loader asks a few times; the library once
    _flag(world, True)
    assert c.get(f"/api/split-session?id={sid}").json["confidential"] is True      # the next request sees the new flag
    assert len(calls) == 2


def test_the_thumb_route_answers_503_with_a_retry_when_the_library_is_unreadable_and_the_private_view_is_closed(world):
    sid = _open(world, False)
    c = _signed(world)
    url = f"/api/split/thumb?id={sid}&page=1&size=96"
    assert c.get(url).status_code == 200
    _break(world)
    r = c.get(url)
    assert r.status_code == 503 and r.headers["Retry-After"] and "could not be read just now" in r.json["error"]
    assert c.post("/api/private", json={"reason": "board review"}).status_code == 200
    got = c.get(url)
    assert got.status_code == 200 and got.headers["Cache-Control"] == "private, no-store"          # treated as confidential while it is unreadable
    assert c.get("/api/split-sessions").json["sessions"][0]["label"] == "a confidential file"


# --- (3) the picture's cache headers ---------------------------------------------------------------------------------------------------

def test_a_library_picture_is_revalidated_and_a_flag_set_later_takes_effect(world):
    sid = _open(world, False)
    sha = ss.load(world.root, sid).source.sha256
    c = _signed(world)
    url = f"/api/split/thumb?id={sid}&page=2&size=200"
    r = c.get(url)
    assert r.status_code == 200 and r.headers["Cache-Control"] == "private, no-cache" and "immutable" not in r.headers["Cache-Control"]
    assert r.headers["ETag"] == th.etag(sha, 2, 200, False) and r.headers["ETag"].endswith('-p"')
    again = c.get(url, headers={"If-None-Match": r.headers["ETag"]})
    assert again.status_code == 304 and again.headers["Cache-Control"] == "private, no-cache"
    _flag(world, True)
    held = c.get(url, headers={"If-None-Match": r.headers["ETag"]})                 # the browser's copy was made before the flag
    assert held.status_code == 403 and "private view" in held.json["error"]
    assert c.post("/api/private", json={"reason": "board review"}).status_code == 200
    seen = c.get(url, headers={"If-None-Match": r.headers["ETag"]})
    assert seen.status_code == 200 and seen.headers["ETag"].endswith('-c"') and seen.headers["ETag"] != r.headers["ETag"]
    assert seen.headers["Cache-Control"] == "private, no-store"


def test_only_a_file_whose_standing_can_never_change_has_an_immutable_picture(world):
    s = ss.open_session({"kind": "path", "path": str(world.pdf)}, by=BY, root=world.root)["session"]
    c = _signed(world)
    r = c.get(f"/api/split/thumb?id={s['id']}&page=2&size=200")
    assert r.headers["Cache-Control"] == "private, max-age=31536000, immutable" and r.headers["ETag"] == th.etag(s["source"]["sha256"], 2, 200)
    # an upload keeps the flag it was opened with, so its pictures can never change standing
    data = base64.b64encode(split_gold.blank_separated().pdf).decode()
    up = c.post("/api/write/split/new", json={"act": "open", "by": BY, "ref": {"kind": "upload", "name": "a.pdf", "base64": data}}).json["session"]
    assert c.get(f"/api/split/thumb?id={up['id']}&page=1&size=96").headers["Cache-Control"] == "private, max-age=31536000, immutable"


# --- (4) the duplicate check and the open never switch off silently -----------------------------------------------------------------------

def test_an_open_of_a_library_file_is_not_misreported_as_no_such_file_when_the_library_is_busy(world):
    _library(world, False)
    _break(world)
    with pytest.raises(ss.LibraryBusy) as raised:
        ss.open_session({"kind": "library", "id": "9001"}, by=BY, root=world.root)
    assert "no file" not in str(raised.value) and "Try again" in str(raised.value) and isinstance(raised.value, ValueError)
    c = _signed(world)
    r = c.post("/api/write/split/new", json={"act": "open", "by": BY, "ref": {"kind": "library", "id": "9001"}})
    assert r.status_code == 503 and r.headers["Retry-After"] and r.json["busy"] is True and "Try again" in r.json["error"]
    assert not (world.root / "split" / "sessions").exists() or not list((world.root / "split" / "sessions").glob("*.json"))


def test_a_busy_library_shows_that_the_duplicate_check_was_skipped_and_refuses_an_apply(world):
    sid = _open(world, False)
    ok = ss.review(sid, root=world.root)
    assert ok["duplicateCheck"] == {"checked": True, "skipped": ""}
    _break(world)
    shown = ss.review(sid, root=world.root)
    assert shown["duplicateCheck"]["checked"] is False and "not checked against the files it already holds" in shown["duplicateCheck"]["skipped"]
    assert shown["files"] and shown["duplicates"] == []
    dry = ss.apply(sid, by=BY, root=world.root)
    assert dry["dryRun"] is True and dry["review"]["duplicateCheck"]["checked"] is False
    with pytest.raises(ss.LibraryBusy, match="Nothing was written"):
        ss.apply(sid, by=BY, confirm=True, root=world.root)
    assert ss.load(world.root, sid).status == "draft"
    c = _signed(world)
    r = c.post(f"/api/write/split/{sid}", json={"act": "apply", "by": BY, "dryRun": False, "confirm": True, "expect": "0" * 32})
    assert r.status_code == 503 and r.headers["Retry-After"] and "Nothing was written" in r.json["error"]
    assert not (world.root / "records" / "history.jsonl").exists() or "split-apply" not in (world.root / "records" / "history.jsonl").read_text("utf-8")


def test_a_mark_goes_on_while_the_library_is_busy_but_an_apply_will_not_(world):
    sid = _open(world, False)
    _break(world)
    out = ss.act(sid, "mark", {"pages": [4]}, by=BY, root=world.root)               # the stale check cannot be made; the write checks again
    assert out["changed"] is True
    with pytest.raises(ss.LibraryBusy):
        ss._check_not_stale(world.root, ss.load(world.root, sid), strict=True)


# --- (5) no file name in the cache, the logs, or the access log -------------------------------------------------------------------------

def test_the_cache_paths_and_the_logs_of_a_confidential_session_carry_no_file_name(world, monkeypatch, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    sid = _open(world, True)
    c = _signed(world)
    assert c.post("/api/private", json={"reason": "board review"}).status_code == 200
    for page in (1, 2):
        assert c.get(f"/api/split/thumb?id={sid}&page={page}&size=200").status_code == 200
    _outputs(world, sid, monkeypatch, capsys, c)
    ss.act(sid, "mark", {"pages": [5]}, by=BY, root=world.root)
    needles = _needles(world, sid) | {LIB_NAME, "Held Statement", "scan.pdf"}
    logged = "\n".join(r.getMessage() + " " + str(r.args) for r in caplog.records)
    for needle in needles:
        assert needle not in logged, needle
    # the folders the splitter wrote are named by hash, page, size, and session id only
    hexish = re.compile(r"^[0-9a-f]{2,64}(\.pdf|\.json|\.json\.bak|\.jsonl|\.webp|\.jpg)?$|^\d+(\.webp|\.jpg)?$|^_incoming$|^(sources|facts|sessions|journal|thumbs|\d+)$")
    for path in (world.root / "split").rglob("*"):
        assert hexish.match(path.name), path.name
    for path in (world.root / "thumbs").rglob("*") if (world.root / "thumbs").exists() else ():
        assert hexish.match(path.name), path.name
    for name in ("access/served.jsonl", "records/history.jsonl"):
        f = world.root / name
        if f.is_file():
            text = f.read_text(encoding="utf-8")
            assert not any(n in text for n in needles), name
