"""The person steps waiting on the viewer, by band (``GET /api/work-due[?within=DAYS]``; docs/workflows/person-steps.md, section 6;
docs/console/screens/work-guide.md, "Data").

The read side of the reminders, and nothing more: **nothing is sent, snoozed, or stored.** A reading of the runs on disk as they stand
today (the same dry resume the run page makes), through ``jason.workflows.nudge``'s bands: ``legal`` (a law clock due today or past),
``late``, ``date`` (a date the step needs and nobody has given), ``soon``, and ``stale`` (open a while, no clock). The three numbers
behind ``soon``, ``stale`` and the escalation delay are the proposals in ``nudge.DEFAULTS`` and are labeled so (``numbers.note``):
the board has not adopted them. No away or cover logic is applied; a step is the viewer's when one of their offices may act on it, or
(an ``anyone`` step) the run is theirs.

**Who.** The Work loaders' own gate (``jason.web.extra.work_scope.gate``): a signed-in person whose offices open P2, or an
administrator (who then reads the ``Visibility.ADMIN`` definitions alone). 401 signed out, 403 with ``access.may_see``'s sentence
otherwise. The owner view never reads it. Where console sign-in is not set up nobody is named, so nothing is "yours".

**What a row holds.** The run's own label (any email or phone masked), the definition, the step and its place, who holds it by
office, the band and its word, the date with its basis word, how far off, and, for a step that repeats per item, a count and the
earliest date. Never an item, an address, a subject, a name, or an answer. A claim is only whether it is the viewer's and stale. A
held run (a hearing, a delinquent account, a records request: CIV 4935(e)) is its general title, the band, and the date with its
basis word, even in the private view: opening one in full is the Work screen's act, and it is logged there. ``escalated`` lists what
is late (or legal) for another office and shown to the viewer's office: visibility, not a message.
"""

from __future__ import annotations

from typing import Any

from jason.tasks import step_guide
from jason.web.extra import work, work_guide, work_scope
from jason.workflows import nudge

Args = dict[str, str]

BANDS = (nudge.Band.LEGAL, nudge.Band.LATE, nudge.Band.DATE, nudge.Band.SOON, nudge.Band.STALE)
"""The bands a person is told of, most urgent first (``quiet`` is never listed)."""
CAVEATS = (
    "A reading, not a message: nothing here is sent to anyone, and reading a line does not silence it. Acting on the step does.",
    "The lead time, the open-a-while threshold, and the escalation delay are proposals the board has not adopted; a legal date is the "
    "law's and is never moved by them.",
    "Who holds a step comes from the offices on the roster. No cover or away period is applied.",
)
SIGN_IN = "Sign in to see the steps waiting on you."


def _row(r: dict[str, Any]) -> dict[str, Any]:
    """One step as the page shows it: the run's words, the step, the band, the date. Nothing that names an item or a matter."""
    claim = r.get("claim")
    items = r.get("items")
    return {
        "run": r["run"], "definition": r["definition"], "label": work._mask(r["runLabel"]), "held": r["held"], "step": r["step"],
        "n": r["n"], "title": r["title"], "holder": r["holder"], "band": r["band"], "word": r["word"], "due": r["due"],
        "days": r["days"], "basis": r["basis"], "basisLabel": r["basisLabel"], "legal": r["legal"], "proposed": r["proposed"],
        "dueLabel": "" if r["held"] else r.get("label", ""), "cite": "" if r["held"] else r.get("cite", ""),
        "openDays": r["openDays"], "escalatedTo": r["escalatedTo"], "escalatedWhy": "" if r["held"] else r["escalatedWhy"],
        "items": None if not items else {"total": items["total"], "notDone": items["notDone"], "earliest": items["earliest"] or None},
        "claim": None if not claim else {"mine": bool(claim.get("mine")), "stale": bool(claim.get("stale"))},
    }


def counts_of(rows: list[dict[str, Any]]) -> dict[str, int]:
    """The rows by band, and all of them."""
    out = {b.value: sum(1 for r in rows if r["band"] == b.value) for b in BANDS}
    out["total"] = len(rows)
    return out


def read(root: Any, day: Any, who: work.Who, scope: Any, *, within: int | None = None, readers: Any = None) -> dict[str, Any]:
    """The reading for ``who`` on ``day``. Pure of the request: the loader and the Today band call it."""
    problems: list[dict[str, str]] = []
    work._register(root, problems)
    base = {"found": True, "asOf": day.isoformat(), "viewer": {"roles": sorted(who.roles)}, "numbers": numbers(),
            "caveats": list(CAVEATS), "problems": problems}
    if not who.account:
        return {**base, "mine": [], "escalated": [], "counts": {**counts_of([]), "escalated": 0}, "bands": bands_of([]),
                "empty": SIGN_IN}
    report = step_guide.due_report(root, day, person=who.account, holders=work_guide.holders_now(), readers=readers,
                                   within=within, roles=who.roles, reads=scope.reads)
    mine = [_row(r) for r in report["mine"] if r["band"] != "quiet"]
    escalated = [_row(r) for r in report["escalated"]]
    return {**base, "mine": mine, "escalated": escalated, "counts": {**counts_of(mine), "escalated": len(escalated)},
            "bands": bands_of(mine), "empty": "" if mine or escalated else "No step waiting on you is due, late, or open a while."}


def numbers() -> dict[str, Any]:
    p = nudge.DEFAULTS
    return {"leadDays": p.lead_days, "afterHours": p.after_hours, "escalateAfterHours": p.escalate_after_hours, "adopted": p.adopted,
            "note": "" if p.adopted else nudge.PROPOSED_NOTE}


def bands_of(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each band with its digest word and its count, most urgent first."""
    return [{"key": b.value, "word": nudge.WORDS[b], "count": sum(1 for r in rows if r["band"] == b.value)} for b in BANDS]


def work_due(args: Args) -> dict[str, Any]:
    """``GET /api/work-due[?within=DAYS]``: the steps waiting on the viewer by band, then what is escalated to their office."""
    viewer = work._gate()
    who = work.who_is(viewer)
    scope = work_scope.scope_of(viewer)
    text = (args.get("within") or "").strip()
    try:
        within = int(text) if text else None
    except ValueError:
        raise ValueError("within is a number of days") from None
    if within is not None and within < 0:
        raise ValueError("within is a number of days")
    root, day = work._root(), work._today()
    return read(root, day, who, scope, within=within, readers=work._readers(root, day))


__all__ = ["BANDS", "CAVEATS", "counts_of", "numbers", "read", "work_due"]
