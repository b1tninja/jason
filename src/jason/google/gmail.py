"""Gmail API helper. Read-only: list and fetch messages, never send or mutate."""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable

import httpx

from jason.google.errors import GoogleError

_API = "https://gmail.googleapis.com/gmail/v1"
# Gmail's published allowance is 15,000 quota units a minute per user (a read costs 5), but this project is refused
# well below it on a sustained run. One pace for every thread in the process, starting at 15 requests a second. A
# refusal pauses every thread for 30 seconds and doubles the spacing (to one request a second at most); each success
# eases it back by a hundredth. A refusal is retried for up to about seven minutes.
_MIN_INTERVAL = 0.066
_MAX_INTERVAL = 1.0
_RETRIES = 8
_pace = threading.Lock()
_next_at = [0.0]
_interval = [_MIN_INTERVAL]


def _wait_turn() -> None:
    with _pace:
        now = time.monotonic()
        slot = max(now, _next_at[0])
        _next_at[0] = slot + _interval[0]
    time.sleep(max(0.0, slot - now))


def _refused() -> None:
    with _pace:
        _interval[0] = min(_MAX_INTERVAL, _interval[0] * 2)
        _next_at[0] = max(_next_at[0], time.monotonic() + 30)


def _served() -> None:
    with _pace:
        _interval[0] = max(_MIN_INTERVAL, _interval[0] * 0.99)


def _throttled_get(http: httpx.Client, url: str, *, params: dict[str, Any], headers: dict[str, str],
                   renew: Callable[[str], dict[str, str]] | None = None) -> httpx.Response:
    renewed = False
    for attempt in range(_RETRIES + 1):
        _wait_turn()
        try:
            response = http.get(url, params=params, headers=headers)
        except httpx.TransportError:
            # A dropped connection ("forcibly closed by the remote host") is retried like a refusal.
            if attempt == _RETRIES:
                raise
            time.sleep(min(60, 5 * 2**attempt))
            continue
        # An access token lasts an hour; a long sync outlives it. Renew once and ask again.
        if response.status_code == 401 and renew is not None and not renewed:
            headers = renew(headers.get("Authorization", ""))
            renewed = True
            continue
        limited = response.status_code == 429 or (response.status_code == 403 and "quota" in response.text.lower())
        if not limited:
            _served()
            return response
        _refused()
        if attempt == _RETRIES:
            return response
        time.sleep(min(60, 5 * 2**attempt))
    return response


