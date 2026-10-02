"""Concepts a declaration keeps restating, and how an annotation records them.

A CC&R set restricts a shared list of subjects. The wording differs. The subject
does not. An annotation names the subject and the document section that states
it. The section stays empty until the instrument body is in hand.

``statute`` is the current Civil Code citation for that subject. ``prior_statute``
is the citation printed in the document when that printing uses an older
numbering. Leave ``prior_statute`` empty until the body shows the old number.
Do not copy either citation into a draft as if it were the CC&R text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class CitationEra(Enum):
    """Which Davis-Stirling numbering was in force on a recording date.

    The Act was renumbered effective January 1, 2014. An instrument recorded
    before that date was written against the earlier section numbers.
    """

    PRIOR = "prior"
    CURRENT = "current"


DAVIS_STIRLING_RENUMBERED = date(2014, 1, 1)


def citation_session(recorded: date | None, sessions: tuple[str, ...]) -> str | None:
    """The loaded publication year to close a lookup over.

    PRIOR uses the latest loaded year that is still before the 2014 renumber.
    CURRENT uses the latest loaded year. When no loaded year sits in that era,
    the result is ``None``. That is a miss, not the other era's text.
    ``indexed_in`` may show that the same section number exists in another
    year. It is not a map from a current number to a repealed one.
    """
    era = citation_era(recorded)
    years = sorted(year for year in sessions if str(year).isdigit())
    if era is None or not years:
        return None
    if era is CitationEra.PRIOR:
        prior = [year for year in years if int(year) < DAVIS_STIRLING_RENUMBERED.year]
        return prior[-1] if prior else None
    return years[-1]


def citation_era(recorded: date | None) -> CitationEra | None:
    """The numbering to expect in an instrument recorded on this date.

    ``None`` when the recording date is unknown. Do not infer the date from a
    file name.
    """
    if recorded is None:
        return None
    if recorded < DAVIS_STIRLING_RENUMBERED:
        return CitationEra.PRIOR
    return CitationEra.CURRENT


class Provision(Enum):
    """One subject a governing document defines or restricts."""

    DECLARATION = "declaration"
    COMMON_AREA = "common_area"
    SEPARATE_INTEREST = "separate_interest"
    EXCLUSIVE_USE = "exclusive_use"
    MAINTENANCE = "maintenance"
    ARCHITECTURE = "architecture"
    USE = "use"
    RENTAL = "rental"
    ASSESSMENT = "assessment"
    INSURANCE = "insurance"
    TRANSFER = "transfer"
    DISCIPLINE = "discipline"


class Alignment(Enum):
    """What the annotation claims. Unread claims nothing about the words."""

    UNREAD = "unread"
    DEFINED = "defined"
    RESTRICTS = "restricts"
    DEFERS = "defers"
    SUPERSEDED = "superseded"


# Current Davis-Stirling anchors. These are where to open the code, not quotations.
STATUTE: dict[Provision, str] = {
    Provision.DECLARATION: "CIV 4135",
    Provision.COMMON_AREA: "CIV 4095",
    Provision.SEPARATE_INTEREST: "CIV 4185",
    Provision.EXCLUSIVE_USE: "CIV 4145",
    Provision.MAINTENANCE: "CIV 4775",
    Provision.ARCHITECTURE: "CIV 4765",
    Provision.USE: "CIV 4700",
    Provision.RENTAL: "CIV 4740",
    Provision.ASSESSMENT: "CIV 5600",
    Provision.INSURANCE: "CIV 5806",
    Provision.TRANSFER: "CIV 4525",
    Provision.DISCIPLINE: "CIV 5855",
}


@dataclass(frozen=True)
class Annotation:
    """One subject located in one instrument.

    ``section`` is the instrument's own citation, such as ``"4.2"``. An amendment
    that changes that section carries the same provision on its own annotation.
    """

    provision: Provision
    alignment: Alignment = Alignment.UNREAD
    section: str = ""
    prior_statute: str = ""

    @property
    def statute(self) -> str:
        return STATUTE[self.provision]


def annotate(
    provision: Provision,
    *,
    alignment: Alignment = Alignment.UNREAD,
    section: str = "",
    prior_statute: str = "",
) -> Annotation:
    """Record a subject. A superseded or restricting note needs the section it cites."""
    if alignment is not Alignment.UNREAD and not section.strip():
        raise ValueError("a read annotation needs the instrument section")
    return Annotation(
        provision,
        alignment,
        section.strip(),
        prior_statute.strip(),
    )
