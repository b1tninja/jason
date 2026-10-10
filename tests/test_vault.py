"""The credential vault (jason.vault): paths, MemoryStore, KeeperStore over a fake Keeper, the .env fallback, and the
migration plan. No test reaches Keeper; every value is made up."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

import pytest

from jason.vault import (
    CredentialMissing,
    InvalidVaultPath,
    MemoryStore,
    MigrationState,
    Scope,
    Secret,
    VersionConflict,
    credential,
    migrate,
    parse_path,
    plan_migration,
    vault_path,
)
from jason.vault.keeper import KeeperEntry, KeeperStore, SdkKeeperAdapter, record_fields

VALUE = "made-up-value-123"
PATH = "jason/community/oakview/payhoa/login"


class FakeKeeper:
    """A KeeperAdapter in memory: records by UID, a title each, a revision that rises on every write."""

    def __init__(self, records: dict[str, tuple[str, dict[str, str]]] | None = None, *, outside: dict | None = None,
                 fail: Exception | None = None) -> None:
        self.records = {uid: [title, dict(fields), 1] for uid, (title, fields) in (records or {}).items()}
        self.outside = outside or {}          # records outside the jason folder, readable only by UID
        self.fail = fail
        self.revision = 10
        self.created: list[str] = []

    def _check(self):
        if self.fail:
            raise self.fail

    def entries(self):
        self._check()
        return [KeeperEntry(uid, title, rev) for uid, (title, _, rev) in self.records.items()]

    def read(self, uid):
        self._check()
        return dict(self.records[uid][1]), 1_700_000_000_000

    def create(self, title, fields, notes):
        self._check()
        self.revision += 1
        uid = f"NEW{len(self.created) + 1}"
        self.records[uid] = [title, dict(fields), self.revision]
        self.created.append(uid)
        return uid

    def update(self, uid, fields):
        self._check()
        self.revision += 1
        self.records[uid][1:] = [dict(fields), self.revision]

    def remove(self, uid):
        self._check()
        del self.records[uid]

    def load_by_uid(self, uid):
        self._check()
        if uid in self.outside:
            return dict(self.outside[uid])
        if uid in self.records:
            return dict(self.records[uid][1])
        raise LookupError("no record")


# ----- paths -----

def test_a_path_follows_the_scheme_and_parses_back():
    assert vault_path("oakview", "payhoa", "login") == PATH
    assert vault_path("instance", "signin", "oauth-client") == "jason/instance/instance/signin/oauth-client"
    token = vault_path("oakview", "google-workspace", "token/officer@example.org")
    vp = parse_path(token)
    assert (vp.scope, vp.owner, vp.integration, vp.name) == (Scope.COMMUNITY, "oakview", "google-workspace",
                                                             "token/officer@example.org")
    assert str(vp) == token


@pytest.mark.parametrize("bad", [
    "jason/community/oakview/payhoa",              # no name
    "vault/community/oakview/payhoa/login",        # not under jason/
    "jason/tenant/oakview/payhoa/login",           # no such scope
    "jason/community/instance/payhoa/login",       # "instance" is not a community
    "jason/instance/oakview/payhoa/login",         # an instance path's owner is "instance"
    "jason/community/OakView/payhoa/login",        # lower case only
    "jason/community/oakview/pay_hoa/login",       # an integration is a slug
    "jason/community/oakview/payhoa/../login",     # no traversal
    "jason/community/oakview/payhoa//login",       # no empty segment
    "jason/community/oakview/payhoa/login/",
    "jason/community/oak view/payhoa/login",
])
def test_a_path_off_the_scheme_is_refused(bad):
    with pytest.raises(InvalidVaultPath):
        parse_path(bad)


def test_vault_path_refuses_bad_parts():
    for args in (("", "payhoa", "login"), ("oakview", "PayHOA", "login"), ("oakview", "payhoa", ""),
                 ("oakview", "payhoa", "x" * 300)):
        with pytest.raises(InvalidVaultPath):
            vault_path(*args)


# ----- Secret and MemoryStore -----

def test_a_secret_never_shows_its_values():
    secret = Secret({"login": "someone@example.org", "password": VALUE, "empty": ""})
    for text in (repr(secret), str(secret), f"{secret}", repr([secret]), repr({"s": secret})):
        assert VALUE not in text and "someone@example.org" not in text
    assert repr(secret) == "Secret(fields=['login', 'password'])"
    assert secret["password"] == VALUE and "empty" not in secret
    assert secret.first("API_KEY", "Password") == VALUE
    with pytest.raises(TypeError):
        import pickle

        pickle.dumps(secret)


def test_memory_store_check_and_set_refuses_a_stale_version(memory_vault):
    assert memory_vault.put(PATH, {"password": VALUE}, if_version=0, by="tester") == 1
    with pytest.raises(VersionConflict) as stale:
        memory_vault.put(PATH, {"password": "another-made-up"}, if_version=0)
    assert VALUE not in str(stale.value) and stale.value.actual == 1
    assert memory_vault.put(PATH, {"password": "second-made-up"}, if_version=1) == 2
    with pytest.raises(VersionConflict):
        memory_vault.put(PATH, {"password": "third-made-up"}, if_version=1)      # someone wrote version 2 first
    assert memory_vault.get(PATH)["password"] == "second-made-up"
    assert memory_vault.put(PATH, {"password": "fourth-made-up"}) == 3           # no check: written
    assert memory_vault.delete(PATH) and not memory_vault.delete(PATH)
    assert memory_vault.get(PATH) is None
    assert memory_vault.put(PATH, {"password": VALUE}, if_version=0) == 4        # create again after a delete


def test_describe_and_list_give_names_never_values():
    clock = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    store = MemoryStore(now=lambda: clock)
    store.put(PATH, {"login": "someone@example.org", "password": VALUE}, by="tester")
    store.put("jason/community/other/zoom/app", {"client_secret": VALUE})
    entry = store.describe(PATH)
    assert (entry.is_set, entry.version, entry.changed, entry.by) == (True, 1, clock, "tester")
    assert VALUE not in repr(entry) and VALUE not in repr(store)
    assert not store.describe("jason/community/oakview/zoom/app").is_set
    assert store.list("jason/") == ["jason/community/oakview/payhoa/login", "jason/community/other/zoom/app"]
    assert store.list("jason/community/oakview/") == [PATH]
    assert all(VALUE not in name for name in store.list("jason/"))
    with pytest.raises(InvalidVaultPath):
        store.list("other/")
    with pytest.raises(ValueError):
        store.put(PATH, {"password": ""})                                         # nothing to store


# ----- KeeperStore over a fake Keeper -----

def test_keeper_store_maps_a_path_to_the_record_titled_with_it():
    keeper = FakeKeeper({"U1": (PATH, {"login": "someone@example.org", "password": VALUE}),
                         "U2": ("Some other record", {"password": "made-up-other"})})
    store = KeeperStore(keeper)
    assert store.get(PATH)["password"] == VALUE
    assert store.get("jason/community/oakview/zoom/app") is None
    assert store.list("jason/") == [PATH]                                         # a non-path title is not listed
    entry = store.describe(PATH)
    assert entry.is_set and entry.version == 1 and entry.changed is not None and entry.by == ""
    assert VALUE not in repr(store) and VALUE not in repr(entry)


def test_keeper_store_check_and_set_uses_the_revision():
    keeper = FakeKeeper()
    store = KeeperStore(keeper)
    first = store.put(PATH, {"password": VALUE}, if_version=0)
    assert keeper.created == ["NEW1"] and keeper.records["NEW1"][0] == PATH
    with pytest.raises(VersionConflict):
        store.put(PATH, {"password": "made-up-two"}, if_version=0)
    second = store.put(PATH, {"password": "made-up-two"}, if_version=first)
    assert second > first and store.get(PATH)["password"] == "made-up-two"
    with pytest.raises(VersionConflict):
        store.put(PATH, {"password": "made-up-three"}, if_version=first)
    assert store.delete(PATH) and store.get(PATH) is None


def test_keeper_store_refuses_two_records_with_one_title():
    from jason.vault import VaultError

    store = KeeperStore(FakeKeeper({"U1": (PATH, {"password": VALUE}), "U2": (PATH, {"password": VALUE})}))
    with pytest.raises(VaultError):
        store.get(PATH)


def test_a_non_interactive_keeper_store_fails_fast_without_prompting(monkeypatch):
    import builtins
    import getpass

    import jason.secrets as secrets

    def must_not_prompt(*args, **kwargs):
        raise AssertionError("prompted")

    monkeypatch.setattr(builtins, "input", must_not_prompt)
    monkeypatch.setattr(getpass, "getpass", must_not_prompt)
    asked = {}

    def fake_login(**kwargs):
        asked.update(kwargs)
        raise secrets.KeeperAuthRequired("Keeper passwordless session not active")

    monkeypatch.setattr(secrets, "login_to_vault", fake_login)
    store = KeeperStore.from_session(secrets.VaultSession(interactive=False))
    with pytest.raises(secrets.KeeperAuthRequired):
        store.get(PATH)
    assert asked["interactive"] is False


def test_the_sdk_adapter_writes_a_typed_record_with_masked_custom_fields(monkeypatch):
    """The real adapter's record, built without Keeper: standard fields typed, the rest masked, read back by name."""
    import jason.secrets as secrets
    from keepersdk.vault import record_management

    made = {}

    class Vault:
        def sync_down(self):
            made["synced"] = True

    session = secrets.VaultSession()
    session._vault = Vault()
    adapter = SdkKeeperAdapter(session)
    monkeypatch.setattr(adapter, "_folder_uid", lambda create=False: "FOLDER1")

    def fake_add(vault, record, folder_uid=None):
        made["record"], made["folder"] = record, folder_uid
        return "UID9"

    monkeypatch.setattr(record_management, "add_record_to_folder", fake_add)
    fields = {"login": "client-id-made-up", "password": VALUE, "oneTimeCode": "otpauth://totp/x?secret=MADEUP",
              "account_id": "account-made-up"}
    assert adapter.create(PATH, fields, "a note") == "UID9" and made["folder"] == "FOLDER1" and made["synced"]
    record = made["record"]
    assert record.title == PATH
    assert [f.type for f in record.fields] == ["login", "password", "url", "oneTimeCode"]
    assert [(f.type, f.label) for f in record.custom] == [("secret", "account_id")]
    assert record_fields(record) == fields


