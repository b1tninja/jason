"""The record checklist's phase 3 writes (docs/record-intake.md): an upload from the computer, the confirmed split of a
combined scan, and acknowledging a changed file.

Each names its person (``by``; never jason), is a **dry run** unless told otherwise, holds the store's lock, writes only jason's
own stores (``data/spec/<profile>/records.json``, ``data/record-intake/<profile>/``, or the key documents' store for a recorded
instrument), and appends one line to ``data/records/history.jsonl`` that holds the slot, the act, who, and ids, and never a file
name. Nothing here reaches Drive, PayHOA, Google, or the county.

- ``upload``: the bytes of a file a person chose are kept in jason's own store, addressed by their SHA-256
  (``record-intake/<profile>/files/<first 16>/<name>``), after a size cap and a type check (the name's suffix and the file's own
  first bytes must agree: PDF, an image, or a Word file, which is what a Google Doc exports as). The same bytes twice are one copy.
  The file is pinned to the slot (a recorded instrument's slot takes it through the key documents' one writer) and then read back
  exactly as a pick is (``record_readback.read``).
- ``split``: a person confirms parts of a combined scan's proposal. Per part they name the slot it fills. Only the parts named are
  filled; each is a new file of just those pages, kept beside the original, pinned to its slot. A slot that already holds a file,
  or that an earlier part of the same request fills, is a **collision**: shown, and not overwritten. The original scan and its pin
  are not changed. A person may instead decline the proposal.
- ``ack``: a person has seen that a pinned file changed since it was last read; the mark stays in the trail as acknowledged.
"""

from __future__ import annotations

import base64
import hashlib
import io
import os
import secrets
from pathlib import Path
from typing import Any, Callable

from jason import limits
from jason.community.key_documents import key_document, max_upload_bytes, safe_name
from jason.community.record_slots import Cardinality, PinKind
from jason.tasks import record_readback
from jason.tasks import record_slots as rs

UPLOAD_TYPES = (
    (".pdf", "a PDF", (b"%PDF-",)),
    (".png", "a PNG image", (b"\x89PNG\r\n\x1a\n",)),
    (".jpg", "a JPEG image", (b"\xff\xd8\xff",)),
    (".jpeg", "a JPEG image", (b"\xff\xd8\xff",)),
    (".tif", "a TIFF image", (b"II*\x00", b"MM\x00*")),
    (".tiff", "a TIFF image", (b"II*\x00", b"MM\x00*")),
    (".docx", "a Word file (a Google Doc's export)", (b"PK\x03\x04",)),
)
CAVEATS = (
    "An upload is kept in jason's own store and never put in Drive. The original you chose is not changed or moved.",
    "jason reads and suggests; a person confirms the kind, a split, and what stays in a slot.",
)


def _spec(name: str) -> tuple[str, str, tuple[bytes, ...]]:
    suffix = Path(name).suffix.lower()
    found = next((t for t in UPLOAD_TYPES if t[0] == suffix), None)
    if found is None:
        raise ValueError(f"{name}: jason takes a PDF, an image (PNG, JPEG, TIFF), or a Word file; "
                         "export a Google Doc as Word or PDF first")
    return found[0], found[1], found[2]


def cap_for(slot: Any = None, community: Any = None) -> int:
    """The largest upload, the ``upload.max_bytes`` limit. A key document's slot stores through the key documents' writer, so it
    is held to that writer's reading of the same limit as well."""
    cap = int(limits.value("upload.max_bytes", community=community))
    if slot is not None and getattr(slot, "key_document", ""):
        cap = min(cap, max_upload_bytes())
    return cap


def check(name: str, data: bytes, cap: int | None = None) -> tuple[str, str]:
    """The safe name and what the file is, after the cap (``cap``, else the limit) and the type check. The suffix and the first bytes must agree, and a
    Word file must be a Word package. Raises ValueError in words a person can act on."""
    cap = cap if cap is not None else cap_for()
    clean = safe_name(name)
    suffix, what, magics = _spec(clean)
    if not data:
        raise ValueError(f"{clean} is empty")
    if len(data) > cap:
        raise limits.refusal("upload.max_bytes", len(data), cap)
    head = data[:1024] if suffix == ".pdf" else data[:16]
    if not any((m in head) if suffix == ".pdf" else head.startswith(m) for m in magics):
        raise ValueError(f"{clean} does not read as {what}: its contents are something else, so it was not kept")
    if suffix == ".docx":
        import zipfile

        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" not in z.namelist():
                    raise ValueError("no document part")
        except (zipfile.BadZipFile, ValueError) as exc:
            raise ValueError(f"{clean} does not read as {what}: it is not a Word package, so it was not kept") from exc
    return clean, what


