"""WSGI app for the React UI.

One process, one origin: ``/api/*`` is JSON over the stores already on disk (no PayHOA, Google, or Keeper calls),
and every other path serves the built bundle, falling back to ``index.html`` so client-side routes survive a reload.
Read-only: the API has no write routes. It binds to loopback unless a person passes ``--host``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request, send_from_directory

from jason.web.sources import default_loaders, set_board_item, write_canvas

DEFAULT_DIST = Path(__file__).resolve().parents[3] / "ui" / "dist"

# name -> loader; each takes the query args and returns a JSON-able dict. Loaders import lazily so the app starts
# without loading a profile (importing jason loads none).
Loader = Callable[[dict[str, str]], dict[str, Any]]
Writer = Callable[[str, dict[str, Any]], dict[str, Any]]


def create_app(dist: Path | None = None, loaders: dict[str, Loader] | None = None, board_writer: Writer | None = set_board_item,
               canvas_writer: Writer | None = write_canvas) -> Flask:
    dist = Path(dist) if dist else Path(os.environ.get("JASON_UI_DIST", DEFAULT_DIST))
    sources = default_loaders() if loaders is None else loaders
    app = Flask(__name__, static_folder=None)

    @app.post("/api/board-items/<item_id>")
    def board_item(item_id: str):
        """The board's columns only (status, owner, meeting, notes), as `jason board --set`. Nothing else is written."""
        if board_writer is None:
            return jsonify(error="writes are off"), 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(board_writer(item_id, body))
        except KeyError:
            return jsonify(error=f"no item {item_id}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post("/api/canvases")
    @app.post("/api/canvases/<key>")
    def canvas(key: str = ""):
        """A person's scratchpad: create, edit the editable fields, or add a clip. jason's own store, nothing outward."""
        if canvas_writer is None:
            return jsonify(error="writes are off"), 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(canvas_writer(key, body))
        except KeyError:
            return jsonify(error=f"no canvas {key}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, ui=(dist / "index.html").is_file(), sources=sorted(sources), writes=[w for w, on in (("board-items", board_writer), ("canvases", canvas_writer)) if on])

    @app.get("/api/<name>")
    def source(name: str):
        load = sources.get(name)
        if load is None:
            return jsonify(error=f"no such source: {name}"), 404
        try:
            return jsonify(load(request.args.to_dict()))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except Exception as exc:  # a missing store is a miss to show, not a crash
            return jsonify(error=f"{type(exc).__name__}: {exc}"), 500

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def bundle(path: str):
        if path.startswith("api/"):
            return jsonify(error="not found"), 404
        if not (dist / "index.html").is_file():
            return ("UI not built: run `npm install && npm run build` in ui/.", 503)
        target = dist / path
        if path and target.is_file() and target.resolve().is_relative_to(dist.resolve()):
            resp = send_from_directory(dist, path)
            if path.startswith("assets/"):  # content-hashed by Vite
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        resp = send_from_directory(dist, "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="jason-web", description="Serve the board UI (read-only).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--dist", type=Path, default=None, help="built UI folder (default ui/dist)")
    a = p.parse_args(argv)
    from waitress import serve

    serve(create_app(a.dist), host=a.host, port=a.port)


if __name__ == "__main__":
    main()
