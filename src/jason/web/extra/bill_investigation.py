"""The investigation card (``GET /api/bill-investigation?tx=ID``) and the person's outcome
(``POST /api/write/bill-investigation/<tx>``; docs/console/handoff-mail-and-payment-attachments.md, Part C).

The read is disk only: the stored PayHOA snapshot, the profile's payee rows, the county tax catalog, the library, scanned mail,
Gmail headers, and the vendor ledgers (``jason.tasks.bill_investigation``). Amounts and payees are P1; a mailed letter and a
message's subject are P2, so an office that does not open P2 sees that a letter or message names the amount and nothing of it.

The write records the signer's outcome, append only (``jason.tasks.bill_outcomes``). It attaches nothing, approves nothing, and
calls no PayHOA: a person's word, with their name. Never while an admin views as someone else.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

Args = dict[str, str]
ACTING_REFUSED = "Viewing as {who} (admin view): an outcome is recorded in a person's own name. Go back to yourself first."


def _settings() -> Any:
    try:
        from jason.config import Settings

        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: the profile's own rules
        return None


def bill_investigation(args: Args) -> dict[str, Any]:
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.sources.offline import routing_registry
    from jason.tasks import bill_outcomes
    from jason.tasks.bill_investigation import investigate
    from jason.web import access

    viewer = access.signed_in()
    try:
        ident = int(args.get("tx") or "")
    except ValueError:
        raise ValueError("tx is a transaction's id") from None
    private = access.may_see(viewer, access.Level.P2, private=access.private_window() is not None)[0]
    if private:
        try:
            access.served(viewer, access.Level.P2, address="api/bill-investigation")
        except OSError:
            private = False                # an opening that cannot be logged is not served
    root, c = Path(_data_dir(None)), community()
    out = investigate(root, c, routing_registry(c, _settings(), root), ident, private=private)
    if out.get("found"):
        history = bill_outcomes.history(root, ident)
        out["history"], out["outcome"] = history, (history[-1] if history else None)
    return out


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/bill-investigation/<tx>`` with ``{outcome, doc?, note?}`` in the signer's name."""
    from flask import abort

    from jason.mcp.county import _data_dir
    from jason.tasks import bill_outcomes
    from jason.web import access

    viewer = access.signed_in()
    if viewer.acting:
        abort(access.refusal(403, ACTING_REFUSED.format(who=viewer.label)))
    ok, why = access.may_see(viewer, access.Level.P2)
    if not ok:
        abort(access.refusal(403, why))
    try:
        ident = int(key)
    except ValueError:
        raise ValueError("the key is a transaction's id") from None
    return bill_outcomes.record(Path(_data_dir(None)), ident, str(body.get("outcome") or ""), by=viewer.account,
                                note=str(body.get("note") or ""), doc=str(body.get("doc") or ""))


__all__ = ["bill_investigation", "write"]
