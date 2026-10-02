"""Community model.

Implementation lives in jason. The facts for one association are a class such
as `mystique.Mystique`. Tasks ask a `Community`; they do not hardcode it.
"""

from __future__ import annotations

from jason.community.base import (
    BuildingRange,
    Community,
    TransactionRule,
    assign_building,
    split_address,
)
from jason.community.register import InsuranceRegistry
from jason.community.spec import find_spec_root, first_utility, load_mystique
from jason.community.provisions import (
    Alignment,
    Annotation,
    CitationEra,
    Provision,
    annotate,
    citation_era,
    citation_session,
)
from jason.community.records import citation
from jason.community.symbols import (
    AssociationRecord,
    Building,
    ComponentMajor,
    CostCenter,
    DocumentCategory,
    DocumentKind,
    DocumentRule,
    FileKind,
    InsuranceVisit,
    KnownFile,
    MembershipTab,
    Parity,
    PayhoaFolder,
    PolicyKind,
    PublicDrive,
    SitePage,
    Street,
    Utility,
)

_MYSTIQUE: Community | None = None


def mystique() -> Community:
    """The `mystique` class checked in beside this package."""
    global _MYSTIQUE
    if _MYSTIQUE is None:
        _MYSTIQUE = load_mystique()
    return _MYSTIQUE


__all__ = [
    "Alignment",
    "Annotation",
    "AssociationRecord",
    "Building",
    "BuildingRange",
    "ComponentMajor",
    "CostCenter",
    "CitationEra",
    "Community",
    "DocumentCategory",
    "DocumentKind",
    "DocumentRule",
    "FileKind",
    "InsuranceRegistry",
    "InsuranceVisit",
    "KnownFile",
    "MembershipTab",
    "Parity",
    "PayhoaFolder",
    "Provision",
    "PolicyKind",
    "PublicDrive",
    "SitePage",
    "Street",
    "TransactionRule",
    "Utility",
    "annotate",
    "assign_building",
    "citation",
    "citation_era",
    "citation_session",
    "find_spec_root",
    "load_mystique",
    "first_utility",
    "mystique",
    "split_address",
]
