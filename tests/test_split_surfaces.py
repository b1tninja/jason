"""The splitter's surfaces: the console's routes, `jason split`, and the read-only MCP tool (docs/pdf-splitter.md, section 7), with
the limits it registers. The record-intake phase-2 world; made-up PDFs; no service."""

import argparse
import base64
import json

import pytest

import webclient
from jason import limits
from jason.community import split_gold
from jason.tasks import split_session as ss

from test_record_intake_phase2 import world  # noqa: F401  (a fixture)

BY = "A Manager"


@pytest.fixture
def pdf(world):
    path = world.tmp / "numbered.pdf"
    path.write_bytes(split_gold.numbered().pdf)
    return path


# --- the limits --------------------------------------------------------------------------------------------------------------------

def test_the_splitters_limits_are_registered_with_their_reasons_and_bounds():
    rows = {l.key: l for l in limits.all_limits()}
    assert rows["split.thumbnail_cache_bytes"].default == 512 * 1024 * 1024 and rows["split.thumbnail_cache_bytes"].minimum == 32 * 1024 * 1024
    assert rows["split.thumbnail_cache_bytes"].maximum == 8 * 1024 ** 3
    assert (rows["split.max_pages"].default, rows["split.max_pages"].minimum, rows["split.max_pages"].maximum) == (3000, 50, 10000)
    assert rows["split.suggest_enabled"].default is True and rows["split.suggest_enabled"].unit == "switch"
    assert (rows["split.draft_days"].default, rows["split.draft_days"].minimum, rows["split.draft_days"].maximum) == (60, 7, 365)
    assert rows["split.max_parts"].default == 500
    for key in ("thumbnail_cache_bytes", "max_pages", "suggest_enabled", "draft_days", "max_parts"):
        l = rows["split." + key]
        assert l.why.strip() and l.when_hit.strip() and l.applies_to
    # a value outside the range is held to it, never rejected on read
    import os

    os.environ["JASON_LIMIT_SPLIT_MAX_PAGES"] = "999999"
    try:
        assert limits.value("split.max_pages") == 10000
    finally:
        del os.environ["JASON_LIMIT_SPLIT_MAX_PAGES"]
    words = limits.refusal("split.max_pages", 4000, 3000).words
    assert "This file has 4,000 pages; the splitter opens files of up to 3,000" in words


# --- the console -------------------------------------------------------------------------------------------------------------------

def _app(world, monkeypatch):
    from jason.web.app import create_app
    from jason.web.extra import split as web_split
    from jason.web.sources import default_loaders

    monkeypatch.setattr(web_split, "_community", lambda: world.community)
    monkeypatch.setattr(web_split, "_root", lambda: world.root)
    return create_app(world.tmp, default_loaders(), sign_in=webclient.roster_sign_in(required=False))


def _signed(world, monkeypatch, name=BY):
    c = webclient.client(_app(world, monkeypatch))
    webclient.sign_in(c, name)
    return c


def _open(c, pdf, **extra):
    body = {"act": "open", "by": BY, "ref": {"kind": "upload", "name": "scan.pdf", "base64": base64.b64encode(pdf.read_bytes()).decode()}, **extra}
    return c.post("/api/write/split/new", json=body)


