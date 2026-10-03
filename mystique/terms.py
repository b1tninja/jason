"""The terms the association's documents define, and where (``jason.community.definitions``).

Read from the definitions articles (the CC&Rs' Article 1, the Bylaws' Article 2) by ``definitions.read`` on
2026-10-02 and checked against the outlines; every quoted term found is here. A term a document defines takes that
document's meaning where the document uses it (Civil Code 1644), so reciting a section that uses one carries the
definition beside it. The CC&Rs and the Bylaws each define "Declaration", "Member", and the voting terms: a section is
read with its own document's definition.

"The Governing Documents" are the CC&Rs' own term (1.21): the Articles, Bylaws, Declaration, Rules, and the policies and
resolutions duly adopted by the Board. That is broader than the Act's list (CIV 4150); the difference is reported by
``jason cite jason://gov``, not resolved.
"""

from __future__ import annotations

from jason.community.books import Book
from jason.community.definitions import DefinedTerm, GoverningSet

_CCRS = (
    ("1.2", "Absolute Majority"), ("1.3", "Additional Charges"), ("1.4", "Articles"), ("1.5", "Assessment"),
    ("1.6", "Association"), ("1.7", "Board of Directors"), ("1.7", "Board"), ("1.8", "Bylaws"), ("1.9", "City"),
    ("1.10", "Common Area"), ("1.11", "Condominium"), ("1.12", "Condominium Plan"), ("1.12", "Plan"),
    ("1.13", "Contract Purchaser"), ("1.13", "Contract Seller"), ("1.14", "County"), ("1.15", "Declarant"),
    ("1.16", "Declaration"), ("1.17", "Declaration of Annexation"), ("1.18", "Development"), ("1.19", "Director"),
    ("1.20", "Exclusive Use Common Area"), ("1.21", "Governing Documents"), ("1.22", "Improvement"),
    ("1.23", "Member"), ("1.24", "Member in Good Standing"), ("1.25", "Mortgage"), ("1.26", "Owner"),
    ("1.27", "Phase 1"), ("1.28", "Phase"), ("1.29", "Record"), ("1.29", "Recordation"), ("1.29", "Filed"),
    ("1.30", "Resident"), ("1.31", "Rules"), ("1.32", "Simple Majority"), ("1.33", "Subdivision Map"),
    ("1.34", "Supplemental Declaration"), ("1.35", "Total Voting Power"), ("1.36", "Unit"),
)

_BYLAWS = (
    ("2.2", "Absolute Majority"), ("2.3", "Association Records"), ("2.4", "Declaration"),
    ("2.5", "Enhanced Association Records"), ("2.6", "Member"), ("2.7", "Member in Good Standing"), ("2.8", "Proxy"),
    ("2.9", "Reserve Accounts"), ("2.10", "Signed"), ("2.11", "Simple Majority"), ("2.12", "Total Voting Power"),
)

DEFINED_TERMS: tuple[DefinedTerm, ...] = (
    *(DefinedTerm(term, "ccrs", section) for section, term in _CCRS),
    *(DefinedTerm(term, "bylaws", section) for section, term in _BYLAWS),
)

GOVERNING_SET = GoverningSet(
    "decl#1.21", (Book.ARTS, Book.BYLAWS, Book.DECL, Book.RULES, Book.DISC, Book.COLL, Book.RES),
    also=("the policies and resolutions duly adopted by the Board",),
    note="disc, coll, and res are in the term by its last words, the policies and resolutions the Board adopted",
)
