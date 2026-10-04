"""Who may open a file or a document from the console, decided on the server (docs/console/security-and-privacy.md,
Roles and Data levels).

The person's decision: opening documents and files from the console needs a signed-in roster person
(``jason.web.signin``), and what they may open is their offices' data levels. Hiding a button is not a check; this is.

- **Levels.** ``Level`` P0 (the association's documents and the law), P1 (members' names and units), P2 (contact
  details and members' submissions: documents shown unmasked, a request's files, form responses, mail scans), P3
  (restricted: executive session, legal case files, private facts, confidential library files), P4 (secrets: never
  served).
- **Who sees what** is ``SEE_RULES``, one row an office: the levels it opens, and the levels it opens only in the
  private view, for a stated reason. Anyone on the roster opens P0 and P1. A person holding several offices gets the
  union of their rows. An admin with no office or manager role holds only the roster row. An admin viewing the
  console as someone (``jason-web --dev``) is judged as that someone, and the log names both.
- **What a path is** is ``PATH_RULES``, matched in order by its place under data/ and by the stores' own flags (the
  library's ``confidential``, the Zoom index's ``confidential`` or kind, the Drive holdings' ``confidential``; a Drive
  file's copy by ``jason.tasks.drive_copies.level_of``).
  Anything no row places is P2: closed, never open.
- **``require``** answers a route: the ``Viewer``, or a 401 (no one signed in, or sign-in not set up on this
  jason-web) or a 403 with the reason. A fetch gets JSON with ``signIn``; a top-level navigation gets a small page.
- **The private view** is a window a signed-in person opens for themselves (``POST /api/private`` with ``{reason,
  minutes}``), for 15, 30, or 60 minutes, when one of their offices opens P3 in the private view. It is kept in the
  Flask session, bound to the account's Google ``sub``, so another sign-in in the same browser never inherits it. It
  closes on ``DELETE /api/private``, on sign-out, and when its time is up (the next request finds it expired). While
  an admin views the console as someone else it is not open. ``private_window`` is the one place a route asks.
  Each opening, closing, and expiry is a line in ``data/access/private.jsonl``: ``{at, event, id, by, reason,
  minutes?}``.
- **The log** is ``data/access/served.jsonl``: one line a file served or a document viewed unmasked, ``{at, by, as?,
  path | address, level, private, privateId?, reason?}``; a line served while the private view is open carries its id
  and its reason. Never the contents. It is written before the bytes go out; a log that cannot be written serves
  nothing.
"""

from __future__ import annotations

import fnmatch
import hmac
import html
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from flask import Flask, Response, abort, current_app, has_request_context, jsonify, make_response, request, session

SERVED_LOG = Path("access") / "served.jsonl"
PRIVATE_LOG = Path("access") / "private.jsonl"
PRIVATE_ROUTE = "/api/private"
PRIVATE_KEY = "private"                     # the Flask session's key for the open window
PRIVATE_MINUTES = (15, 30, 60)
PRIVATE_DEFAULT = 30
ROSTER = "anyone on the roster"
SIGN_IN = "Sign in with Google to open this."
NOT_SET_UP = "Console sign-in isn't set up on this jason-web; see docs/setup.md, Console sign-in."
REASON_CHARS = 120
PRIVATE_HINT = "Open the private view (at the top of the console) for a stated reason."


