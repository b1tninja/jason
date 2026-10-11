"""The control types: written once, for any association. Nothing here names an association, an office-holder, an amount,
or a provision. A floor in this catalog is what any association is held to (a payment needs at least one signer); the
floor a particular provision sets (its bylaws require two) is the control's own ``Basis.floor``.

``signers`` is capped at two because the approvals engine records a submitter and one confirmer; a control asking for
more is refused rather than half enforced.

Each type may carry its ``evidence``: the general words of a provision that speak to it (``jason.controls.suggest`` reads
the governing documents with them). They are phrases of ordinary governing-document language ("shall be signed by"),
never a name, a citation, or a number of one association's. ``proposal`` is jason's proposal for the parameters, a
proposal and never a rule, and ``board_sets`` the parameters it leaves to the board: an amount or a period is never
invented.
"""

from __future__ import annotations

from jason.community.base import OfficerRole
from jason.controls.types import (ControlFamily, ControlRefused, ControlType, Cue, Evidence, FloorRead, Governs,
                                  GovernsKind, ParamKind, ParamSpec)

F, G, K = ControlFamily, GovernsKind, ParamKind

_SIGNERS = (
    ParamSpec("signers", K.COUNT, "How many people sign", maximum=2),
    ParamSpec("roles", K.ELIGIBLE, "Who may count as a signer (empty: any board member)"),
    ParamSpec("must_include", K.REQUIRED, "Offices that must be among the signers"),
    ParamSpec("over_cents", K.CENTS, "The amount above which the rule applies (empty: every amount)"),
)

# --- the words ---------------------------------------------------------------------------------------------------------
# A count a provision names next to the signing: "signed by two", "two signatures", "the signatures of two". The group n is
# the count; a number word or digits.
_N = r"(?P<n>one|two|three|four|five|\d+)"
_SIGN_COUNT = FloorRead("signers", (
    rf"\b(?:signed|countersigned|endorsed)\s+by\s+(?:at\s+least\s+|not\s+fewer\s+than\s+|any\s+|the\s+signatures?\s+of\s+)?{_N}\b(?!\s*(?:days?|%|percent))",
    rf"\b{_N}\s+(?:\(\d+\)\s+)?(?:signatures?|signers?)\b",
    rf"\bsignatures?\s+of\s+(?:at\s+least\s+|any\s+)?{_N}\b",
))

_IS_SIGNED = Cue("signed by", r"\b(?:signed|countersigned|endorsed)\s+by\b")
_THE_RESERVE = Cue("the reserve", r"\breserves?\b")
_SIGNING = Cue("signatures", r"\b(?:signatures?|signers?|signed\s+by|countersign\w*)\b")

