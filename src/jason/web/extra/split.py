"""The PDF splitter's sources and write (docs/pdf-splitter.md, section 7).

- ``split_sessions(args)`` is ``GET /api/split-sessions``: the sessions (id, status, pages, segments, suggestions open, updated). A
  confidential file's label is masked. Disk only; the board's.
- ``split_session(args)`` is ``GET /api/split-session?id=``: one session: its source summary (an id, never a file name), boundaries,
  segments, suggestions with reasons, counts, and the version a save must start from. ``?facts=1-200`` adds the page facts for a range
  (the placeholders). ``?review=1`` adds the review of what an apply would do (a dry run: nothing is written).
- ``write(key, body)`` is ``POST /api/write/split/<session id>`` (``/api/write/split/new`` for ``open``), behind the write guard's token,
  with ``by`` (the signed-in person; a different name is refused). ``body["act"]`` is one of:

  - ``open`` ``{"ref": {"kind": "library", "id": ...} | {"kind": "upload", "name": ..., "base64": ...}, "dryRun": false}``: start or
    resume (the same bytes resume the same draft). A server path is never taken from the console;
  - ``boundaries`` ``{"boundaries": [[page, level], ...], "version": N}``: the autosave, the whole boundary set (one undo step);
  - ``mark`` / ``unmark`` ``{"pages": [..]}``, ``move`` ``{"from", "to"}``, ``level`` ``{"page", "level"}``, ``clear`` ``{"pages": [..]}``,
    ``range`` ``{"first", "last", "every"}``, ``label`` ``{"page", "field", "value"}``, ``undo``, ``redo``, ``accept`` / ``reject``
    ``{"id": "g12" | "all"}``: each with ``version``; a draft that moved on answers **409** with the server's copy;
  - ``suggest``: run the cheap rule pass again (off when ``split.suggest_enabled`` is off); the model pass is not built;
  - ``review``: the dry run of an apply;
  - ``apply`` ``{"dryRun": true (the default), "confirm": false, "parts": [...], "drop": [pages], "keepCopies": false}``: **a dry run
    unless** ``dryRun`` is false **and** ``confirm`` is true, as the signed-in person; it writes through the record intake's one split
    writer. The original is never changed;
  - ``decline`` ``{"dryRun": false}``.

Nothing here reaches Drive, PayHOA, Google, or the county. A confidential file is masked in every answer, and its pictures need the
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
            "draftDays": limits.value("split.draft_days", community=c), "maxParts": limits.value("split.max_parts", community=c)}


def split_session(args: Args) -> dict[str, Any]:
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
    out["confidential"] = ss.is_confidential(root, session)
    span = (args.get("facts") or "").strip()
    if span:
        a, _, b = span.partition("-")
        out["facts"] = ss.facts_view(root, sid, int(a or 1), int(b or a or 0), lqip=not out["confidential"])["facts"]
    if (args.get("review") or "").strip() in ("1", "true", "yes") and session.status in ("draft", "confirmed"):
        out["review"] = ss.review(sid, community=_community(), root=root)
    return out


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    from flask import abort, jsonify, make_response

    from jason.community.split_session import SplitConflict
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
            out = ss.open_session(ref, by=by, dry_run=bool(body.get("dryRun")), community=community, root=root)
            if not body.get("dryRun") and out.get("factsPending"):
                out.update(ss.queue_facts(root, out["session"]["id"], by))
            return {"ok": True, "act": act, **{k: v for k, v in out.items() if k != "ok"}}
        sid = key
        if act in ("review", "apply"):
            parts = list(body.get("parts") or ())
            drop = [int(p) for p in body.get("drop") or ()]
            kw = {"parts": parts, "drop": drop, "keep_copies": bool(body.get("keepCopies")), "community": community, "root": root}
            if act == "review":
                return {"ok": True, "act": act, "review": ss.review(sid, **kw)}
            dry = body.get("dryRun", True) is not False
            out = ss.apply(sid, by=by, confirm=bool(body.get("confirm")) and not dry, dry_run=dry, **kw)
            return {"ok": True, "act": act, **out}
        if act == "suggest":
            return {"act": act, **ss.suggest(sid, by=by, community=community, root=root)}
        if act == "decline":
            return {"ok": True, "act": act, **ss.decline(sid, by=by, note=str(body.get("note") or ""), dry_run=bool(body.get("dryRun")),
                                                        root=root, community=community)}
        return {"act": act, **ss.act(sid, act, body, by=by, version=None if version is None else int(version),
                                     dry_run=bool(body.get("dryRun")), community=community, root=root)}
    except SplitConflict as exc:
        abort(make_response(jsonify(error=str(exc), conflict=True, current=exc.current), 409))
