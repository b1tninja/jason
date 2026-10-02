"""Pull PayHOA units, people, violations, requests, documents, and each unit's other contacts into the catalog."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from payhoa import PayhoaClient

from jason.catalog import PayhoaCatalog

CATALOG_KINDS = ("units", "people", "violations", "requests", "documents", "contacts")


@dataclass
class CatalogSyncReport:
    units: int = 0
    people: int = 0
    violations: int = 0
    requests: int = 0
    documents: int = 0
    contacts: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [
            f"units={self.units}",
            f"people={self.people}",
            f"violations={self.violations}",
            f"requests={self.requests}",
            f"documents={self.documents}",
            f"contacts={self.contacts}",
        ]
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return " ".join(parts)


def sync_catalog(
    client: PayhoaClient,
    catalog: PayhoaCatalog,
    org_id: int,
    *,
    kinds: tuple[str, ...] | list[str] | None = None,
    people_status: str = "active",
    violation_status: str = "",
    violation_filters: dict[str, Any] | None = None,
) -> CatalogSyncReport:
    """Fetch each requested collection and upsert it. One failure does not stop the rest."""
    selected = tuple(kinds) if kinds else CATALOG_KINDS
    unknown = [name for name in selected if name not in CATALOG_KINDS]
    if unknown:
        raise ValueError(f"unknown catalog kinds: {', '.join(unknown)}")

    report = CatalogSyncReport()
    runners: dict[str, Callable[[], int]] = {
        "units": lambda: catalog.upsert_units(org_id, list(client.iter_units(org_id))),
        "people": lambda: catalog.upsert_people(
            org_id, list(client.iter_people(org_id, status=people_status))
        ),
        "violations": lambda: catalog.upsert_violations(
            org_id,
            list(
                client.iter_violations(
                    org_id,
                    status=violation_status,
                    filters=violation_filters,
                )
            ),
        ),
        "requests": lambda: _sync_requests(client, catalog, org_id),
        "documents": lambda: catalog.upsert_documents(
            org_id, client.list_documents(org_id)
        ),
        "contacts": lambda: _sync_contacts(client, catalog, org_id),
    }
    for name in selected:
        try:
            setattr(report, name, runners[name]())
        except Exception as exc:  # noqa: BLE001 — collect per-kind failures
            report.errors.append(f"{name}: {exc}")
    return report


def _sync_contacts(client: PayhoaClient, catalog: PayhoaCatalog, org_id: int) -> int:
    """Each unit's other contacts (one call a unit), replacing what the catalog held for it."""
    total = 0
    for unit in client.iter_units(org_id):
        if unit.get("deletedAt"):
            continue
        total += catalog.replace_unit_contacts(org_id, int(unit["id"]), client.list_unit_contacts(int(unit["id"])))
    return total


def _sync_requests(client: PayhoaClient, catalog: PayhoaCatalog, org_id: int) -> int:
    forms = [
        form
        for form in client.list_forms()
        if int(form.get("organizationId") or org_id) == org_id
    ]
    names = {int(form["id"]): str(form.get("name") or "") for form in forms}
    rows: list[dict[str, Any]] = []
    for form in forms:
        for submission in client.list_form_submissions(int(form["id"])):
            if int(submission.get("organizationId") or org_id) == org_id:
                rows.append(submission)
    return catalog.upsert_requests(org_id, rows, form_names=names)
