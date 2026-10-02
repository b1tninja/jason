"""Which source controls: the order of authority a community manager reads in.

Civil Code 4205 orders the governing documents under the law: the law prevails over all of them, the declaration over
the articles, the articles or declaration over the bylaws, and all three over the operating rules. Around that order:

- federal law preempts state law where it speaks (fair housing, the FCC's antenna rule, flood insurance mandates);
- the state's statutes, then its regulations (Title 10 for the DRE, Title 19 for fire systems), then local law (the City
  code) — a regulation or ordinance binds the association too, but yields to the statute that authorizes it;
- an amendment to the declaration or a declaration of annexation is part of the declaration; between two versions of
  the same section the later controls (``apply_supersessions`` records what replaced what);
- an operating rule is valid only within the authority and limits of everything above it (Civil Code 4350); the board's
  policies and resolutions are operating rules or board decisions, not governing documents of higher rank;
- contracts and insurance policies bind the parties by their terms; records (minutes, bills, reports) are facts, not
  rules; and secondary guidance (practice articles, jason's own pages) explains and never controls.

``Tier`` is that order; a lower number controls. A conflict is reported, never resolved silently: the higher source
controls, and the lower one is a finding for the board (an outdated rule, a document citing a renumbered statute).
"""

from __future__ import annotations

from enum import IntEnum

from jason.community.symbols import DocumentKind


class Tier(IntEnum):
    FEDERAL_LAW = 1
    STATUTE = 2
    REGULATION = 3
    LOCAL_LAW = 4
    DECLARATION = 5
    ARTICLES = 6
    BYLAWS = 7
    OPERATING_RULES = 8
    CONTRACT = 9
    RECORD = 10
    GUIDANCE = 11

    @property
    def label(self) -> str:
        return {
            Tier.FEDERAL_LAW: "federal law",
            Tier.STATUTE: "California statute",
            Tier.REGULATION: "regulation",
            Tier.LOCAL_LAW: "local ordinance",
            Tier.DECLARATION: "declaration (CC&Rs, amendments, annexations)",
            Tier.ARTICLES: "articles of incorporation",
            Tier.BYLAWS: "bylaws",
            Tier.OPERATING_RULES: "operating rules, policies, resolutions",
            Tier.CONTRACT: "contract or policy of insurance",
            Tier.RECORD: "association record (fact)",
            Tier.GUIDANCE: "secondary guidance (explains, never controls)",
        }[self]

    @property
    def is_rule(self) -> bool:
        """A source that states a rule the association must follow, as against a fact or an explanation."""
        return self <= Tier.CONTRACT


KIND_TIERS: dict[DocumentKind, Tier] = {
    DocumentKind.DECLARATION: Tier.DECLARATION,
    DocumentKind.AMENDMENT: Tier.DECLARATION,
    DocumentKind.ANNEXATION: Tier.DECLARATION,
    DocumentKind.ARTICLES: Tier.ARTICLES,
    DocumentKind.BYLAWS: Tier.BYLAWS,
    DocumentKind.OPERATING_RULES: Tier.OPERATING_RULES,
    DocumentKind.POLICY: Tier.OPERATING_RULES,
    DocumentKind.ELECTION_RULES: Tier.OPERATING_RULES,
    DocumentKind.RESOLUTION: Tier.OPERATING_RULES,
    DocumentKind.CONTRACT: Tier.CONTRACT,
    DocumentKind.LEASE: Tier.CONTRACT,
    DocumentKind.INSURANCE_POLICY: Tier.CONTRACT,
}

# Code abbreviations as lawlibrary and the citation grammar write them.
FEDERAL_CODES = frozenset({"USC", "CFR"})
REGULATION_CODES = frozenset({"CCR"})
LOCAL_CODES = frozenset({"SCC"})            # Sacramento City Code


def tier_of_kind(kind: DocumentKind | None) -> Tier:
    """A document's tier by its kind; anything else the association holds is a record."""
    return KIND_TIERS.get(kind, Tier.RECORD) if kind is not None else Tier.RECORD


def tier_of_citation(citation: str) -> Tier:
    """``CIV 5810`` is a statute, ``10 CCR 2792.23`` a regulation, ``42 USC 3604`` federal, ``SCC 13.10`` local."""
    parts = citation.upper().split()
    codes = {p for p in parts if p.isalpha()}
    if codes & FEDERAL_CODES:
        return Tier.FEDERAL_LAW
    if codes & REGULATION_CODES:
        return Tier.REGULATION
    if codes & LOCAL_CODES:
        return Tier.LOCAL_LAW
    return Tier.STATUTE


__all__ = ["KIND_TIERS", "Tier", "tier_of_citation", "tier_of_kind"]
