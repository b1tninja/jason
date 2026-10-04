"""The approvals engine (``jason.approvals``) through jason-web: the same functions the CLI calls, no logic of its own.

- **Reads.** ``GET /api/approvals`` is the ``approvals`` loader: the letters inbox it always served
  (``jason.web.extra.approvals``) with the engine's approvals beside it under ``approvals`` (``?status=``, ``?kind=``);
  ``?key=`` is still one letter. ``GET /api/approvals/<id>`` is the Approval JSON as the engine stores it
  (``approval.schema.json``); ``GET /api/approvals/audit`` the log (``?approval=``, ``?verify=1``);
  ``GET /api/evidence?address=&approval=`` one evidence address opened from disk (``jason.approvals.evidence``).
- **Check.** ``POST /api/approvals/<id>/check`` re-plans live and compares, writing nothing (``engine.check``, the
  CLI's ``apply ID`` without ``--yes``). A POST, not a GET: it signs in to PayHOA and reads it, which a link, a
  prefetch, or another site's ``<img>`` must never set off, so it sits behind the write guard and the token header.
- **Writes to jason's own store.** ``decide``, ``submit``, ``confirm``, ``decline``, ``withdraw``: each names its
  person (``by``) and returns the Approval; the engine's refusal comes back as 400 in its own words.
- **Refresh one piece of evidence.** ``POST /api/evidence/refresh`` with ``{address, approval?, by}`` reads that one
  record again live under the person's name and keeps it in jason's cache (``jason.approvals.evidence.refresh``);
  it never writes to PayHOA. Behind the write guard and the token header, like a check.
  ``POST /api/evidence/refresh-all`` with ``{approval, by}`` reads every refreshable record of one plan on one sign-in
  (``jason.approvals.evidence.refresh_all``) and answers what it read and what failed, never the answers.
- **View one document unmasked.** ``POST /api/evidence/view`` with ``{address, approval?, document, by}`` opens one of
  the documents an evidence answer lists (``jason.approvals.evidence_documents.view``): a person's ask to see it, so it
  is unmasked, logged in ``evidence/views.jsonl``, and behind the write guard and the token header. A submission or a
  text comes back whole; a pdf, an image, or another file as a link, ``GET /api/evidence/document/<token>``, that
  serves it from disk for ten minutes (``Grants``, in memory only), sandboxed, never sniffed, never cached.
- **Sign-in for the evidence's live reads and documents.** A refresh, a refresh-all, a view, and a view's link need a
  signed-in roster person whose offices open the level (``jason.web.access``: P2 for a request, P0 for a citation's
  documents, P3 for a confidential one, listed and opened only while the person's private view is open); the record names the signed-in account, never the body's ``by``. A view's link is bound to the sign-in
  that opened it, and each view is logged in ``access/served.jsonl`` too.
- **Apply, a write to PayHOA.** ``POST /api/approvals/<id>/apply`` with ``{by, confirm: <the fingerprint reviewed>}``.
  Off unless jason-web was started with ``--allow-apply``. The engine re-plans and refuses (409) when anything
  changed, superseding the approval with a new one to review.

Privacy: the store holds names and tags (P1). Anything that looks like an email address or a phone number (a reason a
person typed, a result's detail) is masked before it leaves the server.
"""

from __future__ import annotations

import re
import secrets
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, ContextManager, Iterator

from flask import Blueprint, jsonify, request

Args = dict[str, str]
LiveFactory = Callable[[Any], ContextManager[Any]]      # an ActionKind -> a context yielding an engine.Live

CAVEAT = ("An approval is decided, submitted, confirmed, and applied by a named person; jason never approves its own "
          "plan. Items held for the board, for a person, or to confirm with the owner are never approvable. A check "
          "reads PayHOA live and writes nothing; an apply re-reads and refuses when anything changed since review.")
APPLY_OFF = ("apply is off: jason-web was started without --allow-apply. A person applies from a terminal with "
             "`jason approvals apply ID --by NAME --yes`, or restarts jason-web with --allow-apply")
