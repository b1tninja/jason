"""Open a Google client from the OAuth client and the refresh token, both in the credential vault.

The client is the community's vault entry ``google-workspace/oauth-client`` (``client_id`` and ``client_secret``
fields), else the Keeper record ``google_oauth_record_uid`` names (``jason.vault.resolver``; the fallback is logged as
deprecated). The refresh token is read vault first (``google-workspace/token/<name>``), then the local file where
``google_oauth_token_file`` puts it (``jason.google.tokens``), so a worktree or another working directory with no
``secrets/`` folder still opens. A sign-in (``interactive`` only) saves to both.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from jason.google.auth import authorize_in_browser, token_has_scopes
from jason.google.drive import GoogleDrive
from jason.google.errors import GoogleAuthRequired, GoogleError
from jason.google.scopes import GOOGLE_SCOPES
from jason.google.tokens import DRIVE, name_of_file, token_store

INTEGRATION, CLIENT = "google-workspace", "oauth-client"
NEEDS_BROWSER = "Google sign-in needs a browser. Pass interactive=True."


def oauth_client(settings: Any, vault: Any, *, store: Any = None, community: str = "") -> tuple[str, str]:
    """The OAuth client's id and secret: the community's own vault path first (``store``; a ``VaultSession`` given as
    ``vault`` supplies one when ``store`` is not; the profile may pin the entry's name, ``Community.google_workspace``),
    else, while ``settings.google_installation_client`` allows (default), the Keeper record ``google_oauth_record_uid``
    names: the installation's record, logged as not this community's. Another community's path is never read."""
    from jason.google import workspace
    from jason.secrets import VaultSession
    from jason.vault.keeper import KeeperStore

    if not community:
        from jason.community.profile import profile_name

        community = profile_name()
    if store is None and isinstance(vault, VaultSession):
        store = KeeperStore.from_session(vault)
    own = workspace.community_client(store, community)
    if own is not None:
        return own.client_id, own.client_secret
    path = workspace.client_path(community)
    if workspace.installation_allowed(settings) and workspace.installation_uid(settings):
        found = workspace.installation_client(vault, settings)
        if found is not None:
            workspace.note_installation(community, path)
            return found.client_id, found.client_secret
    raise GoogleError(f"google_oauth_record_uid is not set (and the vault holds nothing at {path}); "
                      "`jason google setup` stores this community's own OAuth client")


def open_drive(
    settings: Any,
    vault: Any,
    *,
    interactive: bool = False,
    authorize: Any = None,
    http: httpx.Client | None = None,
    store: Any = None,
) -> GoogleDrive:
    """Build a Drive client.

    A missing or rejected token, or a token that lacks the current scopes,
    opens a browser only when ``interactive`` is true.
    """
    sign_in = authorize or authorize_in_browser
    store = _vault_store(vault, store)
    client_id, client_secret = oauth_client(settings, vault, store=store)
    tokens = token_store(settings, store)
    saved = tokens.load(DRIVE, GOOGLE_SCOPES) or {}
    refresh = str(saved.get("refresh_token") or "")
    if not refresh or not token_has_scopes(saved):
        refresh = _sign_in(sign_in, client_id, client_secret, tokens, DRIVE, GOOGLE_SCOPES, interactive)
    try:
        return GoogleDrive.from_refresh_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh,
            http=http,
        )
    except GoogleError as exc:
        if isinstance(exc, GoogleAuthRequired):
            raise
        refresh = _sign_in(sign_in, client_id, client_secret, tokens, DRIVE, GOOGLE_SCOPES, interactive)
        return GoogleDrive.from_refresh_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh,
            http=http,
        )


