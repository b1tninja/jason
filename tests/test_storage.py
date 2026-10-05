"""JASON_TEMP_DIR (jason.config.apply_temp_dir) and `jason storage`."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from jason import config, storage
from jason.config import TEMP_ENV_VARS, TempDirError, apply_temp_dir

GB = 1024 ** 3


@pytest.fixture
def clean_temp(monkeypatch, tmp_path):
    """No JASON_TEMP_DIR anywhere, and the process's temp settings restored after the test."""
    keep = {name: os.environ.get(name) for name in TEMP_ENV_VARS}
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    monkeypatch.setattr(config, "_SYSTEM_TEMP", None)
    monkeypatch.delenv("JASON_TEMP_DIR", raising=False)
    monkeypatch.setenv("JASON_ENV", str(tmp_path / "no.env"))       # no .env supplies one
    yield
    for name, value in keep.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_setting_points_tempfile_and_the_environment_at_the_folder(clean_temp, monkeypatch, tmp_path):
    target = tmp_path / "scratch" / "tmp"
    monkeypatch.setenv("JASON_TEMP_DIR", str(target))
    assert apply_temp_dir() == target
    assert target.is_dir()
    assert tempfile.gettempdir() == str(target)
    for name in TEMP_ENV_VARS:
        assert os.environ[name] == str(target)
    with tempfile.TemporaryDirectory() as made:
        assert Path(made).parent == target
    assert apply_temp_dir() == target                                # idempotent


def test_a_child_process_inherits_it(clean_temp, monkeypatch, tmp_path):
    target = tmp_path / "child"
    monkeypatch.setenv("JASON_TEMP_DIR", str(target))
    apply_temp_dir()
    out = subprocess.run([sys.executable, "-c", "import tempfile; print(tempfile.gettempdir())"],
                         capture_output=True, text=True, check=True).stdout.strip()
    assert Path(out) == target


def test_unset_changes_nothing(clean_temp):
    before = (tempfile.tempdir, {n: os.environ.get(n) for n in TEMP_ENV_VARS})
    assert apply_temp_dir() is None
    assert (tempfile.tempdir, {n: os.environ.get(n) for n in TEMP_ENV_VARS}) == before


def test_a_relative_value_is_taken_from_the_data_roots_parent(clean_temp, monkeypatch, tmp_path):
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "checkout" / "data"))
    monkeypatch.setenv("JASON_TEMP_DIR", "scratch/tmp")
    assert apply_temp_dir() == tmp_path / "checkout" / "scratch" / "tmp"


def test_the_setting_is_read_from_the_env_file(clean_temp, monkeypatch, tmp_path):
    env = tmp_path / "x.env"
    env.write_text(f"JASON_TEMP_DIR={tmp_path / 'from-env-file'}\n", encoding="utf-8")      # unquoted: backslashes stay
    assert apply_temp_dir(env) == tmp_path / "from-env-file"
    assert config.Settings.load(env).temp_dir == str(tmp_path / "from-env-file")


def test_a_double_quoted_backslash_path_is_explained(clean_temp, tmp_path):
    env = tmp_path / "q.env"
    env.write_text('JASON_TEMP_DIR="D:\\scratch\\jason\\tmp"\n', encoding="utf-8")           # dotenv reads \s \j \t as escapes
    with pytest.raises(TempDirError, match="control character"):
        apply_temp_dir(env)


@pytest.mark.skipif(os.name != "nt", reason="drive letters")
def test_a_missing_drive_fails_fast_and_changes_nothing(clean_temp, monkeypatch):
    missing = next(c for c in "ZYXWVUTSRQ" if not Path(f"{c}:\\").exists())
    monkeypatch.setenv("JASON_TEMP_DIR", f"{missing}:\\scratch")
    before = tempfile.tempdir
    with pytest.raises(TempDirError, match="does not exist"):
        apply_temp_dir()
    assert tempfile.tempdir == before


def test_a_folder_that_cannot_be_made_fails_fast(clean_temp, monkeypatch, tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("JASON_TEMP_DIR", str(blocker / "tmp"))
    with pytest.raises(TempDirError):
        apply_temp_dir()


def test_the_exit_form_prints_the_reason(clean_temp, monkeypatch, tmp_path, capsys):
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("JASON_TEMP_DIR", str(blocker / "tmp"))
    with pytest.raises(SystemExit) as stop:
        config.apply_temp_dir_or_exit()
    assert stop.value.code == 2
    assert "JASON_TEMP_DIR" in capsys.readouterr().err


def test_importing_jason_does_not_apply_it(tmp_path):
    env = {**os.environ, "JASON_TEMP_DIR": str(tmp_path / "never-made"), "JASON_ENV": str(tmp_path / "no.env")}
    code = ("import tempfile, jason, jason.config, jason.cli, jason.jobs; "
            "print(tempfile.tempdir); import os; print(os.environ.get('SQLITE_TMPDIR'))")
    env.pop("SQLITE_TMPDIR", None)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=True,
                         cwd=str(Path(__file__).resolve().parents[1])).stdout.split()
    assert "never-made" not in out[0] and out[1] == "None"
    assert not (tmp_path / "never-made").exists()


