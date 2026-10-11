"""Choose files from a person's own Google Drive with Google's Picker, the redirect form (docs/google-picker.md).

``GET /auth/google/pick?next=#/route&slot=&purpose=split|slot`` sends a signed-in board member to Google's authorization endpoint
with ``trigger_onepick=true`` and the one scope ``drive.file``. Google shows its Picker; the person's choice comes back to
``GET /auth/google/pick/callback`` as ``picked_file_ids`` and a ``code``. The **server** trades the code (the community's Web
client and its secret, from the vault) for an access token held in one local variable, reads each picked file once, read-only
(``jason.tasks.drive_pick``), and drops the token: no refresh token is asked for (``access_type=online``), none is stored, logged,
put in the session, or sent to the page. The page is redirected to ``next`` with ``?pick=<result token>``; it reads the result
once with ``POST /api/drive/pick/result``.

- **Who**: a signed-in person on the roster whose offices open the board's level (P2), not viewing as someone else, and only while
  the community's ``pick.enabled`` switch is on. The pick is written under the signed-in person's name.
- **State**: a random value, kept hashed on disk with the person, purpose and an end time (``pick.state_minutes``), and in the
  session. The callback needs both, claims the disk record by an atomic rename (so it works once), and refuses a forged, reused,
  expired, or another person's state.
- **Nothing in a URL but ids Google sent and an opaque result token.** No file name or Drive id is logged; the sign-in log gets
  events and counts only.
"""

from __future__ import annotations

import hmac
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, redirect, request, session

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.file"
START = "/auth/google/pick"
CALLBACK = "/auth/google/pick/callback"
RESULT = "/api/drive/pick/result"
KEY = "jason_pick"                                 # app.extensions
SESSION_KEY = "pick"


class Refused(ValueError):
    """A pick that cannot go on, in words a person can act on."""


@dataclass
class PickDeps:
    """What a pick reads, replaceable in a test: trade a code for an access token, build a Drive client from the token, find the
    data folder and the community. Nothing here is a module-level state; ``app.extensions`` holds the one instance."""

    exchange: Callable[[Any, str, str], str]
    drive: Callable[[str], Any]
    root: Callable[[], Path]
    community: Callable[[], Any] | None = None


def default_exchange(client: Any, code: str, redirect_uri: str) -> str:
    """The code for an access token at Google's token endpoint, with the Web client's secret. Returns the token; any refresh token in
    the answer is ignored and not kept. Google's text is not passed on (it can echo parts of a request)."""
    import httpx

    try:
        resp = httpx.post(TOKEN_URL, data={"code": code, "client_id": client.client_id, "client_secret": client.client_secret,
                                           "redirect_uri": redirect_uri, "grant_type": "authorization_code"}, timeout=20)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    except (httpx.HTTPError, ValueError):
        raise Refused("jason could not reach Google to finish the pick. Nothing was read.") from None
    if resp.status_code != 200 or not isinstance(body, dict) or not body.get("access_token"):
        err = str(body.get("error", "")) if isinstance(body, dict) else ""
        raise Refused("Google would not give jason access to the picked files" + (f" ({err})" if err.isalpha() or "_" in err else "")
                      + ". Nothing was read. Start the pick again.")
    scope = str(body.get("scope") or "")
    if scope and SCOPE not in scope.split():
        raise Refused("Google's answer did not include the Drive file permission. Nothing was read.")
    return str(body["access_token"])


def default_drive(token: str) -> Any:
    from jason.google.drive import GoogleDrive

    return GoogleDrive(token)


def default_deps() -> PickDeps:
    from jason.mcp.county import _data_dir

    return PickDeps(exchange=default_exchange, drive=default_drive, root=lambda: Path(_data_dir(None)))


def deps() -> PickDeps:
    found = current_app.extensions.get(KEY)
    return found if found is not None else default_deps()


