"""``jason rentals``: the units rented now against the CC&Rs' cap, and which have the board's approval on file.

Reads the stored PayHOA catalog: the occupancy tag ("Rental": rented now) beside the approval tag ("Rental Approved":
the board approved a CC&Rs 4.15 application or recognized an existing rental), and the declaration's cap
(``mystique/leasing.py``; never below the 25 percent of Civil Code 4741(b)). ``--list`` prints each unit's standing.
It changes nothing; approving a rental, asking for an application, or recognizing existing rentals is the board's.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def cmd_rentals(args: argparse.Namespace) -> int:
    from jason.community import community as active
    from jason.community.leasing import standing
    from jason.config import Settings
    from jason.tasks.broadcast import catalog_rows

    community = active()
    db = Settings.load(args.env).payhoa_catalog
    units, people_rows, synced = catalog_rows(db)
    found = standing(units, community.payhoa_tags(), community.leasing_rules())
    report = found.summary()
    report["catalogSynced"] = synced
    print(json.dumps(report, indent=1))
    if args.list:
        for u in found.units:
            if u.standing != "owner-occupied or vacant":
                print(f"  {u.unit:24} {u.standing}")
    if args.register:
        return _register(db, units, people_rows, community)
    return 0


def _register(db: Any, units: list[dict[str, Any]], people_rows: list[dict[str, Any]], community: Any) -> int:
    """The rental register (``tasks/rental_register``) to data/board/rental-register-<date>.md."""
    import sqlite3
    from datetime import date
    from pathlib import Path

    from jason.catalog import person_name
    from jason.community.tags import tag_names
    from jason.tasks.leases import Lease
    from jason.tasks.parties import PartyResolver
    from jason.tasks.rental_register import markdown, register

    data = Path(db).parent
    people = {int(p["id"]): {"name": person_name(p), "tags": tag_names(p)} for p in people_rows if p.get("id") is not None}
    con = sqlite3.connect(db)
    contacts: dict[int, list[dict[str, Any]]] = {}
    try:
        for unit_id, name in con.execute("select unit_id, name from unit_contacts"):
            contacts.setdefault(unit_id, []).append({"name": name})
    except sqlite3.OperationalError:
        print("no other contacts in the catalog: run jason sync-catalog --only contacts", file=sys.stderr)
    con.close()
    lease_file = data / "leases" / "leases.json"
    leases = [Lease(**d) for d in json.loads(lease_file.read_text(encoding="utf-8"))] if lease_file.is_file() else []
    mail = data / "gmail" / "correspondence.json"
    messages = json.loads(mail.read_text(encoding="utf-8")).get("messages", []) if mail.is_file() else []
    today = date.today()
    rows, candidates = register(units, people, contacts, leases, community.payhoa_tags(), messages, community.senders(),
                                today, deeds=PartyResolver(data).latest_deed)
    out = data / "board" / f"rental-register-{today.isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(markdown(rows, candidates, today=today)) + "\n", encoding="utf-8")
    print(f"{len(rows)} units; {sum(len(r.actions) for r in rows)} actions: {out}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("rentals", help="Rented units against the CC&Rs' cap, and which have the board's approval (4.15)")
    add_common(p)
    p.add_argument("--list", action="store_true", help="each rented or approved unit's standing")
    p.add_argument("--register", action="store_true",
                   help="the rental register: leases, tenants, other contacts, property managers, and actions")
    p.set_defaults(func=cmd_rentals)
