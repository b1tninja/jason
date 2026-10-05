"""ASSPY_HOME can come from jason's .env: asspy reads only the process environment (jason.asspy_home)."""

import os

from asspy import paths

from jason import asspy_home
from jason.community.placer.index import open_cache


def _no_home(monkeypatch, tmp_path):
    monkeypatch.setenv("ASSPY_HOME", "placeholder")
    monkeypatch.delenv("ASSPY_HOME")                       # undone at the end: the variable is absent again
    env = tmp_path / ".env"
    monkeypatch.setenv("JASON_ENV", str(env))
    return env


def test_env_file_names_the_home(monkeypatch, tmp_path):
    env = _no_home(monkeypatch, tmp_path)
    env.write_text(f"ASSPY_HOME={tmp_path / 'on-the-data-drive'}\n", encoding="utf-8")
    assert asspy_home.apply() == str(tmp_path / "on-the-data-drive")
    assert paths.home() == (tmp_path / "on-the-data-drive").resolve()


def test_the_process_environment_wins_over_the_env_file(monkeypatch, tmp_path):
    env = _no_home(monkeypatch, tmp_path)
    env.write_text(f"ASSPY_HOME={tmp_path / 'from-file'}\n", encoding="utf-8")
    monkeypatch.setenv("ASSPY_HOME", str(tmp_path / "from-environment"))
    assert asspy_home.apply() == str(tmp_path / "from-environment")
    assert paths.home() == (tmp_path / "from-environment").resolve()


def test_nothing_named_changes_nothing(monkeypatch, tmp_path):
    env = _no_home(monkeypatch, tmp_path)
    env.write_text("KEEPER_USERNAME=someone\n", encoding="utf-8")
    assert asspy_home.apply() == ""
    assert "ASSPY_HOME" not in os.environ


def test_placer_cache_lands_under_the_named_home(monkeypatch, tmp_path):
    env = _no_home(monkeypatch, tmp_path)
    env.write_text(f"ASSPY_HOME={tmp_path / 'asspy'}\n", encoding="utf-8")
    open_cache()
    assert (tmp_path / "asspy" / "counties" / "placer" / "index.db").is_file()
