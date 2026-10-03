"""Mystique's documents kept as amended (``jason.community.living``).

The CC&Rs: the base is the authoritative copy at its best quality, the county's own recorded copy of the 2007 Restated
Declaration (stamped Book 20070920, Page 0938, September 20, 2007; scanned in 2007), read by OCR with the corrections
below. It is crisper than the title company's certified copy in the library (CCRs.pdf, a 2012 rescan of a copy). The
working copy (the board's hand-kept Doc) is the comparison that corrects the OCR (``jason intake``). The First Amendment is read from its recorded copy's extract (it adds a section, so it needs no
marks). The Second is read from its recorded scan (202312060284), its struck and bold words measured in the pixels
(``jason.community.scan_marks``), and its draft Doc's words are compared with it. The Third is a draft and is listed, not applied. The working copy is the CC&Rs
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
    base=SourceRef(SourceKind.SCAN, "1DLjMdMWGsKZ_aenjL0o_2xS1pxPLROIl",
                   sha256="24f7d30ee1e606b8fb19a05e1b9034424f019e972e9dd9ea10aecbe3df73e193",
                   note="the county's recorded copy (Mystique CC R's RESTATED RECORDED), 56 pages"),
    base_from="the county's recorded copy of the 2007 Restated Declaration (200709200938), read by OCR",
    instruments=(
        LivingInstrument("ccrs-1st-amendment", _FIRST,
                         SourceRef(SourceKind.LIBRARY_TEXT, "Governing Documents/CCRs - 1st Amendment.pdf",
                                   sha256="be3415aeb68f5c62bf2246e8a7b128a2632e635251ce50d5493fd3efc4fb328d",
                                   note="the recorded copy's OCR; it adds 4.15(o), so no marks are needed")),
        LivingInstrument("ccrs-2nd-amendment", _SECOND,
                         SourceRef(SourceKind.SCAN, "1ArMfQcWN6xdTubij06NS15DMjdog8yVo",
                                   sha256="8ed582c9c55a6839c619f1631752828f3c2ee7595f9fec574f7578cd437369fa",
                                   note="the recorded copy (202312060284), its struck and bold words read from the scan"),
                         check=SourceRef(SourceKind.DOC, "1G2GgTJjpJ1N3ZFAT7XJ9K6NI5RrqP7FyM7SclFhdWRE",
                                         note="the draft Doc: its words must agree with the recorded copy's")),
        LivingInstrument("ccrs-3rd-amendment", _THIRD,
                         SourceRef(SourceKind.DOC, "1Sz8Wq_4cOhkVj75lSc7wCXobUEs5LPsJm4zI2PkDBcQ",
                                   note="a draft (an unsigned 2025 date): listed, not applied")),
    ),
    corrections=(
        # Keyed to the inline subsection the words are in: the working copy numbers the base (aligned numbering).
        Correction("4.15(m)(iii)", "ofanyprovisions", "of any provisions", CorrectionKind.SPACING,
                   source="recorded copy"),
        # The scan's OCR glues the struck "six"'s first letter onto "of"; the draft Doc and the page read "of".
        Correction("4.15(m)(iii)", "term ofs thirty", "term of thirty", CorrectionKind.OCR,
                   source="the Second Amendment's recorded copy, page 4"),
    ),
    checks=(
        TextCheck("4.15(a)", f"({LEASING.cap_percent}%)", f"LeasingRules.cap_percent = {LEASING.cap_percent}"),
        TextCheck("4.15(m)(iii)", f"({LEASING.min_term_days}) days", f"LeasingRules.min_term_days = {LEASING.min_term_days}"),
    ),
    working_doc="1hJcV7Vs2mu2IqMalANdsmE4gOA_RhgupNLwwXjHyfE8",
)

LIVING_DOCUMENTS = (CCRS_LIVING,)
