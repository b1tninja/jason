"""Build a local sample set: a few real PDFs of every known document kind, from the PDFs already on disk.

    python scripts/build_samples.py [--per-kind 3] [--max-mb 8] [--dry-run]

Reads the library's own classification (``data/library/library.db``) and, for every other PDF under ``data/``, the
active profile's name rules (``community().classify_document``). A document is never classified by a model here: a
name that matches nothing goes to ``unclassified``. Copies at most ``--per-kind`` distinct files (by SHA-256) of each
``DocumentKind`` into ``data/samples/<kind>/`` and writes ``data/samples/manifest.json``. ``data/`` is not checked in:
the samples hold real, sometimes confidential, documents. A kind with no PDF on disk is listed as a gap.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from jason.community import community
from jason.community.symbols import DocumentKind

DATA = Path("data")
OUT = DATA / "samples"
# Folders under data/ that are copies of the library, outputs, or tooling, not sources of documents.
SKIP = {"samples", "library", "revisions", "packets", "annotations", "readings", "reports", "retrieval"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_rows() -> list[dict]:
    db = DATA / "library" / "library.db"
    if not db.exists():
        return []
    con = sqlite3.connect(db)
    rows = []
    for kind, path, confidential in con.execute("select kind, path, confidential from documents"):
        file = DATA / "library" / "files" / path
        if kind and file.suffix.lower() == ".pdf" and file.exists():
            rows.append({"kind": kind, "file": file, "confidential": bool(confidential), "how": "library"})
    return rows


def other_rows() -> list[dict]:
    rules = community()
    rows = []
    for folder in sorted(p for p in DATA.iterdir() if p.is_dir() and p.name not in SKIP):
        for file in folder.rglob("*"):
            if file.suffix.lower() != ".pdf" or not file.is_file():
                continue
            try:
                kind = rules.classify_document(file.name, None, file.relative_to(folder).as_posix())
            except Exception:  # noqa: BLE001 - one odd name never stops the walk
                kind = None
            rows.append({"kind": kind.value if kind else "unclassified", "file": file, "confidential": False,
                         "how": f"name rules ({folder.name})"})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-kind", type=int, default=3)
    ap.add_argument("--max-mb", type=float, default=8.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pick", action="append", default=[], metavar="KIND=PATH",
                    help="a file a person (or a search of Gmail and Drive) found for a kind the name rules miss; repeatable")
    args = ap.parse_args()
    limit = int(args.max_mb * 1024 * 1024)

    rows = library_rows() + other_rows()
    for pick in args.pick:
        kind, _, path = pick.partition("=")
        if kind not in {k.value for k in DocumentKind}:
            raise SystemExit(f"--pick {pick!r}: {kind!r} is not a document kind")
        file = Path(path)
        if not file.is_file():
            raise SystemExit(f"--pick {pick!r}: no such file")
        rows.append({"kind": kind, "file": file, "confidential": False, "how": "picked by search"})
    by: dict[str, list[dict]] = {}
    for row in rows:
        if row["file"].stat().st_size <= limit:
            by.setdefault(row["kind"], []).append(row)

    manifest, taken = {}, set()
    for kind in [k.value for k in DocumentKind] + ["unclassified"]:
        # library-classified first, then smaller files: a sample should open quickly
        candidates = sorted(by.get(kind, []), key=lambda r: (r["how"] not in ("library", "picked by search"), r["file"].stat().st_size))
        chosen = []
        if not args.dry_run and (OUT / kind).is_dir():
            shutil.rmtree(OUT / kind)  # this script's own folder for the kind; a rebuild replaces it
        for row in candidates:
            digest = sha256(row["file"])
            if digest in taken:
                continue
            taken.add(digest)
            target = OUT / kind / row["file"].name
            if not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(row["file"], target)
            chosen.append({"file": target.as_posix(), "source": row["file"].as_posix(), "sha256": digest,
                           "confidential": row["confidential"], "classified_by": row["how"],
                           "bytes": row["file"].stat().st_size})
            if len(chosen) >= args.per_kind:
                break
        manifest[kind] = {"available": len(by.get(kind, [])), "samples": chosen}

    if not args.dry_run:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    gaps = [k for k, v in manifest.items() if not v["samples"] and k != "unclassified"]
    print(f"{sum(len(v['samples']) for v in manifest.values())} samples in {sum(1 for v in manifest.values() if v['samples'])} kinds")
    print("no PDF on disk for:", ", ".join(gaps) or "none")


if __name__ == "__main__":
    main()
