"""``jason onboard``: bringing an association into jason, as one guided session.

With no flags, the session view (read-only): progress by checklist group, the stage gates (start, ingest, establish,
operate, adopt), and the next questions ranked by what each answer unblocks (``jason.tasks.onboarding_session``).
``--questions`` lists more (``--group``, ``--stage``, ``--limit``). ``--scan`` parks the onboarding questions (facts a
person supplies, documents and records with no book or folder) in the intake queue so they can be answered.

Answering reuses the intake queue (``data/intake/asks.json``) and its apply path: ``--answer ID TEXT --by NAME`` (a
secret is refused and not stored), ``--confirm ID --by NAME`` (a second person, for a high-stakes answer), and
``--apply`` (private facts merged with a backup and a diff; a Keeper record named; a profile change proposed as a
patch under ``data/onboarding/proposals/``; ``--replace`` lets a different answer replace a private fact).

``--checklist`` checks every item of the onboarding checklist (``jason.community.onboarding``) against the active
profile and the data on disk, read-only, and prints present, partial, or missing with the evidence; ``--write`` keeps
the report under ``data/onboarding/``. ``--request SOURCE`` prints the items to ask one source for (the prior manager
by default), as the list a board or a new manager sends. ``--items`` prints the checklist itself.

``--new KEY --name NAME`` starts a new association: its profile package written from jason's general templates
(``jason.tasks.profile_scaffold``), beside the default profile unless ``--dir`` says where, and its empty private facts
in ``data/spec/KEY.json``. It refuses to overwrite either, and refuses a key that collides with a record address's
book, a document key or alias, another profile, or a jason-mcp tool set. ``--county`` sets the profile's region;
``--lookup`` searches that county recorder's public index for the name, read-only, and keeps what it finds as leads,
each asked as a FACT question with the found value as its suggestion (``jason.tasks.onboarding_lookup``). Alone,
``--lookup`` does the same for the active profile.

Nothing here writes to PayHOA, Google, or the mail, or edits an existing profile.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def cmd_onboard(args: argparse.Namespace) -> int:
    from jason.community.onboarding import Group, Source, Stage, items, request_markdown

    try:
        group = Group(args.group) if args.group else None
    except ValueError:
        print(f"groups: {', '.join(g.value for g in Group)}", file=sys.stderr)
        return 2
    if args.stage:
        try:
            Stage(args.stage)
        except ValueError:
            print(f"stages: {', '.join(s.value for s in Stage)}", file=sys.stderr)
            return 2
    if args.request is not None:
        try:
            source = Source(args.request) if args.request else Source.PRIOR_MANAGER
        except ValueError:
            print(f"sources: {', '.join(s.value for s in Source)}", file=sys.stderr)
            return 2
        print(request_markdown(source, title=f"Requested from the {source.value}"))
        return 0
    if args.items:
        for g, rows in ((g, items(g)) for g in Group if group in (None, g)):
            print(g.title)
            for i in rows:
                mark = " [person]" if i.by_person else ""
                print(f"  {i.key}: {i.title}{mark}")
                print(f"    why: {i.why}; from: {', '.join(s.value for s in i.sources)}; fills: {i.fills}")
                if i.ask:
                    print(f"    asks: {i.ask.question} ({i.ask.record.value}{', high stakes' if i.ask.stakes else ''})")
        return 0
    if args.new:
        return _new(args)
    if args.lookup:
        return _lookup_active(args)
    if args.checklist:
        return _checklist(args, group)
    if args.answer or args.confirm or args.apply or args.scan:
        return _queue(args)
    return _session(args, group)


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    settings = Settings.load(args.env)
    return settings, settings.payhoa_catalog.parent


def _session(args: argparse.Namespace, group: Any) -> int:
    from jason.community import community
    from jason.tasks import onboarding_session as session_task

    settings, data_dir = _data_dir(args)
    session = session_task.build(community(), data_dir, settings=settings)
    if not args.questions:
        if args.json:
            out = session_task.status_dict(session)
            out["next"] = [session_task.question_dict(r, session.stored) for r in session.questions(limit=5)]
            print(json.dumps(out, indent=1))
            return 0
        print("\n".join(session_task.lines(session, limit=5)))
        return 0
    rows = session.questions(group=group.value if group else "", stage=args.stage or "", limit=args.limit)
    if args.json:
        print(json.dumps([session_task.question_dict(r, session.stored) for r in rows], indent=1))
        return 0
    total = len(session.questions(group=group.value if group else "", stage=args.stage or ""))
    print(f"{total} open questions" + (f" in {group.value}" if group else "") + (f" for {args.stage}" if args.stage else "")
          + f"; the first {len(rows)} by priority")
    for r in rows:
        print("\n".join(session_task.question_lines(r, session.stored)))
    return 0


def _queue(args: argparse.Namespace) -> int:
    """Scan, answer, confirm, and apply: the intake queue's own paths, holding its store lock."""
    from jason.commands.intake import print_applied
    from jason.community import community, intake
    from jason.locks import Resource, hold
    from jason.tasks import intake as intake_task
    from jason.tasks import onboarding_session as session_task

    settings, data_dir = _data_dir(args)
    with hold(Resource.STORE, "intake-asks", timeout=120, purpose="jason onboard"):
        asks = intake.load(data_dir)
        if args.scan or args.answer:
            # The onboarding questions are added (an id not yet in the queue can then be answered); a document
            # question is left as the last ``jason intake --scan`` parked it.
            asks = intake.merge(asks, session_task.generate_for(community(), data_dir, settings=settings),
                                scope=session_task.SCOPE)
            intake.save(data_dir, asks)
            if args.scan:
                fresh = [a for a in asks if a.kind.value in ("fact", "map") and a.status is intake.AskStatus.OPEN]
                print(f"onboarding questions open in the queue: {len(fresh)} "
                      f"({sum(a.kind.value == 'fact' for a in fresh)} facts, {sum(a.kind.value == 'map' for a in fresh)} maps)")
        if args.answer:
            ident, text = args.answer
            try:
                a = intake.answer(asks, ident, text, args.by or "")
            except (KeyError, ValueError) as exc:
                print(f"cannot answer {ident}: {exc}", file=sys.stderr)
                return 2
            intake.save(data_dir, asks)
            print(f"{a.id}: {a.status.value} (by {a.answered_by}, {a.answered_at})"
                  + ("; high stakes: a second person confirms it (--confirm ID --by NAME) before --apply"
                     if intake.high_stakes(a) and a.status is intake.AskStatus.ANSWERED else ""))
        if args.confirm:
            try:
                a = intake.confirm(asks, args.confirm, args.by or "")
            except (KeyError, ValueError) as exc:
                print(f"cannot confirm {args.confirm}: {exc}", file=sys.stderr)
                return 2
            intake.save(data_dir, asks)
            print(f"{a.id}: confirmed by {a.confirmed_by} (answered by {a.answered_by})")
        if args.apply:
            refused: list = []
            shown: list = []
            done = intake_task.apply(asks, data_dir, refused=refused, shown=shown, replace=args.replace)
            intake.save(data_dir, asks)
            print_applied(done, refused, shown)
    return 0


