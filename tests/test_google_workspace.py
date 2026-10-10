"""jason google: a community's own Google Workspace. Fake vault, made-up client files, no network, no browser."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import jason.commands.google as gc
from jason.community.base import GoogleWorkspace
from jason.google import workspace
from jason.google.errors import GoogleError
from jason.google.scopes import GOOGLE_SCOPES, SCOPE_PURPOSES, TASKS_SCOPES
from jason.google.session import oauth_client, open_drive
from jason.google.tokens import (FileTokenStore, VaultTokenStore, migrate_tokens, plan_token_migration, token_store)
from jason.secrets import KeeperAuthRequired
from jason.vault.paths import vault_path
from jason.vault.store import MemoryStore

CLIENT_ID = "made-up-id.apps.example"
CLIENT_SECRET = "made-up-client-secret-XYZ"
REFRESH = "1//made-up-refresh-GW"
INSTALL_ID, INSTALL_SECRET = "installation-id.apps.example", "installation-secret-QQQ"
SECRETS = (CLIENT_ID, CLIENT_SECRET, REFRESH, INSTALL_ID, INSTALL_SECRET)


class Store(MemoryStore):
    """A MemoryStore that also reads the ``.env`` record by UID, like KeeperStore."""

    def __init__(self, record: dict | None = None) -> None:
        super().__init__()
        self.record = record or {}
        self.refuse_puts = False

    def load_by_uid(self, uid: str) -> dict:
        return dict(self.record)

    def put(self, path, value, if_version=None, *, by=""):
        if self.refuse_puts and "/token/" in path:
            raise KeeperAuthRequired("sign in")
        return super().put(path, value, if_version, by=by)


def _download(tmp_path: Path, kind: str = "installed", **body) -> Path:
    inner = {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "project_id": "oakview-hoa"} | body
    inner = {k: v for k, v in inner.items() if v is not None}
    path = tmp_path / "client_secret_made-up.json"
    path.write_text(json.dumps({kind: inner}), encoding="utf-8")
    return path


@pytest.fixture
def world(tmp_path, monkeypatch):
    """The command module over a fake vault, a settings object, a terminal, and the profile ``oakview``."""
    store = Store()
    settings = SimpleNamespace(google_oauth_record_uid="", record_uids={}, google_installation_client=True,
                               google_oauth_token_file=tmp_path / "secrets" / "google-token.json")

    @contextmanager
    def vault(_settings, interactive=False):
        yield store, object()

    monkeypatch.setattr(gc, "_vault", vault)
    monkeypatch.setattr(gc, "_settings", lambda args: settings)
    monkeypatch.setattr("jason.commands.integrations.at_terminal", lambda: True)
    monkeypatch.setattr("jason.community.profile.profile_name", lambda: "oakview")
    monkeypatch.setattr("getpass.getuser", lambda: "an.admin")
    workspace._noted.clear()
    return SimpleNamespace(store=store, settings=settings, tmp=tmp_path)


def _run(action: str, **kw) -> int:
    base = dict(action=action, from_file="", project="", replace=False, yes=False, name="drive", again=False,
                interactive=False, env=None)
    return gc.run(SimpleNamespace(**(base | kw)))


def _own_path(community: str = "oakview") -> str:
    return vault_path(community, "google-workspace", "oauth-client")


def _put_client(store, community: str = "oakview") -> None:
    store.put(_own_path(community), {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "project_id": "oakview-hoa"})


def _clean(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text


# ----- the command is registered -----


def test_the_command_is_registered_and_the_name_was_free():
    import jason.cli as cli

    args = cli.build_parser().parse_args(["google", "status"])
    assert args.command == "google" and args.action == "status"


# ----- setup -----


def test_setup_dry_run_writes_nothing(world, capsys):
    path = _download(world.tmp)
    assert _run("setup", from_file=str(path)) == 0
    out = capsys.readouterr().out
    assert "Nothing written" in out and _own_path() in out
    assert world.store.get(_own_path()) is None
    _clean(out)


def test_setup_yes_writes_the_three_fields_and_echoes_none(world, capsys):
    path = _download(world.tmp)
    assert _run("setup", from_file=str(path), yes=True) == 0
    out = capsys.readouterr()
    stored = world.store.get(_own_path())
    assert dict(stored) == {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "project_id": "oakview-hoa"}
    _clean(out.out + out.err)


def test_setup_is_create_only_without_replace(world, capsys):
    path = _download(world.tmp)
    assert _run("setup", from_file=str(path), yes=True) == 0
    other = _download(world.tmp, client_secret="a-different-made-up-secret")
    assert _run("setup", from_file=str(other), yes=True) == 2
    assert world.store.get(_own_path())["client_secret"] == CLIENT_SECRET
    assert "--replace" in capsys.readouterr().err
    assert _run("setup", from_file=str(other), yes=True, replace=True) == 0
    assert world.store.get(_own_path())["client_secret"] == "a-different-made-up-secret"
    assert "sign in again" in capsys.readouterr().out


def test_setup_yes_needs_a_person_at_a_terminal(world, monkeypatch, capsys):
    monkeypatch.setattr("jason.commands.integrations.at_terminal", lambda: False)
    assert _run("setup", from_file=str(_download(world.tmp)), yes=True) == 2
    assert world.store.get(_own_path()) is None


def test_setup_hidden_prompt_takes_the_id_and_secret_without_echo(world, monkeypatch, capsys):
    answers = iter([CLIENT_ID, CLIENT_SECRET])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))
    assert _run("setup", yes=True, project="oakview-hoa") == 0
    assert world.store.get(_own_path())["client_id"] == CLIENT_ID
    out = capsys.readouterr()
    _clean(out.out + out.err)


@pytest.mark.parametrize("content,named", [
    ("not json at all", "not JSON"),
    (json.dumps({"web": {"client_id": "x", "client_secret": "y"}}), "Web application client"),
    (json.dumps({"other": {}}), "no \"installed\" client"),
    (json.dumps({"installed": {"client_id": CLIENT_ID}}), "installed.client_secret missing"),
    (json.dumps([1, 2]), "not a Google OAuth client download"),
])
def test_a_malformed_client_file_gives_a_named_error(world, capsys, content, named):
    path = world.tmp / "client_secret_bad.json"
    path.write_text(content, encoding="utf-8")
    assert _run("setup", from_file=str(path), yes=True) == 2
    err = capsys.readouterr().err
    assert named in err and "client_secret_bad.json" in err
    assert world.store.get(_own_path()) is None
    assert CLIENT_ID not in err


def test_a_missing_client_file_is_named(world, capsys):
    assert _run("setup", from_file=str(world.tmp / "nope.json")) == 2
    assert "cannot be read" in capsys.readouterr().err


# ----- adopt-installation-record -----


def test_adopt_copies_only_on_yes(world, capsys):
    world.settings.record_uids = {"google_oauth_record_uid": "UID1"}
    world.store.record = {"client_id": INSTALL_ID, "client_secret": INSTALL_SECRET}
    assert _run("adopt-installation-record") == 0
    assert world.store.get(_own_path()) is None
    _clean(capsys.readouterr().out)
    assert _run("adopt-installation-record", yes=True) == 0
    assert world.store.get(_own_path())["client_id"] == INSTALL_ID
    out = capsys.readouterr().out
    _clean(out)
    assert _run("adopt-installation-record", yes=True) == 0          # create only: left alone
    assert "left alone" in capsys.readouterr().out


def test_adopt_with_no_env_record_says_so(world, capsys):
    assert _run("adopt-installation-record", yes=True) == 2
    assert "google_oauth_record_uid" in capsys.readouterr().err


# ----- status -----


def test_status_says_when_the_client_is_the_installations_record(world, capsys):
    world.settings.record_uids = {"google_oauth_record_uid": "UID1"}
    assert _run("status") == 0
    out = capsys.readouterr().out
    assert "this is the installation's record, not this community's" in out
    assert "adopt-installation-record" in out


def test_status_when_the_installation_fallback_is_off(world, capsys):
    world.settings.record_uids = {"google_oauth_record_uid": "UID1"}
    world.settings.google_installation_client = False
    _run("status")
    assert "turns it off" in capsys.readouterr().out


def test_status_names_the_community_client_tokens_and_missing_scopes(world, capsys, caplog):
    _put_client(world.store)
    VaultTokenStore(world.store, "oakview").save("drive", REFRESH, list(GOOGLE_SCOPES)[:3])
    with caplog.at_level(logging.DEBUG):
        assert _run("status") == 0
    out = capsys.readouterr().out
    assert f"in this community's vault ({_own_path()}); project oakview-hoa" in out
    assert "drive: read from the vault; missing scopes:" in out and "documents" in out
    assert "tasks: no token" in out
    _clean(out + caplog.text)


def test_status_flags_a_token_kept_in_a_local_file(world, capsys):
    _put_client(world.store)
    FileTokenStore(world.settings.google_oauth_token_file).save("drive", REFRESH, list(GOOGLE_SCOPES))
    _run("status")
    out = capsys.readouterr().out
    assert "a local file" in out and "jason vault migrate --yes" in out
    _clean(out)


def test_status_shows_a_profiles_domain_pin(world, capsys, monkeypatch):
    monkeypatch.setattr(gc, "_pins", lambda: GoogleWorkspace(domain="example.org", note="Ask the treasurer."))
    _run("status")
    out = capsys.readouterr().out
    assert "example.org" in out and "Ask the treasurer." in out


# ----- scopes -----


def test_every_scope_asked_has_a_purpose_and_an_api(capsys):
    from jason.google.tokens import NAMES, scopes_of

    assert _run("scopes") == 0
    out = capsys.readouterr().out
    for name in NAMES:
        assert name in out
        for scope in scopes_of(name):
            assert scope in SCOPE_PURPOSES and SCOPE_PURPOSES[scope][1] in out


# ----- sign-in -----


def test_sign_in_non_interactive_fails_fast_and_touches_no_vault(world, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("no vault, no browser")

    monkeypatch.setattr(gc, "_vault", boom)
    monkeypatch.setattr(gc, "authorize_in_browser", boom)
    assert _run("sign-in") == 2
    err = capsys.readouterr().err
    assert "needs a browser" in err and "interactive" in err


def test_sign_in_states_the_scopes_before_the_browser_and_saves_to_the_vault_alone(world, monkeypatch, capsys):
    _put_client(world.store)
    said_before_browser: list[str] = []

    def person(client_id, client_secret, path, *, scopes):
        said_before_browser.append(capsys.readouterr().out)
        FileTokenStore(path).save("tasks", REFRESH, list(scopes))
        return REFRESH

    monkeypatch.setattr(gc, "authorize_in_browser", person)
    assert _run("sign-in", name="tasks", interactive=True) == 0
    assert "a browser will open for consent to 1 scopes" in said_before_browser[0]
    assert "100 refresh tokens" in said_before_browser[0] and "tasks" in said_before_browser[0]
    held = VaultTokenStore(world.store, "oakview").load("tasks")
    assert held["refresh_token"] == REFRESH and held["scopes"] == list(TASKS_SCOPES)
    assert not list(world.tmp.rglob("*token*.json"))                   # no local copy anywhere
    out = capsys.readouterr()
    assert "saved in the vault" in out.out
    _clean(out.out + out.err + said_before_browser[0])


def test_sign_in_says_already_signed_in_unless_again(world, monkeypatch, capsys):
    _put_client(world.store)
    VaultTokenStore(world.store, "oakview").save("tasks", REFRESH, list(TASKS_SCOPES))
    calls: list[int] = []

    def person(client_id, client_secret, path, *, scopes):
        calls.append(1)
        FileTokenStore(path).save("tasks", "1//made-up-second", list(scopes))
        return "1//made-up-second"

    monkeypatch.setattr(gc, "authorize_in_browser", person)
    assert _run("sign-in", name="tasks", interactive=True) == 0
    assert "already signed in" in capsys.readouterr().out and not calls
    assert _run("sign-in", name="tasks", interactive=True, again=True) == 0
    assert calls and VaultTokenStore(world.store, "oakview").load("tasks")["refresh_token"] == "1//made-up-second"


def test_sign_in_without_a_client_points_at_setup(world, monkeypatch, capsys):
    monkeypatch.setattr(gc, "authorize_in_browser", lambda *a, **k: pytest.fail("no browser without a client"))
    assert _run("sign-in", interactive=True) == 2
    assert "jason google setup" in capsys.readouterr().err


def test_sign_in_needs_a_terminal(world, monkeypatch, capsys):
    monkeypatch.setattr("jason.commands.integrations.at_terminal", lambda: False)
    assert _run("sign-in", interactive=True) == 2


# ----- two communities -----


def test_one_communitys_client_and_tokens_are_never_read_for_another(world, caplog):
    _put_client(world.store, "oakview")
    VaultTokenStore(world.store, "oakview").save("drive", REFRESH, list(GOOGLE_SCOPES))
    settings = world.settings
    assert oauth_client(settings, object(), store=world.store, community="oakview") == (CLIENT_ID, CLIENT_SECRET)
    with pytest.raises(GoogleError, match="jason/community/pinecrest/google-workspace/oauth-client"):
        oauth_client(settings, object(), store=world.store, community="pinecrest")
    assert VaultTokenStore(world.store, "pinecrest").load("drive") is None
    assert token_store(settings, world.store, "pinecrest").load("drive", GOOGLE_SCOPES) is None
    st = workspace.client_state(world.store, settings, "pinecrest")
    assert st.source == "missing" and "pinecrest" in st.path
    # And the other way round: B's own client never serves A.
    world.store.put(_own_path("pinecrest"), {"client_id": "b-id", "client_secret": "b-secret"})
    assert oauth_client(settings, object(), store=world.store, community="oakview") == (CLIENT_ID, CLIENT_SECRET)
    assert oauth_client(settings, object(), store=world.store, community="pinecrest") == ("b-id", "b-secret")


def test_the_env_fallback_is_the_installations_and_is_logged_as_such(world, caplog):
    world.settings.record_uids = {"google_oauth_record_uid": "UID1"}
    old = SimpleNamespace(load_record=lambda uid: SimpleNamespace(
        custom=[{"label": "client_id", "value": [INSTALL_ID]}, {"label": "client_secret", "value": [INSTALL_SECRET]}]))
    with caplog.at_level(logging.WARNING, logger="jason.google.workspace"):
        assert oauth_client(world.settings, old, store=world.store, community="oakview") == (INSTALL_ID, INSTALL_SECRET)
        assert oauth_client(world.settings, old, store=world.store, community="pinecrest") == (INSTALL_ID, INSTALL_SECRET)
    text = caplog.text
    assert "installation's .env record, not this community's" in text
    assert "jason google adopt-installation-record" in text and "oakview" in text and "pinecrest" in text
    _clean(text)
    # turned off: a community with no client of its own gets none, rather than the installation's
    world.settings.google_installation_client = False
    with pytest.raises(GoogleError):
        oauth_client(world.settings, old, store=world.store, community="oakview")


def test_a_profile_may_pin_its_client_entry_name(world, monkeypatch):
    class Pinned:
        def google_workspace(self):
            return GoogleWorkspace(client="board-client")

    monkeypatch.setattr("jason.community.community", lambda: Pinned())
    assert workspace.client_path("oakview").endswith("/google-workspace/board-client")
    assert workspace.client_path("pinecrest").endswith("/google-workspace/oauth-client")    # a pin is its own profile's
    world.store.put(vault_path("oakview", "google-workspace", "board-client"),
                    {"client_id": "pinned-id", "client_secret": "pinned-secret"})
    assert oauth_client(world.settings, object(), store=world.store, community="oakview") == ("pinned-id", "pinned-secret")


def test_the_installation_fallback_is_off_by_default(tmp_path, monkeypatch):
    from jason.config import Settings

    monkeypatch.delenv("GOOGLE_INSTALLATION_CLIENT", raising=False)
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    assert Settings.load(str(env)).google_installation_client is False
    env.write_text("GOOGLE_INSTALLATION_CLIENT=1\n", encoding="utf-8")
    assert Settings.load(str(env)).google_installation_client is True


def test_the_default_hook_pins_nothing():
    from jason.community.base import Community

    pins = Community.google_workspace(object())    # the default needs no profile state
    assert pins == GoogleWorkspace("", "", "")


# ----- persistence: a consent's token is never lost -----


def test_a_consent_token_survives_a_refusing_vault_and_a_later_migrate_moves_it(world, capsys):
    _put_client(world.store)
    world.store.refuse_puts = True
    settings = world.settings

    def person(client_id, client_secret, path):
        FileTokenStore(path).save("drive", REFRESH, list(GOOGLE_SCOPES))
        return REFRESH

    class Http:
        def post(self, url, *, data=None, content=None, headers=None):
            import httpx

            return httpx.Response(200, content=b'{"access_token": "ya29.made-up"}')

        def close(self):
            return None

    open_drive(settings, object(), store=world.store, authorize=person, http=Http(), interactive=True)   # type: ignore[arg-type]
    local = FileTokenStore(settings.google_oauth_token_file)
    assert local.load("drive")["refresh_token"] == REFRESH                      # sign-in succeeded; the file kept it
    assert VaultTokenStore(world.store, "oakview").load("drive") is None
    _run("status")
    assert "a local file" in capsys.readouterr().out                            # and status flags it

    world.store.refuse_puts = False                                             # the vault answers again
    tokens = token_store(settings, world.store, "oakview")
    done = migrate_tokens(plan_token_migration(tokens, "oakview"), tokens, by="an.admin")
    assert [o for s, o in done if s.name == "drive"] == ["copied; local file removed"]
    assert VaultTokenStore(world.store, "oakview").load("drive")["refresh_token"] == REFRESH
    assert local.load("drive") is None and not settings.google_oauth_token_file.exists()
