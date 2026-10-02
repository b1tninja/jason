"""Briefs that answer a person's question from the stores, without a new search.

A board member asks about one unit ("what is on title, is it leased, is it
delinquent"), an escrow officer asks what the association knows before a
sale, someone asks what a recorded document is, and once a month someone
asks what recorded. Each brief reads the parcel histories and the
association's record that ``property_history`` already loads, and states
the bounds the models carry: no filing is not proof of purchase, an
expired lien is still of record, a cure is not a release, and a lien
indexes a person, not a parcel. Every function here is pure; the MCP tools
and the CLI load the stores and call them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from jason.community.filings import PROCESS_NOTES, Encumbrance, Family, Process, instrument_class, same_party
from jason.community.parcel_history import ParcelHistory
from jason.community.tax import parcel_number

PRIOR_LOAN_NOTE = "A prior owner's loan with no reconveyance in the cache is presumed paid at the sale that ended their tenure; the reconveyance may be indexed under the trustee alone."

CAVEATS = (
    "A lien indexes a person, not a parcel; one that opened while the owner held this unit is likely on it, and the pages count the rest.",
    PRIOR_LOAN_NOTE,
    "An expired mechanic's lien is unenforceable under Civil Code section 8460 and still of record until released.",
    "A rescission or a cancelled default cures a default and leaves the loan or lien open; only a release closes it.",
    "No solar lease filing is not proof of purchase; a filing can be missed or never recorded.",
    "Value figures are the community's own recorded sales read as comps; none is an appraisal.",
)


def lifecycle_dict(e: Encumbrance) -> dict[str, Any]:
    return {
        "process": e.process.value,
        "status": e.status,
        "opened": e.opened.recorded.isoformat() if e.opened.recorded else "",
        "closed": e.closed.isoformat() if e.closed else "",
        "unenforceableAfter": e.unenforceable_after.isoformat() if e.unenforceable_after else "",
        "debtor": list(e.debtor),
        "claimant": list(e.claimant),
        "steps": [{"number": s.number, "recorded": s.recorded.isoformat() if s.recorded else "", "filing": s.filing, "effect": s.effect} for s in e.steps],
        "law": PROCESS_NOTES.get(e.process, ""),
    }


def lien_row(lien, item=None, **extra) -> dict[str, Any]:
    """One lien for a brief: the owner, how the filing names them, where it stands against the title, and the lifecycle."""
    row: dict[str, Any] = {"owner": lien.owner, "nameMatch": lien.name_match.value, "namesakeRisk": lien.namesake_risk}
    if item is not None:
        from jason.community.title import lien_standing

        reading = lien_standing(item, lien)
        row["standing"] = reading.standing.name
        row["standingMeaning"] = reading.standing.value
        if reading.sale is not None:
            row["presumedPaidAt"] = reading.sale.isoformat()
    row.update(extra)
    row.update(lifecycle_dict(lien.encumbrance))
    return row


def _namesake(lien) -> str:
    """The sentence escrow reads when a lien names the owner by surname and given name only."""
    if not lien.namesake_risk:
        return ""
    names = [party for party in lien.encumbrance.debtor if party.split()[:1] == lien.owner.split()[:1]]
    shown = names[0] if names else ", ".join(lien.encumbrance.debtor[:1])
    return f" The filing names the owner only as {shown}; confirm it is this owner and not a namesake before relying on it."


def unit_brief(item: ParcelHistory, *, unit=None, plan=None, value=None) -> dict[str, Any]:
    """One unit on one page: title, chain, liens, solar, taxes, members, events, audit, value."""
    last = item.last_sale
    price, source = last.price_or_base if last else (None, "")
    open_here = [lien for lien in item.liens if lien.where != "another time or property" and lien.encumbrance.status != "closed"]
    open_liens = [lien for lien in open_here if on_current_owner(item, lien)]
    open_prior = [lien for lien in open_here if not on_current_owner(item, lien)]
    closed_here = sum(1 for lien in item.liens if lien.where != "another time or property" and lien.encumbrance.status == "closed")
    elsewhere = sum(1 for lien in item.liens if lien.where == "another time or property")
    brief: dict[str, Any] = {
        "apn": parcel_number(item.apn),
        "address": item.address,
        "building": item.building,
        "phase": item.phase,
        "developer": item.developer,
        "commonArea": item.association,
        "owner": {
            "names": list(item.owners),
            "since": last.recorded.isoformat() if last and last.recorded else "",
            "instrument": item.current_number,
            "instrumentDate": item.current_date.isoformat() if item.current_date else "",
            "instrumentConveys": item.current_conveys,
        },
        "chain": {
            "deeds": len(item.steps),
            "sales": len(item.sales),
            "reachesDeveloper": not item.open,
            "placedByScan": item.verified,
            "lastSale": {
                "recorded": last.recorded.isoformat() if last and last.recorded else "",
                "process": last.process if last else "",
                "priceCents": price,
                "priceSource": source,
                "from": list(last.grantors) if last else [],
            } if last else None,
        },
        "liens": {
            "open": [lien_row(lien, item, where=lien.where) for lien in open_liens],
            "openOnPriorOwners": [lien_row(lien, item, where=lien.where, presumed=_presumed(lien)) for lien in open_prior],
            "closedWhileOwningHere": closed_here,
            "otherTimeOrProperty": elsewhere,
        },
        "solar": _solar(item),
        "taxes": _taxes(item),
        "membership": _membership(item),
        "ownerEvents": [_event(event) for event in item.owner_events],
        "audit": [{"check": f.check, "number": f.number, "detail": f.detail} for f in item.findings],
        "notes": [{"note": n.note, "source": n.source, "noted": n.noted.isoformat() if n.noted else ""} for n in item.notes],
        "caveats": list(CAVEATS),
    }
    if unit is not None:
        brief["home"] = {
            "bedrooms": unit.bedrooms, "baths": unit.baths, "livingSqft": unit.living_sqft, "yearBuilt": unit.year_built,
            "garageSqft": unit.garage_sqft, "plan": plan.name if plan else "", "planDeveloper": plan.developer if plan else "",
        }
    if value is not None:
        brief["value"] = {
            "lastPriceCents": value.last_price, "priceSource": value.source, "compsCents": value.comps, "compsBasis": value.comps_basis,
            "indexedCents": value.indexed, "sizeAdjustedCents": value.size_estimate, "sizeBasis": value.size_basis,
            "appreciationPct": value.appreciation_pct, "annualPct": value.annual_pct, "assessedCents": value.assessed,
        }
    return brief


def escrow_brief(item: ParcelHistory, record=None) -> dict[str, Any]:
    """What the association can tell escrow before a sale of this unit, and what it cannot."""
    here = [lien for lien in item.liens if lien.where != "another time or property"]
    prior_loans = [lien for lien in here if lien.encumbrance.process is Process.LOAN and lien.encumbrance.status != "closed" and not on_current_owner(item, lien)]
    here = [lien for lien in here if lien not in prior_loans]
    assessment = [lien for lien in here if lien.encumbrance.process is Process.ASSESSMENT_LIEN]
    defaults = [lien for lien in here if lien.encumbrance.status in ("in default", "noticed for sale", "ordered for sale", "noticed for tax sale")]
    mechanics = [lien for lien in here if lien.encumbrance.process is Process.MECHANICS_LIEN]
    other_open = [
        lien for lien in here
        if lien.encumbrance.status != "closed" and lien.encumbrance.process not in (Process.ASSESSMENT_LIEN, Process.MECHANICS_LIEN, Process.LOAN)
    ]
    loans = [lien for lien in here if lien.encumbrance.process is Process.LOAN and lien.encumbrance.status != "closed"]
    deaths = [event for event in item.owner_events if event.still_on_title]
    brief: dict[str, Any] = {
        "apn": parcel_number(item.apn),
        "address": item.address,
        "building": item.building,
        "owner": list(item.owners),
        "ownerSince": item.last_sale.recorded.isoformat() if item.last_sale and item.last_sale.recorded else "",
        "assessmentLiens": [lien_row(lien, item) for lien in assessment],
        "defaults": [lien_row(lien, item) for lien in defaults],
        "mechanicsLiens": [lien_row(lien, item) for lien in mechanics],
        "otherOpenLiens": [lien_row(lien, item) for lien in other_open],
        "openLoans": len(loans),
        "priorOwnerLoansPresumedPaid": [lien_row(lien, item) for lien in prior_loans],
        "solar": _solar(item),
        "taxes": _taxes(item),
        "deathsOnTitle": [_event(event) for event in deaths],
        "membership": _membership(item),
        "association": _association_own(record) if record is not None else None,
        "tellEscrow": _tell_escrow(item, assessment, defaults, mechanics, other_open, deaths),
        "caveats": list(CAVEATS),
    }
    return brief


def _tell_escrow(item, assessment, defaults, mechanics, other_open, deaths) -> list[str]:
    lines: list[str] = []
    open_assessment = [lien for lien in assessment if lien.encumbrance.status != "closed"]
    if open_assessment:
        lines.append(f"The association's assessment lien of {open_assessment[-1].encumbrance.opened.recorded} stands; the demand must clear it.")
    elif assessment:
        lines.append("The association's earlier assessment liens on this owner were released.")
    else:
        lines.append("No association assessment lien names this owner.")
    if defaults:
        lines.append("A default or sale notice is of record: " + "; ".join(f"{lien.encumbrance.process.value} {lien.encumbrance.status}" for lien in defaults) + ".")
    for lien in mechanics:
        e = lien.encumbrance
        if e.status == "expired":
            lines.append(f"A mechanic's lien by {', '.join(e.claimant)} recorded {e.opened.recorded} expired unsued on {e.unenforceable_after}; it is unenforceable but of record until released." + _namesake(lien))
        elif e.status != "closed":
            lines.append(f"A mechanic's lien by {', '.join(e.claimant)} recorded {e.opened.recorded} is {e.status}." + _namesake(lien))
    for lien in other_open:
        e = lien.encumbrance
        if e.status == "lapsed":
            lines.append(
                f"A {e.process.value} by {', '.join(e.claimant)} recorded {e.opened.recorded} reached the end of its statutory life by {e.unenforceable_after} "
                "with no renewal in the index; it is unenforceable but of record until released, and title may still ask for the release." + _namesake(lien)
            )
            continue
        lines.append(f"A {e.process.value} by {', '.join(e.claimant)} recorded {e.opened.recorded} is {e.status}." + _namesake(lien))
    if item.solar is not None and not item.association:
        lines.append(f"Solar: {item.solar.standing.value}." + (f" {item.solar.note}" if item.solar.note else ""))
    if item.taxes is not None and item.taxes.status in ("due", "delinquent"):
        lines.append(f"County taxes read {item.taxes.status} on the stored bills.")
    for event in deaths:
        lines.append(f"A death record names {event.owner}, still a grantee on the newest deed; the trust or the survivor continues.")
    lines.append("The association does not maintain the panels and does not approve, deny, or assign anything here; this is what its records show.")
    return lines


def recent_filings(histories: tuple[ParcelHistory, ...], record, since: date) -> list[dict[str, Any]]:
    """Everything that recorded on or after ``since`` and touches a unit, an owner, or the association, with what to do about it."""
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in histories:
        for step in item.steps:
            if step.recorded and step.recorded >= since and step.number not in seen:
                seen.add(step.number)
                found.append({
                    "recorded": step.recorded.isoformat(), "number": step.number, "what": f"{step.process or 'deed'}: {', '.join(step.grantors)} to {', '.join(step.grantees)}",
                    "apn": parcel_number(item.apn), "address": item.address,
                    "action": "new owner: update the membership record and the escrow file" if step.reassesses else "title restated; the member is the same",
                })
        for lien in item.liens:
            if lien.where == "another time or property":
                continue
            e = lien.encumbrance
            for s in e.steps:
                if s.recorded and s.recorded >= since and s.number not in seen:
                    seen.add(s.number)
                    found.append({
                        "recorded": s.recorded.isoformat(), "number": s.number, "what": f"{s.filing}: {e.process.value}, now {e.status}",
                        "apn": parcel_number(item.apn), "address": item.address, "owner": lien.owner,
                        "action": _lien_action(e, s),
                    })
        for event in item.owner_events:
            if event.recorded and event.recorded >= since and event.number not in seen and event.during_tenure:
                seen.add(event.number)
                found.append({
                    "recorded": event.recorded.isoformat(), "number": event.number, "what": f"{event.filing}: {event.kind}",
                    "apn": parcel_number(item.apn), "address": item.address, "owner": event.owner,
                    "action": _event_action(event),
                })
    if record is not None:
        for label, items in (("placed by the association", record.placed), ("against the association", record.against), ("construction lien against a developer", record.construction)):
            for e in items:
                for s in e.steps:
                    if s.recorded and s.recorded >= since and s.number not in seen:
                        seen.add(s.number)
                        found.append({
                            "recorded": s.recorded.isoformat(), "number": s.number, "what": f"{s.filing}: {e.process.value} {label}, now {e.status}",
                            "apn": "", "address": "the association", "action": _lien_action(e, s),
                        })
        for g in record.governing:
            if g.recorded and g.recorded >= since and g.number not in seen:
                seen.add(g.number)
                found.append({"recorded": g.recorded.isoformat(), "number": g.number, "what": f"{g.filing}: {g.role}", "apn": "", "address": "the association", "action": "file with the association's records under Civil Code 5200"})
    found.sort(key=lambda row: (row["recorded"], row["number"]))
    return found


def on_current_owner(item: ParcelHistory, lien) -> bool:
    """True when the lifecycle's owner is a grantee on the newest deed."""
    return any(same_party(lien.owner, name) for name in item.owners)