def _new(args: argparse.Namespace) -> int:
    """Write a new association's profile package and its empty private facts; with ``--lookup``, its leads."""
    from pathlib import Path

    from jason.tasks import profile_scaffold as scaffold

    try:
        made = scaffold.write(args.new, args.name or "", county=args.county or "",
                              directory=Path(args.dir) if args.dir else None)
    except scaffold.ScaffoldRefused as exc:
        print("not written:", file=sys.stderr)
        for reason in exc.reasons:
            print(f"  {reason}", file=sys.stderr)
        return 2
    print(f"wrote the profile {made.key} ({made.name}) at {made.package}: {len(made.files)} files")
    for path in made.files:
        print(f"  {path.relative_to(made.package).as_posix()}")
    print(f"wrote empty private facts at {made.spec} (never checked in)")
    if args.lookup:
        _print_lookup(made.key, made.name, args.county or "")
    print("\nTo make it the active profile, set in .env (or the environment):")
    for line in scaffold.environment(made):
        print(f"  {line}")
    print(f"Its stores are under data/{made.key}/ unless PAYHOA_CATALOG names another folder. Then:\n"
          f"  jason onboard                 # every gate closed, the checklist mostly missing, the next questions")
    return 0


def _print_lookup(profile: str, name: str, county: str) -> None:
    from jason.tasks import onboarding_lookup as lookup

    found = lookup.lookup(name, county)
    if found.leads:
        path = lookup.save_leads(profile, found.leads)
        print(f"\nleads from public sources: {len(found.leads)}, kept in {path} and asked as FACT questions:")
        for lead in found.leads:
            print(f"  {lead['key']}: {lead['suggestion']} (serves {lead['item']}"
                  + (", high stakes" if lead.get("stakes") else "") + ")")
    else:
        print("\nleads from public sources: none")
    for note in found.notes:
        print(f"  {note}")


