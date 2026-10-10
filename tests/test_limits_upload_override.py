"""The per-act override at the upload point (jason.tasks.record_upload.upload, `jason records --upload --override`): one file past the
limit, once, by a community administrator with a reason; a key document's slot takes none; the temp-drive guard speaks first.
Fakes only: the phase-2 world, made-up files, no Drive."""

import json

import pytest

from jason import limits, storage
from jason.tasks import record_upload as up

from test_record_intake_phase2 import BY, world, store, slot_row, quiet_preflight  # noqa: F401
from test_record_intake_phase3 import BYL, MIN, _up

MB = 1024 * 1024


@pytest.fixture(autouse=True)
def _own_folders(tmp_path, monkeypatch):
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "limits-data"))
    monkeypatch.setenv("JASON_LIMITS_FILE", str(tmp_path / "home" / "limits.json"))
    monkeypatch.delenv("JASON_LIMIT_UPLOAD_MAX_BYTES", raising=False)


def _ov(allowed="6MB", reason="One large combined scan"):
    return limits.parse_override(f"upload.max_bytes={allowed}", reason=reason, by="A. Admin", what="an upload")


def _small_limit(world):
    world.community.limits = lambda: {"upload.max_bytes": 2 * MB}


def _big(n_mb):
    return b"%PDF-" + b"x" * (n_mb * MB)


def test_one_file_passes_a_small_limit_with_an_override_and_the_next_does_not(world):
    _small_limit(world)
    with pytest.raises(ValueError, match="the limit is 2 MB"):
        _up(world, data=_big(3))
    out = _up(world, data=_big(3), override=_ov(), read=False)
    assert out["ok"] and out["size"] > 2 * MB
    pin = next(p for p in rs_pins(world) if p["id"] == out["pin"])
    assert pin["limit_override"]["allowed"] == 6 * MB and pin["limit_override"]["limit"] == 2 * MB
    assert pin["limit_override"]["reason"] == "One large combined scan" and pin["limit_override"]["by"] == "A. Admin"
    (line,) = limits.read_log("community", community=world.community)
    assert line["kind"] == "override" and line["what"] == "an upload" and "Scan" not in json.dumps(line)
    assert limits.value("upload.max_bytes", community=world.community) == 2 * MB       # no setting was written
    with pytest.raises(ValueError, match="the limit is 2 MB"):
        _up(world, data=_big(3) + b"y", read=False)                                  # a different file: refused again


def rs_pins(world):
    return json.loads((world.spec / "example" / "records.json").read_text(encoding="utf-8"))["pins"]


def test_a_dry_run_with_an_override_says_so_and_leaves_no_line(world):
    _small_limit(world)
    out = _up(world, data=_big(3), override=_ov(), dry_run=True)
    assert out["dryRun"] and "allowed once" in out["would"]["limitOverride"]
    assert limits.read_log("community", community=world.community) == []


def test_an_override_without_a_reason_or_past_its_maximum_keeps_nothing(world):
    _small_limit(world)
    with pytest.raises(limits.LimitRefused, match="needs a reason"):
        _up(world, data=_big(3), override=_ov(reason=" "))
    with pytest.raises(limits.LimitRefused) as hit:
        _up(world, data=_big(3), override=_ov(allowed="400MB"))
    assert "The nearest allowed value is 250 MB" in hit.value.describe()
    assert not (world.root / "record-intake").exists()


def test_a_key_documents_slot_takes_no_override(world):
    _small_limit(world)
    with pytest.raises(ValueError, match="key document's file is held to the upload limit"):
        _up(world, slot=BYL, data=_big(3), override=_ov())
    assert not (world.root / "record-intake").exists()


def test_the_temp_drive_guard_speaks_first_and_an_override_cannot_get_past_it(world, monkeypatch):
    _small_limit(world)
    monkeypatch.setattr(storage, "free_bytes", lambda p: 1 * MB)
    with pytest.raises(storage.DriveShort, match="Nothing was saved"):
        _up(world, data=_big(3), override=_ov())
    assert limits.read_log("community", community=world.community) == []
    assert not (world.root / "record-intake").exists()


def test_the_command_takes_override_and_reason_and_names_the_refusal(world, capsys, tmp_path, monkeypatch):
    import argparse

    from jason.commands import record_slots as cmd

    _small_limit(world)
    path = tmp_path / "Big.pdf"
    path.write_bytes(_big(3))
    base = dict(upload=MIN, file=str(path), by="A. Admin", period="2099-06", note="", entry="", no_ocr=True, json=False, override=None,
                reason="", yes=False)
    args = argparse.Namespace(**{**base, "override": "upload.max_bytes=6MB"})
    assert cmd._upload(args, world.community, world.root, True, str) == 2                 # --override needs --reason
    args = argparse.Namespace(**{**base, "override": "upload.max_bytes=400MB", "reason": "Large scan"})
    assert cmd._upload(args, world.community, world.root, True, str) == 1
    assert "nearest allowed value is 250 MB" in capsys.readouterr().err
    args = argparse.Namespace(**{**base, "override": "upload.max_bytes=6MB", "reason": "Large scan"})
    assert cmd._upload(args, world.community, world.root, True, str) == 0
    assert "allowed once" in capsys.readouterr().out