CATALOG: tuple[ControlType, ...] = (
    ControlType(
        "payment-signers", "Payment signers", F.MONEY,
        (Governs(G.APPROVAL_KIND, "payment"), Governs(G.SPEND, "payment")), _SIGNERS, {"signers": 1},
        ("a bylaws section on who signs checks and drafts",),
        evidence=(Evidence(
            (Cue("checks, drafts, or orders for payment",
                 r"\b(?:checks?|drafts?|orders?\s+for\s+(?:the\s+)?payment|warrants?)\b"), _IS_SIGNED),
            unless=(_THE_RESERVE,), floor=(_SIGN_COUNT,)),),
        proposal={"signers": 2, "must_include": (OfficerRole.TREASURER,)}, board_sets=("over_cents",)),
    ControlType(
        "reserve-signers", "Reserve withdrawal signers", F.MONEY,
        (Governs(G.APPROVAL_KIND, "reserve"), Governs(G.SPEND, "reserve")), _SIGNERS, {"signers": 1},
        ("a stricter rule for the reserve in the governing documents",),
        evidence=(
            Evidence((_THE_RESERVE, Cue("withdrawal", r"\b(?:withdraw\w*|disburse\w*|expenditures?|transfers?)\b")),
                     floor=(_SIGN_COUNT,)),
            Evidence((_THE_RESERVE, _SIGNING), floor=(_SIGN_COUNT,)),
        ),
        proposal={"signers": 2}, board_sets=("must_include",)),
    ControlType(
        "contract-authorization", "Contract authorization", F.CONTRACTS,
        (Governs(G.WORKFLOW_STEP, "contract-signing"),),
        (ParamSpec("resolution_first", K.FLAG, "A board resolution on record before an officer signs"),
         ParamSpec("max_term_days", K.DAYS, "The longest contract term an officer may sign"),
         ParamSpec("max_cents", K.CENTS, "The largest contract an officer may sign")),
        {}, ("a provision that no officer binds the association without a resolution",),
        evidence=(Evidence((
            Cue("binds the association",
                r"\b(?:bind|binds|binding|obligate|obligates|commit)\b[^.]{0,80}\b(?:association|corporation|board)\b"
                r"|\b(?:enter\s+into|execute|sign)\b[^.]{0,40}\bcontracts?\b"),
            Cue("authorized by resolution",
                r"\b(?:authori[sz]ed|approved|directed)\s+(?:in\s+advance\s+)?(?:by|in|under)\s+(?:a\s+|an\s+|the\s+)?"
                r"(?:written\s+)?(?:resolution|vote|action)\b|\bresolution\b[^.]{0,60}\b(?:authori[sz]\w+|approv\w+)\b"
                r"|\bunless\s+(?:first\s+)?(?:authori[sz]ed|approved)\b")),),),
        proposal={"resolution_first": True}, board_sets=("max_term_days", "max_cents")),
    ControlType(
        "limit-checks", "Limit checks", F.CONTRACTS,
        (Governs(G.WORKFLOW_STEP, "plan-limit"),),
        (ParamSpec("response", K.CHOICE, "What jason does when a plan passes the limit", options=("warn", "refuse")),
         ParamSpec("limit_cents", K.CENTS, "The spending limit"),
         ParamSpec("limit_days", K.DAYS, "The term limit")),
        {}, ("a limit on the board's powers in the governing documents",),
        evidence=(Evidence((
            Cue("shall not have the power to",
                r"\b(?:shall|may|does|do|will)\s+not\s+have\s+(?:the\s+)?(?:power|authority)\b|\bhas?\s+no\s+(?:power|authority)\b"
                r"|\bshall\s+not\s+(?:have\s+the\s+)?(?:power|authority)\b|\bis\s+not\s+authori[sz]ed\s+to\b"),
            Cue("a term or an amount",
                r"(?:\b(?:term\s+(?:of|exceeding|longer)|exceed\w*|in\s+excess\s+of|more\s+than|greater\s+than|longer\s+than"
                r"|for\s+a\s+term|\d+\s*(?:years?|months?)|dollars?)\b|\$\s?\d)")),),),
        proposal={"response": "warn"}, board_sets=("limit_cents", "limit_days")),
    ControlType(
        "manager-spending-authority", "Manager spending authority", F.MONEY,
        (Governs(G.APPROVAL_KIND, "*"), Governs(G.SPEND, "manager")),
        (ParamSpec("over_cents", K.CENTS, "The amount above which the manager asks"),
         ParamSpec("asked", K.REQUIRED, "Offices that must approve past it")),
        {}, ("a provision that the board prescribes the manager's duties",),
        evidence=(Evidence((
            Cue("engage a manager",
                r"\b(?:engage|employ|hire|retain|appoint|contract\s+with)\b[^.]{0,80}\b(?:managing\s+agent|manager"
                r"|management\s+(?:company|firm|agent))\b|\b(?:managing\s+agent|manager|management\s+(?:company|firm))\b"
                r"[^.]{0,80}\b(?:engage\w*|employ\w*|hire\w*|retain\w*|appoint\w*)\b"),
            Cue("prescribe their duties",
                r"\bprescrib\w+\b[^.]{0,60}\bduties\b|\bduties\b[^.]{0,60}\b(?:prescrib\w+"
                r"|as\s+(?:the\s+)?board\s+(?:may\s+)?(?:determine|direct|fix|set))\b")),),),
        proposal={}, board_sets=("over_cents", "asked")),
    ControlType(
        "review-cadence", "Review cadence", F.REVIEWS,
        (Governs(G.WORKFLOW_STEP, "review"),),
        (ParamSpec("every_days", K.DAYS, "How often the review is made"),
         ParamSpec("recorded_by", K.REQUIRED, "Offices that record the review"),
         ParamSpec("ratify", K.FLAG, "The board ratifies it at its next meeting")),
        {}, ("a review the documents or the law require of the board",),
        evidence=(Evidence((
            Cue("shall review", r"\b(?:shall|must|will)\s+(?:\w+\s+){0,3}?(?:review|examine|inspect|audit)\b"),
            Cue("reconciliation", r"\breconcil\w+\b|\bbank\s+statements?\b"),
            Cue("a period",
                r"\b(?:daily|weekly|monthly|quarterly|semi-?annual\w*|annual\w*|yearly|each\s+(?:month|quarter|year)"
                r"|every\s+(?:month|quarter|year|\d+\s+days?))\b")),),),
        proposal={"ratify": True}, board_sets=("every_days", "recorded_by")),
    ControlType(
        "delivery-class", "Delivery class", F.NOTICES,
        (Governs(G.SEND, "notice-letter"),),
        (ParamSpec("method", K.CHOICE, "The method a notice letter defaults to",
                   options=("standard", "first class", "certified")),),
        {}, ("a provision that a notice goes by a named method",),
        evidence=(Evidence((
            Cue("a notice", r"\bnotices?\b"),
            Cue("a named method",
                r"\b(?:first[- ]class(?:\s+mail)?|certified\s+mail|registered\s+mail|return\s+receipt(?:\s+requested)?"
                r"|personal(?:ly)?\s+deliver\w*|electronic\s+(?:transmission|mail)|e-?mail)\b"),
            Cue("delivery", r"\b(?:deliver\w*|mail\w*|sent|served|given)\b")),),),
        proposal={}, board_sets=("method",)),
    ControlType(
        "recorder", "Recorder", F.MEETINGS,
        (Governs(G.WORKFLOW_STEP, "decision-record"),),
        (ParamSpec("recorded_by", K.REQUIRED, "Offices that record the board's decisions and notices given"),),
        {}, ("a provision on who keeps the records and gives the notices",),
        evidence=(
            Evidence((Cue("shall keep", r"\b(?:shall|must)\s+(?:keep|record|prepare|maintain|have\s+charge\s+of"
                                        r"|be\s+responsible\s+for)\b"),
                      Cue("minutes", r"\bminutes\b"))),
            Evidence((Cue("give notice", r"\b(?:shall|must)\s+(?:cause\s+to\s+be\s+)?give\b[^.]{0,40}\bnotices?\b"
                                         r"|\bgive\s+(?:all\s+|written\s+)?notices?\b|\bnotices?\b[^.]{0,60}\bshall\s+be\s+given\b"),
                      Cue("of meetings", r"\b(?:meetings?|board|directors)\b"))),
        ),
        proposal={"recorded_by": (OfficerRole.SECRETARY,)}, board_sets=()),
    ControlType(
        "second-person-confirmation", "Second-person confirmation", F.ONBOARDING,
        (Governs(G.APPROVAL_KIND, "*"), Governs(G.WORKFLOW_STEP, "intake-answer")),
        (ParamSpec("required", K.FLAG, "A second, distinct person confirms"),),
        {}, ("high-stakes answers at onboarding",)),
)

