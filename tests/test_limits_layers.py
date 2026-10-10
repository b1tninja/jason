"""docs/instance-limits.md, phases 1 and 2: the registry's full record, the layers (default, environment, instance file, community
file), the ceiling, ``lower_only``, a file that cannot be read, ``check`` and its words, and the one writer with its trail.

Rows that exercise a layer the registry does not use yet (a ``lower_only`` limit, one only the instance sets) are made here and
put in the registry for the test with ``monkeypatch``; nothing real is written (every file is under ``tmp_path``).
"""

import hashlib
import json
from argparse import Namespace
from pathlib import Path

import pytest

from jason import jobs, limits
from jason.limits import Limit, LimitReached, LimitRefused

MB = 1024 * 1024
KEY = "upload.max_bytes"
CAP = "cap.test_mailing"          # lower_only, instance and community may lower it
OPS = "ops.test_window"           # only the instance may set it


def _rows():
    return (
        Limit(CAP, 150, 1, 1000, "count", "a made-up cap", kind="cost", direction="lower_only",
              why="A test ceiling that can be tightened and never raised.", when_hit="This act has {amount}; the limit is {limit}.",
              applies_to=("tests",)),
        Limit(OPS, 600, 60, 3600, "seconds", "a made-up window", kind="time", scopes=("instance",),
              why="A test window only the operator sets.", when_hit="Ended after {limit}.", applies_to=("tests",)),
    )


@pytest.fixture
def where(tmp_path, monkeypatch):
    for name in ("JASON_LIMIT_UPLOAD_MAX_BYTES", "JASON_LIMIT_SPLIT_AUTO_READ", "JASON_LIMITS_FILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(limits, "LIMITS", limits.LIMITS + _rows())
    data = tmp_path / "community"
    data.mkdir()
    return {"data_folder": data, "instance_file": tmp_path / "instance" / "limits.json"}


def _file(path: Path, entries: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "limits": entries}), encoding="utf-8")


def _eff(key=KEY, **where):
    return limits.limit(key).effective(**where)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


# --- the record -------------------------------------------------------------------------------------------------------------

def test_every_registered_limit_is_a_full_record():
    for l in limits.LIMITS:
        assert l.why and l.when_hit and l.applies_to and l.unit and l.kind and l.restart in limits.RESTARTS
        if l.unit != "switch":
            assert isinstance(l.minimum, int) and isinstance(l.maximum, int) and l.minimum <= l.default <= l.maximum
    assert limits.limit(KEY).scopes == ("instance", "community")


def test_a_row_without_why_or_when_hit_does_not_load():
    base = dict(key="a.b", default=5, minimum=1, maximum=9, unit="count", description="d", applies_to=("x",))
    Limit(**base, why="w", when_hit="h")
    with pytest.raises(ValueError, match="no why"):
        Limit(**base, when_hit="h")
    with pytest.raises(ValueError, match="no when_hit"):
        Limit(**base, why="w")
    with pytest.raises(ValueError, match="finite minimum"):
        Limit("a.b", 5, None, 9, "count", "d", why="w", when_hit="h", applies_to=("x",))
    with pytest.raises(ValueError, match="default inside"):
        Limit("a.b", 50, 1, 9, "count", "d", why="w", when_hit="h", applies_to=("x",))


def test_no_registered_key_names_a_safety_control():
    forbidden = ("audit", "banner", "confirm", "jail", "identity", "lock", "preflight", "temp_guard", "two_person", "write_line")
    for l in limits.LIMITS:
        assert not any(word in l.key for word in forbidden), l.key


# --- the unit's words --------------------------------------------------------------------------------------------------------

def test_values_are_read_and_said_in_the_units_words_and_nothing_means_unlimited(where):
    cap, window = limits.limit(KEY), limits.limit(OPS)
    assert cap.parse("50MB") == 50 * MB and cap.parse("1.5GB") == 1536 * MB and cap.parse("1048576") == MB
    assert window.parse("30m") == 1800 and window.parse("2h") == 7200
    assert limits.limit("split.auto_read").parse("on") is True and limits.limit("split.auto_read").parse("off") is False
    for bad in ("inf", "unlimited", "none", "-5", "", "lots", "1e9", float("inf"), True):
        assert cap.parse(bad) is None, bad
    assert cap.format(100 * MB) == "100 MB" and cap.format(MB + 5, up=True) == "1.1 MB" and window.format(1800) == "30 minutes"


# --- the layers --------------------------------------------------------------------------------------------------------------

