"""Whether the association keeps the two assessment cost centers its annexations require.

Each Watt declaration of annexation (section 1.3) makes a Regular Assessment a General Assessment Component, shared by
every unit under the declaration's section 6.5(b), plus a cost center component shared equally within the unit's cost
center: the Phases 1 and 2 Property (A.C.A. 3 and 8, WL Homes' 2008 buildings) or the Annexed Property (Watt's
buildings). The DRE public reports for phases 3 to 8 say the same to buyers: "Your Condominium Unit will also be subject
to a Cost Center budget", $116.60 a month at build-out on top of the $168.15 regular assessment.

``review`` sets the rule beside what the records show:

- the specification's Association Common Areas and their cost centers, and the units in each;
- the DRE reports' regular and cost center budgets (the document model readings, ``jason models``);
- the monthly assessments PayHOA charged each unit (the stored general ledger, ``jason books --sync``), by cost center:
  the same charge on every unit means the components are not separated;
- the budget's categories (``data/payhoa/budgets``): a cost center is kept only if some line carries it;
- the reserve studies' funding plans: one plan for all units does not keep the cost centers' reserves apart.

It reads disk only. Whether and how to restore the cost centers is the board's, with counsel.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jason.community.base import CostCenter


def _center_of_building(community: Any) -> dict[int, CostCenter]:
    return {int(a.building): a.cost_center for a in community.association_common_areas() if a.cost_center is not None}


def charges_by_center(data_dir: Path, community: Any) -> dict[str, dict[str, Any]]:
    """Each year's monthly Regular Assessment charges, by cost center: the amounts charged and how often."""
    path = Path(data_dir) / "payhoa" / "ledger.db"
    if not path.is_file():
        return {}
    centers = _center_of_building(community)
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT account, day, debit, description FROM entries WHERE type = 'Accounts Receivable' AND debit > 0 "
                            "AND description LIKE '%Regular Assessment (monthly)%' AND description NOT LIKE '%Payment Plan%'").fetchall()
    found: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for account, day, debit, _ in rows:
        building = community.building_for_address(account)
        center = centers.get(int(building.number)) if building is not None else None
        found[str(day)[:4]][center.value if center else "unplaced"][int(debit)] += 1
    return {year: {center: dict(amounts.most_common()) for center, amounts in sorted(by.items())} for year, by in sorted(found.items())}


def budget_lines(data_dir: Path) -> dict[int, list[str]]:
    """Each stored budget year's lines that name a cost center, a building, or a phase."""
    found = {}
    for path in sorted((Path(data_dir) / "payhoa" / "budgets").glob("*.json")):
        tree = json.loads(path.read_text(encoding="utf-8"))
        names: list[str] = []

        def walk(rows):
            for row in rows or []:
                name = str(row.get("name") or row.get("label") or "")
                if re.search(r"cost cent|phases? 1|annexed|bldg|building|\bACA\b", name, re.I):
                    names.append(name)
                walk(row.get("children"))

        walk(tree.get("expense"))
        walk(tree.get("income"))
        found[int(path.stem)] = names
    return found


def budgeted_assessments(data_dir: Path) -> dict[int, int]:
    """Each stored budget year's "Assessments" income for the year, in cents (PayHOA's monthly budget items summed)."""
    found = {}
    for path in sorted((Path(data_dir) / "payhoa" / "budgets").glob("*.json")):
        tree = json.loads(path.read_text(encoding="utf-8"))
        total = sum(int(i.get("amount") or 0) for row in tree.get("income") or [] if str(row.get("name")) == "Assessments"
                    for i in row.get("budgetItems") or [] if not i.get("deletedAt"))
        if total:
            found[int(path.stem)] = total
    return found


def dre_budgets(data_dir: Path) -> list[dict[str, Any]]:
    from jason.tasks.document_models import load

    rows = []
    for r in load(Path(data_dir)):
        f = r.get("fields") or {}
        if r["kind"] == "dre_report" and f.get("phase"):
            rows.append({"file": r["name"], "phase": f.get("phase"), "regularCents": f.get("built_out_assessment_cents"),
                         "costCenterCents": f.get("cost_center_assessment_cents"), "costCenterReserveCents": f.get("cost_center_reserve_cents"),
                         "adoptedCents": f.get("adopted_assessment_cents")})
    return sorted(rows, key=lambda r: (r["phase"], r["file"]))


def study_plans(data_dir: Path) -> list[dict[str, Any]]:
    from jason.tasks.reserves import load_studies

    rows = []
    for s in load_studies(Path(data_dir)):
        grouped = [c.description for c in s.components or () if re.search(r"bldg|building|\(20(?:19|20|21)\)", c.description or "", re.I)]
        rows.append({"preparer": getattr(s, "preparer", ""), "fiscalYear": getattr(s, "fiscal_year", None), "fundingPlans": 1,
                     "componentsByBuildingOrAge": len(grouped), "examples": grouped[:4]})
    return rows


