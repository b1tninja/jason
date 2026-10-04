"""Sign in with Google for jason-web: OpenID Connect's authorization-code flow, run on the server, with PKCE.

The person's browser goes to Google and comes back to ``/auth/google/callback`` with a code; the server trades the
code for an ID token directly with Google (its client secret, over HTTPS) and reads who signed in. That account is
let in only when all of these hold (Google's guidance: docs/setup.md "Console sign-in"):

- the ID token is for the client the person chose (``aud``), from Google (``iss``), unexpired, and carries the
  ``nonce`` this server sent, and the ``state`` round-trips;
- the email is verified, and when that client names email domains, the token's ``hd`` claim is one of them (``hd``
  sent to Google is a hint only; the claim is what counts);
- the email is on the roster: the community's officers (``Community.officers``), the managers whose portfolio holds
  this community, and jason's admins (``jason.access``). Sign-in names a person and grants what the roster grants.

**Providers.** A community sets up its own Google Sign-In (``Community.sign_in``: one or more clients, each with its
own domains); the installation may add its own (``jason.access.installation_sign_in``: a management company's
Workspace, for admins and managers). With neither, the .env client: ``google_signin_record_uid``, else jason's own
Desktop client (``google_oauth_record_uid``). The console shows one button a provider.

The signed-in person is kept in Flask's signed session cookie (``jason_session``: HttpOnly, SameSite=Lax), signed
with a key made when the app starts, so a restart signs everyone out, and it lasts at most ``LIFETIME``. No Google
token is kept: jason-web asks only ``openid email profile`` and never calls a Google API in the person's name.

While someone is signed in, a write's ``by`` must be that person's name (an empty ``by`` is filled with it), so the
record names who actually signed in; the approvals routes take the name from the session and record ``via``
``console:google``. ``jason-web --require-sign-in`` refuses every write until someone signs in. Sign-in is not a role:
what a person may approve is still the roster's (``Officer.approves``), and the write guard (``jason.web.guard``)
still applies to every write.

One person may hold two offices (two roster rows with one name): sign-in matches them once, with the offices joined.
Under ``jason-web --dev`` (not production), a signed-in admin may view the console as any person on the roster or any
office (``POST /auth/act-as``), to build and check role-based views. Every write is refused while they view as
someone else, so no record ever carries a name its person did not sign in as.
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
ACT_AS = "/auth/act-as"
RECORD_KEY = "google_signin_record_uid"     # .env: a Web application client's Keeper record (the fallback)
DESKTOP_KEY = "google_oauth_record_uid"     # .env: jason's own Desktop client, the last fallback
LIFETIME = timedelta(hours=12)
PENDING_SECONDS = 600                        # a sign-in started and not finished in ten minutes starts over
VIA = "console:google"
SAFE = frozenset({"GET", "HEAD", "OPTIONS"})


class Refused(ValueError):
    """A sign-in that is not let in, in words a person can act on."""


@dataclass(frozen=True)
class Client:
    """An OAuth client: its id and secret, read from Keeper."""

    client_id: str
    client_secret: str


@dataclass
class Provider:
    """One way to sign in, resolved for this jason-web: its key, its button's words, where it was set up
    (``community``, ``jason``, or an .env key), the domains it accepts (empty: any), and how to load its client."""

    key: str
    label: str
    source: str
    domains: tuple[str, ...]
    client: Callable[[], Client]
    _loaded: Client | None = field(default=None, repr=False)

    def load(self) -> Client:
        if self._loaded is None:
            self._loaded = self.client()
        return self._loaded


@dataclass(frozen=True)
class Account:
    """Who is signed in: the person the Google account matched, the account itself, and the provider used."""

    name: str
    role: str
    email: str
    sub: str = ""
    at: str = ""
    admin: bool = False
    provider: str = ""


@dataclass(frozen=True)
class Person:
    """One person on the roster: their roles joined (``"secretary, treasurer"``, ``"manager"``, ``"admin"``), the
    address they sign in with (empty: cannot sign in), and whether they are one of jason's admins."""

    name: str
    role: str
    email: str
    admin: bool = False


@dataclass(frozen=True)
class Acting:
    """Who an admin views the console as under ``--dev``: a person on the roster, or an office with no person."""

    name: str
    role: str


Exchange = Callable[[Client, str, str, str], dict[str, Any]]   # client, code, redirect_uri, verifier -> token reply


