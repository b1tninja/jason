"""CC&Rs: the Restated Declaration and its amendments.

The declaration in force is the Restated Declaration of Covenants, Conditions and Restrictions for Mystique, recorded
September 20, 2007 as Sacramento County document 200709200938 (Book 20070920, Page 0938; indexed "220 AMENDED
RESTRICTION"). Its recital F rescinds and revokes the prior declaration of September 12, 2007, 200709120758 (Book
20070912, Page 758; indexed "324 DECLARATION OF RESTRICTION"); ``mystique/annexations.py`` pins that supersession. The
First Amendment (202001170712, recorded January 17, 2020) and every annexation recite 200709200938. Confirmed by the
board September 29, 2026. Section citations and adoption dates stay empty until that text is in hand.
"""

from __future__ import annotations

from datetime import date

from jason.community.documents import Amendment, Document, GoverningDocument
from jason.community.recorder import Sacramento
from jason.community.symbols import DocumentKind

_RECORDED = Sacramento.county_recorder.parse("200709200938")
# The declaration the restatement rescinded; the county index still lists it as a 324 declaration.
PRIOR_DECLARATION = "200709120758"
_FIRST_AMENDMENT = Sacramento.county_recorder.parse("202001170712")
_SECOND_AMENDMENT = Sacramento.county_recorder.parse("202312060284")


class FirstAmendment(Amendment, Document):
    """The First Amendment to the Restated Declaration, recorded January 17, 2020; it adds section 4.15(o)."""

    def __init__(self) -> None:
        super().__init__(
            title="CCRs - 1st Amendment.pdf",
            drive_id="1yzsa5yPtb1L6NqdXs1vRU7cYrBBKT3jA",
            sections=("4.15(o)",),
            recorder_number=_FIRST_AMENDMENT.number,
            recorded=_FIRST_AMENDMENT.recorded,
        )


class SecondAmendment(Amendment, Document):
    """The Second Amendment, adopted by the board under Civil Code 4741(f) on November 16, 2023 and recorded December 6,
    2023 (read from the recorded copy, "Mystique - 231208 - CC&R and Second Amendment.pdf", ten pages). It restates
    4.15(a) (the rental cap, 20 to 25 percent) and 4.15(m)(iii) (the minimum lease, six months to thirty days), and
    removes 4.15(n). Its witness clause calls it "this FIRST AMENDMENT", a template's leftover; the title, recitals,
    and the index say Second. The Google Doc is its draft; the recorded copy is the instrument."""

    def __init__(self) -> None:
        super().__init__(
            title="CCRs - 2nd Amendment",
            drive_id="1ArMfQcWN6xdTubij06NS15DMjdog8yVo",
            sections=("4.15(a)", "4.15(m)(iii)", "4.15(n)"),
            adopted=date(2023, 11, 16),
            recorder_number=_SECOND_AMENDMENT.number,
            recorded=_SECOND_AMENDMENT.recorded,
        )


class ThirdAmendment(Amendment, Document):
    def __init__(self) -> None:
        super().__init__(
            title="CCRs - 3rd Amendment",
            drive_id="1Sz8Wq_4cOhkVj75lSc7wCXobUEs5LPsJm4zI2PkDBcQ",
        )


class CCRs(GoverningDocument):
    def __init__(self) -> None:
        super().__init__(
            title="CCRs",
            drive_id="1hJcV7Vs2mu2IqMalANdsmE4gOA_RhgupNLwwXjHyfE8",
            document_kind=DocumentKind.DECLARATION,
            recorder_number=_RECORDED.number,
            recorded=_RECORDED.recorded,
            amendments=(FirstAmendment(), SecondAmendment(), ThirdAmendment()),
        )

    def cite(self) -> str:
        return "CC&Rs"


CCRS = CCRs()