def review(data_dir: Path, community: Any) -> dict[str, Any]:
    areas = community.association_common_areas()
    if not areas:
        return {"found": False, "note": "the specification sets no Association Common Areas"}
    centers = []
    for center in CostCenter:
        mine = [a for a in areas if a.cost_center is center]
        rule = next((r for r in community.cost_centers() if r.center is center), None)
        centers.append({"center": center.value, "acas": [a.number for a in mine], "buildings": [int(a.building) for a in mine],
                        "units": sum(a.unit_count for a in mine), "expenses": rule.expenses if rule else "", "allocation": rule.allocation if rule else "",
                        "source": rule.source if rule else ""})
    charges = charges_by_center(Path(data_dir), community)
    budgets = budget_lines(Path(data_dir))
    dre = dre_budgets(Path(data_dir))
    studies = study_plans(Path(data_dir))
    findings = []
    for year, by in charges.items():
        known = {c: amounts for c, amounts in by.items() if c != "unplaced"}
        usual = {c: max(amounts, key=amounts.get) for c, amounts in known.items() if amounts}
        if len(usual) == 2 and len(set(usual.values())) == 1:
            findings.append(f"{year}: every unit in both cost centers was charged the same monthly assessment "
                            f"(${next(iter(usual.values())) / 100:,.2f}); no cost center component is separated")
    units = sum(a.unit_count for a in areas)
    pooled = {}
    for year, total in budgeted_assessments(Path(data_dir)).items():
        per_unit = total / units / 12
        pooled[year] = {"annualCents": total, "perUnitMonthlyCents": round(per_unit)}
        usual = {max(a, key=a.get) for c, a in (charges.get(str(year)) or {}).items() if c != "unplaced" and a}
        if usual == {round(per_unit)}:
            findings.append(f"{year}: the budget's assessment income (${total / 100:,.2f}) divided by {units} units and 12 months is "
                            f"${per_unit / 100:,.2f}, the flat assessment charged: one pool, with no cost center component")
    empty = [year for year, names in budgets.items() if not names]
    if empty:
        findings.append(f"the {', '.join(map(str, empty))} budget{'s' if len(empty) > 1 else ''} carry no cost center line")
    if studies and all(s["fundingPlans"] == 1 for s in studies):
        findings.append("each reserve study has one funding plan for all units; neither cost center's reserves are kept apart")
    watt = [d for d in dre if d["costCenterCents"]]
    if watt:
        d = watt[-1]
        findings.append(f"the DRE reports for phases {', '.join(str(p) for p in dict.fromkeys(x['phase'] for x in watt))} told buyers of a Cost Center budget of "
                        f"${d['costCenterCents'] / 100:,.2f} a month on top of the ${(d['regularCents'] or 0) / 100:,.2f} regular assessment")
    return {"found": True, "centers": centers, "charges": charges, "budgetLines": budgets, "pooledBudget": pooled, "dreBudgets": dre,
            "reserveStudies": studies,
            "findings": findings,
            "caveats": ["The Phases 1 and 2 Property Cost Center's expenses are defined in 1.3(d)(ii) of the Phase 3 annexation; the "
                        "Phase 6 and 7 annexations cite 1.3(d)(ii) but their text goes from (i) to (iii), so whether Phase 3's words "
                        "govern the later phases is for counsel.",
                        "The budget sets one assessment income for all units; a flat rate close to the DRE reports' two components "
                        "summed comes from that pooled total, not from a split the budget records.",
                        "Whether and how to restore the cost centers is for the board, with counsel."]}


def review_lines(result: dict[str, Any]) -> list[str]:
    if not result.get("found"):
        return [result.get("note", "")]
    out = ["Assessment cost centers (each Watt declaration of annexation, section 1.3)", ""]
    for c in result["centers"]:
        out.append(f"  {c['center']}: A.C.A. {', '.join(map(str, c['acas']))} (buildings {', '.join(map(str, c['buildings']))}), {c['units']} units")
        out.append(f"      carries: {c['expenses']}; shared {c['allocation']}")
    out.append("")
    out.append("DRE public reports (monthly, built-out)")
    for d in result["dreBudgets"]:
        cc = f"  cost center ${d['costCenterCents'] / 100:,.2f}" if d["costCenterCents"] else ""
        adopted = f"  (adopted then: ${d['adoptedCents'] / 100:,.2f})" if d["adoptedCents"] else ""
        out.append(f"  phase {d['phase']} {d['file'][:22]:<22} regular {('$' + format((d['regularCents'] or 0) / 100, ',.2f')) if d['regularCents'] else '-'}{cc}{adopted}")
    out.append("")
    out.append("Monthly assessments charged, by cost center (amount: charges)")
    for year, by in result["charges"].items():
        out.append(f"  {year}: " + "; ".join(f"{c}: " + ", ".join(f"${a / 100:,.2f} x{n}" for a, n in amounts.items()) for c, amounts in by.items()))
    out.append("")
    out.append("Findings")
    out.extend(f"  ! {f}" for f in result["findings"])
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["review", "review_lines", "charges_by_center", "budget_lines", "budgeted_assessments", "dre_budgets", "study_plans"]
