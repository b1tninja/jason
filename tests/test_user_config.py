"""jason's user config (~/.jason/.env): machine settings found from any working directory, under the project's own .env."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from jason import config
from jason.config import TEMP_ENV_VARS


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def user_config(monkeypatch, tmp_path):
    """A user config file of the test's own, no JASON_* setting in the environment, and the project's .env elsewhere."""
    path = tmp_path / "user.env"
    monkeypatch.setenv("JASON_CONFIG", str(path))
    for name in ("JASON_DATA_DIR", "JASON_TEMP_DIR", "JASON_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JASON_ENV", str(tmp_path / "no-project.env"))     # not the checkout's own .env
    monkeypatch.chdir(tmp_path)
    return path


def test_the_default_user_config_is_in_the_home_folder_not_appdata(monkeypatch):
    monkeypatch.delenv("JASON_CONFIG")
    found = config.user_config_path()
    assert found == Path.home() / ".jason" / ".env"
    assert "AppData" not in found.parts


def test_a_setting_is_found_in_the_user_config_from_any_working_directory(user_config, tmp_path, monkeypatch):
    _write(user_config, "JASON_DATA_DIR=D:/somewhere/data\n")
    assert config._env_value("JASON_DATA_DIR") == "D:/somewhere/data"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert config.data_root() == Path("D:/somewhere/data")


def test_the_projects_env_wins_over_the_user_config_and_the_environment_over_both(user_config, tmp_path, monkeypatch):
    _write(user_config, "JASON_DATA_DIR=D:/user\nKEEPER_USERNAME=user-name\n")
    project = _write(tmp_path / "project.env", "JASON_DATA_DIR=D:/project\n")
    monkeypatch.setenv("JASON_ENV", str(project))
    assert config._env_value("JASON_DATA_DIR") == "D:/project"
    monkeypatch.setenv("JASON_DATA_DIR", "D:/environment")
    assert config._env_value("JASON_DATA_DIR") == "D:/environment"


def test_settings_load_takes_what_the_project_lacks_from_the_user_config(user_config, tmp_path):
    _write(user_config, "KEEPER_USERNAME=machine-user\nPAYHOA_MY_MEMBERSHIP_ID=7\n")
    project = _write(tmp_path / "project.env", "PAYHOA_MY_MEMBERSHIP_ID=9\n")
    settings = config.Settings.load(project)
    assert settings.keeper_username == "machine-user"
    assert str(settings.payhoa_my_membership_id) == "9"


def test_a_missing_or_unreadable_user_config_sets_nothing(user_config, tmp_path):
    assert config._env_value("JASON_DATA_DIR") == ""
    user_config.mkdir()                              # a folder where the file should be
    assert config._env_value("JASON_DATA_DIR") == ""


def test_the_temp_setting_applies_from_the_user_config(user_config, tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    _write(user_config, f"JASON_TEMP_DIR={scratch.as_posix()}\n")
    keep = {name: os.environ.get(name) for name in TEMP_ENV_VARS}
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    monkeypatch.setattr(config, "_SYSTEM_TEMP", None)
    try:
        assert config.apply_temp_dir() == scratch
        assert Path(tempfile.gettempdir()) == scratch
    finally:
        for name, value in keep.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_the_profile_name_is_found_in_the_user_config(user_config):
    from jason.community.profile import profile_name

    _write(user_config, "JASON_PROFILE=mystique\n")
    assert profile_name() == "mystique"


def test_the_tests_themselves_read_no_user_config():
    assert not config.user_config_path().exists()
