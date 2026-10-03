"""``jason section-refs``: embedded references to governing-document sections, and the copies they replace.

A document jason renders for members or the board (an owner guide or notice in Markdown, a base template) can carry
``{QUOTE:ccrs#4.2(b)}`` (the section's current words, its citation, and who set them), ``{QUOTE:ccrs#4.2(b)
as-of=2025-01-01}`` (the words in force on a date), or ``{CITE:ccrs#4.2(b)}`` (the citation) in place of a copied
passage, filled from the document kept as amended each time it is rendered. Reference material agents read (docs,
notes) keeps its quoted words and never carries a token.

- ``jason section-refs`` lists the documents a reference can name.
- ``--show ccrs#4.2(b) [--as-of DATE]`` prints the section as a quote renders it, with its record.
- ``--render FILE [--out OUT]`` fills a file's references (Markdown or HTML) and writes OUT and ``OUT.refs.json``,
  the record of each one; ``--check FILE...`` only resolves them, and fails on any that cannot be filled.
- ``--scan`` finds the copies of each living document's sections (current, superseded, and draft words) in the
  outlines, the library, jason's sources, and the reference material, and writes ``data/section-refs/copies.md``.
- ``--patch`` shows, for jason's own sources, the token that would replace each whole-section copy; ``--apply PATH
  --yes`` writes one (the old text kept as ``.bak``). A sent notice is history: apply only to a base or a draft.
- ``--guide [KEY...]`` compiles ``data/section-refs/guide/``, the index of each document's sections agents read.

Read-only toward Drive, PayHOA, and the mail: nothing here reaches them.
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

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_section_refs(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.community.section_refs import SectionRefError
    from jason.tasks import section_refs as sr

    c = community()
    data_dir = _data_dir(args)
    try:
        if args.refresh:
            for living in c.living_documents():
                sr.build_versions(living, data_dir, refresh=True, log=print)
        if args.show:
            return _show(args, sr, data_dir, c)
        if args.render or args.check:
            return _render(args, sr, data_dir, c)
        if args.scan:
            found = sr.scan(data_dir, c, args.document or (), library=not args.no_library,
                            confidential=args.confidential, log=print)
            path = sr.save(found, data_dir)
            copies = found.copies()
            stale = [(h, x) for h, x in copies if x.currency.value == "stale" and h.owner is not sr.Owner.SELF]
            print(f"{len(found.results)} documents carry copies ({sum(1 for r in found.results if r.whole)} whole copies); "
                  f"{len(copies)} copies elsewhere, {len(stale)} stale")
            for h, x in stale:
                print(f"  stale: {h.name} ({h.owner.value}): {x.target} reads as {x.matched}")
            print(f"wrote {path} and {path.with_suffix('.json')}")
            return 0
        if args.patch or args.apply:
            return _patch(args, sr, data_dir, c)
        if args.guide is not None:
            saved = sr.load_saved(data_dir)
            if saved is None:
                print("no copies scan yet: the guide lists no copies (run jason section-refs --scan first)")
            paths = sr.guide(data_dir, c, args.guide, saved=saved, log=print)
            print(f"wrote {len(paths) - 1} guides and the index {paths[0]}")
            return 0
    except SectionRefError as exc:
        print(f"section-refs: {exc}", file=sys.stderr)
        return 1
    resolver = sr.DiskResolver(data_dir, c)
    print("A reference names a document by its key and a section as the document numbers it:")
    print("  {QUOTE:KEY#N}  {QUOTE:KEY#N as-of=YYYY-MM-DD}  {CITE:KEY#N}")
    living = {d.key for d in c.living_documents()}
    for key in resolver.keys():
        try:
            name = resolver.name(key)
        except SectionRefError:
            name = key
        how = "kept as amended (as-of works)" if key in living else (
            "its outline" if resolver.outline(key) is not None else "no outline on disk: not quotable yet")
        print(f"  {key}: cited as {name}; {how}")
    return 0


def _show(args: argparse.Namespace, sr: Any, data_dir: Path, c: Any) -> int:
    from jason.community.section_refs import Ref, Verb, expand_markdown

    key, _, number = args.show.partition("#")
    if not number:
        print("give the section as KEY#N (ccrs#4.2(b))", file=sys.stderr)
        return 2
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    token = Ref(Verb.QUOTE, key, number, as_of).text()
    text, records = expand_markdown(token + "\n", sr.DiskResolver(data_dir, c, log=print))
    print(text)
    for line in sr.record_lines(records):
        print(f"record: {line}")
    return 0


def _render(args: argparse.Namespace, sr: Any, data_dir: Path, c: Any) -> int:
    from jason.community.section_refs import SectionRefError, expand_html, expand_markdown

    resolver = sr.DiskResolver(data_dir, c, log=print)
    files = [Path(args.render)] if args.render else [Path(f) for f in args.check]
    failed = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        expand = expand_html if path.suffix.lower() in (".html", ".htm") else expand_markdown
        try:
            out, records = expand(text, resolver)
        except SectionRefError as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            failed += 1
            continue
        print(f"{path}: {len(records)} references")
        for line in sr.record_lines(records):
            print(f"  {line}")
        if args.render:
            dest = Path(args.out) if args.out else path.with_name(f"{path.stem}.rendered{path.suffix}")
            dest.write_text(out, encoding="utf-8")
            sidecar = dest.with_name(dest.name + ".refs.json")
            sidecar.write_text(json.dumps({"source": str(path), "rendered": date.today().isoformat(),
                                           "references": [r.as_dict() for r in records]}, indent=1), encoding="utf-8")
            print(f"wrote {dest} and {sidecar}")
    return 1 if failed else 0


def _patch(args: argparse.Namespace, sr: Any, data_dir: Path, c: Any) -> int:
    keys = args.document or [d.key for d in c.living_documents()]
    own = [h for h in sr.hosts(data_dir, c, keys, library=False) if h.owner in sr.TOKENIZABLE]
    found = sr.scan(data_dir, c, keys, host_list=own, log=print)
    proposals = sr.proposals(found)
    if args.apply:
        wanted = Path(args.apply).resolve()
        chosen = [p for p in proposals if Path(p.path).resolve() == wanted]
        if not chosen:
            print(f"no proposal for {args.apply}: jason section-refs --patch lists them", file=sys.stderr)
            return 2
        print(chosen[0].diff())
        if not args.yes:
            print("not written: add --yes to write it (a sent notice is history; apply only to a base or a draft)")
            return 0
        print(f"wrote {sr.apply(chosen[0])} (the old text kept beside it as .bak)")
        return 0
    if not proposals:
        print("no whole-section copies in jason's own sources")
    for p in proposals:
        print(f"{p.path}: {p.token}")
        print(p.diff())
    excerpts = [(r.host, x) for r in found.results for x in r.copies if x.kind.value in ("excerpt", "paraphrase")]
    for h, x in excerpts:
        print(f"{h.name}: {x.target} {x.kind.value} (no token: a quote of the whole section would say more; "
              f"consider {{CITE:{x.target}}} beside the words)")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("section-refs", help="Embedded references ({QUOTE:ccrs#4.2(b)}, {CITE:...}) in place of copied "
                                            "governing-document passages; find the copies; compile the guide")
    add_common(p)
    p.add_argument("--show", metavar="KEY#N", help="print a section as a quote renders it (ccrs#4.2(b))")
    p.add_argument("--as-of", help="with --show: the words in force on this date (YYYY-MM-DD)")
    p.add_argument("--render", metavar="FILE", help="fill a Markdown or HTML file's references; writes --out and its "
                                                    ".refs.json record")
    p.add_argument("--out", help="with --render: where to write (default FILE.rendered.EXT beside it)")
    p.add_argument("--check", nargs="+", metavar="FILE", help="resolve the references in files; fail on any that "
                                                              "cannot be filled")
    p.add_argument("--scan", action="store_true", help="find copies of the sections in other documents (read-only)")
    p.add_argument("--document", nargs="+", metavar="KEY", help="with --scan or --patch: the documents to look for "
                                                                "(default: those kept as amended)")
    p.add_argument("--no-library", action="store_true", help="with --scan: leave the library's extracts out")
    p.add_argument("--confidential", action="store_true", help="with --scan: include confidential library files")
    p.add_argument("--patch", action="store_true", help="show the tokens that would replace whole-section copies in "
                                                        "jason's own sources")
    p.add_argument("--apply", metavar="PATH", help="write the proposal for this file (needs --yes)")
    p.add_argument("--yes", action="store_true", help="with --apply: write it")
    p.add_argument("--guide", nargs="*", metavar="KEY", help="compile the guide to the documents (default: all) in "
                                                             "data/section-refs/guide")
    p.add_argument("--refresh", action="store_true", help="rebuild the cached versions of the living documents first")
    p.set_defaults(func=cmd_section_refs)


__all__ = ["register", "cmd_section_refs"]
