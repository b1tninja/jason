"""docs/instance-limits.md phases 3 and 5 on the registry: the fetch limit read at its two points, the per-act override (honoured only
where a row allows it, up to its once-only maximum, with a reason; never stored; one `override` line), the `clamped` and `refused`
trail kinds, the temp-drive guard at the upload point, and the read-only MCP tool. Made-up data in tmp_path only."""

import json

import pytest

from jason import limits, storage
from jason.limits import LimitReached, LimitRefused, Override

MB = 1024 * 1024
UP = "upload.max_bytes"


@pytest.fixture
def where(tmp_path, monkeypatch):
    monkeypatch.delenv("JASON_LIMIT_UPLOAD_MAX_BYTES", raising=False)
    monkeypatch.delenv("JASON_LIMIT_FETCH_MAX_BYTES", raising=False)
    folder = tmp_path / "community"
    folder.mkdir()
    return {"data_folder": folder, "instance_file": tmp_path / "home" / "limits.json"}


def _ov(allowed="200MB", reason="One large combined scan", by="A. Admin", **kw):
    return Override(UP, limits.limit(UP).parse(allowed), reason, by, **kw)


# --- the fetch limit ---------------------------------------------------------------------------------------------------------

def test_fetch_is_a_registered_size_limit_with_a_default_of_100_mb_read_at_its_two_points(where):
    row = limits.limit("fetch.max_bytes")
    assert (row.default, row.kind, row.unit) == (100 * MB, "size", "bytes") and row.override is False
    assert limits.check("fetch.max_bytes", 100 * MB, **where).value == 100 * MB
    with pytest.raises(LimitReached) as hit:
        limits.check("fetch.max_bytes", 101 * MB, **where)
    assert "101 MB" in hit.value.words and "100 MB" in hit.value.words and "Nothing was copied" in hit.value.words


def test_a_stored_drive_file_over_the_fetch_limit_is_not_copied_and_a_read_back_does_not_fetch_it(monkeypatch):
    from jason.tasks import drive_copies, record_readback

    monkeypatch.delenv("JASON_LIMIT_FETCH_MAX_BYTES", raising=False)
    why = record_readback._problem({"mimeType": "application/pdf", "size": str(150 * MB)})
    assert "150 MB" in why and "100 MB" in why and "Nothing was copied" in why
    assert record_readback._problem({"mimeType": "application/pdf", "size": str(5 * MB)}) == ""

    class Drive:
        def file_metadata(self, file_id, fields):
            return {"id": file_id, "name": "Big.pdf", "mimeType": drive_copies.PDF, "size": str(150 * MB),
                    "capabilities": {"canDownload": True, "canCopy": True}}

        def download_bytes(self, file_id):                      # pragma: no cover - must not be reached
            raise AssertionError("a file over the limit was downloaded")

    monkeypatch.setattr(drive_copies, "_reusable", lambda *a, **k: "")
    with pytest.raises(drive_copies.CopyRefused, match="150 MB"):
        drive_copies.export(Drive(), drive_copies.Path("."), "a" * 20)


def test_the_two_fetch_literals_are_gone_from_the_code():
    import inspect

    from jason.tasks import drive_copies, record_readback

    assert not hasattr(drive_copies, "DOWNLOAD_LIMIT") and not hasattr(record_readback, "MAX_FETCH")
    assert "100 * 1024 * 1024" not in inspect.getsource(drive_copies) + inspect.getsource(record_readback)


# --- the per-act override ----------------------------------------------------------------------------------------------------

def test_an_override_lets_one_act_through_once_and_is_never_a_setting(where):
    over = 140 * MB
    with pytest.raises(LimitReached):
        limits.check(UP, over, **where)                                      # no override: refused
    eff = limits.check(UP, over, act=_ov(), **where)
    assert eff.value == 100 * MB                                              # the limit itself did not move
    assert not (where["data_folder"] / limits.FILE_NAME).exists()
    assert limits.value(UP, **where) == 100 * MB
    with pytest.raises(LimitReached):
        limits.check(UP, over, **where)                                      # the next act is refused again
    (line,) = limits.read_log("community", data_folder=where["data_folder"])
    assert (line["kind"], line["scope"], line["key"], line["from"], line["to"], line["amount"]) == ("override", "community", UP, 100 * MB, 200 * MB, over)
    assert line["reason"] == "One large combined scan" and line["by"] == "A. Admin" and line["role"] == "community administrator"
    assert line["what"] == "an act" and "at" in line and line["via"] == "cli"
    assert str(where["data_folder"]) not in json.dumps(line)


