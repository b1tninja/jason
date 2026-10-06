"""The funnel of a campaign: what was asked, how it came back, and who has still not answered (docs/followups-design.md,
"The two views": forms and campaigns, what we ask).

For one campaign (``tasks.campaigns``: a form, a cycle, a channel) the funnel counts, from what is on disk:

- **asked**: the copies jason sent and recorded (``data/forms/references.json``), by the channel each went by, and the
  mailings (one letter for everyone, so no recipients are listed).
- **answered**, by the way each came in (the inbox channels: ``payhoa``, ``gmail``, ``mail``, ``forms``, and ``manual``, a
  return a person keyed from paper or a call), and for each channel how many were read, confirmed, and recorded. These are
  the arrivals of the request that watches the campaign, not dismissed and not superseded by a later answer for the unit.
  A PayHOA submission or a form response is already structured: it needs no reading, so it counts as read and confirmed.
  When one request is watched by several campaigns (a form's emailed copies and its mailing), the answers are the
  request's, and the funnel says so: an arrival is not attributed to a campaign unless it names a copy.
- **outstanding**, by owner and unit and **channel-agnostic**: an owner who answered by any method is not on it. It is
  ``tasks.response_outstanding`` (the sent-copy catalog less the answers kept), narrowed to this campaign's copies and
  without the owners who are unreachable. Names and units only.
- **unreachable**: an owner no delivery reached, by the notice ledger (``data/notices/deliveries.db``): every attempt this
  campaign's copies made to them bounced, failed, was not shown delivered, was never mailed, or came back, and none arrived.
  They are listed apart and never counted as outstanding: no ask has reached them, so a reminder cannot (Civil Code 4041(e)).
  An owner who answered is not unreachable, and an owner whose attempts are still pending is outstanding.

Each count carries the age of its source, and a source that is missing says so with its reason in ``missing`` (a count that
cannot be made is ``None``, never a bare zero). Disk only: nothing here calls PayHOA, Gmail, or Google, and nothing is
written. No address, email, phone, or answer is read into the result.
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from jason.community.response_inbox import Channel, State
from jason.tasks import campaigns, form_references
from jason.tasks import response_inbox as ri
from jason.tasks.recognize import Catalog, SentCopy

LEDGER = Path("notices") / "deliveries.db"
LEDGER_HOW = "`jason notices KEY --sync` reads each delivery's outcome from PayHOA"
FAILED = ("bounced", "failed", "unknown", "skipped", "returned")        # a delivery that did not reach the owner (see Delivery)
CHANNELS = tuple(c.value for c in Channel)


def moment_of(now: datetime | None = None, today: date | None = None) -> datetime:
    """The clock a read uses: ``now``, else noon UTC on ``today`` (a test's fake clock), else the real time."""
    if now is not None:
        return now
    if today is not None:
        return datetime.combine(today, time(12, 0), tzinfo=timezone.utc)
    return ri.now_utc()


def age_hours(moment: datetime, stamp: Any) -> float | None:
    then = ri.when(stamp)
    return round(max(0.0, (moment - then).total_seconds() / 3600), 1) if then else None      # never negative: a clock's skew is not an age


def mtime(path: Path) -> str:
    return ri.iso(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)) if path.is_file() else ""


def read_ledger(data_dir: Path, moment: datetime) -> dict[str, Any]:
    """The notice ledger on disk: every attempt of every notice, when it was last synced, and how old that is. A ledger that
    is not there, or cannot be read, is ``{"exists": False, "reason": ...}``. Reading never creates the file."""
    path = Path(data_dir) / LEDGER
    if not path.is_file():
        return {"exists": False, "attempts": [], "syncedAt": "", "ageHours": None,
                "reason": f"no notice ledger is on disk (data/{LEDGER.as_posix()}): {LEDGER_HOW}"}
    from jason.tasks import notice_ledger

    try:
        listed = notice_ledger.notices(Path(data_dir))
        attempts = [a for notice, _, _ in listed for a in notice_ledger.load(Path(data_dir), notice)]
    except Exception as exc:  # noqa: BLE001 - a ledger that cannot be read is a missing source, not a traceback
        return {"exists": False, "attempts": [], "syncedAt": "", "ageHours": None,
                "reason": f"the notice ledger could not be read ({type(exc).__name__})"}
    synced = max((s for _, _, s in listed if s), default="")
    return {"exists": True, "attempts": attempts, "syncedAt": synced, "ageHours": age_hours(moment, synced), "reason": ""}