def install(app: Any, pick_deps: PickDeps | None = None) -> None:
    app.extensions[KEY] = pick_deps or default_deps()
    app.register_blueprint(blueprint())


def _community(d: PickDeps) -> Any:
    if d.community is not None:
        return d.community()
    try:
        from jason.community import community

        return community()
    except Exception:  # noqa: BLE001 - limits read their defaults without a community
        return None


def _who():
    """The viewer and the signed-in account, or the response that refuses. The board's level, not viewing as another person."""
    from jason.web import access
    from jason.web.signin import current_account

    viewer = access.signed_in()
    access.allow(viewer, access.Level.P2)
    account = current_account()
    if account is None or viewer.acting:
        raise _Stop(access.refusal(403, "Choosing from Google Drive is done as yourself: go back to your own view first."))
    return account


class _NoRequestLines(logging.Filter):
    """httpx logs each request line at INFO, and a Drive request's URL holds the file's id. While a pick is read, those lines are
    dropped; the filter is removed as the read ends."""

    def filter(self, record: logging.LogRecord) -> bool:
        return False


@contextmanager
def _quiet_requests():
    drop, names = _NoRequestLines(), ("httpx", "httpcore")
    for name in names:
        logging.getLogger(name).addFilter(drop)
    try:
        yield
    finally:
        for name in names:
            logging.getLogger(name).removeFilter(drop)


class _Stop(Exception):
    def __init__(self, response: Any):
        self.response = response


def _client(account: Any) -> Any:
    from jason.web.signin import Refused as SignInRefused

    sign_in = current_app.extensions.get("jason_sign_in")
    try:
        return sign_in.provider(account.provider).load()
    except SignInRefused as exc:
        raise Refused(str(exc)) from None
    except Exception as exc:  # noqa: BLE001 - the vault or Keeper: said, not a crash
        hint = " (run `jason login` in a terminal)" if type(exc).__name__.endswith("AuthRequired") else ""
        raise Refused(f"jason could not read the community's Google client{hint}.") from None


def _slot(value: str) -> str:
    from jason.tasks import drive_pick

    value = (value or "").strip()
    return value if drive_pick.SLOT_RE.match(value) else ""


def session_info() -> dict[str, Any]:
    """What ``GET /api/session`` adds: whether choosing from the person's own Drive is on for this community, and where it starts."""
    from jason import limits

    d = deps()
    try:
        on = bool(limits.value("pick.enabled", community=_community(d)))
    except Exception:  # noqa: BLE001 - a limit that cannot be read is off
        on = False
    return {"enabled": on, "start": START, "result": RESULT}