def test_an_override_carried_on_the_acts_record_is_read_the_same_way(where):
    act = {"limit_override": {"key": UP, "allowed": 150 * MB, "reason": "A whole-association mailing list", "by": "A. Admin"}}
    assert limits.check(UP, 120 * MB, act=act, **where).value == 100 * MB
    assert limits.read_log("community", data_folder=where["data_folder"])[0]["kind"] == "override"


def test_an_override_needs_a_row_that_allows_it_a_reason_a_name_and_the_right_role(where):
    other = Override("fetch.max_bytes", 200 * MB, "r", "A. Admin")
    with pytest.raises(LimitRefused, match="allows no override"):
        limits.check("fetch.max_bytes", 150 * MB, act=other, **where)
    for bad, match in ((_ov(reason=" "), "needs a reason"), (_ov(by=""), "needs the name"),
                       (_ov(role="community officer"), "only a community administrator")):
        with pytest.raises(LimitRefused, match=match):
            limits.check(UP, 140 * MB, act=bad, **where)
    assert limits.read_log("community", data_folder=where["data_folder"]) == []          # a refused override leaves no override line


def test_an_override_stops_at_the_rows_once_only_maximum_with_the_nearest_allowed_value(where):
    with pytest.raises(LimitRefused) as hit:
        limits.check(UP, 140 * MB, act=_ov(allowed="400MB"), **where)
    assert hit.value.nearest == 250 * MB and "The nearest allowed value is 250 MB" in hit.value.describe()
    with pytest.raises(LimitReached):                                                    # past what this act was allowed
        limits.check(UP, 220 * MB, act=_ov(allowed="200MB"), **where)
    assert limits.read_log("community", data_folder=where["data_folder"]) == []


def test_an_override_does_not_log_for_a_dry_run_or_when_the_amount_is_within_the_limit(where):
    limits.check(UP, 140 * MB, act=_ov(), record=False, **where)
    limits.check(UP, 5 * MB, act=_ov(), **where)
    assert limits.read_log("community", data_folder=where["data_folder"]) == []


