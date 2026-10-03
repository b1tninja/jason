"""The delinquency page: each account's standing from the ledger and liens, with the board's recorded steps beside it.

The loader joins ``association_collections`` (the standing, the balance, the lien, and the statute's next step) to the
steps the board recorded in ``tasks.collection_steps``. The write appends one step. jason records the board's step; it
submits an account to no collection agency, records no lien, and forecloses on nothing. Executive session (Civil Code
4935): for directors.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

CAVEATS = (
    "Executive session (Civil Code 4935): for directors. jason records the board's step; it submits an account to no collection agency, records no lien, and forecloses on nothing.",
    "The next step beside each account is the statute's, read from the ledger and the liens; the recorded step is the board's.",
    "A lien is recorded only after a majority of the board votes for it in an open meeting, by roll call, recorded in the minutes (Civil Code 5673).",
    "The ledger's past-due figure can include late charges and fees the 5720 foreclosure floor excludes.",
)


def delinquency(args: Args) -> dict[str, Any]:
    """The accounts from ``association_collections``, each with the steps recorded on its parcel (all, and the latest)."""
    from jason.mcp.county import _data_dir, association_collections
    from jason.tasks import collection_steps as store

    out = association_collections()
    recorded = store.load(_data_dir(None))
    rows = []
    for row in out.get("rows", []) or []:
        steps = recorded.get(str(row.get("apn", "")), [])
        rows.append({**row, "steps": steps, "latestStep": steps[-1] if steps else None})
    seen = {str(r.get("apn", "")) for r in rows}
    orphans = [{"apn": apn, "steps": steps, "latestStep": steps[-1]} for apn, steps in recorded.items() if apn not in seen and steps]
    return {**out, "rows": rows, "recordedOnly": orphans, "steps": list(store.STEPS), "lienStep": store.Step.LIEN_RECORDED.value,
            "rollCall": store.ROLL_CALL_REMINDER, "caveats": [*CAVEATS, *([out["note"]] if out.get("note") else [])]}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Record one step the board took on parcel ``key``: ``step``, ``decidedOn``, ``by``, ``vote`` (empty or ayes-noes), ``note``."""
    from jason.mcp.county import _data_dir
    from jason.tasks.collection_steps import record_step

    return record_step(_data_dir(None), key, step=str(body.get("step", "")), decided_on=str(body.get("decidedOn", "")),
                       by=str(body.get("by", "")), vote=str(body.get("vote", "") or ""), note=str(body.get("note", "") or ""))
