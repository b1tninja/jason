"""The responses inbox, read from disk: has anyone answered the association's request? (docs/responses-design.md)

Three tools for the board profile. ``new_responses`` lists the arrivals the last check kept (new ones by default): each with
the owner's name and unit, when it came, by which channel, and the names of its attachments, and for each channel when
it last succeeded, how the last try ended, and how old that is. ``response`` is one arrival: its reading, its keyed
answers, its acts, and what is left to do (read, confirm, apply). ``outstanding_responses`` is the other side: the
sent-copy catalog less the answers, who was sent a copy and has not responded, and the owners never sent one.

None calls Gmail, PayHOA, Google, or Keeper, and none writes. They read ``data/responses`` (``jason.tasks.response_inbox``)
and the sent-copy catalog (``data/forms/references.json``): what the last ``jason responses --check`` kept. A reading is evidence for a person, never an answer; a contact value in an
answer is masked (``jason.approvals.audit.mask``); no email address or phone number is ever in the output, and none is
stored on an arrival. A miss carries its reason, never an exception.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CHECK_LINE = "this reads what the last check kept; `jason responses --check` is the live read"
CAVEATS = (
    CHECK_LINE + ". Nothing here calls Gmail or PayHOA: an answer that arrived since the last check is not listed, and a "
    "check that failed for a channel is shown under `checked`.",
    "A reading is evidence for a person, never an answer: a scan's boxes and handwriting are read by a machine, each field "
    "with its confidence and how it was read. Nothing is an owner's answer until a person confirms it "
    "(`jason responses --confirm ID --by NAME`).",
    "A printed reference names a copy jason sent; it is a hint checked against what was sent, and a form is recognised "
    "from its own printed lines, not from the reference. A match to the sender's unit is not a match to the signer.",
    "Names, units, dates, channels, and attachment names only: an email address or phone number is never stored on an "
    "arrival, and a contact value in an answer is masked here.",
    "PayHOA is written only by `jason owner-info --apply --yes`, a person's yes; jason replies to no one, files no return, "
    "and completes no request because of an email.",
)
STATES = ("new", "seen", "read", "keyed", "recorded", "dismissed")
CHANNELS = ("payhoa", "gmail", "mail", "forms")
# What each state leaves to do, in order; the command is the person's, never jason's own initiative.
_APPLY = {"step": "apply", "command": "jason owner-info --apply --payhoa",
          "says": "a dry run plans the writes and what is left for a person; --yes writes them, with a named person"}
_READ = {"step": "read", "command": "jason responses --read ID --by NAME",
         "says": "download the attachments, find the form and its printed reference, read the boxes and writing"}
_CONFIRM = {"step": "confirm", "command": "jason responses --confirm ID --by NAME [--set FIELD=VALUE]",
            "says": "a person says this is what the form says, with corrections; only then is it an answer"}


def _root(data_dir: Path | None) -> Path:
    from jason.config import Settings

    return Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent


def _mask(value: Any, *, addresses: bool = True) -> Any:
    from jason.approvals.audit import mask

    return mask(value, addresses=addresses)


def _hide(name: str, value: Any) -> Any:
    """An answer's value as it may leave: an email or a phone number masked wherever it is, and a field named for contact
    details (an email, a phone, a mailing address) masked whole. A unit's own address is the unit's, so it stays."""
    from jason.approvals.evidence import _CONTACT_NAME

    if isinstance(value, (list, tuple)):
        return [_hide(name, v) for v in value]
    if isinstance(value, dict):
        return {k: _hide(k, v) for k, v in value.items()}
    if not isinstance(value, str):
        return value
    private = bool(_CONTACT_NAME.search(name or ""))
    text = _mask(value, addresses=private)
    return "[masked]" if private and text.strip() and text == value else text


def _age_hours(at: str) -> float | None:
    from jason.tasks import response_inbox as ri

    moment = ri.when(at)
    return round((ri.now_utc() - moment).total_seconds() / 3600, 1) if moment else None


def checked(root: Path) -> list[dict[str, Any]]:
    """Each channel: when the last try succeeded, how it ended, and the success's age in hours. A channel no check has
    reached is shown as never checked."""
    from jason.community.response_inbox import Channel
    from jason.tasks import response_inbox as ri

    kept = {row["channel"]: row for row in ri.channel_status(root)}
    out = []
    for channel in Channel:
        row = kept.get(channel.value)
        if row is None:
            out.append({"channel": channel.value, "lastOk": "", "lastTried": "", "ended": "never checked", "reason": "",
                        "ageHours": None})
            continue
        out.append({"channel": row["channel"], "lastOk": row["lastOk"], "lastTried": row["lastTried"],
                    "ended": row["ended"], "reason": _mask(row["reason"]), "ageHours": row["ageHours"]})
    return out


def _row(a: Any) -> dict[str, Any]:
    return {"id": a.id, "request": a.request, "channel": a.channel.value, "at": a.at, "ageHours": _age_hours(a.at),
            "who": _mask(a.who, addresses=False), "unit": _mask(a.unit, addresses=False),
            "summary": _mask(a.summary, addresses=False), "attachments": [_mask(n, addresses=False) for n in a.attachments],
            "state": a.state.value, "supersededBy": a.superseded_by, "note": _mask(a.note, addresses=False),
            "keptAt": a.kept_at}


def _miss(reason: str, root: Path | None = None, **more: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"found": False, "reason": reason, **more}
    if root is not None:
        try:
            out["checked"] = checked(root)
        except Exception:  # noqa: BLE001 - a miss still says why
            out["checked"] = []
    out["note"] = CHECK_LINE
    out.setdefault("caveats", list(CAVEATS))
    return out


def new_responses(request: str = "", channel: str = "", unit: str = "", state: str = "new", days: int = 0,
                  data_dir: Path | None = None) -> dict[str, Any]:
    """Has anyone answered the association's request? The arrivals the last `jason responses --check` kept, newest first
    (new ones unless ``state`` says another: seen, read, keyed, recorded, dismissed, or all), each with the owner's name
    and unit, when it came and how long ago, the channel (payhoa, gmail, mail, forms), the attachments' names, and its
    state; and ``checked``: for each channel when it last succeeded, how the last try ended, and its age in hours. Filter by
    ``request`` (the request's key), ``channel``, ``unit`` (part of it), and ``days``. This reads what the last check kept;
    `jason responses --check` is the live read. No email address or phone number is stored or shown; an arrival nobody has
    read is not an answer. Read-only; repeat the caveats."""
    try:
        from jason.tasks import response_inbox as ri

        root = _root(data_dir)
        want = (state or "").strip().lower()
        want = "" if want in ("all", "any") else want
        if want and want not in STATES:
            return _miss(f"no state {state!r}; the states are {', '.join(STATES)}, or all", root)
        way = (channel or "").strip().lower()
        if way and way not in CHANNELS:
            return _miss(f"no channel {channel!r}; the channels are {', '.join(CHANNELS)}", root)
        inbox = ri.load_inbox(root)
        if not inbox.arrivals and not inbox.channels:
            return _miss("no check has been run: there is no inbox yet (data/responses/inbox.json). `jason responses "
                         "--check` looks at every channel and keeps what it finds", root, count=0, arrivals=[])
        rows = ri.list_arrivals(root, state=want, request=(request or "").strip(), unit=(unit or "").strip(), channel=way,
                                days=max(0, int(days or 0)))
        held: dict[str, int] = {}
        for a in inbox.arrivals.values():
            held[a.state.value] = held.get(a.state.value, 0) + 1
        if not rows:
            return _miss(f"no arrival matches (state {want or 'any'}"
                         + "".join(f", {k} {v}" for k, v in (("request", request), ("channel", way), ("unit", unit)) if v)
                         + (f", last {int(days)} days" if days else "") + f"); the inbox holds {len(inbox.arrivals)}",
                         root, count=0, arrivals=[], inbox=held)
        return {"found": True, "state": want or "all", "count": len(rows), "arrivals": [_row(a) for a in rows],
                "inbox": held, "checked": checked(root), "note": CHECK_LINE, "caveats": list(CAVEATS)}
    except Exception as exc:  # noqa: BLE001 - a reader that fails is an answer, not a traceback
        return {"found": False, "reason": f"the inbox could not be read: {_mask(f'{type(exc).__name__}: {exc}')}",
                "note": CHECK_LINE, "caveats": list(CAVEATS)}


def _id(value: str) -> str:
    """An arrival's id as the inbox keeps it (``gmail:abc``); the file name's hyphen is read as the colon."""
    text = (value or "").strip()
    if ":" not in text:
        head, dash, tail = text.partition("-")
        if dash and head.lower() in CHANNELS:
            return f"{head.lower()}:{tail}"
    return text


def _copy(root: Path, reading: dict[str, Any], arrival_unit: str) -> dict[str, Any]:
    """The printed reference beside the copy jason sent under it: whether one is on record, and whether it was sent to the
    unit the sender's address belongs to. A hint either way."""
    reference = str(reading.get("reference") or "")
    out: dict[str, Any] = {"text": reference, "how": reading.get("referenceHow") or "",
                           "campaign": reading.get("campaign") or "",
                           "campaignMatchesRequest": bool(reading.get("campaignMatches"))}
    from jason.tasks import response_inbox as ri

    copy = ri.copy_of(root, reading, arrival_unit=arrival_unit)
    if not copy.get("found"):
        if not reference and not copy.get("unsent"):
            out["copy"] = {"found": False, "reason": "no printed reference was read"}
        elif copy.get("unsent"):
            out["copy"] = {"found": False, "unsent": True,
                           "reason": "a reference we did not send: no sent copy is recorded under it (an old test, another "
                                     "association's, or a misread)"}
        else:
            out["copy"] = {"found": False, "reason": "no sent copy is recorded under it (jason keeps a copy's reference "
                                                     "only when it sent that copy)"}
        return out
    owner = reading.get("owner") or {}
    read = str(owner.get("unit") or arrival_unit or "")
    out["copy"] = {"found": True, "reference": copy["reference"], "channel": copy.get("channel", ""), "year": copy.get("year"),
                   "firstSent": copy.get("firstSent", ""), "sentToUnit": _mask(str(copy.get("unit") or ""), addresses=False),
                   "readUnit": _mask(read, addresses=False), "sentToOwner": _mask(str(copy.get("owner") or ""), addresses=False),
                   "matchesUnit": copy.get("matchesUnit"), "matchesOwner": copy.get("matchesOwner"),
                   "matchesWrittenUnit": copy.get("matchesWritten"), "foundBy": copy.get("rung", ""),
                   "sure": copy.get("sure", ""), "putRight": bool(copy.get("putRight")),
                   "says": "whether the copy was sent to the unit and owner the sender's address belongs to, and to the unit "
                           "the form names (null: cannot be told); a hint checked against what was sent, not a reading"}
    return out


def _reading(root: Path, arrival: Any, reading: dict[str, Any]) -> dict[str, Any]:
    owner = reading.get("owner") or {}
    return {
        "label": "evidence for a person, never an answer: nothing here is an owner's answer until a person confirms it",
        "readAt": reading.get("readAt", ""), "by": reading.get("by", ""), "model": reading.get("model", ""),
        "how": reading.get("how", ""), "isTheForm": bool(reading.get("form")),
        "files": [{"name": _mask(f.get("name"), addresses=False), "how": f.get("how"), "linesMatched": f.get("linesMatched")}
                  for f in reading.get("files") or []],
        "reference": _copy(root, reading, arrival.unit),
        "owner": ({"unit": _mask(owner.get("unit"), addresses=False), "name": _mask(owner.get("name"), addresses=False),
                   "matchedBy": owner.get("matchedBy", "")} if owner else {}),
        "fields": {k: {"value": _hide(k, v.get("value")), "how": v.get("how"), "confidence": v.get("confidence")}
                   for k, v in (reading.get("fields") or {}).items()},
        "answers": _hide("answers", reading.get("answers") or {}),
        "signed": reading.get("signed", ""), "signature": _mask(reading.get("signature", ""), addresses=False),
        "residual": reading.get("residual"), "notes": [_mask(n, addresses=False) for n in reading.get("notes") or []],
    }


def _keyed(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": "a person confirmed this reading; it reaches PayHOA only through `jason owner-info --apply --yes`",
        "by": raw.get("by", ""), "at": raw.get("at", ""), "source": raw.get("source", ""),
        "corrected": list(raw.get("corrected") or []), "problems": [_mask(p, addresses=False) for p in raw.get("problems") or []],
        "answers": _hide("answers", raw.get("answers") or {}), "submitted": raw.get("submitted", ""),
        "signed": raw.get("signed", ""), "signature": _mask(raw.get("signature", ""), addresses=False),
        "contacts": [{k: _hide(k, v) for k, v in c.items() if k != "id"} for c in raw.get("contacts") or []],
        "reference": raw.get("reference", ""),
    }


def left(arrival: Any, reading: dict[str, Any] | None) -> list[dict[str, Any]]:
    """What is left to do with an arrival, in order: read, confirm, apply. Each is a person's act."""
    state = arrival.state.value
    if state in ("recorded", "dismissed") or arrival.superseded_by:
        return []
    if arrival.structured:
        return [dict(_APPLY)] if state in ("new", "seen") else []
    if state in ("new", "seen"):
        return [dict(_READ), dict(_CONFIRM), dict(_APPLY)]
    if state == "read":
        if reading and reading.get("form"):
            return [dict(_CONFIRM), dict(_APPLY)]
        return [{"step": "decide", "command": "jason responses --dismiss ID --by NAME --why TEXT",
                 "says": "the reading found no form: dismiss it, or read it again"}]
    return [dict(_APPLY)]


def response(id: str, data_dir: Path | None = None) -> dict[str, Any]:  # noqa: A002 - the tool's argument is the id
    """One arrival in the responses inbox, by its id (``gmail:ID``, ``payhoa:ID``, ``mail:ID``, ``forms:ID``): who it is
    from (a name; no address is stored), the unit, when, the channel, its attachments' names, and its state; its reading
    when `jason responses --read` made one (each field with its confidence and how it was read; the printed reference and
    whether the copy it names was sent to the sender's unit), labeled as evidence, never an answer; the answers a person
    confirmed, with emails, phone numbers, and mailing addresses masked; every act on it (who, when, why); and what is left
    (read, confirm, apply), each a person's step. Reads disk only. A reading is evidence for a person; repeat the caveats."""
    try:
        from jason.tasks import response_inbox as ri

        root = _root(data_dir)
        wanted = _id(id)
        if not wanted:
            return _miss("give an arrival's id (`new_responses` lists them)", root)
        inbox = ri.load_inbox(root)
        if wanted not in inbox.arrivals:
            return _miss(f"no arrival {wanted!r} in the inbox; `new_responses` lists what the last check kept", root,
                         known=len(inbox.arrivals))
        shown = ri.show(root, wanted)
        arrival = inbox.arrivals[wanted]
        reading = shown["reading"]
        return {
            "found": True, "arrival": _row(arrival), "files": [_mask(n, addresses=False) for n in shown["files"]],
            "reading": _reading(root, arrival, reading) if reading else None,
            "keyed": _keyed(shown["keyed"]) if shown["keyed"] else None,
            "acts": [_mask(act) for act in shown["acts"]],
            "left": left(arrival, reading),
            "superseded": (f"a later answer for the unit stands ({arrival.superseded_by}); this one is kept as it came"
                           if arrival.superseded_by else ""),
            "checked": checked(root), "note": CHECK_LINE, "caveats": list(CAVEATS),
        }
    except Exception as exc:  # noqa: BLE001 - a reader that fails is an answer, not a traceback
        return {"found": False, "reason": f"the arrival could not be read: {_mask(f'{type(exc).__name__}: {exc}')}",
                "note": CHECK_LINE, "caveats": list(CAVEATS)}


OUTSTANDING_CAVEATS = (
    "This is the sent-copy catalog (`data/forms/references.json`, written when jason sends a copy) less the answers kept on "
    "disk. An answer that arrived since the last check is not counted: `jason responses --check` is the live read, and the "
    "ages say how old the catalog and the last check are.",
    "A copy is answered when its owner or unit has an arrival that was not dismissed, a PayHOA submission, or keyed answers. "
    "Answering for one unit does not answer for another, and an unread email is counted as an answer from its sender's "
    "unit: a reading is still evidence for a person.",
    "A mailed letter's marker names the mailing, not an owner, so the catalog lists no recipients of it: owners the law "
    "mails appear under `neverAsked` until they answer.",
    "Names and units only: no email address, phone number, or mailing address is stored or shown. Following up with an "
    "owner is a person's act; jason sends and replies to no one.",
)


def outstanding_responses(request: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """Who was sent a copy of a request and has not responded? For each request the profile watches (or the one named by
    ``request``): the copies sent and how many are answered, then each owner and unit that was sent a copy and has no
    answer, with the channel and when it was sent, and a short second list of owners never sent a copy (from the owner
    list on disk). It is the sent-copy catalog jason keeps when it sends a copy, less the answers kept on disk; it says
    how old the catalog, the owner list, and the last check are ("nothing outstanding" always carries its time).
    Names and units only. Reads disk only: no call to PayHOA or Gmail, and nothing is sent; `jason responses --check` is
    the live read. Read-only; repeat the caveats."""
    try:
        from jason.community import community
        from jason.tasks import response_inbox as ri
        from jason.tasks.response_outstanding import LINE, outstanding

        root = _root(data_dir)
        try:
            body = outstanding(root, community(), request=(request or "").strip())
        except ri.ResponseError as exc:
            return _miss(str(exc), root, caveats=list(OUTSTANDING_CAVEATS))
        if not body["requests"]:
            return _miss("the profile watches no request (Community.response_requests is empty), so no copy is tracked", root,
                         catalog=_mask(body["catalog"], addresses=False), caveats=list(OUTSTANDING_CAVEATS))
        out = {"found": True, **_mask(body, addresses=False), "note": LINE, "caveats": list(OUTSTANDING_CAVEATS)}
        out["lastCheck"]["channels"] = checked(root)
        return out
    except Exception as exc:  # noqa: BLE001 - a reader that fails is an answer, not a traceback
        return {"found": False, "reason": f"the catalog could not be read: {_mask(f'{type(exc).__name__}: {exc}')}",
                "note": CHECK_LINE, "caveats": list(OUTSTANDING_CAVEATS)}


TOOLS = (new_responses, response, outstanding_responses)
