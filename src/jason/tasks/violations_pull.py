"""Pull outstanding and broader violation sets from PayHOA."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DEFAULT_OUTSTANDING_STATUS = "All Outstanding"
# Empty status asks the API for an unfiltered table when the client forwards it.
DEFAULT_BROADER_STATUS = ""


@dataclass
class ViolationsPullReport:
    outstanding: list[dict[str, Any]] = field(default_factory=list)
    broader: list[dict[str, Any]] = field(default_factory=list)
    outstanding_count: int = 0
    broader_count: int = 0
    outstanding_status: str = DEFAULT_OUTSTANDING_STATUS
    broader_status: str = DEFAULT_BROADER_STATUS

    def summary(self) -> str:
        return (
            f"outstanding={self.outstanding_count} "
            f"broader={self.broader_count} "
            f"(statuses={self.outstanding_status!r}/{self.broader_status!r})"
        )


def pull_violations(
    client: Any,
    org_id: int,
    *,
    outstanding_status: str = DEFAULT_OUTSTANDING_STATUS,
    broader_status: str = DEFAULT_BROADER_STATUS,
    filters: dict[str, Any] | None = None,
) -> ViolationsPullReport:
    """Fetch violations twice: outstanding filter, then a broader status.

    A zero outstanding count is not treated as proof that there are no
    violations; the broader call always runs.
    """
    outstanding = list(
        client.iter_violations(
            org_id, status=outstanding_status, filters=filters
        )
    )
    broader = list(
        client.iter_violations(org_id, status=broader_status, filters=filters)
    )
    return ViolationsPullReport(
        outstanding=outstanding,
        broader=broader,
        outstanding_count=len(outstanding),
        broader_count=len(broader),
        outstanding_status=outstanding_status,
        broader_status=broader_status,
    )