def test_status_says_when_keeper_needs_a_sign_in():
    from jason.commands.vault import status_lines
    from jason.secrets import KeeperAuthRequired

    store = KeeperStore(FakeKeeper(fail=KeeperAuthRequired("sign in")))
    lines = status_lines(store, {"payhoa_record_uid": "FAKEUID1"}, "oakview")
    text = "\n".join(lines)
    assert "Keeper needs a sign-in" in text and "payhoa_record_uid -> " + PATH in text and "FAKEUID1" not in text


def test_status_lists_paths_by_community_and_the_keys_still_in_env():
    from jason.commands.vault import status_lines

    store = KeeperStore(FakeKeeper({"U1": (PATH, {"password": VALUE}),
                                    "U2": ("jason/instance/instance/signin/oauth-client", {"password": VALUE})}))
    lines = status_lines(store, {"payhoa_record_uid": "FAKEUID1", "zoom_record_uid": "FAKEUID2"}, "oakview")
    text = "\n".join(lines)
    assert "Answers: yes, 2 entries" in text and "Instance:" in text and "Community oakview:" in text
    assert "zoom_record_uid -> jason/community/oakview/zoom/app" in text
    assert "payhoa_record_uid ->" not in text                                     # already in the vault
    assert VALUE not in text and "FAKEUID" not in text