def _presumed(lien) -> str:
    if lien.encumbrance.process is Process.LOAN:
        return "paid at the sale that ended this owner's tenure; no reconveyance cached"
    return "still of record unless paid at that sale; read the release"


def _event_action(event) -> str:
    """What the membership record does with an owner event. A transfer on death deed is a plan, not a death."""
    if event.kind.startswith("death"):
        return "membership record: note the death and who continues"
    if event.kind.startswith("transfer on death"):
        return "note on the owner's file: a beneficiary is named; nothing changes until a death affidavit records"
    return "note on the owner's file"


def _lien_action(e: Encumbrance, s) -> str:
    if e.process is Process.ASSESSMENT_LIEN:
        return "collections: the association's own lien moved" if s.effect != "closes" else "collections: the association's lien was released"
    if s.effect == "closes":
        return "released; nothing to do"
    if e.status in ("in default", "noticed for sale"):
        return "an owner is in default; watch for a trustee's deed, which changes the member"
    if e.process is Process.TAX_DEFAULT:
        return "tax default; the parcel can be sold for taxes"
    if e.process is Process.MECHANICS_LIEN:
        return "a contractor's claim; note the ninety-day mark"
    if e.process is Process.FIXTURE_FILING:
        return "a fixture filing; if by a solar lessor, the unit's solar standing changed"
    return _LIEN_MEANING.get(e.process, "note on the owner's file") if s.effect != "advances" or e.process is not Process.LOAN else (
        "a substitution of trustee, which often comes before a reconveyance or a notice of default; watch the next filing"
    )


