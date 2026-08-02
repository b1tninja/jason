"""Ordered registry of bill sources."""

from __future__ import annotations

from typing import Any

from jason.sources.protocol import BillSource


class BillSourceRegistry:
    """First-match routing; register SMUD before City Sac for exclusivity."""

    def __init__(self, sources: list[BillSource] | None = None) -> None:
        self._sources: list[BillSource] = list(sources or [])

    def register(self, source: BillSource) -> None:
        self._sources.append(source)

    @property
    def sources(self) -> list[BillSource]:
        return list(self._sources)

    def get(self, name: str) -> BillSource | None:
        for source in self._sources:
            if source.name == name:
                return source
        return None

    def route(self, tx: dict[str, Any]) -> BillSource | None:
        for source in self._sources:
            if source.matches_transaction(tx):
                return source
        return None

    def filter(self, names: set[str] | None) -> BillSourceRegistry:
        if not names:
            return BillSourceRegistry(self._sources)
        return BillSourceRegistry([s for s in self._sources if s.name in names])
