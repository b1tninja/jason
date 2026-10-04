"""``jason key-documents``: the key documents checklist (the declaration, each amendment and annexation, the plans,
maps, common-area deeds, and the rest), each with its recording number, copies, and status, and a person's links.

``jason key-documents`` prints the checklist; ``--json`` the rows the console shows; ``--markdown`` a page.
``--link KEY --file PATH`` (under data/), ``--drive ID`` or ``--payhoa ID`` links a copy; ``--upload KEY --file PATH``
copies a file from anywhere into ``data/key-documents/<profile>/files/`` and links it; ``--unlink KEY`` removes a link
(``--link-id`` when it has several; the file stays); ``--status KEY --set missing --note "..."`` records a person's
word. Every write names its person with ``--by``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable


def cmd_key_documents(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.commands._shared import data_dir, to_json
    from jason.tasks import key_documents as kd

    root = data_dir(args)
    writing = args.link or args.upload or args.unlink or args.status
    if writing and not (args.by or "").strip():
        print("a write names its person: add --by NAME", file=sys.stderr)
        return 2
    try:
        if args.link:
            if not (args.file or args.drive or args.payhoa):
                print("--link KEY needs --file PATH (under data/), --drive ID, or --payhoa ID", file=sys.stderr)
                return 2
            out = kd.link(args.link, by=args.by, file=args.file or "", drive=args.drive or "", payhoa=args.payhoa or "",
                          note=args.note or "", title=args.title or "", root=root)
            print(f"linked {out['name']} to {args.link} ({out['kind']}, {out['id']}) as {out['by']}")
            return 0
        if args.upload:
            if not args.file:
                print("--upload KEY needs --file PATH (the file to copy into data/key-documents)", file=sys.stderr)
                return 2
            out = kd.upload(args.upload, by=args.by, path=args.file, note=args.note or "", title=args.title or "", root=root)
            print(f"uploaded {out['name']} to {out['ref']} (sha256 {out['sha256'][:12]}) and linked it to {args.upload} as {out['by']}")
            return 0
        if args.unlink:
            link_id = args.link_id or ""
            if not link_id:
                held = [l for l in kd.KeyDocumentStore(root, kd._profile(None)).entry(args.unlink).get("links", []) if not l.get("unlinked")]
                if len(held) != 1:
                    print(f"{args.unlink} has {len(held)} links; name one with --link-id ("
                          + ", ".join(f"{l['id']} {l['name']}" for l in held) + ")", file=sys.stderr)
                    return 2
                link_id = held[0]["id"]
            out = kd.unlink(args.unlink, link_id, by=args.by, note=args.note or "", root=root)
            print(f"unlinked {out['name']} from {args.unlink} as {args.by}; the file stays where it is")
            return 0
        if args.status:
            if not args.set:
                print("--status KEY needs --set expected|located|held|missing", file=sys.stderr)
                return 2
            out = kd.set_status(args.status, args.set, by=args.by, note=args.note or "", root=root)
            print(f"{args.status}: {out['value']}, recorded by {out['by']}")
            return 0
    except KeyError as exc:
        print(f"no {exc.args[0] if exc.args else 'such entry'}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    data = kd.checklist(root=root)
    if args.json:
        print(to_json(data))
        return 0
    if args.markdown:
        print(kd.markdown(data))
        return 0
    print(f"Key documents: {data['association']} ({data['county']} County); "
          + ", ".join(f"{k} {v}" for k, v in sorted(data["counts"].items())))
    for group in data["groups"]:
        print(f"\n{group['title']}")
        if not group["entries"]:
            print("  none on record yet")
        for e in group["entries"]:
            number = f" {e['number']}" if e["number"] else ""
            day = f" {e['recorded']}" if e["recorded"] else ""
            gone = f" superseded by {e['supersededBy']}" if e["supersededBy"] else ""
            print(f"  {e['status']:8} {e['key']}{number}{day}{gone}  {e['title']}")
            for c in e["links"]:
                print(f"           linked {c['kind']} {c['name']} ({c['id']}, by {c['by']})")
            if not e["links"]:
                for c in e["copies"][:3]:
                    print(f"           {c['source']}: {c['name']}")
            for lead in e["leads"][:2]:
                print(f"           lead: {lead.get('number', '')} {lead.get('filing', '')} ({lead.get('tie', '')})")
    for note in data["notes"]:
        print(f"note: {note}")
    for caveat in data["caveats"]:
        print(f"> {caveat}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("key-documents", help="The key documents checklist (declaration, amendments, annexations, plans, maps, deeds) with links to each copy")
    add_common(p)
    p.add_argument("--json", action="store_true", help="print the checklist as JSON")
    p.add_argument("--markdown", action="store_true", help="print the checklist as a Markdown page")
    p.add_argument("--link", metavar="KEY", help="link a copy to this entry (with --file under data/, --drive, or --payhoa)")
    p.add_argument("--upload", metavar="KEY", help="copy --file into data/key-documents and link it to this entry")
    p.add_argument("--unlink", metavar="KEY", help="remove a link from this entry (the file stays); --link-id when it has several")
    p.add_argument("--status", metavar="KEY", help="record a person's status for this entry (with --set)")
    p.add_argument("--file", metavar="PATH", help="the file: under data/ for --link, anywhere for --upload")
    p.add_argument("--drive", metavar="ID", help="a Drive file id or link, for --link")
    p.add_argument("--payhoa", metavar="ID", help="a PayHOA library document id, for --link")
    p.add_argument("--link-id", metavar="ID", help="which link --unlink removes")
    p.add_argument("--set", metavar="STATUS", help="with --status: expected, located, held, or missing")
    p.add_argument("--note", help="a few words kept with the write (required for missing: what was looked for, where)")
    p.add_argument("--title", help="a title for an other/<name> entry, kept with its first link")
    p.add_argument("--by", metavar="NAME", help="the person making the write (required for every write)")
    p.set_defaults(func=lambda args: cmd_key_documents(args, agent_factory))