@dataclass
class SignIn:
    """What sign-in reads: the providers (cheap: no Keeper read until one is used), the roster, the token exchange."""

    providers: Callable[[], tuple[Provider, ...]]
    roster: Callable[[], tuple[Person, ...]]
    exchange: Exchange
    required: bool = False
    log: Path | None = None
    dev: bool = False                         # jason-web --dev: an admin may view the console as anyone
    _cache: dict[str, Provider] = field(default_factory=dict, repr=False)

    def all(self) -> tuple[Provider, ...]:
        """The providers, each kept once so its client is read from Keeper once."""
        out = []
        for p in self.providers():
            out.append(self._cache.setdefault(p.key, p))
        return tuple(out)

    @property
    def configured(self) -> bool:
        try:
            return bool(self.all())
        except Exception:  # noqa: BLE001 - a broken setup is no sign-in, said at the start route
            return False

    def provider(self, key: str = "") -> Provider:
        found = self.all()
        if not found:
            raise Refused(f"Google sign-in is not set up: see docs/setup.md, Console sign-in ({DESKTOP_KEY})")
        return next((p for p in found if p.key == key), found[0]) if key else found[0]


def _settings():
    from jason.config import Settings

    return Settings.load()


def client_record(settings: Any) -> tuple[str, str]:
    """The .env fallback: a Web application client (``google_signin_record_uid``) when one is set, else jason's own
    Desktop client (``google_oauth_record_uid``), which Google lets redirect to any loopback address and port with
    nothing registered. ``("", "")`` when neither."""
    web = str(getattr(settings, "record_uids", {}).get(RECORD_KEY, "") or "")
    if web:
        return web, RECORD_KEY
    desktop = str(getattr(settings, DESKTOP_KEY, "") or "")
    return (desktop, DESKTOP_KEY) if desktop else ("", "")


def keeper_client(record_uid: str) -> Callable[[], Client]:
    """A loader for the Google client in a Keeper record: ``client_id`` and ``client_secret`` as custom fields, or the
    id as the login and the secret as the password (as ``jason sign-in --import-client`` stores them). Read without a
    prompt; a missing Keeper login raises KeeperAuthRequired."""

    def load() -> Client:
        from jason.secrets import VaultSession, _field_value, extract_custom_fields

        record = VaultSession.from_settings(_settings(), interactive=False).load_record(record_uid)
        custom = extract_custom_fields(record)
        cid = str(custom.get("client_id") or _field_value(record, "login") or "").strip()
        secret = str(custom.get("client_secret") or _field_value(record, "password") or "").strip()
        if not cid or not secret:
            raise Refused("the sign-in Keeper record needs the client id (client_id, or the login) and the secret "
                          "(client_secret, or the password)")
        return Client(cid, secret)
    return load


def default_providers() -> tuple[Provider, ...]:
    """The community's providers, then the installation's; with neither, the .env client."""
    from jason.access import installation_sign_in
    from jason.community import community

    c = community()
    own_domains = tuple(d.strip().lower() for d in c.email_domains() if d.strip())
    out = [Provider(p.key, p.label, "community", p.domains or own_domains, keeper_client(p.record_uid))
           for p in c.sign_in()]
    out += [Provider(p.key, p.label, "jason", p.domains, keeper_client(p.record_uid)) for p in installation_sign_in()
            if p.key not in {q.key for q in out}]
    if not out:
        uid, key = client_record(_settings())
        if uid:
            out.append(Provider("google", "", key, own_domains, keeper_client(uid)))
    return tuple(out)


def roster_of(officers: Any, admins: Any = (), managers: Any = (), community: str = "") -> tuple[Person, ...]:
    """One ``Person`` a name: a person's offices joined and their first address; the managers whose portfolio holds
    ``community`` as its manager; jason's admins marked (added with the role ``admin`` when they hold no office)."""
    people: dict[str, Person] = {}

    def add(name: str, role: str, email: str, admin: bool = False) -> None:
        p = people.get(name)
        roles = [r for r in (p.role.split(", ") if p and p.role else []) if r]
        if role and role not in roles:
            roles.append(role)
        people[name] = Person(name, ", ".join(roles), (p.email if p and p.email else email.strip().lower()),
                              admin or bool(p and p.admin))

    for o in officers:
        add(o.name, o.role.value, o.email)
    for m in managers:
        if m.manages(community):
            hit = next((p for p in people.values() if p.email and p.email == m.email.strip().lower()), None)
            add(hit.name if hit else m.name, "manager", m.email)
    for a in admins:
        hit = next((p for p in people.values() if p.email and p.email == a.email.strip().lower()), None)
        if hit is not None:
            add(hit.name, "", hit.email, True)
        else:
            add(a.name, "admin", a.email, True)
    return tuple(people.values())


def default_roster() -> tuple[Person, ...]:
    from jason.access import admins, managers
    from jason.community import community
    from jason.community.profile import profile_name

    return roster_of(community().officers(), admins(), managers(), profile_name())


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