def _campaign_of(catalog: Catalog, reference: str) -> str:
    copy = catalog.copy(reference)
    if copy is not None:
        return copy.campaign
    from jason.community.form_refs import parse

    markers = parse(reference)
    return markers[0].campaign if markers else ""


def attempts_of(catalog: Catalog, attempts: list[Any], code: str) -> list[Any]:
    """The ledger's attempts that were this campaign's copies: an email by the reference in its subject, a letter by the
    mailing's batch (``references.json`` keeps each mailing under the batch it went out in)."""
    batches = {c.batch: c.campaign for c in catalog.copies() if c.identity == "campaign" and c.batch}
    out = []
    for a in attempts:
        mine = _campaign_of(catalog, a.key) if a.channel == "email" else batches.get(a.batch, "")
        if mine == code:
            out.append(a)
    return out


def unreachable_owners(attempts: list[Any], answered: Any = None) -> list[dict[str, Any]]:
    """Owners none of whose attempts arrived (mailed, delivered, opened, forwarded) and at least one failed: each with a
    plain reason. An owner ``answered`` (an ``Answers``) names is left out: they were reached."""
    from jason.tasks.notice_ledger import ARRIVED

    by_owner: dict[Any, list[Any]] = {}
    for a in attempts:
        by_owner.setdefault(a.membership_id or a.unit.casefold(), []).append(a)
    out = []
    for key, mine in by_owner.items():
        if any(a.status in ARRIVED for a in mine) or not any(a.status.value in FAILED for a in mine):
            continue
        first = next((a for a in mine if a.unit), mine[0])
        if answered is not None and answered.of(SentCopy("", unit=first.unit, unit_id=first.unit_id or None,
                                                         membership_id=first.membership_id or None)):
            continue
        why = sorted({f"{a.channel} {a.status.value}" for a in mine if a.status.value in FAILED})
        out.append({"unit": ri.scrub(first.unit, 80), "membershipId": first.membership_id or None, "why": "; ".join(why)})
    return sorted(out, key=lambda r: (r["unit"].casefold(), r["why"]))


def _stage(arrival: Any) -> tuple[bool, bool, bool]:
    """Whether an arrival was read, confirmed, and recorded. A structured one (PayHOA, a Google Form) needs no reading and is
    its own confirmation."""
    structured = arrival.structured
    read = structured or arrival.state in (State.READ, State.KEYED, State.RECORDED)
    confirmed = structured or arrival.state in (State.KEYED, State.RECORDED)
    return read, confirmed, arrival.state is State.RECORDED


def _watching(community: Any, code: str) -> Any:
    try:
        requests = tuple(community.response_requests() or ()) if community is not None else ()
    except Exception:  # noqa: BLE001 - a profile that cannot say watches nothing
        requests = ()
    return next((r for r in requests if r.names_campaign(code)), None)


def _answered(data_dir: Path, request: Any, moment: datetime, checks: dict[str, Any]) -> dict[str, Any]:
    inbox_path = ri.responses_dir(data_dir) / ri.INBOX
    mine = [a for a in ri.load_inbox(data_dir).arrivals.values()
            if a.request == request.key and a.state is not State.DISMISSED and not a.superseded_by]
    by_channel: dict[str, dict[str, Any]] = {}
    for channel in Channel:
        rows = [a for a in mine if a.channel is channel]
        stages = [_stage(a) for a in rows]
        record = checks.get(channel.value) or {}
        by_channel[channel.value] = {
            "answered": len(rows), "read": sum(s[0] for s in stages), "confirmed": sum(s[1] for s in stages),
            "recorded": sum(s[2] for s in stages),
            "checkedHoursAgo": None if channel is Channel.MANUAL else record.get("ageHours"),
            "checked": "keyed by a person: nothing to check" if channel is Channel.MANUAL else (
                "never checked" if not record else f"last succeeded {record.get('lastOk') or 'never'}; last try ended "
                                                   f"{record.get('ended') or 'unknown'}")}
    total = {k: sum(c[k] for c in by_channel.values()) for k in ("answered", "read", "confirmed", "recorded")}
    return {"request": request.key, **total, "byChannel": by_channel, "inboxExists": inbox_path.is_file(),
            "inboxAgeHours": age_hours(moment, mtime(inbox_path)),
            "source": "the response inbox, as the last check and the people who keyed returns kept it"}