# --- apply preferences ---------------------------------------------------------------------------------------------------
# How a board wants a signed plan applied (docs/console/approval-clarity.md, section 5). They are adopted like a control: the
# same record, the same act log, an effective date, a history. They are not safeguards, so they are not in ``CATALOG``: they
# never touch who signs or how many, no suggestion reads the documents for them, and ``jason.controls.apply_prefs`` holds
# the floors (the console never applies a kind that is terminal-only, costs money, or sends mail). Defaults hold until one is
# adopted: terminal only, any board member or the manager, no pause, no typed count, a reminder after 24 hours.
# The shape is the same everywhere: a CHOICE lists its values weakest first, so the later value is the stricter.

_APPLY = (Governs(G.APPLY, "signed plan"),)

PREFERENCES: tuple[ControlType, ...] = (
    ControlType(
        "where-apply", "Where a signed plan is applied", F.APPLYING, _APPLY,
        (ParamSpec("where", K.CHOICE, "Where apply happens", options=("console", "terminal")),), {},
        ("the board's choice of where a signed plan is applied",), board_sets=("where",)),
    ControlType(
        "who-may-apply", "Who may apply a signed plan", F.APPLYING, _APPLY,
        (ParamSpec("who", K.CHOICE, "Who may apply",
                   options=("board_or_manager", "any_signer", "not_signer")),), {},
        ("the board's choice of who applies a signed plan",), board_sets=("who",)),
    ControlType(
        "pause-before-apply", "A pause before a signed plan is applied", F.APPLYING, _APPLY,
        (ParamSpec("minutes", K.COUNT, "Minutes to wait after the last signature", maximum=14 * 24 * 60),
         ParamSpec("until_next_day", K.FLAG, "Wait until the next day")), {},
        ("the board's choice to pause between the last signature and apply",), board_sets=("minutes", "until_next_day")),
    ControlType(
        "typed-count-over", "A typed count for a large plan", F.APPLYING, _APPLY,
        (ParamSpec("over", K.CEILING, "Above this many changes the person applying types the count", maximum=100000),),
        {}, ("the board's choice to have a large plan's count typed at apply",), board_sets=("over",)),
    ControlType(
        "reminder-hours", "A reminder for a signed plan", F.APPLYING, _APPLY,
        (ParamSpec("hours", K.CEILING, "Hours after the last signature when the reminder is due", minimum=1, maximum=24 * 90),
         ParamSpec("off", K.FLAG, "No reminder")), {},
        ("the board's choice of when a signed plan that waits is called out",), board_sets=("hours", "off")),
)


def get(key: str) -> ControlType:
    for t in (*CATALOG, *PREFERENCES):
        if t.key == key:
            return t
    raise ControlRefused(f"no control type {key!r}: " + ", ".join(t.key for t in (*CATALOG, *PREFERENCES)))


def keys() -> tuple[str, ...]:
    return tuple(t.key for t in CATALOG)


__all__ = ["CATALOG", "PREFERENCES", "get", "keys"]
