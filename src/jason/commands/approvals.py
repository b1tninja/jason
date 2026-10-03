"""``jason approvals``: plans of writes outside jason, decided item by item by a named person (``jason.approvals``).

``jason approvals`` lists them, open ones first. ``plan KIND`` reads live and stores a plan (it writes nothing
outside jason). ``show ID`` gives its items: the approvable ones, then those held for the board, for a person, to
confirm with the owner, and what follows. ``decide ID --items ... --by NAME`` approves (``--hold`` or ``--reject`` with
``--reason``), ``submit ID --by NAME`` signs, ``confirm ID --by NAME`` is the second person. ``apply ID`` re-plans
live and shows whether anything changed since review, writing nothing; ``apply ID --yes`` applies only the approved
items, or, when something changed, supersedes the approval with a new plan and writes nothing. ``audit`` reads the
log; ``--verify`` checks its chain.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ACTIONS = ("list", "kinds", "plan", "show", "decide", "submit", "confirm", "decline", "withdraw", "apply", "audit")

_SECTIONS = (
    ("approvable", "To decide"),
    ("held_for_board", "Held for the board (never approvable)"),
    ("for_a_person", "For a person, in PayHOA (never approvable)"),
    ("confirm_with_owner", "Confirm with the owner first (never approvable)"),
    ("informational", "What follows"),
)


def _data_dir(args: argparse.Namespace) -> Path:
    from jason.config import data_dir

    return data_dir(getattr(args, "env", None))


def _live(args: argparse.Namespace, agent: Any, kind: Any) -> Any:
    from jason.approvals import Live

    if agent is None:
        return Live(data_dir=_data_dir(args), env=getattr(args, "env", None))
    return Live(agent.payhoa(), agent.org_id, _data_dir(args), getattr(args, "env", None))


def _with_live(args: argparse.Namespace, agent_factory: Callable[[Any], Any], kind: Any,
               fn: Callable[[Any], int]) -> int:
    """Run ``fn`` with the live context the kind's system needs (PayHOA: a signed-in client)."""
    if kind.system == "payhoa":
        with agent_factory(args) as agent:
            return fn(_live(args, agent, kind))
    return fn(_live(args, None, kind))


def _age(stamp: str) -> str:
    try:
        delta = datetime.now(timezone.utc) - datetime.fromisoformat(stamp)
    except ValueError:
        return "?"
    hours = delta.total_seconds() / 3600
    return f"{hours:.0f}h" if hours < 48 else f"{hours / 24:.0f}d"


def _list(args: argparse.Namespace) -> int:
    from jason.approvals import store
    from jason.approvals.model import OPEN

    rows = store.load_all(_data_dir(args))
    if args.status:
        rows = [a for a in rows if a.status.value == args.status]
    if args.kind:
        rows = [a for a in rows if a.kind == args.kind]
    rows.sort(key=lambda a: (a.status not in OPEN, a.requested_at), reverse=False)
    if not rows:
        print("no approvals (jason approvals plan KIND makes one)")
        return 0
    for a in rows:
        approvable = len(a.approvable)
        held = sum(1 for i in a.items if i.klass.value == "held_for_board")
        print(f"{a.id}  {a.kind:16} {a.status.value:18} {approvable:3} to decide, {len(a.approved):3} approved, "
              f"{held:2} held  {_age(a.requested_at):>4}  by {a.requested_by}")
    return 0


def _item_line(i: Any) -> str:
    change = i.change.text() if i.change is not None else i.value
    decided = ""
    if i.decision.value != "undecided":
        decided = f"  [{i.decision.value} by {i.decided_by}" + (f": {i.reason}" if i.reason else "") + "]"
    result = f"  -> {i.result.value}" + (f" ({i.result_detail})" if i.result_detail else "") \
        if i.result.value != "pending" else ""
    board = f"  board item {i.board_item}" if i.board_item else ""
    waits = f"  waits on {', '.join(d[:10] for d in i.depends_on)}" if i.depends_on and i.approvable else ""
    return f"    {i.id[:10]}  {i.op:18} {change}{board}{waits}{decided}{result}\n{'':16}why: {i.why}" \
           + (f"\n{'':16}rule: {i.rule}" if i.rule else "")


