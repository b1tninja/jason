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
sys.path.insert(0, str(Path(__file__).resolve().parent))


def build(data: Path, dist: Path, required: bool = False, port: int = 0):
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

    @app.get("/__e2e/limit")
    def e2e_limit():
        """Set (``?key=split.client_render&value=off``) or clear (no ``value``) one limit for this process, as ``JASON_LIMIT_<KEY>`` does."""
        from jason import limits

        env = limits.limit(request.args["key"]).env_name
        if request.args.get("value"):
            os.environ[env] = request.args["value"]
        else:
            os.environ.pop(env, None)
        return {"ok": True, "env": env, "value": os.environ.get(env, "")}

    @app.get("/__e2e/sign-out")
    def e2e_sign_out():
        session.pop("account", None)
        return redirect("/")

    if port:
        # Google's Picker and Drive stood in for (e2e/pick_fake.py): the real start and callback routes run, the "Google" they leave for is
        # this process, and the files are made up. Choosing from the person's own Drive stays off until a test turns `pick.enabled` on.
        import pick_fake

        pick_fake.install(app, f"http://127.0.0.1:{port}")

    return app


def seed_library(data: Path) -> None:
    """A made-up library for the explorer: three PDFs (a 13-page scan filed from the PayHOA library, a 2-page minutes file taken in by
    hand with its text held, and a confidential statement), their classification rows, and the text the library holds for one."""
    import sqlite3

    import pymupdf

    from jason.community import split_gold
    from jason.tasks.library import SCHEMA

    files = data / "library" / "files"
    (data / "library" / "text").mkdir(parents=True, exist_ok=True)
    (files / "Board").mkdir(parents=True, exist_ok=True)
    (files / "Confidential").mkdir(parents=True, exist_ok=True)
    (files / "Board" / "Combined Scan 2099.pdf").write_bytes(split_gold.numbered().pdf)

    def small(path: Path, pages: list[str]) -> None:
        doc = pymupdf.open()
        for text in pages:
            doc.new_page().insert_text((72, 100), text)
        doc.save(str(path))
        doc.close()

    small(files / "Board" / "Board Minutes 2099-06.pdf", ["Minutes of the board meeting, made up.", "Motion carried, made up."])
    small(files / "Confidential" / "Bank Statement 2099-06.pdf", ["Statement, made up."])
    (data / "library" / "text" / "7002.txt").write_text("Minutes of the board meeting, made up.", encoding="utf-8")
    rows = [("7001", "payhoa", "Board/Combined Scan 2099.pdf", "Combined Scan 2099.pdf", "", "", "", "NONE", "2099-06", 0),
            ("7002", "ingest", "Board/Board Minutes 2099-06.pdf", "Board Minutes 2099-06.pdf", "minutes", "governance", "minutes", "NAME", "2099-06", 0),
            ("7003", "payhoa", "Confidential/Bank Statement 2099-06.pdf", "Bank Statement 2099-06.pdf", "bank_statement", "financial", "", "NAME", "2099-06", 1)]
    with sqlite3.connect(data / "library" / "library.db") as conn:
        conn.execute(SCHEMA)
        conn.executemany("INSERT INTO documents (id, source, path, name, kind, category, records, method, period, confidential, evidence)"
                         " VALUES (?,?,?,?,?,?,?,?,?,?,'')", rows)


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
    # The made-up private facts are copied beside the data: a test that pins a file to a record slot writes the slot's store under this folder,
    # and the checked-in fixtures must stay as they are.
    spec = data / "e2e-spec"
    shutil.copytree(ROOT / "tests" / "fixtures" / "spec", spec, dirs_exist_ok=True)
    os.environ["JASON_SPEC_DIR"] = str(spec)
    from jason.community import split_gold

    (data / "e2e").mkdir(exist_ok=True)
    (data / "e2e" / "sample.pdf").write_bytes(split_gold.numbered().pdf)      # five made-up documents of 3, 2, 4, 1, and 3 pages
    sys.path.insert(0, str(ROOT / "scripts"))
    from client_pdf_make import build_image_pdf

    build_image_pdf(data / "e2e" / "jpx.pdf", "jpx", 3, 60)            # three made-up pages, each one JPEG 2000 image (JPXDecode)
    build_image_pdf(data / "e2e" / "ccitt.pdf", "ccitt", 3, 100)       # three made-up pages, each one 1-bit CCITT Group 4 image
    seed_library(data)
    os.environ["JASON_DATA_DIR"] = str(data.resolve())      # every store the console reads or writes is under the throwaway folder
    app = build(data, Path(a.dist), a.require_sign_in, a.port)
    from waitress import serve

    print(f"READY http://127.0.0.1:{a.port} {data}", flush=True)
    serve(app, host="127.0.0.1", port=a.port, threads=8)


if __name__ == "__main__":
    main()