class Level(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


WORDS = {
    Level.P0: "the association's documents (P0)",
    Level.P1: "members' names and units (P1)",
    Level.P2: "contact details and members' submissions (P2)",
    Level.P3: "executive-session and other restricted material (P3)",
    Level.P4: "secrets (P4)",
}


# --- who sees what ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SeeRule:
    """One office's data levels: those it opens, and those it opens only in the private view for a stated reason.
    ``holder`` is an ``OfficerRole`` value, or ``ROSTER`` for anyone on the roster."""

    holder: str
    open: frozenset[Level]
    private: frozenset[Level] = frozenset()


def _levels(*levels: Level) -> frozenset[Level]:
    return frozenset(levels)


SEE_RULES: tuple[SeeRule, ...] = (
    SeeRule(ROSTER, _levels(Level.P0, Level.P1)),
    SeeRule("manager", _levels(Level.P2), _levels(Level.P3)),
    SeeRule("president", _levels(Level.P2), _levels(Level.P3)),
    SeeRule("vice president", _levels(Level.P2), _levels(Level.P3)),
    SeeRule("director", _levels(Level.P2), _levels(Level.P3)),
    SeeRule("secretary", _levels(Level.P2), _levels(Level.P3)),
    SeeRule("treasurer", _levels(Level.P2)),
)


@dataclass(frozen=True)
class Viewer:
    """Whose view a request is judged as: the signed-in person, or the person (or office alone) an admin views the
    console as. ``account`` is who actually signed in, the log's ``by``; ``bind`` ties a document link to that sign-in."""

    name: str
    offices: frozenset[str]
    admin: bool = False
    account: str = ""
    bind: str = ""
    acting: bool = False

    @property
    def manager(self) -> bool:
        return "manager" in self.offices

    @property
    def label(self) -> str:
        return self.name or "the " + ", ".join(sorted(self.offices))


def _offices(role: str) -> frozenset[str]:
    from jason.community.base import OfficerRole

    known = {r.value for r in OfficerRole}
    return frozenset(r.strip() for r in str(role or "").split(",") if r.strip() in known)


def _office_words(offices: frozenset[str]) -> str:
    names = sorted(offices)
    if len(names) == 1:
        return f"The {names[0]}'s office doesn't"
    return f"The {', '.join(names[:-1])} and {names[-1]}'s offices don't"


def may_see(viewer: Viewer, level: Level, *, private: bool = False) -> tuple[bool, str]:
    """Whether ``viewer`` may open ``level``, by ``SEE_RULES``; ``private`` is the private view, open for a stated
    reason. The reason a refusal gives is a sentence a person can act on."""
    if level is Level.P4:
        return False, "Secrets (P4) are never served."
    holders = {ROSTER} | set(viewer.offices)
    rows = [r for r in SEE_RULES if r.holder in holders]
    if any(level in r.open for r in rows):
        return True, ""
    if any(level in r.private for r in rows):
        if private:
            return True, ""
        return False, f"{WORDS[level][0].upper()}{WORDS[level][1:]} opens only in the private view. {PRIVATE_HINT}"
    if not viewer.offices:
        who = "An admin with no office or manager role doesn't" if viewer.admin else "Someone with no office doesn't"
        return False, f"{who} open {WORDS[level]}."
    return False, f"{_office_words(viewer.offices)} open {WORDS[level]}."


# --- what a path is -----------------------------------------------------------------------------------------------------

Ask = Callable[[str, Path], "Level | None"]


@dataclass(frozen=True)
class PathRule:
    """One place under data/ (``pattern``, an fnmatch pattern on the posix path, lower case) and its level. ``ask``
    reads the store's own flag for the path: the level it says, or None for ``level`` (None: on to the next row)."""

    pattern: str
    level: Level | None
    ask: Ask | None = None


def _read_only(db: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)


def _library_flag(root: Path, where: str, value: str) -> Level | None:
    """P3 when library.db holds the file (by ``path`` or ``id``), or any copy of it (same sha256), as confidential;
    P0 when it holds it otherwise; None when it does not hold it; P2 when the store cannot be read."""
    db = root / "library" / "library.db"
    if not db.is_file():
        return None
    try:
        conn = _read_only(db)
        try:
            row = conn.execute(f"SELECT sha256, confidential FROM documents WHERE {where} = ? LIMIT 1",
                               (value,)).fetchone()
            if row is None:
                return None
            flagged = bool(row[1])
            if not flagged and row[0]:
                flagged = bool(conn.execute("SELECT MAX(confidential) FROM documents WHERE sha256 = ?",
                                            (row[0],)).fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return Level.P2
    return Level.P3 if flagged else Level.P0


def _library_file(rel: str, root: Path) -> Level | None:
    return _library_flag(root, "path", rel.split("/", 2)[2])


def _library_text(rel: str, root: Path) -> Level | None:
    return _library_flag(root, "id", Path(rel).name.split(".", 1)[0])


def _payhoa_document(rel: str, root: Path) -> Level | None:
    found = _library_flag(root, "path", rel.split("/", 2)[2])
    return Level.P3 if found is Level.P3 else (Level.P2 if found is Level.P2 else None)


def _zoom_meeting(rel: str, root: Path) -> Level | None:
    """P3 for a meeting the Zoom index marks confidential or whose kind is an executive session or a hearing; P1 for
    another meeting it lists; None (P2) for a folder it does not list."""
    parts = rel.split("/")
    if len(parts) < 3:
        return None
    try:
        from jason.tasks.zoom import load_index

        index = load_index(root)
    except (OSError, ValueError):
        return Level.P2
    folder = "/".join(parts[1:3])
    for row in (index.get("meetings") or []) if isinstance(index, dict) else []:
        if isinstance(row, dict) and str(row.get("folder") or "") == folder:
            kind = str(row.get("kind") or "").lower()
            return Level.P3 if row.get("confidential") or kind in ("executive session", "hearing") else Level.P1
    return None


_PLACES: dict[str, tuple[tuple[int, int], frozenset[str]]] = {}


def _confidential_places(report: Path) -> frozenset[str]:
    """The paths under data/ where the Drive holdings place a confidential Drive file, read once a version of the
    report (it is large)."""
    try:
        stat = report.stat()
    except OSError:
        return frozenset()
    stamp = (stat.st_mtime_ns, stat.st_size)
    cached = _PLACES.get(str(report))
    if cached is not None and cached[0] == stamp:
        return cached[1]
    try:
        rows = json.loads(report.read_text(encoding="utf-8")).get("rows") or []
    except (OSError, ValueError, AttributeError):
        rows = []
    places: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not row.get("confidential"):
            continue
        for place in row.get("elsewhere") or ():
            where = str(place.get("where") or "").replace("\\", "/") if isinstance(place, dict) else ""
            if not where:
                continue
            if place.get("channel") == "PayHOA library":
                places.update({f"library/files/{where}", f"payhoa-files/documents/{where}"})
            else:
                places.add(where)
    found = frozenset(places)
    _PLACES[str(report)] = (stamp, found)
    return found


def _holdings(rel: str, root: Path) -> Level | None:
    """P3 for a path the Drive holdings (``drive/holdings.json``) place a confidential Drive file at."""
    report = root / "drive" / "holdings.json"
    if not report.is_file():
        return None
    return Level.P3 if rel in _confidential_places(report) else None


def _drive_copy(rel: str, root: Path) -> Level | None:
    """A Drive file's copy (``drive/copies/<id>.*``, ``jason.tasks.drive_copies``) at its file's level: P3 when the
    holdings mark it confidential, P0 for a letter template or a file under a Drive root's path rule, else P2."""
    from jason.tasks.drive_copies import level_of, valid_id

    file_id = Path(rel).name.split(".", 1)[0]
    if not valid_id(file_id):
        return None
    try:
        return Level(level_of(root, file_id))
    except (OSError, ValueError):
        return Level.P2


PATH_RULES: tuple[PathRule, ...] = (
    PathRule("*", None, _holdings),
    PathRule("drive/copies/*", Level.P2, _drive_copy),
    PathRule("spec/*", Level.P3),
    PathRule("cases/*", Level.P3),
    PathRule("legal/*", Level.P3),
    PathRule("access/*", Level.P3),
    PathRule("library/files/*", Level.P2, _library_file),
    PathRule("library/text/*", Level.P2, _library_text),
    PathRule("zoom/meetings/*", Level.P2, _zoom_meeting),
    PathRule("payhoa-files/requests/*", Level.P2),
    PathRule("payhoa-requests-images/*", Level.P2),
    PathRule("forms/*/responses.json", Level.P2),
    PathRule("gmail/files/*", Level.P2),
    PathRule("mail/*", Level.P2),
    PathRule("mailroom/*", Level.P2),
    PathRule("photos/*", Level.P1),
    PathRule("drafts/*", Level.P1),
    PathRule("board/minutes*", Level.P1),
    PathRule("authorities/*", Level.P0),
    PathRule("reader/*", Level.P0),
    PathRule("artifacts/site-docs/*", Level.P0),
    PathRule("governing/*", Level.P0),
    PathRule("payhoa-files/documents/*", Level.P0, _payhoa_document),
)
UNPLACED = Level.P2


def level_of_path(rel_path: str, data_dir: Path) -> Level:
    """The level of a file under ``data_dir`` by ``PATH_RULES``, first match; P2 for a path no row places; P4 for one
    outside ``data_dir`` (never served)."""
    root = Path(data_dir).resolve()
    try:
        rel = (root / str(rel_path or "")).resolve().relative_to(root).as_posix()
    except ValueError:
        return Level.P4
    key = rel.lower()
    for rule in PATH_RULES:
        if not fnmatch.fnmatchcase(key, rule.pattern):
            continue
        said = rule.ask(rel, root) if rule.ask else None
        if said is not None:
            return said
        if rule.level is not None:
            return rule.level
    return UNPLACED


# --- the request's viewer, and the answers that refuse -----------------------------------------------------------------

def _navigation() -> bool:
    """A top-level page load (or a frame's), not a fetch: ``Sec-Fetch-Mode: navigate``, or ``Accept`` preferring HTML."""
    if request.headers.get("Sec-Fetch-Mode", "").lower() == "navigate":
        return True
    return request.accept_mimetypes.best_match(["application/json", "text/html"]) == "text/html" and \
        request.accept_mimetypes["text/html"] > request.accept_mimetypes["application/json"]


def _page(status: int, sentence: str, *, sign_in: bool) -> Response:
    from jason.web.signin import START

    link = (f'<p><a href="{html.escape(START)}" target="_top">Sign in with Google</a></p>' if sign_in else "")
    body = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"<title>{'Sign in to open this' if sign_in else 'Not opened'}</title><style>"
            ":root{color-scheme:light dark}body{margin:0;padding:2rem 1rem;font:16px/1.5 system-ui,sans-serif;"
            "background:#fff;color:#1b1b1b}main{max-width:34rem;margin:0 auto}a{color:#0b57d0}"
            "@media (prefers-color-scheme: dark){body{background:#161616;color:#ececec}a{color:#8ab4f8}}"
            f"</style></head><body><main><p>{html.escape(sentence)}</p>{link}</main></body></html>")
    resp = make_response(body, status)
    resp.mimetype = "text/html"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return resp


def refusal(status: int, sentence: str) -> Response:
    """A 401 or 403 in the shape the request can show: a small page for a navigation, else JSON (``signIn`` on 401)."""
    from jason.web.signin import START

    if _navigation():
        return _page(status, sentence, sign_in=status == 401)
    body: dict[str, Any] = {"error": sentence}
    if status == 401:
        body["signIn"] = START
    resp = jsonify(body)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _viewer() -> tuple[Viewer | None, Response | None]:
    """The request's viewer, or the 401 that says why there is none."""
    from jason.web.signin import acting_as, current_account

    sign_in = current_app.extensions.get("jason_sign_in")
    if sign_in is None or not sign_in.configured:
        return None, refusal(401, NOT_SET_UP)
    account = current_account()
    if account is None:
        return None, refusal(401, SIGN_IN)
    try:
        roster = tuple(sign_in.roster())
    except Exception:  # noqa: BLE001 - a roster that cannot be read opens nothing
        return None, refusal(401, "The roster could not be read, so nothing opens: " + SIGN_IN)
    me = next((p for p in roster if p.name == account.name), None)
    if me is None:
        session.clear()
        return None, refusal(401, f"{account.name} is no longer on the roster: signed out. {SIGN_IN}")
    bind = account.sub or f"{account.name}|{account.email}"
    acting = acting_as() if (getattr(sign_in, "dev", False) and (account.admin or me.admin)) else None
    if acting is not None:
        other = next((p for p in roster if acting.name and p.name == acting.name), None)
        if other is not None:
            return Viewer(other.name, _offices(other.role), other.admin, account.name, bind, True), None
        return Viewer("", _offices(acting.role), False, account.name, bind, True), None
    return Viewer(me.name, _offices(me.role), me.admin or account.admin, account.name, bind), None


def clean_reason(reason: str) -> str:
    """A stated reason as it is logged: one line, short, contact details masked; empty when it looks like a secret."""
    from jason.community.intake import secret_reason
    from jason.web.approvals import mask

    text = " ".join(str(reason or "").split())[:REASON_CHARS]
    if not text or secret_reason(text):
        return ""
    return str(mask(text))


# --- the private view ---------------------------------------------------------------------------------------------------

def now() -> datetime:
    """The clock the private view reads (a test fakes it)."""
    return datetime.now(timezone.utc)


def _stamp(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="seconds")


def _when(value: Any) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def _log_private(event: str, window: dict[str, Any], **extra: Any) -> None:
    """One line in ``access/private.jsonl``. Raises ``OSError`` when it cannot be written."""
    row: dict[str, Any] = {"at": _stamp(now()), "event": event, "id": str(window.get("id") or ""),
                           "by": str(window.get("by") or ""), "reason": str(window.get("reason") or "")}
    row.update({k: v for k, v in extra.items() if v not in (None, "")})
    file = _data_root() / PRIVATE_LOG
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _quiet_log(event: str, window: dict[str, Any], **extra: Any) -> None:
    """A closing's line: a closing that cannot be logged still closes (it opens nothing)."""
    try:
        _log_private(event, window, **extra)
    except OSError:
        pass


def _account_bind() -> str:
    from jason.web.signin import current_account

    account = current_account()
    if account is None:
        return ""
    return account.sub or f"{account.name}|{account.email}"


def _acting() -> bool:
    """Whether an admin is viewing the console as someone else (``jason-web --dev``)."""
    from jason.web.signin import acting_as, current_account

    sign_in = current_app.extensions.get("jason_sign_in")
    account = current_account()
    return bool(getattr(sign_in, "dev", False) and account is not None and account.admin) and acting_as() is not None


def private_window() -> dict[str, Any] | None:
    """The private view open on this request: ``{id, by, sub, reason, opened, until}``, or None.

    None when no window is in the session; when the window belongs to another sign-in (it is dropped and logged
    ``closed``); when its time is up (dropped and logged ``expired``); and while an admin views the console as someone
    else (kept, but not open for that view)."""
    if not has_request_context():
        return None
    raw = session.get(PRIVATE_KEY)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        session.pop(PRIVATE_KEY, None)
        return None
    bind = _account_bind()
    if not bind or not hmac.compare_digest(str(raw.get("sub") or "").encode("utf-8"), bind.encode("utf-8")):
        session.pop(PRIVATE_KEY, None)
        _quiet_log("closed", raw, why="another sign-in")
        return None
    until = _when(raw.get("until"))
    if until is None or now() >= until:
        session.pop(PRIVATE_KEY, None)
        _quiet_log("expired", raw)
        return None
    if _acting():
        return None
    return dict(raw)


def close_private(why: str = "") -> bool:
    """Close the window in this session, whoever's it is, and log it ``closed`` (with ``why``: "signed out").
    True when one was open."""
    if not has_request_context():
        return False
    raw = session.pop(PRIVATE_KEY, None)
    if not isinstance(raw, dict):
        return False
    until = _when(raw.get("until"))
    _quiet_log("expired" if until is None or now() >= until else "closed", raw, why=why)
    return True


def private_open(viewer: Viewer | None = None) -> bool:
    """Whether the private view is open on this request and the viewer's offices open P3 in it."""
    if private_window() is None:
        return False
    if viewer is None:
        viewer, refused = _viewer()
        if refused is not None or viewer is None:
            return False
    return may_see(viewer, Level.P3, private=True)[0]


def _may_open() -> tuple[bool, str]:
    """Whether the person on this request may open the private view, and the sentence that says why not."""
    viewer, refused = _viewer()
    if refused is not None or viewer is None:
        got = refused.get_json(silent=True) if refused is not None else None
        said = str(got.get("error") or "") if isinstance(got, dict) else ""
        if said == NOT_SET_UP:
            return False, NOT_SET_UP
        return False, "Sign in with Google to open the private view."
    if viewer.acting:
        return False, (f"Viewing as {viewer.label} (admin view): the private view opens only as yourself. Go back to "
                       "yourself to open it.")
    return may_see(viewer, Level.P3, private=True)


def private_info() -> dict[str, Any]:
    """What ``GET /api/session`` says of the private view: ``{open, until, reason, id, mayOpen, why, minutes,
    default}``."""
    window = private_window()
    ok, why = _may_open()
    return {"open": window is not None, "until": str((window or {}).get("until") or ""),
            "reason": str((window or {}).get("reason") or ""), "id": str((window or {}).get("id") or ""),
            "mayOpen": ok, "why": "" if ok else why, "minutes": list(PRIVATE_MINUTES), "default": PRIVATE_DEFAULT}


def _minutes(value: Any) -> int:
    if value in (None, ""):
        return PRIVATE_DEFAULT
    if isinstance(value, bool):
        raise ValueError("minutes is 15, 30, or 60")
    try:
        minutes = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("minutes is 15, 30, or 60") from exc
    if minutes not in PRIVATE_MINUTES or str(value).strip() not in (str(minutes), f"{minutes}.0"):
        raise ValueError("minutes is 15, 30, or 60")
    return minutes


def _stated(reason: Any) -> str:
    """The reason as it is kept, or ``ValueError`` with the sentence that says what to change."""
    from jason.community.intake import secret_reason

    text = " ".join(str(reason or "").split())
    if not text:
        raise ValueError("Say why you open the private view: a short phrase, e.g. executive session prep. It's logged.")
    if len(text) > REASON_CHARS:
        raise ValueError(f"Keep the reason short: {REASON_CHARS} characters at most. It's a phrase, never an owner's "
                         "personal details.")
    secret = secret_reason(text)
    if secret:
        raise ValueError(f"That reason looks like a secret ({secret}): nothing was opened or kept. Say why in a short "
                         "phrase.")
    kept = clean_reason(text)
    if not kept:
        raise ValueError("Say why you open the private view in a short phrase.")
    return kept


# --- what a route asks -------------------------------------------------------------------------------------------------

def check(level: Level) -> tuple[Viewer | None, Response | None]:
    """The viewer when they may open ``level`` (P3 only while the private view is open), else the refusal."""
    viewer, refused = _viewer()
    if refused is not None:
        return None, refused
    assert viewer is not None
    ok, why = may_see(viewer, level, private=private_window() is not None)
    if not ok:
        return viewer, refusal(403, why)
    return viewer, None


def require(level: Level) -> Viewer:
    """For a route: the ``Viewer`` who may open ``level``, or abort with the 401 or 403 that says why."""
    viewer, refused = check(level)
    if refused is not None:
        abort(refused)
    assert viewer is not None
    return viewer


def signed_in() -> Viewer:
    """For a route: the request's ``Viewer`` (any level not yet judged), or abort with the 401."""
    viewer, refused = _viewer()
    if refused is not None:
        abort(refused)
    assert viewer is not None
    return viewer


def allow(viewer: Viewer, level: Level) -> None:
    """For a route that already has its viewer: abort with the 403 unless they may open ``level`` (P3 only while the
    private view is open)."""
    ok, why = may_see(viewer, level, private=private_window() is not None)
    if not ok:
        abort(refusal(403, why))


def _data_root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def served(viewer: Viewer, level: Level, *, path: str = "", address: str = "", data_dir: Path | None = None,
           **extra: Any) -> None:
    """One line in ``access/served.jsonl``: when, who signed in, whom they viewed as, what, its level, and, while the
    private view is open, its id and stated reason. Never the contents. Raises ``OSError`` when it cannot be written,
    so nothing is served unlogged."""
    root = Path(data_dir) if data_dir is not None else _data_root()
    window = private_window()
    row: dict[str, Any] = {"at": _stamp(now()), "by": viewer.account}
    if viewer.acting:
        row["as"] = viewer.label
    row.update({"path": path} if path else {"address": address})
    row.update({"level": level.value, "private": window is not None})
    if window is not None:
        row.update({"privateId": str(window.get("id") or ""), "reason": str(window.get("reason") or "")})
    row.update({k: v for k, v in extra.items() if v not in (None, "")})
    file = root / SERVED_LOG
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def log_or_refuse(viewer: Viewer, level: Level, **fields: Any) -> None:
    """``served``, or abort with a 503: a serve that cannot be logged does not happen."""
    try:
        served(viewer, level, **fields)
    except OSError:
        abort(make_response(jsonify(error="The access log (access/served.jsonl) could not be written, so nothing "
                                          "was opened."), 503))


# --- the listings that hold confidential rows back ----------------------------------------------------------------------

def _flag(value: str | None) -> bool:
    return str(value or "").lower() in ("1", "true", "yes")


HELD_BACK = "{n} held back (confidential); open the private view to see them."
PRIVATE_LISTINGS = ("library", "embeds")


def _no_store(resp: Response) -> Response:
    resp.headers["Cache-Control"] = "no-store"
    return resp


def install(app: Flask, loaders: dict[str, Callable[[dict[str, str]], dict[str, Any]]]) -> None:
    """The private view's routes (``POST`` and ``DELETE /api/private``), and the hold-back on the confidential rows of
    ``GET /api/library?confidential=1`` (and ``/api/embeds?confidential=1``) unless the private view is open for a
    viewer whose offices open P3 in it. The listing's own loader runs unchanged: without the window, it runs without
    the flag, and the answer says how many it held back."""
    from jason.web.guard import TOKEN_HEADER, header_token_ok

    @app.post(PRIVATE_ROUTE)
    def private_view_open():
        """Open the private view for the signed-in person: ``{reason, minutes}`` (15, 30, or 60; 30 when not given).
        401 signed out; 403 without the token in its header, while viewing as someone else, or for an office that
        does not open P3; 400 for no reason, a long one, one that looks like a secret, or other minutes; 503 when
        the log cannot be written (nothing opened)."""
        if not header_token_ok():
            return _no_store(refusal(403, f"Opening the private view carries this server's token in {TOKEN_HEADER}."))
        viewer = signed_in()
        if viewer.acting:
            return _no_store(refusal(403, f"Viewing as {viewer.label} (admin view): the private view opens only as "
                                          "yourself."))
        ok, why = may_see(viewer, Level.P3, private=True)
        if not ok:
            return _no_store(refusal(403, why))
        body = request.get_json(silent=True)
        body = body if isinstance(body, dict) else {}
        try:
            reason = _stated(body.get("reason"))
            minutes = _minutes(body.get("minutes"))
        except ValueError as exc:
            return _no_store(make_response(jsonify(error=str(exc)), 400))
        old = session.get(PRIVATE_KEY)
        if isinstance(old, dict):
            close_private("opened again")
        opened = now()
        window = {"id": secrets.token_hex(4), "by": viewer.account, "sub": viewer.bind, "reason": reason,
                  "opened": _stamp(opened), "until": _stamp(opened + timedelta(minutes=minutes))}
        try:
            _log_private("opened", window, minutes=minutes)
        except OSError:
            return _no_store(make_response(jsonify(error="The access log (access/private.jsonl) could not be "
                                                         "written, so the private view was not opened."), 503))
        session[PRIVATE_KEY] = window
        return _no_store(jsonify(private=private_info()))

    @app.delete(PRIVATE_ROUTE)
    def private_view_close():
        """Close the private view in this session (logged ``closed``). Answers the private view as ``/api/session``
        says it, open or not."""
        if not header_token_ok():
            return _no_store(refusal(403, f"Closing the private view carries this server's token in {TOKEN_HEADER}."))
        close_private()
        return _no_store(jsonify(private=private_info()))

    @app.before_request
    def _private_listing():
        if request.endpoint != "source" or not _flag(request.args.get("confidential")):
            return None
        name = str((request.view_args or {}).get("name") or "")
        load = loaders.get(name) if name in PRIVATE_LISTINGS else None
        if load is None:
            return None
        viewer, refused = check(Level.P3)
        if refused is None and viewer is not None:
            try:
                served(viewer, Level.P3, path=f"api/{name}?confidential=1")
            except OSError:
                return jsonify(error="The access log (access/served.jsonl) could not be written, so nothing was "
                                     "listed."), 503
            return None
        why = ""
        if refused is not None:
            got = refused.get_json(silent=True)
            why = str(got.get("error") or "") if isinstance(got, dict) else ""
        args = {k: v for k, v in request.args.to_dict().items() if k != "confidential"}
        try:
            out = load(args)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception as exc:  # noqa: BLE001 - a missing store is a miss to show, as the source route says it
            return jsonify(error=f"{type(exc).__name__}: {exc}"), 500
        if isinstance(out, dict):
            if name == "library":
                n = int(out.get("heldBackConfidential") or 0)
            else:
                said = [re.match(r"(\d+) confidential", str(note)) for note in out.get("notes") or []]
                n = sum(int(m.group(1)) for m in said if m)
            out = {**out, "heldBack": n, "heldBackWhy": why}
            if name == "library":
                out["note"] = HELD_BACK.format(n=n) if n else str(out.get("note") or "")
        return _no_store(jsonify(out))


__all__ = ["HELD_BACK", "Level", "NOT_SET_UP", "PATH_RULES", "PRIVATE_DEFAULT", "PRIVATE_LOG", "PRIVATE_MINUTES",
           "PRIVATE_ROUTE", "PathRule", "ROSTER", "SEE_RULES", "SERVED_LOG", "SIGN_IN", "SeeRule", "Viewer", "allow",
           "check", "clean_reason", "close_private", "install", "level_of_path", "log_or_refuse", "may_see", "now",
           "private_info", "private_open", "private_window", "refusal", "require", "served", "signed_in"]
