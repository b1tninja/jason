"""Who was asked and has not answered (docs/arrivals-design.md, "The sent-copy catalog").

Every copy jason sends is recorded when it goes (``data/forms/references.json``, ``tasks.form_references``). Those are the
**asked** side: each reference sent, to which owner and unit, by which channel, and when. Subtract the units and owners
with an arrival, a PayHOA submission, or a keyed answer (``tasks.response_inbox.answered_by``), and what is left is who was
sent a copy and has not responded. Owners the current owner list holds who were sent no copy at all are the second, short
list: never asked.

Disk only: nothing here calls PayHOA, Gmail, or Google, writes anything, or names more than a unit and an owner's name (no
address, no email, no phone). Every answer says how old the catalog and the last check are, so "nothing outstanding" always
carries its time. A mailed letter's marker names the campaign only (every copy of the mailing is the same), so the catalog
lists no recipients of a mailing: the owners it reached appear in the second list unless they answered, and the answer says
so and names the batch (``jason batches``).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from jason.tasks import form_references
from jason.tasks import response_inbox as ri
from jason.tasks.recognize import Catalog, SentCopy

LINE = ("this is the sent-copy catalog less the answers kept on disk; `jason responses --check` looks for new answers (live), "
        "and `jason owner-info --email-batch` records each copy it sends")


def _age(moment: datetime, stamp: Any) -> float | None:
    then = ri.when(stamp)
    return round((moment - then).total_seconds() / 3600, 1) if then else None


def _mtime(path: Path) -> str:
    return ri.iso(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)) if path.is_file() else ""


def owner_units(data_dir: Path, community: Any) -> list[Any] | None:
    """The current owners by unit from the stored PayHOA catalog on disk, or None when there is none or it cannot be read."""
    db = Path(data_dir) / "payhoa.db"
    if not db.is_file():
        return None
    from jason.tasks.member_preferences import payhoa_owners

    try:
        return payhoa_owners(db, tags=community.payhoa_tags() if community is not None else ())
    except Exception:  # noqa: BLE001 - a catalog that cannot be read is no owner list
        return None


def outstanding(data_dir: Path, community: Any, *, request: str = "", now: datetime | None = None,
                units: Sequence[Any] | None = None) -> dict[str, Any]:
    """For each request the profile watches (or the one named): the copies sent, how many are answered, who was sent a copy
    and has not responded (unit, owner, channel, when sent), and the owners never sent one. ``units`` replaces the owner list
    read from disk (a test's). Raises ``ResponseError`` for a request the profile does not have."""
    data_dir = Path(data_dir)
    moment = now or ri.now_utc()
    asked = tuple(r for r in community.response_requests() if not request or r.key == request)
    if request and not asked:
        raise ri.ResponseError(f"the profile has no request {request!r} (Community.response_requests)")
    catalog = Catalog.load(data_dir)
    path = data_dir / form_references.STORE
    owners = list(units) if units is not None else owner_units(data_dir, community)
    names = {o.membership_id: o.name for u in owners or [] for o in u.owners}
    every = catalog.copies()
    sent_stamps = [c.last_sent for c in every if c.last_sent]
    checked = ri.channel_status(data_dir, now=moment)
    last_ok = max((c["lastOk"] for c in checked if c["lastOk"]), default="")
    out_requests = []
    for req in asked:
        copies = ri.request_copies(catalog, req)
        personal = [c for c in copies if c.identity == "copy"]
        mailings = [c for c in copies if c.identity == "campaign"]
        answers = ri.answered_by(data_dir, req.key)
        waiting, done = [], []
        for c in sorted(personal, key=lambda c: (c.unit.casefold(), c.reference)):
            by = answers.of(c)
            row = {"unit": c.unit, "owner": names.get(c.membership_id, "") if c.membership_id is not None else "",
                   "channel": c.channel, "sentAt": c.first_sent, "lastSent": c.last_sent,
                   "daysSinceSent": max(0, (moment - ri.when(c.first_sent)).days) if ri.when(c.first_sent) else None,
                   "reference": c.reference}
            (done if by else waiting).append({**row, "answeredBy": by} if by else row)
        asked_members = {c.membership_id for c in personal}
        asked_units = {c.unit_id for c in personal}
        never, unasked_answered = [], 0
        for u in owners or []:
            for o in u.owners:
                if o.membership_id in asked_members:
                    continue
                if answers.of(SentCopy("", unit=u.label, unit_id=u.unit_id, membership_id=o.membership_id)):
                    unasked_answered += 1
                    continue
                never.append({"unit": u.label, "owner": o.name, "unitHasASentCopy": u.unit_id in asked_units})
        note = ""
        if mailings:
            batches = sorted({c.batch for c in mailings if c.batch})
            note = ("A mailed letter's marker names the mailing, not an owner, so the catalog lists no recipients of it"
                    + (f" (batch {', '.join(batches)}: `jason batches --show`)" if batches else "")
                    + ": owners it reached who were sent no emailed copy are listed under never asked until they answer.")
        out_requests.append({
            "request": req.key, "title": req.title, "year": req.cycle.year,
            "returnBy": req.cycle.return_by.isoformat() if req.cycle.return_by else "",
            "sent": len(personal), "answered": len(done), "notResponded": len(waiting), "outstanding": waiting,
            "answeredCopies": done, "mailings": [{"reference": c.reference, "channel": c.channel, "sentAt": c.first_sent,
                                                  "batch": c.batch} for c in mailings],
            "neverAsked": never if owners is not None else None, "neverAskedAnswered": unasked_answered,
            "neverAskedNote": ("" if owners is not None else "no owner list is on disk (data/payhoa.db), so owners who were "
                               "never sent a copy cannot be listed"), "note": note})
    return {
        "at": ri.iso(moment), "requests": out_requests,
        "catalog": {"path": "data/" + form_references.STORE.as_posix(), "exists": path.is_file(), "writtenAt": _mtime(path),
                    "ageHours": _age(moment, _mtime(path)) if path.is_file() else None,
                    "copies": sum(1 for c in every if c.identity == "copy"),
                    "mailings": sum(1 for c in every if c.identity == "campaign"),
                    "newestSent": max(sent_stamps, default=""), "newestSentAgeHours": _age(moment, max(sent_stamps, default=""))},
        "lastCheck": {"at": last_ok, "ageHours": _age(moment, last_ok), "channels": checked},
        "ownerList": {"exists": owners is not None, "writtenAt": _mtime(data_dir / "payhoa.db"),
                      "ageHours": _age(moment, _mtime(data_dir / "payhoa.db")) if owners is not None else None},
        "note": LINE}


__all__ = ["LINE", "outstanding", "owner_units"]