STEPS = ("submit", "confirm", "decline", "withdraw")

_PHONE = re.compile(r"(?<![\w-])(?:\+?1[-. ]?)?(?:\(\d{3}\)\s?|\d{3}[-. ])\d{3}[-. ]\d{4}(?![\w-])")


def mask(value: Any) -> Any:
    """``value`` with email addresses (``jason.approvals.audit.mask``) and phone numbers replaced."""
    from jason.approvals.audit import mask as mask_email

    def phones(v: Any) -> Any:
        if isinstance(v, str):
            return _PHONE.sub("[phone]", v)
        if isinstance(v, dict):
            return {k: phones(x) for k, x in v.items()}
        if isinstance(v, list):
            return [phones(x) for x in v]
        return v

    return phones(mask_email(value))


@contextmanager
def default_live(kind: Any) -> Iterator[Any]:
    """The live context a kind needs, as the CLI builds it: PayHOA signed in non-interactively (a missing Keeper
    session fails fast, ``KeeperAuthRequired``; ``jason login`` in a terminal fixes it)."""
    from jason.approvals.engine import Live
    from jason.config import data_dir

    if kind.system != "payhoa":
        yield Live(data_dir=data_dir())
        return
    from jason.agent import Jason

    with Jason(interactive=False) as agent:
        yield Live(agent.payhoa(), agent.org_id, data_dir(), None)


# --- reads --------------------------------------------------------------------------------------------------------------

def _row(a: Any) -> dict[str, Any]:
    from jason.approvals.engine import counts, needs_second

    try:
        second = needs_second(a)
    except KeyError:                                   # a kind this checkout no longer has
        second = None
    return {"id": a.id, "kind": a.kind, "title": a.title, "status": a.status.value, "fingerprint": a.fingerprint,
            "readAt": a.read_at, "requestedBy": a.requested_by, "requestedAt": a.requested_at,
            "requestedVia": a.requested_via, "approved": len(a.approved), "needsSecond": second,
            "first": a.first.name if a.first else "", "second": a.second.name if a.second else "",
            "clock": a.clock, "supersedes": a.supersedes, "supersededBy": a.superseded_by, **counts(a)}


def plans(args: Args) -> dict[str, Any]:
    """The engine's approvals, open ones first; ``status`` and ``kind`` filter."""
    from jason.approvals import store
    from jason.approvals.model import OPEN, ApprovalStatus

    status, kind = args.get("status", "").strip(), args.get("kind", "").strip()
    statuses = [s.value for s in ApprovalStatus]
    if status and status not in statuses:
        raise ValueError(f"status is one of {', '.join(statuses)}")
    every = store.load_all()
    rows = [a for a in every if (not status or a.status.value == status) and (not kind or a.kind == kind)]
    rows.sort(key=lambda a: (a.status not in OPEN, a.requested_at))
    return {"approvals": mask([_row(a) for a in rows]), "approvalsOpen": sum(1 for a in every if a.status in OPEN),
            "approvalStatuses": statuses, "approvalsCaveat": CAVEAT}


def approvals(args: Args) -> dict[str, Any]:
    """The ``approvals`` source: the letters inbox as before, with the engine's approvals beside it. ``key`` is one
    letter, unchanged. A letters store that cannot be read is said (``lettersError``) and the approvals still show."""
    from jason.web.extra import approvals as letters

    if args.get("key", "").strip():
        return letters.approvals(args)
    out: dict[str, Any] = {}
    try:
        out.update(letters.approvals(args))
    except Exception as exc:  # noqa: BLE001 - the letters are one half of the page
        out["lettersError"] = f"{type(exc).__name__}: {exc}"
    out.update(plans(args))
    return out


def show(ident: str) -> dict[str, Any]:
    from jason.approvals import store
    from jason.approvals.model import to_dict

    return mask(to_dict(store.load(ident)))


