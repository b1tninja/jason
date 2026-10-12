"""The PDF splitter's sources and write (docs/pdf-splitter.md, section 7).

- ``split_sessions(args)`` is ``GET /api/split-sessions``: the sessions (id, status, pages, segments, suggestions open, updated). A
  confidential file's label is masked. Disk only; the board's.
- ``split_session(args)`` is ``GET /api/split-session?id=``: one session: its source summary (an id, never a file name), boundaries,
  segments, suggestions with reasons, counts, and the version a save must start from. ``?facts=1-200`` adds the page facts for a range
  (the placeholders; each page carries its measured ``turn``, ``sideways``, ``fix``, and ``orientation`` when its text layer was read).
  ``?review=1`` adds the review of what an apply would do (a dry run: nothing is written). ``?flags=1`` adds the pre-review flags of each
  segment (blank only, near-duplicate of another segment, sideways pages, over the part limit, slot already filled, may hold more than one
  document): disk only, it cuts nothing.
- ``write(key, body)`` is ``POST /api/write/split/<session id>`` (``/api/write/split/new`` for ``open``), behind the write guard's token,
  with ``by`` (the signed-in person; a different name is refused). ``body["act"]`` is one of:

  - ``open`` ``{"ref": {"kind": "library", "id": ...} | {"kind": "upload", "name": ..., "base64": ...} | {"kind": "drive", "id": <Drive
    file id or link>}, "dryRun": false}``: start or resume (the same bytes resume the same draft). A server path is never taken from the
    console. A **Drive** file is read once, read-only, with the server's Drive token (never a browser): the dry run reads only its
    metadata and says what would happen (its pages are counted when it is read); the open refuses a folder, a non-PDF, a file over
    ``fetch.max_bytes``, a full drive, and a file over ``split.max_pages`` before it keeps a copy. When Drive is not connected the answer
    is ``{"found": false, "driveConnected": false, "why", "command"}``. Nothing is written to Drive;
  - ``boundaries`` ``{"boundaries": [[page, level], ...], "version": N}``: the autosave, the whole boundary set (one undo step);
  - ``mark`` / ``unmark`` ``{"pages": [..]}``, ``move`` ``{"from", "to"}``, ``level`` ``{"page", "level"}``, ``clear`` ``{"pages": [..]}``,
    ``range`` ``{"first", "last", "every"}``, ``label`` ``{"page", "field", "value"}``, ``undo``, ``redo``, ``accept`` / ``reject``
    ``{"id": "g12" | "all"}``: each with ``version``; a draft that moved on answers **409** with the server's copy;
  - ``suggest``: run the cheap rule pass again (off when ``split.suggest_enabled`` is off); the model pass is not built;
  - ``review``: the dry run of an apply;
  - ``apply`` ``{"dryRun": true (the default), "confirm": false, "parts": [...], "drop": [pages], "keepCopies": false, "filing": "",
    "rotate": ..., "ocr": true}``: **a dry run unless** ``dryRun`` is false **and** ``confirm`` is true, as the signed-in person; it writes through the
    record intake's one split writer. The original is never changed. ``filing`` is ``held`` (every part kept in jason's store), ``library``
    (every part given to the library intake; one it cannot file is kept held, with the reason) or ``slots`` (each part into the slot it
    names); a part's own ``filing`` (``held``, ``library``, ``slot``) overrides it, and with neither a part with a slot fills it and any
    other is held. A part filed to the library with no text layer gets a background OCR job in the person's name (``"ocr": false``
    opts out; at most ``split.ocr_queue_max`` per apply); the answer carries ``ocrQueued``, ``ocrSkipped``, ``notQueued``. ``rotate`` turns pages **in the new files only**: ``{"61": 90, "66": "fix"}`` (degrees clockwise, or ``fix`` for the
    degrees jason measured the page's text needs), or ``"sideways"`` for every page measured sideways. ``review`` takes the same;
  - ``decline`` ``{"dryRun": false}``.

Nothing here reaches PayHOA, Google, or the county; the one Drive read is ``open`` with ``{"kind": "drive"}``, and it writes nothing there. A confidential file is masked in every answer, and its pictures need the
private view (``jason.web.split``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

Args = dict[str, str]

ACTS = ("open", "boundaries", "mark", "unmark", "move", "level", "clear", "range", "label", "undo", "redo", "accept", "reject",
        "suggest", "review", "apply", "decline")
CAVEATS = (
    "A suggestion is jason's guess, with its reasons; it is not a boundary until a person accepts it. A split writes new files "
    "only when a person confirms it, and the original is never changed.",
)
OWNER_REFUSED = "The splitter is the board's: it is not served in the owner view."


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _community() -> Any:
    from jason.community import community

    return community()


def _gate(body: dict[str, Any] | None = None) -> None:
    """The splitter is the board's. In a request: the owner view is refused, and a signed-in roster person whose offices open the board's
    level (P2) is required where console sign-in is set up. Outside a request (a script, a test) there is no one to refuse."""
    from flask import abort, current_app, has_request_context, request

    if not has_request_context():
        return
    from jason.web import access

    if request.args.get("view") == "owner" or str((body or {}).get("view") or "") == "owner":
        abort(access.refusal(403, OWNER_REFUSED))
    sign_in = current_app.extensions.get("jason_sign_in")
    if sign_in is not None and getattr(sign_in, "configured", False):
        access.require(access.Level.P2)


def split_sessions(args: Args) -> dict[str, Any]:
    from jason.tasks import split_session as ss

    _gate()
    return {"sessions": ss.listing(_root()), "limits": _limits(), "caveats": list(CAVEATS)}


def _limits() -> dict[str, Any]:
    from jason import limits

    c = _community()
    return {"maxPages": limits.value("split.max_pages", community=c), "suggestEnabled": bool(limits.value("split.suggest_enabled", community=c)),
            "draftDays": limits.value("split.draft_days", community=c), "maxParts": limits.value("split.max_parts", community=c),
            "clientRender": bool(limits.value("split.client_render", community=c)),
            "clientRenderMaxPages": limits.value("split.client_render_max_pages", community=c)}


def split_session(args: Args) -> dict[str, Any]:
    from jason.tasks import split_mask
    from jason.tasks import split_session as ss
    from jason.tasks import split_thumbs

    _gate()
    sid = (args.get("id") or "").strip()
    if not sid:
        raise ValueError("a split is named by its id: ?id=")
    root = _root()
    try:
        session = ss.load(root, sid)
    except KeyError:
        from flask import abort, has_request_context, jsonify, make_response

        if has_request_context():
            abort(make_response(jsonify(error="No such split."), 404))
        raise KeyError(sid) from None
    out: dict[str, Any] = {**ss.view_of(root, session), "renderer": split_thumbs.renderer_name() or "", "sizes": list(split_thumbs.SIZES),
                           "limits": _limits(), "caveats": list(CAVEATS)}
    held = ss.standing(root, session)
    out["confidential"] = held.confidential
    hide = split_mask.hide_text(held)
    if hide:
        out["confidentialWhy"] = held.words
        out["retry"] = not held.known
    span = (args.get("facts") or "").strip()
    if span:
        a, _, b = span.partition("-")
        out["facts"] = ss.facts_view(root, sid, int(a or 1), int(b or a or 0), lqip=not out["confidential"])["facts"]
    if (args.get("review") or "").strip() in ("1", "true", "yes") and session.status in ("draft", "confirmed"):
        out["review"] = split_mask.review(ss.review(sid, community=_community(), root=root), hide)
    if (args.get("flags") or "").strip() in ("1", "true", "yes"):
        from jason.tasks import split_flags

        out["flags"] = split_flags.flags(sid, community=_community(), root=root)
    return out


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    from flask import abort, jsonify, make_response

    from jason.community.split_session import SplitConflict
    from jason.tasks import split_mask
    from jason.tasks import split_session as ss
    from jason.web.extra.record_slots import _actor

    act = str(body.get("act") or "").strip()
    if act not in ACTS:
        raise ValueError(f"act is one of {', '.join(ACTS)}")
    _gate(body)
    by = _actor(str(body.get("by") or ""))
    community, root = _community(), _root()
    version = body.get("version")
    try:
        if act == "open":
            ref = dict(body.get("ref") or {})
            if ref.get("path") or str(ref.get("kind") or "") == "path":
                raise ValueError("the console opens a library file or an upload's bytes, never a path on the server")
            client = None
            if str(ref.get("kind") or "") == "drive":
                from jason.tasks import drive_choose
                from jason.web.extra import drive_choose as web_drive

                try:
                    client = web_drive._open()
                except drive_choose.DriveUnavailable as exc:
                    return drive_choose.unavailable_answer(exc)
            try:
                out = ss.open_session(ref, by=by, dry_run=bool(body.get("dryRun")), community=community, root=root, drive=client)
            finally:
                closer = getattr(client, "close", None)
                if callable(closer):
                    closer()
            if not body.get("dryRun") and out.get("factsPending"):
                out.update(ss.queue_facts(root, out["session"]["id"], by))
            return {"ok": True, "act": act, **{k: v for k, v in out.items() if k != "ok"}}
        sid = key
        if act in ("review", "apply"):
            parts = list(body.get("parts") or ())
            drop = [int(p) for p in body.get("drop") or ()]
            kw = {"parts": parts, "drop": drop, "keep_copies": bool(body.get("keepCopies")), "community": community, "root": root,
                  "filing": str(body.get("filing") or ""), "rotate": body.get("rotate")}
            hide = ss.hides_text(root, ss.load(root, sid))
            if act == "review":
                return {"ok": True, "act": act, "review": split_mask.review(ss.review(sid, **kw), hide)}
            dry = body.get("dryRun", True) is not False
            try:
                out = ss.apply(sid, by=by, confirm=bool(body.get("confirm")) and not dry, dry_run=dry,
                               ocr=body.get("ocr") is not False, expect=str(body.get("expect") or ""), **kw)
            except ss.PlanChanged as exc:        # the draft moved since the review: nothing was written; the new review comes back
                abort(make_response(jsonify(error=str(exc), conflict=True, planChanged=True,
                                            review=split_mask.review(exc.review, hide)), 409))
            return {"ok": True, "act": act, **split_mask.apply_result(out, hide)}
        if act == "suggest":
            return {"act": act, **ss.suggest(sid, by=by, community=community, root=root)}
        if act == "decline":
            return {"ok": True, "act": act, **ss.decline(sid, by=by, note=str(body.get("note") or ""), dry_run=bool(body.get("dryRun")),
                                                        root=root, community=community)}
        return {"act": act, **ss.act(sid, act, body, by=by, version=None if version is None else int(version),
                                     dry_run=bool(body.get("dryRun")), community=community, root=root)}
    except SplitConflict as exc:
        abort(make_response(jsonify(error=str(exc), conflict=True, current=exc.current), 409))
    except ss.LibraryBusy as exc:                    # the library could not be read: not "no such file"; a person tries again
        resp = make_response(jsonify(error=str(exc), busy=True, retryAfter=exc.retry_after), 503)
        resp.headers["Retry-After"] = str(exc.retry_after)
        abort(resp)
