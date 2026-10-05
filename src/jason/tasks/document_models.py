"""Read every classified library file with its kind's document model; store the readings and report coverage.

``run`` walks the classified library (``jason library``), reads each file's cached text with the models registered
for its kind (``jason.community.document_models``), and writes ``data/documents/readings.json``: per file its kind,
the model that read it, whether the record is complete, what is missing, the fields, and the findings. ``read_file``
reads one file on disk (a Drive copy the library lacks) the same way. ``coverage`` says, per kind, how many files
there are, how many have text, how many a model read, and how many readings are complete, and lists the kinds no
model reads yet. It reads disk only.

A confidential library file's fields stay on disk; ``summary`` leaves them out unless asked.

**Files the library does not hold.** ``run_filed`` reads the documents ``jason gmail --file-vendor`` filed to Drive from
email (the filing log, ``data/drive/vendor-files.jsonl``): the local copy of each attachment, its words from the
library's ``text_of`` (the text layer, else local OCR; the vision model only when a person asks) kept in the library's
text cache under the row's id, and the row made the way ``run`` makes one, under the id ``drive-<Drive file id>``.
``run`` keeps every row of a file the library does not hold (``outside_library``): those, and the Drive minutes'
(``jason.tasks.drive_minutes``). Each pass writes the store under its lock.

**What a row says about its own making** (docs/ingestion-and-review.md, the inventory). Beside the keys above, a row
carries ``textSha`` (the SHA-256 of the text the reader was given), ``asOf`` (the date the reader used as today),
``version`` (``reader_version`` of the model that read it), ``fieldsBasis`` (what ``parse`` read to fill the fields),
and on each finding ``basis`` (what the call that produced it read). A row written before these keys has none of
them, and every reader of the store treats them as optional. ``basis`` reports, from the stored rows alone, which
findings are ingestion (the text only) and which are reviews.

**A row is a joined view** (docs/ingestion-and-review.md, step 2). What depends on the date is made by the as-of lens,
and what depends on another document or store by the records lens (``jason.community.reviews``); both are joined into
the row, so the row shows what it always did. The row says which part is which: a finding from a lens carries ``lens``
and ``check``; ``lenses`` gives, per lens, its version, its as-of date, where each check's findings go among the row's
own (``slots``, and ``order`` where two lenses share a row), and the fields it derived; ``checkBasis`` is what the
reader's own check read; ``enriched`` names the fields looked up in another store after the parse and what that read.
``parts`` takes a row apart along those lines. ``run`` also saves each lens's review apart from the row
(``jason.tasks.document_reviews``), and ``jason models --as-of DATE`` (with ``--lens records`` for the second) makes
them again from the stored fields without reading a document.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from jason.community.document_models import Basis, ModelContext, basis_values, modeled_kinds, read
from jason.community.symbols import DocumentKind

STORE = Path("documents") / "readings.json"
LOCK = "document-readings"                 # the store's lock: each pass reads the file, changes its own rows, and writes it back
FILED_SOURCE = "Drive, filed from email"   # the ``source`` of a row ``run_filed`` writes


def _kind(value: str) -> DocumentKind | None:
    try:
        return DocumentKind(value)
    except ValueError:
        return None


def text_sha(text: str) -> str:
    """The SHA-256 of a text as the reader was given it (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def provenance(text: str, today: date) -> dict[str, str]:
    """What a row records of its inputs: the text's digest and the date used as today."""
    return {"textSha": text_sha(text), "asOf": today.isoformat()}


def _entry(data_dir: Path, community: Any, today: date, stored: dict[str, Any], *, ident: str, name: str, period: str,
           kind: DocumentKind, confidential: bool, text: str) -> tuple[dict[str, Any], list[Any]]:
    """One file's row of the store, and the lens reviews joined into it: the one way a row is made, whichever pass
    found the file. ``stored`` is ``document_reviews.known`` for the run's date."""
    from jason.tasks import document_reviews

    entry = {"id": ident, "name": name, "period": period, "kind": kind.value, "confidential": confidential,
             "hasText": bool(text.strip()), "model": None}
    if not text.strip():
        return entry, []
    entry.update(provenance(text, today))
    sha = entry["textSha"]
    context = ModelContext(community, data_dir, today, str(name or ""), str(period or ""), confidential,
                           {lens: r for lens, r in stored.get(str(ident), {}).items() if r.text_sha == sha})
    try:
        reading = read(kind, text, context)
    except Exception as exc:  # one bad file does not stop the run; the error is the finding
        entry["error"] = f"{type(exc).__name__}: {exc}"
        reading = None
    if reading is None:
        return entry, []
    entry.update(reading.as_dict())
    return entry, document_reviews.of_reading(reading, str(ident), sha)


def outside_library(row: dict[str, Any]) -> bool:
    """A row of a file the library does not hold: one read from Drive (``jason.tasks.drive_minutes``) or filed to Drive
    from email (``run_filed``). A library run did not write it and keeps it."""
    return row.get("source") == "Drive" or str(row.get("id") or "").startswith("drive-")


def _replace(data_dir: Path, readings: list[dict[str, Any]], keep: Any) -> list[dict[str, Any]]:
    """Write the store as the rows ``keep`` takes from it followed by ``readings``, under the store's lock."""
    from jason.locks import Resource, hold

    path = Path(data_dir) / STORE
    with hold(Resource.STORE, LOCK, timeout=120, purpose="jason models"):
        path.parent.mkdir(parents=True, exist_ok=True)
        old = json.loads(path.read_text(encoding="utf-8")).get("readings", []) if path.is_file() else []
        result = {"readAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "readings": [r for r in old if keep(r)] + readings}
        path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result["readings"]


def run(data_dir: Path, community: Any, *, kinds: tuple[DocumentKind, ...] = (), today: date | None = None) -> dict[str, Any]:
    """Read the library with the document models and save the readings."""
    from jason.tasks import document_reviews
    from jason.tasks.library import distinct, load, text_for

    data_dir = Path(data_dir)
    today = today or date.today()  # one as-of date for the whole run
    rows = distinct(load(data_dir))
    stored = document_reviews.known(data_dir, today)   # a review whose key and inputs are unchanged is not made again
    readings, reviews = [], []
    for row in rows:
        kind = _kind(str(row.get("kind") or ""))
        if kind is None or (kinds and kind not in kinds):
            continue
        entry, made = _entry(data_dir, community, today, stored, ident=row["id"], name=row.get("name"), period=row.get("period"),
                             kind=kind, confidential=bool(row.get("confidential")), text=text_for(data_dir, row["id"]))
        readings.append(entry)
        reviews += made
    document_reviews.save(data_dir, reviews)   # each lens's findings as of today, apart from the readings (data/reviews/documents)
    # A run over some kinds keeps the other kinds' readings; every run keeps the readings of files the library does not
    # hold (Drive's minutes, the documents filed from email), which their own passes write.
    return coverage(_replace(data_dir, readings, lambda r: outside_library(r) or (kinds and _kind(r["kind"]) not in kinds)))


# ---------------------------------------------------------------------------------------------------------------
# The documents filed to Drive from email (``jason gmail --file-vendor``), which the library does not hold.


def filed(data_dir: Path, kinds: tuple[DocumentKind, ...]) -> list[dict[str, Any]]:
    """The filing log's rows of ``kinds`` (``data/drive/vendor-files.jsonl``), one per Drive file, in the log's order."""
    from jason.tasks.vendor_files import LOG

    path = Path(data_dir) / "drive" / LOG
    if not path.is_file():
        return []
    wanted = {k.value for k in kinds}
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("kind") in wanted and row.get("file_id"):
            out[str(row["file_id"])] = row            # a file moved or tagged again is logged again: the last row stands
    return list(out.values())


def local_copies(data_dir: Path) -> dict[str, Path]:
    """Where the bytes of an email attachment are on disk, by SHA-256: the files ``jason gmail --files`` saved, from
    their index (``data/gmail/files.json``). Only files that are there."""
    from jason.tasks.gmail import email_files

    out: dict[str, Path] = {}
    for f in email_files(Path(data_dir)):
        path = Path(data_dir) / str(f.get("path") or "").replace("\\", "/")   # the index may hold another system's separators
        if f.get("sha256") and f["sha256"] not in out and path.is_file():
            out[str(f["sha256"])] = path
    return out


def _vision_page_read(data_dir: Path, ident: str) -> str:
    """How much of a file the vision model read, from its note beside the cached text; "" when it read none."""
    from jason.tasks.library import TEXT_DIR

    try:
        note = json.loads((Path(data_dir) / TEXT_DIR / f"{ident}.vision.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return f"vision model {note.get('model') or note.get('engine') or ''}, {note.get('pagesRead')} of {note.get('pages')} pages".replace("  ", " ")


# How ``text_of`` says it could not read a file. Such a file is tried again on the next pass: an OCR engine may be there by then.
_NOT_READ = ("image-only", "image;", "unreadable", "no text reader", "PyMuPDF not installed")


def filed_text(data_dir: Path, ident: str, path: Path, sha256: str, *, engines: Sequence[Any] | None = None, vision: Any = None,
               refresh: bool = False, label: str = "") -> tuple[str, str]:
    """The words of a filed document and how they were read, kept in the library's text cache under the row's id.

    The library's ``text_of`` reads them: the text layer, else, for a scan, the OCR engines that run on this machine
    without the model server (``engines``; None is ``ocr.local_engines``). A file whose bytes are unchanged since its
    text was cached is not read again; ``refresh`` reads it again. ``vision`` is the vision model's reader, only when a
    person asked: it reads a file that has no text layer, under the GPU lock, and its reading is kept beside the cached
    text the way ``library.vision_read`` keeps one. Returns ("", reason) when nothing could be read."""
    from jason.community import ocr
    from jason.tasks.library import TEXT_DIR, text_for, text_of, vision_read

    folder = Path(data_dir) / TEXT_DIR
    cache, note_path = folder / f"{ident}.txt", folder / f"{ident}.json"
    try:
        note = json.loads(note_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        note = {}
    settled = note.get("sha256") == sha256 and not str(note.get("source") or "").startswith(_NOT_READ)
    if not refresh and settled and cache.is_file() and cache.read_text(encoding="utf-8", errors="ignore").strip():
        how = str(note.get("source") or "cached text")
    else:
        text, how = text_of(path, ocr_engines=tuple(ocr.local_engines() if engines is None else engines))
        folder.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        note_path.write_text(json.dumps({"path": label or path.name, "file": str(path), "source": how, "sha256": sha256,
                                         "chars": len(text)}), encoding="utf-8")
        for stale in (folder / f"{ident}.vision.txt", folder / f"{ident}.vision.json"):
            if stale.is_file():
                stale.unlink()                          # a vision reading of other bytes, or one a refresh asks for again
    if vision is not None and not how.startswith("text layer"):
        from jason.locks import Resource, hold

        with hold(Resource.GPU, purpose=f"jason models --filed --vision: {path.name}"):
            vision_read(Path(data_dir), ident, engine=vision)
    text = text_for(Path(data_dir), ident)
    seen = _vision_page_read(data_dir, ident)
    if seen:
        how = f"{seen}; else {how}"
    return (text, how) if text.strip() else ("", how or "no words in the file")


def run_filed(data_dir: Path, community: Any, *, kinds: tuple[DocumentKind, ...] = (DocumentKind.INSPECTION_REPORT,),
              today: date | None = None, engines: Sequence[Any] | None = None, vision: Any = None, refresh: bool = False,
              log: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Read the documents filed to Drive from email with the document models, and save their readings.

    ``jason gmail --file-vendor`` files a vendor's attachments to Drive and logs each filing; the library does not hold
    them, so ``run`` never reads them. For each logged filing of ``kinds`` this reads the local copy of the attachment
    (``local_copies``) with its kind's readers, the way ``run`` reads a library file, and stores the row under the id
    ``drive-<Drive file id>`` with ``source`` and, under ``filed``, where it came from and how its words were read.

    - A filing whose bytes the library also holds is left to the library's reading.
    - A filing with no local copy is a miss: it gets no row and is listed (``jason gmail --files`` saves the copies).
    - A file no reader recognizes, or one with no words, gets a row with no model, so the next pass and a person can
      see it was tried and why it was not read.

    It reads disk only. ``vision`` (the vision model's reader, after ``local_ai.preflight``) is for a person who asked;
    without it a scan goes to the local OCR engines and never to a model."""
    from jason.community.content import private_content
    from jason.community.library import CONFIDENTIAL_KINDS
    from jason.tasks import document_reviews
    from jason.tasks.library import load as library_rows

    data_dir = Path(data_dir)
    today = today or date.today()
    say = log or (lambda _m: None)
    in_library = {str(r.get("sha256")) for r in library_rows(data_dir) if r.get("sha256")}
    copies = local_copies(data_dir)
    stored = document_reviews.known(data_dir, today)
    rows, reviews = [], []
    result: dict[str, Any] = {"kinds": [k.value for k in kinds], "filed": 0, "inLibrary": [], "noLocalCopy": [], "noText": [],
                              "noModel": [], "read": [], "how": Counter()}
    for filing in filed(data_dir, kinds):
        result["filed"] += 1
        name, sha = str(filing.get("name") or ""), str(filing.get("sha256") or "")
        ident = f"drive-{filing['file_id']}"
        if sha and sha in in_library:
            result["inLibrary"].append(name)
            continue
        path = copies.get(sha)
        if path is None:
            result["noLocalCopy"].append(name)
            say(f"{name}: no local copy of the attachment (jason gmail --files saves them)")
            continue
        text, how = filed_text(data_dir, ident, path, sha, engines=engines, vision=vision, refresh=refresh,
                               label=f"{filing.get('where') or 'Drive'}/{name}")
        kind = DocumentKind(filing["kind"])
        # Confidential by the library's own rule: the kind, or member-level detail in the words.
        held = kind in CONFIDENTIAL_KINDS or bool(private_content(kind, text))
        entry, made = _entry(data_dir, community, today, stored, ident=ident, name=name, period="", kind=kind,
                             confidential=held, text=text)
        entry["source"] = FILED_SOURCE
        entry["filed"] = {"vendor": filing.get("vendor"), "sent": str(filing.get("at") or "")[:10], "where": filing.get("where"),
                          "messageId": filing.get("message_id"), "sha256": sha,
                          "file": path.relative_to(data_dir).as_posix(), "textFrom": how}
        rows.append(entry)
        reviews += made
        result["how"][how if text.strip() else "no words"] += 1
        result["read" if entry.get("model") else "noModel" if text.strip() else "noText"].append(name)
        say(f"{name}: " + (f"read by {entry['model']} ({how})" if entry.get("model")
                           else f"no reader recognized it ({how})" if text.strip() else f"no words ({how})"))
    document_reviews.save(data_dir, reviews)
    ids = {r["id"] for r in rows}
    _replace(data_dir, rows, lambda r: r.get("id") not in ids)
    return {**result, "how": dict(result["how"]), "rows": rows}


def filed_lines(result: dict[str, Any]) -> list[str]:
    out = [f"{result['filed']} filed document(s) of kind {', '.join(result['kinds'])} in the filing log: {len(result['read'])} read, "
           f"{len(result['noModel'])} no reader recognized, {len(result['noText'])} with no words, "
           f"{len(result['noLocalCopy'])} with no local copy, {len(result['inLibrary'])} the library holds"]
    if result["how"]:
        out.append("  words from: " + "; ".join(f"{how} ({n})" for how, n in sorted(result["how"].items())))
    for key, label in (("noModel", "no reader recognized"), ("noText", "no words"),
                       ("noLocalCopy", "no local copy (jason gmail --files saves the attachments)")):
        out += [f"  {label}: {name}" for name in result[key]]
    return out


def read_file(path: Path, kind: DocumentKind, community: Any, *, data_dir: Path | None = None, today: date | None = None) -> dict[str, Any]:
    """One file on disk (a PDF, or its text) read with ``kind``'s models."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from jason.tasks.library import text_of

        text, _how = text_of(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")
    today = today or date.today()
    reading = read(kind, text, ModelContext(community, data_dir, today, path.name, ""))
    return {"file": str(path), "kind": kind.value, **provenance(text, today),
            **(reading.as_dict() if reading else {"model": None, "note": "no model recognized the text"})}


def load(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / STORE
    return json.loads(path.read_text(encoding="utf-8")).get("readings", []) if path.is_file() else []


def coverage(readings: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, Counter] = defaultdict(Counter)
    severities: dict[str, Counter] = defaultdict(Counter)
    for r in readings:
        c = by_kind[r["kind"]]
        c["files"] += 1
        c["text"] += int(r["hasText"])
        c["read"] += int(bool(r.get("model")))
        c["complete"] += int(bool(r.get("complete")))
        c["errors"] += int(bool(r.get("error")))
        for f in r.get("findings") or []:
            severities[r["kind"]][f["severity"]] += 1
    modeled = {k.value for k in modeled_kinds()}
    rows = [{"kind": k, "modeled": k in modeled, **dict(c), "findings": dict(severities[k])} for k, c in by_kind.items()]
    rows.sort(key=lambda r: (-r["files"], r["kind"]))
    return {"kinds": rows, "files": sum(r["files"] for r in rows), "read": sum(r.get("read", 0) for r in rows),
            "unmodeled": [r["kind"] for r in rows if not r["modeled"]]}


def summary(data_dir: Path, *, kind: str = "", include_confidential: bool = False, limit: int = 50) -> dict[str, Any]:
    """The stored readings of one kind (or all), newest first, with the findings; a confidential file's fields are held back."""
    readings = [r for r in load(data_dir) if not kind or r["kind"] == kind]
    readings.sort(key=lambda r: str(r.get("period") or ""), reverse=True)
    out = []
    for r in readings[:limit]:
        row = {k: v for k, v in r.items() if k != "fields"}
        if r.get("fields") is not None and (include_confidential or not r.get("confidential")):
            row["fields"] = r["fields"]
        out.append(row)
    return {"found": bool(readings), "coverage": coverage(load(data_dir)), "readings": out,
            "caveats": ["A reading is what a model found in the file's text; OCR text can be wrong, and a finding is a lead, not a determination."]}


_CONTEXT = (Basis.PROFILE.value, Basis.STORE.value, Basis.TODAY.value)

BASIS_CAVEATS = (
    "The basis is observed per call, not per finding: a finding carries everything its check read, so \"review\" is an upper "
    "bound. A finding marked text only needed nothing but the record.",
    "A text-only finding on a reading whose fields read the profile, a store, or today is not ingestion yet: the record it "
    "came from was not filled from the text alone.",
    "What a reader reaches without its context (a cache an earlier call filled, a clock it reads itself) is not seen.",
)


def basis_report(readings: list[dict[str, Any]], *, kind: str = "") -> dict[str, Any]:
    """Which stored findings are ingestion and which are reviews, from the rows alone (nothing is read again).

    Per reader and finding code: how many, what the calls that produced them read (every part any of them read, and the
    parts all of them read), how many read the text only, and the class: ``ingestion`` when every one read the text
    only, ``review`` when any read more, ``not observed`` for rows stored before the basis was recorded. Per reader:
    what ``parse`` read to fill the fields, in how many readings."""
    readers: dict[str, dict[str, Any]] = {}
    as_of: Counter = Counter()
    by_basis: Counter = Counter()
    by_lens: Counter = Counter()
    for r in readings:
        if not r.get("model") or (kind and r.get("kind") != kind):
            continue
        row = readers.setdefault(r["model"], {"reader": r["model"], "kinds": set(), "versions": set(), "readings": 0, "observed": 0,
                                              "fields": Counter(), "codes": {}, "enriched": Counter(), "enrichedFields": set(),
                                              "lensFields": set(), "check": Counter(), "checked": 0})
        row["kinds"].add(r.get("kind") or "")
        row["readings"] += 1
        if r.get("version"):
            row["versions"].add(r["version"])
        if r.get("asOf"):
            as_of[r["asOf"]] += 1
        fields = r.get("fieldsBasis")
        if fields:
            row["observed"] += 1
            row["fields"].update(b for b in fields if b in _CONTEXT)
        if r.get("checkBasis") is not None:
            row["checked"] += 1
            row["check"].update(b for b in r["checkBasis"] if b in _CONTEXT)
        enriched = r.get("enriched") or {}
        row["enrichedFields"].update(enriched.get("fields") or ())
        row["enriched"].update(b for b in enriched.get("basis") or () if b in _CONTEXT)
        for stamp in (r.get("lenses") or {}).values():
            row["lensFields"].update(stamp.get("fields") or ())
        through = [b for b in fields or () if b in _CONTEXT]
        for f in r.get("findings") or []:
            code = row["codes"].setdefault(f["code"], {"code": f["code"], "count": 0, "observed": 0, "textOnly": 0, "throughFields": 0,
                                                       "lens": 0, "parts": Counter()})
            code["count"] += 1
            if f.get("lens"):
                code["lens"] += 1
                by_lens[f["lens"]] += 1
            basis = f.get("basis") or []
            if not basis:
                continue
            code["observed"] += 1
            code["parts"].update(basis)
            by_basis["+".join(basis)] += 1
            if basis == [Basis.TEXT.value]:
                code["textOnly"] += 1
                code["throughFields"] += int(bool(through))
    out, totals = [], Counter()
    for name in sorted(readers):
        row = readers[name]
        codes = []
        for c in sorted(row["codes"].values(), key=lambda c: (-c["count"], c["code"])):
            parts = c.pop("parts")
            c["basis"] = basis_values({Basis(p) for p in parts})
            c["always"] = basis_values({Basis(p) for p, n in parts.items() if n == c["observed"]})
            # A lens's finding is a review made apart from the reading; "review" alone is one the reader's own check still makes.
            c["class"] = "not observed" if not c["observed"] else "ingestion" if c["textOnly"] == c["observed"] else \
                "lens" if c["lens"] == c["count"] else "review"
            codes.append(c)
        summed = Counter()
        for c in codes:
            summed.update({"findings": c["count"], "ingestion": c["textOnly"], "review": c["observed"] - c["textOnly"],
                           "unobserved": c["count"] - c["observed"], "ingestionThroughFields": c["throughFields"], "lens": c["lens"]})
        totals.update(summed)
        totals.update({"readings": row["readings"], "observed": row["observed"]})
        out.append({"reader": name, "kinds": sorted(row["kinds"]), "versions": sorted(row["versions"]), "readings": row["readings"],
                    "observed": row["observed"], "fields": {b: row["fields"][b] for b in _CONTEXT if row["fields"][b]},
                    "enriched": {"fields": sorted(row["enrichedFields"]), **{b: row["enriched"][b] for b in _CONTEXT if row["enriched"][b]}},
                    "lensFields": sorted(row["lensFields"]),
                    # What the reader's own check read, in how many of the readings that recorded it.
                    "check": {"readings": row["checked"], **{b: row["check"][b] for b in _CONTEXT if row["check"][b]}},
                    **{k: summed[k] for k in ("findings", "ingestion", "review", "unobserved", "ingestionThroughFields", "lens")}, "codes": codes})
    caveats = list(BASIS_CAVEATS)
    stale = totals["readings"] - totals["observed"]
    if stale:
        caveats.append(f"{stale} readings were stored before the basis was recorded; jason models reads them again.")
    return {"found": bool(out), "readings": totals["readings"], "observed": totals["observed"], "asOf": dict(sorted(as_of.items())),
            "totals": {k: totals[k] for k in ("findings", "ingestion", "review", "unobserved", "ingestionThroughFields")},
            # Of the reviews: how many each lens made. The rest are still made inside a reader's own check.
            "byLens": dict(sorted(by_lens.items())), "reviewInReaders": totals["review"] - totals["lens"],
            # How many readers' own check read each part of the context, of the readers whose rows record what it read.
            "checkReads": {"readers": sum(1 for r in out if r["check"]["readings"]),
                           **{b: sum(1 for r in out if r["check"].get(b)) for b in _CONTEXT}},
            "byBasis": dict(sorted(by_basis.items(), key=lambda kv: (-kv[1], kv[0]))),
            "fieldsFromContext": [{"reader": r["reader"], "readings": r["observed"], **r["fields"]} for r in out if r["fields"]],
            "fieldsEnriched": [{"reader": r["reader"], **r["enriched"]} for r in out if r["enriched"]["fields"]],
            "fieldsFromLens": [{"reader": r["reader"], "fields": r["lensFields"]} for r in out if r["lensFields"]],
            "readers": out, "caveats": caveats}


def parts(row: dict[str, Any]) -> dict[str, Any]:
    """A stored row taken apart by where each part came from.

    ``ingestion`` is what rests on the document: the fields ``parse`` filled, and the findings whose basis is the text
    alone. ``enriched`` is the fields an enrichment looked up in another store. ``lens`` is each lens's findings and the
    fields it derived. ``other`` is the findings a reader's own check still makes from the profile, a store, the date, or
    the law. (``fieldsBasis`` still says whether the parse itself read the profile.)"""
    fields = row.get("fields") if isinstance(row.get("fields"), dict) else {}
    looked_up = set((row.get("enriched") or {}).get("fields") or ())
    derived = {lens: set(stamp.get("fields") or ()) for lens, stamp in (row.get("lenses") or {}).items()}
    outside = looked_up | {name for names in derived.values() for name in names}
    findings = row.get("findings") or []
    return {"ingestion": {"fields": {k: v for k, v in fields.items() if k not in outside},
                          "findings": [f for f in findings if not f.get("lens") and f.get("basis") == [Basis.TEXT.value]]},
            "enriched": {k: v for k, v in fields.items() if k in looked_up},
            "lens": {lens: {"fields": {k: v for k, v in fields.items() if k in names},
                            "findings": [f for f in findings if f.get("lens") == lens]} for lens, names in derived.items()},
            "other": [f for f in findings if not f.get("lens") and f.get("basis") != [Basis.TEXT.value]]}


def basis_lines(result: dict[str, Any]) -> list[str]:
    t = result["totals"]
    lenses = "; ".join(f"{n} by the {lens} lens" for lens, n in result.get("byLens", {}).items())
    split = f" ({lenses}; {result.get('reviewInReaders', t['review'])} in the readers' own checks)" if lenses else ""
    out = [f"{result['readings']} readings by {len(result['readers'])} readers ({result['observed']} with an observed basis); "
           f"{t['findings']} findings: {t['ingestion']} ingestion (the text only), {t['review']} review{split}, {t['unobserved']} not observed"]
    if t["ingestionThroughFields"]:
        out.append(f"  {t['ingestionThroughFields']} of the ingestion findings are on readings whose fields read the profile, a store, or today")
    reads = result.get("checkReads") or {}
    if reads.get("readers"):
        out.append(f"  readers whose own check read: the specification {reads['profile']}, a store {reads['store']}, today {reads['today']} "
                   f"(of {reads['readers']} readers whose rows record it)")
    if result["byBasis"]:
        out.append("  by basis: " + "; ".join(f"{basis} {n}" for basis, n in result["byBasis"].items()))
    if result["asOf"]:
        out.append("  as of: " + ", ".join(f"{day} ({n})" for day, n in result["asOf"].items()))
    out += ["", "Readers whose fields depend on context (what parse read, in how many readings):",
            f"  {'reader':<34} {'readings':>8} {'profile':>8} {'store':>6} {'today':>6}"]
    out += [f"  {r['reader']:<34} {r['readings']:>8} {r.get('profile', 0):>8} {r.get('store', 0):>6} {r.get('today', 0):>6}"
            for r in result["fieldsFromContext"]] or ["  (none)"]
    if result.get("fieldsEnriched"):
        out += ["", "Fields an enrichment fills after the parse, from another store (what it read, in how many readings):"]
        out += [f"  {r['reader']:<34} {', '.join(r['fields'])}: " + ", ".join(f"{b} {r[b]}" for b in _CONTEXT if r.get(b))
                for r in result["fieldsEnriched"]]
    if result.get("fieldsFromLens"):
        out += ["", "Fields a lens derives as of its date, not the parse:"]
        out += [f"  {r['reader']:<34} {', '.join(r['fields'])}" for r in result["fieldsFromLens"]]
    out += ["", "Findings by reader and code (basis: every part any call read; always: the parts every call read):"]
    for r in result["readers"]:
        version = f" version {', '.join(r['versions'])}" if r["versions"] else ""
        by_lens = f" ({r['lens']} by a lens)" if r.get("lens") else ""
        out += ["", f"{r['reader']} ({', '.join(r['kinds'])}){version}: {r['readings']} readings; {r['findings']} findings: "
                    f"{r['ingestion']} ingestion, {r['review']} review{by_lens}" + (f", {r['unobserved']} not observed" if r["unobserved"] else ""),
                f"  {'code':<40} {'count':>5} {'text only':>9}  {'class':<12}  basis"]
        for c in r["codes"]:
            always = "" if c["always"] == c["basis"] else f" (always: {', '.join(c['always'])})"
            out.append(f"  {c['code']:<40} {c['count']:>5} {c['textOnly']:>9}  {c['class']:<12}  {', '.join(c['basis'])}{always}")
    out += [""] + [f"Note: {c}" for c in result["caveats"]]
    return out


def coverage_lines(result: dict[str, Any]) -> list[str]:
    out = [f"{result['read']} of {result['files']} library files read by a document model", "",
           f"  {'kind':<30} {'files':>5} {'text':>5} {'read':>5} {'complete':>8}  findings"]
    for r in result["kinds"]:
        mark = "" if r["modeled"] else "  (no model)"
        findings = ", ".join(f"{k} {v}" for k, v in sorted(r["findings"].items()))
        out.append(f"  {r['kind']:<30} {r['files']:>5} {r.get('text', 0):>5} {r.get('read', 0):>5} {r.get('complete', 0):>8}  {findings}{mark}")
    return out


__all__ = ["run", "run_filed", "filed", "filed_lines", "filed_text", "local_copies", "outside_library", "read_file", "load", "coverage",
           "summary", "coverage_lines", "text_sha", "provenance", "basis_report", "basis_lines", "parts", "BASIS_CAVEATS",
           "FILED_SOURCE", "LOCK", "STORE"]
