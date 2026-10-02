"""Google Vault (``vault.googleapis.com/v1``): the Workspace's own matters and legal holds.

A matter is a case file; a hold in it preserves a corpus (Drive, Mail, Groups, Chat, Voice, Calendar) for named accounts
or an organizational unit, even if a person deletes the items. A Drive hold covers the whole account; a Mail hold can be
narrowed by search terms and dates. Only the Workspace's own accounts can be held: a personal Google account, a Zoom
cloud recording, or a file on disk is outside Vault.

The signed-in account needs a Vault role (Manage Matters, Manage Holds) granted in the Admin console, and the
``ediscovery`` scope, on a token of its own. jason reads matters and holds freely; it creates a matter or a hold, or adds
an account to one, only when a person passes ``--yes``. It never deletes or closes a matter or releases a hold: counsel
releases a hold, and a person does it in Vault.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterator

import httpx

from jason.google.errors import GoogleError

API = "https://vault.googleapis.com/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class Corpus(Enum):
    DRIVE = "DRIVE"
    MAIL = "MAIL"
    GROUPS = "GROUPS"
    CHAT = "HANGOUTS_CHAT"
    VOICE = "VOICE"
    CALENDAR = "CALENDAR"


class GoogleVault:
    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=60.0)

    @classmethod
    def from_refresh_token(cls, *, client_id: str, client_secret: str, refresh_token: str,
                           http: httpx.Client | None = None) -> GoogleVault:
        client = http or httpx.Client(timeout=60.0)
        response = client.post(_TOKEN_URL, data={"client_id": client_id, "client_secret": client_secret,
                                                 "refresh_token": refresh_token, "grant_type": "refresh_token"})
        token = (response.json() if response.content else {}).get("access_token")
        if not token:
            raise GoogleError("the Vault token was refused; sign in again with `jason vault --check --interactive`")
        vault = cls(str(token), http=client)
        vault._owns_http = http is None
        return vault

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> GoogleVault:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _call(self, method: str, path: str, *, params: dict[str, Any] | None = None, body: Any = None) -> dict[str, Any]:
        response = self._http.request(method, f"{API}/{path.lstrip('/')}", params=params, json=body,
                                      headers={"Authorization": f"Bearer {self._token}"})
        if response.status_code == 403:
            raise GoogleError("HTTP 403 from Vault: the signed-in account needs a Vault role (Manage Matters, Manage Holds), "
                              "and the Workspace plan must include Vault")
        if not response.is_success:
            try:
                message = response.json().get("error", {}).get("message", "")
            except Exception:
                message = response.text[:200]
            raise GoogleError(f"HTTP {response.status_code} {method} {path}: {message}")
        return response.json() if response.content else {}

    # --- reads ----------------------------------------------------------------------------------------------------

    def matters(self, *, state: str = "") -> Iterator[dict[str, Any]]:
        """Every matter the account can see (``state``: OPEN, CLOSED, DELETED), with the full view."""
        params: dict[str, Any] = {"pageSize": 100, "view": "FULL"}
        if state:
            params["state"] = state
        while True:
            body = self._call("GET", "matters", params=params)
            yield from body.get("matters") or []
            if not body.get("nextPageToken"):
                return
            params["pageToken"] = body["nextPageToken"]

    def matter(self, matter_id: str) -> dict[str, Any]:
        return self._call("GET", f"matters/{matter_id}", params={"view": "FULL"})

    def holds(self, matter_id: str) -> Iterator[dict[str, Any]]:
        params: dict[str, Any] = {"pageSize": 100, "view": "FULL_HOLD"}
        while True:
            body = self._call("GET", f"matters/{matter_id}/holds", params=params)
            yield from body.get("holds") or []
            if not body.get("nextPageToken"):
                return
            params["pageToken"] = body["nextPageToken"]

    # --- writes (a person passes --yes) ---------------------------------------------------------------------------

    def create_matter(self, name: str, description: str = "") -> dict[str, Any]:
        return self._call("POST", "matters", body={"name": name, "description": description})

    def create_hold(self, matter_id: str, name: str, corpus: Corpus, emails: list[str], *, terms: str = "",
                    start: str = "", end: str = "", shared_drives: bool = True) -> dict[str, Any]:
        """A hold on ``corpus`` for the named accounts. Mail may be narrowed by ``terms`` and an RFC 3339 window."""
        if not emails:
            raise GoogleError("a hold needs at least one account")
        body: dict[str, Any] = {"name": name, "corpus": corpus.value, "accounts": [{"email": e} for e in emails]}
        if corpus is Corpus.DRIVE:
            body["query"] = {"driveQuery": {"includeSharedDriveFiles": shared_drives}}
        elif corpus is Corpus.MAIL and (terms or start or end):
            body["query"] = {"mailQuery": {k: v for k, v in (("terms", terms), ("startTime", start), ("endTime", end)) if v}}
        return self._call("POST", f"matters/{matter_id}/holds", body=body)

    def add_held_accounts(self, matter_id: str, hold_id: str, emails: list[str]) -> dict[str, Any]:
        return self._call("POST", f"matters/{matter_id}/holds/{hold_id}:addHeldAccounts", body={"emails": emails})


__all__ = ["API", "Corpus", "GoogleVault"]
