"""Mystique specification: the `mystique` profile. Import `Mystique`; do not parse a data file."""

from .community import Mystique

PROFILE = Mystique

__all__ = ["Mystique", "PROFILE"]