def audit_log(args: Args) -> dict[str, Any]:
    from jason.approvals import audit, store

    ident = args.get("approval", "").strip()
    if ident:
        ident = store.resolve(ident)
    entries = audit.read(None, ident)
    out: dict[str, Any] = {"entries": mask(entries), "count": len(entries)}
    if args.get("verify", "").lower() in ("1", "true", "yes", "on"):
        ok, line, why = audit.verify()
        out["verify"] = {"whole": ok, "line": line, "why": why}
    return out


def evidence(args: Args) -> dict[str, Any]:
    """``GET /api/evidence?address=...&approval=...``: what jason holds on disk of an evidence address, with the
    commands that read it again. Nothing is read live; contact details are masked by the resolver and again here.
    While the person's private view is open (``jason.web.access.private_open``), restricted and confidential material
    comes back too: a restricted book's words, confidential documents (marked P3), an executive item's notes."""
    from jason.approvals.evidence import resolve
    from jason.web.access import private_open

    return _masked_evidence(resolve(args.get("address", ""), approval_id=args.get("approval", "").strip(),
                                    private=private_open()))


def _masked_evidence(out: dict[str, Any]) -> dict[str, Any]:
    """An evidence answer masked on its way out, but a citation's recited words, quoted as stored."""
    texts = [s.get("text", "") for s in out["sources"]]
    out = mask(out)
    for s, text in zip(out["sources"], texts):
        s["text"] = text
    return out


# What a refresh's live context is built for: ``default_live`` (and a test's factory) read ``system`` and ``key``.
EVIDENCE_REFRESH = SimpleNamespace(key="evidence-refresh", system="payhoa")


def refresh_evidence(body: dict[str, Any], by: str, live: LiveFactory) -> dict[str, Any]:
    """``POST /api/evidence/refresh``: one record read again live for ``by`` and kept in jason's cache
    (``jason.approvals.evidence.refresh``), then opened as ``GET /api/evidence`` opens it, masked."""
    from jason.approvals.evidence import refresh

    out = refresh(_text(body, "address"), by=by, approval_id=_text(body, "approval").strip(),
                  client_factory=lambda: live(EVIDENCE_REFRESH))
    return _masked_evidence(out)


def refresh_all_evidence(body: dict[str, Any], by: str, live: LiveFactory) -> dict[str, Any]:
    """``POST /api/evidence/refresh-all``: every refreshable evidence address of one approval read again live for
    ``by`` on one sign-in (``jason.approvals.evidence.refresh_all``). The summary only, masked; the page refetches
    what it has open."""
    from jason.approvals.evidence import refresh_all

    return mask(refresh_all(_text(body, "approval").strip(), by=by, client_factory=lambda: live(EVIDENCE_REFRESH)))


VIEW_TTL = timedelta(minutes=10)
# A served document runs nothing and loads nothing but itself: no script, no frame, no form, no request elsewhere.
# One policy for every kind, PDFs included: Chromium's PDF viewer renders a PDF served with it inside an iframe
# (checked against the variants without sandbox, with allow-scripts, and with allow-same-origin: all render, so the
# strictest stays).
DOCUMENT_CSP = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"


@dataclass(frozen=True)
class Grant:
    """One opened document a link serves: the file, the folder it must stay inside, its kind and name, who opened
    it, for which address, and until when."""
    address: str
    path: Path
    root: Path
    kind: str
    name: str
    by: str
    expires: datetime
    bind: str = ""              # the sign-in it was opened under (``access.Viewer.bind``); another sign-in gets 403
    level: str = "P2"           # the document's data level (``access.Level``), judged again on each read


class Grants:
    """The short-lived links ``POST /api/evidence/view`` makes, in memory only (a restart forgets them): a random token
    (``secrets.token_urlsafe(24)``) to one opened document, good for ``ttl``. Many reads are allowed meanwhile, since
    a PDF viewer asks for ranges."""

    def __init__(self, ttl: timedelta = VIEW_TTL) -> None:
        self.ttl = ttl
        self.now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
        self._rows: dict[str, Grant] = {}
        self._lock = threading.Lock()

    def mint(self, *, address: str, path: Path, root: Path, kind: str, name: str, by: str, bind: str = "",
             level: str = "P2") -> tuple[str, Grant]:
        token = secrets.token_urlsafe(24)
        grant = Grant(address, path, root, kind, name, by, self.now() + self.ttl, bind, level)
        with self._lock:
            self._purge()
            self._rows[token] = grant
        return token, grant

    def get(self, token: str) -> Grant | None:
        with self._lock:
            self._purge()
            return self._rows.get(str(token or ""))

    def _purge(self) -> None:
        now = self.now()
        for token in [t for t, g in self._rows.items() if g.expires <= now]:
            del self._rows[token]


