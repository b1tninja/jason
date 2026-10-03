"""Zoom's REST API (``https://api.zoom.us/v2``) for the association's account: meeting history, and one write.

Authentication is a Server-to-Server OAuth app the account owner creates in the Zoom App Marketplace. Its account id,
client id, and client secret are custom fields on a Keeper record (``zoom_record_uid``). ``POST
https://zoom.us/oauth/token`` with ``grant_type=account_credentials`` trades them for an hour's bearer token; the client
fetches a new one when it runs out. No person signs in and no browser opens.

Reads:

- ``GET /users/me/meetings?type=scheduled|previous_meetings``: the host's meetings;
- ``GET /past_meetings/{id}/instances``: every occurrence of a meeting id (a recurring board meeting keeps one id);
- ``GET /past_meetings/{uuid}`` and ``/participants``: one occurrence's times and who joined (participants need a
  paid plan; a refusal leaves them out);
- ``GET /users/me/recordings?from&to``: cloud recordings, a month at a time, each with its files (transcript VTT,
  chat, audio, video, and the AI Companion summary); a file is downloaded with the bearer token;
- ``GET /meetings/meeting_summaries`` and ``/meetings/{uuid}/meeting_summary``: the AI Companion summaries.

The one write is ``create_meeting`` (``POST /users/me/meetings``), used for a disciplinary hearing only when a person
passes ``--create --yes``. The response's ``start_url`` signs its holder in as the host: ``create_meeting`` drops it
before returning. The client does not update, delete, or end meetings, change settings, or delete recordings.

A past meeting's UUID can hold ``/`` or ``+``: it is URL-encoded, and encoded twice when it starts with ``/`` or holds
``//`` (Zoom's rule).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import httpx

API_URL = "https://api.zoom.us/v2/"
TOKEN_URL = "https://zoom.us/oauth/token"
USER_AGENT = "jason (Mystique Community Association; meeting history and hearings)"
RECORDING_WINDOW_DAYS = 30   # the recordings list takes a range of at most a month


class ZoomError(Exception):
    """Zoom answered with something other than the page it documents."""


class ZoomAuthError(ZoomError):
    """The app's credentials were refused, or the token lacks a scope the call needs."""


@dataclass(frozen=True)
class ZoomCredentials:
    """A Server-to-Server OAuth app's account id, client id, and client secret."""

    account_id: str
    client_id: str
    client_secret: str

    @classmethod
    def from_fields(cls, fields: dict[str, str]) -> ZoomCredentials:
        """From a Keeper record's custom fields, labels matched without case, ``-``, ``_``, or spaces."""
        norm = {"".join(ch for ch in k.lower() if ch.isalnum()): v for k, v in fields.items()}
        creds = cls(norm.get("accountid", ""), norm.get("clientid", ""), norm.get("clientsecret", ""))
        missing = [name for name, value in (("account_id", creds.account_id), ("client_id", creds.client_id),
                                            ("client_secret", creds.client_secret)) if not value]
        if missing:
            raise ZoomAuthError(f"the Zoom Keeper record lacks {', '.join(missing)}")
        return creds


def encode_uuid(uuid: str) -> str:
    """A meeting UUID as a path segment: encoded once, or twice when it starts with ``/`` or holds ``//``."""
    once = quote(uuid, safe="")
    return quote(once, safe="") if uuid.startswith("/") or "//" in uuid else once


