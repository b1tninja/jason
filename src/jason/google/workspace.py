"""A community's own Google Workspace: where its OAuth client is kept, and how it is read, checked and written.

The OAuth client (client id and secret, from a Desktop app client in the community's own Cloud project) is the vault
entry ``jason/community/<profile>/google-workspace/oauth-client`` with the fields ``client_id``, ``client_secret`` and
``project_id``. A community whose path holds nothing may still be served by the installation's ``.env`` record
(``google_oauth_record_uid``) while ``settings.google_installation_client`` allows (default off, deprecated): that is the
installation's record, not the community's, and the read logs it as such. One community's client and tokens are never
read for another: every path carries the profile name.

Nothing here prints, logs or returns a secret except ``read_client`` / ``installation_client`` / ``community_client``,
which hand the client to the caller that signs in; messages carry names only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jason.google.errors import GoogleError
from jason.vault.paths import vault_path

log = logging.getLogger("jason.google.workspace")

INTEGRATION = "google-workspace"
DEFAULT_CLIENT = "oauth-client"
ENV_KEY = "google_oauth_record_uid"

_noted: set[str] = set()


class ClientFileError(ValueError):
    """A downloaded client JSON that cannot be used. The message names what is wrong, never a value."""


@dataclass(frozen=True)
class Client:
    """An OAuth client. ``repr`` shows no secret and no id."""

    client_id: str
    client_secret: str
    project_id: str = ""

    def __repr__(self) -> str:
        return f"Client(project_id={self.project_id!r})"

    def fields(self) -> dict[str, str]:
        return {"client_id": self.client_id, "client_secret": self.client_secret, "project_id": self.project_id}


def client_name_of(community: str) -> str:
    """The vault entry name for ``community``'s client: the profile's pin when it is the active profile, else the
    default. A profile that cannot load names none."""
    try:
        from jason.community import community as active
        from jason.community.profile import profile_name

        if community == profile_name():
            return active().google_workspace().client or DEFAULT_CLIENT
    except Exception:  # noqa: BLE001 - a profile that cannot load pins nothing
        pass
    return DEFAULT_CLIENT


def client_path(community: str, name: str = "") -> str:
    return vault_path(community, INTEGRATION, name or client_name_of(community))


def _fields_of(secret: Any) -> Client:
    lowered = {str(k).lower(): str(v) for k, v in dict(secret).items() if v}
    for label in ("client_id", "client_secret"):
        if not lowered.get(label):
            raise GoogleError(f"the Google OAuth client record is missing {label}")
    return Client(lowered["client_id"], lowered["client_secret"], lowered.get("project_id", ""))


def community_client(store: Any, community: str, name: str = "") -> Client | None:
    """The client at the community's own path, else None."""
    found = store.get(client_path(community, name)) if store is not None else None
    return _fields_of(found) if found else None


def installation_uid(settings: Any) -> str:
    from jason.vault.resolver import record_uids_of

    return record_uids_of(settings).get(ENV_KEY, "")


def installation_allowed(settings: Any) -> bool:
    return bool(getattr(settings, "google_installation_client", False))


def installation_client(vault: Any, settings: Any, store: Any = None) -> Client | None:
    """The client in the Keeper record ``.env`` names (the installation's record), else None. Read through ``store``
    (``load_by_uid``) when it has one, else through ``vault.load_record``."""
    from jason.vault.keeper import record_fields

    uid = installation_uid(settings)
    if not uid:
        return None
    loader = getattr(store, "load_by_uid", None)
    fields = loader(uid) if loader is not None else record_fields(vault.load_record(uid))
    return _fields_of(fields)


def note_installation(community: str, path: str) -> None:
    """Log, once a process per community, that the client is the installation's record."""
    if community in _noted:
        return
    _noted.add(community)
    log.warning("deprecated: the OAuth client for community %s is the installation's .env record, not this community's; "
                "`jason google adopt-installation-record` copies it to %s, or `jason google setup` stores the "
                "community's own", community, path)


# ----- reading a downloaded client -----


