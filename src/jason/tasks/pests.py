"""The pest control program, read from the vendor's portal: what was applied, where, how often, and what the stations show.

Inputs are the portal snapshots ``jason vendors --sync`` saves (``data/vendors/<key>/<customer>/account.json``)
and, when ``jason pests --fetch`` has run, each product's label and safety data sheet under
``data/pesticides/``. The brief is for the board and the manager: every product with its EPA
registration, active ingredient, class, and the California rules that apply to it; the rodent
program's activity by month; the visits by building; the vendor's open recommendations; and the
duties the association keeps (see docs/pest-management.md). It decides nothing and changes nothing.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.pest_visits import Activity, read_note
from jason.tasks.vendor_portals import load_accounts


@dataclass
class ProductUse:
    """One product across every visit: how often, how much, where, against what."""

    product: str
    epa_number: str
    manufacturer: str = ""
    active_ingredient: str = ""
    applications: int = 0
    first: str = ""
    last: str = ""
    properties: set[str] = field(default_factory=set)
    methods: set[str] = field(default_factory=set)
    areas: set[str] = field(default_factory=set)
    targets: set[str] = field(default_factory=set)
    diluted: dict[str, float] = field(default_factory=dict)
    concentrated: dict[str, float] = field(default_factory=dict)
    by_year: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "product": self.product, "epaNumber": self.epa_number, "manufacturer": self.manufacturer,
            "activeIngredient": self.active_ingredient, "applications": self.applications, "first": self.first,
            "last": self.last, "properties": sorted(self.properties), "methods": sorted(m for m in self.methods if m),
            "areas": sorted(a for a in self.areas if a), "targets": sorted(t for t in self.targets if t)[:30],
            "diluted": {k: round(v, 3) for k, v in self.diluted.items()},
            "concentrated": {k: round(v, 4) for k, v in self.concentrated.items()}, "byYear": dict(sorted(self.by_year.items())),
        }


_AMOUNT = re.compile(r"([\d.]+)\s*([A-Za-z]+)")


def _add(totals: dict[str, float], text: str) -> None:
    match = _AMOUNT.match(text or "")
    if match:
        totals[match.group(2)] = totals.get(match.group(2), 0.0) + float(match.group(1))


def product_uses(accounts: list[dict[str, Any]]) -> list[ProductUse]:
    """Every product applied, from the chemical usage report rows, with the visit records' details beside them."""
    found: dict[tuple[str, str], ProductUse] = {}
    for account in accounts:
        name = account["customer"]["name"]
        for app in account["applications"]:
            key = (app["product"], app["epa_number"])
            use = found.setdefault(key, ProductUse(app["product"], app["epa_number"]))
            use.applications += 1
            day = app["day"] or ""
            use.first = min(use.first or day, day) if day else use.first
            use.last = max(use.last, day)
            use.properties.add(name)
            use.areas.update(a.strip() for a in app["areas"].split(","))
            use.targets.update(t.strip() for t in app["targets"].split(","))
            _add(use.diluted, app["diluted"])
            _add(use.concentrated, app["concentrated"])
            if day:
                use.by_year[day[:4]] = use.by_year.get(day[:4], 0) + 1
        for visit in account["services"]:
            for product in visit["products"]:
                use = found.get((product["name"], product["epa_number"]))
                if use is None:
                    continue
                use.manufacturer = use.manufacturer or product["manufacturer"]
                use.active_ingredient = use.active_ingredient or product["active_ingredient"]
                use.methods.add(product["method"])
    return sorted(found.values(), key=lambda u: (-u.applications, u.product))


def rodent_program(account: dict[str, Any]) -> dict[str, Any]:
    """The bait stations visit by visit: checked, refilled, and the highest activity each month."""
    months: dict[str, int] = {}
    readings = []
    for visit in account["services"]:
        reading = read_note(visit["notes"])
        readings.append((visit["day"], reading))
        if reading.rodent_activity is not None and visit["day"]:
            month = visit["day"][:7]
            months[month] = max(months.get(month, 0), int(reading.rodent_activity))
    rated = [r.rodent_activity for _d, r in readings if r.rodent_activity is not None]
    above = [(d, r.rodent_activity.name.lower().replace("_", " ")) for d, r in readings
             if r.rodent_activity is not None and r.rodent_activity >= Activity.MODERATE]
    return {
        "visits": len(readings),
        "stationsChecked": sum(1 for _d, r in readings if r.stations_checked),
        "stationsRefilled": sum(1 for _d, r in readings if r.stations_refilled),
        "rated": len(rated),
        "byActivity": {a.name.lower(): sum(1 for x in rated if x is a) for a in Activity if any(x is a for x in rated)},
        "moderateOrMore": sorted(above, reverse=True),
        "monthlyHighest": {m: Activity(v).name.lower() for m, v in sorted(months.items())},
    }


