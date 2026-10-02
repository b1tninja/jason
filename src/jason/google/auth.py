"""Browser sign-in for the Google OAuth client stored in Keeper.

The client id and secret identify the app. A refresh token still requires one
user consent. This opens a browser only when that token is missing or rejected.
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from jason.google.errors import GoogleError
from jason.google.scopes import GOOGLE_SCOPES

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


def authorize_in_browser(
    client_id: str,
    client_secret: str,
    token_path: str | Path,
    *,
    opener: Callable[[str], Any] = webbrowser.open,
    http: httpx.Client | None = None,
    scopes: tuple[str, ...] = GOOGLE_SCOPES,
) -> str:
    """Open a browser, catch the localhost redirect, and store the refresh token (for ``scopes``; Photos keeps its
    own token so its consent never touches Drive's)."""
    code, redirect_uri = _listen_for_code(client_id, opener, scopes)
    client = http or httpx.Client(timeout=60.0)
    owns = http is None
    try:
        response = client.post(
            _TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
    finally:
        if owns:
            client.close()
    try:
        body = response.json()
    except json.JSONDecodeError:
        body = {}
    if not isinstance(body, dict):
        body = {}
    refresh = str(body.get("refresh_token") or "")
    if not refresh:
        raise GoogleError("Google did not return a refresh token")
    path = Path(token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        # What Google granted (a person may untick a scope on the consent screen), else what was asked.
        json.dumps({"refresh_token": refresh, "scopes": str(body.get("scope") or "").split() or list(scopes)}, indent=2),
        encoding="utf-8",
    )
    return refresh


def token_has_scopes(saved: dict[str, Any], scopes: tuple[str, ...] = GOOGLE_SCOPES) -> bool:
    """True when the stored grant includes every scope we request now."""
    granted = set(saved.get("scopes") or [])
    return set(scopes).issubset(granted)


def _listen_for_code(client_id: str, opener: Callable[[str], Any], scopes: tuple[str, ...] = GOOGLE_SCOPES) -> tuple[str, str]:
    holder: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            query = parse_qs(urlparse(self.path).query)
            holder["code"] = (query.get("code") or [""])[0]
            holder["error"] = (query.get("error") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab.")

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}/"
    url = _AUTH_URL + "?" + urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "prompt": "consent",
        }
    )
    print("Opening a browser for Google sign-in.", flush=True)
    print(url, flush=True)
    opener(url)
    print("Waiting for Google sign-in in the browser...", flush=True)
    server.handle_request()
    server.server_close()
    if holder.get("error"):
        raise GoogleError(f"Google sign-in was declined: {holder['error']}")
    if not holder.get("code"):
        raise GoogleError("Google sign-in did not return a code")
    return holder["code"], redirect_uri
