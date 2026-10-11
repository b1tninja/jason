"""``jason county-tax``: keep what a person saved from the county tax collector's payment site. It contacts nothing.

- ``--import-receipts FILE --by NAME``: a receipt document (or a list of them) a person saved from the site's payment
  history. Each is trimmed to its confirmation number, posted time, paid items with their amounts in cents, and the bank
  account's last four, and added once to ``data/tax/receipts.json`` (a second import of the same receipt adds nothing).
  The billing party's contact details and the account's name are dropped.
- ``--import-bill FILE --apn APN --year YEAR --by NAME [--bill NUMBER]``: a bill PDF a person downloaded from the site.
  It is copied to the tax bill folder where ``jason sync-tax`` files its own (``{parcel}/{year}-{bill number}.pdf``) and
  recorded on the stored bill's row. When the catalog holds no such bill, ``--bill NUMBER`` files it for the sync to find.
- ``--list`` (the default): the receipts held and which stored bills have a PDF, parcels by their last four characters.

The investigation (``jason.tasks.bill_investigation``) reads the receipts file offline. Reading the site itself needs a
person's sign-in at a terminal and is not built (``jason.tasks.tax_receipts.read_live_receipts``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _refuse(reason: str) -> int:
    print(f"jason county-tax: {reason}", file=sys.stderr)
    return 2


def _tax_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    """The tax catalog and the tax bill folder the profile's settings name."""
    from jason.config import Settings

    settings = Settings.load(getattr(args, "env", None))
    return Path(settings.tax_db), Path(settings.tax_bills_dir)


def _import_receipts(args: argparse.Namespace, root: Path) -> int:
    from jason.tasks import tax_receipts as tr

    try:
        payload = json.loads(Path(args.import_receipts).read_text(encoding="utf-8"))
        receipts, skipped = tr.receipts_from_list(payload)
        if not receipts:
            return _refuse(f"no receipt with a confirmation number in {Path(args.import_receipts).name}"
                           + (f" ({skipped} entries unreadable)" if skipped else ""))
        result = tr.import_receipts(root, receipts, by=args.by)
    except (OSError, ValueError) as exc:
        return _refuse(str(exc))
    print(f"{len(result['added'])} receipts added, {len(result['already'])} already held"
          + (f", {skipped} unreadable" if skipped else "") + f"; the store holds {len(tr.load(root))}.")
    for line in tr.lines(result["added"]):
        print("  " + line)
    return 0


