"""What a fire protection contractor must hand the owner, by regulation: the deliverables of Title 19, Chapter 5.

The State Fire Marshal's regulation for water-based fire protection systems (19 CCR 904.1 and 904.2, adopting NFPA 25 as
the 2013 California Edition; the adopted text is on the authorities shelf) puts duties on whoever inspects, tests, and
maintains a system. These include a written report to the owner and the fire authority, an itemized invoice, a written
estimate before repairs, a tag only once deficiencies are corrected, and the State Fire Marshal's forms. A contract that
cites "Title 19" or "NFPA 25" carries them even when it does not repeat them, and a contract that does repeat one is
promising a deliverable the law already requires.

``DELIVERABLE_RULES`` are rows in match order. Each names the deliverable, a pattern over a term's quote, who receives
it, the regulation, when, and what it applies to. ``deliverable_rule(quote)`` returns the first that matches. The
reference is docs/fire-protection.md. Pure: no network, no store.

**What each row applies to** (``applies``, a ``jason.community.applicability`` condition): the subject is a water-based
fire protection system, the words of 19 CCR 904(a)(1), and the vendor does the kind of work the row's own provision is
about. 904.2 is "Testing and Maintenance Requirements" and 904.1 "Inspection Requirements", so a row that rests on
904.2 alone asks for testing or maintenance, and the forms and the inspection report also reach inspections. The rows
carry no exclusion the regulation's words do not give: 19 CCR 901 makes the chapter apply "to all automatic fire
extinguishing systems identified in Health and Safety Code Section 13195". ``deliverables(facts)`` sorts the rows by
their answers for a document's facts; the contract reader's own gate is its session's code (docs/applicability.md,
step 7), and ``deliverable_rule`` matches words only, as before.

**The standards' scopes**, for the rows that keep a system (a profile's obligations): ``NFPA_25_SCOPE``,
``NFPA_25_SPRINKLERS``, and ``FIRE_ALARM_SYSTEM``.

**How long the records are kept**: ``RECORD_RULES``, each a citation and a locator for its words on the authorities
shelf. ``jason inspections`` recites them (``jason.tasks.inspections.recite``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jason.community.applicability import (
    ALWAYS,
    WATER_BASED_FIRE_PROTECTION,
    AllOf,
    Condition,
    Except,
    Fact,
    Facts,
    In,
    InstallationStandard,
    Is,
    Partition,
    SystemKind,
    Work,
    partition,
)

# --- What the standards reach -----------------------------------------------------------------------------------

WATER_BASED = In(Fact.SYSTEM, WATER_BASED_FIRE_PROTECTION, "a water-based fire protection system")
_INSTALLED_UNDER_13D = Is(Fact.INSTALLATION_STANDARD, InstallationStandard.NFPA_13D)

# NFPA 25 covers water-based fire protection systems, and leaves out sprinkler systems installed under NFPA 13D (one-
# and two-family dwellings and manufactured homes). A reading from secondary sources: the standard's own scope section
# is not on disk (docs/fire-protection.md, "Gaps associations commonly have" and "Sources").
NFPA_25_SCOPE: Condition = Except(WATER_BASED, _INSTALLED_UNDER_13D)

# NFPA 25's chapter on sprinkler systems (Table 5.1.1.2, "Summary of Sprinkler System Inspection, Testing, and
# Maintenance", as California amended it): the quarterly, annual, and five-year items, the gauges, and the sample tests.
NFPA_25_SPRINKLERS: Condition = Except(Is(Fact.SYSTEM, SystemKind.FIRE_SPRINKLER), _INSTALLED_UNDER_13D)

# NFPA 72's chapter 14, adopted by the California Fire Code for fire alarms.
FIRE_ALARM_SYSTEM: Condition = Is(Fact.SYSTEM, SystemKind.FIRE_ALARM)


def _serviced(*work: Work) -> Condition:
    """A water-based fire protection system on which the vendor does one of these kinds of work."""
    return AllOf(WATER_BASED, In(Fact.VENDOR_WORK, frozenset(work)))


_TESTED_OR_MAINTAINED = _serviced(Work.TEST, Work.MAINTAIN)                       # 19 CCR 904.2
_INSPECTED_TESTED_OR_MAINTAINED = _serviced(Work.INSPECT, Work.TEST, Work.MAINTAIN)  # 904.1 and 904.2; NFPA 25 4.3.1
_TESTED_MAINTAINED_OR_REPAIRED = _serviced(Work.TEST, Work.MAINTAIN, Work.REPAIR)    # 904.2(e), (k): parts and repairs


# --- The deliverables -------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DeliverableRule:
    key: str
    pattern: str                # a regex over a term's quote, matched ignoring case
    what: str
    recipient: str
    authority: str
    when: str
    applies: Condition = ALWAYS  # the subject and the vendor's work the provision reaches


DELIVERABLE_RULES: tuple[DeliverableRule, ...] = (
    DeliverableRule("report-to-owner-and-fire-authority",
                    r"\b(?:written\s+)?report\b[^.]{0,120}\b(?:fire\s+(?:authority|department|marshal)|authority\s+having\s+jurisdiction|AHJ)\b|"
                    r"\b(?:fire\s+(?:authority|department)|AHJ)\b[^.]{0,120}\breport\b",
                    "a written report of the test and maintenance results", "owner and fire authority", "19 CCR 904.2(j)",
                    "at the completion of the testing and maintenance", applies=_TESTED_OR_MAINTAINED),
    DeliverableRule("aes-forms",
                    r"\b(?:AES\s*(?:2\.\d|10|\d+(?:\.\d+)?)|inspection,?\s+testing\s*(?:&|and)\s*maintenance\s+reports?|ITM\s+reports?|"
                    r"state\s+fire\s+marshal\s+(?:automatic\s+extinguishing\s+systems\s+)?forms?)\b",
                    "the State Fire Marshal's AES form for the inspection, test, or maintenance", "owner",
                    "19 CCR 904(a)(1); NFPA 25 4.3.1.1 (California amendment)", "for each inspection, test, and maintenance",
                    applies=_INSPECTED_TESTED_OR_MAINTAINED),
    DeliverableRule("inspection-report",
                    r"\binspection\s+reports?\b|\breports?\b[^.]{0,80}\b(?:inspection|test(?:ing)?|condition\s+of\s+the\s+system)\b",
                    "an inspection or test report showing the system's condition and the test data", "owner",
                    "19 CCR 904.2(j); NFPA 25 4.3.1 (California amendment)", "at the conclusion of each inspection or test",
                    applies=_INSPECTED_TESTED_OR_MAINTAINED),
    DeliverableRule("itemized-invoice",
                    r"\bitemi[sz]ed\s+invoices?\b|\binvoices?\b[^.]{0,80}\b(?:work\s+performed|parts\s+replaced)\b",
                    "an itemized invoice of the work performed and the parts replaced", "owner", "19 CCR 904.2(e)",
                    "at the time of testing and maintenance, and whenever parts are replaced",
                    applies=_TESTED_MAINTAINED_OR_REPAIRED),
    DeliverableRule("repair-estimate",
                    r"\b(?:written\s+)?estimates?\b[^.]{0,80}\b(?:repairs?|before|prior)\b|\b(?:before|prior\s+to)\b[^.]{0,60}\brepairs?\b[^.]{0,40}\bestimates?\b",
                    "a written estimate of the cost of repair, parts and labor", "owner", "19 CCR 904.2(k)",
                    "before any repair is performed", applies=_TESTED_MAINTAINED_OR_REPAIRED),
    DeliverableRule("service-tag",
                    r"\b(?:tag(?:ged|s)?|label(?:ed|s)?)\b[^.]{0,120}\b(?:deficienc(?:y|ies)|inspection|technician|date)\b",
                    "a service tag or label on the system, only after all deficiencies are corrected", "the system (posted at the riser)",
                    "19 CCR 904.2(d)", "after the service, once every deficiency is corrected", applies=_TESTED_OR_MAINTAINED),
    DeliverableRule("notice-to-fire-authority",
                    r"\b(?:contact|notify|notice\s+to)\b[^.]{0,60}\b(?:fire\s+(?:authority|department)|AHJ)\b[^.]{0,60}\b(?:before|prior)\b",
                    "notice to the local fire authority before testing, when it requires one", "fire authority", "19 CCR 904.2(i)",
                    "before testing and maintenance, where the fire authority requires it", applies=_TESTED_OR_MAINTAINED),
)

_COMPILED = [(rule, re.compile(rule.pattern, re.I)) for rule in DELIVERABLE_RULES]


def deliverable_rule(quote: str) -> DeliverableRule | None:
    """The first rule whose pattern matches the term's quote, or None."""
    words = re.sub(r"\s+", " ", quote or "")
    return next((rule for rule, pattern in _COMPILED if pattern.search(words)), None)


