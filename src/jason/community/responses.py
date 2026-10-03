r"""What each request of the association is, the clock it starts, and who owns the answer.

A member's request (a PayHOA request, an email, a letter) is classified by kind (``classify``, rule rows in order: the
form it came on, then its words). Each kind has a ``ResponseRule``:

- **the clock**: a notice catalog requirement whose timing runs from the request (records within 10 business days,
  CIV 5210; a solar decision within 45 days, CIV 714), or a clock the governing documents set (a rental application
  decided within 30 days), or, where the law and the documents are silent, a policy clock jason proposes and the board
  adopts ("where the law is silent, write it down");
- **the owner**: the schedule's assignment for the kind (``jason.community.schedule``);
- **the first step**: what the owner does first (acknowledge, gather the records, put it on the next agenda).

The handler never approves, denies, or assigns a request: it says what kind it is, when the answer is due, whose it
is, and whether it is late. A kind no rule recognizes is ``OTHER`` and gets the general clock; a miss stays a miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ResponseKind(Enum):
    RECORDS = "records request"
    RESALE = "resale documents"
    ARCHITECTURAL = "architectural application"
    SOLAR = "solar application"
    EV_CHARGER = "EV charger application"
    RENTAL = "rental application"
    VARIANCE = "variance request"
    PAYMENT_PLAN = "payment plan request"
    HEARING_REQUEST = "hearing request"
    DISPUTE = "internal dispute resolution"
    ADR = "request for resolution (ADR)"
    MAINTENANCE = "maintenance request"
    COMPLAINT = "complaint"
    QUESTION = "question"
    OTHER = "other"


class ClockSource(Enum):
    STATUTE = "statute"                  # a notice catalog requirement
    DOCUMENTS = "governing documents"    # a clause the documents state
    POLICY = "proposed policy"           # the law and the documents are silent: a clock for the board to adopt
    NONE = "none"


@dataclass(frozen=True)
class KindRule:
    """One classification row: a request on one of ``forms`` (any form when empty) whose words match ``words`` is
    ``kind``. Rows are tried in order; the first match wins."""

    kind: ResponseKind
    words: str = ""                      # a regular expression over the title and message, case-insensitive
    forms: tuple[str, ...] = ()
    exclude: str = ""                    # words that make it something else (a reply to the association's own notice)

    def matches(self, form: str, text: str) -> bool:
        if self.forms and form not in self.forms:
            return False
        if self.exclude and re.search(self.exclude, text, re.I):
            return False
        return not self.words or re.search(self.words, text, re.I) is not None


@dataclass(frozen=True)
class ResponseRule:
    kind: ResponseKind
    source: ClockSource
    notice: str = ""                     # STATUTE: the notice catalog key whose timing is the clock
    days: int = 0                        # DOCUMENTS or POLICY: the clock in days
    business_days: bool = False
    authority: str = ""                  # the statute, the documents' section, or "proposed policy"
    assignment: str = ""                 # the schedule's assignment key that owns it
    first_step: str = ""
    acknowledge_days: int = 0            # a proposed acknowledgment within these business days (0: none)
    note: str = ""


# General classification: the statute's kinds by their words, then the form. A profile's rows come first.
KIND_RULES: tuple[KindRule, ...] = (
    # An application, not every mention: solar or a charger with the words of installing or asking.
    KindRule(ResponseKind.SOLAR, r"\b(?:solar|photovoltaic|pv)\b[^.]{0,60}\b(?:install\w*|panels?|system|application|"
                                 r"permit|approv\w*|request)\b|\b(?:install\w*|add\w*)\b[^.]{0,40}\bsolar\b"),
    KindRule(ResponseKind.EV_CHARGER, r"\b(?:EV|electric\s+vehicle)\s+charg\w*\b[^.]{0,60}\b(?:install\w*|application|"
                                      r"permit|approv\w*|request)\b|\binstall\w*\b[^.]{0,40}\bcharg(?:er|ing\s+station)\b|"
                                      r"\bcharging\s+station\b"),
    # The documents a sale needs (4525, 4528), not every message that mentions escrow.
    KindRule(ResponseKind.RESALE, r"\b452[58]\b|\bresale\s+(?:disclosure|package|documents?|certificate)\b|"
                                  r"\bdisclosure\s+package\b|\bdemand\s+(?:statement|for\s+payoff)\b|\bpayoff\s+demand\b|"
                                  r"\b(?:HOA|association)\s+(?:documents|docs|package)\b[^.]{0,40}\b(?:sale|escrow|buyer)\b"),
    KindRule(ResponseKind.PAYMENT_PLAN, r"\bpayment\s+plan\b"),
    KindRule(ResponseKind.ADR, r"\brequest\s+for\s+resolution\b|\bmediation\b|\barbitration\b"),
    KindRule(ResponseKind.DISPUTE, r"\bmeet\s+and\s+confer\b|\binternal\s+dispute\b|\bIDR\b"),
    KindRule(ResponseKind.HEARING_REQUEST, r"\brequest(?:ing)?\s+(?:a\s+)?hearing\b|\bappeal\b[^.]{0,40}\b(?:fine|decision)\b"),
    KindRule(ResponseKind.VARIANCE, r"\bvariance\b"),
    KindRule(ResponseKind.RECORDS, r"\b(?:inspect|copies|copy)\b[^.]{0,60}\b(?:records?|minutes|budget|financial|"
                                   r"ledger|statements?|contracts?|membership\s+list)\b|\brecords?\s+request\b|"
                                   r"\bmembership\s+list\b|\b5200\b|\b5205\b|"
                                   # a copy of the governing documents
                                   r"\bcop(?:y|ies)\s+of\b[^.]{0,40}\b(?:CC&?Rs?|bylaws|(?:operating\s+)?rules|"
                                   r"owners?'?\s+manual|governing\s+documents|articles\s+of\s+incorporation)\b"),
    KindRule(ResponseKind.RENTAL, r"\b(?:lease|rent(?:al)?|tenant)\b[^.]{0,60}\b(?:application|approv\w*|request)\b|"
                                  r"\bapply\b[^.]{0,30}\b(?:lease|rent)\b|\bintent\s+to\s+(?:rent|lease)\b|"
                                  r"\b(?:rent|renting|lease|leasing)\s+out\b"),
    KindRule(ResponseKind.ARCHITECTURAL, forms=("Architectural Request",)),
    KindRule(ResponseKind.MAINTENANCE, forms=("Maintenance Request",)),
    # Asking leave to change the unit or the common area is an application on any form.
    KindRule(ResponseKind.ARCHITECTURAL, r"\bhome\s+improvement\b|\barchitectural\s+(?:request|application|approval)\b|"
                                         r"\bpermission\s+to\b[^.]{0,30}\b(?:install\w*|paint\w*|decorat\w*|replac\w*|"
                                         r"add\w*|plant\w*|modif\w*|alter\w*|build\w*)\b"),
    # Conduct reported, not the association's own notice about it, and not an owner asking not to be cited.
    KindRule(ResponseKind.COMPLAINT, r"\bcomplain\w*\b|\bnoise\b|\bnuisance\b|\bharass\w*\b|\bviolat\w*\b|"
                                     r"\bvandal\w*\b|\bdisturbance\b|\bdefecat\w*\b|\bdog\s+(?:poop\w*|waste|feces)\b|"
                                     r"\bpoop\w*\b|\bparked\s+(?:car|vehicle|truck)\b|"
                                     r"\bconcerns?\b[^.]{0,60}\b(?:parking|common\s+areas?|neighbou?rs?)\b",
             exclude=r"\bcourtesy\s+notice\b|\bnotice\s+of\s+(?:violation|hearing)\b|\bhearing\s+notice\b|"
                     r"\b(?:do\s+not|don'?t|not\s+to)\s+(?:mark|cite|fine|count)\w*\b[^.]{0,40}\bviolation\b|"
                     r"\bviolation\s+report\b"),
    # Something to fix or tend, on a form that is not the maintenance form (or an email subject). A question about it
    # (whose job is it?) is a question.
    KindRule(ResponseKind.MAINTENANCE, r"\bleak\w*|\brepairs?\b|\bbroken\b|\bnot\s+working\b|\bno\s+(?:power|heat|hot\s+"
                                       r"water)\b|\brust(?:y|ed)\b|\btrees?\b|\bstanding\s+water\b|\b(?:re)?stak(?:e|ed|"
                                       r"ing)\b|\b(?:light|lamp|bulb)s?\b[^.]{0,40}\bout\b|\bclog\w*|\bpest\s+control\b|"
                                       r"\bwasps?\b|\brodents?\b|\bweeds?\b|\bdrip\s+lines?\b|\bsprinklers?\b|"
                                       r"\bheat(?:er|ing)\b|\bhvac\b|\bgarage\s+door\b|\bfire\s+alarm\b|\bwork\s+order\b|"
                                       r"\bgutters?\b|\bmisalign\w*",
             exclude=r"\bquestions?\b|\brecommend\w*|\bresponsib\w*|\bliab(?:le|ility)\b"),
    KindRule(ResponseKind.QUESTION, forms=("General Request",)),
    KindRule(ResponseKind.QUESTION, r"\?|\bquestions?\b|\binquir(?:y|ies|ing)\b|\bclarif\w*"),
)


# General rules: the statute's clocks. The profile adds the documents' clocks and the proposed policies.
RESPONSE_RULES: tuple[ResponseRule, ...] = (
    ResponseRule(ResponseKind.RECORDS, ClockSource.STATUTE, notice="records-current-year", authority="CIV 5210",
                 assignment="records-requests", first_step="Gather the records and send them, or the 5215 explanation of "
                 "what is withheld; a prior year's records have 30 days (records-prior-years).", acknowledge_days=2),
    ResponseRule(ResponseKind.RESALE, ClockSource.STATUTE, notice="resale-documents", authority="CIV 4530",
                 assignment="records-requests", first_step="Send the 4525 documents and the 4528 form, at actual cost."),
    ResponseRule(ResponseKind.SOLAR, ClockSource.STATUTE, notice="solar-decision", authority="CIV 714",
                 assignment="architecture", first_step="Put it on the next board agenda; a complete application not "
                 "denied in writing within 45 days is deemed approved."),
    ResponseRule(ResponseKind.EV_CHARGER, ClockSource.STATUTE, notice="ev-charger-decision", authority="CIV 4745",
                 assignment="architecture", first_step="Put it on the next board agenda; an application not denied in "
                 "writing within 60 days is deemed approved."),
    ResponseRule(ResponseKind.PAYMENT_PLAN, ClockSource.STATUTE, notice="payment-plan-meeting", authority="CIV 5665",
                 assignment="collections", first_step="Meet with the owner in executive session within 45 days of the "
                 "request's postmark."),
    ResponseRule(ResponseKind.ADR, ClockSource.STATUTE, notice="request-for-resolution", authority="CIV 5935",
                 assignment="disputes", first_step="Accept or reject in writing within 30 days of service; counsel."),
)


def classify(form: str, text: str, rules: tuple[KindRule, ...] = KIND_RULES) -> tuple[ResponseKind, str]:
    """The request's kind and why: the first rule whose form and words match."""
    for rule in rules:
        if rule.matches(form, text):
            if rule.words:
                m = re.search(rule.words, text, re.I)
                return rule.kind, f'its words: "{m.group(0)}"' if m else "its words"
            return rule.kind, f"its form: {form}"
    return ResponseKind.OTHER, "no rule matched"


def rules_for(community: object | None) -> tuple[tuple[KindRule, ...], dict[ResponseKind, ResponseRule]]:
    """The classification rows (the profile's first) and the response rule per kind (the profile's replace jason's)."""
    own_kinds = tuple(getattr(community, "request_kind_rules", lambda: ())()) if community is not None else ()
    by_kind = {r.kind: r for r in RESPONSE_RULES}
    for r in (getattr(community, "response_rules", lambda: ())() if community is not None else ()):
        by_kind[r.kind] = r
    return own_kinds + KIND_RULES, by_kind


__all__ = ["ClockSource", "KIND_RULES", "KindRule", "RESPONSE_RULES", "ResponseKind", "ResponseRule", "classify",
           "rules_for"]
