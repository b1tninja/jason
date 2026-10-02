"""Who owes what: unpaid issued charges tied to units and owners."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from jason.catalog import person_name, unit_label


@dataclass
class WhoOwesRow:
    unit_id: int | None
    unit_label: str
    owner_name: str
    unpaid_amount_cents: int
    past_due_balance_cents: int | None
    charge_ids: list[int] = field(default_factory=list)
    charge_titles: list[str] = field(default_factory=list)
    recurring_titles: list[str] = field(default_factory=list)


@dataclass
class WhoOwesReport:
    rows: list[WhoOwesRow]
    total_unpaid_cents: int = 0
    unit_count: int = 0

    def summary(self) -> str:
        return (
            f"units_owing={self.unit_count} "
            f"total_unpaid_cents={self.total_unpaid_cents}"
        )


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _charge_title(charge: Mapping[str, Any]) -> str:
    for key in ("title", "name", "description", "chargeTitle"):
        text = str(charge.get(key) or "").strip()
        if text:
            return text
    return ""


def _owner_from_mapping(row: Mapping[str, Any]) -> str:
    direct = str(
        row.get("ownerName")
        or row.get("owner")
        or row.get("memberName")
        or ""
    ).strip()
    if direct and not isinstance(row.get("owner"), (dict, list)):
        return direct
    owner = row.get("owner")
    if isinstance(owner, dict):
        return person_name(owner) or str(owner.get("name") or "").strip()
    owners = row.get("owners")
    if isinstance(owners, list) and owners:
        first = owners[0]
        if isinstance(first, dict):
            return person_name(first) or str(first.get("name") or "").strip()
        return str(first).strip()
    profile = row.get("profile")
    if isinstance(profile, dict):
        return person_name({"profile": profile})
    return person_name(dict(row))


def _template_title(template: Mapping[str, Any]) -> str:
    for key in ("title", "name", "description"):
        text = str(template.get(key) or "").strip()
        if text:
            return text
    return ""


def build_who_owes_rows(
    charges: Iterable[Mapping[str, Any]],
    *,
    units: Iterable[Mapping[str, Any]] | None = None,
    recurring_templates: Iterable[Mapping[str, Any]] | None = None,
) -> list[WhoOwesRow]:
    """Group unpaid charges by unit; attach owner, past-due, and recurring titles."""
    units_by_id: dict[int, Mapping[str, Any]] = {}
    for unit in units or ():
        uid = _as_int(unit.get("id"))
        if uid is not None:
            units_by_id[uid] = unit

    recurring_by_unit: dict[int | None, list[str]] = {}
    for template in recurring_templates or ():
        title = _template_title(template)
        if not title:
            continue
        uid = _as_int(template.get("unitId"))
        recurring_by_unit.setdefault(uid, []).append(title)

    grouped: dict[int | None, WhoOwesRow] = {}
    for charge in charges:
        uid = _as_int(charge.get("unitId"))
        amount = _as_int(charge.get("amount") if charge.get("amount") is not None else charge.get("balance"))
        amount = amount or 0
        title = _charge_title(charge)
        charge_id = _as_int(charge.get("id"))

        if uid not in grouped:
            unit = units_by_id.get(uid) if uid is not None else None
            owner = _owner_from_mapping(charge)
            if not owner and unit is not None:
                owner = _owner_from_mapping(unit)
            label = ""
            past_due: int | None = None
            if unit is not None:
                label = unit_label(dict(unit))
                past_due = _as_int(
                    unit.get("pastDueBalance")
                    if unit.get("pastDueBalance") is not None
                    else unit.get("past_due_balance")
                )
            if not label:
                label = str(charge.get("unitTitle") or charge.get("unitName") or "").strip()
                if not label and uid is not None:
                    label = f"unit:{uid}"
            if past_due is None:
                past_due = _as_int(charge.get("pastDueBalance") or charge.get("pastDue"))
            recurring = list(recurring_by_unit.get(uid, []))
            # Org-wide templates (no unitId) apply to every unit row.
            if uid is not None:
                recurring = recurring + list(recurring_by_unit.get(None, []))
            grouped[uid] = WhoOwesRow(
                unit_id=uid,
                unit_label=label,
                owner_name=owner,
                unpaid_amount_cents=0,
                past_due_balance_cents=past_due,
                recurring_titles=recurring,
            )

        row = grouped[uid]
        row.unpaid_amount_cents += amount
        if charge_id is not None:
            row.charge_ids.append(charge_id)
        if title:
            row.charge_titles.append(title)
        if not row.owner_name:
            row.owner_name = _owner_from_mapping(charge)

    # Units with past-due balance but no unpaid charge rows still surface.
    for uid, unit in units_by_id.items():
        past_due = _as_int(
            unit.get("pastDueBalance")
            if unit.get("pastDueBalance") is not None
            else unit.get("past_due_balance")
        )
        if uid in grouped:
            if grouped[uid].past_due_balance_cents is None and past_due is not None:
                grouped[uid].past_due_balance_cents = past_due
            continue
        if past_due is None or past_due == 0:
            continue
        recurring = list(recurring_by_unit.get(uid, [])) + list(
            recurring_by_unit.get(None, [])
        )
        grouped[uid] = WhoOwesRow(
            unit_id=uid,
            unit_label=unit_label(dict(unit)),
            owner_name=_owner_from_mapping(unit),
            unpaid_amount_cents=0,
            past_due_balance_cents=past_due,
            recurring_titles=recurring,
        )

    rows = list(grouped.values())
    rows.sort(key=lambda r: (r.unit_label or "", r.unit_id or 0))
    return rows


def _load_units(
    client: Any, org_id: int, *, catalog: Any | None
) -> list[Mapping[str, Any]]:
    if catalog is not None and hasattr(catalog, "iter_units"):
        return list(catalog.iter_units(org_id))
    return list(client.iter_units(org_id))


def who_owes(
    client: Any,
    org_id: int,
    *,
    catalog: Any | None = None,
    status: str = "unpaid",
) -> WhoOwesReport:
    """Fetch unpaid charges and recurring templates; return unit-level owe rows.

    Calls ``client.iter_issued_charges(org_id, status=...)`` and
    ``client.iter_recurring_charge_templates(org_id)``. Units come from
    ``catalog`` when it exposes an ``iter_units``/query helper, otherwise
    ``client.iter_units(org_id)``.
    """
    charges = list(client.iter_issued_charges(org_id, status=status))
    templates: list[Mapping[str, Any]] = []
    if hasattr(client, "iter_recurring_charge_templates"):
        templates = list(client.iter_recurring_charge_templates(org_id))
    units = _load_units(client, org_id, catalog=catalog)
    rows = build_who_owes_rows(
        charges, units=units, recurring_templates=templates
    )
    total = sum(r.unpaid_amount_cents for r in rows)
    return WhoOwesReport(rows=rows, total_unpaid_cents=total, unit_count=len(rows))
