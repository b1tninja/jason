"""jason's copies of Drive files through jason-web: the thumbnail a screen shows beside a Drive file.

``GET /api/drive/thumb/<id>`` serves the thumbnail jason kept when a person last read the file from Drive
(``jason.tasks.drive_copies``, ``data/drive/copies/<id>.png``). It reads disk only, never Google: the browser asks
jason, and jason never asks Google on a page load. It needs a signed-in roster person whose offices open the file's
level (``jason.web.access``; ``drive_copies.level_of``: P3 confidential, only in the private view; P0 a letter
template or a file under a Drive root's path rule; else P2), and each serve is logged in ``access/served.jsonl``.

Answers: 200 with the image (``Cache-Control: private, max-age=300``, ``nosniff``, ``CSP: sandbox``); 401 signed out;
403 for a level the person's offices do not open; 404 ``{"error": "No preview yet"}`` when there is no thumbnail (no
copy yet, or Drive gave none); 404 for something that is not a Drive id.

Exporting a file (the copy and its thumbnail) is a person's act through the evidence's refresh
(``POST /api/evidence/refresh`` with ``drive:<id>``, or ``/api/evidence/refresh-many``), not a route here.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

NO_PREVIEW = "No preview yet"
THUMB_CACHE = "private, max-age=300"
THUMB_TYPES = {".png": "image/png", ".jpg": "image/jpeg"}


def _missing(message: str = NO_PREVIEW):
    resp = jsonify(error=message)
    resp.status_code = 404
    resp.headers["Cache-Control"] = "no-store"
    return resp


def blueprint() -> Blueprint:
    bp = Blueprint("drive", __name__)

    @bp.get("/api/drive/thumb/<file_id>")
    def drive_thumb(file_id: str):
        """A Drive file's kept thumbnail, from disk, for a signed-in person whose offices open the file's level."""
        from flask import send_file

        from jason.tasks import drive_copies
        from jason.web import access

        viewer = access.signed_in()
        if not drive_copies.valid_id(file_id):
            return _missing("Not a Drive file id.")
        root = drive_copies.data_root()
        level = access.Level(drive_copies.level_of(root, file_id))
        access.allow(viewer, level)
        path = drive_copies.thumbnail(root, file_id)
        mime = THUMB_TYPES.get(path.suffix.lower()) if path is not None else None
        if path is None or mime is None:
            return _missing()
        access.log_or_refuse(viewer, level, path=f"{drive_copies.COPIES.as_posix()}/{path.name}")
        resp = send_file(path.resolve(), mimetype=mime, conditional=True, etag=True, max_age=300)
        resp.headers["Cache-Control"] = THUMB_CACHE
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Content-Security-Policy"] = "sandbox"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    return bp


__all__ = ["NO_PREVIEW", "THUMB_CACHE", "blueprint"]
