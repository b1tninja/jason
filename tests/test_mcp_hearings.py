"""The MCP ``hearings`` tool: a hearing is a member's discipline (CIV 4935(b)), so by default it returns the handle, the
general title, the days and the clock; the address, violation, notice, Zoom link and passcode, and findings only with
``include_confidential``. A handle is minted where a hearing is saved and by the one-off migration, never by a reader.
Everything here is made up."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from types import SimpleNamespace

from jason.mcp.county import hearings
from jason.tasks import hearing_decisions as hd

ADDRESS = "123 Main St #12"


def _row(**more):
    row = {"address": ADDRESS, "building": "4", "start": "2026-10-20T18:00:00-07:00", "noticeBy": "2026-10-10", "noticeOn": "2026-10-05",
           "decisionByIfHeld": "2026-11-03", "violation": "A fence beyond the lot line", "problems": ["no meeting day for 123 Main St"],
           "zoom": {"id": "123456789", "joinUrl": "https://zoom.example/j/123456789", "passcode": "s3cret"},
           "notice": "hearings/2026-10-20-123-main-st-12.md", "noticeDoc": {"id": "doc1", "url": "https://docs.example/d/doc1"},
           "handle": "h-0a1b2c3d",
           "decision": {"findings": "A $50 fine, waived if moved.", "decidedOn": "2026-10-20", "noticeDueBy": "2026-11-03",
                        "by": "Sam Secretary", "recorded": "2026-10-21T00:00:00+00:00", "history": ["recorded by Sam Secretary"]}}
    row.update(more)
    return row


def _seed(root, *rows):
    (root / "zoom").mkdir(parents=True, exist_ok=True)
    (root / "zoom" / "hearings.json").write_text(json.dumps({"hearings": list(rows or [_row()])}), encoding="utf-8")


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def test_by_default_only_the_handle_the_general_title_and_the_clock_are_returned(tmp_path):
    _seed(tmp_path)
    out = hearings(data_dir=tmp_path)
    assert out["found"] is True and out["confidential"] is False and out["unmigrated"] == 0 and "include_confidential" in out["heldBack"]
    (row,) = out["hearings"]
    assert row["handle"] == "h-0a1b2c3d" and "member discipline" in row["title"] and row["start"].startswith("2026-10-20")
    assert row["noticeBy"] == "2026-10-10" and row["decisionByIfHeld"] == "2026-11-03" and row["scheduled"] is True
    assert row["decision"] == {"decidedOn": "2026-10-20", "noticeDueBy": "2026-11-03"}
    assert set(row) == {"handle", "title", "start", "noticeBy", "noticeOn", "decisionByIfHeld", "standing", "scheduled", "decision"}
    text = " ".join(_strings(out)).lower()
    for leak in ("main st", "fence", "s3cret", "zoom.example", "123456789", "hearings/2026", "doc1", "$50", "sam secretary", "no meeting day"):
        assert leak not in text, leak


def test_a_field_added_to_the_stored_row_stays_out_until_it_is_allowed(tmp_path):
    _seed(tmp_path, _row(owner="Rae Roster", unit="12"))
    text = " ".join(_strings(hearings(data_dir=tmp_path))).lower()
    assert "rae roster" not in text and '"unit"' not in text


def test_include_confidential_returns_the_whole_row(tmp_path):
    _seed(tmp_path)
    out = hearings(include_confidential=True, data_dir=tmp_path)
    (row,) = out["hearings"]
    assert row["address"] == ADDRESS and row["violation"].startswith("A fence") and row["zoom"]["passcode"] == "s3cret"
    assert row["decision"]["findings"].startswith("A $50 fine") and row["standing"]


def test_a_hearing_with_no_handle_is_counted_not_listed_and_nothing_is_written(tmp_path):
    _seed(tmp_path, _row(), _row(address="9 Elm St", start="2026-11-10T18:00:00-08:00", handle=""))
    before = _tree(tmp_path)
    out = hearings(data_dir=tmp_path)
    assert [r["handle"] for r in out["hearings"]] == ["h-0a1b2c3d"] and out["unmigrated"] == 1
    assert "Elm" not in " ".join(_strings(out))
    assert len(hearings(include_confidential=True, data_dir=tmp_path)["hearings"]) == 2
    assert hd.ensure_handles(tmp_path) and hd.unmigrated(tmp_path) == 1
    assert _tree(tmp_path) == before                                                    # a read wrote nothing


def test_no_store_is_a_miss_not_a_crash(tmp_path):
    out = hearings(data_dir=tmp_path)
    assert out["found"] is False and out["hearings"] == [] and "no hearings saved" in out["note"]


def test_the_migration_counts_without_write_and_mints_with_it(tmp_path):
    (tmp_path / "zoom").mkdir()
    rows = [_row(handle=""), _row(address="9 Elm St", start="2026-11-10T18:00:00-08:00", handle=""), _row(address="1 Oak St", start="2026-12-01T18:00:00-08:00")]
    rows[2]["handle"] = "h-ffffffff"
    (tmp_path / "zoom" / "hearings.json").write_text(json.dumps({"hearings": rows}), encoding="utf-8")
    before = _tree(tmp_path)
    assert hd.mint_handles(tmp_path) == {"hearings": 3, "unmigrated": 2, "minted": 0} and _tree(tmp_path) == before
    assert hd.mint_handles(tmp_path, write=True) == {"hearings": 3, "unmigrated": 2, "minted": 2}
    got = hd.load(tmp_path)
    assert len({r["handle"] for r in got}) == 3 and all(hd.is_handle(r["handle"]) for r in got)
    assert next(r for r in got if r["address"] == "1 Oak St")["handle"] == "h-ffffffff"      # a handle already given is kept
    assert [r["start"] for r in got] == sorted(r["start"] for r in got)
    assert hd.mint_handles(tmp_path, write=True) == {"hearings": 3, "unmigrated": 0, "minted": 0}
    assert hd.mint_handles(tmp_path / "nowhere", write=True) == {"hearings": 0, "unmigrated": 0, "minted": 0}


def test_the_command_counts_by_default_and_migrates_only_with_yes(tmp_path, monkeypatch, capsys):
    from jason import cli

    _seed(tmp_path, _row(handle=""))
    monkeypatch.setattr("jason.config.Settings.load", classmethod(lambda cls, env=None: SimpleNamespace(payhoa_catalog=tmp_path / "catalog.json")))
    before = _tree(tmp_path)
    assert cli.cmd_zoom(cli.build_parser().parse_args(["zoom", "--mint-handles"])) == 0
    assert "1 of 1" in capsys.readouterr().out and _tree(tmp_path) == before
    assert cli.cmd_zoom(cli.build_parser().parse_args(["zoom", "--mint-handles", "--yes"])) == 0
    assert "gave 1 of 1" in capsys.readouterr().out and hd.unmigrated(tmp_path) == 0
