"""A recorded copy's thumbnail through jason-web: page 1 of a PDF under the data folder, for a screen's preview cell.

``GET /api/thumb?path=<path under data/>`` renders the PDF's first page with PyMuPDF (``jason.tasks.pdf_thumbs``) and
keeps it in ``data/thumbs``, rendered again when the PDF changes. It reads disk only, never Google, PayHOA, or the
county, so a screen may load it on page load. It is judged as ``/api/file`` is: a signed-in roster person whose offices
open the file's level (``jason.web.access.level_of_path``; P3 only while their private view is open), and each serve is
logged in ``access/served.jsonl`` under the PDF's path.

Answers: 200 with the PNG (``Cache-Control: private, max-age=300``, ``nosniff``, ``CSP: sandbox``); 401 signed out;
404 for no path, a path outside the data folder, a file that is not a PDF on disk, or one that cannot be rendered
(``{"error": "No preview yet"}``); 403 for a level the person's offices do not open.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request

NO_PREVIEW = "No preview yet"
THUMB_CACHE = "private, max-age=300"


def _missing(message: str = NO_PREVIEW):
    resp = jsonify(error=message)
    resp.status_code = 404
    resp.headers["Cache-Control"] = "no-store"
    return resp


def blueprint() -> Blueprint:
    bp = Blueprint("previews", __name__)

    @bp.get("/api/thumb")
    def pdf_thumb():
        """Page 1 of a PDF under data/, as a PNG about 300 pixels wide, for a signed-in person who may open the PDF."""
        from flask import send_file

        from jason.mcp.county import _data_dir
        from jason.tasks import pdf_thumbs
        from jason.web import access

        viewer = access.signed_in()
        root = Path(_data_dir(None)).resolve()
        rel = str(request.args.get("path", "") or "").strip().replace("\\", "/").lstrip("/")
        try:
            target = (root / rel).resolve()
            posix = target.relative_to(root).as_posix()
        except (OSError, ValueError):
            return _missing("Not a file under the data folder.")
        if not rel or target.suffix.lower() != ".pdf" or not target.is_file():
            return _missing("Not a PDF on disk.")
        level = access.level_of_path(posix, root)
        access.allow(viewer, level)
        png = pdf_thumbs.thumbnail(root, posix)
        if png is None:
            return _missing()
        access.log_or_refuse(viewer, level, path=posix, thumb=True)
        resp = send_file(png.resolve(), mimetype="image/png", conditional=True, etag=True, max_age=300)
        resp.headers["Cache-Control"] = THUMB_CACHE
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = "sandbox"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    return bp


__all__ = ["NO_PREVIEW", "THUMB_CACHE", "blueprint"]