class Zoom:
    """The association's Zoom account: meeting history read-only, and ``create_meeting``."""

    def __init__(self, credentials: ZoomCredentials, *, api_url: str = API_URL, token_url: str = TOKEN_URL,
                 http: httpx.Client | None = None, timeout: float = 60.0, user: str = "me") -> None:
        self._creds = credentials
        self._api = api_url.rstrip("/") + "/"
        self._token_url = token_url
        self._user = user
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=timeout, follow_redirects=True)
        self._token = ""
        self._expires = 0.0

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Zoom:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --- auth -----------------------------------------------------------------------------------------------------

    def token(self) -> str:
        """A bearer token, fetched again a minute before the last one runs out."""
        if self._token and time.monotonic() < self._expires - 60:
            return self._token
        response = self._http.post(
            self._token_url,
            data={"grant_type": "account_credentials", "account_id": self._creds.account_id},
            auth=(self._creds.client_id, self._creds.client_secret),
            headers={"User-Agent": USER_AGENT},
        )
        if response.status_code in (400, 401, 403):
            reason = _reason(response)
            raise ZoomAuthError(f"HTTP {response.status_code}: Zoom refused the app's credentials" + (f": {reason}" if reason else ""))
        if not response.is_success:
            raise ZoomError(f"HTTP {response.status_code} fetching a token")
        body = response.json()
        self._token = str(body.get("access_token") or "")
        if not self._token:
            raise ZoomAuthError("Zoom's token response had no access_token")
        self._expires = time.monotonic() + float(body.get("expires_in") or 3600)
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Accept": "application/json", "User-Agent": USER_AGENT}

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, json: Any = None,
                 missing_ok: bool = False) -> dict[str, Any] | None:
        response = self._http.request(method, self._api + path.lstrip("/"), params=params, json=json, headers=self._headers())
        if response.status_code == 401:
            # A token can be revoked before it expires: fetch one more time.
            self._token = ""
            response = self._http.request(method, self._api + path.lstrip("/"), params=params, json=json, headers=self._headers())
        if missing_ok and response.status_code in (400, 404):
            return None
        if response.status_code in (401, 403):
            raise ZoomAuthError(f"HTTP {response.status_code} on {path}: {_message(response)} (does the app have the scope?)")
        if response.status_code == 429:
            raise ZoomError(f"HTTP 429 on {path}: Zoom's rate limit; run again later")
        if not response.is_success:
            raise ZoomError(f"HTTP {response.status_code} on {path}: {_message(response)}")
        return response.json() if response.content else {}

    def _get(self, path: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> dict[str, Any] | None:
        return self._request("GET", path, params=params, missing_ok=missing_ok)

    def _pages(self, path: str, key: str, params: dict[str, Any] | None = None, *, missing_ok: bool = False) -> Iterator[dict[str, Any]]:
        """Every row of a paged list, following ``next_page_token``."""
        query = {"page_size": 300, **(params or {})}
        while True:
            body = self._get(path, query, missing_ok=missing_ok)
            if body is None:
                return
            yield from body.get(key) or []
            token = body.get("next_page_token")
            if not token:
                return
            query["next_page_token"] = token

    # --- reads ----------------------------------------------------------------------------------------------------

    def meetings(self, kind: str = "scheduled") -> Iterator[dict[str, Any]]:
        """The host's meetings: ``scheduled``, ``upcoming``, or ``previous_meetings``."""
        return self._pages(f"users/{self._user}/meetings", "meetings", {"type": kind})

    def past_instances(self, meeting_id: int | str) -> list[dict[str, Any]]:
        """Every ended occurrence of a meeting id (``uuid``, ``start_time``); empty when Zoom has none."""
        body = self._get(f"past_meetings/{meeting_id}/instances", missing_ok=True)
        return list((body or {}).get("meetings") or [])

    def past_meeting(self, uuid: str) -> dict[str, Any] | None:
        """One ended occurrence: topic, start and end, duration, participant count."""
        return self._get(f"past_meetings/{encode_uuid(uuid)}", missing_ok=True)

    def participants(self, uuid: str) -> list[dict[str, Any]]:
        """Who joined one occurrence, with join and leave times; empty when the plan or the meeting has none."""
        try:
            return list(self._pages(f"past_meetings/{encode_uuid(uuid)}/participants", "participants", missing_ok=True))
        except ZoomAuthError:
            return []

    def recordings(self, since: date, until: date) -> Iterator[dict[str, Any]]:
        """Cloud recordings from ``since`` to ``until``, asked a month at a time; each carries ``recording_files``."""
        start = since
        while start <= until:
            end = min(start + timedelta(days=RECORDING_WINDOW_DAYS - 1), until)
            yield from self._pages(f"users/{self._user}/recordings", "meetings", {"from": start.isoformat(), "to": end.isoformat()})
            start = end + timedelta(days=1)

    def summaries(self, since: date, until: date) -> Iterator[dict[str, Any]]:
        """The AI Companion summaries made from ``since`` to ``until`` (the list only: meeting UUID, topic, times)."""
        start = since
        while start <= until:
            end = min(start + timedelta(days=RECORDING_WINDOW_DAYS - 1), until)
            params = {"from": f"{start.isoformat()}T00:00:00Z", "to": f"{end.isoformat()}T23:59:59Z"}
            yield from self._pages("meetings/meeting_summaries", "summaries", params, missing_ok=True)
            start = end + timedelta(days=1)

    def summary(self, uuid: str) -> dict[str, Any] | None:
        """One meeting's AI Companion summary: overview, details by topic, next steps (the edited version when there is one)."""
        return self._get(f"meetings/{encode_uuid(uuid)}/meeting_summary", missing_ok=True)

    def download(self, url: str, dest: Path) -> Path:
        """Save a recording file. The bearer token goes to Zoom's host only; the redirect to storage carries none."""
        response = self._http.get(url, headers={"Authorization": f"Bearer {self.token()}", "User-Agent": USER_AGENT})
        if not response.is_success:
            raise ZoomError(f"HTTP {response.status_code} downloading {url.split('?')[0]}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest

    # --- the one write --------------------------------------------------------------------------------------------

    def in_meeting_control(self, meeting_id: int | str, method: str, params: dict[str, Any] | None = None) -> None:
        """One in-meeting control on a live meeting (``PATCH /live_meetings/{id}/events``): ``recording.start``,
        ``recording.pause``, ``recording.resume``, ``recording.stop``. The app acts as the meeting's host."""
        self._request("PATCH", f"live_meetings/{meeting_id}/events", json={"method": method, "params": params or {}})

    def caption_token(self, meeting_id: int | str) -> str:
        """The meeting's closed-caption URL (``GET /meetings/{id}/token?type=closed_caption_token``). Text posted to it
        shows in every participant's captions; the host must allow the caption API token in the meeting's settings."""
        answer = self._request("GET", f"meetings/{meeting_id}/token", params={"type": "closed_caption_token"}) or {}
        token = str(answer.get("token") or "")
        if not token:
            raise ZoomError(f"meeting {meeting_id} gave no caption token; is 'Allow use of caption API token' on for the host?")
        return token

    def post_caption(self, caption_url: str, seq: int, text: str, *, lang: str = "en-US") -> None:
        """Post one line of caption text to the caption URL; ``seq`` counts up by one per line for the meeting."""
        response = self._http.post(caption_url, params={"seq": seq, "lang": lang}, content=text.encode("utf-8"),
                                   headers={"Content-Type": "text/plain", "User-Agent": USER_AGENT})
        if not response.is_success:
            raise ZoomError(f"HTTP {response.status_code} posting a caption: {_message(response)}")

    def create_meeting(self, body: dict[str, Any]) -> dict[str, Any]:
        """Schedule a meeting on the host's account. The host's ``start_url`` is removed from what is returned."""
        created = self._request("POST", f"users/{self._user}/meetings", json=body) or {}
        created.pop("start_url", None)
        return created


def _reason(response: httpx.Response) -> str:
    """The token endpoint's ``reason`` ("The app has been disabled by the developer"), which never echoes the secret."""
    try:
        return str(response.json().get("reason") or "")
    except Exception:
        return ""


def _message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("message") or "")
    except Exception:
        return response.text[:200]


__all__ = ["API_URL", "TOKEN_URL", "Zoom", "ZoomAuthError", "ZoomCredentials", "ZoomError", "encode_uuid"]