def _lookup_active(args: argparse.Namespace) -> int:
    """The lookup for the active profile: its name, in the county its ``region`` names (or ``--county``)."""
    from jason.community import community
    from jason.community.profile import profile_name

    the = community()
    county = args.county or (the.region.split("/", 1)[1] if "/" in the.region else "")
    _print_lookup(profile_name(), the.name, county)
    return 0


def _checklist(args: argparse.Namespace, group: Any) -> int:
    from jason.community import community
    from jason.community.onboarding import Status, by_group, counts, report_dicts
    from jason.tasks.onboarding import run, write_report

    settings, data_dir = _data_dir(args)
    the = community()
    results = run(the, data_dir, settings=settings)
    if group is not None:
        results = tuple(r for r in results if r.item.group is group)
    if args.status:
        results = tuple(r for r in results if r.status is Status(args.status))
    if args.write:
        print(f"wrote {write_report(results, data_dir, title=f'Onboarding checklist: {the.name}')}")
    if args.json:
        print(json.dumps(report_dicts(results), indent=1))
        return 0
    total = counts(results)
    print(f"{len(results)} items: {total['present']} present, {total['partial']} partial, {total['missing']} missing")
    for g, rows in by_group(results).items():
        print(g.title)
        for r in rows:
            mark = " [person]" if r.item.by_person else ""
            print(f"  {r.status.value:8} {r.item.key}: {r.item.title}{mark}")
            print(f"           {r.evidence}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("onboard", help="Onboarding as a session: progress, stage gates, and the next questions ranked "
                                       "by what each answer unblocks; the checklist; answers that become records")
    add_common(p)
    p.add_argument("--questions", action="store_true", help="list the open questions by priority (--group, --stage, --limit)")
    p.add_argument("--stage", help="with --questions: one stage (start, ingest, establish, operate, adopt)")
    p.add_argument("--limit", type=int, default=20, help="with --questions: how many (default 20)")
    p.add_argument("--scan", action="store_true", help="park the onboarding questions in the intake queue (data/intake)")
    p.add_argument("--answer", nargs=2, metavar=("ID", "TEXT"),
                   help="answer one question (a choice's number or words; dismiss); a secret is refused, never stored")
    p.add_argument("--confirm", metavar="ID", help="a second person confirms a high-stakes answer (with --by)")
    p.add_argument("--by", help="the person answering or confirming (required to answer or confirm)")
    p.add_argument("--apply", action="store_true",
                   help="turn answers into records: private facts (with a backup and a diff), Keeper notes, proposed "
                        "profile patches in data/onboarding/proposals/")
    p.add_argument("--replace", action="store_true", help="with --apply: let a new answer replace a different private fact")
    p.add_argument("--checklist", action="store_true", help="check each item: present, partial, or missing, with the evidence")
    p.add_argument("--items", action="store_true", help="print the checklist itself: each item, why, where it comes from, and what it fills")
    p.add_argument("--request", nargs="?", const="", default=None, metavar="SOURCE",
                   help="print the items to ask one source for (default: the prior manager)")
    p.add_argument("--group", help="one group, e.g. finance or insurance (the checklist, or --questions)")
    p.add_argument("--status", choices=("present", "partial", "missing"), help="with --checklist: only items with this status")
    p.add_argument("--write", action="store_true", help="with --checklist: keep the report in data/onboarding/ (private)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--new", metavar="KEY",
                   help="write a new association's profile package from jason's templates (with --name; --county, "
                        "--dir, --lookup), and its empty private facts in data/spec/KEY.json; never overwrites")
    p.add_argument("--name", help="with --new: the association's name as its notices give it")
    p.add_argument("--county", help="with --new or --lookup: the county whose public records hold the association's")
    p.add_argument("--dir", help="with --new: where to write the package (default: beside the default profile)")
    p.add_argument("--lookup", action="store_true",
                   help="search the county recorder's public index for the association's name, read-only; each find "
                        "becomes a FACT question with the found value as its suggestion (alone: the active profile)")
    p.set_defaults(func=cmd_onboard)