def default_sign_in(*, required: bool = False, dev: bool = False) -> SignIn:
    """Sign-in as the community, the installation, and the .env set it up."""
    from jason.mcp.county import _data_dir

    return SignIn(providers=default_providers, roster=default_roster, exchange=default_exchange, required=required,
                  log=_data_dir(None) / "web" / "sign-ins.jsonl", dev=dev)


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
                domains: tuple[str, ...], now: float | None = None, provider: str = "") -> Account:
    """The person a verified Google account is, or ``Refused`` with the reason. Every check in the module doc."""
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
        raise Refused(f"{email} is not an account of the Google Workspace this sign-in accepts")
    match = [p for p in roster if p.email and p.email == email]
    if not match:
        raise Refused(f"{email} is not on the roster: add it to the officers (or to jason's admins or managers)")
    if len({p.name for p in match}) > 1:
        raise Refused(f"{email} is on the roster for more than one person: correct the roster")
    p = match[0]
    return Account(p.name, p.role, email, str(claims.get("sub") or ""),
                   datetime.now(timezone.utc).isoformat(timespec="seconds"), p.admin, provider)


def current_account() -> Account | None:
    """Who is signed in on this request, from the session; None when no one is."""
    raw = session.get("account")
    if not isinstance(raw, dict) or not raw.get("name"):
        return None
    try:
        return Account(**{k: str(raw.get(k, "")) for k in ("name", "role", "email", "sub", "at", "provider")},
                       admin=raw.get("admin") is True)
    except TypeError:
        return None


def acting_as() -> Acting | None:
    """Who an admin is viewing the console as (``--dev``); None when they view it as themselves."""
    raw = session.get("acting")
    if not isinstance(raw, dict) or not (raw.get("name") or raw.get("role")):
        return None
    return Acting(str(raw.get("name", "")), str(raw.get("role", "")))


def signed_in_name() -> str:
    a = current_account()
    return a.name if a else ""


def _next(value: str) -> str:
    """Where to land after sign-in: a console route (``#/...``) only, so the callback is never an open redirect."""
    value = (value or "").strip()
    return value if value.startswith("#/") and "\n" not in value and len(value) < 200 else ""