# ----- the resolver -----

def test_the_resolver_reads_the_vault_path_first():
    store = MemoryStore()
    store.put("jason/community/oakview/postscanmail/api-key", {"api_key": VALUE})
    loaded = []
    found = credential("oakview", "postscanmail", "api-key", store=store,
                       record_uids={"postscanmail_record_uid": "FAKEUID"}, load_record=loaded.append)
    assert found["api_key"] == VALUE and loaded == []


def test_the_resolver_falls_back_to_the_env_record_and_logs_the_key_only(caplog):
    from jason.vault import resolver

    resolver._noted.discard("zoom_record_uid")
    keeper = FakeKeeper(outside={"FAKEUID": {"password": VALUE, "account_id": "made-up-account"}})
    store = KeeperStore(keeper)
    with caplog.at_level(logging.WARNING, logger="jason.vault"):
        found = credential("oakview", "zoom", "app", store=store, record_uids={"zoom_record_uid": "FAKEUID"},
                           load_record=store.load_by_uid)
    assert found["password"] == VALUE
    assert "zoom_record_uid" in caplog.text and "jason/community/oakview/zoom/app" in caplog.text
    assert VALUE not in caplog.text and "FAKEUID" not in caplog.text
    assert len(caplog.records) == 1


def test_the_resolver_reads_an_instance_credential_from_the_instance_path():
    store = MemoryStore()
    store.put("jason/instance/instance/signin/oauth-client", {"client_id": "made-up-client"})
    assert credential("oakview", "signin", "oauth-client", store=store)["client_id"] == "made-up-client"


def test_a_credential_in_neither_place_is_a_miss():
    with pytest.raises(CredentialMissing) as miss:
        credential("oakview", "postscanmail", "api-key", store=MemoryStore(), record_uids={},
                   load_record=lambda uid: {})
    assert "postscanmail_record_uid" in str(miss.value)


# ----- migration -----

