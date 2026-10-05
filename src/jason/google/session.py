"""Open a Google client from the OAuth client in the vault and the local refresh token.

The client is the community's vault entry ``google-workspace/oauth-client`` (``client_id`` and ``client_secret``
fields), else the Keeper record ``google_oauth_record_uid`` names (``jason.vault.resolver``; the fallback is logged as
deprecated). The token files stay where ``google_oauth_token_file`` puts them, one set for the installation: storing a
token per community and account in the vault is build step 3 (docs/integrations-design.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from jason.google.auth import authorize_in_browser, token_has_scopes
from jason.google.drive import GoogleDrive
from jason.google.errors import GoogleAuthRequired, GoogleError

INTEGRATION, CLIENT = "google-workspace", "oauth-client"


def oauth_client(settings: Any, vault: Any, *, store: Any = None, community: str = "") -> tuple[str, str]:
    """The OAuth client's id and secret: the vault path first (``store``; a ``VaultSession`` given as ``vault``
    supplies one when ``store`` is not), else the Keeper record ``google_oauth_record_uid`` names."""
    from jason.secrets import VaultSession
    from jason.vault.keeper import KeeperStore, record_fields
    from jason.vault.resolver import CredentialMissing, credential, credential_path, record_uids_of

    if not community:
        from jason.community.profile import profile_name

        community = profile_name()
    if store is None and isinstance(vault, VaultSession):
        store = KeeperStore.from_session(vault)
    uids = record_uids_of(settings)
    try:
        secret = credential(community, INTEGRATION, CLIENT, store=store, record_uids=uids,
                            load_record=lambda uid: record_fields(vault.load_record(uid)))
    except CredentialMissing:
        raise GoogleError(f"google_oauth_record_uid is not set (and the vault holds nothing at "
                          f"{credential_path(community, INTEGRATION, CLIENT)})") from None
    return _field(secret, "client_id"), _field(secret, "client_secret")


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
    client_id, client_secret = oauth_client(settings, vault, store=store)
    token_path = Path(settings.google_oauth_token_file)
    saved: dict[str, Any] = {}
    refresh = ""
    if token_path.is_file():
        saved = json.loads(token_path.read_text(encoding="utf-8"))
        refresh = str(saved.get("refresh_token") or "")
    if not refresh or not token_has_scopes(saved):
        refresh = _sign_in(sign_in, client_id, client_secret, token_path, interactive)
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
        refresh = _sign_in(sign_in, client_id, client_secret, token_path, interactive)
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
    client_id, client_secret = oauth_client(settings, vault, store=store)
    token_path = Path(settings.google_oauth_token_file).with_name(token_name)
    saved = json.loads(token_path.read_text(encoding="utf-8")) if token_path.is_file() else {}
    refresh = str(saved.get("refresh_token") or "")
    if not refresh or not token_has_scopes(saved, scopes):
        refresh = _sign_in(sign_in, client_id, client_secret, token_path, interactive)
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
    token_path: Path,
    interactive: bool,
) -> str:
    if not interactive:
        raise GoogleAuthRequired(
            "Google sign-in needs a browser. Pass interactive=True."
        )
    return sign_in(client_id, client_secret, token_path)


def _field(custom: Any, label: str) -> str:
    for key, value in custom.items():
        if key.lower() == label and value:
            return value
    raise GoogleError(f"Keeper OAuth record is missing {label}")