# What a new lien of each process means for the unit. Nothing here is the association's to act on but the note.
_LIEN_MEANING = {
    Process.LOAN: "a new loan on the owner; ordinary",
    Process.UTILITY_LIEN: "a delinquent utility account became a lien on the owner; it clears on payment, and a sale needs its termination",
    Process.JUDGMENT_LIEN: "a judgment creditor's lien on the owner's real property for ten years; a sale needs it satisfied",
    Process.STATE_TAX_LIEN: "a state tax lien on the owner's property; a sale needs its release",
    Process.FEDERAL_TAX_LIEN: "a federal tax lien on the owner's property; a sale needs its release",
    Process.COUNTY_TAX_LIEN: "the tax collector's lien for unsecured taxes; a sale needs its release",
    Process.SUPPORT_LIEN: "a child support lien on the owner's property; the agency releases it when paid",
}


def lifecycle_lookup(histories: tuple[ParcelHistory, ...], record, number: str) -> dict[str, Any]:
    """The lifecycle a document number belongs to, wherever it sits: a unit's owner, the association, or a developer."""
    digits = "".join(ch for ch in number if ch.isdigit())
    for item in histories:
        for step in item.steps:
            if step.number == digits:
                return {"found": True, "where": "chain", "apn": parcel_number(item.apn), "address": item.address, "process": step.process, "recorded": step.recorded.isoformat() if step.recorded else "", "from": list(step.grantors), "to": list(step.grantees)}
        for lien in item.liens:
            if any(s.number == digits for s in lien.encumbrance.steps):
                return {"found": True, "where": "owner lien", "apn": parcel_number(item.apn), "address": item.address, "owner": lien.owner, "tenure": lien.where, **lifecycle_dict(lien.encumbrance)}
        for event in item.owner_events:
            if event.number == digits:
                return {"found": True, "where": "owner event", "apn": parcel_number(item.apn), "address": item.address, "owner": event.owner, "kind": event.kind, "filing": event.filing}
    if record is not None:
        for label, items in (("placed by the association", record.placed), ("against the association", record.against), ("construction lien", record.construction)):
            for e in items:
                if any(s.number == digits for s in e.steps):
                    return {"found": True, "where": label, **lifecycle_dict(e)}
        for g in record.governing:
            if g.number == digits:
                return {"found": True, "where": "governing instrument", "role": g.role, "filing": g.filing, "phase": g.phase, "recorded": g.recorded.isoformat() if g.recorded else ""}
    return {"found": False, "number": digits, "note": "not on any chain, lifecycle, or record in the stores; recorder_detail reads the index"}


