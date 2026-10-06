"""Follow-ups and campaign status, read from disk (docs/followups-design.md).

Two tools for the board profile. ``followups`` is what is overdue, due today, and coming up: dated actions for a person (remind
the owners who have not answered, the day answers must be entered in the books, resend a bounced notice by mail, read or confirm
an arrival, answer a request on its clock), each with its basis (law with its citation, the documents, a proposed policy
labeled proposed, or a person's own), the count outstanding, the command, and the age of its source. ``campaign_status`` is one
campaign's funnel (or each campaign's): asked, answered by the way each came in, read, confirmed, recorded, outstanding by owner
(an owner who answered by any method is not on it), and unreachable (no delivery reached them), each with the age of its source
and, for a source that is missing, why.

Neither calls Gmail, PayHOA, Google, or Keeper, and neither writes. They read what ``jason responses --check`` and ``jason
notices KEY --sync`` last kept. Names and units only: no address, email, phone, or answer is ever in the output. A miss carries
its reason, never an exception.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

LIVE_LINE = ("this reads what the last check and the last sync kept; `jason responses --check` and `jason notices KEY --sync` "
             "are the live reads")
CAVEATS = (
    "A follow-up is a dated action for a person. jason works it out from what is on disk and sends nothing, resends nothing, "
    "and completes nothing: each is a person's act, and each command shown is a dry run until a person adds --yes.",
    "Where the law and the documents are silent, a number is proposed policy and says so (basis `proposed policy`): the board "
    "adopts it, and jason never makes a rule. A date counted from a proposed number carries a `dueNote`.",
    "No count without its age: " + LIVE_LINE + ". The ages say how old each source is, and a source that is missing says so.",
    "Outstanding is by owner and unit, and an owner who answered by any method (PayHOA, email, mail, a Google Form, or keyed by "
    "a person) is not on it. An owner no delivery reached is unreachable, listed apart, never counted as outstanding.",
    "Names and units only: an email address, phone number, mailing address, or an owner's answer is never stored or shown here.",
)


def _root(data_dir: Path | None) -> Path:
    from jason.config import Settings

    return Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent


def _today() -> date:
    return date.today()


def _mask(value: Any) -> Any:
    from jason.approvals.audit import mask

    return mask(value, addresses=False)


def _miss(reason: str, **more: Any) -> dict[str, Any]:
    return {"found": False, "reason": reason, **more, "note": LIVE_LINE, "caveats": list(CAVEATS)}


def _community() -> Any:
    from jason.community import community

    return community()


def followups(days: int = 30, campaign: str = "", kind: str = "", state: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """What do we do next, and when? The association's follow-ups, in date order: what is overdue, due today, and due in the
    next ``days`` days (30 by default), each with its kind (remind, return-by, enter-by, reports-mailed, resend, acknowledge,
    review, decide, answer-due, close, manual), what to do, the basis (law with its citation, the documents, a proposed policy
    labeled proposed, or a person's own), the count still outstanding with the owners' names and units, the command a person
    runs, its state (upcoming, due, overdue, done, deferred, dropped; who changed it and why), and how old the source is. Filter
    by ``campaign`` (its code), ``kind``, or ``state`` (a state shows every date). Derived from the campaigns' cycles, the notice
    ledger, the response inbox, and a request's clocks, plus a person's own items; reads disk only and sends, resends, and
    completes nothing. Names and units only. Read-only; repeat the caveats."""
    try:
        from jason.tasks import followups as fu

        root = _root(data_dir)
        today = _today()
        reach = max(0, int(days or 0))
        try:
            found = fu.items(root, _community(), today=today)
            shown = fu.select(found, today=today, within=reach, campaign=(campaign or "").strip(), kind=(kind or "").strip(),
                              state=(state or "").strip())
        except fu.FollowUpError as exc:
            return _miss(exc.reason)
        known = fu.ages(root, _community(), today=today)
        sources = {k: {kk: vv for kk, vv in v.items() if kk != "reason" or vv} for k, v in known.items() if isinstance(v, dict)}
        if not shown:
            gaps = [v["reason"] for v in known.values() if isinstance(v, dict) and v.get("reason") and not v.get("exists", True)]
            return _miss(f"no follow-up matches as of {today.isoformat()} (overdue, due today, or due within {reach} days"
                         + "".join(f"; {k} {v}" for k, v in (("campaign", campaign), ("kind", kind), ("state", state)) if v)
                         + f"); {len(found)} follow-up(s) in all"
                         + (": " + "; ".join(gaps) if gaps else ""), count=0, items=[], asOf=today.isoformat(), ages=sources)
        counts: dict[str, int] = {}
        for i in shown:
            counts[i.state.value] = counts.get(i.state.value, 0) + 1
        rows = [{**i.to_json(), "sourceAge": fu.source_age(i, known)} for i in shown]
        return {"found": True, "asOf": today.isoformat(), "within": reach, "count": len(rows), "counts": counts,
                "items": _mask(rows), "ages": _mask(sources), "note": LIVE_LINE, "caveats": list(CAVEATS)}
    except Exception as exc:  # noqa: BLE001 - a reader that fails is an answer, not a traceback
        return _miss(f"the follow-ups could not be read: {_mask(f'{type(exc).__name__}: {exc}')}")


def campaign_status(code: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """How is a request campaign going? For the campaign named by ``code`` (or each campaign when it is empty): the form and
    cycle, the funnel by the way answers came in (asked: copies sent by channel; answered: PayHOA, email, mail, a Google Form,
    or keyed by a person, each with how many were read, confirmed, and recorded), who is outstanding by owner and unit (an
    owner who answered by any method is not on it), who is unreachable (every delivery failed, per the notice ledger: listed
    apart, never counted as outstanding), the next follow-up, and the age of each source; a source that is missing says so with
    its reason, and a count that cannot be made is null, never a bare zero. Reads disk only. Names and units only. Read-only;
    repeat the caveats."""
    try:
        from jason.tasks import campaign_funnel, campaigns
        from jason.tasks import followups as fu

        root = _root(data_dir)
        today = _today()
        community = _community()
        held = campaigns.view(root, community)
        want = (code or "").strip().upper()
        if want and want not in held:
            return _miss(f"no campaign {code!r}; the campaigns are " + (", ".join(sorted(held)) or "none (a person opens one: "
                         "`jason campaigns --open`)"), campaigns=sorted(held))
        if not held:
            return _miss("no campaign is recorded (data/forms/campaigns.json), and the profile's requests name none: nothing "
                         "has been asked of owners yet (`jason campaigns --open FORM --channel C --cycle-year Y --by NAME`)",
                         campaigns=[])
        coming = [i for i in fu.items(root, community, today=today) if i.open]
        out = []
        for c in sorted(held.values(), key=lambda c: (-c.year, c.code)):
            if want and c.code != want:
                continue
            f = campaign_funnel.funnel(root, community, c.code, today=today)
            nxt = next((i for i in coming if c.code in (i.campaign.upper(), i.subject.upper())), None)
            out.append({**f, "nextFollowUp": nxt.to_json() if nxt is not None else None})
        return {"found": True, "asOf": today.isoformat(), "count": len(out), "campaigns": _mask(out), "note": LIVE_LINE,
                "caveats": list(CAVEATS)}
    except Exception as exc:  # noqa: BLE001 - a reader that fails is an answer, not a traceback
        return _miss(f"the campaigns could not be read: {_mask(f'{type(exc).__name__}: {exc}')}")


TOOLS = (followups, campaign_status)