def test_the_plan_maps_each_env_key_and_never_shows_a_uid():
    from jason.commands.vault import plan_lines

    store = MemoryStore()
    store.put("jason/community/oakview/zoom/app", {"client_secret": VALUE})
    uids = {"payhoa_record_uid": "FAKEUID1", "zoom_record_uid": "FAKEUID2", "exampleportal_record_uid": "FAKEUID3",
            "mystery_record_uid": "FAKEUID4", "google_signin_record_uid": "FAKEUID5", "smud_record_uid": ""}
    steps, problem = plan_migration("oakview", uids, portal_keys=["exampleportal"], store=store)
    by_key = {s.env_key: s for s in steps}
    assert problem == "" and "smud_record_uid" not in by_key
    assert by_key["payhoa_record_uid"].path == PATH and by_key["payhoa_record_uid"].state is MigrationState.COPY
    assert by_key["zoom_record_uid"].state is MigrationState.IN_VAULT
    assert by_key["exampleportal_record_uid"].path == "jason/community/oakview/vendor-portal/exampleportal"
    assert by_key["google_signin_record_uid"].path == "jason/instance/instance/signin/oauth-client"
    assert by_key["mystery_record_uid"].state is MigrationState.UNMAPPED
    text = "\n".join(plan_lines(steps, "oakview"))
    assert "payhoa_record_uid -> jason/community/oakview/payhoa/login: copy" in text
    assert "zoom_record_uid -> jason/community/oakview/zoom/app: already in the vault" in text
    assert "FAKEUID" not in text and VALUE not in text


def test_the_plan_without_an_answering_vault_marks_steps_not_checked():
    from jason.secrets import KeeperAuthRequired

    store = KeeperStore(FakeKeeper(fail=KeeperAuthRequired("sign in")))
    steps, problem = plan_migration("oakview", {"payhoa_record_uid": "FAKEUID1"}, store=store)
    assert "KeeperAuthRequired" in problem and steps[0].state is MigrationState.NOT_CHECKED


def test_migrate_copies_create_only():
    keeper = FakeKeeper({"OLD": (PATH, {"password": "already-there"})},
                        outside={"FAKEUID1": {"login": "someone@example.org", "password": VALUE},
                                 "FAKEUID2": {"password": "made-up-zoom"}})
    store = KeeperStore(keeper)
    uids = {"payhoa_record_uid": "FAKEUID1", "zoom_record_uid": "FAKEUID2", "smud_record_uid": "GONE"}
    steps, _ = plan_migration("oakview", uids, store=store)
    results = {r.step.env_key: r.outcome for r in migrate(steps, store, uids, store.load_by_uid, by="tester")}
    assert results == {"smud_record_uid": "source record not found", "zoom_record_uid": "copied"}
    assert store.get(PATH)["password"] == "already-there"                         # never overwritten
    assert store.get("jason/community/oakview/zoom/app")["password"] == "made-up-zoom"


# ----- the command -----

def test_vault_status_and_migrate_are_actions_of_the_vault_command():
    from jason.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["vault"]).action is None                            # Google Vault, as before
    args = parser.parse_args(["vault", "migrate", "--community", "oakview"])
    assert (args.action, args.community, args.yes) == ("migrate", "oakview", False)
    assert parser.parse_args(["vault", "status"]).action == "status"


def _args(tmp_path, **kw):
    env = tmp_path / ".env"
    env.write_text("keeper_username=someone@example.org\npayhoa_record_uid=FAKEUID1\nzoom_record_uid=FAKEUID2\n",
                   encoding="utf-8")
    return argparse.Namespace(env=str(env), interactive=False, community="oakview", yes=False, json=False, **kw)


def _no_keeper(monkeypatch):
    import jason.secrets as secrets

    def fake_login(**kwargs):
        assert kwargs["interactive"] is False
        raise secrets.KeeperAuthRequired("sign in")

    monkeypatch.setattr(secrets, "login_to_vault", fake_login)


def test_migrate_without_yes_prints_the_plan_only(monkeypatch, tmp_path, capsys):
    from jason.commands.vault import run

    _no_keeper(monkeypatch)
    assert run(_args(tmp_path, action="migrate")) == 0
    out = capsys.readouterr().out
    assert "payhoa_record_uid -> jason/community/oakview/payhoa/login" in out and "Nothing written" in out
    assert "FAKEUID" not in out


def test_migrate_yes_refuses_without_a_terminal(monkeypatch, tmp_path, capsys):
    import io

    from jason.commands.vault import run

    _no_keeper(monkeypatch)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    args = _args(tmp_path, action="migrate")
    args.yes = True
    assert run(args) == 2
    assert "a person at a terminal" in capsys.readouterr().err


def test_vault_status_never_prompts(monkeypatch, tmp_path, capsys):
    from jason.commands.vault import run

    _no_keeper(monkeypatch)
    assert run(_args(tmp_path, action="status")) == 0
    out = capsys.readouterr().out
    assert "Vault backend: keeper" in out and "Keeper needs a sign-in" in out and "FAKEUID" not in out