def assessment_liens(histories: tuple[ParcelHistory, ...], record) -> dict[str, Any]:
    """The association's own liens, unit by unit, with where each stands under Civil Code sections 5650 to 5720."""
    units: list[dict[str, Any]] = []
    others: list[dict[str, Any]] = []
    matched: set[str] = set()
    for item in histories:
        for lien in item.liens:
            e = lien.encumbrance
            if e.process is not Process.ASSESSMENT_LIEN:
                continue
            row = {"apn": parcel_number(item.apn), "address": item.address, "owner": lien.owner, "currentOwner": list(item.owners), "tenure": lien.where, **lifecycle_dict(e)}
            if not lien.community:
                # Another association's lien on an owner's unit in that community; it is not ours and not on this unit.
                others.append({k: row[k] for k in ("apn", "address", "owner", "claimant", "status", "opened")})
                continue
            matched.add(e.opened.number)
            units.append(row)
    unplaced = [lifecycle_dict(e) for e in (record.placed if record is not None else ()) if e.opened.number not in matched]
    open_count = sum(1 for row in units if row["status"] != "closed")
    return {
        "count": len(units), "open": open_count, "units": units, "notOnAUnit": unplaced,
        "otherAssociations": others,
        "law": PROCESS_NOTES.get(Process.ASSESSMENT_LIEN, ""),
        "note": "The sheet is the handoff. Jason does not submit an account to a collection agency, and does not start a foreclosure.",
    }