def read_client_file(path: str | Path) -> Client:
    """The id, secret and project of a Desktop client downloaded from the Cloud console (``client_secret_*.json``).
    A named ``ClientFileError`` for a file that is missing, not JSON, a Web client, or lacks a field."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        raise ClientFileError(f"{p.name}: the file cannot be read") from None
    try:
        data = json.loads(text)
    except ValueError:
        raise ClientFileError(f"{p.name}: not JSON; use the file the Cloud console's Download JSON gives") from None
    if not isinstance(data, dict):
        raise ClientFileError(f"{p.name}: not a Google OAuth client download")
    if "installed" not in data:
        if "web" in data:
            raise ClientFileError(f"{p.name}: a Web application client; jason's sign-in needs a Desktop app client "
                                  "(a Web client is for the console's sign-in: docs/integrations-design.md)")
        raise ClientFileError(f"{p.name}: no \"installed\" client in it; is this a Google OAuth client download?")
    body = data["installed"] if isinstance(data["installed"], dict) else {}
    missing = [k for k in ("client_id", "client_secret") if not str(body.get(k) or "")]
    if missing:
        raise ClientFileError(f"{p.name}: installed.{' and installed.'.join(missing)} missing")
    return Client(str(body["client_id"]), str(body["client_secret"]), str(body.get("project_id") or ""))


# ----- status -----


@dataclass(frozen=True)
class ClientState:
    """Where the client for a community would come from: ``community`` (its own path), ``installation`` (the ``.env``
    record, still in use), ``installation-off`` (only the ``.env`` record exists and the setting forbids it) or
    ``missing``. ``project_id`` is the community's record's, when it carries one."""

    source: str
    path: str
    project_id: str = ""
    problem: str = ""


def client_state(store: Any, settings: Any, community: str, name: str = "") -> ClientState:
    path = client_path(community, name)
    try:
        found = community_client(store, community, name) if store is not None else None
    except GoogleError:
        return ClientState("missing", path, problem="the record is missing client_id or client_secret")
    except Exception as exc:  # noqa: BLE001 - the vault did not answer
        return ClientState("missing", path, problem=f"the vault was not read: {type(exc).__name__}")
    if found is not None:
        return ClientState("community", path, found.project_id)
    if installation_uid(settings):
        return ClientState("installation" if installation_allowed(settings) else "installation-off", path)
    return ClientState("missing", path)


def status_text(state: ClientState) -> list[str]:
    if state.source == "community":
        return [f"OAuth client: in this community's vault ({state.path})"
                + (f"; project {state.project_id}" if state.project_id else "; the record names no project")]
    if state.source == "installation":
        return [f"OAuth client: the .env installation record ({ENV_KEY}) is in use: this is the installation's record, "
                "not this community's.",
                f"  `jason google setup --from-file client_secret.json` stores the community's own at {state.path}; "
                "`jason google adopt-installation-record --yes` copies the installation's there."]
    if state.source == "installation-off":
        return [f"OAuth client: none at {state.path}. The .env installation record exists but "
                "GOOGLE_INSTALLATION_CLIENT=0 turns it off for this community."]
    tail = f" ({state.problem})" if state.problem else ""
    return [f"OAuth client: none at {state.path}{tail}. Run `jason google setup`."]


def token_lines(tokens: Any) -> list[str]:
    """One line a token name: where it is read from and which scopes are covered or missing (short scope names).
    Never the token."""
    from jason.google.tokens import NAMES, scopes_of

    lines = []
    for name in NAMES:
        asked = scopes_of(name)
        found = tokens.locate(name, asked)
        if found.token is None:
            tail = f" (the vault was not read: {found.problem})" if found.problem else ""
            lines.append(f"  {name}: no token{tail}; `jason google sign-in --name {name} --interactive`")
            continue
        held = set(found.token.get("scopes") or ())
        short = [s.rsplit("/", 1)[-1] for s in asked if s not in held]
        fit = "all scopes covered" if not short else "missing scopes: " + ", ".join(short)
        where = f"read from the {found.where}"
        if found.where == "file" and tokens.vault is not None:
            where += " (a local file: the vault did not take it or has not been migrated; `jason vault migrate --yes`)"
        lines.append(f"  {name}: {where}; {fit}")
    return lines


__all__ = ["Client", "ClientFileError", "ClientState", "DEFAULT_CLIENT", "ENV_KEY", "INTEGRATION", "client_name_of",
           "client_path", "client_state", "community_client", "installation_allowed", "installation_client",
           "installation_uid", "note_installation", "read_client_file", "status_text", "token_lines"]
