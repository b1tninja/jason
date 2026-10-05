"""Read the minutes the library lacks from Drive: one copy per meeting, read by the minutes model like a library file.

The meeting catalog (``data/meetings/catalog.json``) places each minutes file in Drive by its meeting's date. ``run``
takes, for each meeting whose minutes no library reading covers, one Drive copy: the Google Doc when there is one (the
original; the PDFs are its exports), else the PDF. It reads it (never changes it): a PDF downloaded, a Doc exported as
PDF, into ``data/meetings/minutes-files/<Drive id>.pdf`` with its text beside it (``.txt``), then reads the text with
the minutes model. Each reading goes into ``data/documents/readings.json`` with ``"source": "Drive"`` and the id
``drive-<Drive id>``, so the minutes questions, the cross-checks, and ``text_for`` find it; a library run keeps it.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.community.symbols import DocumentKind

FILES = Path("meetings") / "minutes-files"
DOC_MIME = "application/vnd.google-apps.document"


def wanted(data_dir: Path) -> list[dict[str, Any]]:
    """Per meeting whose minutes no reading covers: the Drive copy to read (the Doc first), with its date."""
    data_dir = Path(data_dir)
    catalog = json.loads((data_dir / "meetings" / "catalog.json").read_text(encoding="utf-8"))
    store = data_dir / "documents" / "readings.json"
    readings = json.loads(store.read_text(encoding="utf-8")).get("readings", []) if store.is_file() else []
    read_names = {r.get("name") for r in readings if r.get("kind") == DocumentKind.MINUTES.value}
    read_ids = {r.get("id") for r in readings}
    listing = json.loads((data_dir / "drive" / "files.json").read_text(encoding="utf-8"))
    mime = {r["id"]: r.get("mimeType", "") for r in (listing if isinstance(listing, list) else listing.get("files", []))}
    out = []
    for m in catalog.get("meetings", []):
        minutes = [r for r in m.get("records", []) if r.get("kind") == "minutes"]
        if not minutes or any(r.get("name") in read_names for r in minutes):
            continue
        drive = [r for r in minutes if r.get("where") == "Drive" and r.get("ref") in mime]
        if not drive:
            continue
        best = sorted(drive, key=lambda r: (mime[r["ref"]] != DOC_MIME, "draft" in r["name"].lower(), r["name"]))[0]
        if f"drive-{best['ref']}" in read_ids:
            continue
        out.append({"date": m["date"], "ref": best["ref"], "name": best["name"], "mimeType": mime[best["ref"]]})
    return out


def run(drive: Any, data_dir: Path, community: Any, *, limit: int = 0, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    from jason.community.document_models import ModelContext, read
    from jason.tasks import document_reviews
    from jason.tasks.document_models import provenance
    from jason.tasks.library import text_of

    data_dir = Path(data_dir)
    today = date.today()  # one as-of date for the run, recorded on each row
    todo = wanted(data_dir)[: limit or None]
    folder = data_dir / FILES
    folder.mkdir(parents=True, exist_ok=True)
    added, failed, reviews = [], [], []
    for w in todo:
        pdf = folder / f"{w['ref']}.pdf"
        try:
            if not pdf.is_file():
                if w["mimeType"] == DOC_MIME:
                    drive.export_pdf(w["ref"], pdf)
                else:
                    drive.download(w["ref"], pdf)
            text, _how = text_of(pdf)
        except Exception as exc:  # one file refused does not stop the rest
            failed.append({"ref": w["ref"], "name": w["name"], "error": str(exc)[:160]})
            continue
        (folder / f"{w['ref']}.txt").write_text(text, encoding="utf-8")
        entry = {"id": f"drive-{w['ref']}", "name": w["name"], "period": w["date"], "kind": DocumentKind.MINUTES.value,
                 # Executive session minutes are confidential (CIV 4935).
                 "confidential": "executive" in w["name"].lower(),
                 "hasText": bool(text.strip()), "model": None, "source": "Drive"}
        if text.strip():
            entry.update(provenance(text, today))
            reading = read(DocumentKind.MINUTES, text, ModelContext(community, data_dir, today, w["name"], w["date"]))
            if reading is not None:
                entry.update(reading.as_dict())
                reviews += document_reviews.of_reading(reading, entry["id"], entry["textSha"])
        added.append(entry)
        if log:
            log(f"{w['date']} {w['name']}: {'read' if entry.get('model') else 'no model recognized it' if text.strip() else 'no text'}")
    document_reviews.save(data_dir, reviews)   # the as-of lens's findings, apart from the readings
    store = data_dir / "documents" / "readings.json"
    body = json.loads(store.read_text(encoding="utf-8")) if store.is_file() else {"readings": []}
    ids = {e["id"] for e in added}
    body["readings"] = [r for r in body.get("readings", []) if r.get("id") not in ids] + added
    store.write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
    return {"wanted": len(todo), "read": sum(1 for e in added if e.get("model")), "noText": sum(1 for e in added if not e["hasText"]),
            "failed": failed}


def reread(data_dir: Path, community: Any) -> int:
    """Read the Drive minutes already fetched again with the current minutes model (after a rule changes)."""
    from jason.community.document_models import ModelContext, read
    from jason.tasks import document_reviews
    from jason.tasks.document_models import provenance

    data_dir = Path(data_dir)
    today = date.today()
    store = data_dir / "documents" / "readings.json"
    body = json.loads(store.read_text(encoding="utf-8"))
    n = 0
    reviews = []
    stored = document_reviews.known(data_dir, today)   # a review whose key and inputs are unchanged is not made again
    for r in body.get("readings", []):
        if r.get("source") != "Drive" or r.get("kind") != DocumentKind.MINUTES.value:
            continue
        kept = data_dir / FILES / f"{str(r['id'])[6:]}.txt"
        text = kept.read_text(encoding="utf-8", errors="ignore") if kept.is_file() else ""
        if not text.strip():
            continue
        sha = provenance(text, today)["textSha"]
        known = {lens: review for lens, review in stored.get(str(r["id"]), {}).items() if review.text_sha == sha}
        reading = read(DocumentKind.MINUTES, text, ModelContext(community, data_dir, today, r.get("name") or "", r.get("period") or "",
                                                                known=known))
        if reading is not None:
            r.update(reading.as_dict())
            r.update(provenance(text, today))
            reviews += document_reviews.of_reading(reading, str(r["id"]), r["textSha"])
            n += 1
    document_reviews.save(data_dir, reviews)
    store.write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
    return n


__all__ = ["reread", "run", "wanted"]
