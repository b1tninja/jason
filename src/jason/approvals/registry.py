"""The action kinds: each write jason can plan for a person's approval is a row, not a branch.

A kind declares how to plan (a read-only function returning the items and the live state they rest on), how to apply
the approved items, its approver rule, and its cost. Adding a ``--yes`` path to the approvals means adding a row with
a planner and an applier that call the task functions the CLI already calls (docs/console/approval-workflow.md).

``planner(live, scope) -> engine.Planned`` reads and never writes. ``applier(live, planned, items, recorder)``
performs only ``items`` (the approved ones, from the re-plan) and reports each one through ``recorder``.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from jason.locks import Resource


class Risk(Enum):
    R0 = "local"
    R1 = "private outside jason"
    R2 = "member-facing record"
    R3 = "irreversible, costly, or legal"


class Approver(Enum):
    ONE_PERSON = "one person"        # one named person decides and submits; a high-stakes item still needs a second
    TWO_PERSON = "two person"        # a second, distinct person signs the same fingerprint before any apply


@dataclass(frozen=True)
class ActionKind:
    key: str                          # "owner-info-tags"
    title: str
    cli: str                          # the command it stands beside
    system: str                       # "payhoa", "google", "zoom", "local": what the live read needs
    resource: Resource                # the lock held during apply
    risk: Risk
    approver: Approver
    reversible: str
    planner: str | Callable[..., Any]  # dotted "module:function", or the function
    applier: str | Callable[..., Any]
    cost: str = ""                    # how its cost is shown; "" when it has none
    clock: str = ""                   # the clock it serves
    rule: str = ""                    # the rule that authorizes it, where one does
    max_age_hours: int = 24           # an approval older than this is planned again before apply
    default_scope: dict[str, Any] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()
    # what the kind moves, for the controls scoped to all: "payment" (it pays or commits the association's money) or
    # "reserve" (it moves reserve funds). Empty for a kind that moves no money (docs/controls.md, section 7).
    categories: tuple[str, ...] = ()
    # A kind whose write only a person at a terminal makes: the engine's apply refuses it unless the caller is that
    # command (``Live.terminal``), so ``jason approvals apply`` and jason-web never run it. ``cli`` names the command.
    terminal_only: bool = False
    # What the kind sends to people when it is applied, in words ("" when it sends nothing): a mailed letter, an email.
    # A kind that sends is never applied from the console, whatever a board prefers (jason.controls.apply_prefs).
    sends: str = ""

    @property
    def has_sends(self) -> bool:
        return bool(self.sends)

    @property
    def terminal_note(self) -> str:
        return (f"{self.key} is applied by a person at a terminal: {self.cli}; neither jason-web nor "
                "`jason approvals apply` runs it")

    @property
    def has_cost(self) -> bool:
        return bool(self.cost)

    def plan(self, live: Any, scope: dict[str, Any]) -> Any:
        return _resolve(self.planner)(live, scope)

    def apply(self, live: Any, planned: Any, items: list[Any], recorder: Any) -> None:
        _resolve(self.applier)(live, planned, items, recorder)


def _resolve(ref: str | Callable[..., Any]) -> Callable[..., Any]:
    if callable(ref):
        return ref
    module, _, name = ref.partition(":")
    return getattr(importlib.import_module(module), name)


KINDS: tuple[ActionKind, ...] = (
    ActionKind(
        key="owner-info-tags",
        title="Owner information: PayHOA tags and request completions",
        cli="jason owner-info --apply --payhoa --yes",
        system="payhoa", resource=Resource.PAYHOA, risk=Risk.R2, approver=Approver.ONE_PERSON,
        reversible="tags: yes, remove or add the tag back; a completed request's status: yes; the comment emailed "
                   "to the owner: no",
        planner="jason.approvals.kinds.owner_info:plan",
        applier="jason.approvals.kinds.owner_info:apply",
        clock="the owner-information cycle (Civil Code 4040, 4041)",
        rule="the board's owner-information completion rule "
             "(Community.owner_information: OWNER_INFO_COMPLETED_COMMENT)",
        aliases=("payhoa.owner-info.tags",),
        # a completed request carries the board's comment, which PayHOA emails to the owner
        sends="the board's completion comment, emailed to the owner by PayHOA, for each request completed",
    ),
    ActionKind(
        key="payhoa-attach-bills",
        title="Bills: attach matched PDFs to PayHOA transactions",
        cli="jason sync-bills --yes",
        # R1, not R2: a PDF on an unapproved transaction is seen only by the association's own people in PayHOA's
        # books. It changes no record about a member, approves nothing, and emails nothing.
        system="payhoa", resource=Resource.PAYHOA, risk=Risk.R1, approver=Approver.ONE_PERSON,
        reversible="yes: a person deletes the attachment in PayHOA; nothing is approved or emailed",
        planner="jason.approvals.kinds.attach_bills:plan",
        applier="jason.approvals.kinds.attach_bills:apply",
        clock="",
        rule="CIV 5500(a)",
        max_age_hours=6,                       # the plan rests on PayHOA's live transaction list
        default_scope={"date_window_days": 7},
        aliases=("payhoa.attach-bills",),
    ),
    ActionKind(
        key="gmail-drafts",
        title="Gmail draft: save a prepared email as a draft (never sent)",
        cli="jason draft --yes",
        # R1, not R2: the draft is in the signed-in Gmail account's own drafts, seen by no one else. Nothing is sent
        # (the drafts client has no send method), no member is contacted, and no record about a member changes.
        system="google", resource=Resource.GOOGLE, risk=Risk.R1, approver=Approver.ONE_PERSON,
        reversible="yes: a person deletes the draft in Gmail; nothing is sent",
        planner="jason.approvals.kinds.gmail_drafts:plan",
        applier="jason.approvals.kinds.gmail_drafts:apply",
        rule="gmail_drafts.CASES",
        max_age_hours=6,                       # the plan rests on the stores the email is composed from
        aliases=("google.gmail-drafts",),
    ),
    ActionKind(
        key="payhoa-mailroom-send",
        title="Mailroom: print and mail a letter to owners (USPS through Lob), charged to the association",
        cli="jason mailroom --send --yes --expect FINGERPRINT --approval ID",
        # R3 and two-person: letters cannot be recalled (the cancel window is minutes) and the postage is charged.
        # Applied only by that command, at a terminal: the applier never mails from the engine's other paths.
        system="payhoa", resource=Resource.PAYHOA, risk=Risk.R3, approver=Approver.TWO_PERSON,
        reversible="no: a letter is printed and mailed; PayHOA's cancel works only while it is still processing, a "
                   "window of minutes (jason mailroom --cancel LETTER_ID --yes)",
        planner="jason.approvals.kinds.mailroom_send:plan",
        applier="jason.approvals.kinds.mailroom_send:apply",
        cost="postage and printing by PayHOA's pricing guide (payhoa.pricing), for the letters PayHOA names",
        rule="CIV 4040(a)(2)",
        max_age_hours=24,                      # the preview's own limit (tasks.mailroom.PREVIEW_MAX_AGE_HOURS)
        aliases=("payhoa.mailroom.send",),
        categories=("payment",),               # it commits the association's money: payment-signers controls bind
        terminal_only=True,
        sends="a printed letter, mailed by USPS to each owner",
    ),
)

_registered: dict[str, ActionKind] = {}


def register(kind: ActionKind) -> ActionKind:
    """Add a kind (a test's fake kind, or one a module defines); a key already taken is replaced."""
    _registered[kind.key] = kind
    return kind


def unregister(key: str) -> None:
    _registered.pop(key, None)


def kinds() -> list[ActionKind]:
    out = {k.key: k for k in KINDS}
    out.update(_registered)
    return list(out.values())


def get(key: str) -> ActionKind:
    for kind in kinds():
        if key == kind.key or key in kind.aliases:
            return kind
    raise KeyError(f"no action kind {key}: " + ", ".join(k.key for k in kinds()))


__all__ = ["ActionKind", "Approver", "KINDS", "Risk", "get", "kinds", "register", "unregister"]
