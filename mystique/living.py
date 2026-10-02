"""Mystique's documents kept as amended (``jason.community.living``).

The CC&Rs: the base is the recorded Restated Declaration of 2007 as the library's text extract reads it (OCR, with the
corrections below). The First Amendment is read from its recorded copy's extract (it adds a section, so it needs no
marks). The Second is read from its Google Doc draft's runs, whose struck and bold words match the recorded scan's
(202312060284, read October 2, 2026). The Third is a draft and is listed, not applied. The working copy is the CC&Rs
Doc the board's secretary keeps by hand; jason reports where it differs and never edits it.
"""

from __future__ import annotations

from jason.community.living import (Correction, CorrectionKind, LivingDocument, LivingInstrument, SourceKind,
                                    SourceRef, TextCheck)
from jason.community.symbols import DocumentKind

from .ccrs import CCRS
from .leasing import LEASING

_FIRST, _SECOND, _THIRD = CCRS.amendments

CCRS_LIVING = LivingDocument(
    "ccrs", "Restated Declaration of Covenants, Conditions and Restrictions", DocumentKind.DECLARATION,
    base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing Documents/CCRs.pdf",
                   sha256="185536dc64b1e6a7aef0ce75c3cc8b14e7e636ad29fd99c9564a4e5281b59683",
                   note="the recorded 2007 Restated Declaration (200709200938), as OCR reads it"),
    base_from="the recorded 2007 Restated Declaration (200709200938), read by OCR",
    instruments=(
        LivingInstrument("ccrs-1st-amendment", _FIRST,
                         SourceRef(SourceKind.LIBRARY_TEXT, "Governing Documents/CCRs - 1st Amendment.pdf",
                                   sha256="be3415aeb68f5c62bf2246e8a7b128a2632e635251ce50d5493fd3efc4fb328d",
                                   note="the recorded copy's OCR; it adds 4.15(o), so no marks are needed")),
        LivingInstrument("ccrs-2nd-amendment", _SECOND,
                         SourceRef(SourceKind.DOC, "1G2GgTJjpJ1N3ZFAT7XJ9K6NI5RrqP7FyM7SclFhdWRE",
                                   note="the draft Doc's runs; its struck and bold words match the recorded scan's")),
        LivingInstrument("ccrs-3rd-amendment", _THIRD,
                         SourceRef(SourceKind.DOC, "1Sz8Wq_4cOhkVj75lSc7wCXobUEs5LPsJm4zI2PkDBcQ",
                                   note="a draft (an unsigned 2025 date): listed, not applied")),
    ),
    corrections=(
        Correction("4.15(m)", "ofanyprovisions", "of any provisions", CorrectionKind.SPACING, source="recorded copy"),
        Correction("4.15(m)", "tenns", "terms", CorrectionKind.OCR, source="recorded copy"),
        Correction("4.15(m)", "tenn ", "term ", CorrectionKind.OCR, source="recorded copy"),
    ),
    checks=(
        TextCheck("4.15(a)", f"({LEASING.cap_percent}%)", f"LeasingRules.cap_percent = {LEASING.cap_percent}"),
        TextCheck("4.15(m)(iii)", f"({LEASING.min_term_days}) days", f"LeasingRules.min_term_days = {LEASING.min_term_days}"),
    ),
    working_doc="1hJcV7Vs2mu2IqMalANdsmE4gOA_RhgupNLwwXjHyfE8",
)

LIVING_DOCUMENTS = (CCRS_LIVING,)