def explain_filing(text: str) -> dict[str, Any]:
    """What a filing code or name is: family, sides, the process it opens or closes, and the law behind that process."""
    value = " ".join(str(text or "").split())
    digits = "".join(ch for ch in value if ch.isdigit())
    klass = instrument_class(digits if len(digits) == 3 and digits == value.strip() else "", value if not (len(digits) == 3 and digits == value.strip()) else "")
    if klass.family is Family.OTHER and not klass.code:
        return {"found": False, "query": value, "note": "no registry row; recorder_detail reads the index and index_survey lists what is unmodeled"}
    return {
        "found": bool(klass.code or klass.name),
        "code": klass.code, "name": klass.name, "family": klass.family.value,
        "rSide": klass.r_side, "eSide": klass.e_side,
        "process": klass.process.value if klass.process else "",
        "effect": klass.effect or "none",
        "law": PROCESS_NOTES.get(klass.process, "") if klass.process else "",
    }


def brief_markdown(brief: dict[str, Any]) -> str:
    """A unit brief as a short page."""
    owner = brief.get("owner", {})
    lines = [f"# {brief.get('address') or brief.get('apn')}", ""]
    lines.append(f"- **Parcel** {brief.get('apn')}, building {brief.get('building')}, phase {brief.get('phase')}, sold by {brief.get('developer')}")
    if brief.get("home"):
        h = brief["home"]
        lines.append(f"- **Home** {h.get('bedrooms')} bd, {h.get('baths')} ba, {h.get('livingSqft')} sq ft, built {h.get('yearBuilt')}" + (f", {h['plan']}" if h.get("plan") else ""))
    lines.append(f"- **Owner** {', '.join(owner.get('names', []))} since {owner.get('since')} under {owner.get('instrument')}")
    chain = brief.get("chain", {})
    last = chain.get("lastSale") or {}
    if last:
        price = f"${last['priceCents'] // 100:,}" if last.get("priceCents") else "unpriced"
        lines.append(f"- **Chain** {chain.get('deeds')} deeds, {chain.get('sales')} sales, {'reaches' if chain.get('reachesDeveloper') else 'does not reach'} the developer; last sale {last.get('recorded')} {last.get('process')} at {price} ({last.get('priceSource')})")
    liens = brief.get("liens", {})
    if liens.get("open"):
        lines.append(f"- **Open liens on the current owner** " + "; ".join(f"{l['process']} by {', '.join(l['claimant'])} ({l['status']})" for l in liens["open"]))
    else:
        lines.append("- **Open liens on the current owner** none")
    if liens.get("openOnPriorOwners"):
        lines.append(f"- **On prior owners, not closed in the cache** {len(liens['openOnPriorOwners'])}: " + "; ".join(f"{l['process']} on {l['owner']} ({l['presumed']})" for l in liens["openOnPriorOwners"]))
    if brief.get("solar"):
        lines.append(f"- **Solar** {brief['solar'].get('meaning')}")
    if brief.get("taxes"):
        lines.append(f"- **Taxes** {brief['taxes'].get('status')}")
    if brief.get("membership"):
        lines.append(f"- **Members** {brief['membership'].get('verdict')}: {', '.join(brief['membership'].get('members', []))}")
    if brief.get("value"):
        v = brief["value"]
        comps = f"${v['compsCents'] // 100:,}" if v.get("compsCents") else "none"
        lines.append(f"- **Value** recent comps {comps} ({v.get('compsBasis')}); appreciation {v.get('appreciationPct')}% against the last price")
    if brief.get("audit"):
        lines.append("- **Audit** " + "; ".join(f"{f['check']}: {f['detail']}" for f in brief["audit"]))
    if brief.get("tellEscrow"):
        lines.append("")
        lines.append("## For escrow")
        lines.append("")
        lines.extend(f"- {line}" for line in brief["tellEscrow"])
    lines.append("")
    lines.append("Bounds: " + " ".join(brief.get("caveats", [])))
    return "\n".join(lines)