def funnel(data_dir: Path, community: Any, campaign_code: str, *, today: date | None = None,
           now: datetime | None = None) -> dict[str, Any]:
    """The funnel of one campaign (see the module): asked, answered by channel, read, confirmed, recorded, outstanding by
    owner (channel-agnostic), and unreachable, each with the age of its source; ``missing`` lists each source that is not on
    disk and why. ``found`` is False, with the reason, for a campaign the record does not have. Never raises for a missing
    store."""
    from jason.tasks import response_outstanding as outstanding_of

    data_dir = Path(data_dir)
    moment = moment_of(now, today)
    code = (campaign_code or "").strip().upper()
    rows = campaigns.view(data_dir, community)
    row = rows.get(code)
    if row is None:
        return {"found": False, "campaign": code, "at": ri.iso(moment),
                "reason": f"there is no campaign {campaign_code!r} (jason campaigns lists them)"}
    missing: list[dict[str, str]] = []
    notes: list[str] = []
    catalog = Catalog.load(data_dir)
    refs_path = data_dir / form_references.STORE
    catalog_age = age_hours(moment, mtime(refs_path))
    mine = [c for c in catalog.copies() if c.campaign == code]
    personal = [c for c in mine if c.identity == "copy"]
    mailings = [c for c in mine if c.identity == "campaign"]
    by_sent: dict[str, int] = {}
    for c in personal:
        by_sent[c.channel or "unknown"] = by_sent.get(c.channel or "unknown", 0) + 1
    if not refs_path.is_file():
        missing.append({"source": "sent-copy catalog",
                        "reason": "no copy has been recorded as sent (data/forms/references.json is not on disk)"})
    asked = {"total": len(personal), "byChannel": by_sent, "mailings": len(mailings), "source": "the sent-copy catalog",
             "ageHours": catalog_age, "newestSent": max((c.last_sent for c in mine if c.last_sent), default="")}
    request = _watching(community, code)
    checks = {r["channel"]: r for r in ri.channel_status(data_dir, now=moment)}
    answered: dict[str, Any] | None = None
    out: dict[str, Any] = {"count": None, "owners": [], "neverAsked": None, "source": "the sent-copy catalog less the answers kept",
                           "ageHours": catalog_age}
    answers = None
    if request is None:
        missing.append({"source": "response inbox",
                        "reason": "no request watches this campaign (Community.response_requests), so its answers cannot be "
                                  "counted and nobody can be called outstanding"})
        out["reason"] = "no request watches this campaign"
    else:
        answered = _answered(data_dir, request, moment, checks)
        if not answered["inboxExists"]:
            missing.append({"source": "response inbox",
                            "reason": "no check has been run (data/responses/inbox.json is not on disk), so no answer is counted: "
                                      "`jason responses --check` looks at every channel"})
        if len(campaigns.for_request(rows, request)) > 1:
            notes.append(f"request {request.key} is watched by several campaigns "
                         f"({', '.join(c.code for c in campaigns.for_request(rows, request))}): the answers are the request's, "
                         "not this campaign's alone")
        answers = ri.answered_by(data_dir, request.key)
        if not personal:
            out["reason"] = ("no emailed copy of this campaign is on record, so who was asked cannot be listed"
                             + (": a mailed letter names no recipient (`jason batches`)" if mailings else ""))
        else:
            body = outstanding_of.outstanding(data_dir, community, request=request.key, now=moment)
            [req] = body["requests"]
            seen: dict[Any, dict[str, Any]] = {}
            for waiting in req["outstanding"]:
                copy = catalog.copy(waiting["reference"])
                if copy is None or copy.campaign != code:
                    continue
                key = copy.membership_id if copy.membership_id is not None else waiting["unit"].casefold()
                seen.setdefault(key, {"unit": waiting["unit"], "name": waiting["owner"], "channel": waiting["channel"],
                                      "sentAt": waiting["sentAt"], "daysSinceSent": waiting["daysSinceSent"],
                                      "membershipId": copy.membership_id})
            out.update({"count": len(seen), "owners": list(seen.values()),
                        "neverAsked": None if req["neverAsked"] is None else len(req["neverAsked"])})
            if req["neverAsked"] is None:
                out["neverAskedReason"] = req["neverAskedNote"]
                missing.append({"source": "owner list", "reason": req["neverAskedNote"]})
    ledger = read_ledger(data_dir, moment)
    unreachable: dict[str, Any] = {"count": None, "owners": [], "source": "the notice ledger", "ageHours": ledger["ageHours"],
                                   "syncedAt": ledger["syncedAt"]}
    if not ledger["exists"]:
        unreachable["reason"] = ledger["reason"]
        missing.append({"source": "notice ledger", "reason": ledger["reason"]})
    else:
        theirs = attempts_of(catalog, ledger["attempts"], code)
        if not theirs:
            unreachable["reason"] = (f"the ledger holds no delivery of this campaign's copies yet ({LEDGER_HOW})")
        else:
            lost = unreachable_owners(theirs, answers)
            unreachable.update({"count": len(lost), "owners": lost, "attempts": len(theirs)})
            gone = {o["membershipId"] for o in lost if o["membershipId"] is not None} | {o["unit"].casefold() for o in lost}
            kept = [o for o in out["owners"] if o.get("membershipId") not in gone and o["unit"].casefold() not in gone]
            if len(kept) != len(out["owners"]) and out["count"] is not None:
                out["owners"], out["count"] = kept, len(kept)
                notes.append("an owner no delivery reached is listed under unreachable, not outstanding")
    for owner in out["owners"]:
        owner.pop("membershipId", None)
    for owner in unreachable["owners"]:
        owner.pop("membershipId", None)
    ages = {"catalogHours": catalog_age, "inboxHours": answered["inboxAgeHours"] if answered else None,
            "checks": {k: v["checkedHoursAgo"] for k, v in (answered["byChannel"] if answered else {}).items()},
            "ledgerHours": ledger["ageHours"], "ledgerSyncedAt": ledger["syncedAt"]}
    return {"found": True, "campaign": code, "form": row.form, "version": row.version, "year": row.year, "channel": row.channel,
            "status": row.status.value, "returnBy": row.return_by, "request": request.key if request else "",
            "at": ri.iso(moment), "asked": asked, "answered": answered, "outstanding": out, "unreachable": unreachable,
            "ages": ages, "missing": missing, "notes": notes}