# ----- the switched callers -----

def _agent_with(monkeypatch, store, uids):
    from jason.agent import Jason
    from jason.config import Settings

    settings = Settings(keeper_username="", payhoa_record_uid="", smud_record_uid="", idoxs_record_uid="",
                        payhoa_org_id=1, smud_category_id=None, idoxs_category_id=None, record_uids=uids)
    agent = Jason(settings=settings)
    monkeypatch.setattr(agent, "vault_store", lambda: store)
    monkeypatch.setattr("jason.community.profile.profile_name", lambda: "oakview")
    # The profile is a name only here: the clients take their User-Agent from a stand-in specification.
    from types import SimpleNamespace

    stand_in = SimpleNamespace(user_agent=lambda purpose: f"jason (Oakview Owners Association; {purpose})")
    monkeypatch.setattr(type(agent), "community", property(lambda self: stand_in))
    return agent


def test_postscanmail_reads_its_key_from_the_vault(monkeypatch):
    store = KeeperStore(FakeKeeper({"U1": ("jason/community/oakview/postscanmail/api-key", {"password": VALUE})}))
    agent = _agent_with(monkeypatch, store, {})
    with agent.postscanmail() as client:
        assert client._key == VALUE
        assert client._user_agent == "jason (Oakview Owners Association; read-only mail sync)"


def test_zoom_falls_back_to_the_env_record(monkeypatch):
    store = KeeperStore(FakeKeeper(outside={"FAKEUID": {"login": "made-up-client", "password": VALUE,
                                                        "account_id": "made-up-account",
                                                        "client_id": "made-up-client"}}))
    agent = _agent_with(monkeypatch, store, {"zoom_record_uid": "FAKEUID"})
    client = agent.zoom()
    assert (client._creds.account_id, client._creds.client_id, client._creds.client_secret) == (
        "made-up-account", "made-up-client", VALUE)
    assert VALUE not in repr(client._creds)


def test_credential_records_hide_their_secrets_in_repr():
    from jason.secrets import IdoxsCredentials, LoginCredentials, PayhoaCredentials

    for creds in (LoginCredentials("someone", VALUE, "123456"), PayhoaCredentials("someone", VALUE, "123456"),
                  IdoxsCredentials("someone", VALUE, {"pet": VALUE})):
        assert VALUE not in repr(creds) and "123456" not in repr(creds) and "someone" in repr(creds)


def test_a_missing_credential_is_a_value_error_for_the_callers(monkeypatch):
    agent = _agent_with(monkeypatch, KeeperStore(FakeKeeper()), {})
    with pytest.raises(ValueError, match="postscanmail_record_uid"):
        agent.postscanmail()
    with pytest.raises(ValueError, match="zoom_record_uid"):
        agent.zoom()


# ----- every reader through the resolver: the vault path first, then .env, then the caller's own error -----

SEED = "JBSWY3DPEHPK3PXP"                       # a made-up TOTP seed
LOGIN = {"login": "someone@example.org", "password": VALUE, "oneTimeCode": SEED}
PORTAL = "exampleportal"


