"""The reading back after a pick (docs/record-intake.md, "What happens after a pick", steps 1 to 6): a person has named a file
for a slot, and now a person asks jason to read it and say what it found.

``read`` is one function behind ``jason records --read KEY`` and the console's job. For a slot's pinned file it:

1. **fetches** the bytes into jason's own store, and only when told (``dry_run=False``, a person's ``--yes``): a dry run says
   what it would fetch and how big it is, and fetches nothing. A Drive file is downloaded (a Google Doc is exported as a
   Word file; the Doc stays the original) into ``data/record-intake/<profile>/fetched/<hash>/``. A file already under
   ``data/`` or in the library is read where it is;
2. **ingests** that one file with the library's own steps (``jason.tasks.ingest``): the hash, the words (a text layer, OCR as
   configured), and the classification chain (a person's earlier answer, the kind rules, the phrase rules). It is not filed
   into the library: a reading is not a filing;
3. **compares** the kind with the slot's. A file that reads as another kind is a **wrong-slot** finding, never silently
   accepted, with the slots it fits;
4. for a PDF, adds ``jason preflight``'s facts (blank pages, text-layer quality) and ``jason segments``'s rule pass, so a
   combined scan **proposes** several slots (a split for a person to confirm; nothing is pinned, no other slot is filled);
5. records the reading beside the pin (``data/record-intake/<profile>/readings/<pin>.json``) with the readers and the tiers
   (likely: two readers agree; suggested: one; conflict: they disagree), and a history line with no file name.

It is idempotent by the file's hash: the same bytes are not read twice, and Drive is not asked for them again while its modified
time and size are the same. A changed file marks the pin changed and shows a diff of facts (counts, kinds), never of text. The
original is never changed. Reads Drive (metadata, and the bytes under ``--yes``) and writes only jason's own stores.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason import limits
from jason.community.record_slots import Pin, PinKind, Reading, Slot
from jason.google.drive import DOCX_MIME_TYPE, FOLDER_MIME_TYPE, GOOGLE_DOC_MIME_TYPE
from jason.tasks import record_slots as rs

log = logging.getLogger(__name__)

FOLDER = "record-intake"
TIERS = ("likely", "suggested", "conflict")
CAVEATS = (
    "A reading is jason's, not a finding of law: a kind is a suggestion until a person confirms it, and a combined scan's "
    "split is a proposal that fills nothing.",
    "Reading copies a Drive file into jason's own store at a person's request; the file in Drive is not touched, and the "
    "original here is never changed.",
)
META_FIELDS = "id,name,mimeType,size,modifiedTime,md5Checksum"


def folder(root: Path, profile: str) -> Path:
    return Path(root) / FOLDER / profile


def reading_path(root: Path, profile: str, pin_id: str) -> Path:
    safe = "".join(ch for ch in str(pin_id) if ch.isalnum() or ch in "-_")
    return folder(root, profile) / "readings" / f"{safe}.json"


def load(root: Path, profile: str, pin_id: str) -> dict[str, Any] | None:
    try:
        data = json.loads(reading_path(root, profile, pin_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save(root: Path, profile: str, pin_id: str, record: dict[str, Any]) -> Path:
    """One reading, written whole beside the pin, under the store's lock."""
    from jason.locks import Resource, hold

    path = reading_path(root, profile, pin_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, f"record-readings-{profile}", timeout=60, purpose="record read-back"):
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return path


def reading_for(root: Path, profile: str, pin_id: str) -> Reading | None:
    """The reading a read-back kept for a pin, as the slot's state machine takes it; None when it was never read."""
    rec = load(root, profile, pin_id)
    if rec is None:
        return None
    return Reading(True, str(rec.get("name") or ""), rec.get("kind") or None, bool(rec.get("confidential")),
                   bool((rec.get("text") or {}).get("chars")), str(rec.get("personBy") or ""), str(rec.get("personOn") or ""),
                   str(rec.get("libraryId") or ""), str(rec.get("method") or ""))


def copy_reading(root: Path, profile: str, old_pin: str, new_pin: str, slot_key: str) -> bool:
    """A repinned file keeps its reading: the record is copied to the new pin (the old one stays in the trail)."""
    rec = load(root, profile, old_pin)
    if rec is None:
        return False
    save(root, profile, new_pin, {**rec, "pin": new_pin, "slot": slot_key, "movedFrom": old_pin})
    return True


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# What the reading shows ------------------------------------------------------------------------------------------------------

