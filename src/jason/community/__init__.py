"""Community model.

Implementation lives in jason. The facts for one association are a profile: a
`Community` subclass in its own package (`jason.community.profile`), such as
`mystique.Mystique`. Tasks ask a `Community`; they do not hardcode it.
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
from jason.community.profile import load_profile, profile_name
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


def community() -> Community:
    """The active profile's community (``JASON_PROFILE``, default ``mystique``), loaded once."""
    return load_profile()


def mystique() -> Community:
    """The active profile's community; the name predates profiles (see `community`)."""
    return load_profile()


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
    "community",
    "find_spec_root",
    "load_profile",
    "profile_name",
    "load_mystique",
    "first_utility",
    "mystique",
    "split_address",
]
