"""The signed acts of a slot beyond the pick, the answer, and the unpin (docs/record-intake.md, phase 2): a person keeps a pick
jason doubts, moves a pick to the slot it fits, says whether a set has another, reopens an answer, and binds a Drive folder.

Each names its person (``by``; never jason), is a **dry run** unless told otherwise, holds the store's lock, writes only
``data/spec/<profile>/records.json`` (or, for a recorded instrument, the key documents' store through their one writer),
and appends one line to ``data/records/history.jsonl`` that holds the slot and the act and never a file name or id. Nothing
here changes, moves, shares, or copies a file.

- ``keep``: the pick stays in the slot although jason reads it as another kind. A reason is required. It is a person's
  override, listed with who and when; the reading still says what jason read, and the slot stops showing a problem.
- ``repin``: the pick moves to another slot (a new pin there, the old one marked unpinned with where it went). Its reading
  goes with it, and is compared with the new slot's kinds.
- ``more``: "is there another?" for a set that grows. ``yes`` means a person will add one; ``no`` is "this is all", a person's
  word that the set is complete, signed.
- ``reopen``: takes back the standing answer (not applicable, none exists, waiting) or a closed set. It stays in the trail
  and no longer counts.
- ``bind``: a Drive folder named for a slot. Its files are candidates, never pins. For a Civil Code 5200 record the answer
  carries the *proposed* text of a sync rule for a person to apply to the profile; jason edits nothing.
"""

from __future__ import annotations

import secrets
from typing import Any

from jason.community.record_slots import Cardinality, Pin, PinKind, parse_drive_ref
from jason.tasks import record_slots as rs

MORE_VALUES = {"yes": "yes", "no": "no", "another": "yes", "all": "no"}


def _target(pin: str, active: list[Pin], slot_key: str) -> Pin:
    if not pin:
        if len(active) != 1:
            raise ValueError(f"{slot_key} holds {len(active)} pins; name one with --pin (" + ", ".join(p.id for p in active) + ")"
                             if active else f"{slot_key} holds no pin of a person's")
        return active[0]
    found = next((p for p in active if p.id == pin), None)
    if found is None:
        raise ValueError(f"{slot_key} has no active pin {pin}")
    return found


def _files(community: Any, slot_key: str, root: Any, profile: str) -> list[Pin]:
    """The pins a person may act on: theirs and the key documents' links, and the specification's (which are shown, never
    edited here)."""
    active = rs._active_pins(root, profile, slot_key)
    return active


def keep(slot_key: str, *, pin: str = "", reason: str = "", by: str, dry_run: bool = True, community: Any = None, root: Any = None,
         profile: str | None = None) -> dict[str, Any]:
    """Keep a pick in its slot although jason reads the file as another kind. The reason is the person's own words."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    slot, hidden = rs._slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    why = rs._words(reason, "reason it belongs here")
    computed = next((c for c in rs.compute(community, root, profile) if c.slot.key == slot_key), None)
    wrong = [st for st in (computed.statuses if computed else []) if st.wrong_slot and (not pin or st.pin.id == pin)]
    if not wrong:
        raise ValueError(f"nothing to keep in {slot_key}: jason's reading of its pick agrees with the slot, or it has not read the "
                         "file (jason records --read)")
    target = wrong[0] if not pin and len(wrong) == 1 else next((st for st in wrong if st.pin.id == pin), None)
    if target is None:
        raise ValueError(f"{slot_key} has {len(wrong)} picks that read as another kind; name one with --pin ("
                         + ", ".join(st.pin.id for st in wrong) + ")")
    would = {"act": "keep", "slot": slot_key, "pin": target.pin.id, "by": person, "reads as": (target.reads_as or "").replace("_", " "),
             "writes": f"spec/{profile}/{rs.STORE}"}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to keep this pick here. It is "
                "your override, with your reason; jason still reads the file as another kind and says so."}
    ident = "kp-" + secrets.token_hex(4)
    row = {"id": ident, "slot": slot_key, "pin": target.pin.id, "reason": why, "by": person, "at": rs._now(), "undone": None}
    rs._write_store(profile, lambda data: data.setdefault("keeps", []).append(row), purpose="record slots: keep")
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "keep", "slot": slot_key, "pin": target.pin.id, "by": person,
                              "store": f"spec/{profile}/{rs.STORE}"})
    return {"dryRun": False, "ok": True, "keep": ident, "pin": target.pin.id, "written": f"spec/{profile}/{rs.STORE}", "slot": slot_key}


def repin(slot_key: str, *, to: str, pin: str = "", by: str, period: str = "", entry: str = "", note: str = "",
          dry_run: bool = True, community: Any = None, root: Any = None, profile: str | None = None) -> dict[str, Any]:
    """Move a pick to another slot: a new pin there, the old one unpinned with where it went; the reading goes with it. The file
    is not touched. Through ``pick`` and ``unpin``, so a recorded instrument's slot still takes its link through the key
    documents (``entry`` names the instrument)."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    rs._slot(community, slot_key)
    dest, hidden = rs._slot(community, to)
    if to == slot_key:
        raise ValueError("that is the slot it is in; name another slot to move the pick to")
    if hidden:
        raise ValueError(f"{to} is hidden by the profile: {hidden}. Nothing was written.")
    old = _target(pin, _files(community, slot_key, root, profile), slot_key)
    if old.kind is PinKind.DRIVE:
        ref = old.ref
    elif old.kind is PinKind.LIBRARY:
        ref = f"library:{old.ref}"
    else:
        raise ValueError("an uploaded file is moved by unpinning it and uploading it to the other slot")
    moved = rs.pick(to, ref, by=person, period=period, note=rs._words(note, "note", required=False) or f"moved from {slot_key}",
                    entry=entry, dry_run=dry_run, community=community, root=root, profile=profile)
    if dry_run:
        return {"dryRun": True, "would": {"act": "repin", "from": slot_key, "to": dest.key, "pin": old.id, "by": person,
                                          "pick": moved["would"], "then": f"unpin {old.id} in {slot_key}"},
                "note": "A dry run: nothing was written. Add --yes to move the pick. The file is not touched."}
    rs.unpin(slot_key, by=person, pin=old.id, note=f"moved to {dest.key}", dry_run=False, community=community, root=root, profile=profile)
    from jason.tasks import record_readback

    carried = record_readback.copy_reading(root, profile, old.id, moved["pin"], dest.key)
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "repin", "slot": slot_key, "to": dest.key, "pin": old.id,
                              "newPin": moved["pin"], "by": person, "reading": carried})
    return {"dryRun": False, "ok": True, "from": slot_key, "to": dest.key, "pin": moved["pin"], "unpinned": old.id,
            "written": moved["written"], "readingMoved": carried, "slot": dest.key}