def disposition(how: str, name: str) -> str:
    """``inline`` or ``attachment`` with the file's name: an ASCII ``filename`` (quotes, backslashes, and control
    characters replaced) and, for any other name, ``filename*`` in UTF-8 (RFC 6266)."""
    from urllib.parse import quote

    plain = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in name).strip() or "document"
    value = f'{how}; filename="{plain}"'
    return value if plain == name else value + f"; filename*=UTF-8''{quote(name, safe='')}"


def evidence_level(address: str) -> Any:
    """The data level of the documents behind an evidence address (``jason.web.access.Level``): a citation's documents
    are the association's and the law (P0; a confidential one is listed only in the private view, and its own answer
    says P3); a PayHOA request's submission and files, and anything else, P2."""
    from jason.approvals.evidence import EvidenceKind, rule_for
    from jason.web.access import Level

    try:
        rule, _ = rule_for(" ".join(str(address or "").split()))
    except Exception:  # noqa: BLE001 - an address no rule reads is judged closed
        return Level.P2
    return Level.P0 if rule.kind is EvidenceKind.CITATION else Level.P2


def view_evidence(body: dict[str, Any], by: str, grants: Grants, *, bind: str = "", level: str = "P2",
                  private: bool = False) -> dict[str, Any]:
    """``POST /api/evidence/view``: one document behind an evidence address opened unmasked for ``by`` and logged
    (``jason.approvals.evidence_documents.view``). Never masked here: the person asked to see it. A pdf, an image, or
    another file comes back as a link that serves it for ten minutes, to the sign-in ``bind`` only. ``private`` (the
    person's private view, open) opens a confidential document too; its answer and its link are P3."""
    from jason.approvals.evidence_documents import CONFIDENTIAL, view

    if not isinstance(body.get("document"), str) or not body["document"].strip():
        raise ValueError("name the document to open (document): an id the evidence lists")
    opened = view(_text(body, "address"), body["document"], by=by, approval_id=_text(body, "approval").strip(),
                  private=private)
    out = {"kind": "", "name": "", "readAt": "", "url": "", "expires": "", **opened.answer}
    if out.get("level") == CONFIDENTIAL:
        level = CONFIDENTIAL
    if opened.path is not None and opened.root is not None:
        token, grant = grants.mint(address=_text(body, "address"), path=opened.path, root=opened.root,
                                   kind=out["kind"], name=out["name"], by=by, bind=bind, level=level)
        out["url"] = f"/api/evidence/document/{token}"
        out["expires"] = grant.expires.isoformat(timespec="seconds")
    return out


def _item(i: Any) -> dict[str, Any]:
    return {"id": i.id, "op": i.op, "target": i.target, "label": i.label, "value": i.value,
            "change": i.change.text() if i.change else ""}


def _check_dict(r: Any) -> dict[str, Any]:
    from dataclasses import asdict

    a = r.approval
    return mask({"approval": a.id, "status": a.status.value, "fingerprint": a.fingerprint, "ok": r.ok,
                 "readLive": r.planned is not None, "problems": list(r.problems),
                 "unchanged": r.planned is not None and not r.changed, "then": r.then, "now": r.now,
                 "changed": [asdict(c) for c in r.changed], "new": [_item(i) for i in r.new],
                 "wouldApply": [_item(i) for i in a.approved] if r.ok else [],
                 "note": "read live just now; nothing written"})


# --- the routes ---------------------------------------------------------------------------------------------------------

