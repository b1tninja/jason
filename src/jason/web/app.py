"""WSGI app for the React UI.

One process, one origin: ``/api/*`` is JSON over the stores already on disk, and every other path serves the built
bundle, falling back to ``index.html`` so client-side routes survive a reload. Its writes go to jason's own stores,
each behind the write guard (``jason.web.guard``: Host, Origin, and a per-process token). The one exception is the
approvals' check (a live PayHOA read that writes nothing) and apply (a PayHOA write), and apply is off unless a person
starts it with ``--allow-apply`` (``jason.web.approvals``). It binds to loopback unless a person passes ``--host``.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, make_response, request, send_from_directory

from jason.web import guard, signin
from jason.web.approvals import LiveFactory, blueprint as approvals_routes, default_live
from jason.web.sources import confirm_owner_info_write, default_loaders, extra_writer, set_board_item, write_canvas, write_decision, write_hearing_decision, write_request

DEFAULT_DIST = Path(__file__).resolve().parents[3] / "ui" / "dist"

# name -> loader; each takes the query args and returns a JSON-able dict. Loaders import lazily so the app starts
# without loading a profile (importing jason loads none).
Loader = Callable[[dict[str, str]], dict[str, Any]]
Writer = Callable[[str, dict[str, Any]], dict[str, Any]]


def create_app(dist: Path | None = None, loaders: dict[str, Loader] | None = None, board_writer: Writer | None = set_board_item,
               canvas_writer: Writer | None = write_canvas, decision_writer: Writer | None = write_decision,
               request_writer: Writer | None = write_request, owner_info_writer: Writer | None = confirm_owner_info_write,
               hearing_writer: Writer | None = write_hearing_decision, extra_writes: bool = True,
               approvals_live: LiveFactory | None = default_live, allow_apply: bool = False,
               approvals_writes: bool = True, hosts: tuple[str, ...] = (),
               sign_in: signin.SignIn | None = None) -> Flask:
    """``allow_apply`` turns on ``POST /api/approvals/<id>/apply``, a write to PayHOA (``jason-web --allow-apply``);
    ``approvals_live`` builds the live context a check or an apply reads (None turns both off); ``hosts`` adds a
    name the Host check accepts beside the loopback names (``--host``); ``sign_in`` is Google sign-in
    (``jason.web.signin``; default: as .env sets it up, not required)."""
    dist = Path(dist) if dist else Path(os.environ.get("JASON_UI_DIST", DEFAULT_DIST))
    sources = default_loaders() if loaders is None else loaders
    app = Flask(__name__, static_folder=None)
    token = guard.install(app, hosts=hosts)
    signin.install(app, sign_in or signin.default_sign_in())
    app.config["JASON_ALLOW_APPLY"] = bool(allow_apply and approvals_live is not None)
    app.register_blueprint(approvals_routes(live=approvals_live, allow_apply=allow_apply, writes=approvals_writes))

    @app.get("/api/session")
    def session():
        """What the page needs to write: the token to send in ``X-Jason-Token``, which writes are on, and who is
        signed in (``signedIn``, from Google sign-in; null when no one is)."""
        return jsonify(token=token, header=guard.TOKEN_HEADER, applyEnabled=app.config["JASON_ALLOW_APPLY"],
                       liveChecks=approvals_live is not None, approvalsWrites=approvals_writes, **signin.session_info())

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

    @app.post("/api/decisions")
    @app.post("/api/decisions/<decision_id>")
    def decision(decision_id: str = ""):
        """The board's decision at a meeting, recorded in its words: a motion, the votes, the outcome. jason's own store."""
        if decision_writer is None:
            return jsonify(error="writes are off"), 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(decision_writer(decision_id, body))
        except KeyError:
            return jsonify(error=f"no decision {decision_id}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post("/api/onboarding/<key>")
    def onboarding_request(key: str):
        """What a person did about one item of the request list: asked, received, pinned, gap, not applicable."""
        if request_writer is None:
            return jsonify(error="writes are off"), 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(request_writer(key, body))
        except KeyError:
            return jsonify(error=f"no request item {key}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post("/api/owner-info/<path:key>")
    def owner_info_confirm(key: str):
        """A person's confirmation of one planned PayHOA write; the apply stays a terminal command."""
        if owner_info_writer is None:
            return jsonify(error="writes are off"), 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(owner_info_writer(key, body))
        except KeyError:
            return jsonify(error=f"no planned write {key}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post("/api/hearings/<path:key>")
    def hearing_decision(key: str):
        """The board's decision after a hearing, in its words; the notice stays a letter a person fills and sends."""
        if hearing_writer is None:
            return jsonify(error="writes are off"), 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(hearing_writer(key, body))
        except KeyError:
            return jsonify(error=f"no hearing {key}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post("/api/write/<store>/<path:key>")
    def extra_write(store: str, key: str):
        """A person's entry into one of the extra stores (jason.web.extra): a decision, a choice, a filled blank."""
        writer = extra_writer(store) if extra_writes else None
        if writer is None:
            return jsonify(error=f"no writes for {store}"), 405 if extra_writes else 405
        body = request.get_json(silent=True) or {}
        try:
            return jsonify(writer(key, body))
        except KeyError as exc:
            return jsonify(error=f"no {store} {exc.args[0] if exc.args else key}"), 404
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.get("/api/file")
    def local_file():
        """A photo or document under data/, read-only, for a canvas to show. Only files under data/ and only these types."""
        from flask import abort, send_file

        from jason.mcp.county import _data_dir

        root = _data_dir(None).resolve()
        rel = request.args.get("path", "")
        target = (root / rel).resolve()
        if not rel or not target.is_relative_to(root) or not target.is_file():
            abort(404)
        kinds = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                 ".pdf": "application/pdf", ".md": "text/plain", ".txt": "text/plain",
                 ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".ogg": "audio/ogg"}
        mime = kinds.get(target.suffix.lower())
        if mime is None:
            abort(404)
        resp = send_file(target, mimetype=mime, conditional=True)
        resp.headers["Content-Security-Policy"] = "sandbox"  # a served SVG or PDF runs no script against the app
        return resp

    @app.get("/api/health")
    def health():
        return jsonify(ok=True, ui=(dist / "index.html").is_file(), sources=sorted(sources), writes=[w for w, on in (("board-items", board_writer), ("canvases", canvas_writer), ("decisions", decision_writer), ("onboarding", request_writer), ("owner-info", owner_info_writer), ("hearings", hearing_writer)) if on] + (sorted(__import__("jason.web.sources", fromlist=["EXTRA_WRITERS"]).EXTRA_WRITERS) if extra_writes else []))

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
        html = (dist / "index.html").read_text(encoding="utf-8")
        resp = make_response(guard.inject_meta(html, token))
        resp.mimetype = "text/html"
        resp.headers["Cache-Control"] = "no-cache, no-store"     # it carries this process's token
        return resp

    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="jason-web", description="Serve the board UI: reads, and writes to jason's own "
                                "stores behind the write guard. PayHOA is written only with --allow-apply.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--dist", type=Path, default=None, help="built UI folder (default ui/dist)")
    p.add_argument("--allow-apply", action="store_true",
                   help="turn on POST /api/approvals/<id>/apply: an approved plan written to PayHOA, after a live "
                        "re-read, by the named person who echoes its fingerprint. Off by default")
    p.add_argument("--require-sign-in", action="store_true",
                   help="refuse every write until an officer signs in with Google (docs/setup.md, Console sign-in)")
    a = p.parse_args(argv)
    from waitress import serve

    sign_in = signin.default_sign_in(required=a.require_sign_in)
    if a.require_sign_in and not sign_in.configured:
        p.error(f"--require-sign-in needs Google sign-in set up: {signin.DESKTOP_KEY} or {signin.RECORD_KEY} in .env "
                "(docs/setup.md, Console sign-in)")
    if a.allow_apply:
        print("jason-web: apply is ON: an approved plan can be written to PayHOA from the console", file=sys.stderr)
    if sign_in.configured:
        key = signin.client_record(signin._settings())[1]
        which = "jason's Desktop client" if key == signin.DESKTOP_KEY else "the Web client"
        print(f"jason-web: Google sign-in is on with {which} ({key}){' and required for writes' if a.require_sign_in else ''}; "
              f"its redirect is http://{a.host}:{a.port}{signin.CALLBACK}", file=sys.stderr)
    serve(create_app(a.dist, allow_apply=a.allow_apply, hosts=(a.host,), sign_in=sign_in), host=a.host, port=a.port)


if __name__ == "__main__":
    main()