def building_coverage(account: dict[str, Any]) -> dict[str, Any]:
    """How often each building was named in a visit note, and the last time."""
    count: dict[int, int] = defaultdict(int)
    last: dict[int, str] = {}
    for visit in account["services"]:
        for building in read_note(visit["notes"]).buildings:
            count[int(building)] += 1
            last[int(building)] = max(last.get(int(building), ""), visit["day"] or "")
    return {str(b): {"visits": count[b], "last": last[b]} for b in sorted(count)}


def inspection_reports(account: dict[str, Any], folder: Path) -> list[dict[str, Any]]:
    """The vendor's inspection reports on the account (rodent proofing, bird exclusion): date, findings, and the quote."""
    found = []
    for doc in account["documents"]:
        if doc["kind"] != "document" or "inspection" not in doc["description"].lower():
            continue
        path = folder / "files" / f"{doc['document_id']}.{doc['extension']}"
        text = ""
        if path.is_file():
            try:
                import pymupdf

                with pymupdf.open(str(path)) as pdf:
                    text = "\n".join(page.get_text() for page in pdf)
            except Exception:  # an unreadable report is still listed
                text = ""
        total = re.search(r"Total Cost\s*=\s*\$\s*([\d,]+)", text)
        points = re.search(r"Total Entry Points Located:\s*(\d+)", text)
        notes = re.search(r"Notes:\s*(.*?)(?:\*\*|Technician Signature)", text, re.S)
        found.append({
            "date": doc["added"], "report": doc["description"], "file": str(path) if path.is_file() else None,
            "entryPoints": int(points.group(1)) if points else None,
            "quoteCents": int(total.group(1).replace(",", "")) * 100 if total else None,
            "findings": " ".join(notes.group(1).split()) if notes else "",
            "activity": bool(re.search(r"Current Activity/Evidence Present:\s*\[X\]\s*Yes", text)),
        })
    return found


def pest_brief(data_dir: Path, portal: Any, *, today: date | None = None) -> dict[str, Any]:
    """The whole program on one page, per property on the vendor account."""
    from jason.tasks.vendor_portals import portal_root

    accounts = load_accounts(data_dir, portal.key)
    if not accounts:
        return {"found": False, "note": f"no {portal.key} portal data; run jason vendors --sync"}
    from jason.community.pesticide_facts import check_applications, ingredients_of
    from jason.community.pesticides import EpaNumber
    from jason.tasks.pesticides import load_product, pesticide_root

    root = portal_root(data_dir, portal.key)
    properties = []
    for account in accounts:
        folder = root / account["customer"]["customer_id"]
        buildings = {v["day"]: tuple(int(b) for b in read_note(v["notes"]).buildings) for v in account["services"]}
        labels = {p["name"]: p["active_ingredient"] for v in account["services"] for p in v["products"]}
        products = [u.as_dict() for u in product_uses([account])]
        for product in products:
            fetched = load_product(data_dir, product["epaNumber"], product["product"])
            if fetched:
                reg = fetched.get("registration") or {}
                ca = fetched.get("californiaRegistration") or {}
                sds = fetched.get("sds") or {}
                product["registration"] = {
                    "name": reg.get("name"), "registrant": reg.get("registrant"), "status": reg.get("status"),
                    "signalWord": reg.get("signal_word"), "restrictedUse": reg.get("restricted_use"),
                    "activeIngredients": reg.get("active_ingredients"), "labelDate": reg.get("label_date"),
                    "california": ca.get("number"), "californiaStatus": ca.get("status"),
                }
                product["sds"] = {
                    "product": sds.get("product"), "revised": sds.get("revised"), "ghsSignalWord": sds.get("signal_word"),
                    "hazards": [f"{code} {text}".strip() for code, text in sds.get("hazards") or []],
                    "firstAidSwallowed": (sds.get("first_aid") or {}).get("swallowed", ""),
                    "ecology": list(sds.get("ecology") or [])[:3], "prop65": sds.get("prop65", ""),
                    "emergency": list(sds.get("emergency") or []),
                    "files": {k: str(pesticide_root(data_dir) / EpaNumber.parse(product["epaNumber"]).key / fetched[k])
                              for k in ("labelFile", "specimenLabelFile", "sdsFile") if fetched.get(k)},
                }
            product["ingredients"] = [{
                "name": i.name, "class": i.chemical_class, "action": i.action, "peopleAndPets": i.people_and_pets,
                "bees": i.bees.value, "aquatic": i.aquatic.value, "california": i.california, "sources": list(i.sources),
            } for i in ingredients_of(product["activeIngredient"] or labels.get(product["product"], ""), product["product"])]
        properties.append({
            "customerId": account["customer"]["customer_id"],
            "name": account["customer"]["name"],
            "address": account["customer"]["address"],
            "plan": [s["title"] for s in account["subscriptions"]],
            "products": products,
            "labelChecks": _with_technicians(check_applications(account["applications"], buildings, labels), account, portal.license),
            "rodents": rodent_program(account),
            "buildings": building_coverage(account),
            "inspections": inspection_reports(account, folder),
        })
    return {"found": True, "vendor": portal.vendor, "license": _license(portal.license), "properties": properties}