def test_the_instance_file_beats_the_environment_and_the_community_file_beats_both(where, monkeypatch):
    assert _eff(**where).source == "default"
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", str(80 * MB))
    got = _eff(**where)
    assert (got.source, got.value) == ("env", 80 * MB)
    _file(where["instance_file"], {KEY: {"value": 60 * MB, "ceiling": 90 * MB, "by": "A. Operator", "at": "2026-10-10T16:02:11Z",
                                         "reason": "small disk"}})
    got = _eff(**where)
    assert (got.source, got.value, got.ceiling) == ("instance", 60 * MB, 90 * MB)
    assert got.set["by"] == "A. Operator" and got.set["reason"] == "small disk"
    _file(where["data_folder"] / "limits.json", {KEY: {"value": 70 * MB, "by": "B. Admin"}})
    got = _eff(**where)
    assert (got.source, got.value, got.clamped) == ("community", 70 * MB, False) and got.set["by"] == "B. Admin"


def test_an_instance_value_with_no_ceiling_is_also_the_ceiling(where):
    _file(where["instance_file"], {KEY: {"value": 50 * MB}})
    _file(where["data_folder"] / "limits.json", {KEY: {"value": 200 * MB}})
    got = _eff(**where)
    assert (got.value, got.ceiling, got.source, got.clamped) == (50 * MB, 50 * MB, "community", True)
    assert "the operator's limit is 50 MB" in got.note


def test_the_ceiling_clamps_a_community_and_the_bounds_clamp_everyone(where):
    _file(where["instance_file"], {KEY: {"value": 100 * MB, "ceiling": 200 * MB}})
    _file(where["data_folder"] / "limits.json", {KEY: {"value": 400 * MB}})
    got = _eff(**where)
    assert (got.value, got.clamped) == (200 * MB, True) and got.ceiling == 200 * MB
    _file(where["data_folder"] / "limits.json", {KEY: {"value": 1}})
    assert _eff(**where).value == MB                                               # the minimum
    _file(where["instance_file"], {KEY: {"value": 9999 * MB}})
    _file(where["data_folder"] / "limits.json", {})
    assert _eff(**where).value == 500 * MB                                         # the maximum


def test_a_lower_only_limit_never_rises_above_its_default_at_any_layer(where, monkeypatch):
    _file(where["instance_file"], {CAP: {"value": 900}})
    _file(where["data_folder"] / "limits.json", {CAP: {"value": 800}})
    got = _eff(CAP, **where)
    assert got.value == 150 and got.clamped is True
    monkeypatch.setenv("JASON_LIMIT_CAP_TEST_MAILING", "400")
    assert _eff(CAP, **where).value == 150
    _file(where["data_folder"] / "limits.json", {CAP: {"value": 100}})
    assert _eff(CAP, **where).value == 100


def test_a_scope_the_row_does_not_allow_is_ignored(where):
    _file(where["data_folder"] / "limits.json", {OPS: {"value": 120}})
    assert _eff(OPS, **where).value == 600                                         # only the instance sets it
    _file(where["instance_file"], {OPS: {"value": 120}})
    assert _eff(OPS, **where).value == 120


def test_a_file_that_cannot_be_read_gives_the_stricter_value_and_says_so(where):
    inst, comm = where["instance_file"], where["data_folder"] / "limits.json"
    assert _eff(**where).note == ""                                                # absent files are no layer and no note
    for text in ("", '{"version": 1, "limits": {"upload.max', "[]", "not json", '{"limits": []}'):
        inst.parent.mkdir(parents=True, exist_ok=True)
        inst.write_text(text, encoding="utf-8")
        got = _eff(**where)
        assert got.value == 100 * MB and got.unreadable == ("the instance limits file",) and "could not read" in got.note, text
        # a community asking for more than the default is held to it, since the ceiling is unknown
        _file(comm, {KEY: {"value": 300 * MB}})
        assert _eff(**where).value == 100 * MB
        _file(comm, {KEY: {"value": 20 * MB}})
        assert _eff(**where).value == 20 * MB                                      # asking for less is honored
        comm.unlink()
    inst.unlink()
    comm.write_text("{", encoding="utf-8")
    _file(inst, {KEY: {"value": 30 * MB}})
    assert _eff(**where).value == 30 * MB and _eff(**where).unreadable == ("this community's limits file",)


