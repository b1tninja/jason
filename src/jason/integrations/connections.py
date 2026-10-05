"""Connections: one community's configured use of an integration (docs/integrations-design.md, The model).

A ``Connection`` row names the community, the integration, the account label, the capabilities on, where its
credential lives in the vault (a path string: ``jason/<scope>/<community or "instance">/<integration>/<name>``; the
vault itself is build step 2), its state, who connected it and when, its last check, and schedule overrides with who and
when. The rows are kept per community at ``integrations.json`` in its data folder (``jason.config.data_dir`` for the
active profile, ``default_data_dir(key)`` for another; the installation's at ``<data root>/instance/``), written under
the store lock (``jason.locks``).

``state_of`` derives today's state from what exists now, since nothing writes the rows yet but a check:
- a credential configured: a Keeper record UID set in the settings, a sign-in client named, a folder there, or (when the
  caller passes the vault's names) an entry at the credential's vault path. Only whether; a value is never read, kept,
  or printed (a token file is looked at for being there, never opened). The vault is listed without prompting; when it
  does not answer, the ``.env`` test stands alone and the reading says so;
- the vault's login on this machine (Keeper's persistent config) for every credential the vault holds;
- the Status screen's reading of each of its sources (``jason.web.extra.status``): a failed job or refresh, a sign-in
  failure, a last read;
- the connection's own last check and a pause a person set.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.integrations.registry import REGISTRY, ConnectionState, Integration, Scope, duration

INSTANCE = "instance"
FILE = "integrations.json"
LOCK_TIMEOUT = 60
VAULT_ROOT = "jason"


# --- the rows ----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ScheduleOverride:
    """An administrator's change to one source's cadence: the new ``every`` or ``cron`` and ``window``, or a pause,
    with who and when and why."""

    source_key: str
    every: str = ""
    cron: str = ""
    window: str = ""
    paused: bool = False
    by: str = ""
    at: str = ""
    why: str = ""

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in ("", False) or k == "source_key"}

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> ScheduleOverride:
        return cls(str(row.get("source_key") or ""), str(row.get("every") or ""), str(row.get("cron") or ""),
                   str(row.get("window") or ""), bool(row.get("paused")), str(row.get("by") or ""),
                   str(row.get("at") or ""), str(row.get("why") or ""))


@dataclass(frozen=True)
class Connection:
    """One community's use of one integration. Holds no secret: ``vault_path`` names where the credential is."""

    community: str
    integration: str
    account: str = ""
    capabilities: tuple[str, ...] = ()
    vault_path: str = ""
    state: ConnectionState = ConnectionState.NOT_SET_UP
    connected_by: str = ""
    connected_at: str = ""
    last_checked: str = ""
    last_check: str = ""                       # the last check's words: "ok: ..." or "failed: ..." (masked)
    note: str = ""                             # why it is paused, by whom
    overrides: tuple[ScheduleOverride, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {"community": self.community, "integration": self.integration, "account": self.account,
                "capabilities": list(self.capabilities), "vaultPath": self.vault_path, "state": self.state.value,
                "connectedBy": self.connected_by, "connectedAt": self.connected_at, "lastChecked": self.last_checked,
                "lastCheck": self.last_check, "note": self.note,
                "overrides": [o.to_json() for o in self.overrides]}

    @classmethod
    def from_json(cls, row: dict[str, Any]) -> Connection:
        word = str(row.get("state") or ConnectionState.NOT_SET_UP.value)
        try:
            state = ConnectionState(word)
        except ValueError:
            raise ValueError(f"connection {row.get('integration')!r}: {word!r} is not a connection state") from None
        return cls(str(row.get("community") or ""), str(row.get("integration") or ""), str(row.get("account") or ""),
                   tuple(str(c) for c in row.get("capabilities") or ()), str(row.get("vaultPath") or ""), state,
                   str(row.get("connectedBy") or ""), str(row.get("connectedAt") or ""),
                   str(row.get("lastChecked") or ""), str(row.get("lastCheck") or ""), str(row.get("note") or ""),
                   tuple(ScheduleOverride.from_json(o) for o in row.get("overrides") or () if isinstance(o, dict)))


def vault_path(community: str, integration_key: str, name: str) -> str:
    """The vault path of ``name`` for an integration: ``jason/<scope>/<community or "instance">/<integration>/<name>``
    (docs/integrations-design.md, The vault). A path names a secret; it is not one."""
    scope = Scope.INSTANCE.value if community == INSTANCE else Scope.COMMUNITY.value
    return f"{VAULT_ROOT}/{scope}/{community}/{integration_key}/{name}"


def default_vault_path(integ: Integration, community: str) -> str:
    """Where the integration's credential goes for ``community``: its first name with no placeholder, else its prefix
    (an integration with a credential a portal or an account); "" when it holds none."""
    if not integ.vault_names:
        return ""
    plain = next((n for n in integ.vault_names if "<" not in n), "")
    return vault_path(community, integ.key, plain) if plain else vault_path(community, integ.key, "").rstrip("/") + "/"


def new_connection(integ: Integration, community: str) -> Connection:
    """A connection not set up yet: the read capabilities on, the vault path it will use."""
    return Connection(community, integ.key, capabilities=integ.default_capabilities(),
                      vault_path=default_vault_path(integ, community))


# --- the store ---------------------------------------------------------------------------------------------------------

def store_path(community: str, env_file: str | Path | None = None) -> Path:
    """``integrations.json`` for ``community``: the active profile's data folder (``data_dir``, from ``env_file``),
    another profile's own (``default_data_dir``), or the installation's (``<data root>/instance``)."""
    from jason.config import data_dir, data_root, default_data_dir
    from jason.community.profile import profile_name

    if community == INSTANCE:
        return data_root() / INSTANCE / FILE
    if community == profile_name():
        return data_dir(env_file) / FILE
    return default_data_dir(community) / FILE


def _lock_key(community: str) -> str:
    return f"integrations-{community}"


def load(community: str, path: Path | None = None) -> dict[str, Connection]:
    """The community's connections by integration key; none when the file is not there."""
    path = Path(path) if path is not None else store_path(community)
    if not path.is_file():
        return {}
    body = json.loads(path.read_text(encoding="utf-8"))
    rows = body.get("connections") if isinstance(body, dict) else None
    out: dict[str, Connection] = {}
    for row in rows or ():
        if isinstance(row, dict):
            c = Connection.from_json(row)
            out[c.integration] = c
    return out


def save(community: str, connections: Iterable[Connection], path: Path | None = None, *,
         now: datetime | None = None) -> Path:
    """Write the community's connections (replacing the file, atomically) under the store lock."""
    from jason.locks import Resource, hold

    path = Path(path) if path is not None else store_path(community)
    rows = sorted(connections, key=lambda c: c.integration)
    for c in rows:
        if c.community != community:
            raise ValueError(f"connection {c.integration!r} is {c.community!r}'s, not {community!r}'s")
    at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    body = {"community": community, "updatedAt": at, "connections": [c.to_json() for c in rows]}
    with hold(Resource.STORE, _lock_key(community), timeout=LOCK_TIMEOUT, purpose=f"integrations {community}"):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(body, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return path


def record_check(community: str, integ: Integration, *, ok: bool, words: str, state: ConnectionState,
                 path: Path | None = None, now: datetime | None = None, by: str = "") -> Connection:
    """Record a check's outcome on the community's connection (read, changed, and written under one lock hold). A
    first successful check records who connected it and when."""
    from jason.locks import Resource, hold

    at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    with hold(Resource.STORE, _lock_key(community), timeout=LOCK_TIMEOUT, purpose=f"integrations check {integ.key}"):
        rows = load(community, path)
        row = rows.get(integ.key) or new_connection(integ, community)
        changes: dict[str, Any] = {"last_checked": at, "last_check": ("ok: " if ok else "failed: ") + words}
        if row.state is not ConnectionState.PAUSED:
            changes["state"] = state
        if ok and not row.connected_at:
            changes.update(connected_at=at, connected_by=by)
        rows[integ.key] = replace(row, **changes)
        save(community, rows.values(), path, now=now)
    return rows[integ.key]


# --- what is configured, from what exists now --------------------------------------------------------------------------

@dataclass(frozen=True)
class Probe:
    """What the settings and the disk say of an integration's credential: configured or not, the vault's login (None
    when the credential is not the vault's), the account label, and why, in words. Never a value."""

    configured: bool
    vault_login: bool | None = None
    account: str = ""
    why: str = ""
    google_token: bool | None = None


def _record_set(settings: Any, name: str) -> bool:
    """Whether a Keeper record UID is set as ``<name>_record_uid`` (only whether; the UID is not kept)."""
    if settings is None:
        return False
    if str(getattr(settings, f"{name}_record_uid", "") or ""):
        return True
    reader = getattr(settings, "record_uid", None)
    return bool(reader(name)) if callable(reader) else False


def _keeper_login(settings: Any) -> bool:
    path = getattr(settings, "keeper_config", None)
    return bool(path) and Path(path).is_file()


@dataclass(frozen=True)
class VaultAsked:
    """What a probe knows of the vault: the community's key and the vault's names (``resolver.VaultNames``), or
    ``names`` None when the vault was not asked at all (the ``.env`` test alone, said nowhere)."""

    community: str = ""
    names: Any = None

    def path(self, name: str, portal_keys: Iterable[str] = ()) -> str:
        """The vault path of the credential ``<name>_record_uid`` names (``resolver.legacy_record``), or ""."""
        from jason.vault.resolver import legacy_record

        row = legacy_record(f"{name}_record_uid", portal_keys)
        return row.path(self.community) if row is not None and self.community else ""

    def holds(self, path: str) -> bool:
        return bool(path) and self.names is not None and self.names.has(path)

    def under(self, prefix: str) -> bool:
        return self.names is not None and bool(self.names.under(prefix))

    def caveat(self) -> str:
        """Why only ``.env`` was tested, when the vault was asked and did not answer; "" otherwise."""
        if self.names is None or self.names.answered:
            return ""
        return f"; the vault could not be asked ({self.names.problem}), so only .env was tested"


def _vault_probe(settings: Any, names: tuple[str, ...], what: str, vault: VaultAsked | None = None,
                 portal_keys: Iterable[str] = ()) -> Probe:
    """A credential kept at its vault path, or as a Keeper record named ``<name>_record_uid``: configured when any
    is set in either place (names only)."""
    vault = vault or VaultAsked()
    portals = tuple(portal_keys)
    in_vault = [n for n in names if vault.holds(vault.path(n, portals))]
    set_ = [n for n in names if n in in_vault or _record_set(settings, n)]
    if not set_:
        return Probe(False, why=f"no {what} is named in the settings or held in the vault{vault.caveat()}")
    account = ", ".join(set_) if len(names) > 1 else ""
    if len(names) > 1:
        why = f"{len(set_)} of {len(names)} set"
    elif in_vault:
        why = f"the vault holds the {what} ({vault.path(names[0], portals)})"
    else:
        why = f"the {what} is named in the settings"
    return Probe(True, _keeper_login(settings), account, why + vault.caveat())


def _google(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    vault = vault or VaultAsked()
    in_vault = vault.holds(vault.path("google_oauth"))
    via_vault = in_vault or _record_set(settings, "google_oauth")
    client = via_vault or bool(
        getattr(settings, "google_oauth_client_file", None) and Path(settings.google_oauth_client_file).is_file())
    if not client:
        return Probe(False, why="no OAuth client is named in the settings or held in the vault" + vault.caveat())
    token = getattr(settings, "google_oauth_token_file", None)
    has_token = bool(token) and Path(token).is_file()
    why = "the vault holds the OAuth client" if in_vault else "the OAuth client is named in the settings"
    return Probe(True, _keeper_login(settings) if via_vault else None, why=why + vault.caveat(),
                 google_token=has_token)


def _sign_in(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    from jason.vault.paths import ROOT

    vault = vault or VaultAsked()
    try:
        clients = tuple(community().sign_in()) if community is not None else ()
    except Exception:  # noqa: BLE001 - a profile that cannot load: not set up, with why
        return Probe(False, why="the profile's sign-in clients could not be read")
    held = vault.community and vault.under(f"{ROOT}/community/{vault.community}/signin/")
    if not clients and not held and not _record_set(settings, "google_signin") \
            and not vault.holds(vault.path("google_signin")):
        return Probe(False, why="no sign-in client is named for the community" + vault.caveat())
    return Probe(True, _keeper_login(settings), ", ".join(c.key for c in clients),
                 f"{len(clients) or 1} sign-in client(s) named" + vault.caveat())


def _instance_sign_in(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    from jason.vault.paths import INSTANCE as VAULT_INSTANCE, ROOT

    vault = vault or VaultAsked()
    try:
        from jason.access import installation_sign_in

        clients = installation_sign_in()
    except Exception:  # noqa: BLE001
        clients = ()
    if not clients and not vault.under(f"{ROOT}/instance/{VAULT_INSTANCE}/signin/"):
        return Probe(False, why="no installation sign-in client is named (data/access/sign_in.json)" + vault.caveat())
    return Probe(True, _keeper_login(settings), ", ".join(c.key for c in clients),
                 f"{len(clients) or 1} client(s) named" + vault.caveat())


def _portals(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    try:
        keys = tuple(p.key for p in community().vendor_portals()) if community is not None else ()
    except Exception:  # noqa: BLE001
        return Probe(False, why="the profile's portal rows could not be read")
    if not keys:
        return Probe(False, why="the profile names no vendor portal")
    return _vault_probe(settings, keys, "portal login", vault, keys)


def _vault(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    if _keeper_login(settings):
        return Probe(True, True, why="the vault's login is on this machine")
    return Probe(True, False, why="the vault's login is not on this machine")


def _law_library(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    home = getattr(settings, "lawlibrary_home", None)
    if home and Path(home).is_dir():
        return Probe(True, why="the lawlibrary checkout is there")
    return Probe(False, why="no lawlibrary checkout at lawlibrary_home")


def _bedrock(settings: Any, community: Any, vault: VaultAsked | None = None) -> Probe:
    aws = Path.home() / ".aws"
    if any(os.environ.get(k) for k in ("AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")) \
            or (aws / "credentials").is_file() or (aws / "config").is_file():
        return Probe(True, why="AWS credentials are configured in the AWS chain")
    return Probe(False, why="no AWS credentials are configured (optional)")


PROBES = {
    "google-workspace": _google,
    "sign-in": _sign_in,
    "payhoa": lambda s, c, v=None: _vault_probe(s, ("payhoa",), "PayHOA login record", v),
    "zoom": lambda s, c, v=None: _vault_probe(s, ("zoom",), "Zoom app record", v),
    "postscanmail": lambda s, c, v=None: _vault_probe(s, ("postscanmail",), "API key record", v),
    "utilities": lambda s, c, v=None: _vault_probe(s, ("smud", "idoxs"), "utility login", v),
    "accela": lambda s, c, v=None: _vault_probe(s, ("accela",), "portal login record", v),
    "vendor-portals": _portals,
    "vault": _vault,
    "instance-sign-in": _instance_sign_in,
    "law-library": _law_library,
    "bedrock": _bedrock,
}


def probe(integ: Integration, settings: Any = None, community: Any = None, vault: VaultAsked | None = None) -> Probe:
    """What the settings, the disk, and (with ``vault``) the vault's names say of the integration's credential; one
    with none to configure is configured."""
    fn = PROBES.get(integ.key)
    return fn(settings, community, vault) if fn is not None else Probe(True, why="nothing to configure")


# --- the state ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Reading:
    """An integration's state today, why, its account label, its connection row, and its sources' Status rows."""

    integration: Integration
    state: ConnectionState
    why: str
    account: str
    connection: Connection
    sources: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    configured: bool = False                   # its credential is configured (only whether)


def _later(a: str, b: str) -> bool:
    from jason.web.extra.status import _after

    return _after(a, b)


def state_of(integ: Integration, *, community: str, settings: Any = None, rows: Iterable[dict[str, Any]] = (),
             connection: Connection | None = None, profile: Any = None, vault: Any = None) -> Reading:
    """The integration's state from what exists now. ``rows`` are the Status screen's rows for its sources
    (``status.source_rows``); ``profile`` is the active ``Community`` getter (``jason.community.community``), asked
    only by the integrations whose instances are profile rows. ``vault`` is the vault's names
    (``resolver.VaultNames``, from ``jason.vault.keeper.vault_names``, which never prompts): a credential at its vault
    path counts as set too; a vault that did not answer leaves the ``.env`` test, and the reading says so."""
    from jason.web.extra import status as st

    conn = connection or new_connection(integ, community)
    keys = {c.source_key for c in integ.sources}
    mine = tuple(r for r in rows if r.get("key") in keys)
    found = probe(integ, settings, profile, VaultAsked(community, vault) if vault is not None else None)
    account = conn.account or found.account

    def reading(state: ConnectionState, why: str) -> Reading:
        return Reading(integ, state, why, account, conn, mine, found.configured)

    if conn.state is ConnectionState.PAUSED:
        return reading(ConnectionState.PAUSED, conn.note or "paused")
    if not found.configured:
        return reading(ConnectionState.NOT_SET_UP, found.why)
    if found.vault_login is False:
        return reading(ConnectionState.NEEDS_SIGN_IN, "the vault's login is not on this machine: jason login")
    if found.google_token is False:
        return reading(ConnectionState.NEEDS_SIGN_IN, "no Google token on this machine: the first sign-in")
    signed_out = [r for r in mine if r.get("standing") == st.NOT_SIGNED_IN]
    if signed_out:
        return reading(ConnectionState.NEEDS_SIGN_IN, f"{signed_out[0]['name']}: {signed_out[0].get('note') or 'not signed in'}")
    failed = [r for r in mine if r.get("standing") == st.FAILED]
    last_read = max((str(r.get("lastRead") or "") for r in mine), default="")
    check_failed = conn.last_check.startswith("failed") and _later(conn.last_checked, last_read)
    if check_failed:
        sign_in = st._SIGN_IN_WORDS.search(conn.last_check)
        return reading(ConnectionState.NEEDS_SIGN_IN if sign_in else ConnectionState.FAILING, conn.last_check)
    if failed:
        return reading(ConnectionState.FAILING, f"{failed[0]['name']}: {failed[0].get('note') or 'its last run failed'}")
    if last_read or conn.last_check.startswith("ok"):
        why = f"last read {last_read}" if last_read else f"checked {conn.last_checked}"
        return reading(ConnectionState.CONNECTED, why)
    from jason.integrations.checks import LIVE

    if not integ.sources and integ.key not in LIVE:
        return reading(ConnectionState.CONNECTED, found.why)      # its check is the disk read just made
    return reading(ConnectionState.NOT_SET_UP,
                   f"{found.why}; nothing read yet (jason integrations check {integ.key} --live)")


def readings(community: str, *, scope: Scope, settings: Any = None, root: Path | None = None,
             now: datetime | None = None, path: Path | None = None, profile: Any = None,
             vault: Any = None) -> list[Reading]:
    """Every ``scope`` integration's reading for ``community``: its stored row, the Status rows of its sources read
    from the data folder ``root`` (disk only), what the settings say, and, given ``vault``, the vault's names."""
    from jason.web.extra import status as st

    stored = load(community, path)
    rows = st.source_rows(Path(root), settings=settings, now=now) if root is not None else []
    return [state_of(i, community=community, settings=settings, rows=rows, connection=stored.get(i.key),
                     profile=profile, vault=vault)
            for i in REGISTRY if i.scope is scope]


def below_floor(integ: Integration, override: ScheduleOverride) -> bool:
    """Whether an override's ``every`` is faster than its source's floor (refused: integrations-design.md)."""
    cad = next((c for c in integ.sources if c.source_key == override.source_key), None)
    if cad is None or not override.every or not cad.floor:
        return False
    every, floor = duration(override.every), duration(cad.floor)
    return every is not None and floor is not None and every < floor


__all__ = ["FILE", "INSTANCE", "Connection", "PROBES", "Probe", "Reading", "ScheduleOverride", "VaultAsked", "below_floor",
           "default_vault_path", "load", "new_connection", "probe", "readings", "record_check", "save", "state_of",
           "store_path", "vault_path"]
