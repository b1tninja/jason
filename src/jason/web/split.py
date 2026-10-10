"""The splitter's page pictures through jason-web (docs/pdf-splitter.md, sections 3 and 8).

``GET /api/split/thumb?id=<session>&page=<n>&size=<96|200|800>`` is one page of the session's file, drawn by the server and kept by
content (``jason.tasks.split_thumbs``). It takes a session id and a page number, never a path or a name, and it is the board's: a
signed-in person whose offices open the file's level (P2; a confidential file is P3, which opens only while the private view is open),
judged again at every request. Each serve is logged in ``access/served.jsonl`` under the session id and page, never a name.

Answers: 200 with the picture (``ETag`` of the hash, page, size, and render version; ``304`` on a matching ``If-None-Match``;
``Cache-Control: private, max-age=31536000, immutable``, or ``private, no-store`` for a confidential file); 400 for a bad page or size;
401 signed out; 403 for a level the person's offices do not open; 404 for an unknown session; 422 for a page that could not be drawn
(``{"error": "This page could not be drawn"}``); 503 when no renderer is installed. A picture the drive had no room to keep is served
once with ``X-Split-Cache: full``.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, make_response, request

IMMUTABLE = "private, max-age=31536000, immutable"
NO_STORE = "private, no-store"


def _error(status: int, message: str):
    resp = jsonify(error=message)
    resp.status_code = status
    resp.headers["Cache-Control"] = "no-store"
    return resp


def blueprint() -> Blueprint:
    bp = Blueprint("split", __name__)

    @bp.get("/api/split/thumb")
    def split_thumb():
        from jason.mcp.county import _data_dir
        from jason.tasks import split_session as ss
        from jason.tasks import split_thumbs
        from jason.web import access
        from jason.web.extra import owner_view

        if request.args.get("view") == owner_view.OWNER:
            return access.refusal(403, "The page pictures of a scan are the board's: they are not served in the owner view.")
        viewer = access.signed_in()
        root = Path(_data_dir(None))
        try:
            page = int(request.args.get("page", ""))
            size = split_thumbs.size_of(request.args.get("size", "200"))
        except ValueError as exc:
            return _error(400, str(exc) if "pixels" in str(exc) else "A page is a number, from 1.")
        sid = str(request.args.get("id", ""))
        try:
            session = ss.load(root, sid)
        except KeyError:
            return _error(404, "No such split.")
        confidential = ss.is_confidential(root, session)
        level = access.Level.P3 if confidential else access.Level.P2
        access.allow(viewer, level)
        if page < 1 or page > session.pages:
            return _error(400, f"This file has {session.pages} pages.")
        tag = split_thumbs.etag(session.source.sha256, page, size)
        cache = NO_STORE if confidential else IMMUTABLE
        if tag in [t.strip() for t in request.headers.get("If-None-Match", "").split(",")]:
            access.log_or_refuse(viewer, level, path=f"split/{sid}", page=page, size=size, cached=True)
            resp = make_response("", 304)
            resp.headers["ETag"] = tag
            resp.headers["Cache-Control"] = cache
            return resp
        copy = ss.source_file(root, session.source.sha256)
        if not copy.is_file():
            return _error(404, "The copy of this file was removed; open the file again.")
        try:
            got = split_thumbs.get(root, copy, session.source.sha256, page, size)
        except split_thumbs.RendererUnavailable as exc:
            return _error(503, str(exc))
        except split_thumbs.PageUnreadable:
            return _error(422, "This page could not be drawn")
        except ValueError as exc:                       # a limit reached: the registry's words
            return _error(507, str(exc))
        access.log_or_refuse(viewer, level, path=f"split/{sid}", page=page, size=size)
        resp = make_response(got["data"])
        resp.headers["Content-Type"] = got["mime"]
        resp.headers["ETag"] = got["etag"]
        resp.headers["Cache-Control"] = cache
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = "sandbox"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if not got["kept"]:
            resp.headers["X-Split-Cache"] = "full"
        return resp

    return bp


__all__ = ["IMMUTABLE", "NO_STORE", "blueprint"]