def _tier(readers: dict[str, str | None], person: bool) -> str:
    """likely when two readers name the same kind, suggested when one does, conflict when they name different kinds; a
    person's own answer is theirs. "" when no reader named a kind: a miss stays a miss."""
    if person:
        return "confirmed by a person"
    kinds = [k for k in readers.values() if k]
    if not kinds:
        return ""
    if len(set(kinds)) > 1:
        return "conflict"
    return "likely" if len(kinds) >= 2 else "suggested"


def detail(root: Path, profile: str, pin_id: str, *, private: bool) -> dict[str, Any] | None:
    """What a read-back kept for a pin, for the slot's page: the readers and tier, the file's facts, the preflight and
    segment facts, the split proposal, and a change since the last read. A confidential file's names are held back outside
    the private view. None when it was never read."""
    rec = load(root, profile, pin_id)
    if rec is None:
        return None
    held = bool(rec.get("confidential")) and not private
    segments = rec.get("segments") or None
    if segments and held:
        segments = {**segments, "proposal": [{**p, "title": ""} for p in segments.get("proposal") or ()]}
    return {
        "readAt": rec.get("readAt", ""), "readBy": rec.get("by", ""), "sha256": str(rec.get("sha256") or "")[:12],
        "size": rec.get("size"), "type": rec.get("type", ""), "readers": rec.get("readers") or {}, "method": rec.get("method", ""),
        "tier": rec.get("tier", ""), "readsAs": rec.get("kind") or None, "period": rec.get("period", ""),
        "text": rec.get("text") or {}, "alreadyFiled": bool(rec.get("libraryId")),
        "preflight": rec.get("preflight"), "segments": segments, "findings": [] if held else rec.get("findings") or [],
        "changed": _open_change(rec), "acknowledged": (rec.get("lastChange") or {}).get("ack"),
        "split": _split_state(rec), "history": [{"at": h.get("at"), "sha256": str(h.get("sha256") or "")[:12]}
                                                      for h in rec.get("history") or ()],
        "held": held,
    }


def _open_change(rec: dict[str, Any]) -> dict[str, Any] | None:
    """The changed mark, until a person acknowledges it (it then stays on the reading as history)."""
    mark = rec.get("lastChange")
    return mark if mark and not mark.get("ack") else None


