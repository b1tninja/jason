"""Read every classified library file with its kind's document model; store the readings and report coverage.

``run`` walks the classified library (``jason library``), reads each file's cached text with the models registered
for its kind (``jason.community.document_models``), and writes ``data/documents/readings.json``: per file its kind,
the model that read it, whether the record is complete, what is missing, the fields, and the findings. ``read_file``
reads one file on disk (a Drive copy the library lacks) the same way. ``coverage`` says, per kind, how many files
there are, how many have text, how many a model read, and how many readings are complete, and lists the kinds no
model reads yet. It reads disk only.

A confidential library file's fields stay on disk; ``summary`` leaves them out unless asked.

**What a row says about its own making** (docs/ingestion-and-review.md, the inventory). Beside the keys above, a row
carries ``textSha`` (the SHA-256 of the text the reader was given), ``asOf`` (the date the reader used as today),
``version`` (``reader_version`` of the model that read it), ``fieldsBasis`` (what ``parse`` read to fill the fields),
and on each finding ``basis`` (what the call that produced it read). A row written before these keys has none of
them, and every reader of the store treats them as optional. ``basis`` reports, from the stored rows alone, which
findings are ingestion (the text only) and which are reviews.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.document_models import Basis, ModelContext, basis_values, modeled_kinds, read
from jason.community.symbols import DocumentKind

STORE = Path("documents") / "readings.json"


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


def run(data_dir: Path, community: Any, *, kinds: tuple[DocumentKind, ...] = (), today: date | None = None) -> dict[str, Any]:
    """Read the library with the document models and save the readings."""
    from jason.tasks.library import distinct, load, text_for

    data_dir = Path(data_dir)
    today = today or date.today()  # one as-of date for the whole run
    rows = distinct(load(data_dir))
    readings = []
    for row in rows:
        kind = _kind(str(row.get("kind") or ""))
        if kind is None or (kinds and kind not in kinds):
            continue
        text = text_for(data_dir, row["id"])
        entry = {"id": row["id"], "name": row.get("name"), "period": row.get("period"), "kind": kind.value,
                 "confidential": bool(row.get("confidential")), "hasText": bool(text.strip()), "model": None}
        if text.strip():
            entry.update(provenance(text, today))
            context = ModelContext(community, data_dir, today, str(row.get("name") or ""), str(row.get("period") or ""),
                                   bool(row.get("confidential")))
            try:
                reading = read(kind, text, context)
            except Exception as exc:  # one bad file does not stop the run; the error is the finding
                entry["error"] = f"{type(exc).__name__}: {exc}"
                reading = None
            if reading is not None:
                entry.update(reading.as_dict())
        readings.append(entry)
    path = data_dir / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    result = {"readAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "readings": readings}
    if path.is_file():
        # A run over some kinds keeps the other kinds' readings; every run keeps the readings of files read from Drive
        # (``jason.tasks.drive_minutes``), which the library does not hold.
        old = json.loads(path.read_text(encoding="utf-8")).get("readings", [])
        kept = [r for r in old if r.get("source") == "Drive" or (kinds and _kind(r["kind"]) not in kinds)]
        result["readings"] = kept + readings
    path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return coverage(result["readings"])


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
    for r in readings:
        if not r.get("model") or (kind and r.get("kind") != kind):
            continue
        row = readers.setdefault(r["model"], {"reader": r["model"], "kinds": set(), "versions": set(), "readings": 0, "observed": 0,
                                              "fields": Counter(), "codes": {}})
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
        through = [b for b in fields or () if b in _CONTEXT]
        for f in r.get("findings") or []:
            code = row["codes"].setdefault(f["code"], {"code": f["code"], "count": 0, "observed": 0, "textOnly": 0, "throughFields": 0,
                                                       "parts": Counter()})
            code["count"] += 1
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
            c["class"] = "not observed" if not c["observed"] else "ingestion" if c["textOnly"] == c["observed"] else "review"
            codes.append(c)
        summed = Counter()
        for c in codes:
            summed.update({"findings": c["count"], "ingestion": c["textOnly"], "review": c["observed"] - c["textOnly"],
                           "unobserved": c["count"] - c["observed"], "ingestionThroughFields": c["throughFields"]})
        totals.update(summed)
        totals.update({"readings": row["readings"], "observed": row["observed"]})
        out.append({"reader": name, "kinds": sorted(row["kinds"]), "versions": sorted(row["versions"]), "readings": row["readings"],
                    "observed": row["observed"], "fields": {b: row["fields"][b] for b in _CONTEXT if row["fields"][b]},
                    **{k: summed[k] for k in ("findings", "ingestion", "review", "unobserved", "ingestionThroughFields")}, "codes": codes})
    caveats = list(BASIS_CAVEATS)
    stale = totals["readings"] - totals["observed"]
    if stale:
        caveats.append(f"{stale} readings were stored before the basis was recorded; jason models reads them again.")
    return {"found": bool(out), "readings": totals["readings"], "observed": totals["observed"], "asOf": dict(sorted(as_of.items())),
            "totals": {k: totals[k] for k in ("findings", "ingestion", "review", "unobserved", "ingestionThroughFields")},
            "byBasis": dict(sorted(by_basis.items(), key=lambda kv: (-kv[1], kv[0]))),
            "fieldsFromContext": [{"reader": r["reader"], "readings": r["observed"], **r["fields"]} for r in out if r["fields"]],
            "readers": out, "caveats": caveats}


def basis_lines(result: dict[str, Any]) -> list[str]:
    t = result["totals"]
    out = [f"{result['readings']} readings by {len(result['readers'])} readers ({result['observed']} with an observed basis); "
           f"{t['findings']} findings: {t['ingestion']} ingestion (the text only), {t['review']} review, {t['unobserved']} not observed"]
    if t["ingestionThroughFields"]:
        out.append(f"  {t['ingestionThroughFields']} of the ingestion findings are on readings whose fields read the profile, a store, or today")
    if result["byBasis"]:
        out.append("  by basis: " + "; ".join(f"{basis} {n}" for basis, n in result["byBasis"].items()))
    if result["asOf"]:
        out.append("  as of: " + ", ".join(f"{day} ({n})" for day, n in result["asOf"].items()))
    out += ["", "Readers whose fields depend on context (what parse read, in how many readings):",
            f"  {'reader':<34} {'readings':>8} {'profile':>8} {'store':>6} {'today':>6}"]
    out += [f"  {r['reader']:<34} {r['readings']:>8} {r.get('profile', 0):>8} {r.get('store', 0):>6} {r.get('today', 0):>6}"
            for r in result["fieldsFromContext"]] or ["  (none)"]
    out += ["", "Findings by reader and code (basis: every part any call read; always: the parts every call read):"]
    for r in result["readers"]:
        version = f" version {', '.join(r['versions'])}" if r["versions"] else ""
        out += ["", f"{r['reader']} ({', '.join(r['kinds'])}){version}: {r['readings']} readings; {r['findings']} findings: "
                    f"{r['ingestion']} ingestion, {r['review']} review" + (f", {r['unobserved']} not observed" if r["unobserved"] else ""),
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


__all__ = ["run", "read_file", "load", "coverage", "summary", "coverage_lines", "text_sha", "provenance", "basis_report", "basis_lines",
           "BASIS_CAVEATS"]