def more(slot_key: str, value: str, *, by: str, note: str = "", dry_run: bool = True, community: Any = None, root: Any = None,
         profile: str | None = None) -> dict[str, Any]:
    """"Is there another?" for a set that grows: ``yes`` (a person will add one) or ``no`` ("this is all"), signed. A set is
    complete only when someone says so."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    slot, hidden = rs._slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    if slot.cardinality is not Cardinality.SEVERAL:
        raise ValueError(f"{slot_key} holds {slot.cardinality.value}, not a set that grows: 'is there another?' is asked of a set")
    said = MORE_VALUES.get(str(value or "").strip().lower())
    if said is None:
        raise ValueError("say yes (there is another to add) or no (this is all)")
    text = rs._words(note, "note", required=False)
    would = {"act": "more", "slot": slot_key, "answer": said, "by": person, "writes": f"spec/{profile}/{rs.STORE}"}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to record this answer. 'No' is "
                "your word that the set is complete; it is not jason's finding."}
    ident = "m-" + secrets.token_hex(4)
    row = {"id": ident, "slot": slot_key, "value": said, "note": text, "by": person, "at": rs._now(), "reopened": None}
    rs._write_store(profile, lambda data: data.setdefault("more", []).append(row), purpose="record slots: more")
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "more", "slot": slot_key, "answer": said, "by": person,
                              "store": f"spec/{profile}/{rs.STORE}"})
    return {"dryRun": False, "ok": True, "more": ident, "answer": said, "written": f"spec/{profile}/{rs.STORE}", "slot": slot_key}


def reopen(slot_key: str, *, by: str, note: str = "", what: str = "", dry_run: bool = True, community: Any = None, root: Any = None,
           profile: str | None = None) -> dict[str, Any]:
    """Take back the standing answer on a slot (not applicable, none exists, waiting), or a closed set ("this is all"). The
    answer stays in the trail and stops counting. ``what`` is ``answer`` or ``more``; by default the answer, else the set's
    closing. A single-copy key document's "none exists" is that store's missing, set back to expected through its writer."""
    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    slot, hidden = rs._slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    text = rs._words(note, "note", required=False)
    stored = rs.load_store(profile)
    answers = [a for a in (rs._answer_of(r) for r in stored["answers"]) if a and a.slot == slot_key and a.open]
    kd_answers = rs._key_document_records(root, profile, slot)[1] if slot.key_document else []
    standing = rs.latest_answer([*answers, *kd_answers])
    closing = max((m for m in stored["more"] if m.get("slot") == slot_key and not m.get("reopened") and m.get("value") == "no"),
                  key=lambda m: str(m.get("at") or ""), default=None)
    pick = what or ("answer" if standing is not None else "more" if closing is not None else "")
    if pick not in ("answer", "more"):
        raise ValueError(f"{slot_key} holds no answer to reopen")
    if pick == "answer" and standing is None:
        raise ValueError(f"{slot_key} holds no answer to reopen")
    if pick == "more" and closing is None:
        raise ValueError(f"{slot_key} was not closed with 'this is all'")
    target = standing.id if pick == "answer" and standing is not None else str(closing["id"])
    word = standing.kind.state.word if pick == "answer" and standing is not None else "this is all"
    through_key_documents = pick == "answer" and standing is not None and standing.source == "key-documents"
    store = f"key-documents/{profile}.json" if through_key_documents else f"spec/{profile}/{rs.STORE}"
    would = {"act": "reopen", "slot": slot_key, "reopens": word, "by": person, "writes": store}
    if dry_run:
        return {"dryRun": True, "would": would, "note": "A dry run: nothing was written. Add --yes to reopen. The answer stays in "
                "the trail; the slot goes back to what the records show."}
    if through_key_documents:
        from jason.tasks import key_documents as kd

        kd.set_status(slot.key_document, "expected", by=person, note=text or "reopened", root=root, profile=profile)
    else:
        def change(data: dict[str, Any]) -> None:
            rows = data["answers"] if pick == "answer" else data.setdefault("more", [])
            for row in rows:
                if row.get("id") == target and not row.get("reopened"):
                    row["reopened"] = {"by": person, "at": rs._now(), "note": text}

        rs._write_store(profile, change, purpose="record slots: reopen")
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "reopen", "slot": slot_key, "reopens": target, "by": person,
                              "store": store})
    return {"dryRun": False, "ok": True, "reopened": target, "written": store, "slot": slot_key}


def bind(slot_key: str, folder: str, *, by: str, drive: Any = None, note: str = "", dry_run: bool = True, community: Any = None,
         root: Any = None, profile: str | None = None) -> dict[str, Any]:
    """Name a Drive folder for a slot: its files become candidates, never pins, and nothing is filed. ``drive``, when given,
    reads the folder's name (read-only) and refuses a file. For a Civil Code 5200 record the answer carries the proposed text of
    a sync rule for a person to apply to the profile (``proposal``); jason edits no specification."""
    from jason.tasks import drive_choose

    root = rs._root(root)
    profile = rs._profile(profile, community)
    person = rs._who(by)
    slot, hidden = rs._slot(community, slot_key)
    if hidden:
        raise ValueError(f"{slot_key} is hidden by the profile: {hidden}. Nothing was written.")
    ref = parse_drive_ref(folder)
    text = rs._words(note, "note", required=False)
    name = ""
    if drive is not None:
        try:
            meta = drive.file_metadata(ref.id, "id,name,mimeType")
        except Exception as exc:  # noqa: BLE001 - Google's refusal, in jason's words
            raise ValueError(drive_choose.refusal_words(exc)) from exc
        if str(meta.get("mimeType") or "") != drive_choose.FOLDER_MIME_TYPE:
            raise ValueError("That is a file, not a folder. Pick it for the slot instead (jason records --pick).")
        name = str(meta.get("name") or "")
    elif not ref.folder and ref.form != "id":
        raise ValueError("That is a file's link. Paste the folder's link, or its id.")
    proposal = drive_choose.propose_sync_rule(slot, name, ref.id)
    would = {"act": "bind", "slot": slot_key, "folder": name or "(not read: no --resolve)", "by": person,
             "writes": f"spec/{profile}/{rs.STORE}"}
    for existing in rs.load_store(profile)["bindings"]:
        if existing.get("slot") == slot_key and existing.get("ref") == ref.id and not existing.get("unbound"):
            return {"dryRun": dry_run, "ok": True, "already": True, "binding": existing.get("id"), "slot": slot_key, "proposal": proposal,
                    **({"would": would} if dry_run else {"written": f"spec/{profile}/{rs.STORE}"})}
    if dry_run:
        return {"dryRun": True, "would": would, "proposal": proposal,
                "note": "A dry run: nothing was written. Add --yes to bind the folder. Its files are read as candidates for the "
                        "slot and nothing is filed, moved, or shared."}
    ident = "b-" + secrets.token_hex(4)
    row = {"id": ident, "slot": slot_key, "ref": ref.id, "name": name, "by": person, "at": rs._now(), "note": text, "unbound": None}
    rs._write_store(profile, lambda data: data.setdefault("bindings", []).append(row), purpose="record slots: bind")
    rs._append_history(root, {"at": rs._now(), "profile": profile, "act": "bind", "slot": slot_key, "binding": ident, "by": person,
                              "store": f"spec/{profile}/{rs.STORE}"})
    return {"dryRun": False, "ok": True, "binding": ident, "written": f"spec/{profile}/{rs.STORE}", "slot": slot_key,
            "proposal": proposal}


__all__ = ["bind", "keep", "more", "repin", "reopen"]