def folder(root: Path, profile: str) -> Path:
    return record_readback.folder(root, profile) / "files"


def _keep(root: Path, profile: str, name: str, data: bytes) -> tuple[str, str]:
    """The bytes under ``files/<digest16>/<name>``: the same bytes twice are one copy and nothing is overwritten. Returns the
    path relative to the data folder and the SHA-256."""
    digest = hashlib.sha256(data).hexdigest()
    target = folder(root, profile) / digest[:16] / name
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("a different file is already kept under that address; nothing was written")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, target)
    return target.relative_to(Path(root)).as_posix(), digest


def _bytes(name: str, data: bytes | None, base64_body: str, path: str, cap: int) -> tuple[str, bytes]:
    if path:
        source = Path(path).expanduser()
        if not source.is_file():
            raise ValueError(f"{path}: no such file on this machine")
        if source.stat().st_size > cap:
            raise limits.refusal("upload.max_bytes", source.stat().st_size, cap)
        return name or source.name, source.read_bytes()
    if base64_body:
        if len(base64_body) > (cap // 3 + 2) * 4 + 4:
            raise limits.refusal("upload.max_bytes", len(base64_body) // 4 * 3, cap)
        try:
            raw = base64.b64decode(base64_body.split(",", 1)[-1] if base64_body.startswith("data:") else base64_body, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("the upload is not base64") from exc
        return name, raw
    if data is None:
        raise ValueError("upload needs the file: a path on this machine, or its bytes")
    return name, data


def _entry_key(slot: Any, entry: str) -> str:
    if not slot.key_document:
        return ""
    row = key_document(slot.key_document)
    assert row is not None
    if not row.repeats:
        return row.key
    if not str(entry or "").strip():
        raise ValueError(f"{slot.key} holds recorded instruments, each by its recording number: pass the instrument "
                         f"(--entry NUMBER) so the file goes to {row.key}/NUMBER")
    return f"{row.key}/{str(entry).strip()}"


def upload(slot_key: str, *, by: str, name: str = "", data: bytes | None = None, base64_body: str = "", path: str = "",
           period: str = "", note: str = "", entry: str = "", dry_run: bool = True, read: bool = True, ocr: bool = True,
           segmenter: Callable[..., Any] | None = None, preflighter: Callable[..., Any] | None = None, private: bool = True,
           community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Keep a file from the computer in jason's store and pin it to a slot, then (``read``) read it back as a pick is read. A dry
    run (the default) checks the file and says what it would write; it keeps nothing. ``path`` is for the terminal; the console
    sends ``base64_body``."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    slot, hidden = rs._slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    cap = cap_for(slot, community)
    given, raw = _bytes(name, data, base64_body, path, cap)
    clean, what = check(given, raw, cap)
    when = rs._period(slot, period)
    text = rs._words(note, "note", required=False)
    entry_key = _entry_key(slot, entry)
    digest = hashlib.sha256(raw).hexdigest()
    ref = (folder(root, profile) / digest[:16] / clean).relative_to(Path(root)).as_posix()
    active = rs._active_pins(root, profile, slot_key)
    twin = next((p for p in active if p.kind is PinKind.FILE and f"/{digest[:16]}/" in p.ref), None)
    elsewhere = sorted({c.slot.key for c in rs.compute(community, root, profile) if c.slot.key != slot_key
                        and any(h.kind is PinKind.FILE and f"/{digest[:16]}/" in h.ref for h in c.holders)})
    target = f"key-documents/{profile}.json" if slot.key_document else f"spec/{profile}/{rs.STORE}"
    would = {"act": "upload", "slot": slot_key, "type": what, "size": len(raw), "sha256": digest[:12], "period": when,
             "by": person, "writes": target, "keeps": f"{record_readback.FOLDER}/{profile}/files/{digest[:16]}/",
             "entry": entry_key, "then": "read it back as a pick is read" if read else "queue the read-back"}
    if slot.cardinality is Cardinality.ONE and active and twin is None:
        would["collision"] = f"{slot_key} already holds a file; the upload is added beside it and the slot shows two holders"
    if dry_run:
        return {"dryRun": True, "would": would, "already": twin is not None, "twin": twin.id if twin else "", "alsoIn": elsewhere, "caveats": list(CAVEATS),
                "note": "A dry run: nothing was kept or written. Add --yes to keep the file in jason's store and pin it to the slot."}
    if twin is not None:
        out: dict[str, Any] = {"dryRun": False, "ok": True, "pin": twin.id, "written": target, "already": True, "slot": slot_key,
                               "sha256": digest[:12], "size": len(raw), "alsoIn": elsewhere}
    elif slot.key_document:
        from jason.tasks import key_documents as kd

        link = kd.upload(entry_key, by=person, name=clean, data=raw, note=text, root=root, profile=profile)
        pin_id = "k-" + str(link["id"])
        out = {"dryRun": False, "ok": True, "pin": pin_id, "written": target, "slot": slot_key, "sha256": digest[:12], "size": len(raw),
               "alsoIn": elsewhere}
    else:
        rel, _digest = _keep(root, profile, clean, raw)
        pin_id = "p-" + secrets.token_hex(4)
        row = {"id": pin_id, "slot": slot_key, "kind": PinKind.FILE.value, "ref": rel, "name": clean, "period": when, "by": person,
               "at": rs._now(), "note": text, "unpinned": None, "sha256": digest, "size": len(raw)}
        rs._write_store(profile, lambda d: d["pins"].append(row), purpose="record slots: upload")
        out = {"dryRun": False, "ok": True, "pin": pin_id, "written": target, "slot": slot_key, "sha256": digest[:12], "size": len(raw),
               "alsoIn": elsewhere}
    if twin is None:
        rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "upload", "slot": slot_key, "pin": out["pin"], "by": person,
                                  "size": len(raw), "sha256": digest[:12], "period": when, "store": target})
    out["caveats"] = list(CAVEATS)
    if read:
        out["read"] = record_readback.read(slot_key, pin=out["pin"], by=person, dry_run=False, ocr=ocr, segmenter=segmenter,
                                           preflighter=preflighter, private=private, community=community, root=root, profile=profile)
    else:
        out["reading"] = f"not read yet: jason records --read {slot_key}"
    return out


# The confirmed split -------------------------------------------------------------------------------------------------------

def _parse_part(spec: Any) -> dict[str, str]:
    """A part to fill: ``{"segment": "s2", "slot": KEY, "period": "", "entry": ""}`` or the text ``s2=KEY``, ``s2=KEY@2099-06``,
    ``s2=KEY#NUMBER`` (a repeating key-document row, by its recording number), or ``s2=KEY@2099-06#NUMBER``."""
    if isinstance(spec, dict):
        return {"segment": str(spec.get("segment") or "").strip(), "slot": str(spec.get("slot") or "").strip(),
                "period": str(spec.get("period") or "").strip(), "entry": str(spec.get("entry") or "").strip()}
    seg, _, rest = str(spec or "").partition("=")
    rest, _, entry = rest.partition("#")
    slot, _, period = rest.partition("@")
    return {"segment": seg.strip(), "slot": slot.strip(), "period": period.strip(), "entry": entry.strip()}


def _proposal(root: Path, profile: str, pin_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    rec = record_readback.load(root, profile, pin_id)
    if rec is None:
        raise ValueError(f"pin {pin_id} has not been read; read it first (jason records --read)")
    seg = rec.get("segments") or {}
    if not seg.get("proposal"):
        raise ValueError("jason proposed no split for that file: nothing to confirm")
    return rec, seg


def _source_file(root: Path, rec: dict[str, Any]) -> Path:
    stored = Path(str(rec.get("stored") or ""))
    if not stored.is_file():
        raise ValueError("the file jason read is no longer in its store; read it again before splitting")
    if hashlib.sha256(stored.read_bytes()).hexdigest() != rec.get("sha256"):
        raise ValueError("the file changed since jason read it; read it again (jason records --read) before splitting")
    return stored


def _cut(source: Path, first: int, last: int) -> bytes:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    if first < 1 or last > len(reader.pages) or first > last:
        raise ValueError(f"pages {first}-{last} are not in a file of {len(reader.pages)} pages")
    writer = PdfWriter()
    for n in range(first - 1, last):
        writer.add_page(reader.pages[n])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def split(slot_key: str, *, pin: str = "", parts: list[Any] | tuple[Any, ...] = (), decline: bool = False, by: str, note: str = "",
          dry_run: bool = True, community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """Confirm parts of a combined scan's proposal. ``parts`` names, for each part to fill, its segment and the slot (and a
    period for a series). Parts not named are left unconfirmed and fill nothing. A part whose slot already holds a file (or is
    filled by an earlier part of this request, for a slot that holds one) is a collision: reported, not written. ``decline``
    records that a person looked at the proposal and wants none of it."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    rs._slot(community, slot_key)
    text = rs._words(note, "note", required=False)
    computed = rs.compute(community, root, profile)
    here = next((c for c in computed if c.slot.key == slot_key), None)
    if here is None:
        raise KeyError(slot_key)
    active = [h for h in here.holders if h.kind is not PinKind.FOLDER]
    if not pin:
        withs = [h for h in active if (record_readback.load(root, profile, h.id) or {}).get("segments", {}) and
                 (record_readback.load(root, profile, h.id) or {})["segments"].get("proposal")]
        if len(withs) != 1:
            raise ValueError(f"{slot_key} holds {len(withs)} files with a proposed split; name one with --pin")
        pin = withs[0].id
    if not any(h.id == pin for h in active):
        raise ValueError(f"{slot_key} has no active pin {pin}")
    rec, seg = _proposal(root, profile, pin)
    done = rec.get("split") or {}
    if done.get("declined") and not dry_run:
        raise ValueError("that proposal was declined already; read the file again to get a new one")
    if decline:
        if parts:
            raise ValueError("decline the proposal or confirm its parts, not both")
        would = {"act": "split", "slot": slot_key, "pin": pin, "decline": True, "by": person, "writes": f"{record_readback.FOLDER}/{profile}/readings/"}
        if dry_run:
            return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to record that you want none of this split."}
        rec["split"] = {**done, "declined": {"by": person, "at": rs._now(), "note": text}}
        record_readback.save(root, profile, pin, rec)
        rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "split", "slot": slot_key, "pin": pin, "by": person, "declined": True})
        return {"dryRun": False, "ok": True, "declined": True, "pin": pin, "slot": slot_key}
    proposal = {p["segment"]: p for p in seg["proposal"]}
    wanted = [_parse_part(p) for p in parts]
    if not wanted:
        # Nothing confirmed yet: the proposal, with the slots each part fits, for a person to choose from.
        return {"dryRun": True, "ok": True, "pin": pin, "slot": slot_key, "proposal": [
            {**{k: v for k, v in p.items() if k != "title"}, "confirmed": bool((done.get("confirmed") or {}).get(p["segment"]))}
            for p in seg["proposal"]], "caveats": list(CAVEATS),
            "note": "Name each part you confirm and the slot it fills (--part SEGMENT=SLOT). Parts you do not name fill nothing."}
    if len({w["segment"] for w in wanted}) != len(wanted):
        raise ValueError("a part is named once")
    taken: set[str] = set()
    plan: list[dict[str, Any]] = []
    for w in wanted:
        part = proposal.get(w["segment"])
        if part is None:
            raise ValueError(f"the proposal has no part {w['segment']} (it has {', '.join(sorted(proposal))})")
        dest, hidden = rs._slot(community, w["slot"])
        if hidden:
            raise ValueError(f"{w['slot']} is hidden by the profile: {hidden}. Nothing was written.")
        period = rs._period(dest, w["period"])
        if dest.cardinality is Cardinality.SERIES and not period:
            raise ValueError(f"{dest.key} is a series: name the part's period (SEGMENT={dest.key}@2099-06)")
        entry_key = _entry_key(dest, w["entry"])         # a repeating row needs its recording number; any other takes none
        if w["entry"] and not entry_key:
            raise ValueError(f"{dest.key} takes no instrument number: leave off #{w['entry']}")
        if w["entry"] and entry_key == dest.key_document:
            raise ValueError(f"{dest.key} is not a repeating row: leave off #{w['entry']}")
        holding = next(c for c in computed if c.slot.key == dest.key)
        busy = [h for h in holding.holders if h.kind is not PinKind.FOLDER and (dest.cardinality is not Cardinality.SERIES or h.period == period)
                and (not w["entry"] or h.store_id == entry_key)]
        slot_id = f"{dest.key}@{period}#{entry_key}"
        row: dict[str, Any] = {"segment": w["segment"], "pages": part["pages"], "slot": dest.key, "period": period, "entry": w["entry"],
                               "kind": part.get("kind"), "fits": dest.key in {x["key"] for x in part.get("slots") or ()},
                               "action": "fill"}
        if (dest.cardinality is not Cardinality.SEVERAL or w["entry"]) and (busy or slot_id in taken):      # a numbered row holds one file
            row.update({"action": "collision", "why": f"{dest.key} already holds a file" if busy else
                        f"another part of this request fills {dest.key}", "kept": "the file already there; this part was not written"})
        if row["action"] == "fill":
            taken.add(slot_id)
        plan.append(row)
    fills = [r for r in plan if r["action"] == "fill"]
    would = {"act": "split", "slot": slot_key, "pin": pin, "by": person, "fills": [f"{r['slot']} (pages {r['pages'][0]}-{r['pages'][1]})" for r in fills],
             "collisions": [r["slot"] for r in plan if r["action"] == "collision"], "writes": f"spec/{profile}/{rs.STORE}",
             "keeps": "the original scan and its pin, unchanged"}
    source = _source_file(root, rec)
    if dry_run:
        return {"dryRun": True, "would": would, "parts": plan, "caveats": list(CAVEATS),
                "note": "A dry run: nothing was written. Add --yes to fill the slots marked fill. A collision is shown and left "
                        "alone; the original scan stays where it is."}
    made: list[dict[str, Any]] = []
    for r in fills:
        data = _cut(source, r["pages"][0], r["pages"][1])
        label = f"part-pages-{r['pages'][0]}-{r['pages'][1]}.pdf"
        dest = rs._slot(community, r["slot"])[0]
        why = text or f"pages {r['pages'][0]}-{r['pages'][1]} of a combined scan, confirmed"
        if dest.key_document:
            from jason.tasks import key_documents as kd

            link = kd.upload(_entry_key(dest, r["entry"]), by=person, name=label, data=data, note=why, root=root, profile=profile)
            r["pin"] = "k-" + str(link["id"])
            made.append({"segment": r["segment"], "slot": r["slot"], "pin": r["pin"]})
            continue
        rel, digest = _keep(root, profile, label, data)
        pin_id = "p-" + secrets.token_hex(4)
        row = {"id": pin_id, "slot": r["slot"], "kind": PinKind.FILE.value, "ref": rel, "name": label, "period": r["period"], "by": person,
               "at": rs._now(), "note": why, "unpinned": None,
               "sha256": digest, "size": len(data), "splitFrom": pin}
        rs._write_store(profile, lambda d, row=row: d["pins"].append(row), purpose="record slots: split")
        r["pin"] = pin_id
        made.append({"segment": r["segment"], "slot": r["slot"], "pin": pin_id})
    auto = bool(limits.value("split.auto_read", community=community))
    queued = _queue_reads(root, made, person) if auto else {
        "reading": "the new files are not read yet (the split.auto_read limit is off): jason records --read SLOT for each"}
    confirmed = dict(done.get("confirmed") or {})
    for m in made:
        confirmed[m["segment"]] = {"slot": m["slot"], "pin": m["pin"], "by": person, "at": rs._now()}
    rec["split"] = {**done, "confirmed": confirmed}
    for p in (rec.get("segments") or {}).get("proposal") or ():
        p["confirmed"] = p["segment"] in confirmed
        if p["segment"] in confirmed:
            p["confirmedBy"] = confirmed[p["segment"]]["by"]
    record_readback.save(root, profile, pin, rec)
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "split", "slot": slot_key, "pin": pin, "by": person,
                              "parts": made, "collisions": [r["slot"] for r in plan if r["action"] == "collision"],
                              "store": f"spec/{profile}/{rs.STORE}"})
    return {"dryRun": False, "ok": True, "pin": pin, "slot": slot_key, "parts": plan, "filled": made,
            "written": f"spec/{profile}/{rs.STORE}", "caveats": list(CAVEATS), "autoRead": auto, **queued}


def queue_read(root: Path, slot_key: str, pin: str, by: str) -> dict[str, Any]:
    """Queue a read-back of one pin as a job on Google's lane, in ``by``'s name. It never reads inline."""
    from jason import jobs

    argv = ["records", "--read", slot_key, "--yes", "--by", by, "--pin", pin]
    job = jobs.add(root, argv, confirmed_by=by, job_class_override=jobs.JobClass.GOOGLE)
    return {"pin": pin, "slot": slot_key, "job": job.id, "command": "jason " + " ".join(argv)}


def _queue_reads(root: Path, made: list[dict[str, Any]], by: str) -> dict[str, Any]:
    """A read-back job for each new part file. A part that cannot be queued is named; the split itself stands."""
    from jason import jobs

    queued, failed = [], []
    for m in made:
        try:
            queued.append(queue_read(root, m["slot"], m["pin"], by))
        except jobs.JobRefused as exc:
            failed.append({"pin": m["pin"], "slot": m["slot"], "why": str(exc)})
    out: dict[str, Any] = {"queued": queued, "reading": f"{len(queued)} read-back job(s) queued in {by}'s name (jason worker --once)"}
    if failed:
        out["notQueued"] = failed
    return out


# Acknowledging a change ----------------------------------------------------------------------------------------------------

def ack(slot_key: str, *, pin: str = "", by: str, note: str = "", dry_run: bool = True, community: Any = None,
        root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """A person has seen that the pinned file changed since it was last read. The mark stays on the reading as history, now
    acknowledged (who, when); a later change makes a new mark."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    rs._slot(community, slot_key)
    text = rs._words(note, "note", required=False)
    code = next((c for c in rs.compute(community, root, profile) if c.slot.key == slot_key), None)
    active = [h for h in (code.holders if code else []) if h.kind is not PinKind.FOLDER]
    marked = [h for h in active if (record_readback.load(root, profile, h.id) or {}).get("lastChange")
              and not (record_readback.load(root, profile, h.id) or {})["lastChange"].get("ack")]
    if pin:
        marked = [h for h in marked if h.id == pin]
        if not marked:
            raise ValueError(f"{slot_key} has no changed mark to acknowledge on pin {pin}")
    elif len(marked) != 1:
        raise ValueError(f"{slot_key} has {len(marked)} changed marks to acknowledge" + ("; name one with --pin (" + ", ".join(h.id for h in marked) + ")" if marked else ""))
    target = marked[0]
    rec = record_readback.load(root, profile, target.id) or {}
    would = {"act": "ack", "slot": slot_key, "pin": target.id, "by": person, "writes": f"{record_readback.FOLDER}/{profile}/readings/",
             "changed": [d["fact"] for d in (rec.get("lastChange") or {}).get("diff") or ()]}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to record that you have seen the change. "
                "The mark stays in the trail."}
    rec["lastChange"] = {**rec["lastChange"], "ack": {"by": person, "at": rs._now(), "note": text}}
    record_readback.save(root, profile, target.id, rec)
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "ack", "slot": slot_key, "pin": target.id, "by": person})
    return {"dryRun": False, "ok": True, "acknowledged": target.id, "pin": target.id, "slot": slot_key,
            "written": f"{record_readback.FOLDER}/{profile}/readings/"}


# Replacing a file in one act ----------------------------------------------------------------------------------------------

def replace(slot_key: str, *, by: str, file: str = "", name: str = "", data: bytes | None = None, base64_body: str = "", path: str = "",
            pin: str = "", period: str = "", entry: str = "", note: str = "", force: bool = False, dry_run: bool = True,
            read: bool = True, ocr: bool = True, drive: Any = None, segmenter: Callable[..., Any] | None = None,
            preflighter: Callable[..., Any] | None = None, private: bool = True, community: Any = None, root: Path | None = None,
            profile: str | None = None) -> dict[str, Any]:
    """Swap the file a slot holds for a new one in one act: pin or upload the new file, then unpin the old. ``pin`` names the old
    pin (needed when the slot holds several; with a repeating key-document row, ``entry`` narrows to that instrument). The new
    file is a path on this computer or its bytes (``path``/``data``/``base64_body``, an upload), or ``file``: a Drive link or id,
    or ``library:ID`` (a pick). History keeps both pins, the old one marked unpinned. The old file is never touched.

    A pin a person **kept** (they confirmed it although jason reads the file as another kind) is not replaced without ``force``.
    Everything is checked before anything is written; a dry run shows both halves. If the old pin cannot be unpinned after the new
    one is pinned, the result says so (``partial``) and the slot shows two holders until a person unpins one."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    slot, hidden = rs._slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    if bool(file) == bool(path or data is not None or base64_body):
        raise ValueError("replace needs the new file: a path on this computer (an upload) or a Drive link, id, or library:ID (a pick), not both")
    entry_key = _entry_key(slot, entry) if slot.key_document and entry else ""
    active = rs._active_pins(root, profile, slot_key)
    if entry_key:
        active = [p for p in active if p.store_id == entry_key]
    if not pin:
        if len(active) != 1:
            raise ValueError(f"{slot_key} holds {len(active)} pins to replace; name the old one with --pin (" +
                             ", ".join(p.id for p in active) + ")" if active else f"{slot_key} holds no pin of a person's to replace; "
                             "use --upload or --pick")
        pin = active[0].id
    old = next((p for p in active if p.id == pin), None)
    if old is None:
        coded = any(p.id == pin for p in rs.code_pins(community, rs.assemble(community).slots).get(slot_key, []))
        raise ValueError("that pin is the specification's, not a person's: replacing it is a change to the profile" if coded
                         else f"{slot_key} has no active pin {pin}")
    held = next((h for c in rs.compute(community, root, profile) if c.slot.key == slot_key for h in c.holders if h.id == pin), None)
    if held is not None and held.kept and not force:
        raise ValueError(f"pin {pin} was kept by {held.kept_by}, who confirmed it although jason reads the file as another kind. "
                         "Replacing it overrides that person's decision; add --force if you mean to")
    if file and rs.parse_file_ref(file)[1] == old.ref:
        raise ValueError("that is the file the slot already holds")
    kw = {"by": person, "period": period, "note": note, "community": community, "root": root, "profile": profile}
    if file:
        first = rs.pick(slot_key, file, entry=entry, drive=drive, dry_run=True, **kw)
    else:
        first = upload(slot_key, name=name, data=data, base64_body=base64_body, path=path, entry=entry, dry_run=True, read=read, **kw)
        if first.get("twin") == pin:
            raise ValueError("that is the file the slot already holds")
    second = rs.unpin(slot_key, pin=pin, by=person, note=note or "replaced", dry_run=True, community=community, root=root, profile=profile)
    would = {"act": "replace", "slot": slot_key, "old": pin, "by": person, "new": first["would"], "unpin": second["would"],
             "forced": bool(force and held is not None and held.kept)}
    if dry_run:
        return {"dryRun": True, "would": would, "first": first, "then": second, "caveats": list(CAVEATS),
                "note": "A dry run: nothing was written. Add --yes to pin the new file and then unpin the old one. History keeps both; "
                        "no file is deleted."}
    if file:
        new = rs.pick(slot_key, file, entry=entry, drive=drive, dry_run=False, **kw)
    else:
        new = upload(slot_key, name=name, data=data, base64_body=base64_body, path=path, entry=entry, dry_run=False, read=read, ocr=ocr,
                     segmenter=segmenter, preflighter=preflighter, private=private, **kw)
    out: dict[str, Any] = {"dryRun": False, "ok": True, "slot": slot_key, "pin": new["pin"], "replaced": pin, "new": new, "written": new.get("written"),
                           "caveats": list(CAVEATS)}
    try:
        gone = rs.unpin(slot_key, pin=pin, by=person, note=note or "replaced", dry_run=False, community=community, root=root, profile=profile)
    except Exception as exc:  # noqa: BLE001 - the new pin stands; say what is left to do
        out.update({"ok": False, "partial": True, "why": f"the new file is pinned ({new['pin']}) but the old pin {pin} was not unpinned: {exc}. "
                    f"Unpin it: jason records --unpin {slot_key} --pin {pin} --yes --by NAME"})
        return out
    out["unpinned"] = gone
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "replace", "slot": slot_key, "pin": new["pin"], "replaced": pin,
                              "by": person, "forced": would["forced"]})
    return out


__all__ = ["CAVEATS", "UPLOAD_TYPES", "ack", "cap_for", "check", "queue_read", "replace", "split", "upload"]