class GoogleGmail:
    """Authenticated Gmail v1 client. Share the Drive client's access token."""

    def __init__(
        self,
        access_token: str,
        *,
        http: httpx.Client | None = None,
        owns_http: bool = False,
        renew: Callable[[], str] | None = None,
    ) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._http = http or httpx.Client(timeout=60.0)
        self._owns_http = http is None or owns_http
        # Exchanges the refresh token for a new access token; None when the caller gave only an access token.
        self._renew = renew
        self._renew_lock = threading.Lock()

    def _renewed(self, stale: str) -> dict[str, str]:
        """Headers with a fresh token. Several workers can see the same 401; only the first renews."""
        with self._renew_lock:
            if self._renew is not None and stale == f"Bearer {self._token}":
                self._token = self._renew()
        return self._headers()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def list_messages(
        self, query: str, max_results: int = 20
    ) -> list[dict[str, Any]]:
        """Return message id/threadId rows matching ``query``."""
        response = self._http.get(
            f"{_API}/users/me/messages",
            params={"q": query, "maxResults": max_results},
            headers=self._headers(),
        )
        body = _ok(response, "listing messages")
        return list(body.get("messages") or [])

    def get_message(self, message_id: str) -> dict[str, Any]:
        """Fetch one message with ``format=full``."""
        response = self._http.get(
            f"{_API}/users/me/messages/{message_id}",
            params={"format": "full"},
            headers=self._headers(),
        )
        return _ok(response, f"reading message {message_id}")

    def iter_messages(self, query: str, *, page_size: int = 100, limit: int = 2000):
        """Yield every id/threadId row matching ``query``, page by page, up to ``limit``."""
        token = ""
        seen = 0
        while seen < limit:
            params: dict[str, Any] = {"q": query, "maxResults": min(page_size, limit - seen)}
            if token:
                params["pageToken"] = token
            body = _ok(_throttled_get(self._http, f"{_API}/users/me/messages", params=params, headers=self._headers(), renew=self._renewed), "listing messages")
            for row in body.get("messages") or []:
                seen += 1
                yield row
            token = str(body.get("nextPageToken") or "")
            if not token:
                return

    def get_metadata(self, message_id: str, headers: tuple[str, ...] = ("From", "To", "Subject", "Date")) -> dict[str, Any]:
        """One message's headers and part names only (``format=full`` without reading bodies is not offered, so the
        caller keeps only what it needs); no attachment is downloaded."""
        response = _throttled_get(
            self._http,
            f"{_API}/users/me/messages/{message_id}",
            params={"format": "full", "fields": "id,threadId,internalDate,labelIds,payload(headers,filename,mimeType,parts(filename,mimeType,body(size,attachmentId),parts(filename,mimeType,body(size,attachmentId),parts(filename,mimeType,body(size,attachmentId)))))"},
            headers=self._headers(),
            renew=self._renewed,
        )
        body = _ok(response, f"reading message {message_id}")
        wanted = {h.lower() for h in headers}
        head = {h["name"]: h.get("value", "") for h in (body.get("payload") or {}).get("headers") or [] if h.get("name", "").lower() in wanted}
        files: list[dict[str, Any]] = []

        def walk(part: dict[str, Any]) -> None:
            for child in part.get("parts") or []:
                if child.get("filename"):
                    body = child.get("body") or {}
                    files.append({"name": child["filename"], "type": child.get("mimeType", ""), "size": body.get("size"),
                                  "attachmentId": body.get("attachmentId", "")})
                walk(child)

        walk(body.get("payload") or {})
        return {"id": body.get("id"), "threadId": body.get("threadId"), "internalDate": body.get("internalDate"),
                "labels": body.get("labelIds") or [], "headers": head, "attachments": files}

    def get_body(self, message_id: str, headers: tuple[str, ...] = ("From", "X-Original-From", "X-Original-Sender")) -> dict[str, Any]:
        """One message's sender headers and its text and HTML parts, decoded (gmail.readonly; no attachment is
        downloaded). For a caller that reads one thing from the body (the signature) and keeps nothing else: the
        result is held in memory only, and the caller drops it."""
        import base64

        response = _throttled_get(
            self._http,
            f"{_API}/users/me/messages/{message_id}",
            params={"format": "full", "fields": "id,threadId,internalDate,labelIds,payload(headers,mimeType,filename,body(data),"
                    "parts(mimeType,filename,body(data),parts(mimeType,filename,body(data),parts(mimeType,filename,body(data)))))"},
            headers=self._headers(),
            renew=self._renewed,
        )
        body = _ok(response, f"reading message {message_id}")
        wanted = {h.lower() for h in headers}
        head = {h["name"]: h.get("value", "") for h in (body.get("payload") or {}).get("headers") or [] if h.get("name", "").lower() in wanted}
        found: dict[str, str] = {"text/plain": "", "text/html": ""}

        def walk(part: dict[str, Any]) -> None:
            kind = str(part.get("mimeType") or "").lower()
            data = (part.get("body") or {}).get("data")
            if kind in found and data and not part.get("filename") and not found[kind]:
                raw = base64.urlsafe_b64decode(str(data).encode("ascii") + b"=" * (-len(str(data)) % 4))
                found[kind] = raw.decode("utf-8", errors="replace")
            for child in part.get("parts") or []:
                walk(child)

        walk(body.get("payload") or {})
        return {"id": body.get("id"), "threadId": body.get("threadId"), "internalDate": body.get("internalDate"),
                "labels": body.get("labelIds") or [], "headers": head, "plain": found["text/plain"], "html": found["text/html"]}

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """One attachment's bytes (read-only)."""
        import base64

        response = _throttled_get(self._http, f"{_API}/users/me/messages/{message_id}/attachments/{attachment_id}", params={},
                                  headers=self._headers(), renew=self._renewed)
        body = _ok(response, f"reading an attachment of {message_id}")
        return base64.urlsafe_b64decode(str(body.get("data") or "").encode("ascii"))

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}


def _ok(response: httpx.Response, action: str) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    if not response.is_success:
        message = ""
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        detail = f": {message}" if message else ""
        raise GoogleError(f"HTTP {response.status_code} {action}{detail}")
    return body