def blueprint() -> Blueprint:
    bp = Blueprint("pick", __name__)

    @bp.get(START)
    def pick_start():
        from jason import limits
        from jason.tasks import drive_pick
        from jason.web import access
        from jason.web.guard import hostname
        from jason.web.signin import _next

        if hostname(request.host) not in set(current_app.config.get("JASON_HOSTS", ())):
            return "jason-web answers on its loopback name", 421
        try:
            account = _who()
        except _Stop as stop:
            return stop.response
        d = deps()
        try:
            limits.check("pick.enabled", True, community=_community(d), record=False)
        except limits.LimitReached as exc:
            return access.refusal(403, str(exc))
        try:
            purpose = drive_pick.Purpose(request.args.get("purpose", "split"))
        except ValueError:
            return access.refusal(400, "The purpose of a pick is split or slot.")
        try:
            client = _client(account)
        except Refused as exc:
            return access.refusal(409, str(exc))
        to = _next(request.args.get("next", ""))
        state = drive_pick.new_state(d.root(), by=account.name, purpose=purpose, slot=_slot(request.args.get("slot", "")), to=to,
                                     community=_community(d))
        session[SESSION_KEY] = {"state": state}
        params = {"client_id": client.client_id, "redirect_uri": request.host_url.rstrip("/") + CALLBACK, "response_type": "code",
                  "scope": SCOPE, "access_type": "online", "prompt": "consent", "trigger_onepick": "true", "state": state,
                  "allow_multiple": "true", "mimetypes": drive_pick.PDF}
        return redirect(f"{AUTH_URL}?{urlencode(params)}")

    @bp.get(CALLBACK)
    def pick_callback():
        from jason import limits
        from jason.tasks import drive_pick
        from jason.web import access
        from jason.web.guard import hostname

        if hostname(request.host) not in set(current_app.config.get("JASON_HOSTS", ())):
            return "jason-web answers on its loopback name", 421
        try:
            account = _who()
        except _Stop as stop:
            return stop.response
        d = deps()
        community = _community(d)
        held = session.pop(SESSION_KEY, None)
        sent = str(request.args.get("state", ""))
        if not isinstance(held, dict) or not hmac.compare_digest(sent, str(held.get("state", ""))):
            return access.refusal(400, "The pick did not come back as it was sent: start it again from the button.")
        try:
            row = drive_pick.take_state(d.root(), sent, by=account.name)
        except drive_pick.PickRefused as exc:
            return access.refusal(400, str(exc))
        purpose, slot, to = str(row.get("purpose", "split")), str(row.get("slot", "")), str(row.get("next", ""))

        def done(report: Any = None, error: str = ""):
            token = drive_pick.save_result(d.root(), by=account.name, purpose=purpose, slot=slot, report=report, error=error)
            return redirect("/?" + urlencode({"pick": token}) + to)

        try:
            limits.check("pick.enabled", True, community=community, record=False)
        except limits.LimitReached as exc:
            return done(error=str(exc))
        if request.args.get("error"):
            return done(error="Nothing was picked: Google's Picker was closed or the permission was not given.")
        ids = [i for i in str(request.args.get("picked_file_ids", "")).split(",") if i.strip()]
        code = str(request.args.get("code", ""))
        if not ids or not code:
            return done(error="Nothing was picked.")
        token = ""
        client_drive = None
        try:
            client = _client(account)
            with _quiet_requests():
                token = d.exchange(client, code, request.host_url.rstrip("/") + CALLBACK)
                client_drive = d.drive(token)
                report = drive_pick.pick(ids, by=account.name, drive=client_drive, root=d.root(),
                                         purpose=drive_pick.Purpose(purpose), slot=slot, community=community)
        except (Refused, drive_pick.PickRefused) as exc:
            return done(error=str(exc))
        except Exception as exc:  # noqa: BLE001 - said by kind, never with Google's text (it can hold a file id)
            log.warning("drive-pick failed: %s", type(exc).__name__)
            return done(error=f"The pick could not be finished ({type(exc).__name__}). Nothing was kept.")
        finally:
            token = ""                                   # the one-time token is dropped here; it was never stored
            closer = getattr(client_drive, "close", None)
            if callable(closer):
                closer()
        return done(report)

    @bp.post(RESULT)
    def pick_result():
        """What a pick came to, read once: ``{purpose, slot, error, report: {counts, rows: [{outcome, reason, words, heldId, size,
        pages, name}]}}``. The result is removed as it is read and is for the person who picked."""
        from jason.tasks import drive_pick
        from jason.web import access

        try:
            account = _who()
        except _Stop as stop:
            return stop.response
        body = request.get_json(silent=True) or {}
        found = drive_pick.take_result(deps().root(), str(body.get("token") or ""), by=account.name)
        if found is None:
            resp = jsonify(error="No such result (it is read once, and it expires). Choose from Drive again.")
            resp.status_code = 404
            resp.headers["Cache-Control"] = "no-store"
            return resp
        resp = jsonify(found)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return bp


__all__ = ["AUTH_URL", "CALLBACK", "KEY", "PickDeps", "RESULT", "SCOPE", "START", "TOKEN_URL", "blueprint", "default_exchange",
           "install"]
