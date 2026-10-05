"""``jason notice-check``: whether a notice carries what the law requires of it.

With no file, checks jason's base notice templates (``jason.tasks.notice_templates``) against their catalog
requirements: each required element present, supplied by a token, said to be enclosed, or missing, with where; and
each sentence where a base states the law in its own words, with the statute's words on disk and the reference token
that would cite it (a proposal; nothing is changed). Writes ``data/reports/notice-templates.md``.

``--file PATH --requirement KEY`` checks one rendered notice (a draft, a filled letter) against one requirement.

An element only some notices need (a teleconference meeting's instructions, an emergency rule change's expiry date)
turns on a fact about the event. ``--event FACT=WORD`` says one (``meeting_format=entirely_by_teleconference``,
``rule_change=emergency``, ``electronic_voting=opt_out``; repeatable), and the profile's own facts
(``Community.applicability_facts()``) and a person's answers about the association in the intake queue (``jason
applies --questions``) are read beside it. An element the facts rule out does not apply, with the fact
that decided it; one they call for is required here. With no fact, the element is undetermined: it is checked and
reported with its condition, and the fact that would settle it is named.

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
    from jason.community.notice_elements import EVENT_FACTS, Status, event_facts
    from jason.config import Settings
    from jason.tasks import notice_templates as nt
    from jason.tasks.applicability_asks import association_facts
    from jason.tasks.cite import Shelf

    if args.file and not args.requirement:
        print("error: --file needs --requirement KEY (jason notices --catalog lists the keys)", file=sys.stderr)
        return 2
    try:
        said = event_facts(args.event or (), where="jason notice-check --event")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    data_dir = Settings.load(args.env).payhoa_catalog.parent
    # The profile's facts, then a person's answers about the association in the intake queue, then what was said.
    facts = association_facts(active(), data_dir).merge(said)
    try:
        checks = [nt.check_file(Path(args.file), args.requirement, facts)] if args.file \
            else nt.check_all(tuple(args.keys), facts)
    except (KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([{"requirement": c.base.requirement, "base": c.base.where, "error": c.error,
                           "elements": [f.row() for f in c.findings],
                           "law": [{"line": s.line, "sentence": s.sentence, "citations": list(s.citations),
                                    "tokens": list(s.tokens)} for s in c.law]} for c in checks], indent=1))
        return 0
    shelf = Shelf(active(), data_dir) if not args.no_law else None
    lines = nt.report_lines(checks, shelf=shelf, law=not args.no_law)
    if shelf is not None:
        lines += nt.recitals_lines(checks, shelf)
    for c in checks:
        miss = c.missing
        spared = [f for f in c.findings if f.status is Status.NOT_REQUIRED]
        unread = sum(1 for f in c.findings if not f.ok and f not in miss and f not in spared)
        head = f"{c.base.requirement}: {sum(1 for f in c.findings if f.ok)} of {len(c.findings)} elements shown" + \
               (f", {unread} for a person to read" if unread else "") + \
               (f", {len(spared)} that do not apply" if spared else "") + (f" ({c.error})" if c.error else "")
        print(head)
        for f in miss:
            print(f"    missing{' (' + f.condition() + ')' if f.applies else ''}: {f.element} ({f.cite})")
            if f.needs():
                names = [v.value for v in f.verdict.missing if v in EVENT_FACTS]
                hint = f" (say it with --event {names[0]}=WORD)" if names else ""
                print(f"      undetermined: {f.needs()}{hint}")
        for f in spared:
            print(f"    does not apply: {f.element} ({f.cite}); {f.where}")
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
    p.add_argument("--event", action="append", metavar="FACT=WORD",
                   help="a fact about the meeting, rule change, or election the notice is for, which decides an element "
                        "only some notices need: meeting_format=entirely_by_teleconference, rule_change=emergency, "
                        "electronic_voting=opt_out, election=amendment, director_quorum=at_least_20_percent "
                        "(repeatable)")
    p.add_argument("--no-law", action="store_true", help="leave out the statements of law and the statutes' words")
    p.add_argument("--json", action="store_true", help="print the findings as JSON")
    p.set_defaults(func=cmd_notice_check)