def open_scoped(settings: Any, vault: Any, factory: Any, scopes: tuple[str, ...], token_name: str, *,
                interactive: bool = False, authorize: Any = None, http: httpx.Client | None = None, store: Any = None):
    """A Google client (``factory.from_refresh_token``) on the same OAuth client as Drive, with a token of its own
    beside Drive's (``token_name``), so granting a new API never asks Drive to consent again. A missing token, or one
    without the scopes, needs a person's consent in a browser (``interactive``)."""
    from functools import partial

    sign_in = partial(authorize or authorize_in_browser, scopes=scopes)
    store = _vault_store(vault, store)
    client_id, client_secret = oauth_client(settings, vault, store=store)
    tokens = token_store(settings, store)
    name = name_of_file(token_name)
    saved = tokens.load(name, scopes) or {}
    refresh = str(saved.get("refresh_token") or "")
    if not refresh or not token_has_scopes(saved, scopes):
        refresh = _sign_in(sign_in, client_id, client_secret, tokens, name, scopes, interactive)
    return factory.from_refresh_token(client_id=client_id, client_secret=client_secret, refresh_token=refresh, http=http)


def open_photos(settings: Any, vault: Any, **kwargs: Any):
    """Google Photos: the Picker and jason's own albums (``google-photos-token.json``)."""
    from jason.google.photos import GooglePhotos
    from jason.google.scopes import PHOTOS_SCOPES

    return open_scoped(settings, vault, GooglePhotos, PHOTOS_SCOPES, "google-photos-token.json", **kwargs)


def open_vault(settings: Any, vault: Any, **kwargs: Any):
    """Google Vault: matters and legal holds (``google-vault-token.json``)."""
    from jason.google.scopes import VAULT_SCOPES
    from jason.google.vault import GoogleVault

    return open_scoped(settings, vault, GoogleVault, VAULT_SCOPES, "google-vault-token.json", **kwargs)


def open_tasks(settings: Any, vault: Any, **kwargs: Any):
    """Google Tasks: the board's action items as a task list (``google-tasks-token.json``)."""
    from jason.google.scopes import TASKS_SCOPES
    from jason.google.tasks import GoogleTasks

    return open_scoped(settings, vault, GoogleTasks, TASKS_SCOPES, "google-tasks-token.json", **kwargs)


def _sign_in(
    sign_in: Any,
    client_id: str,
    client_secret: str,
    tokens: Any,
    name: str,
    scopes: tuple[str, ...],
    interactive: bool,
) -> str:
    """A person's browser sign-in (``interactive`` only). With a vault the sign-in writes only a temporary file, which
    is read back for the scopes Google granted and removed; the token is then saved through ``tokens.save``, to the
    vault alone. With no vault the sign-in writes the local file as before."""
    if not interactive:
        raise GoogleAuthRequired(NEEDS_BROWSER)
    # A refresh token is given once, at consent. Nothing may discard it before it is saved: the temporary copy is
    # removed only after ``tokens.save`` has put the token in the vault (or, if the vault refuses, the local file).
    if tokens.vault is None:
        refresh = sign_in(client_id, client_secret, tokens.file.path_of(name))
        written = tokens.file.load(name)
        granted = _granted(written, refresh, scopes)
        tokens.save(name, refresh, granted)
        return refresh
    import tempfile

    from jason.google.tokens import FileTokenStore

    with tempfile.TemporaryDirectory(prefix="jason-signin-") as scratch:
        temporary = FileTokenStore(Path(scratch) / "token.json")
        refresh = sign_in(client_id, client_secret, temporary.path_of(name))
        granted = _granted(temporary.load(name), refresh, scopes)
        tokens.save(name, refresh, granted)
    return refresh


def _granted(written: Any, refresh: str, asked: tuple[str, ...]) -> list[str]:
    """The scopes Google granted (a person may untick one on the consent screen), else those asked."""
    return list(written["scopes"]) if written and written["refresh_token"] == refresh and written["scopes"] \
        else list(asked)


def _vault_store(vault: Any, store: Any) -> Any:
    """The ``SecretStore`` for the vault: the one given, else one over a ``VaultSession``, else None (the file alone)."""
    from jason.secrets import VaultSession
    from jason.vault.keeper import KeeperStore

    if store is None and isinstance(vault, VaultSession):
        return KeeperStore.from_session(vault)
    return store


def _field(custom: Any, label: str) -> str:
    for key, value in custom.items():
        if key.lower() == label and value:
            return value
    raise GoogleError(f"Keeper OAuth record is missing {label}")