def test_the_console_opens_a_draft_edits_it_and_reads_it_back_with_reasons_and_facts(world, pdf, monkeypatch):
    c = _signed(world, monkeypatch)
    dry = _open(c, pdf, dryRun=True)
    assert dry.status_code == 200 and dry.json["dryRun"] is True and not (world.root / "split").exists()
    made = _open(c, pdf)
    assert made.status_code == 200 and made.json["session"]["status"] == "draft" and made.json["resumed"] is False
    sid, v = made.json["session"]["id"], made.json["session"]["version"]
    assert _open(c, pdf).json["resumed"] is True
    url = f"/api/write/split/{sid}"
    got = c.get(f"/api/split-session?id={sid}&facts=1-3&review=1")
    assert got.status_code == 200 and got.json["counts"]["pages"] == 13 and [f["n"] for f in got.json["facts"]] == [1, 2, 3]
    assert got.json["suggestions"][0]["why"] and got.json["review"]["files"] == 1 and got.json["renderer"] in ("pypdfium2", "pymupdf")
    assert got.json["sizes"] == [96, 200, 800] and got.json["limits"]["maxPages"] == 3000
    text = got.get_data(as_text=True)
    assert "scan.pdf" not in text and "numbered.pdf" not in text
    acc = c.post(url, json={"act": "accept", "id": "all", "by": BY, "version": v})
    assert acc.status_code == 200 and acc.json["accepted"] == 4 and acc.json["version"] == v + 1
    stale = c.post(url, json={"act": "mark", "pages": [8], "by": BY, "version": v})
    assert stale.status_code == 409 and stale.json["conflict"] is True and stale.json["current"]["version"] == v + 1
    assert c.post(url, json={"act": "boundaries", "boundaries": [[1, 0], [4, 0], [10, 1]], "by": BY, "version": v + 1}).json["changed"]
    assert c.post(url, json={"act": "undo", "by": BY}).json["undone"] is True
    assert c.post(url, json={"act": "mark", "pages": [99], "by": BY}).status_code == 400
    assert c.post(url, json={"act": "unmark", "page": 1, "by": BY}).status_code == 400
    assert c.post(url, json={"act": "nope", "by": BY}).status_code == 400
    assert c.post("/api/write/split/ffffffff", json={"act": "mark", "pages": [3], "by": BY}).status_code == 404
    assert c.post(url, json={"act": "suggest", "by": BY}).json["open"] >= 0
    listing = c.get("/api/split-sessions").json
    assert listing["sessions"][0]["id"] == sid and listing["limits"]["suggestEnabled"] is True
    assert c.get("/api/health").json["writes"].count("split") == 1


def test_the_console_refuses_a_server_path_a_wrong_name_and_the_owner_view(world, pdf, monkeypatch):
    c = _signed(world, monkeypatch)
    assert c.post("/api/write/split/new", json={"act": "open", "by": BY, "ref": {"kind": "path", "path": str(pdf)}}).status_code == 400
    assert c.post("/api/write/split/new", json={"act": "open", "by": BY, "ref": {"path": str(pdf)}}).status_code == 400
    wrong = c.post("/api/write/split/new", json={"act": "open", "by": "Someone Else", "ref": {"kind": "library", "id": "1"}})
    assert wrong.status_code == 403 and "signed-in name" in wrong.json["error"]
    assert c.get("/api/split-sessions?view=owner").status_code == 403
    assert c.get("/api/split-session?id=ffffffff").status_code == 404
    assert c.get("/api/split-session").status_code == 400
    plain = webclient.client(_app(world, monkeypatch))
    assert plain.get("/api/split-sessions").status_code == 401                    # signed out, where sign-in is set up
    owner = webclient.client(_app(world, monkeypatch))
    webclient.sign_in(owner, "Ada Admin")                                        # an admin with no office opens no board level
    assert owner.get("/api/split-sessions").status_code == 403
    assert webclient.client(_app(world, monkeypatch), token=False).post("/api/write/split/new", json={"act": "open", "by": BY}).status_code == 403


