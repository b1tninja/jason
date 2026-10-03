"""Reserve findings: each borrowing as ``reserve_transfers`` reads it, with the board's recorded finding beside its
documents and gaps.

Reads disk only. Only the board's resolution says which loan a payment restored; whether the statute was met is the
board's call.
"""

from __future__ import annotations

from typing import Any

from jason.tasks import reserve_findings as store

Args = dict[str, str]

CAVEATS = (
    "A match by amount is a lead: only the board's resolution says which loan a payment restored.",
    "Whether Civil Code 5515 was met is the board's call. The finding recorded here is what a person entered in the board's words; jason decides nothing.",
)


def finding_needed(borrowing: dict[str, Any], recorded: dict[str, Any] | None) -> bool:
    """A borrowing whose gaps name a missing finding, with no finding recorded here."""
    return recorded is None and any("finding" in str(g).lower() for g in borrowing.get("gaps") or [])


def reserve_findings(args: Args) -> dict[str, Any]:
    """The borrowings with each one's key and recorded finding, flagged ``findingNeeded`` when the library shows the
    finding missing and none is recorded."""
    from jason.mcp.county import _data_dir, reserve_transfers

    out = reserve_transfers()
    recorded = store.load(_data_dir(None))
    rows = []
    for b in out.get("borrowings", []):
        key = store.key_of(b)
        found = recorded.get(key)
        rows.append({**b, "key": key, "finding": found, "findingNeeded": finding_needed(b, found)})
    return {**out, "borrowings": rows, "kinds": list(store.KINDS), "needed": sum(1 for r in rows if r["findingNeeded"]),
            "caveats": list(out.get("caveats") or []) + list(CAVEATS)}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record the board's finding on borrowing ``key`` (``<day>|<number>``): finding, kind, madeOn, by, meeting."""
    from jason.mcp.county import _data_dir

    return store.record(_data_dir(None), key, finding=str(body.get("finding", "")), kind=str(body.get("kind", "")),
                        made_on=str(body.get("madeOn", "")), by=str(body.get("by", "")), meeting=str(body.get("meeting", "")))
