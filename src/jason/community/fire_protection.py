"""What a fire protection contractor must hand the owner, by regulation: the deliverables of Title 19, Chapter 5.

The State Fire Marshal's regulation for water-based fire protection systems (19 CCR 904.1 and 904.2, adopting NFPA 25 as
the 2013 California Edition; the adopted text is on the authorities shelf) puts duties on whoever inspects, tests, and
maintains a system. These include a written report to the owner and the fire authority, an itemized invoice, a written
estimate before repairs, a tag only once deficiencies are corrected, and the State Fire Marshal's forms. A contract that
cites "Title 19" or "NFPA 25" carries them even when it does not repeat them, and a contract that does repeat one is
promising a deliverable the law already requires.

``DELIVERABLE_RULES`` are rows in match order. Each names the deliverable, a pattern over a term's quote, who receives
it, the regulation, and when. ``deliverable_rule(quote)`` returns the first that matches. The reference is
docs/fire-protection.md. Pure: no network, no store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliverableRule:
    key: str
    pattern: str                # a regex over a term's quote, matched ignoring case
    what: str
    recipient: str
    authority: str
    when: str


DELIVERABLE_RULES: tuple[DeliverableRule, ...] = (
    DeliverableRule("report-to-owner-and-fire-authority",
                    r"\b(?:written\s+)?report\b[^.]{0,120}\b(?:fire\s+(?:authority|department|marshal)|authority\s+having\s+jurisdiction|AHJ)\b|"
                    r"\b(?:fire\s+(?:authority|department)|AHJ)\b[^.]{0,120}\breport\b",
                    "a written report of the test and maintenance results", "owner and fire authority", "19 CCR 904.2(j)",
                    "at the completion of the testing and maintenance"),
    DeliverableRule("aes-forms",
                    r"\b(?:AES\s*(?:2\.\d|10|\d+(?:\.\d+)?)|inspection,?\s+testing\s*(?:&|and)\s*maintenance\s+reports?|ITM\s+reports?|"
                    r"state\s+fire\s+marshal\s+(?:automatic\s+extinguishing\s+systems\s+)?forms?)\b",
                    "the State Fire Marshal's AES form for the inspection, test, or maintenance", "owner",
                    "19 CCR 904(a)(1); NFPA 25 4.3.1.1 (California amendment)", "for each inspection, test, and maintenance"),
    DeliverableRule("inspection-report",
                    r"\binspection\s+reports?\b|\breports?\b[^.]{0,80}\b(?:inspection|test(?:ing)?|condition\s+of\s+the\s+system)\b",
                    "an inspection or test report showing the system's condition and the test data", "owner",
                    "19 CCR 904.2(j); NFPA 25 4.3.1 (California amendment)", "at the conclusion of each inspection or test"),
    DeliverableRule("itemized-invoice",
                    r"\bitemi[sz]ed\s+invoices?\b|\binvoices?\b[^.]{0,80}\b(?:work\s+performed|parts\s+replaced)\b",
                    "an itemized invoice of the work performed and the parts replaced", "owner", "19 CCR 904.2(e)",
                    "at the time of testing and maintenance, and whenever parts are replaced"),
    DeliverableRule("repair-estimate",
                    r"\b(?:written\s+)?estimates?\b[^.]{0,80}\b(?:repairs?|before|prior)\b|\b(?:before|prior\s+to)\b[^.]{0,60}\brepairs?\b[^.]{0,40}\bestimates?\b",
                    "a written estimate of the cost of repair, parts and labor", "owner", "19 CCR 904.2(k)",
                    "before any repair is performed"),
    DeliverableRule("service-tag",
                    r"\b(?:tag(?:ged|s)?|label(?:ed|s)?)\b[^.]{0,120}\b(?:deficienc(?:y|ies)|inspection|technician|date)\b",
                    "a service tag or label on the system, only after all deficiencies are corrected", "the system (posted at the riser)",
                    "19 CCR 904.2(d)", "after the service, once every deficiency is corrected"),
    DeliverableRule("notice-to-fire-authority",
                    r"\b(?:contact|notify|notice\s+to)\b[^.]{0,60}\b(?:fire\s+(?:authority|department)|AHJ)\b[^.]{0,60}\b(?:before|prior)\b",
                    "notice to the local fire authority before testing, when it requires one", "fire authority", "19 CCR 904.2(i)",
                    "before testing and maintenance, where the fire authority requires it"),
)

_COMPILED = [(rule, re.compile(rule.pattern, re.I)) for rule in DELIVERABLE_RULES]


def deliverable_rule(quote: str) -> DeliverableRule | None:
    """The first rule whose pattern matches the term's quote, or None."""
    words = re.sub(r"\s+", " ", quote or "")
    return next((rule for rule, pattern in _COMPILED if pattern.search(words)), None)


__all__ = ["DeliverableRule", "DELIVERABLE_RULES", "deliverable_rule"]