def show_lines(a: Any) -> list[str]:
    from jason.approvals.engine import counts, needs_second
    from jason.approvals.model import short

    out = [f"{a.id}  {a.title}", f"  kind {a.kind}; status {a.status.value}; fingerprint {short(a.fingerprint)}",
           f"  read live {a.read_at}; asked by {a.requested_by} ({a.requested_via})"]
    if a.clock:
        out.append(f"  clock: {a.clock.get('what')} {a.clock.get('due')} ({a.clock.get('daysLeft')} days)")
    if a.first:
        out.append(f"  submitted by {a.first.name} at {a.first.at}")
    if needs_second(a) and a.status.value in ("approved", "partially_approved", "applying", "applied", "failed"):
        out.append(f"  second person: {a.second.name if a.second else 'needed (jason approvals confirm ID --by NAME)'}")
    if a.supersedes:
        out.append(f"  supersedes {a.supersedes}")
    if a.superseded_by:
        out.append(f"  superseded by {a.superseded_by}")
    out.append("  " + json.dumps(counts(a)))
    for key, title in _SECTIONS:
        section = [i for i in a.items if i.klass.value == key]
        if not section:
            continue
        out.append(f"\n  {title} ({len(section)})")
        groups: dict[str, list[Any]] = {}
        for i in section:
            groups.setdefault(i.group or i.label, []).append(i)
        for group, items in groups.items():
            out.append(f"   {group}")
            out += [_item_line(i) for i in items]
    for note in a.notes:
        out.append(f"  note: {note}")
    return out


def _decision(args: argparse.Namespace) -> Any:
    from jason.approvals import Decision

    if args.hold and args.reject:
        raise SystemExit("--hold or --reject, not both")
    return Decision.HELD if args.hold else Decision.REJECTED if args.reject else Decision.APPROVED


def _recheck_lines(r: Any) -> list[str]:
    from jason.approvals.model import short

    out = [f"{r.approval.id}: {r.approval.status.value}; {len(r.approval.approved)} approved item(s)"]
    out += [f"  refused: {p}" for p in r.problems]
    if r.planned is None:
        return out
    out.append(f"  approved items' basis at review {short(r.then)}, read live now {short(r.now)}: "
               + ("unchanged" if not r.changed else f"{len(r.changed)} changed since review"))
    for c in r.changed:
        out.append(f"    {c.id[:10]} {c.op} {c.label}: {c.why}")
    if r.new:
        out.append(f"  {len(r.new)} approvable item(s) new since review, not included")
    if r.ok:
        out.append("  would apply:")
        out += [f"    {i.id[:10]} {i.op:18} {i.change.text() if i.change else i.value}  ({i.label})"
                for i in r.approval.approved]
        out.append("Dry run (read live just now; nothing written): add --yes to apply the approved items.")
    elif r.changed and not r.problems:
        out.append("With --yes nothing would be written: the approval would be superseded by a new plan to review.")
    return out