def _split_state(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Where a combined scan's proposal stands: which parts a person confirmed (and into which slot), or declined."""
    seg = rec.get("segments") or {}
    if not seg.get("proposes"):
        return None
    done = rec.get("split") or {}
    parts = [p["segment"] for p in seg.get("proposal") or ()]
    confirmed = done.get("confirmed") or {}
    return {"parts": len(parts), "confirmed": [{"segment": k, "slot": v.get("slot"), "by": v.get("by"), "at": str(v.get("at") or "")[:10]}
                                               for k, v in confirmed.items()],
            "declined": done.get("declined") and {"by": done["declined"].get("by"), "at": str(done["declined"].get("at") or "")[:10]},
            "open": not done.get("declined") and any(k not in confirmed for k in parts)}


def _facts(rec: dict[str, Any]) -> dict[str, Any]:
    pre = rec.get("preflight") or {}
    seg = rec.get("segments") or {}
    return {"size": rec.get("size"), "kind": rec.get("kind") or "", "tier": rec.get("tier") or "",
            "text characters": (rec.get("text") or {}).get("chars", 0), "pages": pre.get("pages"), "blank pages": pre.get("blank"),
            "documents in the file": seg.get("documents")}


def diff_facts(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """What differs between two readings, as facts (counts and kinds), never as text."""
    a, b = _facts(before), _facts(after)
    return [{"fact": k, "before": a[k], "after": b[k]} for k in b if a.get(k) != b[k]]


# Fetch ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Fetched:
    path: Path
    name: str
    sha256: str
    size: int
    modified: str
    exported: bool = False


def _meta(drive: Any, ref: str) -> dict[str, Any]:
    return drive.file_metadata(ref, META_FIELDS)


def _stage(root: Path, profile: str, name: str, data: bytes) -> tuple[Path, str]:
    import hashlib

    from jason.community.key_documents import safe_name

    digest = hashlib.sha256(data).hexdigest()
    target = folder(root, profile) / "fetched" / digest[:16] / safe_name(name)
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, target)
    return target, digest


def _fetch(drive: Any, ref: str, meta: dict[str, Any], root: Path, profile: str) -> Fetched:
    """The bytes of a Drive file into jason's store (a Doc exported as a Word file). The only call that moves bytes; it never
    writes to Drive."""
    mime = str(meta.get("mimeType") or "")
    name = str(meta.get("name") or ref)
    if mime == GOOGLE_DOC_MIME_TYPE:
        data = drive.export_file(ref, DOCX_MIME_TYPE)
        name = name if name.lower().endswith(".docx") else name + ".docx"
        exported = True
    else:
        data = drive.download_bytes(ref)
        exported = False
    path, digest = _stage(root, profile, name, data)
    return Fetched(path, name, digest, len(data), str(meta.get("modifiedTime") or ""), exported)


def _problem(meta: dict[str, Any]) -> str:
    """Why a Drive file is not fetched, or ""."""
    mime = str(meta.get("mimeType") or "")
    if mime == FOLDER_MIME_TYPE:
        return "that is a folder; bind it instead (jason records --bind)"
    if mime.startswith("application/vnd.google-apps.") and mime != GOOGLE_DOC_MIME_TYPE:
        return "that file type has no document for jason to read; upload an exported PDF or Word file"
    try:
        size = int(meta.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    try:
        limits.check("fetch.max_bytes", size)
    except limits.LimitReached as over:
        return over.words
    return ""


# Preflight and segments ----------------------------------------------------------------------------------------------------

def preflight_facts(path: Path, root: Path, *, text_quality: bool = True) -> dict[str, Any]:
    """``jason preflight``'s facts for one PDF: pages, blank and marked pages, how many have a text layer, the layer's
    suspect share when a word list can score it, and what to do. Facts only; the original is never changed."""
    from jason.community import pdf_preflight as pf

    lexicon = None
    if text_quality:
        try:
            from jason.tasks.ocr_correct import lexicon_for

            lexicon = lexicon_for(root)
            if not getattr(lexicon, "total", 1):
                lexicon = None
        except Exception:  # noqa: BLE001 - no word list: the share is left unscored
            lexicon = None
    facts = pf.inspect_pdf(path, lexicon=lexicon, osd=False, media=False)
    if facts.locked:
        return {"pages": 0, "locked": True, "recommend": [], "note": "the PDF needs a password; jason does not open it"}
    share = facts.share()
    return {
        "pages": len(facts.pages), "blank": facts.count(pf.Blank.BLANK), "marked": facts.count(pf.Blank.MARKED),
        "content": facts.count(pf.Blank.CONTENT), "withText": sum(1 for p in facts.pages if p.text_chars > 0),
        "suspectShare": None if share is None else round(share, 3), "encrypted": facts.encrypted, "locked": False,
        "recommend": [{"action": r.action.value, "pages": pf.ranges(r.pages), "reason": r.reason} for r in pf.recommend(facts)],
    }


def segments_facts(path: Path, root: Path, community: Any, segmenter: Callable[..., Any] | None, slots: tuple[Slot, ...],
                   held_slots: set[str], current: str) -> dict[str, Any]:
    """``jason segments``'s rule pass over one PDF (no model), turned into a proposal: each document found, its pages, its kind,
    its tier, and the slots its kind fits. It fills nothing and pins nothing; a person confirms a split."""
    from jason.tasks import segments as task

    run = segmenter or task.segment_file
    seg = run(path, doc_id=task.file_id(path), data_dir=root, community=community, accept="rules", write=True)
    fits: dict[str, list[Slot]] = {}
    for s in slots:
        for k in s.kinds:
            fits.setdefault(k.value, []).append(s)
    top = [s for s in seg.segments if not getattr(s, "parent", "")]
    proposal = []
    for s in top:
        fitting = fits.get(s.kind, []) if s.kind else []
        proposal.append({
            "segment": s.key, "pages": [s.start, s.end], "title": " ".join(str(s.title or "").split())[:80],
            "kind": s.kind or None, "tier": s.tier.value, "readers": [r.value for r in s.readers], "date": s.date,
            "slots": [{"key": f.key, "title": f.title, "held": f.key in held_slots, "current": f.key == current} for f in fitting],
            "confirmed": False})
    distinct = {x["key"] for p in proposal for x in p["slots"]}
    return {"documents": len(seg.segments), "parts": len(getattr(seg, "parts", ()) or ()), "pageCount": seg.page_count,
            "readers": [k for k in seg.readers if not k.endswith("Seconds")],
            "proposes": len(top) > 1 or len(distinct) > 1, "proposal": proposal,
            "note": "A proposal only: no slot is filled until a person confirms the split."}


# The read ------------------------------------------------------------------------------------------------------------------

def _shown(name: str, kind: str | None, confidential: bool, private: bool) -> str:
    if confidential and not private:
        return f"a confidential file (kind: {(kind or 'unclassified').replace('_', ' ')})"
    return name


def _wrong_slot(slot: Slot, kind: str | None, slots: tuple[Slot, ...]) -> dict[str, Any] | None:
    expected = [k.value for k in slot.kinds]
    if not kind or not expected or kind in expected:
        return None
    return {"readsAs": kind, "expects": expected,
            "fits": [{"key": s.key, "title": s.title} for s in slots if s.key != slot.key and kind in {k.value for k in s.kinds}],
            "acts": ["repin", "keep", "unpin"]}


def _local_source(root: Path, profile: str, pin: Pin, library: rs.Library) -> tuple[Path | None, str]:
    """Where a file that needs no fetch already is: under ``data/`` (an upload or a key-documents file) or in the library."""
    if pin.kind is PinKind.FILE:
        target = (Path(root) / pin.ref).resolve()
        if target.is_file() and target.is_relative_to(Path(root).resolve()):
            return target, ""
        return None, "the file is not on this machine"
    if pin.kind is PinKind.LIBRARY:
        row = library.by_id.get(pin.ref)
        if row is None:
            return None, "the library does not hold that file"
        found = Path(root) / "library" / "files" / str(row.get("path") or "")
        if found.is_file():
            return found, ""
        mirror = next((m for m in [Path(root) / f for f in ("artifacts/site-docs", "governing", "insurance-pdfs", "reserve-studies", "dre")]
                       if (m / str(row.get("name") or "")).is_file()), None)
        return ((mirror / str(row.get("name"))) if mirror is not None else None), ("" if mirror is not None else
                                                                                   "the library row has no file on this machine")
    return None, ""


def _name_kind(community: Any, name: str) -> str | None:
    try:
        found = community.classify_document(name, None, name) if community is not None else None
    except Exception:  # noqa: BLE001 - a rule that cannot answer is a miss
        return None
    return getattr(found, "value", None)


def _read_one(slot: Slot, pin: Pin, computed: list[rs.Computed], *, community: Any, root: Path, profile: str, by: str, drive: Any,
              dry_run: bool, ocr: bool, force: bool, text_quality: bool, segmenter: Callable[..., Any] | None,
              preflighter: Callable[..., Any] | None, private: bool) -> dict[str, Any]:
    from jason.community.content import classify_text
    from jason.tasks import ingest as ing
    from jason.tasks.library import load as load_library, person_kinds

    library = rs.Library(root)
    prior = load(root, profile, pin.id)
    out: dict[str, Any] = {"pin": pin.id, "slot": slot.key, "source": pin.kind.value}
    path: Path | None = None
    fetched: Fetched | None = None
    meta: dict[str, Any] = {}
    if pin.kind is PinKind.DRIVE:
        if drive is None and not dry_run:
            from jason.tasks.drive_choose import NOT_SIGNED_IN, DriveUnavailable

            raise DriveUnavailable(NOT_SIGNED_IN, "jason google sign-in --name drive --interactive")
        if drive is not None:
            try:
                meta = _meta(drive, pin.ref)
            except Exception as exc:  # noqa: BLE001 - a Google refusal is an answer, told without its text
                from jason.tasks.drive_choose import refusal_words

                return {**out, "ok": False, "problem": refusal_words(exc), "fetched": False}
        else:
            known = library.drive.get(pin.ref) or {}
            meta = {"name": known.get("name") or pin.name, "mimeType": known.get("mimeType") or "", "size": known.get("size"),
                    "modifiedTime": known.get("modifiedTime") or ""}
            if dry_run:
                out["note"] = "Drive is not connected, so the size comes from the last catalog read (it may be missing)."
        why = _problem(meta) if meta else ""
        if why:
            return {**out, "ok": False, "problem": why, "fetched": False}
        name = str(meta.get("name") or pin.name or "a file")
        size = rs_int(meta.get("size"))
        unchanged = bool(prior is not None and not force and prior.get("modified")
                         and prior.get("modified") == str(meta.get("modifiedTime") or "") and prior.get("driveSize") == size
                         and Path(str(prior.get("stored") or "")).is_file())
        plan = {"name": name, "type": str(meta.get("mimeType") or ""), "size": size,
                "export": "a Word copy (the Doc stays the original)" if meta.get("mimeType") == GOOGLE_DOC_MIME_TYPE else "",
                "willFetch": not unchanged}
        out["plan"] = {**plan, "name": _shown(name, (prior or {}).get("kind"), bool((prior or {}).get("confidential")), private)}
        if dry_run:
            out.update({"ok": True, "dryRun": True, "fetched": False, "reads": "the file, in jason's store: hash, text, kind, "
                        "preflight and segment facts" if not unchanged else "nothing new: the file is unchanged since the last read"})
            return out
        if unchanged:
            path = Path(str(prior["stored"]))
            out["unchanged"] = True
        else:
            fetched = _fetch(drive, pin.ref, meta, root, profile)
            path = fetched.path
    else:
        path, why = _local_source(root, profile, pin, library)
        if path is None:
            return {**out, "ok": False, "problem": why or "there is no file here for jason to read", "fetched": False}
        out["plan"] = {"name": _shown(path.name, (prior or {}).get("kind"), bool((prior or {}).get("confidential")), private),
                       "size": path.stat().st_size, "willFetch": False}
        if dry_run:
            out.update({"ok": True, "dryRun": True, "fetched": False, "reads": "the file where it is: hash, text, kind, preflight "
                        "and segment facts"})
            return out
    # --- ingest the one file, as jason ingest does, without filing it ---
    items, _ = ing.inventory([str(path)], root)
    item = items[0]
    hashed_same = prior is not None and prior.get("sha256") == item.sha256
    if hashed_same and not force and prior.get("version") == 1:
        out.update({"ok": True, "fetched": fetched is not None, "unchanged": True, "reused": True, "reading": prior})
        return _finish(out, prior, slot, computed, private)
    text = ing.read_text(item, root, ocr=ocr)
    chosen = person_kinds(root)
    if item.library_id:
        rows = {str(r["id"]): r for r in load_library(root)}
        ing._from_library(item, rows)
        row_method, evidence = item.method, item.evidence
    else:
        row, _answer = ing.classify(community, item, text, model=None, chosen=chosen, state={})
        ing._take(item, row)
        row_method, evidence = item.method, item.evidence
    name_kind = _name_kind(community, item.name)
    phrase = classify_text(text)[0] if text.strip() else None
    readers = {"name rule": name_kind, "phrase rule": getattr(phrase, "value", None)}
    person = row_method == "PERSON"
    tier = _tier(readers, person)
    by_person, _, on = evidence.removeprefix("chosen by ").partition(" on ") if person and evidence.startswith("chosen by ") else ("", "", "")
    findings: list[dict[str, str]] = []
    if item.library_id:
        findings.append({"code": "in the library", "text": "the library already holds these bytes; its classification is used"})
    if not text.strip():
        findings.append({"code": "no text", "text": f"no words were read ({item.text_source or 'no reader'}); the kind rests on the name alone"})
    kind = item.kind or None
    if not kind:
        findings.append({"code": "unclassified", "text": "jason could not tell what this is; it stays unclassified until a person says"})
    if tier == "conflict":
        findings.append({"code": "readers disagree", "text": "the name and the words point to different kinds: "
                         + ", ".join(f"{k} reads {v.replace('_', ' ')}" for k, v in readers.items() if v)})
    slots = rs.assemble(community).slots
    wrong = _wrong_slot(slot, kind, slots)
    if wrong:
        findings.append({"code": "wrong slot", "text": f"jason reads this as {kind.replace('_', ' ')}; the slot expects "
                         + " or ".join(k.replace('_', ' ') for k in wrong["expects"])})
    pre = seg = None
    if path.suffix.lower() == ".pdf":
        try:
            pre = preflighter(path, root) if preflighter is not None else preflight_facts(path, root, text_quality=text_quality)
        except Exception as exc:  # noqa: BLE001 - a failed step is named and the others shown
            findings.append({"code": "preflight failed", "text": f"preflight could not read the PDF ({type(exc).__name__})"})
        if pre and pre.get("blank"):
            findings.append({"code": "blank pages", "text": f"{pre['blank']} blank page(s), kept in the original"})
        if pre and (pre.get("suspectShare") or 0) > 0.03:
            findings.append({"code": "text layer doubtful", "text": "the scanner's text layer reads poorly in places; read again from the rendition"})
        held_slots = {c.slot.key for c in computed if c.holders}
        try:
            seg = segments_facts(path, root, community, segmenter, slots, held_slots, slot.key)
        except Exception as exc:  # noqa: BLE001
            findings.append({"code": "segments failed", "text": f"the segment pass could not read the PDF ({type(exc).__name__})"})
        if seg and seg["proposes"]:
            findings.append({"code": "combined scan", "text": f"the file holds {seg['documents']} documents; a split is proposed for a person to confirm"})
    if fetched is not None and fetched.exported:
        findings.append({"code": "exported", "text": "a Google Doc: jason keeps a Word copy; the Doc stays the original"})
    record: dict[str, Any] = {
        "version": 1, "pin": pin.id, "slot": slot.key, "name": item.name, "sha256": item.sha256, "size": item.size,
        "type": item.type, "stored": str(path), "modified": str(meta.get("modifiedTime") or ""), "driveSize": rs_int(meta.get("size")),
        "readAt": _now(), "by": by, "text": {"source": item.text_source, "chars": item.text_chars},
        "kind": kind, "method": row_method, "readers": readers, "tier": tier, "period": item.period,
        "category": item.category, "records": list(item.records), "confidential": bool(item.confidential),
        "libraryId": item.library_id, "personBy": by_person.split(":")[0].strip() if person else "",
        "personOn": on.split(":")[0].strip() if person else "",
        "compare": {"verdict": ("unclassified" if not kind else "differs" if wrong else "agrees"), "expects": [k.value for k in slot.kinds]},
        "preflight": pre, "segments": seg, "findings": findings,
        "history": [*(prior.get("history") if prior else []), {"at": _now(), "sha256": item.sha256}],
    }
    if prior is not None and prior.get("sha256") == item.sha256 and prior.get("split"):
        record["split"] = prior["split"]
        for old in (prior.get("segments") or {}).get("proposal") or ():
            for new in (record.get("segments") or {}).get("proposal") or ():
                if new["segment"] == old["segment"] and old.get("confirmed"):
                    new["confirmed"], new["confirmedBy"] = True, old.get("confirmedBy", "")
    if prior is not None and prior.get("sha256") != item.sha256:
        record["lastChange"] = {"at": _now(), "from": str(prior.get("sha256") or "")[:12], "to": item.sha256[:12],
                                "diff": diff_facts(prior, record)}
        findings.append({"code": "changed", "text": "the file changed since the last read: " + ", ".join(
            d["fact"] for d in record["lastChange"]["diff"]) if record["lastChange"]["diff"] else "the file's bytes changed since the last read"})
    elif prior is not None and prior.get("lastChange"):
        record["lastChange"] = prior["lastChange"]
    save(root, profile, pin.id, record)
    out.update({"ok": True, "fetched": fetched is not None, "unchanged": False, "reading": record})
    return _finish(out, prior, slot, computed, private)


def rs_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _finish(out: dict[str, Any], prior: dict[str, Any] | None, slot: Slot, computed: list[rs.Computed], private: bool) -> dict[str, Any]:
    """The four lines every pick gets: you picked X for Y; jason read it as Z, by which readers; what it found; what you
    confirm. A confidential file's name is held back outside the private view."""
    rec = out.pop("reading")
    held = bool(rec.get("confidential")) and not private
    kind = rec.get("kind")
    name = _shown(str(rec.get("name") or ""), kind, bool(rec.get("confidential")), private)
    verdict = ("unclassified" if not kind else "differs" if kind not in [k.value for k in slot.kinds] and slot.kinds else "agrees")
    out["picked"] = {"for": slot.title, "file": name}
    out["readAs"] = {"kind": kind, "tier": rec.get("tier") or None, "readers": rec.get("readers") or {}, "method": rec.get("method", "")}
    out["compare"] = {"verdict": verdict, "expects": [k.value for k in slot.kinds],
                      "wrongSlot": _wrong_slot(slot, kind, tuple(c.slot for c in computed)) if verdict == "differs" else None}
    out["found"] = [] if held else list(rec.get("findings") or [])
    out["preflight"] = rec.get("preflight")
    segs = rec.get("segments")
    if segs and held:
        segs = {**segs, "proposal": [{**p, "title": ""} for p in segs.get("proposal") or ()]}
    out["segments"] = segs
    out["changed"] = _open_change(rec)
    out["confirm"] = ("Say whether this file belongs here: keep it in this slot, move it to the slot it fits, or unpin it. "
                      "A combined scan's split fills no slot until you confirm it." if verdict == "differs" else
                      "Confirm the kind (jason intake) if the reading is right; jason reads, a person confirms.")
    out["held"] = held
    return out


def read(slot_key: str, *, pin: str = "", by: str = "", dry_run: bool = True, drive: Any = None, ocr: bool = True,
         force: bool = False, text_quality: bool = True, segmenter: Callable[..., Any] | None = None,
         preflighter: Callable[..., Any] | None = None, private: bool = False, community: Any = None, root: Path | None = None,
         profile: str | None = None) -> dict[str, Any]:
    """Read the file(s) pinned for a slot (see the module). ``dry_run`` (the default) says what would be fetched and how big it
    is and fetches nothing. With ``dry_run=False`` a person's name is required (``by``); the bytes are fetched once into jason's
    store, read, compared with the slot, and the reading is kept beside the pin. ``drive`` is a Drive client the caller opens
    (never a browser)."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    who = rs._who(by) if not dry_run else " ".join(str(by or "").split())
    computed = rs.compute(community, root, profile)
    found = next((c for c in computed if c.slot.key == slot_key), None)
    if found is None:
        raise KeyError(slot_key)
    pins = [h for h in found.holders if h.kind is not PinKind.FOLDER and (not pin or h.id == pin)]
    if pin and not pins:
        raise ValueError(f"{slot_key} has no active pin {pin}")
    if not pins:
        return {"dryRun": dry_run, "ok": False, "slot": slot_key, "reads": [],
                "note": f"{slot_key} holds no pinned file to read (pick one first: jason records --pick)", "caveats": list(CAVEATS)}
    reads = []
    for p in pins:
        reads.append(_read_one(found.slot, p, computed, community=community, root=root, profile=profile, by=who, drive=drive,
                               dry_run=dry_run, ocr=ocr, force=force, text_quality=text_quality, segmenter=segmenter,
                               preflighter=preflighter, private=private))
    if not dry_run:
        for r in reads:
            if r.get("ok"):
                rs._append_history(root, {"at": _now(), "profile": profile, "act": "read", "slot": slot_key, "pin": r["pin"],
                                          "by": who, "fetched": bool(r.get("fetched")), "unchanged": bool(r.get("unchanged")),
                                          "verdict": (r.get("compare") or {}).get("verdict", "")})
        log.info("record read: slot=%s pins=%d fetched=%d", slot_key, len(reads), sum(1 for r in reads if r.get("fetched")))
    return {"dryRun": dry_run, "ok": all(r.get("ok") for r in reads), "slot": slot_key, "reads": reads,
            "note": ("A dry run: nothing was fetched or read. Add --yes to fetch the file into jason's store and read it."
                     if dry_run else "Read. jason found and suggests; a person confirms."), "caveats": list(CAVEATS)}


# The confirmations queue ---------------------------------------------------------------------------------------------------

def queue_items(community: Any = None, root: Path | None = None, profile: str | None = None, *, private: bool = False) -> dict[str, Any]:
    """The "record reading" items for the confirmations queue (docs/console/handoff-confirmations-queue.md, a fourth kind):
    a pick that reads as another kind than its slot's (until a person keeps, moves, or unpins it), and a combined scan whose
    split nobody has confirmed. Each says in words what it needs and names the acts. A held file is named by kind only."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    computed = rs.compute(community, root, profile)
    items: list[dict[str, Any]] = []
    today = datetime.now(timezone.utc).date()
    for c in computed:
        for st in c.statuses:
            rec = load(root, profile, st.pin.id)
            if rec is None:
                continue
            held = bool(rec.get("confidential")) and not private
            at = str(rec.get("readAt") or "")[:10]
            try:
                age = f"{(today - datetime.fromisoformat(at).date()).days} d" if at else ""
            except ValueError:
                age = ""
            base = {"kind": "record reading", "slot": c.slot.key, "pin": st.pin.id, "title": c.slot.title,
                    "proposed": at, "age": age, "route": "#/onboarding/records/" + rs.quote(c.slot.key, safe=""), "held": held,
                    "command": f"jason records --slot {c.slot.key}"}
            if st.wrong_slot and not st.pin.kept:
                items.append({**base, "id": f"{c.slot.key}#{st.pin.id}", "reason": "wrong slot", "state": "waiting",
                              "needs": f"A person says whether this file belongs in {c.slot.title}: jason reads it as "
                                       f"{(st.reads_as or '').replace('_', ' ')}.",
                              "acts": ["keep", "repin", "unpin"], "readsAs": st.reads_as,
                              "fits": [{"key": s.slot.key, "title": s.slot.title} for s in computed
                                       if s.slot.key != c.slot.key and st.reads_as in {k.value for k in s.slot.kinds}]})
            seg = rec.get("segments") or {}
            state = _split_state(rec)
            if seg.get("proposes") and state and state["open"]:
                items.append({**base, "id": f"{c.slot.key}#{st.pin.id}#split", "reason": "combined scan", "state": "waiting",
                              "needs": f"A person confirms or declines the proposed split ({seg.get('documents')} documents in one file).",
                              "acts": ["split"], "confirmedParts": len(state["confirmed"]), "readsAs": rec.get("kind")})
    items.sort(key=lambda i: (i["proposed"] or "9999", i["id"]))
    return {"found": True, "kind": "record reading", "items": items,
            "counts": {"total": len(items), "wrongSlot": sum(1 for i in items if i["reason"] == "wrong slot"),
                       "split": sum(1 for i in items if i["reason"] == "combined scan")},
            "caveats": ["jason proposes; a person decides. Nothing here is confirmed twice: a wrong-slot pick is also a line on its slot."]}


# The key documents ---------------------------------------------------------------------------------------------------------

def key_document_summary(community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, dict[str, Any]]:
    """For the key documents' checklist: each key-document item's slot (its state and pins) and, per instrument, how many
    files are linked, how many jason has read, and how many read as another kind. Read through the same slot reader the
    Records tab uses, so the two screens cannot disagree. The writer stays the key documents' link."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    out: dict[str, dict[str, Any]] = {}
    for c in rs.compute(community, root, profile):
        if not c.slot.key_document:
            continue
        per: dict[str, dict[str, int]] = {}
        for st in c.statuses:
            row = per.setdefault(st.pin.store_id or c.slot.key_document, {"pins": 0, "read": 0, "wrongSlot": 0, "held": 0})
            row["pins"] += 1
            row["read"] += 1 if st.reading.found else 0
            row["wrongSlot"] += 1 if st.wrong_slot else 0
            row["held"] += 1 if st.held else 0
        out[c.slot.key_document] = {
            "slot": c.slot.key, "state": c.state.value, "stateWord": c.state.word, "pins": len(c.statuses),
            "read": sum(v["read"] for v in per.values()), "wrongSlot": sum(v["wrongSlot"] for v in per.values()),
            "held": c.held, "route": "#/onboarding/records/" + rs.quote(c.slot.key, safe=""), "entries": per}
    return out


__all__ = ["CAVEATS", "Fetched", "copy_reading", "detail", "diff_facts", "key_document_summary", "load", "preflight_facts", "queue_items",
           "read", "reading_for", "reading_path", "save", "segments_facts"]