def _solar(item: ParcelHistory) -> dict[str, Any] | None:
    record = item.solar
    if record is None:
        return None
    current = record.current_filing
    return {
        "standing": record.standing.name, "meaning": record.standing.value, "lessor": record.lessor,
        "currentFiling": current.number if current else "", "note": record.note,
        "filings": [{"number": f.number, "recorded": f.recorded.isoformat() if f.recorded else "", "against": f.owner, "status": f.status, "terminated": f.closed.isoformat() if f.closed else ""} for f in record.filings],
    }


def _taxes(item: ParcelHistory) -> dict[str, Any] | None:
    taxes = item.taxes
    if taxes is None:
        return None
    return {
        "status": taxes.status, "firstYear": taxes.first_year, "lastYear": taxes.last_year, "missingYears": list(taxes.missing_years),
        "unpaid": [{"year": year, "cents": cents} for year, cents in taxes.unpaid],
        "delinquent": [{"year": year, "cents": cents} for year, cents in taxes.delinquent],
    }


def _membership(item: ParcelHistory) -> dict[str, Any] | None:
    check = item.membership
    if check is None:
        return None
    return {"verdict": check.verdict, "members": list(check.members), "owners": list(check.owners), "unmatchedMembers": list(check.unmatched_members), "unmatchedOwners": list(check.unmatched_owners), "since": check.since.isoformat() if check.since else ""}


def _event(event) -> dict[str, Any]:
    return {"owner": event.owner, "number": event.number, "recorded": event.recorded.isoformat() if event.recorded else "", "filing": event.filing, "kind": event.kind, "duringTenure": event.during_tenure, "stillOnTitle": event.still_on_title}


