"""The records-requests source and its write: a member's Civil Code 5200 request and the decisions a person recorded.

``records_requests(args)`` lists every request with its section 5210 clock as stages and its standing (open,
produced, overdue), or one with ``?id=``; ``?today=`` fixes the day the standing is read against. It also carries
the record kinds from ``records_inventory()`` for the form's choices, falling back to the statute's list when that
tool cannot read the shelf. ``write("", body)`` opens a request; ``write(id, body)`` records a decision on it.
Reads and writes jason's own store only (``data/records-requests/requests.json``).

**Who the record names.** Where console sign-in is set up, a decision is the signed-in person's: the roster person whose
offices open P2, never an admin viewing as someone else, and the name recorded is the account's, whatever ``by`` the body
carries. A request opened by a member through the owner view names no person (``MEMBER_BY``) when nobody is signed in; a
signed-in person's own name when one is. Where sign-in is not set up (the loopback default), and outside a request (a
script, a test), the caller is the person at the machine and the body's ``by`` is kept as typed.

**The fee and the words.** The read carries ``rule`` (``jason.tasks.records_fee.rule``): the stored words of CIV 5205(f) and
(g) and of the membership list's 5210(b)(6) and CORP 8330, each as stored, with jason's reading labeled. Each request with a
fee carries ``feeCheck``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from jason.community.records import CITATION
from jason.community.symbols import AssociationRecord
from jason.tasks import records_requests as store

Args = dict[str, str]

MEMBER_BY = "the member, through the owner view"
ACTING_REFUSED = "Viewing as {who} (admin view): a decision is recorded in a person's own name. Go back to yourself first."

CAVEATS = (
    "The manager decides, with counsel where needed, whether a stated purpose is reasonably related to the member's interest as a member (CIV 5225) and what is withheld or redacted and on what basis (CIV 5215). jason records those decisions; it makes none.",
    "jason prepares the membership list with opt-outs removed (CIV 5220). It does not hand the list to anyone; a person produces it.",
    "The member's purpose is quoted as given. It is not paraphrased, scored, or completed.",
    "Business-day deadlines count Monday through Friday with no holidays subtracted, and the fiscal year is read as the calendar year; a person checks the calendar before relying on a date.",
    "The membership list's date is jason's own count of five business days, computed for a person to check. CIV 5210(b)(6) gives the timeframe as the one in Corporations Code section 8330, which counsel reads.",
    "CIV 5205(g) states a dollar rate per hour and a dollar total for redacting an enhanced association record, and none for copying and mailing. jason compares a recorded redaction charge with those figures, refuses one above them, and lowers no figure; whether the time was actually and reasonably spent, and whether the member agreed first, are for a person.",
)

_LABELS = {
    AssociationRecord.FINANCIAL_DISCLOSURE: "Financial disclosures (budget report, policy statement)",
    AssociationRecord.TRANSFER_FINANCIAL: "Transfer and escrow financial documents",
    AssociationRecord.INTERIM_FINANCIAL: "Interim financial statements",
    AssociationRecord.EXECUTED_CONTRACT: "Executed contracts",
    AssociationRecord.VENDOR_APPROVAL: "Vendor and contractor approvals",
    AssociationRecord.TAX_RETURN: "Tax returns",
    AssociationRecord.RESERVE_ACCOUNT: "Reserve account balances and records",
    AssociationRecord.MINUTES: "Minutes of member, board, and committee meetings",
    AssociationRecord.MEMBERSHIP_LIST: "Membership list",
    AssociationRecord.CHECK_REGISTER: "Check registers",
    AssociationRecord.GOVERNING_DOCUMENTS: "Governing documents",
    AssociationRecord.RESERVE_LITIGATION_ACCOUNTING: "Accounting of reserve funds used for litigation",
    AssociationRecord.ENHANCED: "Enhanced records (invoices, statements, canceled checks, reimbursements)",
    AssociationRecord.ELECTION_MATERIALS: "Election materials",
    AssociationRecord.ELEVATED_ELEMENT_REPORT: "Exterior elevated element inspection report",
}


def _signer(*, board: bool) -> tuple[Any, bool]:
    """``(viewer, set_up)``: whether console sign-in is set up for this request, and the signed-in viewer when it is. Outside
    a request, or where sign-in is not set up (the loopback default), ``(None, False)``: the caller is the person at the machine.
    ``board``: the offices must open P2, and a signed-out request is a 401. An admin viewing as someone else may not write."""
    from flask import abort, current_app, has_request_context

    from jason.web import access

    if not has_request_context():
        return None, False
    sign_in = current_app.extensions.get("jason_sign_in")
    if sign_in is None or not getattr(sign_in, "configured", False):
        return None, False
    viewer = access.signed_in() if board else access.current_viewer()
    if viewer is None:
        return None, True
    if viewer.acting:
        abort(access.refusal(403, ACTING_REFUSED.format(who=viewer.label)))
    if board:
        access.allow(viewer, access.Level.P2)
    return viewer, True


def _root():
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def record_kinds() -> tuple[list[dict[str, Any]], str]:
    """The record kinds a member may ask for, each with its citation and, when the shelf can be read, its meaning,
    retention, and how many files the catalog holds. A failed inventory is a note, not an error."""
    kinds = [{"record": k.value, "label": _LABELS.get(k, k.value.replace("_", " ")), "citation": c, "meaning": "", "retention": "", "files": None, "gap": ""}
             for k, c in CITATION.items()]
    note = ""
    try:
        from jason.mcp.county import records_inventory

        by_kind = {r.get("record"): r for r in records_inventory().get("records", [])}
    except Exception as exc:  # the shelf is a convenience here; the statute's list stands on its own
        by_kind = {}
        note = f"records inventory unavailable ({type(exc).__name__}); kinds listed from the statute alone"
    for row in kinds:
        inv = by_kind.get(row["record"])
        if inv:
            row.update(meaning=inv.get("meaning", ""), retention=inv.get("retention", ""), files=inv.get("files"), gap=inv.get("gap", ""))
    return kinds, note


def records_requests(args: Args) -> dict[str, Any]:
    today = date.fromisoformat(args["today"]) if args.get("today") else None
    from jason.tasks import records_fee

    root = _root()
    kinds, note = record_kinds()
    rule = records_fee.rule()
    if args.get("id"):
        req = store.get(root, args["id"])
        return {"found": True, "request": store.as_dict(req, today), "kinds": kinds, "note": note, "caveats": list(CAVEATS), "rule": rule}
    rows = [store.as_dict(r, today) for r in store.load(root)]
    rows.sort(key=lambda r: r["receivedOn"], reverse=True)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["standing"]] = counts.get(r["standing"], 0) + 1
    return {"found": True, "count": len(rows), "counts": counts, "requests": rows, "kinds": kinds, "vias": list(store.VIAS),
            "note": note, "caveats": list(CAVEATS), "rule": rule}


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """"" or "new": open a request from the body (receivedOn, unit, via, records, purpose, years, by). An id: record
    the decisions in the body on that request."""
    root = _root()
    opening = key in ("", "new")
    viewer, set_up = _signer(board=not opening)
    if viewer is not None:
        by = viewer.account
    elif set_up:
        by = MEMBER_BY                     # sign-in is set up and nobody is signed in: a member's own request names no person
    else:
        by = str(body.get("by", "") or "")
    if opening:
        req = store.open_request(root, body.get("receivedOn", ""), body.get("unit", ""), body.get("via", ""),
                                 body.get("records") or [], body.get("purpose", ""), body.get("years") or [], by,
                                 delivery=str(body.get("delivery", "") or ""))
    else:
        changes = {k: v for k, v in body.items() if k != "by"}
        if viewer is not None or "by" in body:
            changes["by"] = by
        req = store.decide(root, key, **changes)
    return store.as_dict(req)