def deliverables(facts: Facts) -> Partition:
    """The rows sorted by whether each applies to these facts (the subject and the vendor's kinds of work, as a
    document or a profile gives them): applies, does not apply with the deciding fact, or undetermined with the fact
    missing. An undetermined row is a question, never a row dropped."""
    return partition(DELIVERABLE_RULES, facts)


# --- How long the records are kept ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordRule:
    """One provision on how long a system's records are kept, and where its words are on the authorities shelf.

    The row holds the citation and a locator, never the words: ``jason.tasks.inspections.recite`` reads them from the
    publication's text on disk, and a provision the shelf's copy does not print is a miss that says so. ``publication``
    is the title of the ``Publication`` that holds it. ``section`` is a pattern for the line its section starts on,
    ``start`` for the line the provision starts on inside that section, and ``end`` for the first line after it; each
    is matched at the start of a line. ``applies`` is the system the provision reaches.
    """

    key: str
    citation: str
    about: str
    publication: str
    section: str
    start: str
    end: str
    applies: Condition = ALWAYS


_TITLE_19 = "Title 19, Chapter 5 and NFPA 25 California amendments, final text (2014)"

# The chapter's own record rules, and NFPA 25's as California amended it. The chapter's rows reach a water-based
# system, the words of 19 CCR 904(a)(1), with no exclusion the regulation's words do not give; the standard's row
# reaches what the standard does (``NFPA_25_SCOPE``, a reading from secondary sources).
RECORD_RULES: tuple[RecordRule, ...] = (
    RecordRule("inspection-records", "19 CCR 904.1(b)", "records of inspections", _TITLE_19,
               r"§?\s*904\.1\.\s", r"\(b\)\s", r"\(c\)\s|NOTE:", applies=WATER_BASED),
    RecordRule("testing-and-maintenance-records", "19 CCR 904.2(c)", "records of testing and maintenance", _TITLE_19,
               r"§?\s*904\.2\.\s", r"\(c\)\s", r"\(d\)\s", applies=WATER_BASED),
    RecordRule("nfpa-25-records", "NFPA 25 4.3.5 (California amendment)", "records under NFPA 25", _TITLE_19,
               r"Replace Section 4\.3\.5\b", r"4\.3\.5\s", r"(?:Delete|Replace|Add|Revise)\s", applies=NFPA_25_SCOPE),
)


__all__ = ["DeliverableRule", "DELIVERABLE_RULES", "deliverable_rule", "deliverables", "WATER_BASED", "NFPA_25_SCOPE",
           "NFPA_25_SPRINKLERS", "FIRE_ALARM_SYSTEM", "RecordRule", "RECORD_RULES"]
