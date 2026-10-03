"""The write guard for jason-web: a Host check on every API request, and on every write an Origin check and a
per-process token.

jason-web binds 127.0.0.1, but loopback is not a boundary: any browser tab on the machine can send a request there.
Three layers (OWASP's CSRF guidance, as docs/console/security-and-privacy.md sets out for the console):

- **Host.** A request to ``/api/*``, and any write, must name a loopback host (``127.0.0.1``, ``localhost``, ``::1``)
  or the host a person passed with ``--host``; anything else is 421. This stops a DNS-rebinding page from reaching the
  API under its own name.
- **Origin.** A write (POST, PUT, PATCH, DELETE) must carry ``Origin`` equal to the request's own scheme-less host
  (``http://127.0.0.1:8080`` for ``Host: 127.0.0.1:8080``). A missing or ``null`` Origin is refused (403), and so is
  ``Sec-Fetch-Site`` other than ``same-origin`` when the browser sends it.
- **Token.** A random token made when the app is created, held in memory only, never written to ``data/`` or a log.
  The page gets it from ``<meta name="jason-token">`` in ``index.html`` or from ``GET /api/session``, and sends it as
  ``X-Jason-Token``. Every response also sets it as the ``jason_token`` cookie (HttpOnly, SameSite=Strict), so the
  pages written before the token existed keep writing jason's own stores. A write outside jason (an approval's
  ``check`` or ``apply``) takes the header only (``header_token_ok``).

The token is not a sign-in: a program on the machine can read ``/api/session`` as the page does. It guards against a
web page in the person's browser, which the Origin check already refuses, as a second, independent layer.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Iterable
from urllib.parse import urlsplit

from flask import Flask, current_app, jsonify, request

TOKEN_HEADER = "X-Jason-Token"
COOKIE = "jason_token"
META = "jason-token"
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
SAFE = frozenset({"GET", "HEAD", "OPTIONS"})
_ANY = frozenset({"", "0.0.0.0", "::"})


def hostname(host: str) -> str:
    """The name in a Host header, without its port: ``[::1]:8080`` -> ``::1``, ``localhost:8080`` -> ``localhost``."""
    host = (host or "").strip().lower()
    if host.startswith("["):
        return host[1:host.index("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _refuse(status: int, why: str):
    return jsonify(error=why), status


def install(app: Flask, *, hosts: Iterable[str] = (), token: str | None = None) -> str:
    """Guard ``app``'s API and writes; returns the token (also ``app.config["JASON_TOKEN"]``)."""
    token = token or secrets.token_urlsafe(32)
    allowed = LOOPBACK | {hostname(h) for h in hosts if hostname(h) not in _ANY}
    app.config["JASON_TOKEN"] = token
    app.config["JASON_HOSTS"] = sorted(allowed)

    @app.before_request
    def _guard():
        write = request.method not in SAFE
        if (write or request.path.startswith("/api/")) and hostname(request.host) not in allowed:
            return _refuse(421, f"host {hostname(request.host) or '(none)'} is not this server's: "
                                "jason-web answers on its loopback name")
        if not write:
            return None
        origin = request.headers.get("Origin", "")
        if not origin or origin == "null":
            return _refuse(403, "a write carries its page's Origin: send it from the console's own page")
        if urlsplit(origin).netloc.lower() != request.host.lower():
            return _refuse(403, f"a write from {origin} is not from this server's page")
        site = request.headers.get("Sec-Fetch-Site", "")
        if site and site != "same-origin":
            return _refuse(403, f"a write from a {site} page is refused")
        sent = request.headers.get(TOKEN_HEADER) or request.cookies.get(COOKIE) or ""
        if not _same(sent, token):
            return _refuse(403, f"a write carries this server's token ({TOKEN_HEADER}, from GET /api/session)")
        return None

    @app.after_request
    def _cookie(resp):
        if request.cookies.get(COOKIE) != token:
            resp.set_cookie(COOKIE, token, httponly=True, samesite="Strict", path="/")
        return resp

    return token


def header_token_ok() -> bool:
    """Whether the request carries the token in ``X-Jason-Token`` itself (the cookie alone is not enough)."""
    return _same(request.headers.get(TOKEN_HEADER, ""), current_app.config.get("JASON_TOKEN", ""))


def inject_meta(html: str, token: str) -> str:
    """``index.html`` with the token in a ``<meta>`` the page reads."""
    tag = f'<meta name="{META}" content="{token}">'
    lower = html.lower()
    at = lower.find("<head>")
    if at >= 0:
        return html[:at + 6] + tag + html[at + 6:]
    return tag + html


__all__ = ["COOKIE", "LOOPBACK", "META", "TOKEN_HEADER", "header_token_ok", "hostname", "inject_meta", "install"]
