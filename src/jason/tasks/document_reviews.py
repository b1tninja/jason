"""The store of document reviews, and a lens run again over the stored readings (docs/ingestion-and-review.md, step 2).

A review is one lens applied to one document's stored fields (``jason.community.reviews``). This module keeps them on
disk and makes them again without reading any document:

- ``data/reviews/documents/<lens>/<as-of>.json`` holds one lens's reviews as of one date, by document id (a lens that
  needs no date uses ``undated.json``). It is written under the store lock. ``data/reviews/<task>/`` belongs to the
  manager-review packs; document reviews stay in their own folder.
- ``review_stored`` takes the rows of ``data/documents/readings.json``, applies a lens to each row's stored fields as
  of a date, saves the reviews, and says what changed against the findings the rows were stored with. It never reads a
  document and never changes ``readings.json``.
- A review is made again only when its key changes: the document, the text's digest, the lens's version, or the date
  (or, with those the same, the fields or the facts it read). Otherwise the stored one stands.
- The records lens's reviews are kept beside the as-of lens's (``data/reviews/documents/records/<as-of>.json``), under
  the same lock. Its facts come from the association's other records as they are on disk when the review is made, so
  ``review_stored`` with that lens makes again exactly the reviews whose other records changed since.

A review is a lead for a person, like the reading it rests on.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from jason.community.reviews import AS_OF, LENSES, Lens, Records, Review, join, lens_findings
from jason.locks import Resource, hold

ROOT = Path("reviews") / "documents"
LOCK = "document-reviews"
UNDATED = "undated"


def path(data_dir: Path, lens: str, as_of: date | None) -> Path:
    return Path(data_dir) / ROOT / lens / f"{as_of.isoformat() if as_of else UNDATED}.json"


def load(data_dir: Path, lens: str, as_of: date | None) -> dict[str, Review]:
    """One lens's stored reviews as of one date, by document id; empty when there is no such file."""
    file = path(data_dir, lens, as_of)
    try:
        body = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {doc: Review.from_dict(row) for doc, row in (body.get("reviews") or {}).items()}


def known(data_dir: Path, as_of: date) -> dict[str, dict[str, Review]]:
    """Every lens's stored reviews as of ``as_of``, by document id and then lens key: what a run hands to each reading."""
    out: dict[str, dict[str, Review]] = {}
    for lens in LENSES.values():
        for doc, review in load(data_dir, lens.key, as_of if lens.needs_as_of else None).items():
            out.setdefault(doc, {})[lens.key] = review
    return out


def of_reading(reading: Any, document: str, text_sha: str) -> list[Review]:
    """The reviews joined into a reading, keyed to the document and the text they were made from."""
    return [replace(r, document=document, text_sha=text_sha, reader=reading.model, kind=reading.kind.value) for r in reading.reviews]