def funnels(data_dir: Path, community: Any, *, today: date | None = None, now: datetime | None = None,
            open_only: bool = False) -> list[dict[str, Any]]:
    """The funnel of every campaign (the open ones with ``open_only``), newest year first."""
    rows = campaigns.view(Path(data_dir), community)
    chosen = [c for c in rows.values() if c.is_open or not open_only]
    return [funnel(data_dir, community, c.code, today=today, now=now) for c in sorted(chosen, key=lambda c: (-c.year, c.code))]


def line(f: dict[str, Any]) -> str:
    """A funnel in one line: asked, answered by channel, outstanding, unreachable. A count that could not be made says '-'."""
    def number(value: Any) -> str:
        return "-" if value is None else str(value)

    answered = f["answered"]
    by = (", ".join(f"{k} {v['answered']}" for k, v in answered["byChannel"].items() if v["answered"]) or "none") if answered else "-"
    return (f"asked {f['asked']['total']}" + (f" + {f['asked']['mailings']} mailing(s)" if f["asked"]["mailings"] else "")
            + f"; answered {number(answered['answered'] if answered else None)} ({by})"
            + f"; outstanding {number(f['outstanding']['count'])}; unreachable {number(f['unreachable']['count'])}")


__all__ = ["CHANNELS", "LEDGER", "age_hours", "attempts_of", "funnel", "funnels", "line", "moment_of", "mtime", "read_ledger",
           "unreachable_owners"]
