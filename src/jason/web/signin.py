"""Sign in with Google for jason-web: OpenID Connect's authorization-code flow, run on the server, with PKCE.

The person's browser goes to Google and comes back to ``/auth/google/callback`` with a code; the server trades the
code for an ID token directly with Google (its client secret, over HTTPS) and reads who signed in. That account is
let in only when all of these hold (Google's guidance: docs/setup.md "Console sign-in"):

- the ID token is for this client (``aud``), from Google (``iss``), unexpired, and carries the ``nonce`` this server
  sent, and the ``state`` round-trips;
- the email is verified, and when the profile names its email domains (``Community.email_domains``), the token's
  ``hd`` claim is one of them (``hd`` sent to Google is a hint only; the claim is what counts);
- the email is an officer's (``Community.officers``, the ``email`` in ``officers.json``): sign-in names a person on
  the roster and grants what the roster grants, nothing more.

The signed-in person is kept in Flask's signed session cookie (``jason_session``: HttpOnly, SameSite=Lax), signed
with a key made when the app starts, so a restart signs everyone out, and it lasts at most ``LIFETIME``. No Google
token is kept: jason-web asks only ``openid email profile`` and never calls a Google API in the person's name.

While someone is signed in, a write's ``by`` must be that person's name (an empty ``by`` is filled with it), so the
record names who actually signed in; the approvals routes take the name from the session and record ``via``
``console:google``. ``jason-web --require-sign-in`` refuses every write until someone signs in. Sign-in is not a role:
what a person may approve is still the roster's (``Officer.approves``), and the write guard (``jason.web.guard``)
still applies to every write.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from flask import Flask, jsonify, redirect, request, session

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
SCOPES = "openid email profile"
START = "/auth/google"
CALLBACK = "/auth/google/callback"
SIGN_OUT = "/auth/signout"
RECORD_KEY = "google_signin_record_uid"     # .env: the Keeper record holding the Web client's id and secret
LIFETIME = timedelta(hours=12)
PENDING_SECONDS = 600                        # a sign-in started and not finished in ten minutes starts over
VIA = "console:google"
SAFE = frozenset({"GET", "HEAD", "OPTIONS"})


class Refused(ValueError):
    """A sign-in that is not let in, in words a person can act on."""


@dataclass(frozen=True)
class Client:
    """The Web application OAuth client (not the Desktop client jason's own Google calls use)."""

    client_id: str
    client_secret: str


@dataclass(frozen=True)
class Account:
    """Who is signed in: the officer the Google account matched, and the account itself."""

    name: str
    role: str
    email: str
    sub: str = ""
    at: str = ""


@dataclass(frozen=True)
class Person:
    """One roster row sign-in can match: an officer with an email."""

    name: str
    role: str
    email: str


Exchange = Callable[[Client, str, str, str], dict[str, Any]]   # client, code, redirect_uri, verifier -> token reply


@dataclass
class SignIn:
    """What sign-in reads. ``configured`` says a client is set up (cheap: no Keeper read); ``client`` loads it."""

    configured: bool
    client: Callable[[], Client]
    roster: Callable[[], tuple[Person, ...]]
    domains: Callable[[], tuple[str, ...]]
    exchange: Exchange
    required: bool = False
    log: Path | None = None
    _client: Client | None = field(default=None, repr=False)

    def load_client(self) -> Client:
        if self._client is None:
            self._client = self.client()
        return self._client


def _settings():
    from jason.config import Settings

    return Settings.load()


def default_client() -> Client:
    """The Web client from Keeper: the record named by ``google_signin_record_uid`` in .env, with custom fields
    ``client_id`` and ``client_secret``. Read without a prompt; a missing Keeper login raises KeeperAuthRequired."""
    from jason.secrets import VaultSession, extract_custom_fields

    settings = _settings()
    uid = settings.record_uids.get(RECORD_KEY, "")
    if not uid:
        raise Refused(f"{RECORD_KEY} is not set in .env")
    custom = extract_custom_fields(VaultSession.from_settings(settings, interactive=False).load_record(uid))
    cid, secret = str(custom.get("client_id") or "").strip(), str(custom.get("client_secret") or "").strip()
    if not cid or not secret:
        raise Refused("the sign-in Keeper record needs custom fields client_id and client_secret")
    return Client(cid, secret)


def default_roster() -> tuple[Person, ...]:
    from jason.community import community

    return tuple(Person(o.name, o.role.value, o.email.strip().lower()) for o in community().officers() if o.email.strip())


def default_domains() -> tuple[str, ...]:
    from jason.community import community

    return tuple(d.strip().lower() for d in community().email_domains() if d.strip())


def default_exchange(client: Client, code: str, redirect_uri: str, verifier: str) -> dict[str, Any]:
    """Trade the code for tokens at Google's token endpoint (``client_secret`` and the PKCE verifier)."""
    import httpx

    resp = httpx.post(TOKEN_URL, data={"code": code, "client_id": client.client_id, "client_secret": client.client_secret,
                                       "redirect_uri": redirect_uri, "grant_type": "authorization_code",
                                       "code_verifier": verifier}, timeout=20)
    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    if resp.status_code != 200:
        raise Refused(f"Google refused the code: {body.get('error_description') or body.get('error') or resp.status_code}")
    return body


def default_sign_in(*, required: bool = False) -> SignIn:
    """Sign-in as the .env and the profile set it up. ``configured`` only when ``google_signin_record_uid`` is set."""
    try:
        configured = bool(_settings().record_uids.get(RECORD_KEY))
    except Exception:  # noqa: BLE001 - no .env is no sign-in, not a crash
        configured = False
    from jason.mcp.county import _data_dir

    return SignIn(configured=configured, client=default_client, roster=default_roster, domains=default_domains,
                  exchange=default_exchange, required=required, log=_data_dir(None) / "web" / "sign-ins.jsonl")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def claims_of(id_token: str) -> dict[str, Any]:
    """The ID token's payload. Its signature is not checked: the token came straight from Google's token endpoint over
    HTTPS, in exchange for this client's secret, which Google's OpenID Connect guide says is enough. It is never
    passed on to anything else."""
    parts = (id_token or "").split(".")
    if len(parts) != 3:
        raise Refused("Google's answer carried no ID token")
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        out = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (ValueError, UnicodeDecodeError) as exc:
        raise Refused("the ID token could not be read") from exc
    if not isinstance(out, dict):
        raise Refused("the ID token could not be read")
    return out


def account_for(claims: dict[str, Any], *, client_id: str, nonce: str, roster: tuple[Person, ...],
                domains: tuple[str, ...], now: float | None = None) -> Account:
    """The officer a verified Google account is, or ``Refused`` with the reason. Every check in the module doc."""
    now = time.time() if now is None else now
    if claims.get("iss") not in ISSUERS:
        raise Refused("the ID token is not from Google")
    aud = claims.get("aud")
    if aud != client_id and not (isinstance(aud, list) and client_id in aud):
        raise Refused("the ID token is for another client")
    try:
        exp = float(claims.get("exp"))
    except (TypeError, ValueError) as exc:
        raise Refused("the ID token has no expiry") from exc
    if exp < now - 60:
        raise Refused("the ID token has expired: sign in again")
    if not nonce or not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise Refused("the sign-in did not come back as it was sent (nonce): sign in again")
    email = str(claims.get("email") or "").strip().lower()
    if not email or claims.get("email_verified") not in (True, "true"):
        raise Refused("Google did not vouch for this account's email address")
    hd = str(claims.get("hd") or "").strip().lower()
    if domains and hd not in domains:
        raise Refused(f"{email} is not an account of the association's Google Workspace")
    match = [p for p in roster if p.email == email]
    if not match:
        raise Refused(f"{email} is not an officer's account: the manager adds its email to the officers' roster")
    if len(match) > 1:
        raise Refused(f"{email} is on the roster for more than one person: the manager corrects the roster")
    p = match[0]
    return Account(p.name, p.role, email, str(claims.get("sub") or ""),
                   datetime.now(timezone.utc).isoformat(timespec="seconds"))


def current_account() -> Account | None:
    """Who is signed in on this request, from the session; None when no one is."""
    raw = session.get("account")
    if not isinstance(raw, dict) or not raw.get("name"):
        return None
    try:
        return Account(**{k: str(raw.get(k, "")) for k in ("name", "role", "email", "sub", "at")})
    except TypeError:
        return None


def signed_in_name() -> str:
    a = current_account()
    return a.name if a else ""


def _next(value: str) -> str:
    """Where to land after sign-in: a console route (``#/...``) only, so the callback is never an open redirect."""
    value = (value or "").strip()
    return value if value.startswith("#/") and "\n" not in value and len(value) < 200 else ""


def _log(sign_in: SignIn, event: str, **fields: Any) -> None:
    if sign_in.log is None:
        return
    try:
        sign_in.log.parent.mkdir(parents=True, exist_ok=True)
        row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": event, **fields}
        with sign_in.log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass  # the log is a record of sign-ins, not a gate on them


def install(app: Flask, sign_in: SignIn) -> None:
    """The sign-in routes, the session settings, and the write check. Install after ``guard.install``."""
    from jason.web.guard import hostname

    app.secret_key = app.secret_key or secrets.token_bytes(32)
    app.config.update(SESSION_COOKIE_NAME="jason_session", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=LIFETIME)
    app.extensions["jason_sign_in"] = sign_in

    def ours() -> bool:
        return hostname(request.host) in set(app.config.get("JASON_HOSTS", ()))

    def back(error: str = "", to: str = ""):
        if error:
            session["signInError"] = error
        return redirect("/" + to)

    @app.get(START)
    def google_start():
        if not ours():
            return "jason-web answers on its loopback name", 421
        to = _next(request.args.get("next", ""))
        if not sign_in.configured:
            return back(f"Google sign-in is not set up: see docs/setup.md, Console sign-in ({RECORD_KEY})", to)
        try:
            client = sign_in.load_client()
        except Exception as exc:  # noqa: BLE001 - said on the page, not a crash
            hint = " (run `jason login` in a terminal)" if type(exc).__name__.endswith("AuthRequired") else ""
            return back(f"Google sign-in could not read its client: {exc}{hint}", to)
        verifier = _b64(secrets.token_bytes(48))
        pending = {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24), "verifier": verifier,
                   "next": to, "at": time.time()}
        session["pending"] = pending
        session.pop("signInError", None)
        params = {"client_id": client.client_id, "redirect_uri": request.host_url.rstrip("/") + CALLBACK,
                  "response_type": "code", "scope": SCOPES, "state": pending["state"], "nonce": pending["nonce"],
                  "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
                  "code_challenge_method": "S256", "prompt": "select_account"}
        domains = sign_in.domains()
        if len(domains) == 1:
            params["hd"] = domains[0]                  # a hint for Google's account chooser; the claim is checked
        return redirect(f"{AUTH_URL}?{urlencode(params)}")

    @app.get(CALLBACK)
    def google_callback():
        if not ours():
            return "jason-web answers on its loopback name", 421
        pending = session.pop("pending", None)
        if not isinstance(pending, dict) or time.time() - float(pending.get("at", 0)) > PENDING_SECONDS:
            return back("the sign-in took too long or was not started here: sign in again")
        if not hmac.compare_digest(str(request.args.get("state", "")), str(pending.get("state", ""))):
            return back("the sign-in did not come back as it was sent (state): sign in again")
        to = _next(str(pending.get("next", "")))
        if request.args.get("error"):
            return back(f"Google did not sign you in: {request.args['error']}", to)
        code = request.args.get("code", "")
        if not code:
            return back("Google's answer carried no code: sign in again", to)
        try:
            client = sign_in.load_client()
            tokens = sign_in.exchange(client, code, request.host_url.rstrip("/") + CALLBACK, str(pending["verifier"]))
            account = account_for(claims_of(str(tokens.get("id_token", ""))), client_id=client.client_id,
                                  nonce=str(pending.get("nonce", "")), roster=sign_in.roster(), domains=sign_in.domains())
        except Refused as exc:
            _log(sign_in, "refused", why=str(exc))
            return back(str(exc), to)
        except Exception as exc:  # noqa: BLE001 - the network or Keeper: said, not a crash
            _log(sign_in, "failed", why=f"{type(exc).__name__}")
            return back(f"sign-in failed: {type(exc).__name__}: {exc}", to)
        session.clear()
        session.permanent = True
        session["account"] = asdict(account)
        _log(sign_in, "signed in", name=account.name, role=account.role, email=account.email, sub=account.sub)
        return redirect("/" + to)

    @app.post(SIGN_OUT)
    def sign_out():
        a = current_account()
        session.clear()
        if a:
            _log(sign_in, "signed out", name=a.name, email=a.email)
        return jsonify(ok=True, signedIn=None)

    @app.before_request
    def _signed_in():
        """On a write: refuse it without a sign-in when one is required; with one, the record names that person."""
        if request.method in SAFE or not request.path.startswith("/api/"):
            return None
        a = current_account()
        if a is None:
            if sign_in.required:
                return jsonify(error="sign in with Google first (Sign in, at the top of the console): this jason-web "
                                     "takes writes only from a signed-in officer"), 401
            return None
        if a.name not in {p.name for p in sign_in.roster()}:
            session.clear()
            return jsonify(error=f"{a.name} is no longer on the officers' roster: signed out"), 401
        body = request.get_json(silent=True)
        if isinstance(body, dict) and "by" in body:
            given = str(body.get("by") or "").strip()
            if not given:
                body["by"] = a.name                    # the cached body the route reads
            elif given.casefold() != a.name.casefold():
                return jsonify(error=f"signed in as {a.name}: a step goes on the record under the signed-in "
                                     f"name, not {given}"), 403
        return None


def session_info() -> dict[str, Any]:
    """What ``GET /api/session`` adds: who is signed in, whether sign-in is set up or required, its last refusal."""
    from flask import current_app

    sign_in: SignIn | None = current_app.extensions.get("jason_sign_in")
    a = current_account()
    error = session.pop("signInError", "") if "signInError" in session else ""
    return {"signedIn": {"name": a.name, "role": a.role, "email": a.email, "provider": "google", "at": a.at} if a else None,
            "signIn": {"provider": "google", "configured": bool(sign_in and sign_in.configured),
                       "required": bool(sign_in and sign_in.required), "start": START, "signOut": SIGN_OUT},
            "signInError": error}


__all__ = ["Account", "CALLBACK", "Client", "Person", "RECORD_KEY", "Refused", "SCOPES", "SIGN_OUT", "START", "SignIn",
           "VIA", "account_for", "claims_of", "current_account", "default_sign_in", "install", "session_info",
           "signed_in_name"]
