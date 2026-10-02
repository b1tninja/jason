"""A proposed change to an operating rule, as data (Civil Code 4340-4370).

A ``RuleChange`` names the document it amends (an outline key in ``mystique/outlines.py``), the sections it replaces,
the plain-language purpose and effect, and the questions only the board or counsel can answer. A ``SectionChange``
carries the proposed words; the current words are read from the document's outline on disk when the notice is built,
never copied into the specification. Brackets in proposed text (``[effective date]``) mark what the board decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionChange:
    """One section of the rule as proposed. ``number`` is the outline's section number ("20"); an empty ``proposed`` with
    ``repeal`` set deletes it; ``new`` adds a section the document lacks. With ``strike`` set, ``proposed`` replaces only
    those words inside the section (a sentence-level amendment) and the rest of the section stands."""

    number: str
    title: str
    proposed: str = ""
    strike: str = ""
    repeal: bool = False
    new: bool = False
    note: str = ""

    @property
    def label(self) -> str:
        """"Section 18(d)" for the outline's "18(18)(d)"."""
        return "Section " + re.sub(r"^(\d+)\(\1\)", r"\1", self.number)


@dataclass(frozen=True)
class RuleChange:
    """A proposed rule change. ``document`` is the outline key of the rule it amends; ``authorities`` are citations the
    notice names (``CIV 4360``); ``decisions`` are what the board and counsel must settle before the notice goes out."""

    key: str
    title: str
    document: str
    document_title: str
    purpose: str
    effect: str
    sections: tuple[SectionChange, ...]
    decisions: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()
    authorities: tuple[str, ...] = ("CIV 4340", "CIV 4355", "CIV 4360", "CIV 4365")

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.key.lower()).strip("-")

    def placeholders(self) -> tuple[str, ...]:
        """Every ``[bracketed]`` choice in the proposed text, in order, once each."""
        seen: dict[str, None] = {}
        for section in self.sections:
            for token in re.findall(r"\[[^\[\]]+\]", section.proposed):
                seen.setdefault(token, None)
        return tuple(seen)


__all__ = ["RuleChange", "SectionChange"]