def _body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _who(body: dict[str, Any]) -> tuple[str, str, str]:
    """Who takes a step, their role, and ``via``: the signed-in officer (``console:google``) when someone signed in
    with Google, else the name the page sent (``console``)."""
    from jason.web.signin import VIA, current_account

    a = current_account()
    if a is not None:
        return a.name, a.role or "manager", VIA
    return _text(body, "by"), _text(body, "role").strip()[:40] or "manager", "console"


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    return "" if value is None else str(value)


def _answer(fn: Callable[[], Any]):
    """The loader pattern: a value is 200; a missing approval 404; a refusal 400 in the engine's words; a lock held
    elsewhere 409; a live session that needs a person (``jason login``) 503; anything else 500."""
    from jason.locks import ResourceBusy

    try:
        out = fn()
        return out if isinstance(out, tuple) else jsonify(out)    # a tuple is a finished (response, status)
    except KeyError as exc:
        return jsonify(error=str(exc.args[0]) if exc.args else "not found"), 404
    except ValueError as exc:                          # engine.Refused, TransitionError, a bad body
        return jsonify(error=str(exc)), 400
    except ResourceBusy as exc:
        return jsonify(error=f"busy: {exc}"), 409
    except Exception as exc:  # noqa: BLE001 - said, not a crash
        if type(exc).__name__.endswith("AuthRequired"):
            return jsonify(error=f"{exc}: run `jason login` in a terminal; jason-web never asks for a credential"), 503
        return jsonify(error=f"{type(exc).__name__}: {exc}"), 500


