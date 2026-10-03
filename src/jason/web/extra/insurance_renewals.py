"""Insurance renewals: each policy as ``insurance_review`` reads it, with the board's recorded decision beside it.

Reads disk only. The renewal is the board's decision with its agent; jason buys, renews, cancels, and claims nothing.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from jason.tasks import insurance_renewals as store

Args = dict[str, str]
WINDOW_DAYS = 90

CAVEATS = (
    "The renewal is the board's decision with its agent: jason buys, renews, cancels, and claims nothing. The record here is what a person entered.",
    f"A change in coverage (a reduced limit, a higher deductible, a lapse) calls for individual notice to the members as soon as reasonably practical ({store.NOTICE_AUTHORITY}); the flag says the notice is needed and sets no date.",
)


def _days(term_end: Any, today: date) -> int | None:
    try:
        return (date.fromisoformat(str(term_end)[:10]) - today).days
    except (TypeError, ValueError):
        return None


def insurance_renewals(args: Args) -> dict[str, Any]:
    """The policies with each one's recorded renewal decision, ``termEnd`` as the clock, and ``renewalWindow`` when the
    term ends within ninety days (or has ended)."""
    from jason.mcp.county import _data_dir, insurance_review

    review = insurance_review()
    today = date.fromisoformat(args["today"]) if args.get("today") else date.today()
    recorded = store.load(_data_dir(None))
    policies = []
    for p in review.get("policies", []):
        number = str(p.get("number", ""))
        days = _days(p.get("termEnd"), today)
        decision = recorded.get(number)
        policies.append({**p, "key": number, "renewal": decision, "daysToTermEnd": days,
                         "renewalWindow": days is not None and days <= WINDOW_DAYS,
                         "memberNoticeNeeded": bool(decision and decision.get("memberNoticeNeeded"))})
    return {**review, "today": today.isoformat(), "policies": policies, "decisions": list(store.DECISIONS), "windowDays": WINDOW_DAYS,
            "caveats": list(review.get("caveats") or []) + list(CAVEATS)}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record the board's decision on policy ``key`` (its number): decision, decidedOn, by, premiumCents, limitsChanged, note."""
    from jason.mcp.county import _data_dir

    premium = body.get("premiumCents")
    return store.record(_data_dir(None), key, decision=str(body.get("decision", "")), decided_on=str(body.get("decidedOn", "")),
                        by=str(body.get("by", "")), premium_cents=None if premium in (None, "") else premium,
                        limits_changed=body.get("limitsChanged", False), note=str(body.get("note", "") or ""))