def _license(license: Any) -> dict[str, Any] | None:
    if license is None:
        return None
    return {"board": license.board, "number": license.number, "kind": license.kind, "classes": list(license.classes),
            "status": license.status, "issued": str(license.issued), "verified": str(license.verified),
            "rosterRead": f"{license.relationships_seen} of {license.relationships_total}", "lookup": license.lookup}


def _with_technicians(checks: list[dict], account: dict[str, Any], license: Any) -> list[dict]:
    """Each check gets the technician on that visit and, for the certified-applicator question, what the license roster shows."""
    by_day = {v["day"]: v["technician"] for v in account["services"]}
    for check in checks:
        technician = by_day.get(check["date"], "")
        if not technician:
            continue
        check["technician"] = technician
        if check["kind"] == "question" and "12838" in check.get("source", "") and license is not None:
            person = license.person(technician)
            if person and person.role in ("Operator", "Field Representative"):
                check["finding"] = (f"Applied by {technician}, {person.role} {person.number} ({person.status}, verified "
                                    f"{license.verified}). The record lists landscape or yard areas; were plants, trees, or turf treated?")
                check["kind"] = "answered"
            else:
                check["finding"] += (f" Applied by {technician}, who is not among the {license.relationships_seen} of "
                                     f"{license.relationships_total} license relationships recorded on {license.verified}.")
    return checks




def brief_lines(brief: dict[str, Any]) -> list[str]:
    if not brief.get("found"):
        return [brief.get("note", "no pest program data")]
    out = [f"{brief['vendor']}"]
    lic = brief.get("license")
    if lic:
        out.append(f"License: {lic['board']} {lic['kind'].lower()} {lic['number']}, {', '.join(lic['classes'])}, {lic['status']}; "
                   f"issued {lic['issued']}, verified {lic['verified']} (roster read {lic['rosterRead']})")
    for p in brief["properties"]:
        out.append("")
        out.append(f"{p['name']} ({p['customerId']}, {p['address']}): {', '.join(p['plan']) or 'no plan'}")
        for u in p["products"]:
            amounts = "; ".join(f"{v:g} {k}" for k, v in u["concentrated"].items()) or "-"
            kinds = ", ".join(sorted({i["class"] for i in u.get("ingredients", [])})) or "class unknown"
            bees = "/".join(sorted({i["bees"] for i in u.get("ingredients", [])})) or "?"
            water = "/".join(sorted({i["aquatic"] for i in u.get("ingredients", [])})) or "?"
            reg = u.get("registration") or {}
            signal = f"; label {reg['signalWord']}" if reg.get("signalWord") else ""
            out.append(f"  {u['product']:<26} EPA {u['epaNumber']:<14} x{u['applications']:<3} {u['first']}..{u['last']} "
                       f"active {amounts} | {kinds}; bees {bees}, aquatic {water}{signal}")
            sds = u.get("sds") or {}
            if sds:
                ca = f"CA {reg.get('california')} {reg.get('californiaStatus') or ''}".strip() if reg.get("california") else "CA -"
                hazards = "; ".join(sds.get("hazards") or []) or "no GHS hazard statements"
                out.append(f"      SDS {sds.get('revised') or '?'}: GHS {sds.get('ghsSignalWord') or '?'}; {hazards}; {ca}")
        checks = p.get("labelChecks") or []
        for kind, title in (("label", "Label limits the record shows exceeded"), ("question", "Questions for the vendor"),
                            ("answered", "Answered by the license roster")):
            rows = [c for c in checks if c["kind"] == kind]
            if rows:
                out.append(f"  {title}:")
                for c in rows:
                    where = f" ({c['where']})" if c.get("where") else ""
                    out.append(f"    {c['date']} {c['product']}{where}: {c['finding']}")
        r = p["rodents"]
        if r["rated"]:
            out.append(f"  rodent stations: {r['rated']} ratings {r['byActivity']}; moderate or more: "
                       + (", ".join(f"{d} {a}" for d, a in r["moderateOrMore"]) or "none"))
        if p["buildings"]:
            out.append("  visits by building: " + ", ".join(f"{b}: {v['visits']} (last {v['last']})" for b, v in p["buildings"].items()))
        for i in p["inspections"]:
            quote = f"${i['quoteCents'] / 100:,.0f}" if i["quoteCents"] else "-"
            out.append(f"  {i['date']} {i['report']}: {i['entryPoints']} entry points, quote {quote}; {i['findings'][:160]}")
    return out


__all__ = ["ProductUse", "product_uses", "rodent_program", "building_coverage", "inspection_reports", "pest_brief", "brief_lines"]
