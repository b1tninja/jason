"""The control types: written once, for any association. Nothing here names an association, an office-holder, an amount,
or a provision. A floor in this catalog is what any association is held to (a payment needs at least one signer); the
floor a particular provision sets (its bylaws require two) is the control's own ``Basis.floor``.

``signers`` is capped at two because the approvals engine records a submitter and one confirmer; a control asking for
more is refused rather than half enforced.
"""

from __future__ import annotations

from jason.controls.types import (ControlFamily, ControlRefused, ControlType, Governs, GovernsKind, ParamKind,
                                  ParamSpec)

F, G, K = ControlFamily, GovernsKind, ParamKind

_SIGNERS = (
    ParamSpec("signers", K.COUNT, "How many people sign", maximum=2),
    ParamSpec("roles", K.ELIGIBLE, "Who may count as a signer (empty: any board member)"),
    ParamSpec("must_include", K.REQUIRED, "Offices that must be among the signers"),
    ParamSpec("over_cents", K.CENTS, "The amount above which the rule applies (empty: every amount)"),
)

CATALOG: tuple[ControlType, ...] = (
    ControlType(
        "payment-signers", "Payment signers", F.MONEY,
        (Governs(G.APPROVAL_KIND, "payment"), Governs(G.SPEND, "payment")), _SIGNERS, {"signers": 1},
        ("a bylaws section on who signs checks and drafts",)),
    ControlType(
        "reserve-signers", "Reserve withdrawal signers", F.MONEY,
        (Governs(G.APPROVAL_KIND, "reserve"), Governs(G.SPEND, "reserve")), _SIGNERS, {"signers": 1},
        ("a stricter rule for the reserve in the governing documents",)),
    ControlType(
        "contract-authorization", "Contract authorization", F.CONTRACTS,
        (Governs(G.WORKFLOW_STEP, "contract-signing"),),
        (ParamSpec("resolution_first", K.FLAG, "A board resolution on record before an officer signs"),
         ParamSpec("max_term_days", K.DAYS, "The longest contract term an officer may sign"),
         ParamSpec("max_cents", K.CENTS, "The largest contract an officer may sign")),
        {}, ("a provision that no officer binds the association without a resolution",)),
    ControlType(
        "limit-checks", "Limit checks", F.CONTRACTS,
        (Governs(G.WORKFLOW_STEP, "plan-limit"),),
        (ParamSpec("response", K.CHOICE, "What jason does when a plan passes the limit", options=("warn", "refuse")),
         ParamSpec("limit_cents", K.CENTS, "The spending limit"),
         ParamSpec("limit_days", K.DAYS, "The term limit")),
        {}, ("a limit on the board's powers in the governing documents",)),
    ControlType(
        "manager-spending-authority", "Manager spending authority", F.MONEY,
        (Governs(G.APPROVAL_KIND, "*"), Governs(G.SPEND, "manager")),
        (ParamSpec("over_cents", K.CENTS, "The amount above which the manager asks"),
         ParamSpec("asked", K.REQUIRED, "Offices that must approve past it")),
        {}, ("a provision that the board prescribes the manager's duties",)),
    ControlType(
        "review-cadence", "Review cadence", F.REVIEWS,
        (Governs(G.WORKFLOW_STEP, "review"),),
        (ParamSpec("every_days", K.DAYS, "How often the review is made"),
         ParamSpec("recorded_by", K.REQUIRED, "Offices that record the review"),
         ParamSpec("ratify", K.FLAG, "The board ratifies it at its next meeting")),
        {}, ("a review the documents or the law require of the board",)),
    ControlType(
        "delivery-class", "Delivery class", F.NOTICES,
        (Governs(G.SEND, "notice-letter"),),
        (ParamSpec("method", K.CHOICE, "The method a notice letter defaults to",
                   options=("standard", "first class", "certified")),),
        {}, ("a provision that a notice goes by a named method",)),
    ControlType(
        "recorder", "Recorder", F.MEETINGS,
        (Governs(G.WORKFLOW_STEP, "decision-record"),),
        (ParamSpec("recorded_by", K.REQUIRED, "Offices that record the board's decisions and notices given"),),
        {}, ("a provision on who keeps the records and gives the notices",)),
    ControlType(
        "second-person-confirmation", "Second-person confirmation", F.ONBOARDING,
        (Governs(G.APPROVAL_KIND, "*"), Governs(G.WORKFLOW_STEP, "intake-answer")),
        (ParamSpec("required", K.FLAG, "A second, distinct person confirms"),),
        {}, ("high-stakes answers at onboarding",)),
)


def get(key: str) -> ControlType:
    for t in CATALOG:
        if t.key == key:
            return t
    raise ControlRefused(f"no control type {key!r}: " + ", ".join(t.key for t in CATALOG))


def keys() -> tuple[str, ...]:
    return tuple(t.key for t in CATALOG)


__all__ = ["CATALOG", "get", "keys"]