class _Client:
    """Stands in for a portal client: keeps what it was given; no network."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs, self.signed, self.is_authenticated = args, kwargs, None, True

    def login(self, *args, **kwargs):
        self.signed = (args, kwargs)
        return True

    def sign_in(self, *args):
        self.signed = (args, {})
        return True

    def login_accounts(self):
        return None

    def close(self):
        return None


class _Profile:
    def vendor_portals(self):
        from types import SimpleNamespace

        from jason.community.symbols import PortalPlatform

        return (SimpleNamespace(key=PORTAL, platform=PortalPlatform.FIELDPORTALS, account="made-up-account",
                                payhoa_words=(), reports=()),)


def _switched(monkeypatch, store, uids):
    from jason.agent import Jason

    agent = _agent_with(monkeypatch, store, uids)
    monkeypatch.setattr(Jason, "community", property(lambda self: _Profile()))
    for target in ("jason.agent.PayhoaClient", "jason.agent.SmudClient", "jason.agent.IdoxsClient",
                   "jason.fieldportals.client.FieldPortals", "jason.community.accela.SacramentoCitizenAccess"):
        monkeypatch.setattr(target, _Client)
    return agent


def _given(client):
    return tuple((client.signed[0] if client.signed and client.signed[0] else client.args)[:2])


CALLERS = [   # method, integration, name, its .env key, and the caller's error when neither holds it
    ("payhoa", "payhoa", "login", "payhoa_record_uid", ValueError, "payhoa_record_uid is not set"),
    ("payhoa_test", "payhoa", "test-login", "payhoa_test_record_uid", ValueError, "payhoa_test_record_uid is not set"),
    ("smud", "smud", "login", "smud_record_uid", ValueError, "smud_record_uid is not set in .env"),
    ("idoxs", "idoxs", "login", "idoxs_record_uid", ValueError, "idoxs_record_uid is not set in .env"),
    ("vendor_portal", "vendor-portal", PORTAL, f"{PORTAL}_record_uid", LookupError,
     f"{PORTAL}_record_uid is not set in .env"),
    ("citizen_access", "accela", "login", "accela_record_uid", LookupError, "accela_record_uid is not set"),
]


def _call(agent, method):
    return getattr(agent, method)(PORTAL) if method == "vendor_portal" else getattr(agent, method)()


@pytest.mark.parametrize("method, integration, name, env_key, error, words", CALLERS)
def test_each_reader_takes_the_vault_path_first(monkeypatch, memory_vault, method, integration, name, env_key, error,
                                                words):
    memory_vault.put(f"jason/community/oakview/{integration}/{name}", {**LOGIN, "pet": "made-up-answer"})
    agent = _switched(monkeypatch, memory_vault, {env_key: "FAKEUID"})     # .env names a record too: the vault wins
    client = _call(agent, method)
    assert _given(client) == ("someone@example.org", VALUE)
    if method == "payhoa":
        assert client.signed[1]["totp_code"].isdigit()                     # a fresh code from the seed
    if method == "idoxs":
        assert client.kwargs["security_answers"] == {"pet": "made-up-answer"}


@pytest.mark.parametrize("method, integration, name, env_key, error, words", CALLERS)
def test_each_reader_falls_back_to_the_env_record_and_logs_only_the_key(monkeypatch, caplog, method, integration,
                                                                        name, env_key, error, words):
    from jason.vault import resolver

    resolver._noted.discard(env_key)
    store = KeeperStore(FakeKeeper(outside={"FAKEUID": LOGIN}))
    agent = _switched(monkeypatch, store, {env_key: "FAKEUID"})
    with caplog.at_level(logging.WARNING, logger="jason.vault"):
        assert _given(_call(agent, method)) == ("someone@example.org", VALUE)
    assert env_key in caplog.text and f"jason/community/oakview/{integration}/{name}" in caplog.text
    assert VALUE not in caplog.text and "FAKEUID" not in caplog.text and SEED not in caplog.text


@pytest.mark.parametrize("method, integration, name, env_key, error, words", CALLERS)
def test_each_reader_keeps_its_error_when_neither_holds_it(monkeypatch, memory_vault, method, integration, name,
                                                           env_key, error, words):
    agent = _switched(monkeypatch, memory_vault, {})
    with pytest.raises(error, match=words) as missed:
        _call(agent, method)
    assert f"jason/community/oakview/{integration}/{name}" in str(missed.value)


def test_a_portal_with_only_a_vault_entry_is_a_bill_source(monkeypatch, memory_vault):
    agent = _switched(monkeypatch, memory_vault, {})
    agent._bills, agent._idoxs_bills = object(), object()          # the bill stores are not opened
    assert [s.name for s in agent.bill_source_registry().sources] == ["smud", "idoxs"]
    memory_vault.put(f"jason/community/oakview/vendor-portal/{PORTAL}", LOGIN)
    assert [s.name for s in agent.bill_source_registry().sources] == ["smud", "idoxs", PORTAL]

    class Refuses:                                                  # a .env record UID answers without the vault
        def describe(self, path):
            raise AssertionError("the vault is not asked")

    other = _switched(monkeypatch, Refuses(), {f"{PORTAL}_record_uid": "FAKEUID"})
    assert other.credential_configured("vendor-portal", PORTAL)


def _settings_for(uids=None, **named):
    from jason.config import Settings

    base = {"keeper_username": "", "payhoa_record_uid": "", "smud_record_uid": "", "idoxs_record_uid": "",
            "payhoa_org_id": 1, "smud_category_id": None, "idoxs_category_id": None, "record_uids": uids or {}}
    base.update(named)
    return Settings(**base)


def _keeper_is(monkeypatch, store):
    monkeypatch.setattr(KeeperStore, "from_session", classmethod(lambda cls, session, folder="jason": store))
    monkeypatch.setattr("jason.community.profile.profile_name", lambda: "oakview")


def test_the_settings_readers_take_the_vault_path_first(monkeypatch, memory_vault):
    """``get_*_credentials(settings=...)`` (``payhoa_session``, scripts): the vault first, then .env, then the old error."""
    from jason import secrets

    _keeper_is(monkeypatch, memory_vault)
    for integration, name in (("payhoa", "login"), ("accela", "login"), ("idoxs", "login"),
                              ("vendor-portal", PORTAL)):
        memory_vault.put(f"jason/community/oakview/{integration}/{name}", {**LOGIN, "pet": "made-up-answer"})
    s = _settings_for()
    payhoa = secrets.get_payhoa_credentials(settings=s)
    assert (payhoa.email, payhoa.password) == ("someone@example.org", VALUE) and payhoa.totp_code.isdigit()
    assert secrets.get_accela_credentials(settings=s).password == VALUE
    assert secrets.get_vendor_credentials(PORTAL, settings=s).password == VALUE
    idoxs = secrets.get_idoxs_credentials(settings=s)
    assert idoxs.security_answers == {"pet": "made-up-answer"}
    for creds in (payhoa, idoxs, secrets.get_accela_credentials(settings=s)):
        assert VALUE not in repr(creds) and SEED not in repr(creds)


def test_the_settings_readers_fall_back_and_keep_their_errors(monkeypatch):
    from jason import secrets

    _keeper_is(monkeypatch, KeeperStore(FakeKeeper(outside={"FAKEUID": LOGIN})))
    s = _settings_for(payhoa_record_uid="FAKEUID")                      # a named attribute is a .env key too
    assert secrets.get_payhoa_credentials(settings=s).email == "someone@example.org"
    assert secrets.get_vendor_credentials(PORTAL, settings=_settings_for({f"{PORTAL}_record_uid": "FAKEUID"})).login \
        == "someone@example.org"
    _keeper_is(monkeypatch, MemoryStore())
    empty = _settings_for()
    with pytest.raises(ValueError, match="payhoa_record_uid is not set"):
        secrets.get_payhoa_credentials(settings=empty)
    with pytest.raises(LookupError, match="accela_record_uid is not set"):
        secrets.get_accela_credentials(settings=empty)
    with pytest.raises(LookupError, match=f"{PORTAL}_record_uid is not set in .env"):
        secrets.get_vendor_credentials(PORTAL, settings=empty)
    with pytest.raises(ValueError, match="idoxs_record_uid is not set"):
        secrets.get_idoxs_credentials(settings=empty)


def test_the_google_client_comes_from_the_vault_first(monkeypatch, memory_vault):
    from types import SimpleNamespace

    from jason.google.errors import GoogleError
    from jason.google.session import oauth_client

    monkeypatch.setattr("jason.community.profile.profile_name", lambda: "oakview")
    record = SimpleNamespace(custom=[{"label": "client_id", "value": ["old-id"]},
                                     {"label": "client_secret", "value": ["old-made-up"]}])
    old = SimpleNamespace(load_record=lambda uid: record)
    settings = SimpleNamespace(google_oauth_record_uid="FAKEUID", google_installation_client=True)
    assert oauth_client(settings, old, store=memory_vault) == ("old-id", "old-made-up")          # not moved yet
    memory_vault.put("jason/community/oakview/google-workspace/oauth-client",
                     {"client_id": "new-id", "client_secret": VALUE})
    assert oauth_client(settings, old, store=memory_vault) == ("new-id", VALUE)
    assert oauth_client(SimpleNamespace(), old, store=memory_vault) == ("new-id", VALUE)        # no .env key at all
    with pytest.raises(GoogleError, match="google_oauth_record_uid is not set") as missed:
        oauth_client(SimpleNamespace(), old, store=MemoryStore())
    assert "jason/community/oakview/google-workspace/oauth-client" in str(missed.value)


def test_store_zoom_app_writes_the_vault_path_create_only(monkeypatch, memory_vault, tmp_path, capsys):
    import jason.cli as cli

    agent = _agent_with(monkeypatch, memory_vault, {})
    path = agent.store_zoom_app("made-up-account", "made-up-client", by="A. Admin")
    assert path == "jason/community/oakview/zoom/app"
    stored = memory_vault.get(path)
    assert (stored["account_id"], stored["client_id"], "password" in stored) == ("made-up-account", "made-up-client",
                                                                                 False)
    assert memory_vault.describe(path).by == "A. Admin"
    with pytest.raises(VersionConflict):
        agent.store_zoom_app("another", "another")

    class _Ctx:
        def __enter__(self):
            return agent

        def __exit__(self, *a):
            return None

    monkeypatch.setattr(cli, "_agent", lambda args: _Ctx())
    monkeypatch.setattr("jason.config.Settings.load",
                        classmethod(lambda cls, path=None: _settings_for(payhoa_catalog=tmp_path / "payhoa.db")))
    args = argparse.Namespace(env=None, store_app=True, account_id="made-up-account", client_id="made-up-client",
                              by="")
    assert cli.cmd_zoom(args) == 2                                    # the path is set: left alone
    assert "already holds jason/community/oakview/zoom/app" in capsys.readouterr().out
    memory_vault.delete(path)
    assert cli.cmd_zoom(args) == 0
    out = capsys.readouterr().out
    assert "jason/community/oakview/zoom/app" in out and "set zoom_record_uid" not in out
    assert "created Keeper record" not in out and "made-up-account" not in out


def test_connections_count_a_credential_held_only_in_the_vault(tmp_path):
    from types import SimpleNamespace

    from jason.integrations import connections as cn
    from jason.integrations.registry import ConnectionState, integration
    from jason.vault.resolver import VaultNames

    kc = tmp_path / "keeper-config.json"
    kc.write_text("{}", encoding="utf-8")
    settings = SimpleNamespace(keeper_config=kc, record_uid=lambda name: "")       # .env names nothing
    zoom, payhoa = integration("zoom"), integration("payhoa")
    held = VaultNames(frozenset({"jason/community/oakview/zoom/app"}))
    assert not cn.state_of(zoom, community="oakview", settings=settings).configured   # no vault asked: as before
    reading = cn.state_of(zoom, community="oakview", settings=settings, vault=held)
    assert reading.configured and "jason/community/oakview/zoom/app" in reading.why
    assert not cn.state_of(payhoa, community="oakview", settings=settings, vault=held).configured
    unanswered = cn.state_of(zoom, community="oakview", settings=settings, vault=VaultNames(None, "KeeperAuthRequired"))
    assert unanswered.state is ConnectionState.NOT_SET_UP and "could not be asked (KeeperAuthRequired)" in unanswered.why
    portals = cn.probe(integration("vendor-portals"), settings, lambda: _Profile(),
                       cn.VaultAsked("oakview", VaultNames(frozenset({f"jason/community/oakview/vendor-portal/{PORTAL}"}))))
    assert portals.configured


def test_vault_names_never_prompts(tmp_path):
    from types import SimpleNamespace

    from jason.vault.keeper import vault_names

    assert vault_names(SimpleNamespace(keeper_config=tmp_path / "none.json")).problem == \
        "the vault's login is not on this machine"
    kc = tmp_path / "keeper-config.json"
    kc.write_text("{}", encoding="utf-8")
    asked = vault_names(SimpleNamespace(keeper_config=kc, keeper_username="", keeper_password=""))
    assert not asked.answered and asked.problem == "KeeperAuthRequired"        # conftest: Keeper wants a sign-in


def test_onboarding_counts_a_setting_moved_to_the_vault():
    from types import SimpleNamespace

    from jason.community.onboarding import Context, Setting
    from jason.vault.resolver import VaultNames

    settings = SimpleNamespace(payhoa_record_uid="", record_uid=lambda name: "")
    ctx = lambda vault: Context(community=None, settings=settings, profile="oakview", vault=vault)   # noqa: E731
    assert not Setting("payhoa_record_uid").run(ctx(None)).passed
    found = Setting("payhoa_record_uid").run(ctx(VaultNames(frozenset({PATH}))))
    assert found.passed and PATH in found.evidence
    missed = Setting("payhoa_record_uid").run(ctx(VaultNames(None, "KeeperAuthRequired")))
    assert not missed.passed and "could not be asked" in missed.evidence


def test_citizen_access_sign_in_reads_the_vault_and_stays_anonymous_without_one(monkeypatch, memory_vault, capsys):
    import jason.cli as cli
    from jason import secrets

    _keeper_is(monkeypatch, memory_vault)
    monkeypatch.setattr("jason.config.Settings.load", classmethod(lambda cls, path=None: _settings_for()))
    client = _Client()
    cli._sign_in_citizen_access(client)
    assert client.signed is None                                            # neither: anonymous, as before
    memory_vault.put("jason/community/oakview/accela/login", LOGIN)
    cli._sign_in_citizen_access(client)
    assert _given(client) == ("someone@example.org", VALUE) and VALUE not in capsys.readouterr().out

    def no_keeper(*a, **k):
        raise secrets.KeeperAuthRequired("sign in")

    monkeypatch.setattr(secrets, "resolve_credential", no_keeper)
    quiet = _Client()
    cli._sign_in_citizen_access(quiet)                                      # no .env record: anonymous
    assert quiet.signed is None
    monkeypatch.setattr("jason.config.Settings.load",
                        classmethod(lambda cls, path=None: _settings_for(accela_record_uid="FAKEUID")))
    with pytest.raises(secrets.KeeperAuthRequired):
        cli._sign_in_citizen_access(_Client())                             # an .env record: fail fast as before
