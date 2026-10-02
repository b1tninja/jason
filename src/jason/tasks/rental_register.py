"""The rental register for the board's CC&Rs 4.15 work: each rented unit (and each unit a lease or a manager's email
ties to renting) with its owners, the Rental and Rental Approved tags, the lease on file and whether it runs, its tenants
beside the unit's other contacts, its property manager (by lease, other contact, and email), whether the manager has a Property Manager record,
and what a person might do next. Reads disk only (the catalog, ``data/leases/leases.json``, the Gmail headers); writes
nothing to PayHOA.

A manager is recognized three ways, strongest first: a lease names them; they are the unit's other contact; or they
write from a property manager's domain (``mystique/senders.py``, ``SourceKind.PROPERTY_MANAGER``) in a thread with the
unit's owner or naming the unit. A domain that only looks like a manager's (a "properties", "management", or "rentals"
domain not in the directory) is a candidate: a realty selling a unit, a title company, or another association's manager
looks the same in a header.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

LOOKS_LIKE = re.compile(r"propert|management|mgmt|rentals?\b|leasing", re.I)


@dataclass
class ManagerEvidence:
    name: str
    how: list[str] = field(default_factory=list)     # "lease 2025-11-28 to 2026-11-27", "other contact", "email: 4 threads"
    directory: bool = False                          # a property manager in mystique/senders.py


@dataclass
class RentalRow:
    unit: str
    unit_id: int
    owners: list[str]
    rental: bool
    approved: bool
    property_managed: bool
    lease: str = ""                  # the latest lease's term and file
    lease_runs: bool | None = None
    tenants_listed: list[str] = field(default_factory=list)
    tenants_on_lease_unlisted: list[str] = field(default_factory=list)
    managers: list[ManagerEvidence] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)


def _words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (name or "").casefold()) if len(w) > 1}


def manager_threads(messages: list[dict[str, Any]], senders: Iterable[Any], unit_labels: list[str]) -> tuple[
        dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """Each unit's property managers by their email (directory managers, and look-alike candidates), counting the
    threads that tie them to the unit: a thread with the unit's owner among its parties, or a subject naming the unit."""
    from jason.community.base import read_unit_address

    known = {d: s.name for s in senders if s.kind.value == "owner's property manager" for d in s.domains}
    labels = {read_unit_address(l): l for l in unit_labels}
    threads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in messages:
        threads[m["threadId"]].append(m)
    named: dict[str, Counter] = defaultdict(Counter)
    candidates: dict[str, Counter] = defaultdict(Counter)
    for msgs in threads.values():
        domains = {d for m in msgs for d in m.get("domains") or []}
        units = set()
        for m in msgs:
            for p in m.get("parties") or []:
                if p.startswith("owner of "):
                    units.add(p[len("owner of "):])
            hit = labels.get(read_unit_address(m.get("subject") or ""))
            if hit:
                units.add(hit)
        for d in domains:
            name = next((n for k, n in known.items() if d == k or d.endswith("." + k)), None)
            for u in units:
                if name:
                    named[u][name] += 1
                elif LOOKS_LIKE.search(d.split(".")[0]):
                    candidates[u][d] += 1
    return {u: dict(c) for u, c in named.items()}, {u: dict(c) for u, c in candidates.items()}


