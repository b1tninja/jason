"""Which onboarding checklist item a recorded instrument serves, read from the filing name the county's index prints.

A rule row is the words a filing name carries and the item it serves; rows apply in order, so a more specific
filing ("AMENDED CONDOMINIUM PLAN") comes before the general one ("CONDOMINIUM PLAN" would also match it, and both
serve one item). A filing no row names serves no item: the locator leaves it out. ``Tie`` says how an instrument
was tied to the association, strongest first; the locator's questions offer the strong ties as the suggestion and
ask about the weak ones.

The rows are county-neutral words; a county whose index spells a filing differently gets a row, not a branch in
the locator.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tie(Enum):
    """How a located instrument was tied to the association, strongest first."""

    NAMED = "names the association"                    # the association is a party on it
    BESIDE = "recorded with the association's documents"   # a same-day neighbor of one, sharing its builder
    DECLARANT = "the builder's filing"                 # the same builder's governing filing; may be another community's

    @property
    def strong(self) -> bool:
        return self is not Tie.DECLARANT


@dataclass(frozen=True)
class FilingRule:
    """The filing names (any word group) an item's instruments carry, and what finding one means."""

    words: tuple[str, ...]
    item: str                       # the onboarding checklist item (jason.community.onboarding.ITEMS)
    governing: bool = False         # an instrument that creates or changes the community: its neighbors are read
    side: str = ""                  # "E" or "R": the association must be on that index side (a deed TO it)
    beside: bool = True             # found beside a governing instrument counts (a map does; a lien does not)
    unless: tuple[str, ...] = ()    # words that make a matching filing something else ("DECLARATION OF TRUST")


# In match order. The association's own assessment liens are counted, not listed (the survey and title watch keep them).
RULES: tuple[FilingRule, ...] = (
    FilingRule(("DELINQUENT ASSESSMENT", "NOTICE ASSESSMENT LIEN", "ASSESSMENT LIEN"), "recorded-liens", beside=False),
    FilingRule(("DECLARATION OF DEANNEXATION", "DEANNEX"), "annexations", governing=True),
    FilingRule(("ANNEX",), "annexations", governing=True),
    FilingRule(("AMENDED DECLARATION", "MODIFICATION OF RESTRICTIONS", "RESTRICTIVE COVENANT MODIFICATION",
                "CERTIFICATE OF AMENDMENT", "AMENDMENT TO DECLARATION", "TERMINATION CC&R", "PARTIAL TERMINATION CC&R"),
               "amendments", governing=True),
    FilingRule(("CONDOMINIUM PLAN", "CONDOMINIUM CERTIFICATE", "CONDO PLAN"), "condominium-plans", governing=True),
    FilingRule(("DECLARATION OF RESTRICTIONS", "DECLARATION OF COVENANTS", "DECLARATION"), "declaration", governing=True,
               unless=("HOMESTEAD", "OF TRUST", "TRANSMUTATION", "SEVERANCE", "LOST", "DEDICATION", "REORGANIZATION")),
    FilingRule(("MODIFICATION OF BYLAWS", "BYLAWS"), "bylaws"),
    FilingRule(("MODIFICATION ARTICLES OF ASSOCIATION", "ARTICLES OF INCORPORATION", "ARTICLES OF ASSOCIATION"), "articles"),
    FilingRule(("STATEMENT OF HOMEOWNERS ASSOCIATION",), "statement-of-information"),
    FilingRule(("SUBDIVISION MAP", "PARCEL MAP", "AMENDED SUBDIVISION MAP", "AMENDED PARCEL MAP"), "maps"),
    FilingRule(("GRANT DEED", "QUITCLAIM", "CORPORATION DEED", "DEED"), "common-area-deeds", side="E",
               unless=("TRUST", "RECONVEY", "IN LIEU", "TAX DEED")),
    FilingRule(("EASEMENT",), "common-area-deeds", beside=False),
    FilingRule(("LIS PENDENS", "ABSTRACT OF JUDGMENT", "JUDGMENT"), "litigation", beside=False),
)


def rule_for(filing_name: str) -> FilingRule | None:
    """The first rule whose words the filing name carries, or None."""
    upper = " ".join(str(filing_name or "").upper().split())
    for rule in RULES:
        if any(word in upper for word in rule.words) and not any(word in upper for word in rule.unless):
            return rule
    return None


# What each item's question asks the board, by item. The answer is a document number, "all N listed", or none.
QUESTIONS = {
    "declaration": "Which is the association's declaration (the CC&Rs later amendments amend)?",
    "amendments": "Which of these amend the association's declaration and are recorded and in force?",
    "annexations": "Which of these annex a phase into the association (or take one out)?",
    "condominium-plans": "Which of these condominium plans define the association's units?",
    "bylaws": "Is one of these the association's bylaws, or an amendment to them?",
    "articles": "Is one of these an amendment to the association's articles?",
    "statement-of-information": "Is this the association's recorded statement (its name, address, and managing agent)?",
    "maps": "Which of these maps describe the association's development?",
    "common-area-deeds": "Which of these convey the common area (or an easement) to the association?",
    "litigation": "Which of these are the association's lawsuits or judgments, and are any still open?",
}

# Items whose answer decides which words are in force: a second person confirms.
HIGH_STAKES = frozenset({"declaration", "amendments"})
