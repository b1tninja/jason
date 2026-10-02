"""A reserve component: what it is, how long it lasts, and which cost center pays."""

from __future__ import annotations

from dataclasses import dataclass

from jason.community.symbols import ComponentMajor, CostCenter


@dataclass(frozen=True)
class ReserveComponent:
    """One line from the reserve component list.

    ``useful_life_years`` is the study's life expectancy (U/L).
    ``remaining_life_years`` is the remaining useful life (R/L).
    ``cost_cents`` is the current replacement cost. A missing cost stays None.
    """

    cost_center: CostCenter
    major: ComponentMajor
    description: str
    cost_cents: int | None
    useful_life_years: int
    remaining_life_years: int
    last_completed_year: int | None
    scheduled_year: int | None

    @property
    def item_code(self) -> str:
        """The study's numeric item code, when the description starts with one."""
        head = self.description.split(" - ", 1)[0].strip()
        return head if head.isdigit() else ""