def cmd_approvals(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.approvals import engine, registry, store
    from jason.approvals.audit import os_actor
    from jason.approvals.model import to_dict

    data_dir = _data_dir(args)
    action = args.action
    try:
        if action == "list":
            return _list(args)
        if action == "kinds":
            for k in registry.kinds():
                print(f"{k.key:18} {k.risk.name} {k.approver.value:10} {k.title}  (beside: {k.cli})")
            return 0
        if action == "audit":
            return _audit(args, data_dir)
        if not args.ref:
            print(f"jason approvals {action} needs {'a KIND' if action == 'plan' else 'an ID'}", file=sys.stderr)
            return 2
        if action == "plan":
            kind = registry.get(args.ref)
            by = args.by or os_actor()
            a = _with_live(args, agent_factory, kind, lambda live: _planned(engine.plan(kind.key, live, by=by)))
            return a
        if action == "show":
            a = store.load(args.ref, data_dir)
            print(json.dumps(to_dict(a), indent=1, ensure_ascii=False) if args.json else "\n".join(show_lines(a)))
            return 0
        if action == "decide":
            if not args.items and not args.all:
                print("decide needs --items ID [ID ...] or --all", file=sys.stderr)
                return 2
            a = engine.decide(args.ref, "all" if args.all else args.items, by=args.by or "", decision=_decision(args),
                              reason=args.reason or "", data_dir=data_dir)
            undecided = sum(1 for i in a.approvable if i.decision.value == "undecided")
            print(f"{a.id}: {a.status.value}; {len(a.approved)} approved, {undecided} undecided"
                  + ("" if undecided else f" (jason approvals submit {a.id} --by NAME)"))
            return 0
        if action == "submit":
            a = engine.submit(args.ref, by=args.by or "", data_dir=data_dir)
            print(f"{a.id}: {a.status.value}" + ("; a second person confirms next" if engine.needs_second(a)
                                                 and a.status.value != "withdrawn" else ""))
            return 0
        if action == "confirm":
            a = engine.confirm(args.ref, by=args.by or "", data_dir=data_dir)
            print(f"{a.id}: confirmed by {a.second.name}")
            return 0
        if action == "decline":
            a = engine.decline(args.ref, by=args.by or "", reason=args.reason or "", data_dir=data_dir)
            print(f"{a.id}: back to review")
            return 0
        if action == "withdraw":
            a = engine.withdraw(args.ref, by=args.by or "", reason=args.reason or "", data_dir=data_dir)
            print(f"{a.id}: withdrawn")
            return 0
        if action == "apply":
            kind = registry.get(store.load(args.ref, data_dir).kind)
            if not args.yes:
                def dry(live: Any) -> int:
                    r = engine.check(args.ref, live, data_dir=data_dir)
                    print("\n".join(_recheck_lines(r)))
                    return 0 if r.ok else 1
                return _with_live(args, agent_factory, kind, dry)

            def wet(live: Any) -> int:
                done = engine.apply(args.ref, live, by=args.by or os_actor(), data_dir=data_dir)
                if done.superseded_by is not None:
                    print(f"changed since review: nothing written. {done.approval.id} is superseded by "
                          f"{done.superseded_by.id} (jason approvals show {done.superseded_by.id})")
                    for c in done.changed:
                        print(f"  {c.id[:10]} {c.op} {c.label}: {c.why}")
                    return 1
                a = done.approval
                print(f"{a.id}: {a.status.value}; " + ", ".join(f"{k} {v}" for k, v in a.result.items()
                                                               if k not in ("at", "by")))
                for i in a.approved:
                    print(f"  {i.id[:10]} {i.op:18} {i.label[:40]:40} {i.result.value}"
                          + (f" ({i.result_detail})" if i.result_detail else ""))
                return 0 if a.status.value == "applied" else 1
            return _with_live(args, agent_factory, kind, wet)
    except (engine.Refused, KeyError) as exc:
        print(f"refused: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 2
    print(f"unknown action {action}", file=sys.stderr)
    return 2


def _planned(a: Any) -> int:
    print("\n".join(show_lines(a)))
    print(f"\nPlanned (read live; nothing written outside jason): jason approvals decide {a.id} --items ID ... "
          "--by NAME")
    return 0


def _audit(args: argparse.Namespace, data_dir: Path) -> int:
    from jason.approvals import audit

    if args.verify:
        ok, line, why = audit.verify(data_dir)
        print(("whole: " if ok else f"broken at line {line}: ") + why)
        return 0 if ok else 1
    for e in audit.read(data_dir, args.ref or ""):
        what = e.get("item") or ",".join(e.get("items") or [])[:40]
        print(f"{e['seq']:5} {e['at']} {e['event']:20} {e.get('approval', '-'):26} {e.get('actor', '')} "
              f"{what} {e.get('result', '') if not isinstance(e.get('result'), dict) else json.dumps(e['result'])}"
              f" {e.get('detail', '')}".rstrip())
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("approvals", help="Plans of writes outside jason, approved item by item by a named person")
    add_common(p)
    p.add_argument("action", nargs="?", default="list", choices=ACTIONS,
                   help="list (default), kinds, plan KIND, show ID, decide ID, submit ID, confirm ID, decline ID, "
                        "withdraw ID, apply ID, audit [ID]")
    p.add_argument("ref", nargs="?", help="the kind (plan) or the approval's id or a unique prefix")
    p.add_argument("--by", metavar="NAME", help="the person deciding, submitting, confirming, or applying")
    p.add_argument("--items", nargs="+", metavar="ITEM", help="with decide: item ids or unique prefixes (6+ characters)")
    p.add_argument("--all", action="store_true", help="with decide: every approvable item")
    p.add_argument("--hold", action="store_true", help="with decide: hold the items (needs --reason)")
    p.add_argument("--reject", action="store_true", help="with decide: leave the items out (needs --reason)")
    p.add_argument("--reason", help="why: a hold, a rejection, a decline, or a withdrawal")
    p.add_argument("--yes", action="store_true",
                   help="with apply: apply the approved items (without it: re-plan and compare, writing nothing)")
    p.add_argument("--json", action="store_true", help="with show: the approval as JSON")
    p.add_argument("--status", help="with list: only this status (planned, in_review, approved, ...)")
    p.add_argument("--kind", help="with list: only this kind")
    p.add_argument("--verify", action="store_true", help="with audit: check the log's hash chain")
    p.set_defaults(func=lambda a: cmd_approvals(a, agent_factory))
