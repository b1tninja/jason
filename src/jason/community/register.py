"""Decorators that turn a class body into a catalog record."""

from __future__ import annotations

from jason.community.base import BuildingRange, InsuranceCatalog, InsuranceYear, Policy


class InsuranceRegistry:
    """Collect `@policy` classes in definition order."""

    def __init__(self) -> None:
        self._policies: list[Policy] = []

    def policy(self, cls: type) -> type:
        self._policies.append(
            Policy(
                kind=cls.kind,
                number=str(getattr(cls, "number", "") or ""),
                renewal=getattr(cls, "renewal", None),
                building=getattr(cls, "building", None),
                declaration_name=str(getattr(cls, "declaration_name", "") or ""),
                location_prints_building=bool(getattr(cls, "location_prints_building", False)),
                carrier=str(getattr(cls, "carrier", "") or ""),
                program=str(getattr(cls, "program", "") or ""),
                agent=str(getattr(cls, "agent", "") or ""),
                prior_numbers=tuple(getattr(cls, "prior_numbers", ()) or ()),
                premium_categories=tuple(getattr(cls, "premium_categories", ()) or ()),
                deductible_cents=getattr(cls, "deductible_cents", None),
            )
        )
        return cls

    def catalog(self, buildings: tuple[BuildingRange, ...], years: tuple[InsuranceYear, ...]) -> InsuranceCatalog:
        return InsuranceCatalog(years, tuple(self._policies), buildings)
