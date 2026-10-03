"""``jason cite``: cite and recite the association's documents and records, and follow their references.

The citation closure is ``jason.tasks.cite`` (modeled on lawlibrary's ``Citation``). An expression is what a person
or a document writes: "Declaration § 6.2(a)", "Section 6.2(a) of the Declaration", "Bylaws Art. 6", "Owner's Manual
R-3(e)", "Resolution 20990101-1", "Doc. No. 209901010001", "minutes 2099-01-01", "CIV 4920(a)", a canonical target
(``decl#6.2(a)``), ``@YYYY-MM-DD`` for the words in force on a day, and a record address (``jason://decl/6.2(a)``,
``jason://decl@2099-01-01/6.2(a)``, ``jason://decl/history/6.2(a)``, ``jason://res/20990101-1``; docs/record-addresses.md).

- ``jason cite EXPRESSION`` recites the words whole, with the citation and the version in force; an outline for a
  document, an article, a span, or siblings; a miss with its reason.
- ``--refs [--hops N|all] [--same] [--only KINDS]`` follows what it cites; ``--cited-by`` lists what names it (the
  governing documents and jason's own records), each with how the cited words stand now.
- ``--md`` prints a page, ``--chart`` the Mermaid flowchart, ``--json`` the full answer.
- ``--survey`` resolves every reference the governing documents make; ``--stale`` lists citing records whose cited
  words are gone or changed; ``--renumbered`` those a permanent id found under another number; ``--most-cited`` ranks
  the sections and statutes named most.
- ``--books`` lists the association's books (the statute's keys) and the profile's documents in each.
- ``--private`` opens a restricted book (executive-session minutes, the membership list, election materials: CIV 5215).
- ``--html [DIR]`` writes the record reader (``jason.tasks.reader``): static pages for each book, section, history,
  and version, linked by address, into ``data/reader`` (private); restricted books only with ``--private``.
- ``--migrate-ids`` adds each citing record's permanent id and the version it cites (a dry run; ``--apply`` writes,
  backing each file up first): jason.tasks.permanent_ids.

Reading only, except ``--migrate-ids --apply`` (data/ files, backed up), ``--html`` (its own output folder), and the id
tables it caches in data/section-refs: nothing here reaches Drive, PayHOA, or the mail.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def _hops(value: str | None) -> int | None:
    if value is None:
        return 1
    if str(value).lower() in ("all", "none"):
        return None
    return int(value)


def cmd_cite(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.cite import tree_lines
    from jason.tasks.cite import Shelf, markdown

    shelf = Shelf(community(), _data_dir(args), private=args.private)
    if args.html is not None:
        from jason.tasks.reader import write

        out = Path(args.html) if args.html else _data_dir(args) / "reader"
        report = write(shelf, out, private=args.private)
        if args.json:
            print(json.dumps({"out": str(report.out), "pages": report.pages, "byKind": report.by_kind,
                              "missing": report.missing, "restricted": report.restricted, "unread": report.unread,
                              "capped": report.capped}, indent=1))
            return 0
        kinds = ", ".join(f"{k} {n}" for k, n in sorted(report.by_kind.items()))
        print(f"{report.pages} pages in {report.out} ({kinds})")
        print(f"{len(report.missing)} linked addresses have no page (each link to one is marked with why)")
        for reason, n in Counter(v.split(":", 1)[0] for v in report.missing.values()).most_common():
            print(f"  {reason}: {n}")
        if report.restricted:
            print("not written (restricted; --private writes them): " + ", ".join(report.restricted))
        if report.capped:
            print("stopped at the page cap: some links are marked not written")
        if report.unread:
            print("not read: " + "; ".join(report.unread[:10]))
        print(f"open {report.out / 'index.html'}, or serve it: python -m http.server -d {report.out} 8765")
        return 0
    if args.books:
        table = shelf.books.table()
        if args.json:
            print(json.dumps(table, indent=1))
            return 0
        for b in table:
            docs = ", ".join(f"{d['document']}" + (f" ({d['key']})" if d["key"] != b["key"] else "")
                             + (f" [{d['role']}]" if d["role"] != "text" else "") for d in b["documents"])
            flag = f" restricted: {b['restricted']}" if b["restricted"] else ""
            print(f"{b['key']:9} {b['statute'] or '(not in the Act)':16} {b['shape']:7} {b['title']}{flag}"
                  + (f"\n{'':9} {docs}" if docs else ""))
        return 0
    if args.migrate_ids:
        from jason.tasks.permanent_ids import migrate

        found = migrate(shelf, apply=args.apply)
        if args.json:
            print(json.dumps(found, indent=1))
            return 0
        for kind, row in found["kinds"].items():
            print(f"{kind}: {row['placed']} placed, {row['unplaced']} not")
        print(f"register rows (the specification's records): {found['register']}")
        for row in found["unplaced"][:40]:
            print(f"  not placed: {row['record']} names {row['document']} {row['written']}")
        for row in found["ambiguous"][:40]:
            print(f"  more than one section answers: {row['record']} names {row['document']} {row['written']} "
                  f"({', '.join(row['candidates'])}; nothing stored: a person picks)")
        if args.apply:
            print("written: " + (", ".join(found["written"]) or "nothing"))
            print("backups: " + (", ".join(b for b in found["backups"] if b) or "none"))
        else:
            print("a dry run: --apply writes the fields, backing each file up first")
        return 0
    if args.renumbered:
        rows = shelf.relocated()
        if args.json:
            print(json.dumps([r.as_dict() for r in rows], indent=1))
            return 0
        print(f"{len(rows)} citing records found again by their permanent id")
        for r in rows:
            print(f"  {r.holder.value} {r.key}: {r.target}: {r.note}")
        return 0
    if args.survey:
        found = shelf.survey()
        if args.json:
            print(json.dumps(found, indent=1))
            return 0
        print(f"{found['references']} references in the governing documents: {found['found']} resolve, "
              f"{found['missed']} miss, {found['unfollowable']} name nothing jason can follow")
        for unit, counts in sorted(found["byUnit"].items()):
            print(f"  {unit}: {counts.get('found', 0)} found, {counts.get('missed', 0)} missed")
        for reason, n in found["reasons"].items():
            print(f"  {reason}: {n} (e.g. {', '.join(found['examples'].get(reason, [])[:3])})")
        return 0
    if args.stale:
        rows = shelf.stale()
        if args.json:
            print(json.dumps([r.as_dict() for r in rows], indent=1))
            return 0
        print(f"{len(rows)} citing records whose cited words are gone or changed; {len(shelf.relocated())} more were "
              "found again by their permanent id (--renumbered lists them)")
        for r in rows:
            print(f"  {r.holder.value} {r.key}: {r.target} {r.treatment.value}" + (f" ({r.note})" if r.note else ""))
        return 1 if rows else 0
    if args.most_cited is not None:
        rows = shelf.most_cited(args.most_cited)
        if args.json:
            print(json.dumps(rows, indent=1))
            return 0
        for r in rows:
            by = ", ".join(f"{k} {v}" for k, v in sorted(r["by"].items(), key=lambda kv: -kv[1]))
            print(f"{r['total']:5}  {r['citation']}{'' if r['found'] else ' [missing]'}  ({by})")
        return 0
    if not args.expression:
        print("cite: name a section, a record, or a statute (jason cite \"Declaration 6.2(a)\"), or pass --survey, "
              "--stale, or --most-cited", file=sys.stderr)
        return 2
    c = shelf(args.expression)
    if args.as_of:
        c = c.as_of(args.as_of)
    try:
        c = c.hops(_hops(args.hops))
    except ValueError:
        print(f"cite: --hops is a number or all, not {args.hops!r}", file=sys.stderr)
        return 2
    if args.same:
        c = c.same()
    if args.only:
        try:
            c = c.only(*[k.strip() for k in args.only.split(",") if k.strip()])
        except ValueError as exc:
            print(f"cite: {exc}", file=sys.stderr)
            return 2
    if args.chart:
        print(c.chart)
        return 0 if c.found else 1
    if args.md:
        print(markdown(c))
        return 0 if c.found else 1
    if args.json:
        print(json.dumps(c.as_dict(text=not args.no_text, refs=args.refs, cited_by=args.cited_by), indent=1,
                         default=str))
        return 0 if c.found else 1
    _print(c, args, tree_lines)
    return 0 if c.found else 1


def _print(c: Any, args: argparse.Namespace, tree_lines: Callable[..., list[str]]) -> None:
    st = c.state
    print(str(c))
    if not st.found:
        print(f"  not found: {st.reason.value if st.reason else 'unknown'}" + (f": {st.detail}" if st.detail else ""))
    if st.text and not args.no_text:
        print()
        for line in st.text.strip().splitlines():
            print(f"  {line}")
        print()
    if st.text and c.in_force:
        print(f"  {c.in_force}")
    if st.version.get("note"):
        print(f"  note: {st.version['note']}")
    if c.address:
        pid = c.pid if st.found else ""
        print(f"  address: {c.address}" + (f"; permanent id {pid}" if pid else ""))
    for row in c.terms:
        print(f"  defined term: \"{row['term']}\", {row['citation']} ({row['address']})")
    for row in st.extra.get("readings") or ():
        print(f"  {row['says']}")
    diff = st.extra.get("differences")
    if diff:
        print(f"  only in the documents' own term: {', '.join(diff['onlyInTheDocuments']) or 'none'}; only in the "
              f"statute's list: {', '.join(diff['onlyInTheStatute']) or 'none'}"
              + (f"; also named: {'; '.join(diff['alsoNamed'])}" if diff["alsoNamed"] else ""))
        for n in diff["notes"]:
            print(f"  {n}")
    for node in st.nodes[:60]:
        if "book" in node:                     # the governing documents: a set of books
            docs = ", ".join(node["documents"]) or node.get("series") or "none mapped"
            print(f"  - {node['set']}: {node['book']} ({node['title']}): {docs}")
            continue
        if "version" in node:                  # a section's history
            print(f"  - {node['version']} {node['number'] or '(not yet)'}: {node['through']}"
                  + (" (words changed)" if node.get("changed") else "")
                  + ("" if node.get("inForce", True) else " (not in force)"))
            continue
        label = node.get("number") or node.get("first", "")
        caption = node.get("caption") or node.get("title") or node.get("kind") or node.get("where") or ""
        flag = "" if node.get("found", True) else f" [missing: {node.get('reason', '')}]"
        print(f"  - {label} {caption}{flag}".rstrip())
    if len(st.nodes) > 60:
        print(f"  ... and {len(st.nodes) - 60} more (--json lists them)")
    for h in c.history:
        print(f"  history: {h['section']}: {h.get('describe') or h.get('correction')}"
              + ("" if h.get("applied") else " (not in force; not applied)"))
    if args.refs:
        root = c.refs
        edges = root.edges()
        print()
        print(f"What it cites ({c.depth if c.depth is not None else 'all'} hops): {len(root.nodes()) - 1} targets, "
              f"{len(edges)} edges, {sum(1 for e in edges if not e['found'])} missing")
        for line in tree_lines(root):
            print(f"  {line}")
    if args.cited_by:
        rows = c.cited_by
        print()
        counts = Counter((r.holder.value, r.scope.value) for r in rows)
        print(f"What cites it: {len(rows)} ("
              + ", ".join(f"{h} {s} {n}" for (h, s), n in sorted(counts.items())) + ")")
        grouped: dict[tuple[str, ...], list[Any]] = {}
        for r in rows:
            grouped.setdefault((r.holder.value, r.key, r.target, r.scope.value, r.treatment.value), []).append(r)
        for (holder, key, target, scope, treatment), same in list(grouped.items())[:80]:
            times = f" x{len(same)}" if len(same) > 1 else ""
            print(f"  {holder} {key} names {target}{times} ({scope}; {treatment})")
            for reading in dict.fromkeys(r.reading for r in same if r.reading):
                print(f"    jason's reading (not the words): {reading}")
        if len(grouped) > 80:
            print(f"  ... and {len(grouped) - 80} more (--json lists them)")
        if c.shelf.unread:
            print("  not read: " + "; ".join(c.shelf.unread))
    if st.found and st.text:
        from jason.community.cite import CAVEAT

        print()
        print(CAVEAT)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("cite", help="Cite and recite the association's documents and records (Declaration 6.2(a), "
                                    "Resolution N, Doc. No. N, minutes, CIV 4920(a)); follow references both ways")
    add_common(p)
    p.add_argument("expression", nargs="?", help="what to cite: \"Declaration 6.2(a)\", \"Section 6.2(a) of the "
                                                 "Declaration\", \"Resolution 20990101-1\", decl#6.2(a)@2099-01-01")
    p.add_argument("--as-of", help="the words in force on this date (YYYY-MM-DD)")
    p.add_argument("--refs", action="store_true", help="follow what it cites")
    p.add_argument("--hops", help="with --refs: how many hops (default 1); all follows until a target repeats")
    p.add_argument("--same", action="store_true", help="with --refs: stay inside this document")
    p.add_argument("--only", help="with --refs: follow only these kinds (statute,section,document,resolution,"
                                  "instrument)")
    p.add_argument("--cited-by", action="store_true", help="what names it: the governing documents and jason's own "
                                                           "records, with how the cited words stand now")
    p.add_argument("--no-text", action="store_true", help="leave the words out")
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument("--md", action="store_true", help="print a Markdown page")
    fmt.add_argument("--chart", action="store_true", help="print the reference walk as a Mermaid flowchart")
    fmt.add_argument("--json", action="store_true", help="print the full answer as JSON")
    p.add_argument("--survey", action="store_true", help="resolve every reference the governing documents make")
    p.add_argument("--stale", action="store_true", help="citing records whose cited words are gone or changed "
                                                        "(exit 1 when any)")
    p.add_argument("--most-cited", type=int, nargs="?", const=30, metavar="N",
                   help="the sections and statutes named most (default 30)")
    p.add_argument("--renumbered", action="store_true", help="citing records a permanent id found under another "
                                                             "number (renumbered, printed twice, or run inline)")
    p.add_argument("--books", action="store_true", help="the association's books (decl, bylaws, rules, res, min, ...), "
                                                        "each with its statute and the profile's documents")
    p.add_argument("--private", action="store_true", help="open a restricted book (executive-session minutes, the "
                                                          "membership list, election materials: CIV 5215)")
    p.add_argument("--html", nargs="?", const="", metavar="DIR",
                   help="write the record reader: static pages for each book, section, history, and version, linked "
                        "by address (default data/reader; restricted books only with --private)")
    p.add_argument("--migrate-ids", action="store_true", help="add each citing record's permanent id and the version "
                                                              "it cites (a dry run unless --apply)")
    p.add_argument("--apply", action="store_true", help="with --migrate-ids: write the fields (each file backed up "
                                                        "first)")
    p.set_defaults(func=cmd_cite)


__all__ = ["cmd_cite", "register"]