def _association_own(record) -> dict[str, Any]:
    against = [lifecycle_dict(e) for e in record.against if e.status != "closed"]
    return {
        "openAgainstAssociation": against,
        "openPlacedByAssociation": sum(1 for e in record.placed if e.status != "closed"),
        "constructionLiensOpen": [lifecycle_dict(e) for e in record.construction if e.status not in ("closed", "expired")],
    }


@dataclass(frozen=True)
class _Unused:
    """Keeps the dataclass import for readers who extend the briefs with records."""

    value: str = ""


def board_digest(histories: tuple[ParcelHistory, ...], record, since: date, *, limit: int = 12, ledger=None, finance=None) -> dict[str, Any]:
    """What the board should know now, from the stores: what recorded since ``since``, the liens a person acts on,
    the association's own liens, the solar standings, and the owners in default. Each list is capped at ``limit``
    with the full count beside it; the tools named in ``more`` give the rest."""
    from jason.community.title import ATTENTION, LienStanding, standing_counts, title_watch

    filings = recent_filings(histories, record, since)
    rows = title_watch(histories)
    here = [row for row in rows if row.standing is not LienStanding.ELSEWHERE]
    attention = [row for row in here if row.standing in ATTENTION]
    ours = assessment_liens(histories, record)
    solar: dict[str, int] = {}
    for item in histories:
        if item.solar is not None and not item.association:
            key = item.solar.standing.name
            solar[key] = solar.get(key, 0) + 1

    def rows_of(selected) -> list[dict[str, Any]]:
        return [row.as_dict() for row in selected[:limit]]

    by_standing = {standing: [row for row in attention if row.standing is standing] for standing in ATTENTION}
    return {
        "since": since.isoformat(),
        "recorded": {"count": len(filings), "rows": filings[:limit]},
        "liens": {
            "counts": standing_counts(here),
            "inDefault": rows_of(by_standing[LienStanding.IN_DEFAULT]),
            "releaseDue": rows_of(by_standing[LienStanding.RELEASE_DUE]),
            "standsOnPrior": rows_of(by_standing[LienStanding.STANDS_ON_PRIOR]),
            "standsCount": len(by_standing[LienStanding.STANDS]),
            "namesakeRisks": sum(1 for row in here if row.namesake_risk and row.standing is not LienStanding.RELEASED),
        },
        "association": {
            "open": [row for row in ours["units"] if row["status"] != "closed"],
            "otherAssociations": ours["otherAssociations"],
            "notOnAUnit": ours["notOnAUnit"],
        },
        "solar": solar,
        "collections": _collections_summary(histories, ledger, limit) if ledger else None,
        "finance": _finance_brief(finance) if finance else None,
        "more": {
            "recorded": "recent_filings(since)", "liens": "title_watch(attention=True)", "association": "assessment_liens()",
            "unit": "unit_brief(apn)", "sale": "escrow_brief(apn)", "duty": "duty_brief(anchor)", "law": "authorities(citation)",
            "collections": "association_collections()",
            "finance": "budget_status(), bank_accounts()",
        },
        "caveats": list(CAVEATS),
    }


def _collections_summary(histories, ledger, limit: int) -> dict[str, Any]:
    """The ledger beside the association's liens: releases owed first, then liens securing debt, then past due with no lien."""
    from jason.community.collections import CollectionStanding, collections

    rows = collections(histories, ledger)
    pick = lambda standing: [row.as_dict() for row in rows if row.standing is standing][:limit]
    return {
        "releaseDue": pick(CollectionStanding.RELEASE_DUE),
        "lienSecuresDebt": pick(CollectionStanding.LIEN_SECURES_DEBT),
        "owedNoLien": pick(CollectionStanding.OWED_NO_LIEN),
        "pastDueCents": sum(row.past_due_cents for row in rows if row.past_due_cents > 0),
    }


def _finance_brief(summary: dict[str, Any]) -> dict[str, Any]:
    """The budget against actual year to date, the three biggest expense gaps, and the balances, from ``finance_summary``."""
    return {
        "year": summary.get("year"), "throughMonth": summary.get("throughMonth"), "syncedAt": summary.get("syncedAt"),
        "yearToDate": summary.get("yearToDate"), "expenseGaps": (summary.get("expenseGaps") or [])[:3],
        "accounts": summary.get("accounts"), "reserveTotalCents": summary.get("reserveTotalCents"),
    }