def test_apply_from_the_console_is_a_dry_run_until_dry_run_is_false_and_the_person_confirms(world, pdf, monkeypatch):
    c = _signed(world, monkeypatch)
    sid = _open(c, pdf).json["session"]["id"]
    url = f"/api/write/split/{sid}"
    c.post(url, json={"act": "boundaries", "boundaries": [[1, 0], [4, 0], [6, 0]], "by": BY})
    shown = c.post(url, json={"act": "apply", "by": BY})
    assert shown.json["dryRun"] is True and shown.json["review"]["files"] == 3
    nope = c.post(url, json={"act": "apply", "by": BY, "dryRun": False})                # no confirm
    assert nope.json["dryRun"] is True
    assert c.post(url, json={"act": "apply", "by": BY, "confirm": True}).json["dryRun"] is True      # confirm while dryRun is still true
    assert ss.load(world.root, sid).status == "draft"
    review = c.post(url, json={"act": "review", "by": BY, "drop": [2]})
    assert review.json["review"]["dropped"] == [2]
    done = c.post(url, json={"act": "apply", "by": BY, "dryRun": False, "confirm": True})
    assert done.status_code == 200 and done.json["ok"] is True and len(done.json["held"]) == 3
    s = ss.load(world.root, sid)
    assert s.status == "applied" and s.confirmed["by"] == BY
    assert c.post(url, json={"act": "apply", "by": BY, "dryRun": False, "confirm": True}).status_code == 400   # already applied
    assert c.post(url, json={"act": "mark", "pages": [3], "by": BY}).status_code == 400
    other = _open(c, pdf).json["session"]["id"]
    assert c.post(f"/api/write/split/{other}", json={"act": "decline", "by": BY}).json["declined"] is True


# --- the command -------------------------------------------------------------------------------------------------------------------

def _cli(world, monkeypatch, *argv):
    from jason.commands import split as command

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    command.register(sub, lambda p: p.add_argument("--interactive", action="store_true"), lambda a: None)
    args = parser.parse_args(["split", *argv])
    monkeypatch.setattr("jason.mcp.county._data_dir", lambda given=None: world.root)
    return args.func(args)


def test_the_command_is_a_dry_run_until_yes_and_needs_a_name_for_a_write(world, pdf, monkeypatch, capsys):
    assert _cli(world, monkeypatch, str(pdf)) == 0
    assert "would open a file of 13 pages" in capsys.readouterr().out and not (world.root / "split").exists()
    assert _cli(world, monkeypatch, str(pdf), "--yes") == 2
    assert "--yes needs --by NAME" in capsys.readouterr().err
    assert _cli(world, monkeypatch, str(pdf), "--yes", "--by", "Jane Example") == 0
    out = capsys.readouterr().out
    assert "opened" in out and "13 pages" in out and "suggested g4: page 4  High" in out
    assert "numbered.pdf" not in out and str(world.tmp) not in out                # the path is not echoed
    sid = ss.sessions(world.root)[0].id
    assert _cli(world, monkeypatch, "--list") == 0 and sid in capsys.readouterr().out
    # a draft change is shown and not kept until --yes
    assert _cli(world, monkeypatch, sid, "--boundaries", "1,4,6", "--by", "Jane Example") == 0
    assert "A dry run: nothing was saved" in capsys.readouterr().out and ss.load(world.root, sid).version == 1
    assert _cli(world, monkeypatch, sid, "--boundaries", "1,4,6", "--by", "Jane Example", "--yes") == 0
    capsys.readouterr()
    assert [g.start for g in ss.load(world.root, sid).top_segments()] == [1, 4, 6]
    assert _cli(world, monkeypatch, sid, "--accept", "g10", "--reject", "g11", "--by", "Jane Example", "--yes") == 0
    capsys.readouterr()
    assert _cli(world, monkeypatch, sid, "--undo", "--by", "Jane Example", "--yes") == 0
    capsys.readouterr()