def test_the_cli_applies_it_when_a_command_runs(clean_temp, monkeypatch, tmp_path):
    from jason.cli import _apply_temp_dir

    target = tmp_path / "cli"
    monkeypatch.setenv("JASON_TEMP_DIR", str(target))
    _apply_temp_dir(type("Args", (), {"env": None})())
    assert tempfile.gettempdir() == str(target)


def test_storage_reports_a_bad_setting_instead_of_failing_to_start(clean_temp, monkeypatch, tmp_path):
    from jason.cli import _apply_temp_dir

    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("JASON_TEMP_DIR", str(blocker / "tmp"))
    _apply_temp_dir(type("Args", (), {"env": None, "reports_temp_dir": True})())
    with pytest.raises(TempDirError):
        _apply_temp_dir(type("Args", (), {"env": None})())


def test_pytest_puts_tmp_path_under_the_setting(tmp_path_factory):
    configured = config.temp_dir_setting()
    if not configured:
        pytest.skip("JASON_TEMP_DIR is not set for this run")
    root = config.resolve_temp_dir(configured).resolve()
    assert root in tmp_path_factory.getbasetemp().resolve().parents


# ----- jason storage -----

def _report(tmp_path: Path, free: dict[str, int], **kwargs):
    """A report on made-up drives: ``free`` maps a drive to its free bytes."""
    return storage.report(tmp_path / "data", sizes=False, free=lambda p: free.get(storage.drive_of(p), 500 * GB), **kwargs)


def test_a_place_on_a_low_drive_is_flagged(clean_temp, monkeypatch, tmp_path):
    monkeypatch.setenv("JASON_TEMP_DIR", str(tmp_path / "tmp"))
    drive = storage.drive_of(tmp_path)
    rep = _report(tmp_path, {drive: 3 * GB})
    assert any(f"{drive} has 3.0 GB free" in line for line in rep["problems"])
    assert any(p["name"].strip() == "data directory" and p["drive"] == drive for p in rep["places"])


def test_roomy_drives_are_no_problem(clean_temp, monkeypatch, tmp_path):
    monkeypatch.setenv("JASON_TEMP_DIR", str(tmp_path / "tmp"))
    rep = _report(tmp_path, {})
    assert rep["problems"] == []
    assert "every place has at least 20 GB free" in storage.lines(rep)[-1]


@pytest.mark.skipif(os.name != "nt", reason="drive letters")
def test_unset_temp_on_the_small_drive_is_flagged(clean_temp, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_SYSTEM_TEMP", "Q:\\fake-temp")
    free = {"Q:": 40 * GB}                     # above the floor, but smaller than the data directory's drive
    rep = storage.report(tmp_path / "data", sizes=False, free=lambda p: free.get(storage.drive_of(p), 500 * GB))
    text = "\n".join(rep["problems"])
    assert "JASON_TEMP_DIR is unset" in text and "Q:" in text


def test_system_temp_sharing_the_low_data_drive_is_flagged(clean_temp, tmp_path, monkeypatch):
    drive = storage.drive_of(tmp_path)
    monkeypatch.setattr(config, "_SYSTEM_TEMP", str(tmp_path / "temp"))
    rep = _report(tmp_path, {drive: 5 * GB})
    assert any("system temp folder" in line and "data directory's drive" in line for line in rep["problems"])


def test_a_bad_setting_is_a_problem(clean_temp, monkeypatch, tmp_path):
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("JASON_TEMP_DIR", str(blocker / "tmp"))
    rep = _report(tmp_path, {})
    assert any("JASON_TEMP_DIR" in line and "cannot be created" in line for line in rep["problems"])


def test_the_command_exits_1_on_a_problem_and_prints_json(clean_temp, monkeypatch, tmp_path, capsys):
    from jason.commands import storage as command

    monkeypatch.setenv("JASON_TEMP_DIR", str(tmp_path / "tmp"))
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(storage, "free_bytes", lambda p: 1 * GB)
    args = type("Args", (), {"env": None, "no_sizes": True, "min_free_gb": 20.0, "json": True, "check": True})()
    assert command.cmd_storage(args) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["problems"] and data["places"][0]["name"] == "data directory"
    args.check = False
    assert command.cmd_storage(args) == 0


def test_sizes_count_the_files_below_a_folder(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "one.bin").write_bytes(b"x" * 100)
    (tmp_path / "a" / "b" / "two.bin").write_bytes(b"y" * 50)
    assert storage.folder_size(tmp_path / "a") == 150
    assert storage.folder_size(tmp_path / "a" / "one.bin") == 100
    assert storage.folder_size(tmp_path / "missing") == 0


def test_storage_reports_the_asspy_home_the_env_file_names(clean_temp, monkeypatch, tmp_path):
    pytest.importorskip("asspy")
    home = tmp_path / "counties-here"
    env = tmp_path / "named.env"
    env.write_text(f"ASSPY_HOME={home.as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("JASON_ENV", str(env))
    monkeypatch.delenv("ASSPY_HOME", raising=False)
    try:
        rep = storage.report(tmp_path, sizes=False)
        named = [p for p in rep["places"] if p["name"].startswith("ASSPY_HOME")]
        assert named and Path(named[0]["path"]) == home
    finally:
        os.environ.pop("ASSPY_HOME", None)           # apply() set it in the process