def save(data_dir: Path, reviews: Iterable[Review]) -> list[Path]:
    """Store ``reviews``, each in its lens's file for its date, beside the reviews already there (a document's earlier
    review under the same lens and date is replaced). A review with no document id is not stored. A file is written only
    when a review in it is new or was made again."""
    groups: dict[tuple[str, date | None], list[Review]] = {}
    for review in reviews:
        if review.document:
            groups.setdefault((review.lens, review.as_of), []).append(review)
    written = []
    for (lens, as_of), group in groups.items():
        file = path(data_dir, lens, as_of)
        with hold(Resource.STORE, LOCK, timeout=120, purpose=f"reviews {lens} {as_of or UNDATED}"):
            try:
                body = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                body = {}
            stored = dict(body.get("reviews") or {})
            if all(review.reused and review.document in stored for review in group):
                continue
            stored.update({review.document: review.as_dict() for review in group})
            body = {"lens": lens, "asOf": as_of.isoformat() if as_of else None,
                    "writtenAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "reviews": stored}
            file.parent.mkdir(parents=True, exist_ok=True)
            scratch = file.with_suffix(".json.tmp")
            scratch.write_text(json.dumps(body, indent=1, default=str), encoding="utf-8")
            os.replace(scratch, file)
            written.append(file)
    return written


def dates(data_dir: Path, lens: str) -> list[date]:
    """The dates a lens has stored reviews for, oldest first."""
    out = []
    for file in (Path(data_dir) / ROOT / lens).glob("*.json"):
        try:
            out.append(date.fromisoformat(file.stem))
        except ValueError:
            continue
    return sorted(out)


def _reviewed(rows: Iterable[dict[str, Any]], lens: Lens, as_of: date, community: Any,
              stored: dict[str, Review], data_dir: Path | None = None) -> Iterator[tuple[dict[str, Any], Review, list[str]]]:
    """Each stored row the lens was joined into, with the lens's review of its stored fields as of ``as_of`` and the
    checks the row names that the lens no longer has. A lens that gathers reads the association's other records under
    ``data_dir`` as they stand now, through its facts functions; the document itself is not read."""
    lens.version   # loads the readers, which register the lens's checks: without them the first row would name checks the lens lacks
    for row in rows:
        stamp = (row.get("lenses") or {}).get(lens.key)
        if not stamp or not isinstance(row.get("fields"), dict):
            continue
        keys = list(stamp.get("slots") or {})
        text_sha = str(row.get("textSha") or "")
        old = stored.get(str(row.get("id")))
        records = Records(community, data_dir, str(row.get("name") or ""), str(row.get("period") or "")) if lens.gathers else None
        review = lens.review(row["fields"], [lens.checks[k] for k in keys if k in lens.checks], as_of, community, records=records,
                             reading_version=str(row.get("version") or ""), known=old if old is not None and old.text_sha == text_sha else None)
        yield row, replace(review, document=str(row.get("id") or ""), text_sha=text_sha, reader=str(row.get("model") or ""),
                           kind=str(row.get("kind") or "")), [k for k in keys if k not in lens.checks]


def joined_rows(data_dir: Path, community: Any, as_of: date, *, lens: Lens = AS_OF) -> list[dict[str, Any]]:
    """The stored readings as they stand as of ``as_of`` under ``lens``: each row the lens was joined into carries the
    lens's findings and derived fields for that date, and every other row is as stored. Nothing is written."""
    from jason.tasks.document_models import load as load_readings

    rows = load_readings(data_dir)
    stored = load(data_dir, lens.key, as_of if lens.needs_as_of else None)
    fresh = {id(row): join(row, review) for row, review, _gone in _reviewed(rows, lens, as_of, community, stored, Path(data_dir))}
    return [fresh.get(id(row), row) for row in rows]


def _same(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    return (finding.get("code", ""), finding.get("message", ""), finding.get("severity", ""), finding.get("authority", ""))


def difference(row: dict[str, Any], review: Review) -> dict[str, Any]:
    """What ``review`` changes in a stored row: the lens's findings that appear, vanish, or are reworded (the same code
    with other words or another severity), and the derived fields whose value changes."""
    before = [_same(f) for f in lens_findings(row, review.lens)]
    after = [_same(f.as_dict()) for f in review.findings]
    gone, new = list(before), []
    for f in after:
        if f in gone:
            gone.remove(f)
        else:
            new.append(f)
    reworded = []
    for f in list(new):
        was = next((g for g in gone if g[0] == f[0]), None)
        if was is not None:
            gone.remove(was)
            new.remove(f)
            reworded.append({"code": f[0], "was": was[1], "now": f[1], "severityWas": was[2], "severity": f[2]})
    fields = {name: [(row.get("fields") or {}).get(name), value] for name, value in review.fields.items()
              if (row.get("fields") or {}).get(name) != value}
    return {"appear": [{"code": c, "message": m, "severity": s} for c, m, s, _a in new],
            "vanish": [{"code": c, "message": m, "severity": s} for c, m, s, _a in gone], "reworded": reworded, "fields": fields}


CAVEATS = (
    "A review is made from a reading's stored fields; it reads no document. A field the reader got wrong is wrong here too.",
    "Only the lens's findings are made again. A reading's own findings, and any that read another store, stand as of the date "
    "the document was read (asOf on the row); jason models reads again.",
    "A finding is a lead for a person, not a determination.",
)
# For a lens that gathers (the records lens): what its reviews rest on beside the stored fields.
GATHERS_CAVEATS = (
    "A review is made from a reading's stored fields and from the association's other records as they are on disk now (the "
    "library, the ledger, the logs); the document itself is not read again. A field the reader got wrong is wrong here too.",
    "Only the lens's findings are made again. A reading's own findings stand as of the date the document was read (asOf on "
    "the row); jason models reads again.",
    "What the other records lack is not shown to be absent: \"not on file\" means the library does not hold it.",
    "A finding is a lead for a person, not a determination.",
)


def review_stored(data_dir: Path, community: Any, as_of: date, *, lens: Lens = AS_OF, kind: str = "",
                  include_confidential: bool = False) -> dict[str, Any]:
    """Apply ``lens`` as of ``as_of`` to every stored reading it was joined into, save the reviews, and report what
    changed against the findings the rows were stored with. No document is read, and ``readings.json`` is not changed."""
    from jason.tasks.document_models import load as load_readings

    data_dir = Path(data_dir)
    rows = [r for r in load_readings(data_dir) if not kind or r.get("kind") == kind]
    stored = load(data_dir, lens.key, as_of if lens.needs_as_of else None)
    reviews, changed, stored_as_of, gone_checks = [], [], Counter(), Counter()
    for row, review, gone in _reviewed(rows, lens, as_of, community, stored, data_dir):
        reviews.append(review)
        stored_as_of[str(row["lenses"][lens.key].get("asOf") or "")] += 1
        gone_checks.update(gone)
        change = difference(row, review)
        if change["appear"] or change["vanish"] or change["reworded"] or change["fields"]:
            if row.get("confidential") and not include_confidential:
                change["fields"] = {name: ["(held back)", "(held back)"] for name in change["fields"]}
            changed.append({"id": row.get("id"), "name": row.get("name"), "kind": row.get("kind"), "reader": row.get("model"),
                            "confidential": bool(row.get("confidential")), **change})
    written = save(data_dir, reviews)
    readers = {name for _kind, name in lens.readers()}
    unstamped = sum(1 for r in rows if r.get("model") in readers and not (r.get("lenses") or {}).get(lens.key))
    caveats = list(GATHERS_CAVEATS if lens.gathers else CAVEATS)
    if unstamped:
        caveats.append(f"{unstamped} readings by readers the lens reviews were stored before the lens was recorded on the row; "
                       "jason models reads them again.")
    if gone_checks:
        caveats.append("Checks the stored rows name that the lens no longer has: " + ", ".join(sorted(gone_checks)) + ".")
    return {"found": bool(reviews), "lens": lens.key, "question": lens.question, "version": lens.version,
            "asOf": as_of.isoformat(), "reads": sorted(b.value for b in lens.reads), "kinds": [k.value for k in lens.kinds],
            "readings": len(reviews), "made": sum(1 for r in reviews if not r.reused), "reused": sum(1 for r in reviews if r.reused),
            "storedAsOf": dict(sorted(stored_as_of.items())), "findings": sum(len(r.findings) for r in reviews),
            "changed": changed, "unreviewed": unstamped, "written": [str(p) for p in written], "caveats": caveats}


def review_lines(result: dict[str, Any]) -> list[str]:
    since = ", ".join(f"{day or 'no date'} ({n})" for day, n in result["storedAsOf"].items()) or "none"
    out = [f"The {result['lens']} lens (version {result['version']}) as of {result['asOf']}: {result['readings']} stored readings, "
           f"{result['findings']} findings; {result['made']} reviews made, {result['reused']} already stored",
           f"  reads: the stored fields{' and the specification' if 'profile' in result['reads'] else ''}; "
           + ("the association's other records as they are on disk now; no document is read again" if "store" in result["reads"]
              else "no document and no other store"),
           f"  the rows were stored as of: {since}", ""]
    if not result["changed"]:
        out.append("Nothing changes against the stored readings.")
    else:
        out.append(f"{len(result['changed'])} readings change against the stored rows:")
    for c in result["changed"]:
        out.append(f"  {c['name'] or c['id']} [{c['reader']}]")
        out += [f"    + {f['code']} ({f['severity']}): {f['message']}" for f in c["appear"]]
        out += [f"    - {f['code']} ({f['severity']}): {f['message']}" for f in c["vanish"]]
        for f in c["reworded"]:
            severity = f" ({f['severityWas']} to {f['severity']})" if f["severityWas"] != f["severity"] else ""
            out += [f"    ~ {f['code']}{severity}: {f['now']}", f"      was: {f['was']}"]
        out += [f"    = {name}: {was} to {now}" for name, (was, now) in c["fields"].items()]
    out += [""] + [f"Note: {c}" for c in result["caveats"]]
    return out


__all__ = ["ROOT", "path", "load", "known", "of_reading", "save", "dates", "joined_rows", "difference", "review_stored", "review_lines",
           "CAVEATS"]
