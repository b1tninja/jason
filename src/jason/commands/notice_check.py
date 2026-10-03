"""``jason notice-check``: whether a notice carries what the law requires of it.

With no file, checks jason's base notice templates (``jason.tasks.notice_templates``) against their catalog
requirements: each required element present, supplied by a token, said to be enclosed, or missing, with where; and
each sentence where a base states the law in its own words, with the statute's words on disk and the reference token
that would cite it (a proposal; nothing is changed). Writes ``data/reports/notice-templates.md``.

``--file PATH --requirement KEY`` checks one rendered notice (a draft, a filled letter) against one requirement.
Reading only: nothing is sent, and no template is edited.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


def cmd_notice_check(args: argparse.Namespace) -> int:
    from jason.community import community as active
    from jason.config import Settings
    from jason.tasks import notice_templates as nt
    from jason.tasks.cite import Shelf

    if args.file and not args.requirement:
        print("error: --file needs --requirement KEY (jason notices --catalog lists the keys)", file=sys.stderr)
        return 2
    try:
        checks = [nt.check_file(Path(args.file), args.requirement)] if args.file else nt.check_all(tuple(args.keys))
    except (KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([{"requirement": c.base.requirement, "base": c.base.where, "error": c.error,
                           "elements": [f.row() for f in c.findings],
                           "law": [{"line": s.line, "sentence": s.sentence, "citations": list(s.citations),
                                    "tokens": list(s.tokens)} for s in c.law]} for c in checks], indent=1))
        return 0
    data_dir = Settings.load(args.env).payhoa_catalog.parent
    shelf = Shelf(active(), data_dir) if not args.no_law else None
    lines = nt.report_lines(checks, shelf=shelf, law=not args.no_law)
    if shelf is not None:
        lines += nt.recitals_lines(checks, shelf)
    for c in checks:
        miss = c.missing
        unread = sum(1 for f in c.findings if not f.ok and f not in miss)
        head = f"{c.base.requirement}: {sum(1 for f in c.findings if f.ok)} of {len(c.findings)} elements shown" + \
               (f", {unread} for a person to read" if unread else "") + (f" ({c.error})" if c.error else "")
        print(head)
        for f in miss:
            print(f"    missing{' (only for ' + f.applies + ')' if f.applies else ''}: {f.element} ({f.cite})")
    if not args.file:
        path = nt.write(data_dir, lines)
        print(f"Saved {path}")
    else:
        print("\n".join(lines))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("notice-check", help="Check notices and jason's base templates for the elements the law "
                                            "requires (read-only)")
    add_common(p)
    p.add_argument("keys", nargs="*", help="the requirement keys to check (default: every base template)")
    p.add_argument("--file", metavar="PATH", help="a rendered notice to check instead of the bases")
    p.add_argument("--requirement", metavar="KEY", help="with --file: the catalog requirement it serves")
    p.add_argument("--no-law", action="store_true", help="leave out the statements of law and the statutes' words")
    p.add_argument("--json", action="store_true", help="print the findings as JSON")
    p.set_defaults(func=cmd_notice_check)