def test_a_switch_keeps_its_default_when_a_file_is_unreadable_and_an_unknown_key_is_kept(where):
    key = "split.auto_read"
    assert _eff(key, **where).value is True
    where["instance_file"].parent.mkdir(parents=True, exist_ok=True)
    where["instance_file"].write_text("{", encoding="utf-8")
    assert _eff(key, **where).value is True                                        # the built-in value, never looser
    _file(where["data_folder"] / "limits.json", {key: {"value": False}})
    assert _eff(key, **where).value is False                                       # the stricter of what could be read
    (where["data_folder"] / "limits.json").unlink()
    _file(where["data_folder"] / "limits.json", {"future.key": {"value": 3}})
    limits.set_limits({KEY: "40MB"}, scope="community", reason="r", by="b", dry_run=False, data_folder=where["data_folder"],
                      instance_file=where["instance_file"].with_name("other.json"))
    kept = json.loads((where["data_folder"] / "limits.json").read_text(encoding="utf-8"))["limits"]
    assert kept["future.key"] == {"value": 3} and kept[KEY]["value"] == 40 * MB


def test_the_profile_layer_and_the_environment_keep_their_old_places(where, monkeypatch):
    from types import SimpleNamespace

    profile = SimpleNamespace(slug="", limits=lambda: {KEY: 5 * MB})
    assert _eff(community=profile, **where).source == "community"
    _file(where["data_folder"] / "limits.json", {KEY: {"value": 7 * MB}})
    assert _eff(community=profile, **where).value == 7 * MB                        # the file is the last word
    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", str(2 * MB))
    assert _eff(community=SimpleNamespace(slug="", limits=lambda: {KEY: 5 * MB}), data_folder=where["data_folder"] / "none",
                instance_file=where["instance_file"]).source == "env"


# --- check and its words -----------------------------------------------------------------------------------------------------

def test_check_returns_within_and_refuses_over_in_words(where):
    assert limits.check(KEY, 100 * MB, **where).value == 100 * MB
    with pytest.raises(LimitReached) as hit:
        limits.check(KEY, 140 * MB, **where)
    words = hit.value.words
    assert "140 MB" in words and "limit is 100 MB" in words and "Nothing was saved" in words and "administrator" in words
    assert KEY not in words and "upload.max" not in words and "/" not in words and isinstance(hit.value, ValueError)
    assert (hit.value.key, hit.value.limit, hit.value.source) == (KEY, 100 * MB, "default")
    with pytest.raises(LimitReached, match="off"):
        _file(where["data_folder"] / "limits.json", {"split.auto_read": {"value": False}})
        limits.check("split.auto_read", True, **where)
    limits.check("split.auto_read", False, **where)


def test_every_registered_refusal_reads_in_words_with_no_key_or_path(where):
    for l in limits.LIMITS:
        if l.key in (CAP, OPS):
            continue
        amount = True if l.unit == "switch" else l.top + 1
        _file(where["data_folder"] / "limits.json", {l.key: {"value": False if l.unit == "switch" else l.default}})
        with pytest.raises(LimitReached) as hit:
            limits.check(l.key, amount, **where)
        text = hit.value.words
        assert text and l.key not in text and "{" not in text and "\\" not in text and "/" not in text, text


def test_the_upload_refusal_is_the_registrys_words_and_names_no_file(where, monkeypatch):
    from jason.tasks import record_upload as up

    monkeypatch.setenv("JASON_LIMIT_UPLOAD_MAX_BYTES", str(MB))
    with pytest.raises(ValueError) as hit:
        up.check("Private Name.pdf", b"%PDF-" + b"x" * (3 * MB))
    assert "limit is 1 MB" in str(hit.value) and "Private" not in str(hit.value) and "Nothing was saved" in str(hit.value)


# --- the one writer ----------------------------------------------------------------------------------------------------------

def _set(where, changes, scope="community", dry_run=False, **kw):
    return limits.set_limits(changes, scope=scope, reason=kw.pop("reason", "because"), by=kw.pop("by", "A. Person"), dry_run=dry_run,
                             data_folder=where["data_folder"], instance_file=where["instance_file"], **kw)