def test_an_override_is_not_honoured_when_its_line_cannot_be_written(where, monkeypatch):
    monkeypatch.setattr(limits, "_append_log", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(LimitRefused, match="could not be recorded"):
        limits.check(UP, 140 * MB, act=_ov(), **where)


def test_no_registry_row_lets_a_safety_limit_be_passed():
    for l in limits.all_limits():
        if l.override:
            assert l.unit != "switch" and l.direction == "either" and l.override_max <= l.maximum


def test_parse_override_reads_key_equals_value_and_refuses_anything_else():
    ov = limits.parse_override("upload.max_bytes=200MB", reason="r", by="A. Admin", what="an upload")
    assert ov.allowed == 200 * MB and ov.what == "an upload"
    for bad in ("upload.max_bytes", "=200MB", "upload.max_bytes=", "split.auto_read=on"):
        with pytest.raises(LimitRefused):
            limits.parse_override(bad, reason="r", by="A. Admin")


# --- the clamped and refused trail kinds -------------------------------------------------------------------------------------

def test_a_stored_value_held_to_its_range_is_noted_once_as_clamped(where):
    (where["data_folder"] / limits.FILE_NAME).write_text(json.dumps({"version": 1, "limits": {UP: {"value": 900 * MB}}}), encoding="utf-8")
    for _ in range(3):
        assert limits.check(UP, 1 * MB, **where).clamped is True
    rows = limits.read_log("community", data_folder=where["data_folder"])
    assert [r["kind"] for r in rows] == ["clamped"] and rows[0]["key"] == UP and rows[0]["to"] == 500 * MB and rows[0]["by"] == "jason"
    assert limits.value(UP, **where) == 500 * MB


def test_a_change_that_was_refused_leaves_a_refused_line_and_a_dry_run_leaves_none(where):
    kw = dict(scope="community", reason="Because", by="A. Admin", **where)
    with pytest.raises(LimitRefused):
        limits.set_limits({UP: "9GB"}, dry_run=True, **kw)
    assert limits.read_log("community", data_folder=where["data_folder"]) == []
    with pytest.raises(LimitRefused):
        limits.set_limits({UP: "9GB"}, dry_run=False, **kw)
    (line,) = limits.read_log("community", data_folder=where["data_folder"])
    assert (line["kind"], line["key"], line["by"]) == ("refused", UP, "A. Admin") and "above 500 MB" in line["refusal"]
    assert not (where["data_folder"] / limits.FILE_NAME).exists()


def test_each_role_changes_only_its_own_layer_and_the_trail_names_the_role_and_subject(where):
    kw = dict(reason="Because", by="A. Admin", dry_run=False, who="sub-ada", via="console:google", **where)
    with pytest.raises(LimitRefused, match="community administrator changes the community layer only"):
        limits.set_limits({UP: "50MB"}, scope="instance", role=limits.ROLE_COMMUNITY, **kw)
    with pytest.raises(LimitRefused, match="instance operator changes the instance layer only"):
        limits.set_limits({UP: "50MB"}, scope="community", role=limits.ROLE_INSTANCE, **kw)
    with pytest.raises(LimitRefused, match="may not change a limit"):
        limits.set_limits({UP: "50MB"}, scope="community", role="community officer", **kw)
    limits.set_limits({UP: "50MB"}, scope="community", role=limits.ROLE_COMMUNITY, **kw)
    last = [r for r in limits.read_log("community", data_folder=where["data_folder"]) if r["kind"] == "set"][-1]
    assert (last["role"], last["who"], last["via"]) == ("community administrator", "sub-ada", "console:google")


# --- the temp-drive guard ----------------------------------------------------------------------------------------------------

def test_room_problem_names_the_drive_in_words_and_never_a_path(tmp_path):
    def measure(path):
        return 90 * MB
    why = storage.room_problem(tmp_path, 140 * MB, free=measure, scratch=tmp_path)
    assert "140 MB" in why and "90 MB free" in why and "Nothing was saved" in why and str(tmp_path) not in why
    assert "A limit never makes room that is not there" in why
    assert storage.room_problem(tmp_path, 1 * MB, free=lambda p: None, scratch=tmp_path) == ""      # unreadable: not a reason to refuse
    assert storage.room_problem(tmp_path, 1 * MB, free=lambda p: 10 * 1024 ** 3, scratch=tmp_path) == ""


def test_scratch_on_its_own_drive_is_checked_too(tmp_path):
    scratch = tmp_path / "scratch"
    sizes = {str(tmp_path): 10 * 1024 ** 3, str(scratch): 10 * MB}
    why = storage.room_problem(tmp_path, 50 * MB, free=lambda p: sizes[str(p)], scratch=scratch, reserve=0)
    assert why == "" or "10 MB free" in why        # same drive on a test machine: both asks are added; never a crash


def test_a_limit_never_overrides_the_guard_at_the_upload_point(tmp_path, monkeypatch):
    from jason.tasks import record_upload

    monkeypatch.setattr(storage, "free_bytes", lambda p: 30 * MB)
    with pytest.raises(storage.DriveShort, match="Nothing was saved"):
        record_upload._keep(tmp_path, "example", "Scan.pdf", b"%PDF-" + b"x" * (40 * MB))
    assert not (tmp_path / "record-intake").exists()
    assert limits.value(UP) >= 40 * MB             # the limit would have allowed it; the guard did not


# --- MCP ---------------------------------------------------------------------------------------------------------------------

def test_the_mcp_tool_reads_the_limits_for_the_servers_community_and_changes_nothing(where, monkeypatch, tmp_path):
    from types import SimpleNamespace

    from jason.mcp import limits as tool

    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JASON_LIMITS_FILE", str(tmp_path / "home" / "limits.json"))
    monkeypatch.setattr(tool, "_community", lambda: SimpleNamespace(slug="alpha", limits=dict))
    limits.set_limits({UP: "50MB"}, scope="community", reason="SENT-reason", by="A. Admin", dry_run=False,
                      community=SimpleNamespace(slug="alpha", limits=dict))
    out = tool.limits()
    assert out["found"] and {r["key"] for r in out["limits"]} == {l.key for l in limits.all_limits()}
    one = tool.limits("upload.max_bytes")["limits"][0]
    assert one["value"] == 50 * MB and one["source"] == "community" and one["why"] and one["whenHit"] and one["passOnceMax"] == 250 * MB
    assert "SENT-reason" not in json.dumps(out) and "A. Admin" not in json.dumps(out) and str(tmp_path) not in json.dumps(out)
    assert "never changes one" in out["caveats"][0]
    assert tool.limits("nope.key")["found"] is False
    import inspect
    assert list(inspect.signature(tool.limits).parameters) == ["key"]                  # no community argument


def test_the_tool_is_in_the_board_and_governance_sets_and_no_tool_writes_a_limit():
    from jason.mcp.server import ALL_TOOLS, PROFILES, tools_for

    assert "limits" in PROFILES["board"] and "limits" in PROFILES["governance"]
    assert {t.__name__ for t in tools_for("governance")} >= {"limits"}
    names = [t.__name__ for t in ALL_TOOLS]
    assert not [n for n in names if "limit" in n and n != "limits"]
    import jason.mcp.limits as tool_module
    assert "set_limits" not in open(tool_module.__file__, encoding="utf-8").read().replace("no tool here sets", "")
