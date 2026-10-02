"""``jason leases``: the leases the Association holds, read on this machine for who lives in a rented unit and whether
its owner works with a property manager (``jason.tasks.leases``).

``--fetch`` copies the leases from Drive (the lease folders; never an application or screening report) to
``data/leases``; ``--read`` reads each with the local model; then the proposals: tenants to list as the unit's other
contacts, other contacts who may have left, managers to list, and owners to ask what their manager may receive. Units, owners, and
other contacts come from the catalog (``jason sync-catalog``). Nothing is written to PayHOA.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(args.env).payhoa_catalog.parent


def cmd_leases(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.tasks import leases as ls

    data = _data_dir(args)
    folder = data / "leases"
    found_path = folder / "leases.json"
    if args.fetch:
        catalog = json.loads((data / "drive" / "files.json").read_text(encoding="utf-8"))
        files = ls.lease_files(catalog if isinstance(catalog, list) else catalog.get("files", []))
        folder.mkdir(parents=True, exist_ok=True)
        with agent_factory(args) as agent:
            drive = agent.drive()
            for f in files:
                name = f"{f['id'][:8]} {f['name']}"
                dest = folder / (name if Path(name).suffix else name + ".pdf")
                if not dest.exists():
                    drive.download(f["id"], dest)
                print(f"  {dest.name.encode('ascii', 'replace').decode()}")
        print(f"{len(files)} leases in {folder}")
    if args.read:
        from jason.local_ai import LocalAIUnavailable, preflight, unload

        try:
            preflight(args.model)
        except LocalAIUnavailable as exc:
            print(exc, file=sys.stderr)
            return 2
        paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".pdf", ".png", ".jpg", ".jpeg")
                       and not ls.SKIP.search(p.name)) if folder.is_dir() else []
        library = data / "library" / "files" / "Lease Agreements"
        paths += sorted(library.glob("*.pdf")) if library.is_dir() else []
        read = []
        try:
            for p in paths:
                lease = ls.read(p, model=args.model, source="library" if library in p.parents else "drive")
                read.append(lease)
                print(f"  {p.name[:50].encode('ascii', 'replace').decode():50} {lease.unit_address[:28]:28} "
                      f"{lease.start or '?':10} to {lease.end or 'm-t-m':10} {'manager' if lease.manager or lease.manager_company else ''}"
                      f"{lease.error}", flush=True)
        finally:
            unload(args.model)
        ls.save(read, found_path)
        print(f"{len(read)} leases read: {found_path}")
    if not found_path.is_file():
        print("no leases read yet: --fetch --read", file=sys.stderr)
        return 1
    leases = [ls.Lease(**d) for d in json.loads(found_path.read_text(encoding="utf-8"))]
    import sqlite3

    con = sqlite3.connect(data / "payhoa.db")
    con.row_factory = sqlite3.Row
    units = [{**json.loads(r["raw_json"]), "id": r["id"], "label": r["label"]} for r in con.execute("select id, label, raw_json from units")]
    people = {r["id"]: r["name"] for r in con.execute("select id, name from people")}
    contacts: dict[int, list[dict[str, Any]]] = {}
    for r in con.execute("select unit_id, name, email from unit_contacts"):
        contacts.setdefault(r["unit_id"], []).append(dict(r))
    con.close()
    owners = {int(u["id"]): [people.get(int(o["membershipId"]), "") for o in u.get("owners") or []
                             if not o.get("deletedAt") and o.get("membershipId") is not None] for u in units}
    from jason.tasks.parties import PartyResolver

    out = ls.proposals(leases, units, contacts, owners, date.today(), deeds=PartyResolver(data).latest_deed)
    for p in out:
        print(f"{p.unit:24} {p.kind:28} {p.who[:34]:34} {p.why}".encode("ascii", "replace").decode())
    print(f"{len(out)} proposal(s); nothing written. Unread: {[l.file for l in leases if l.error]}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("leases", help="Read the leases the Association holds: tenants and property managers")
    add_common(p)
    p.add_argument("--fetch", action="store_true", help="copy the leases from Drive to data/leases")
    p.add_argument("--read", action="store_true", help="read each with the local model")
    p.add_argument("--model", default="qwen3.5:9b", help="the local model (default qwen3.5:9b)")
    p.set_defaults(func=lambda args: cmd_leases(args, agent_factory))
