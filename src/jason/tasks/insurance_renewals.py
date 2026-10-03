"""The board's renewal decision on each insurance policy, recorded once beside the policy's facts.

``insurance_review`` reads the policy sheet, the mail, and PayHOA's premiums; it says where each term stands. What
the board decided about the next term is not in any of those stores, so it is written here, in jason's own
``data/insurance/renewals.json``, one record per policy number: the decision in a closed set of words, the day
decided, who recorded it, the premium quoted when known, and whether the coverage changes. A change in coverage
(a reduced limit, a higher deductible, a lapse) calls for individual notice to the members as soon as reasonably
practical (Civil Code 5810); the record flags that the notice is needed and computes no date, since the statute sets
none. jason buys, renews, cancels, and claims nothing: it records the board's decision with its agent.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

STORE = Path("insurance") / "renewals.json"
NOTICE_AUTHORITY = "CIV 5810"


class RenewalDecision(Enum):
    RENEW_AS_QUOTED = "renew as quoted"
    RENEW_WITH_CHANGES = "renew with changes"
    RE_BID = "re-bid"
    CHANGE_CARRIER = "change carrier"
    LET_LAPSE = "let lapse"


DECISIONS = tuple(d.value for d in RenewalDecision)
# The decisions that are themselves a change in coverage the members hear of (5810), whatever the limits do.
NOTICE_DECISIONS = (RenewalDecision.LET_LAPSE.value,)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(data_dir: Path) -> dict[str, dict[str, Any]]:
    """The recorded decisions by policy number; none when the store is absent."""
    path = Path(data_dir) / STORE
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8")).get("renewals", {})
    return dict(raw) if isinstance(raw, dict) else {}


def save(data_dir: Path, items: dict[str, dict[str, Any]]) -> Path:
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"savedAt": _now(), "renewals": items}, indent=1), encoding="utf-8")
    return path


def notice_needed(decision: str, limits_changed: bool) -> bool:
    """Whether the decision is a change in coverage the members must hear of (CIV 5810)."""
    return bool(limits_changed) or decision in NOTICE_DECISIONS


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "insurance-renewals", timeout=60, purpose=f"insurance renewals: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


@_store_lock
def record(data_dir: Path, number: str, *, decision: str, decided_on: str, by: str, premium_cents: int | None = None,
           limits_changed: bool = False, note: str = "") -> dict[str, Any]:
    """Record the board's decision on policy ``number``, or replace the one recorded. The words are the board's."""
    number, by, note = str(number).strip(), str(by).strip(), str(note or "").strip()
    decision = str(decision).strip().lower()
    if not number:
        raise ValueError("a renewal decision names the policy number")
    if decision not in DECISIONS:
        raise ValueError(f"decision is one of {', '.join(DECISIONS)}")
    if not by:
        raise ValueError("the decision names who recorded it")
    day = date.fromisoformat(str(decided_on).strip())
    if premium_cents is not None:
        if isinstance(premium_cents, bool) or not isinstance(premium_cents, int):
            raise ValueError("premiumCents is integer cents")
        if premium_cents < 0:
            raise ValueError("premiumCents is not negative")
    if not isinstance(limits_changed, bool):
        raise ValueError("limitsChanged is true or false")
    items = load(data_dir)
    now = _now()
    earlier = items.get(number)
    history = list((earlier or {}).get("history", [])) + [f"{now[:10]}: {'re-recorded' if earlier else 'recorded'} {decision} by {by}"]
    if earlier and earlier.get("decision") != decision:
        history[-1] += f" (was {earlier.get('decision')})"
    items[number] = {
        "number": number, "decision": decision, "decidedOn": day.isoformat(), "by": by, "premiumCents": premium_cents,
        "limitsChanged": limits_changed, "memberNoticeNeeded": notice_needed(decision, limits_changed),
        "noticeAuthority": NOTICE_AUTHORITY if notice_needed(decision, limits_changed) else "",
        "note": note, "recorded": now, "history": history,
    }
    save(data_dir, items)
    return items[number]
