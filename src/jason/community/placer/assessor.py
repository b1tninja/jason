"""Placer County assessor — HTTP in asspy; the owner's instrument through ``ParcelOwnership``."""

from __future__ import annotations

from asspy.core import Parcel, SearchHit
from asspy.placer import PlacerCountyAssessor as _AsspyAssessor
from jason.community.assessor import ParcelOwnership

# Compatibility aliases used by jason callers and tests.
PlacerParcel = Parcel
PlacerSearchHit = SearchHit

__all__ = (
    "PlacerCountyAssessor",
    "PlacerParcel",
    "PlacerSearchHit",
)


class PlacerCountyAssessor(ParcelOwnership, _AsspyAssessor):
    """Placer assessor; the owner's instrument from the Placer recorder."""

    def recorder(self):
        from jason.community.placer.recorder import PlacerCountyRecorder

        return PlacerCountyRecorder()
