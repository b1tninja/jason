"""The record checklist's sources and write (docs/record-intake.md, docs/console/handoff-record-intake.md).

``record_slots(args)`` is ``GET /api/record-slots`` (``?group=``, ``?state=``): the checklist by group, with every state,
count, and the biggest unknowns worked out here, so the page computes nothing. ``record_slot(args)`` is
``GET /api/record-slot?key=``: one slot with its law, holders, the library's reading of each, collisions, candidates, the
person's answer, what the office may do, and the trail. Both read disk only. A file in a confidential slot, or read as a
confidential kind, is named by its kind and its id shortened unless the private view is open for the signed-in person; the
key of a slot is in the URL, never a file's name or id.

``write(key, body)`` is ``POST /api/write/records/<slot key>`` (behind the write guard's token), with ``by``:

- ``{"act": "pick", "file": LINK_OR_ID, "period": "", "entry": "", "note": ""}``: a Drive link or id (or ``library:ID``);
  its name comes from the Drive catalog on disk when it holds the id (the chooser's ``drive/resolve`` reads a pasted link
  in Drive first, read-only);
- ``{"act": "answer", "value": "not_applicable"|"none"|"waiting", "note": ..., "who": ...}``;
- ``{"act": "unpin", "pin": ID}``;
- ``{"act": "bind", "folder": LINK_OR_ID}``: name a Drive folder for the slot (its files are candidates, never pins); the answer
  carries the proposed sync rule for a 5200 record, as text for a person to apply;
- ``{"act": "keep", "pin": ID, "note": reason}``: keep a pick that jason reads as another kind, in a person's words;
- ``{"act": "repin", "pin": ID, "to": SLOT_KEY, "period": "", "entry": ""}``: move a pick to the slot it fits;
- ``{"act": "more", "value": "yes"|"no"}``: "is there another?" for a set that grows ("no" is "this is all"), signed;
- ``{"act": "reopen", "note": ..., "what": "answer"|"more"}``: take back the standing answer or a closed set;
- ``{"act": "read", "pin": ID, "dryRun": true}``: say what reading the pinned file would fetch and how big it is (fetches
  nothing). Without ``dryRun`` it **queues a job** (``jason records --read KEY --yes``, on Google's lane) in the signed-in
  person's name; the job fetches the file into jason's store, reads it, and keeps the reading beside the pin. The page
  never reads inline.

- ``{"act": "upload", "name": "scan.pdf", "base64": "...", "period": "", "entry": "", "note": ""}``: a file from the computer,
  at most 25 MB, a PDF, an image, or a Word file (type and size checked). The bytes are kept in jason's own store (never Drive)
  and pinned; the read-back is **queued** as a job in the signed-in person's name (the page never reads inline). A server path
  is never taken from the console;
- ``{"act": "split", "pin": ID, "parts": [{"segment": "s2", "slot": SLOT_KEY, "period": ""}], "note": ""}``: confirm the parts of a
  combined scan's proposal that a person names, each into its slot. A slot that already holds a file is a collision, shown
  and not overwritten; parts not named fill nothing. With no ``parts`` it answers the proposal and the slots each part fits.
  ``{"act": "split", "pin": ID, "decline": true}`` records that a person wants none of it;
- ``{"act": "ack", "pin": ID}``: the person has seen that the file changed since it was read; the mark stays as history.

Every act takes ``"dryRun": true`` to answer what it would write and write nothing. Replacing a file comes later; asking for it is a 400. Writes jason's own stores only
(``records.json``, the key documents' store for a recorded instrument, and the history); nothing reaches Drive, PayHOA, or the
county, and the picked file is never touched.

``record_readings(args)`` is ``GET /api/record-readings``: the confirmations queue's fourth kind, "record reading" (a wrong-slot
pick, an unconfirmed split), as rows the queue merges; disk only.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

ACTS = ("pick", "answer", "unpin", "bind", "keep", "repin", "more", "reopen", "read", "upload", "split", "ack")
LATER = ("replace", "current")
VALUES = {"not_applicable": "notApplicable", "notapplicable": "notApplicable", "notApplicable": "notApplicable", "none": "none", "waiting": "waiting"}
RETURNED = ("written", "pin", "answer", "already", "reading", "keep", "more", "reopened", "unpinned", "from", "to", "binding", "proposal",
            "dryRun", "would", "note", "reads", "readingMoved", "unchanged", "sha256", "size", "alsoIn", "parts", "filled", "declined",
            "proposal", "acknowledged", "caveats", "job", "queued", "command")


def _private() -> bool:
    """Whether the private view is open on this request for a person whose offices open P3 in it."""
    try:
        from jason.web import access

        return bool(access.private_open())
    except Exception:  # noqa: BLE001 - outside a request (a script, a test) there is no private view
        return False


def _community() -> Any:
    from jason.community import community

    return community()


def _root() -> Any:
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def record_slots(args: Args) -> dict[str, Any]:
    from jason.tasks import record_slots as rs

    return rs.view(_community(), _root(), group=(args.get("group") or "").strip(), state=(args.get("state") or "").strip(),
                   private=_private())


def record_slot(args: Args) -> dict[str, Any]:
    from jason.tasks import record_slots as rs

    key = (args.get("key") or "").strip()
    if not key:
        raise ValueError("a slot is named by its key: ?key=records/5200/minutes")
    return rs.slot_view(key, _community(), _root(), private=_private())


def record_readings(args: Args) -> dict[str, Any]:
    from jason.tasks import record_readback

    return record_readback.queue_items(_community(), _root(), private=_private())


def _actor(by: str) -> str:
    """Who is doing this: while someone is signed in, that person (a different name is refused); else ``by``. Never jason."""
    who = " ".join(str(by or "").split())
    try:
        from jason.web import signin

        acting = signin.acting_as()
        if acting is not None:
            raise ValueError(f"viewing as {acting.name or 'the ' + acting.role} (admin view): a pick or an answer is made as yourself")
        signed = signin.signed_in_name()
    except RuntimeError:          # outside a request (a test, a script): no session to read
        signed = ""
    if signed:
        if who and who.casefold() != signed.casefold():
            raise ValueError(f"signed in as {signed}: the pick goes on the record under the signed-in name, not {who}")
        who = signed
    if not who:
        raise ValueError("A pick names who made it.")
    return who


def _drive_or_none() -> Any:
    """A Drive client to read a folder's name or a file's size, when Drive is connected; none (and no error) when it is not."""
    from jason.tasks.drive_choose import DriveUnavailable
    from jason.web.extra import drive_choose as web_drive

    try:
        return web_drive._open()
    except DriveUnavailable:
        return None


def _close(client: Any) -> None:
    closer = getattr(client, "close", None)
    if client is not None and callable(closer):
        closer()


def _queue_read(key: str, body: dict[str, Any], by: str, community: Any, root: Any) -> dict[str, Any]:
    """Queue the reading as a job in the signed-in person's name. The pipeline runs in the worker (it fetches a file and may
    run OCR); the page never waits on it."""
    from jason import jobs
    from jason.tasks import record_slots as rs

    rs._slot(community, key)
    argv = ["records", "--read", key, "--yes", "--by", by]
    if str(body.get("pin") or "").strip():
        argv += ["--pin", str(body["pin"]).strip()]
    job = jobs.add(root, argv, confirmed_by=by, job_class_override=jobs.JobClass.GOOGLE)
    return {"job": job.id, "command": "jason " + " ".join(argv), "queued": True,
            "note": "queued; the worker fetches the file into jason's store and reads it (jason worker --once)"}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    from jason.tasks import record_acts, record_readback, record_upload
    from jason.tasks import record_slots as rs

    act = str(body.get("act") or "").strip()
    if act in LATER:
        raise ValueError(f"{act} is not built yet: pick or upload the new file and unpin the old one")
    if act not in ACTS:
        raise ValueError(f"act is one of {', '.join(ACTS)}")
    by = _actor(str(body.get("by") or ""))
    community, root = _community(), _root()
    dry = bool(body.get("dryRun"))
    kw = {"by": by, "dry_run": dry, "community": community, "root": root}
    note = str(body.get("note") or "")
    try:
        if act == "pick":
            out = rs.pick(key, str(body.get("file") or ""), period=str(body.get("period") or ""), note=note,
                          entry=str(body.get("entry") or ""), **kw)
        elif act == "answer":
            value = VALUES.get(str(body.get("value") or "").strip())
            if value is None:
                raise ValueError("value is not_applicable, none, or waiting")
            out = rs.answer(key, value, reason=note, who=str(body.get("who") or ""), **kw)
        elif act == "unpin":
            out = rs.unpin(key, pin=str(body.get("pin") or ""), note=note, **kw)
        elif act == "keep":
            out = record_acts.keep(key, pin=str(body.get("pin") or ""), reason=note, **kw)
        elif act == "repin":
            out = record_acts.repin(key, to=str(body.get("to") or ""), pin=str(body.get("pin") or ""),
                                    period=str(body.get("period") or ""), entry=str(body.get("entry") or ""), note=note, **kw)
        elif act == "more":
            out = record_acts.more(key, str(body.get("value") or ""), note=note, **kw)
        elif act == "reopen":
            out = record_acts.reopen(key, note=note, what=str(body.get("what") or ""), **kw)
        elif act == "upload":
            if body.get("path"):
                raise ValueError("the console uploads the file's bytes, never a path on the server")
            out = record_upload.upload(key, name=str(body.get("name") or ""), base64_body=str(body.get("base64") or ""),
                                       period=str(body.get("period") or ""), entry=str(body.get("entry") or ""), note=note, read=False, **kw)
            if not dry and out.get("pin") and not out.get("already"):
                out.update(_queue_read(key, {"pin": out["pin"]}, by, community, root))
        elif act == "split":
            out = record_upload.split(key, pin=str(body.get("pin") or ""), parts=list(body.get("parts") or ()),
                                      decline=bool(body.get("decline")), note=note, **kw)
        elif act == "ack":
            out = record_upload.ack(key, pin=str(body.get("pin") or ""), note=note, **kw)
        elif act == "bind":
            client = _drive_or_none()
            try:
                out = record_acts.bind(key, str(body.get("folder") or ""), note=note, drive=client, **kw)
            finally:
                _close(client)
        else:
            if not dry:
                return {"ok": True, "act": act, "key": key, **_queue_read(key, body, by, community, root)}
            client = _drive_or_none()
            try:
                out = record_readback.read(key, pin=str(body.get("pin") or ""), dry_run=True, drive=client, community=community,
                                           root=root, private=_private())
            finally:
                _close(client)
    except KeyError:
        raise KeyError(key) from None
    return {"ok": True, "act": act, "key": key, **{k: v for k, v in out.items() if k in RETURNED}}
