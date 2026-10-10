"""Google refresh tokens: vault first, then the file; saved to both; migrated and reported without ever showing one."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from jason.community.profile import profile_name
from jason.google import GoogleAuthRequired, open_drive
from jason.google.scopes import GOOGLE_SCOPES, TASKS_SCOPES
from jason.google.session import open_scoped
from jason.google.tokens import (FileTokenStore, LayeredTokenStore, VaultTokenStore, migrate_tokens, name_of_file,
                                 plan_token_migration, status_lines, token_store)
from jason.secrets import KeeperAuthRequired
from jason.vault.paths import vault_path
from jason.vault.store import MemoryStore

SECRET_A = "1//made-up-refresh-AAAA"
SECRET_B = "1//made-up-refresh-BBBB"
SECRET_T = "1//made-up-refresh-TASKS"


class _Http:
    """Answers each refresh with an access token, and remembers which refresh token was sent."""

    def __init__(self, *, accept: bool = True) -> None:
        self.sent: list[str] = []
        self.accept = accept

    def post(self, url, *, data=None, content=None, headers=None):
        self.sent.append(str((data or {}).get("refresh_token", "")))
        body = {"access_token": "ya29.made-up"} if self.accept else {"error": "invalid_grant"}
        return httpx.Response(200 if self.accept else 400, content=json.dumps(body).encode())

    def get(self, *a, **k):  # pragma: no cover - not reached
        raise AssertionError("no GET")

    def close(self) -> None:
        return None


class _Factory:
    @classmethod
    def from_refresh_token(cls, *, client_id, client_secret, refresh_token, http=None):
        cls.refresh = refresh_token
        return cls()


def _community() -> str:
    return profile_name()


def _vault_with_client(token: dict | None = None, name: str = "drive") -> MemoryStore:
    store = MemoryStore()
    store.put(vault_path(_community(), "google-workspace", "oauth-client"),
              {"client_id": "id", "client_secret": "made-up-secret"})
    if token:
        VaultTokenStore(store, _community()).save(name, token["refresh_token"], token["scopes"])
    return store


def _settings(tmp_path: Path, name: str = "google-token.json") -> SimpleNamespace:
    return SimpleNamespace(google_oauth_record_uid="", google_oauth_token_file=tmp_path / "secrets" / name)


def _write_file(settings, name: str, refresh: str, scopes) -> None:
    FileTokenStore(settings.google_oauth_token_file).save(name, refresh, list(scopes))


def test_file_names_map_to_token_names():
    assert [name_of_file(f) for f in ("google-token.json", "google-tasks-token.json", "google-vault-token.json",
                                       "google-photos-token.json")] == ["drive", "tasks", "vault", "photos"]


def test_vault_path_follows_the_scheme():
    path = VaultTokenStore(MemoryStore(), "oakview").path_of("tasks")
    assert path == "jason/community/oakview/google-workspace/token/tasks"


def test_vault_first_beats_a_stale_file(tmp_path):
    settings = _settings(tmp_path)
    _write_file(settings, "drive", SECRET_B, GOOGLE_SCOPES)
    store = _vault_with_client({"refresh_token": SECRET_A, "scopes": list(GOOGLE_SCOPES)})
    http = _Http()
    open_drive(settings, object(), store=store, http=http)   # type: ignore[arg-type]
    assert http.sent == [SECRET_A]


def test_file_fallback_when_the_vault_holds_nothing(tmp_path):
    settings = _settings(tmp_path)
    _write_file(settings, "drive", SECRET_B, GOOGLE_SCOPES)
    http = _Http()
    open_drive(settings, object(), store=_vault_with_client(), http=http)   # type: ignore[arg-type]
    assert http.sent == [SECRET_B]


def test_worktree_case_vault_only_no_file_and_another_cwd(tmp_path, monkeypatch):
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    settings = _settings(tmp_path / "no-such-checkout")
    assert not settings.google_oauth_token_file.exists()
    store = _vault_with_client({"refresh_token": SECRET_A, "scopes": list(GOOGLE_SCOPES)})
    http = _Http()
    open_drive(settings, object(), store=store, http=http)   # type: ignore[arg-type]
    assert http.sent == [SECRET_A]
    assert not settings.google_oauth_token_file.exists()      # a read never writes a local file


def test_scoped_token_has_its_own_vault_name(tmp_path):
    settings = _settings(tmp_path)
    store = _vault_with_client({"refresh_token": SECRET_T, "scopes": list(TASKS_SCOPES)}, "tasks")
    open_scoped(settings, object(), _Factory, TASKS_SCOPES, "google-tasks-token.json", store=store)
    assert _Factory.refresh == SECRET_T


def test_scope_mismatch_needs_a_person_and_asks_only_when_interactive(tmp_path):
    settings = _settings(tmp_path)
    narrow = ["https://www.googleapis.com/auth/drive.readonly"]
    store = _vault_with_client({"refresh_token": SECRET_A, "scopes": narrow})

    def sign_in(*args, **kw):
        raise AssertionError("no browser when not interactive")

    with pytest.raises(GoogleAuthRequired, match="interactive"):
        open_drive(settings, object(), store=store, authorize=sign_in, http=_Http())   # type: ignore[arg-type]

    asked: list[str] = []

    def person(client_id, client_secret, path):
        asked.append(client_id)
        FileTokenStore(path).save("drive", SECRET_B, list(GOOGLE_SCOPES))
        return SECRET_B

    http = _Http()
    open_drive(settings, object(), store=store, authorize=person, http=http, interactive=True)   # type: ignore[arg-type]
    assert asked == ["id"] and http.sent == [SECRET_B]


def test_rejected_token_fails_fast_when_not_interactive(tmp_path):
    settings = _settings(tmp_path)
    store = _vault_with_client({"refresh_token": SECRET_A, "scopes": list(GOOGLE_SCOPES)})
    with pytest.raises(GoogleAuthRequired):
        open_drive(settings, object(), store=store, http=_Http(accept=False))   # type: ignore[arg-type]


def test_interactive_sign_in_saves_to_the_vault_alone(tmp_path):
    settings = _settings(tmp_path)
    store = _vault_with_client()

    def person(client_id, client_secret, path):
        FileTokenStore(path).save("drive", SECRET_A, list(GOOGLE_SCOPES))
        return SECRET_A

    open_drive(settings, object(), store=store, authorize=person, http=_Http(), interactive=True)   # type: ignore[arg-type]
    assert FileTokenStore(settings.google_oauth_token_file).load("drive") is None   # no local copy beside the vault
    assert not settings.google_oauth_token_file.exists()
    held = VaultTokenStore(store, _community()).load("drive")
    assert held["refresh_token"] == SECRET_A and set(GOOGLE_SCOPES) == set(held["scopes"])


def test_a_refused_vault_keeps_the_sign_in_in_the_local_file_rather_than_losing_it(tmp_path):
    settings = _settings(tmp_path)
    tokens = token_store(settings, _Refuses(), _community())
    assert tokens.save("drive", SECRET_A, list(GOOGLE_SCOPES)) == ("file",)
    assert FileTokenStore(settings.google_oauth_token_file).load("drive")["refresh_token"] == SECRET_A


class _Refuses(MemoryStore):
    def put(self, *a, **k):
        raise KeeperAuthRequired("sign in")


class _Down(MemoryStore):
    def get(self, path):
        raise KeeperAuthRequired("sign in")

    def put(self, *a, **k):
        raise KeeperAuthRequired("sign in")


def test_unreachable_vault_uses_the_file_and_logs_the_error_name_only(tmp_path, caplog):
    settings = _settings(tmp_path)
    _write_file(settings, "drive", SECRET_B, GOOGLE_SCOPES)
    tokens = LayeredTokenStore(VaultTokenStore(_Down(), "oakview"), FileTokenStore(settings.google_oauth_token_file))
    with caplog.at_level(logging.DEBUG):
        assert tokens.load("drive", GOOGLE_SCOPES)["refresh_token"] == SECRET_B
    assert "KeeperAuthRequired" in caplog.text and SECRET_B not in caplog.text


def test_unreachable_vault_and_no_file_is_the_vaults_error_never_a_miss(tmp_path):
    settings = _settings(tmp_path)
    tokens = LayeredTokenStore(VaultTokenStore(_Down(), "oakview"), FileTokenStore(settings.google_oauth_token_file))
    with pytest.raises(KeeperAuthRequired):
        tokens.load("drive", GOOGLE_SCOPES)
    # and a file token that lacks the scopes does not hide it either
    _write_file(settings, "drive", SECRET_B, ["https://www.googleapis.com/auth/drive.readonly"])
    with pytest.raises(KeeperAuthRequired):
        tokens.load("drive", GOOGLE_SCOPES)


def test_save_reaches_the_file_when_the_vault_is_down(tmp_path, caplog):
    settings = _settings(tmp_path)
    tokens = LayeredTokenStore(VaultTokenStore(_Down(), "oakview"), FileTokenStore(settings.google_oauth_token_file))
    with caplog.at_level(logging.DEBUG):
        assert tokens.save("drive", SECRET_A, list(GOOGLE_SCOPES)) == ("file",)
    assert SECRET_A not in caplog.text


# ----- migration and status -----


def _layered(tmp_path, store):
    settings = _settings(tmp_path)
    return settings, token_store(settings, store, "oakview")


def test_migrate_plan_writes_nothing_and_yes_copies_create_only(tmp_path):
    store = MemoryStore()
    settings, tokens = _layered(tmp_path, store)
    _write_file(settings, "drive", SECRET_A, GOOGLE_SCOPES)
    _write_file(settings, "tasks", SECRET_T, TASKS_SCOPES)
    (settings.google_oauth_token_file.parent / "google-token.before-scopes-2026-09-29.json").write_text(
        json.dumps({"refresh_token": "1//old", "scopes": []}), encoding="utf-8")
    steps = plan_token_migration(tokens, "oakview")
    assert {s.name: s.state for s in steps} == {"drive": "copy", "tasks": "copy", "vault": "no file", "photos": "no file"}
    assert store.list("jason/") == []                              # the plan wrote nothing
    results = migrate_tokens(steps, tokens, by="a person")
    assert {s.name: o for s, o in results} == {"drive": "copied; local file removed", "tasks": "copied; local file removed"}
    assert not settings.google_oauth_token_file.exists()           # the vault is the only copy now
    assert VaultTokenStore(store, "oakview").load("drive")["refresh_token"] == SECRET_A
    assert store.list("jason/") == ["jason/community/oakview/google-workspace/token/drive",
                                    "jason/community/oakview/google-workspace/token/tasks"]   # no backup copied
    # a second run has nothing left to do
    again = plan_token_migration(tokens, "oakview")
    assert {s.name: s.state for s in again}["drive"] == "no file"
    assert migrate_tokens(again, tokens) == []


def test_migrate_never_overwrites_a_path_set_between_plan_and_copy(tmp_path):
    store = MemoryStore()
    settings, tokens = _layered(tmp_path, store)
    _write_file(settings, "drive", SECRET_A, GOOGLE_SCOPES)
    steps = plan_token_migration(tokens, "oakview")
    VaultTokenStore(store, "oakview").save("drive", SECRET_B, list(GOOGLE_SCOPES))
    assert [o for _, o in migrate_tokens(steps, tokens)] == ["already in the vault; local file differs"]
    assert VaultTokenStore(store, "oakview").load("drive")["refresh_token"] == SECRET_B
    assert FileTokenStore(settings.google_oauth_token_file).load("drive")["refresh_token"] == SECRET_A   # kept: it differs


def test_status_names_the_source_and_scope_fit_and_holds_no_token(tmp_path):
    store = MemoryStore()
    settings, tokens = _layered(tmp_path, store)
    _write_file(settings, "drive", SECRET_A, ["https://www.googleapis.com/auth/drive.readonly"])
    VaultTokenStore(store, "oakview").save("tasks", SECRET_T, list(TASKS_SCOPES))
    text = "\n".join(status_lines(tokens))
    assert "drive: read from the file, 1 scopes, lacks scopes asked now" in text
    assert "tasks: read from the vault, 1 scopes, covers the scopes asked now" in text
    assert "vault: missing" in text and "photos: missing" in text
    assert SECRET_A not in text and SECRET_T not in text
    down = token_store(settings, _Down(), "oakview")
    text = "\n".join(status_lines(down))
    assert "KeeperAuthRequired" in text and SECRET_A not in text


def test_the_commands_print_no_token(monkeypatch, tmp_path, capsys):
    import jason.commands.vault as cv
    import jason.secrets as secrets

    store = MemoryStore()
    settings = _settings(tmp_path)
    _write_file(settings, "drive", SECRET_A, GOOGLE_SCOPES)

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(secrets.VaultSession, "from_settings", classmethod(lambda cls, *a, **k: _Session()))
    monkeypatch.setattr("jason.vault.keeper.KeeperStore.from_session", classmethod(lambda cls, s, **k: store))
    monkeypatch.setattr(cv, "_context", lambda args: (SimpleNamespace(record_uids={}, **vars(settings)), "oakview", ()))
    args = argparse.Namespace(action="migrate", yes=False, community="oakview", interactive=False)
    assert cv.run(args) == 0
    out = capsys.readouterr().out
    assert "drive -> jason/community/oakview/google-workspace/token/drive: copy" in out and "Nothing written" in out
    assert store.list("jason/") == []
    args.action = "status"
    assert cv.run(args) == 0
    out = capsys.readouterr().out
    assert "drive: read from the file" in out and SECRET_A not in out