def _import_bill(args: argparse.Namespace, root: Path) -> int:
    from jason.community.tax import TaxBill, bill_pdf_dest, parcel_number
    from jason.community.tax_store import TaxStore
    from jason.tasks import tax_receipts as tr

    if not (args.apn and args.year and args.by):
        return _refuse("--import-bill goes with --apn, --year, and --by")
    source = Path(args.import_bill)
    try:
        data = source.read_bytes()
    except OSError as exc:
        return _refuse(str(exc))
    if not data.startswith(b"%PDF"):
        return _refuse(f"{source.name} is not a PDF")
    tax_db, bills_dir = _tax_paths(args)
    number = (args.bill or "").strip()
    store = TaxStore(tax_db) if tax_db.is_file() else None
    try:
        rows = [r for r in store.bill_rows(args.apn) if r["year"] == args.year] if store else []
        if number:
            held = [r for r in rows if r["number"] == number]
        else:
            held = rows
        if len(held) > 1:
            return _refuse(f"{len(held)} stored bills for {tr.tail(args.apn)} in {args.year}: choose with --bill "
                           f"({', '.join(r['number'] for r in held)})")
        if held:
            number = held[0]["number"]
        elif not number:
            return _refuse(f"no stored bill for the parcel ending {tr.tail(args.apn)} in {args.year}: run "
                           "`jason sync-tax` first, or name the bill with --bill NUMBER")
        dest = bill_pdf_dest(bills_dir, args.apn, TaxBill(number=number, name="", year=args.year))
        sha = hashlib.sha256(data).hexdigest()
        if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() != sha:
            return _refuse(f"{dest.name} is already filed for the parcel ending {tr.tail(args.apn)} with other content; "
                           "it is not replaced")
        if not dest.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        recorded = store.record_pdf(args.apn, number, str(dest), sha) if store and held else False
    finally:
        if store:
            store.close()
    _log_bill(root, {"apn": parcel_number(args.apn), "year": args.year, "bill": number, "sha256": sha,
                     "file": source.name, "recordedOnRow": recorded, "by": args.by.strip(),
                     "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    print(f"Filed {dest.name} for the parcel ending {tr.tail(args.apn)} ({args.year}, bill {number}); "
          + ("recorded on the stored bill." if recorded else
             "the catalog holds no such bill yet, so `jason sync-tax` will find the file when it reads it."))
    return 0


def _log_bill(root: Path, entry: dict[str, Any]) -> None:
    """Append who filed which bill PDF to ``data/tax/bill-imports.jsonl`` (append only)."""
    from jason.locks import Resource, hold

    path = root / "tax" / "bill-imports.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, "tax-bill-imports", timeout=60, purpose="county tax: bill import log"):
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")


def _bills(args: argparse.Namespace) -> list[dict[str, Any]]:
    tax_db, _bills_dir = _tax_paths(args)
    if not tax_db.is_file():
        return []
    conn = sqlite3.connect(f"file:{tax_db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT apn, number, year, total_cents, pdf_path FROM bills ORDER BY apn, year DESC")]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _list(args: argparse.Namespace, root: Path) -> int:
    from jason.tasks import tax_receipts as tr

    rows = tr.load(root)
    bills = _bills(args)
    if args.json:
        print(json.dumps({"receipts": [{**r, "items": [{**i, "apn": tr.tail(i.get("apn"))} for i in r.get("items") or []]}
                                       for r in rows],
                          "bills": [{"parcelEnding": tr.tail(b["apn"]), "number": b["number"], "year": b["year"],
                                     "totalCents": b["total_cents"],
                                     "hasPdf": bool(b["pdf_path"] and Path(b["pdf_path"]).is_file())} for b in bills]},
                         indent=1))
        return 0
    print(f"{len(rows)} receipts held.")
    for line in tr.lines(rows):
        print("  " + line)
    with_pdf = [b for b in bills if b["pdf_path"] and Path(b["pdf_path"]).is_file()]
    print(f"{len(with_pdf)} of {len(bills)} stored bills have a PDF.")
    for b in bills:
        have = "PDF" if b in with_pdf else "no PDF"
        total = f" {tr.money(int(b['total_cents']))}" if b["total_cents"] is not None else ""
        print(f"  parcel ending {tr.tail(b['apn'])}  {b['year'] or 'supplemental'}  bill {b['number']}{total}  {have}")
    return 0


def cmd_county_tax(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir

    root = data_dir(args)
    if args.import_receipts and args.import_bill:
        return _refuse("one import at a time")
    if args.import_receipts:
        if not args.by:
            return _refuse("--import-receipts goes with --by NAME")
        return _import_receipts(args, root)
    if args.import_bill:
        return _import_bill(args, root)
    return _list(args, root)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("county-tax", help="Keep a county payment receipt or bill PDF a person saved from the tax "
                                          "collector's site (read only; contacts nothing)")
    add_common(p)
    p.add_argument("--list", action="store_true", help="list the receipts held and which stored bills have a PDF (the default)")
    p.add_argument("--json", action="store_true", help="with --list: print JSON")
    p.add_argument("--import-receipts", dest="import_receipts", metavar="FILE",
                   help="a saved receipt document, or a list of them (with --by)")
    p.add_argument("--import-bill", dest="import_bill", metavar="FILE",
                   help="a bill PDF a person downloaded (with --apn, --year, and --by)")
    p.add_argument("--apn", metavar="APN", help="with --import-bill: the parcel number")
    p.add_argument("--year", type=int, metavar="YEAR", help="with --import-bill: the bill's tax year")
    p.add_argument("--bill", metavar="NUMBER", help="with --import-bill: the bill number, when the parcel has several that year")
    p.add_argument("--by", default="", metavar="NAME", help="who imports this (kept with when)")
    p.set_defaults(func=cmd_county_tax)


__all__ = ["cmd_county_tax", "register"]
