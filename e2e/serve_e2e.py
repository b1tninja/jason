"""A test-only launcher for the console's end-to-end suite (e2e/README.md).

It builds the real Flask app (``jason.web.app.create_app``) with the pieces the Python tests use for a signed-in person
(``tests/webclient.py``: Google sign-in set up over a made-up roster, nothing reaching Google), on the made-up private facts
(``tests/fixtures/spec``) and a throwaway data folder. Nothing here is imported by, or switched on in, the shipped app: the
only extra is two routes added to this process's app object, ``/__e2e/sign-in?name=...`` and ``/__e2e/sign-out``, which
put a roster person's account in the browser's session as the sign-in callback does after Google answers. They exist only
while this launcher runs, and it binds 127.0.0.1.

    python e2e/serve_e2e.py --port 8765 [--dist ui/dist] [--data DIR]

Prints ``READY <url> <data folder>`` when it serves. Never touches the real ``data/`` folder, Keeper, Google, or PayHOA.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["JASON_SPEC_DIR"] = str(ROOT / "tests" / "fixtures" / "spec")
os.environ["JASON_PROFILE"] = "mystique"
os.environ["JASON_CONFIG"] = str(ROOT / "tests" / "fixtures" / "no-user-config.env")
os.environ["JASON_OCR_OLLAMA"] = "0"
for name in ("JASON_COMMUNITY", "JASON_COMMUNITY_VIA", "JASON_DEFAULT_COMMUNITY_SHIM"):
    os.environ.pop(name, None)
os.environ["JASON_COMMUNITY_NOTICED"] = "shim,alias"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))


def build(data: Path, dist: Path, required: bool = False):
    """The real app over ``data``, with the splitter reading that folder."""
    import webclient

    from jason.community import community
    from jason.web.app import create_app
    from jason.web.sources import default_loaders

    community()                     # reads the made-up private facts before anything else
    app = create_app(dist, default_loaders(), approvals_live=None, sign_in=webclient.roster_sign_in(required=required))

    from flask import redirect, request, session

    @app.get("/__e2e/sign-in")
    def e2e_sign_in():
        person = next(p for p in webclient.roster_people() if p.name == request.args.get("name", "A Manager"))
        session["account"] = {"name": person.name, "role": person.role, "email": person.email,
                              "sub": "sub-" + person.name.lower().replace(" ", "-"), "at": "2026-10-03T12:00:00+00:00",
                              "admin": person.admin, "provider": "google"}
        return redirect(request.args.get("next", "/"))

    @app.get("/__e2e/sign-out")
    def e2e_sign_out():
        session.pop("account", None)
        return redirect("/")

    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--dist", default=str(ROOT / "ui" / "dist"))
    p.add_argument("--require-sign-in", action="store_true", help="writes and board reads need a sign-in, as jason-web --require-sign-in")
    p.add_argument("--fresh", action="store_true", help="empty the --data folder first (it must be named e2e/.run/...)")
    p.add_argument("--data", default="", help="the data folder (default: a new temporary one)")
    a = p.parse_args(argv)
    data = Path(a.data) if a.data else Path(tempfile.mkdtemp(prefix="jason-e2e-"))
    if a.fresh and data.exists():
        if (ROOT / "e2e" / ".run") not in data.resolve().parents:
            raise SystemExit("--fresh empties only a folder under e2e/.run")
        shutil.rmtree(data)
    data.mkdir(parents=True, exist_ok=True)
    from jason.community import split_gold

    (data / "e2e").mkdir(exist_ok=True)
    (data / "e2e" / "sample.pdf").write_bytes(split_gold.numbered().pdf)      # five made-up documents of 3, 2, 4, 1, and 3 pages
    os.environ["JASON_DATA_DIR"] = str(data.resolve())      # every store the console reads or writes is under the throwaway folder
    app = build(data, Path(a.dist), a.require_sign_in)
    from waitress import serve

    print(f"READY http://127.0.0.1:{a.port} {data}", flush=True)
    serve(app, host="127.0.0.1", port=a.port, threads=8)


if __name__ == "__main__":
    main()