def _log(sign_in: SignIn, event: str, **fields: Any) -> None:
    """One line in ``web/sign-ins.jsonl``. A ``why`` is free text (a refusal can name an address not on the roster):
    contact details in it are masked as the audit log masks them. The signed-in account's own ``email`` is its id."""
    from jason.approvals.audit import mask

    if sign_in.log is None:
        return
    if "why" in fields:
        fields["why"] = mask(str(fields["why"]))
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
        try:
            provider = sign_in.provider(request.args.get("provider", ""))
            client = provider.load()
        except Refused as exc:
            return back(str(exc), to)
        except Exception as exc:  # noqa: BLE001 - said on the page, not a crash
            hint = " (run `jason login` in a terminal)" if type(exc).__name__.endswith("AuthRequired") else ""
            _log(sign_in, "client failed", why=f"{type(exc).__name__}: {exc}")
            return back(f"Google sign-in could not read its client: {exc}{hint}", to)
        verifier = _b64(secrets.token_bytes(48))
        pending = {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24), "verifier": verifier,
                   "next": to, "provider": provider.key, "at": time.time()}
        session["pending"] = pending
        session.pop("signInError", None)
        params = {"client_id": client.client_id, "redirect_uri": request.host_url.rstrip("/") + CALLBACK,
                  "response_type": "code", "scope": SCOPES, "state": pending["state"], "nonce": pending["nonce"],
                  "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
                  "code_challenge_method": "S256", "prompt": "select_account"}
        if len(provider.domains) == 1:
            params["hd"] = provider.domains[0]         # a hint for Google's account chooser; the claim is checked
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
            provider = sign_in.provider(str(pending.get("provider", "")))
            client = provider.load()
            tokens = sign_in.exchange(client, code, request.host_url.rstrip("/") + CALLBACK, str(pending["verifier"]))
            account = account_for(claims_of(str(tokens.get("id_token", ""))), client_id=client.client_id,
                                  nonce=str(pending.get("nonce", "")), roster=sign_in.roster(), domains=provider.domains,
                                  provider=provider.key)
        except Refused as exc:
            _log(sign_in, "refused", why=str(exc))
            return back(str(exc), to)
        except Exception as exc:  # noqa: BLE001 - the network or Keeper: said, not a crash
            _log(sign_in, "failed", why=f"{type(exc).__name__}")
            return back(f"sign-in failed: {type(exc).__name__}: {exc}", to)
        from jason.web.access import close_private

        close_private("signed in again")              # a new sign-in never inherits a private view
        session.clear()
        session.permanent = True
        session["account"] = asdict(account)
        _log(sign_in, "signed in", name=account.name, role=account.role, email=account.email, sub=account.sub,
             provider=account.provider)
        return redirect("/" + to)

    @app.post(SIGN_OUT)
    def sign_out():
        from jason.web.access import close_private

        a = current_account()
        close_private("signed out")                    # the private view closes with the sign-in, and says so
        session.clear()
        if a:
            _log(sign_in, "signed out", name=a.name, email=a.email)
        return jsonify(ok=True, signedIn=None)

    @app.post(ACT_AS)
    def act_as():
        """Under ``--dev``, a signed-in admin views the console as a person on the roster (``{"name": ...}``) or an
        office (``{"role": ...}``); ``{}`` goes back to themselves. Writes are refused while acting."""
        from jason.community.base import OfficerRole

        a = current_account()
        if not sign_in.dev:
            return jsonify(error="viewing as someone else needs jason-web --dev (not production)"), 403
        if a is None or not a.admin:
            return jsonify(error="only one of jason's admins (data/access/admins.json), signed in, may view as "
                                 "someone else"), 403
        body = request.get_json(silent=True) or {}
        name, role = str(body.get("name") or "").strip(), str(body.get("role") or "").strip().lower()
        if name:
            p = next((p for p in sign_in.roster() if p.name == name), None)
            if p is None:
                return jsonify(error=f"{name} is not on the roster"), 400
            acting = None if p.name == a.name else Acting(p.name, p.role)
        elif role:
            if role not in {r.value for r in OfficerRole}:
                return jsonify(error=f"no office {role}: one of {', '.join(r.value for r in OfficerRole)}"), 400
            acting = Acting("", role)
        else:
            acting = None
        if acting is None:
            session.pop("acting", None)
        else:
            session["acting"] = asdict(acting)
        _log(sign_in, "acting as" if acting else "stopped acting", name=a.name,
             **({"as": acting.name or acting.role} if acting else {}))
        return jsonify(ok=True, acting=asdict(acting) if acting else None)

    @app.before_request
    def _signed_in():
        """On a write: refuse it without a sign-in when one is required; with one, the record names that person; while
        an admin views as someone else, refuse it."""
        if request.method in SAFE or not request.path.startswith("/api/"):
            return None
        acting = acting_as()
        if acting is not None:
            return jsonify(error=f"viewing as {acting.name or 'the ' + acting.role} (admin view): writes are "
                                 "refused. Go back to yourself to write in your own name"), 403
        a = current_account()
        if a is None:
            if sign_in.required:
                return jsonify(error="sign in with Google first (Sign in, at the top of the console): this jason-web "
                                     "takes writes only from a signed-in person on the roster"), 401
            return None
        if a.name not in {p.name for p in sign_in.roster()}:
            session.clear()
            return jsonify(error=f"{a.name} is no longer on the roster: signed out"), 401
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
    """What ``GET /api/session`` adds: who is signed in, the ways to sign in, whether it is required, its last
    refusal, and under ``--dev`` whom an admin may view the console as."""
    from flask import current_app

    from jason.community.base import OfficerRole

    sign_in: SignIn | None = current_app.extensions.get("jason_sign_in")
    a = current_account()
    error = session.pop("signInError", "") if "signInError" in session else ""
    try:
        providers = sign_in.all() if sign_in else ()
    except Exception as exc:  # noqa: BLE001 - a broken setup shows as a refusal, not a crash
        providers, error = (), error or f"Google sign-in is not set up correctly: {exc}"
    can_act = bool(sign_in and sign_in.dev and a and a.admin)
    acting = acting_as() if can_act else None
    return {"signedIn": {"name": a.name, "role": a.role, "email": a.email, "provider": a.provider or "google",
                         "at": a.at, "admin": a.admin} if a else None,
            "signIn": {"provider": "google", "configured": bool(providers),
                       "required": bool(sign_in and sign_in.required), "start": START, "signOut": SIGN_OUT,
                       "dev": bool(sign_in and sign_in.dev), "actAs": ACT_AS,
                       "providers": [{"key": p.key, "label": p.label, "source": p.source} for p in providers]},
            "signInError": error,
            "canActAs": can_act,
            "acting": asdict(acting) if acting else None,
            "actAsPeople": [{"name": p.name, "role": p.role} for p in sign_in.roster()] if can_act and sign_in else [],
            "actAsRoles": [r.value for r in OfficerRole] if can_act else []}


__all__ = ["ACT_AS", "Account", "Acting", "CALLBACK", "Client", "Person", "Provider", "RECORD_KEY", "Refused", "SCOPES",
           "SIGN_OUT", "START", "SignIn", "VIA", "account_for", "acting_as", "claims_of", "client_record",
           "current_account", "default_sign_in", "install", "keeper_client", "roster_of", "session_info",
           "signed_in_name"]