def register(units: list[dict[str, Any]], people: dict[int, str], contacts: dict[int, list[dict[str, Any]]],
             leases: list[Any], tags: Iterable[Any], messages: list[dict[str, Any]], senders: Iterable[Any],
             today: date, deeds: dict[str, date] | None = None) -> tuple[list[RentalRow], dict[str, dict[str, int]]]:
    """The register's rows and the look-alike manager domains by unit (candidates for a person to sort)."""
    from jason.community.base import read_unit_address
    from jason.community.tags import TagPurpose, tag_names

    tags = tuple(tags)
    rental = next((t.name.casefold() for t in tags if t.purpose is TagPurpose.OCCUPANCY and t.value == "Rented out"), "rental")
    approved = next((t.name.casefold() for t in tags if t.purpose is TagPurpose.RENTAL_APPROVAL), "rental approved")
    managed = next((t.name.casefold() for t in tags if t.purpose is TagPurpose.PROPERTY_MANAGER), "property manager")
    labels = [str(u.get("label") or u.get("title") or "") for u in units]
    named, candidates = manager_threads(messages, senders, labels)
    by_unit: dict[tuple, list[Any]] = defaultdict(list)
    for lease in leases:
        by_unit[read_unit_address(lease.unit_address)].append(lease)
    rows = []
    for u in units:
        label = str(u.get("label") or u.get("title") or "")
        uid = int(u["id"])
        owner_rows = [o for o in u.get("owners") or [] if not o.get("deletedAt") and o.get("membershipId") is not None]
        owners = [people.get(int(o["membershipId"]), {}).get("name", "") for o in owner_rows]
        owner_tags = set().union(*(people.get(int(o["membershipId"]), {}).get("tags", set()) for o in owner_rows)) \
            if owner_rows else set()
        unit_tags = tag_names(u)
        found = sorted(by_unit.get(read_unit_address(label), []), key=lambda l: l.start or l.end or "")
        listed = [c.get("name") or "" for c in contacts.get(uid, [])]
        is_rental = rental in unit_tags
        if not (is_rental or found or named.get(label)):
            continue
        row = RentalRow(label, uid, owners, is_rental, approved in unit_tags, managed in owner_tags, tenants_listed=listed)
        deed = (deeds or {}).get(label.upper())
        if found:
            latest = found[-1]
            row.lease = f"{latest.start or '?'} to {latest.end or 'no end given'} ({latest.file})"
            row.lease_runs = latest.current(today)
            row.tenants_on_lease_unlisted = [t for t in latest.tenants
                                             if not any(len(_words(t) & _words(c)) >= 2 for c in listed)
                                             and not any(len(_words(t) & _words(o)) >= 2 for o in owners)]
            company = (latest.manager_company or latest.manager).strip()
            if company:
                row.managers.append(ManagerEvidence(company, [f"lease {latest.start} to {latest.end or '?'}"]))
        for c in listed:
            if re.search(r"propert|management|realty|rentals?", c, re.I):
                ev = next((m for m in row.managers if _words(m.name) & _words(c)), None)
                (ev.how.append("other contact") if ev else row.managers.append(ManagerEvidence(c, ["other contact"])))
        for name, n in (named.get(label) or {}).items():
            ev = next((m for m in row.managers if _words(m.name) & _words(name)), None)
            if ev is None:
                ev = ManagerEvidence(name)
                row.managers.append(ev)
            ev.how.append(f"email: {n} thread{'s' if n != 1 else ''}")
            ev.directory = True
        sold = bool(deed and found and found[-1].start and deed.isoformat() > found[-1].start)
        # what a person might do, in the order 4.15 needs it
        if is_rental and not row.approved:
            row.actions.append("4.15: no approval on file (the board's recognition or the owner's application)")
        if is_rental and not found:
            row.actions.append("ask the owner for the current lease (4.15)")
        elif found and row.lease_runs is False:
            row.actions.append("the lease on file has ended: ask for the current one")
        elif found and row.lease_runs is None:
            row.actions.append("the lease on file ended and may run month to month: confirm with the owner")
        if sold:
            row.actions.append(f"the unit changed hands {deed.isoformat()}, after the lease on file began: confirm the tenancy and manager with the new owner")
        if row.tenants_on_lease_unlisted and row.lease_runs and not sold:
            row.actions.append("add as other contacts: " + ", ".join(row.tenants_on_lease_unlisted))
        if found and row.lease_runs is not False:
            gone = [c for c in listed if not re.search(r"propert|management|realty|rentals?", c, re.I)
                    and not any(len(_words(c) & _words(t)) >= 2 for t in found[-1].tenants)]
            if gone:
                row.actions.append("other contacts not on the latest lease, who may have left (confirm before "
                                   "removing): " + ", ".join(gone))
        if row.managers and not row.property_managed and row.lease_runs and not sold:
            row.actions.append("list the manager as an other contact (on file, no notices); the owner's form says "
                               "whether the manager gets copies or is their contact")
        elif row.managers and not row.property_managed:
            row.actions.append("confirm the manager with the owner; the owner's form says what the manager may receive")
        if not is_rental and found and row.lease_runs and not sold:
            row.actions.append("a lease runs but the unit is not tagged Rental: check the occupancy tag")
        rows.append(row)
    return rows, candidates


def markdown(rows: list[RentalRow], candidates: dict[str, dict[str, int]], *, today: date) -> list[str]:
    out = [f"# Rental register ({today.isoformat()})", "",
           "For the board's CC&Rs 4.15 work. Read from the PayHOA catalog, the leases the Association holds (read on "
           "this machine for the unit, term, landlord, manager, and tenants' names only), the units' other contacts, "
           "and the Gmail headers (no message bodies). Names only: no tenant's or manager's email, phone, or address. "
           "Nothing is written to PayHOA; each action is a person's.", "",
           f"{sum(r.rental for r in rows)} units tagged Rental; {sum(r.approved for r in rows)} with an approval on file; "
           f"{sum(bool(r.lease) for r in rows)} with a lease on file ({sum(r.lease_runs is True for r in rows)} running); "
           f"{sum(bool(r.managers) for r in rows)} with a property manager in evidence.", "",
           "| Unit | Owners | Rental | Approved | Lease on file | Tenants listed | On lease, not listed | Manager (evidence) | Manager record |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r.unit):
        lease = r.lease.split(" (")[0] + {True: " (runs)", False: " (ended)", None: " (ended; month to month?)"}[r.lease_runs] if r.lease else "-"
        mgr = "; ".join(f"{m.name} ({', '.join(m.how)})" for m in r.managers) or "-"
        out.append(f"| {r.unit} | {', '.join(r.owners) or '-'} | {'yes' if r.rental else 'no'} | {'yes' if r.approved else 'no'} | "
                   f"{lease} | {', '.join(r.tenants_listed) or '-'} | {', '.join(r.tenants_on_lease_unlisted) or '-'} | "
                   f"{mgr} | {'yes' if r.property_managed else 'no'} |")
    out += ["", "## Actions", ""]
    for r in sorted(rows, key=lambda r: r.unit):
        for a in r.actions:
            out.append(f"- **{r.unit}**: {a}")
    if candidates:
        out += ["", "## Domains that look like a manager's (sort by hand: a realty selling a unit, a title company, "
                "or another association's manager look the same)", ""]
        for unit, doms in sorted(candidates.items()):
            out.append(f"- {unit}: " + ", ".join(f"{d} ({n} thread{'s' if n != 1 else ''})" for d, n in doms.items()))
    return out


__all__ = ["ManagerEvidence", "RentalRow", "manager_threads", "markdown", "register"]