def test_a_dry_run_writes_nothing_and_apply_writes_the_file_and_one_line(where):
    comm = where["data_folder"] / "limits.json"
    out = _set(where, {KEY: "50MB"}, dry_run=True)
    assert out["dryRun"] is True and not comm.exists() and not (where["data_folder"] / limits.LOG_NAME).exists()
    assert "100 MB (default) -> 50 MB" in out["changes"][0]["words"] and "never removes or hides" in out["changes"][0]["words"]
    out = _set(where, {KEY: "50MB"})
    assert out["dryRun"] is False and out["changes"][0]["now"] == 50 * MB
    entry = json.loads(comm.read_text(encoding="utf-8"))["limits"][KEY]
    assert entry["value"] == 50 * MB and entry["by"] == "A. Person" and entry["reason"] == "because" and entry["at"].endswith("Z")
    (line,) = limits.read_log("community", data_folder=where["data_folder"])
    assert {"at", "kind", "scope", "key", "from", "to", "reason", "by", "via"} <= set(line)
    assert (line["kind"], line["scope"], line["key"], line["from"], line["to"], line["via"]) == ("set", "community", KEY, 100 * MB, 50 * MB, "cli")
    assert str(where["data_folder"]) not in json.dumps(line)                       # no path, no file name
    assert limits.read_log("community", key="nope", data_folder=where["data_folder"]) == []


def test_a_reason_and_a_name_are_required_and_a_refusal_writes_nothing(where):
    comm = where["data_folder"] / "limits.json"
    for kw in ({"reason": ""}, {"by": " "}):
        with pytest.raises(LimitRefused, match="reason and a name"):
            _set(where, {KEY: "50MB"}, **kw)
    for changes, match in (({KEY: "1KB"}, "below the lowest"), ({KEY: "9GB"}, "above 500 MB"), ({KEY: "unlimited"}, "no unlimited"),
                           ({OPS: "5m"}, "only the instance"), ({CAP: "151"}, "above 150"), ({KEY: "50MB", CAP: "999"}, "above 150")):
        with pytest.raises(LimitRefused, match=match):
            _set(where, changes)
    assert not comm.exists() and not (where["data_folder"] / limits.LOG_NAME).exists()
    with pytest.raises(LimitRefused) as hit:
        _set(where, {KEY: "9GB"})
    assert hit.value.nearest == 500 * MB
    with pytest.raises(KeyError):
        _set(where, {"nope.key": "1"})


def test_a_community_cannot_set_past_the_instances_ceiling_and_the_instance_sets_one(where):
    _set(where, {KEY: "40MB"}, scope="instance", ceiling="120MB")
    inst = json.loads(where["instance_file"].read_text(encoding="utf-8"))["limits"][KEY]
    assert (inst["value"], inst["ceiling"]) == (40 * MB, 120 * MB)
    _set(where, {KEY: "110MB"})
    assert _eff(**where).value == 110 * MB
    with pytest.raises(LimitRefused, match="above the operator's limit of 120 MB") as hit:
        _set(where, {KEY: "130MB"})
    assert hit.value.nearest == 120 * MB
    with pytest.raises(LimitRefused, match="above its own ceiling"):
        _set(where, {KEY: "60MB"}, scope="instance", ceiling="50MB")
    with pytest.raises(LimitRefused, match="only in the instance"):
        _set(where, {KEY: "60MB"}, ceiling="70MB")
    # the operator lowers the ceiling under the community's value: the community's file stays, the read is clamped
    _set(where, {KEY: "30MB"}, scope="instance", ceiling="60MB")
    got = _eff(**where)
    assert got.value == 60 * MB and got.clamped is True
    assert json.loads((where["data_folder"] / "limits.json").read_text(encoding="utf-8"))["limits"][KEY]["value"] == 110 * MB


def test_several_changes_are_one_write_with_one_reason_and_a_reset_goes_back_to_the_layer_above(where):
    _set(where, {KEY: "40MB", "split.auto_read": "off"}, reason="small host")
    lines = limits.read_log("community", data_folder=where["data_folder"])
    assert [l["key"] for l in lines] == [KEY, "split.auto_read"] and {l["reason"] for l in lines} == {"small host"}
    assert len({l["at"] for l in lines}) == 1
    out = limits.reset_limits([KEY], scope="community", reason="back", by="A", dry_run=True, data_folder=where["data_folder"],
                              instance_file=where["instance_file"])
    assert out["dryRun"] and _eff(**where).value == 40 * MB
    limits.reset_limits([KEY], scope="community", reason="back", by="A", dry_run=False, data_folder=where["data_folder"],
                        instance_file=where["instance_file"])
    assert _eff(**where).value == 100 * MB and _eff("split.auto_read", **where).value is False
    last = limits.read_log("community", key=KEY, data_folder=where["data_folder"])[-1]
    assert (last["kind"], last["from"], last["to"]) == ("reset", 40 * MB, None)
    assert KEY not in json.loads((where["data_folder"] / "limits.json").read_text(encoding="utf-8"))["limits"]


