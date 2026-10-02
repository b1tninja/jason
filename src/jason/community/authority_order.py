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

**Follow what is written, as far as a higher authority allows.** A provision is followed as written, and yields only "to
the extent of any conflict" (Civil Code 4205): the rest of it still governs. A ``Conflict`` records one such provision:
what it says, the authority above it and since when (most often a change in the law after the provision was written),
the part that yields, how the provision is applied meanwhile, whether the conflict is plain or a question for counsel,
and the board item that follows it. A command or procedure working in a conflict's area shows it (``jason sop KEY``,
``jason conflicts``), so whoever follows the written procedure knows where it no longer holds. jason notes a conflict;
only the board, counsel, or an amendment resolves one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum, IntEnum

from jason.community.lessons import Area
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


class Clarity(Enum):
    """How plainly the higher authority displaces the provision."""
    PLAIN = "plain"              # the authority speaks to it directly (a cap, a floor, a required step): apply it now
    UNCLEAR = "unclear"          # whether, or how far, the provision yields turns on a reading: counsel first
    RENUMBERED = "renumbered"    # no conflict of substance: the provision cites a statute by a former number


class ConflictStatus(Enum):
    NOTED = "noted"              # recorded; no one is acting on it yet
    COUNSEL = "counsel"          # with counsel for a reading
    BOARD = "board"              # on the board's action register
    RESOLVED = "resolved"        # amended, repealed, or settled by an adopted reading (``resolved_by``)


@dataclass(frozen=True)
class Conflict:
    """A written provision a higher authority displaces, wholly or in part. ``says`` and ``extent`` paraphrase; quote
    a provision only from its text."""
    key: str
    provision: str                       # the document and section ("CC&Rs 9.9(b)", "the 2022 fine schedule")
    tier: Tier                           # the provision's own tier
    says: str                            # what it provides, in a sentence
    authority: str                       # the higher authority ("CIV 4741(b)")
    authority_tier: Tier
    since: date | None                   # when the higher authority took effect: a change in law after the provision
    extent: str                          # the part that yields; the rest still governs
    apply: str                           # how the provision is followed meanwhile
    clarity: Clarity
    status: ConflictStatus
    areas: tuple[Area, ...] = ()
    board_item: str = ""                 # the board's action item that follows it
    resolved_by: str = ""                # the amendment, resolution, or adopted reading that settled it

    def __post_init__(self) -> None:
        if self.authority_tier >= self.tier:
            raise ValueError(f"{self.key}: {self.authority} ({self.authority_tier.label}) does not rank above "
                             f"{self.provision} ({self.tier.label})")
        if self.status is ConflictStatus.RESOLVED and not self.resolved_by:
            raise ValueError(f"{self.key}: a resolved conflict names what resolved it")

    @property
    def open(self) -> bool:
        return self.status is not ConflictStatus.RESOLVED


def conflicts(community: object | None = None, area: Area | None = None, *, open_only: bool = False
              ) -> tuple[Conflict, ...]:
    """The community's recorded conflicts (``Community.conflicts()``), in an area, optionally only the open ones."""
    found = tuple(getattr(community, "conflicts", lambda: ())()) if community is not None else ()
    return tuple(c for c in found if (area is None or area in c.areas) and (not open_only or c.open))


def conflict_lines(found: tuple[Conflict, ...] | list[Conflict]) -> list[str]:
    """Each conflict as a Markdown item: the provision, the authority above it, the part that yields, and how it is
    applied meanwhile."""
    out = []
    for c in found:
        item =f" (board item {c.board_item})" if c.board_item else ""
        out.append(f"- **{c.provision}** yields to {c.authority}{_since(c.since)} [{c.clarity.value}; "
                   f"{c.status.value}{item}]: {c.extent} Meanwhile: {c.apply}"
                   + (f" Resolved by {c.resolved_by}." if c.resolved_by else ""))
    return out


def _since(when: date | None) -> str:
    return f", since {when.strftime('%B')} {when.day}, {when.year}" if when else ""


__all__ = ["Clarity", "Conflict", "ConflictStatus", "KIND_TIERS", "Tier", "conflict_lines", "conflicts",
           "tier_of_citation", "tier_of_kind"]