def blueprint(*, live: LiveFactory | None = default_live, allow_apply: bool = False,
              writes: bool = True) -> Blueprint:
    """The approvals routes. ``live`` builds the live context for a check or an apply (None turns both off);
    ``allow_apply`` turns the apply on; ``writes`` False turns off the store writes."""
    from jason.web.guard import TOKEN_HEADER, header_token_ok

    bp = Blueprint("approvals", __name__)

    @bp.get("/api/approvals/audit")
    def audit_route():
        return _answer(lambda: audit_log(request.args.to_dict()))

    @bp.get("/api/approvals/<ident>")
    def show_route(ident: str):
        return _answer(lambda: show(ident))

    @bp.get("/api/evidence")
    def evidence_route():
        """An evidence address opened from disk (``jason.approvals.evidence.resolve``): ``?address=`` and, optionally,
        ``?approval=`` for the plan's own read. Reads only; a miss is 200 with ``found: false``."""
        return _answer(lambda: evidence(request.args.to_dict()))

    def _refresh_route(answer: Callable[[dict[str, Any], str, LiveFactory], dict[str, Any]]):
        """A refresh's guard, then ``answer(body, by, live)``: off (405) without a live context or writes; 403 without
        the token in its header; ``RefreshFailed`` 409 in its own words."""
        if live is None:
            return jsonify(error="live reads are off in this jason-web"), 405
        if not writes:
            return jsonify(error="writes are off"), 405
        if not header_token_ok():
            return jsonify(error=f"a refresh carries this server's token in {TOKEN_HEADER}"), 403
        from jason.web.access import Level, require

        viewer = require(Level.P2)               # a signed-in person whose offices open P2; never the body's name
        body = _body()

        def run():
            from jason.approvals.evidence import RefreshFailed

            try:
                return answer(body, viewer.account, live)
            except RefreshFailed as exc:
                return jsonify(error=mask(str(exc))), 409
        return _answer(run)

    @bp.post("/api/evidence/refresh")
    def evidence_refresh_route():
        """One record read again live for the person (``{address, approval?, by}``), kept in jason's own cache and
        logged; never a write to PayHOA. 200 with the fresh answer; 400 for a kind with no refresher or no person;
        409 when Keeper or PayHOA did not answer (or the cache is busy)."""
        return _refresh_route(refresh_evidence)

    @bp.post("/api/evidence/refresh-all")
    def evidence_refresh_all_route():
        """Every refreshable evidence address of one approval read again live for the person (``{approval, by}``) on
        one sign-in, each kept and logged; never a write to PayHOA. 200 with ``{approval, by, at, refreshed, failed,
        skipped}`` (no answers); 400 for no person, no such approval, or too many addresses; 409 when Keeper did not
        answer or the cache is busy."""
        return _refresh_route(refresh_all_evidence)

    grants = Grants()
    bp.record_once(lambda state: state.app.extensions.setdefault("jason_evidence_grants", grants))

    @bp.post("/api/evidence/view")
    def evidence_view_route():
        """One document behind an evidence address opened unmasked for the person (``{address, approval?, document,
        by}``) and logged in ``evidence/views.jsonl``; reads disk only. Off (405) without writes; 403 without the token
        in its header (and while an admin views as someone else); 400 for no person or a bad request; 404 for a
        document the address does not list or a file no longer on disk."""
        if not writes:
            return jsonify(error="writes are off"), 405
        if not header_token_ok():
            return jsonify(error=f"a view carries this server's token in {TOKEN_HEADER}"), 403
        from jason.web.access import Level, private_open, require, served

        body = _body()
        level = evidence_level(_text(body, "address"))
        viewer = require(level)                  # signed in, and their offices open the level; the body's `by` is not
        private = private_open(viewer)           # a confidential document only while their private view is open

        def run():
            out = view_evidence(body, viewer.account, grants, bind=viewer.bind, level=level.value, private=private)
            shown = Level.P3 if out.get("level") == Level.P3.value else level
            try:
                served(viewer, shown, address=" ".join(_text(body, "address").split()),
                       document=str(body.get("document") or "").strip())
            except OSError:
                return jsonify(error="The access log (access/served.jsonl) could not be written, so nothing was "
                                     "opened."), 503
            return out
        return _answer(run)

    @bp.get("/api/evidence/document/<token>")
    def evidence_document_route(token: str):
        """The file a view opened, from disk, while its link lasts; many reads (a PDF viewer's ranges). Never a live
        read. Only to the sign-in that opened it (403 to another), and only while its level is still theirs. An
        unknown or expired link is 404; no one signed in, 401."""
        from flask import send_file

        from jason.approvals.evidence_documents import content_type, inside
        from jason.web.access import Level, allow, signed_in

        viewer = signed_in()
        grant = grants.get(token)
        if grant is None:
            return jsonify(error="no such document link, or it has expired: open the document again"), 404
        if not grant.bind or not secrets.compare_digest(grant.bind.encode("utf-8"), viewer.bind.encode("utf-8")):
            return jsonify(error="This link was opened under another sign-in: open the document again from its "
                                 "evidence panel."), 403
        allow(viewer, Level(grant.level) if grant.level in Level._value2member_map_ else Level.P2)
        if not inside(grant.path, grant.root):
            return jsonify(error=f"{grant.name} is no longer on disk"), 404
        inline = grant.kind in ("pdf", "image", "text")
        mime = content_type(grant.path.name) if inline else "application/octet-stream"
        resp = send_file(grant.path.resolve(), mimetype=mime, conditional=True, etag=True, max_age=0)
        resp.headers["Content-Disposition"] = disposition("inline" if inline else "attachment", grant.name)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Content-Security-Policy"] = DOCUMENT_CSP
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    @bp.get("/api/approvals/<ident>/check")
    @bp.get("/api/approvals/<ident>/apply")
    def not_a_get(ident: str):
        return jsonify(error="a POST: it reads PayHOA live, so a link or a prefetch never sets it off"), 405

    @bp.post("/api/approvals/<ident>/check")
    def check_route(ident: str):
        if live is None:
            return jsonify(error="live reads are off in this jason-web"), 405
        if not header_token_ok():
            return jsonify(error=f"a check carries this server's token in {TOKEN_HEADER}"), 403

        def run() -> dict[str, Any]:
            from jason.approvals import engine, registry, store
            from jason.approvals.model import OPEN

            a = store.load(ident)
            if a.status not in OPEN:                   # nothing to re-read: say so without signing in
                return _check_dict(engine.check(a.id, engine.Live()))
            with live(registry.get(a.kind)) as lv:
                return _check_dict(engine.check(a.id, lv))
        return _answer(run)

    @bp.post("/api/approvals/<ident>/decide")
    def decide_route(ident: str):
        if not writes:
            return jsonify(error="writes are off"), 405
        body = _body()

        def run() -> dict[str, Any]:
            from jason.approvals import engine
            from jason.approvals.model import Decision, to_dict

            items = body.get("items")
            if items != "all" and not (isinstance(items, list) and items and all(isinstance(i, str) for i in items)):
                raise ValueError('items is a list of item ids (or unique prefixes), or "all"')
            choices = [d.value for d in Decision if d is not Decision.UNDECIDED]
            if _text(body, "decision") not in choices:
                raise ValueError(f"decision is one of {', '.join(choices)}")
            by, _, via = _who(body)
            a = engine.decide(ident, items, by=by, decision=Decision(_text(body, "decision")),
                              reason=_text(body, "reason"), via=via)
            return mask(to_dict(a))
        return _answer(run)

    @bp.post("/api/approvals/<ident>/<step>")
    def step_route(ident: str, step: str):
        if step not in STEPS:
            return jsonify(error=f"no step {step}: decide, {', '.join(STEPS)}, check, or apply"), 404
        if not writes:
            return jsonify(error="writes are off"), 405
        body = _body()

        def run() -> dict[str, Any]:
            from jason.approvals import engine
            from jason.approvals.model import to_dict

            (by, role, via), reason = _who(body), _text(body, "reason")
            if step == "submit":
                a = engine.submit(ident, by=by, role=role, via=via)
            elif step == "confirm":
                a = engine.confirm(ident, by=by, role=role, via=via)
            elif step == "decline":
                a = engine.decline(ident, by=by, reason=reason, via=via)
            else:
                a = engine.withdraw(ident, by=by, reason=reason, via=via)
            return mask(to_dict(a))
        return _answer(run)

    @bp.post("/api/approvals/<ident>/apply")
    def apply_route(ident: str):
        if not allow_apply or live is None:
            return jsonify(error=APPLY_OFF), 403
        if not header_token_ok():
            return jsonify(error=f"an apply carries this server's token in {TOKEN_HEADER}"), 403
        body = _body()
        echoed = _text(body, "confirm").strip()
        if not echoed:
            return jsonify(error="an apply echoes the fingerprint the person reviewed (confirm)"), 400

        def run():
            from dataclasses import asdict

            from jason.approvals import engine, registry, store
            from jason.approvals.model import to_dict

            a = store.load(ident)
            if echoed != a.fingerprint:
                return jsonify(error=f"the fingerprint reviewed is not {a.id}'s: nothing written. Reload it, review "
                                     "it again, and confirm what it shows", fingerprint=a.fingerprint,
                               status=a.status.value, supersededBy=a.superseded_by), 409
            by, _, via = _who(body)
            if not by.strip() or engine.problems(a):    # refused (and logged) before any sign-in
                engine.apply(a.id, engine.Live(), by=by, via=via)
            with live(registry.get(a.kind)) as lv:
                done = engine.apply(a.id, lv, by=by, via=via)
            if done.superseded_by is not None:
                fresh = done.superseded_by
                return jsonify(error=f"changed since review: nothing written. {a.id} is superseded by {fresh.id}; "
                                     "review the new plan", supersededBy=fresh.id,
                               changed=mask([asdict(c) for c in done.changed]), new=len(done.new),
                               approval=mask(to_dict(done.approval))), 409
            return mask(to_dict(done.approval))
        return _answer(run)

    return bp


__all__ = ["CAVEAT", "DOCUMENT_CSP", "EVIDENCE_REFRESH", "Grant", "Grants", "VIEW_TTL", "approvals",
           "audit_log", "blueprint", "default_live", "disposition", "evidence", "mask", "plans", "refresh_all_evidence",
           "refresh_evidence", "show", "view_evidence"]