def test_the_file_and_its_line_are_one_write_or_neither(where, monkeypatch):
    comm = where["data_folder"] / "limits.json"
    _set(where, {KEY: "40MB"})
    before, log_before = _hash(comm), _hash(where["data_folder"] / limits.LOG_NAME)

    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(limits, "_append_log", broken)
    with pytest.raises(OSError):
        _set(where, {KEY: "60MB"})
    assert _hash(comm) == before and _hash(where["data_folder"] / limits.LOG_NAME) == log_before
    assert not [p for p in where["data_folder"].iterdir() if p.suffix == ".tmp"]            # no staged file is left


def test_a_file_that_cannot_be_read_is_not_written_over(where):
    comm = where["data_folder"] / "limits.json"
    comm.write_text("{broken", encoding="utf-8")
    with pytest.raises(LimitRefused, match="cannot be read"):
        _set(where, {KEY: "40MB"})
    assert comm.read_text(encoding="utf-8") == "{broken"


# --- the command -------------------------------------------------------------------------------------------------------------

def _args(**kw):
    base = dict(key="", json=False, scope="", set=None, ceiling=None, reset=None, reason=None, by=None, yes=False, log=False)
    base.update(kw)
    return Namespace(**base)


def test_the_command_is_a_dry_run_until_yes_and_stops_without_a_reason_or_name(where, tmp_path, monkeypatch, capsys):
    from jason.commands import limits as cmd

    monkeypatch.setenv("JASON_LIMITS_FILE", str(where["instance_file"]))
    assert cmd.cmd_limits(_args(set=[f"{KEY}=50MB"], scope="instance", by="A")) == 2                 # no reason
    assert cmd.cmd_limits(_args(set=[f"{KEY}=50MB"], reason="r", by="A")) == 2                       # no scope
    assert cmd.cmd_limits(_args(set=["bad"], scope="instance", reason="r", by="A")) == 2
    capsys.readouterr()
    assert cmd.cmd_limits(_args(set=[f"{KEY}=50MB"], scope="instance", reason="r", by="A")) == 0
    out = capsys.readouterr()
    assert "A dry run: nothing was written" in out.out and not where["instance_file"].exists() and out.err.startswith("instance:")
    assert cmd.cmd_limits(_args(set=[f"{KEY}=9GB"], scope="instance", reason="r", by="A")) == 1
    assert "nearest allowed" in capsys.readouterr().err
    assert cmd.cmd_limits(_args(set=[f"{KEY}=50MB"], scope="instance", reason="r", by="A", yes=True)) == 0
    assert _eff(**{"instance_file": where["instance_file"], "data_folder": where["data_folder"]}).value == 50 * MB
    capsys.readouterr()
    assert cmd.cmd_limits(_args(scope="instance")) == 0 and "upload.max_bytes: 52428800" in capsys.readouterr().out
    assert cmd.cmd_limits(_args(scope="instance", log=True)) == 0 and "set  instance  upload.max_bytes" in capsys.readouterr().out
    assert cmd.cmd_limits(_args(reset=[KEY], scope="instance", reason="r", by="A", yes=True)) == 0
    assert not json.loads(where["instance_file"].read_text(encoding="utf-8"))["limits"]


# --- a model job is refused by the preflight before the GPU lane, whatever the limits ---------------------------------------

def test_a_model_job_is_refused_by_the_preflight_before_the_gpu_lock_whatever_the_limits(tmp_path, monkeypatch, where):
    _file(where["instance_file"], {KEY: {"value": 500 * MB, "ceiling": 500 * MB}})            # every limit as loose as it goes
    monkeypatch.setenv("JASON_LIMITS_FILE", str(where["instance_file"]))
    job = jobs.add(tmp_path, ["outlines", "--model"])
    held, ran = [], []

    real = jobs.hold

    def spy(resource, key="", **kw):
        if resource.value == "gpu" or key == jobs.GPU_LANE:
            held.append((resource.value, key))
        return real(resource, key, **kw)
    monkeypatch.setattr(jobs, "hold", spy)

    def not_ready(*a):
        raise RuntimeError("the machine is short of memory right now")
    counts = jobs.work(tmp_path, once=True, runner=lambda argv, log: ran.append(argv) or 0, preflight=not_ready, defer_for=0,
                       log=lambda s: None)
    waiting = jobs.get(tmp_path, job.id)
    assert counts["deferred"] == 1 and not ran and not held
    assert "short of memory" in waiting.note and "limit" not in waiting.note.lower()        # the preflight speaks in its own words