def test_the_command_reviews_applies_and_purges_and_only_apply_yes_writes_pdfs(world, pdf, monkeypatch, capsys):
    assert _cli(world, monkeypatch, str(pdf), "--yes", "--by", "Jane Example") == 0
    sid = ss.sessions(world.root)[0].id
    _cli(world, monkeypatch, sid, "--boundaries", "1,4,6,10", "--by", "Jane Example", "--yes")
    capsys.readouterr()
    assert _cli(world, monkeypatch, sid, "--review", "--drop", "2") == 0
    out = capsys.readouterr().out
    assert "review of" in out and "4 files from 13 pages" in out and "12 pages in files, 1 left out" in out
    assert _cli(world, monkeypatch, sid, "--apply") == 0                            # no --yes: the review, nothing written
    assert "Confirm as a person (--yes)" in capsys.readouterr().out
    assert not (world.root / "record-intake").exists()
    assert _cli(world, monkeypatch, sid, "--apply", "--yes", "--by", "Jane Example") == 0
    out = capsys.readouterr().out
    assert "wrote 0 files into slots and held 4" in out
    assert len(list((world.root / "record-intake" / "example" / "files").glob("*/*.pdf"))) == 4
    assert _cli(world, monkeypatch, sid, "--apply", "--yes", "--by", "Jane Example") == 1       # applied already
    assert "applied already" in capsys.readouterr().err
    assert _cli(world, monkeypatch, "--purge", "--all-drafts") == 0 and "A dry run: nothing was removed" in capsys.readouterr().out
    assert _cli(world, monkeypatch) == 2
    assert "name a PDF" in capsys.readouterr().err
    assert _cli(world, monkeypatch, "--sweep") == 0 and "would remove 0 drafts" in capsys.readouterr().out


def test_the_command_reports_a_refusal_in_words_with_exit_one(world, pdf, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("JASON_LIMIT_SPLIT_MAX_PAGES", "50")
    import pymupdf

    doc = pymupdf.open()
    for _ in range(51):
        doc.new_page()
    big = tmp_path / "big.pdf"
    big.write_bytes(doc.tobytes())
    assert _cli(world, monkeypatch, str(big)) == 1
    assert "This file has 51 pages; the splitter opens files of up to 50" in capsys.readouterr().err
    assert _cli(world, monkeypatch, str(tmp_path / "nope.pdf")) == 1
    assert "no such file" in capsys.readouterr().err
    assert _cli(world, monkeypatch, str(pdf), "--json") == 0
    assert json.loads(capsys.readouterr().out)["dryRun"] is True


# --- the MCP tool -----------------------------------------------------------------------------------------------------------------

def test_the_mcp_tool_reads_saved_suggestions_and_runs_nothing(world, pdf, monkeypatch):
    from jason.mcp import split as tool
    from jason.mcp.server import ALL_TOOLS, PROFILES, tools_for

    monkeypatch.setattr(tool, "_root", lambda: world.root)
    s = ss.open_session({"kind": "path", "path": str(pdf)}, by="Jane Example", root=world.root, community=world.community, profile="example")["session"]
    called = []
    monkeypatch.setattr(ss, "_suggest", lambda *a, **k: called.append(1))
    monkeypatch.setattr("jason.tasks.split_thumbs.render_page", lambda *a, **k: called.append(2))
    out = tool.split_suggestions(session=s["id"])
    assert out["found"] and called == []                                              # it never runs the engine or the renderer
    row = out["sessions"][0]
    assert row["pages"] == 13 and row["boundaries"] == [1] and [x["page"] for x in row["suggestions"]] == [4, 6, 10, 11]
    assert row["suggestions"][0]["band"] == "High" and row["suggestions"][0]["why"] and any("evidence, not a boundary" in c for c in out["caveats"])
    assert tool.split_suggestions(library_id="nope")["found"] is False and tool.split_suggestions(session="ffffffff")["found"] is False
    assert tool.split_suggestions()["sessions"][0]["id"] == s["id"]
    # a confidential file is held back unless asked
    saved = ss.load(world.root, s["id"])
    saved.source = type(saved.source)(**{**saved.source.to_dict(), "confidential": True})
    ss.save(world.root, saved)
    held = tool.split_suggestions(session=s["id"])["sessions"][0]
    assert "heldBack" in held and "suggestions" not in held
    assert "suggestions" in tool.split_suggestions(session=s["id"], include_confidential=True)["sessions"][0]
    assert "split_suggestions" in PROFILES["board"] and "split_suggestions" in {t.__name__ for t in ALL_TOOLS}
    assert len(tools_for("board")) == 49 and "split_suggestions" not in PROFILES["onboarding"]
    names = [t.__name__ for t in ALL_TOOLS]
    assert len(names) == len(set(names))
    assert not [n for n in names if n.startswith("split") and n != "split_suggestions"]       # no tool opens, edits, or applies a split
