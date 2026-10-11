"""``jason workflow``: durable workflows from the terminal (docs/workflows-engine.md, section 7).

A workflow is a registered definition (``jason.workflows.definitions``); a run is its append-only event file under
``data/workflows``. One act at a time:

- ``--list [--definition KEY] [--state open|all|WORD] [--json]``, ``--definitions [--family F]``: read.
- ``--start KEY --subject S --label L --date NAME=YYYY-MM-DD ... --by NAME [--yes]``: a draft run (no clock runs yet).
- ``--open RUN --by NAME [--yes]``: a draft becomes active and the resume check runs; it appends only what changed.
- ``--show RUN [--events]``, ``--verify RUN``, ``--reindex``, ``--from-sop KEY``: read (``--reindex`` rewrites the cache
  ``data/workflows/index.json``; ``--from-sop`` prints a DRAFT definition from a procedure and registers nothing).
- ``--attest RUN STEP``, ``--arrived RUN STEP``, ``--skip RUN STEP``, ``--reopen RUN STEP``, ``--pause RUN``,
  ``--resume RUN``, ``--note RUN``, ``--cancel RUN``: a named person's act, each with ``--by``.

Whether a name holds the role a step needs is read from the community's officers (``jason.access.community_officers``,
which adds the portfolio's managers) and jason's administrators. A profile that names none leaves every role-gated act
refused, and the refusal says so.

The general definitions (``jason.workflows.definitions_general``) are registered when a command first needs them, not at
import. A run is read against ``jason.workflows.readers.StoreReaders``: the stores on disk, read only (the follow-ups, the
response inbox, the campaigns, the notice ledger, the approvals store, the job queue). Opening a run finds the plan or
job a person made for a step; it makes none.

It sends nothing, files nothing, and writes only under ``data/workflows``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Callable, Iterable

WRITES = ("start", "open", "attest", "arrived", "skip", "pause", "resume", "reopen", "note", "cancel")
ACTS = ("list", "definitions", "show", "verify", "reindex", "from_sop") + WRITES


def _refuse(reason: str) -> int:
    print(f"jason workflow: {reason}", file=sys.stderr)
    return 2


def _officers() -> tuple[Any, ...]:
    """The community's officers with its portfolio managers (a test replaces this)."""
    from jason.access import community_officers

    return tuple(community_officers())


def _admins() -> tuple[Any, ...]:
    from jason.access import admins

    return tuple(admins())


def _register_general(args: argparse.Namespace) -> None:
    """Register the general definitions (``jason.workflows.definitions_general``) the first time a command needs them. A
    definition that fails its checks is left out and named on stderr; the others still register. A test replaces this."""
    from jason.workflows.definitions_general import register_general
    from jason.workflows.types import InvalidWorkflow

    try:
        from jason.commands._shared import data_dir

        root = data_dir(args)
    except Exception:  # noqa: BLE001 - no data folder: the statutes are not checked against the shelf
        root = None
    try:
        register_general(root)
    except InvalidWorkflow as exc:
        print(f"jason workflow: a general definition is left out: {exc}", file=sys.stderr)


def _readers(root: Any, today: date | None = None) -> Any:
    """The world a run is read against: the stores under ``root`` (``jason.workflows.readers.StoreReaders``). It reads
    only. A test replaces this with fakes, or ``None`` for the engine's bare default."""
    from jason.workflows.readers import StoreReaders

    return StoreReaders(root, today=today)


class Roster:
    """Who holds which role, from the officers and the administrators. Empty when the profile names none."""

    def __init__(self) -> None:
        self.table: dict[str, set[str]] = {}
        self.names: dict[str, str] = {}
        self.problem = ""
        try:
            for o in _officers():
                self._add(o.name, o.role.value)
        except Exception as exc:  # noqa: BLE001 - a roster that cannot be read leaves no one holding a role
            self.problem = f"the community's officers could not be read: {exc}"
        try:
            for a in _admins():
                self._add(a.name, "administrator")
        except Exception as exc:  # noqa: BLE001
            self.problem = self.problem or f"jason's administrators could not be read: {exc}"

    def _add(self, name: str, role: str) -> None:
        key = (name or "").strip().casefold()
        if key:
            self.table.setdefault(key, set()).add(role)
            self.names.setdefault(key, name.strip())

    def __bool__(self) -> bool:
        return bool(self.table)

    def canonical(self, by: str) -> str:
        """The roster's spelling of a name, so one person's acts are recorded under one name."""
        return self.names.get((by or "").strip().casefold(), (by or "").strip())

    def roles_of(self, by: str) -> Iterable[str]:
        return tuple(sorted(self.table.get((by or "").strip().casefold(), ())))

    def note(self) -> str:
        return self.problem or "the profile names no officers, so no role can be checked and every role-gated act is refused"


# --- text -----------------------------------------------------------------------------------------------------------

def _dump(value: Any) -> str:
    return json.dumps(value, indent=1, default=str, ensure_ascii=False)


def _event_line(e: dict[str, Any]) -> str:
    detail = e.get("detail") or {}
    bits = [f"{k}={detail[k]}" for k in ("what", "reason", "record", "outcome", "choice", "text", "item", "child", "ok", "message")
            if detail.get(k) not in (None, "", [])]
    return (f"  n={e['n']:<3} {e['at']}  {e['kind']:<17} {e.get('step', '') or '-':<20} {e.get('by', '') or '-'}"
            + (f"  ({'; '.join(str(b) for b in bits)})" if bits else ""))


def show_lines(run: dict[str, Any], *, events: bool = False) -> list[str]:
    out = [f"{run['id']}  {run['definition']}  {run['label'] or run['subject']}",
           f"  state {run['state']}; subject {run['subject']}; owner {run['owner'] or '?'}; opened {run['opened']}; n={run['n']}"]
    if run.get("parent"):
        out.append(f"  child of {run['parent']}")
    if run["dates"]:
        out.append("  dates: " + ", ".join(f"{k} {v}" for k, v in run["dates"].items()))
    if run["pausedReason"]:
        out.append(f"  paused: {run['pausedReason']}")
    if run["cancelledReason"]:
        out.append(f"  cancelled: {run['cancelledReason']}")
    if run.get("torn"):
        out.append("  WARNING: the last line is torn (a partial write was dropped); the next write cuts it off and keeps its text")
    if run.get("corrupt"):
        out.append(f"  WARNING: line {run['corrupt']} is not an event; nothing more is appended until a person looks at it")
    out.append("")
    out.append("  Steps")
    for s in run["steps"]:
        mark = ">" if s["id"] == run["current"] else " "
        who = f"  by {s['by']} {s['at']}" if s["by"] and s["state"] in ("done", "skipped") else ""
        rec = f"  record {s['record']}" if s["record"] else ""
        out.append(f" {mark} {s['id']:<22} {s['state']:<14} {s['kind']:<9} {s['role']:<14} {s['title']}{who}{rec}")
        if s["reason"]:
            out.append(f"{'':27}{s['reason']}")
        for c in s["changed"]:
            out.append(f"{'':27}changed since: {c.get('address', '')} was {c.get('was', '')}, now {c.get('now', '')}")
        for it in s["items"]:
            out.append(f"{'':27}item {it['item']}: {it['state']}")
    if run["clocks"]:
        out += ["", "  Clocks"]
        for c in run["clocks"]:
            days = "" if c["days"] is None else f" ({c['days']} days)"
            out.append(f"    {c['key']:<22} {c['basis']:<14} {c['due'] or 'undated':<10} {c['status']}{days}  {c['label']} {c['cite']}".rstrip())
    if run["pastLaw"]:
        out.append("  Past law clocks (a person opens the follow-up): " + ", ".join(run["pastLaw"]))
    if run["links"]:
        out += ["", "  Links"]
        out += [f"    {l['kind']:<10} {l['address']}  {l['label']}".rstrip() for l in run["links"]]
    if run["children"]:
        out.append("  Child runs: " + ", ".join(run["children"]))
    if run["orphans"]:
        out.append("  Steps in the events that the definition no longer has: " + ", ".join(run["orphans"]))
    if events:
        out += ["", "  Events"] + [_event_line(e) for e in run.get("events", [])]
    return out


def _list_lines(rows: list[dict[str, Any]]) -> list[str]:
    return [f"{r['id']}  {r.get('definition', ''):<22} {str(r.get('state', '')):<10} due {r.get('due') or '-':<10} "
            f"{r.get('current') or '-':<22} {r.get('label') or r.get('subject') or ''}" for r in rows]


def _definition_lines(workflows: Iterable[Any]) -> list[str]:
    out = []
    for w in workflows:
        legal = " (has a legal clock)" if w.has_legal_clock() else ""
        slots = ", ".join(d.name + ("" if d.required else "?") for d in w.dates) or "no dates"
        out.append(f"{w.key:<26} {w.family:<14} {w.subject:<10} {len(w.steps):>3} steps{legal}  {w.title}")
        out.append(f"{'':26} dates: {slots}")
    return out


# --- the draft from a procedure -------------------------------------------------------------------------------------

def draft_definition(proc: Any) -> str:
    """A DRAFT ``Workflow`` skeleton, as Python source, for a person to finish from a procedure's steps. A person step
    becomes ``person`` (a ``decision`` where the board decides), a step with a command a ``job`` (a ``plan`` where it writes
    outside jason), a step with only a check a ``check``. Every guess is marked ``TODO``; the draft is never registered."""
    key = proc.key
    out = [f"# DRAFT definition built from the procedure {key!r} ({len(proc.steps)} steps). It is not registered.",
           "# Finish every TODO (kind, role, needs, clock, record, skip rule), then add it as a row and run",
           "# jason.workflows.definitions.validate on it. A legal step has no skip rule.",
           "from jason.workflows.types import Role, StepDef, StepKind, Workflow", "",
           "DRAFT = Workflow(", f"    key={key!r},", f"    title={proc.title!r},", "    family='TODO',", "    subject='TODO',  # campaign, unit, meeting, period",
           "    dates=(),  # TODO: DateSlot rows the run is started with",
           f"    procedure={key!r},", "    steps=("]
    previous = ""
    for n, s in enumerate(proc.steps, 1):
        sid = f"{key}.{n}"
        if s.person:
            kind, note = "StepKind.PERSON", "TODO: StepKind.DECISION if the board decides"
        elif s.command:
            kind, note = "StepKind.JOB", "TODO: StepKind.PLAN (plan_kind=) if it writes outside jason"
        elif s.check:
            kind, note = "StepKind.CHECK", "TODO: check= a pure read returning CheckResult"
        else:
            kind, note = "StepKind.PERSON", "TODO: confirm kind"
        why = "; ".join(x for x in ((("lessons: " + ", ".join(s.lessons)) if s.lessons else ""), s.check) if x)
        out.append(f"        StepDef({sid!r}, {s.do!r}, {kind},  # {note}")
        out.append(f"                role=Role.MANAGER,  # TODO: who acts")
        if previous:
            out.append(f"                needs=({previous!r},),  # TODO: check the order")
        if why:
            out.append(f"                why={why!r},")
        if s.command:
            out.append(f"                command={s.command!r},")
        out.append(f"                sop={f'{key}#{n}'!r}),")
        previous = sid
    out += ["    ),", ")"]
    return "\n".join(out)


# --- the command ----------------------------------------------------------------------------------------------------

def _dates(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in pairs or ():
        name, sep, value = raw.partition("=")
        if not sep or not name.strip() or not value.strip():
            raise ValueError(f"--date takes NAME=YYYY-MM-DD, not {raw!r}")
        out[name.strip()] = value.strip()
    return out


def _as_of(args: argparse.Namespace) -> date | None:
    return date.fromisoformat(args.as_of) if getattr(args, "as_of", None) else None


def _summary_line(result: dict[str, Any], what: str) -> str:
    run = result["run"]
    return (f"{run['id']}: {what}; the run is {run['state']}, n={run['n']}"
            + (f", current step {run['current']}" if run["current"] else ""))


def cmd_workflow(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir
    from jason.workflows import api, definitions
    from jason.workflows.store import NoSuchRun
    from jason.workflows.types import WorkflowError

    acts = [a for a in ACTS if a != "list" and getattr(args, a, None)]
    if args.list:
        acts.append("list")
    if len(acts) > 1:
        return _refuse("one act at a time (" + ", ".join("--" + a.replace("_", "-") for a in acts) + " were given)")
    act = acts[0] if acts else "list"
    by_raw = (getattr(args, "by", "") or "").strip()
    if act in WRITES and not by_raw:
        return _refuse(f"--{act.replace('_', '-')} is a write: it needs --by NAME (who is acting)")
    if act == "cancel" and not args.yes:
        return _refuse("--cancel needs --yes (a cancelled run stays listed, but the act is not undone)")

    roster: Roster | None = None
    try:
        if act == "from_sop":
            return _from_sop(args)
        _register_general(args)
        if act == "definitions":
            return _definitions(args, definitions)
        root = data_dir(args)
        today = _as_of(args)
        readers = _readers(root, today)
        roster = Roster() if act in WRITES else None
        by = roster.canonical(by_raw) if roster else by_raw
        roles_of = roster.roles_of if roster else None
        item = _one_item(args, act)
        out: dict[str, Any]
        if act == "list":
            return _list(args, api, definitions, root)
        if act == "show":
            out = api.show(root, args.show, today=today, readers=readers, events=args.events)
            print(_dump(out) if args.json else "\n".join(show_lines(out, events=args.events)))
            return 0
        if act == "verify":
            out = api.verify(root, args.verify)
            print(_dump(out) if args.json else (f"{out['run']}: " + ("whole" if out["ok"] else f"BROKEN at n={out['n']}") +
                                                f": {out['message']} ({out['events']} events)"
                                                + ("; a torn last line was dropped" if out["torn"] else "")))
            return 0 if out["ok"] else 1
        if act == "reindex":
            out = api.reindex(root, today=today)
            bad = [r for r in out["rows"] if r.get("state") == "unreadable"]
            print(_dump(out) if args.json else f"index rebuilt from the events: {out['runs']} run(s)"
                  + "".join(f"\n  unreadable {r['id']}: {r.get('problem', '')}" for r in bad))
            return 0
        expect = args.expect
        if act == "start":
            if definitions.find(args.start) is None:
                return _refuse(_no_definition(args.start, definitions))
            out = api.start(root, args.start, args.subject or "", args.label or "", _dates(args.date), by, items=args.item or (),
                            yes=args.yes, today=today)
            what = f"started as a draft by {by}; no clock runs until --open"
            print(_dump(out) if args.json else _summary_line(out, what))
            return 0
        if act == "open":
            out = api.open_run(root, args.open, by, readers=readers, yes=args.yes, roles_of=roles_of, expect=expect, today=today)
            print(_dump(out) if args.json else "\n".join(
                [_summary_line(out, f"opened by {by}; {len(out['appended'])} event(s) appended")]
                + [_event_line(e) for e in out["appended"]]))
            return 0
        if act == "attest":
            run, step = args.attest
            out = api.attest(root, run, step, by, roles_of=roles_of, record=args.record or "", what=args.what or "", item=item,
                             outcome=args.outcome or "", motion=args.motion or "", choice=args.choice or "", readers=readers,
                             expect=expect, today=today)
        elif act == "arrived":
            run, step = args.arrived
            out = api.arrived(root, run, step, by, roles_of=roles_of, what=args.what or "", item=item, readers=readers, expect=expect, today=today)
        elif act == "skip":
            run, step = args.skip
            out = api.skip(root, run, step, by, roles_of=roles_of, reason=args.reason or "", item=item, readers=readers, expect=expect, today=today)
        elif act == "reopen":
            run, step = args.reopen
            out = api.reopen(root, run, step, by, roles_of=roles_of, reason=args.reason or "", item=item, readers=readers, expect=expect, today=today)
        elif act == "pause":
            run = args.pause
            out = api.pause(root, run, by, reason=args.reason or "", readers=readers, expect=expect, today=today)
        elif act == "resume":
            run = args.resume
            out = api.resume_run(root, run, by, readers=readers, expect=expect, today=today)
        elif act == "note":
            run = args.note
            out = api.note(root, run, by, text=args.text or "", step=args.step or "", readers=readers, expect=expect, today=today)
        else:
            run = args.cancel
            out = api.cancel(root, run, by, roles_of=roles_of, reason=args.reason or "", yes=args.yes, readers=readers, expect=expect, today=today)
        event = out["event"]
        print(_dump(out) if args.json else "\n".join([_summary_line(out, f"{event['kind']} {event.get('step', '') or 'the run'} by {by}"),
                                                       _event_line(event)]))
        return 0
    except NoSuchRun as exc:
        return _refuse(f"{exc} (jason workflow --list shows the runs)")
    except WorkflowError as exc:
        text = str(exc)
        if roster_note := _roster_note(act, text, roster):
            text += f" ({roster_note})"
        return _refuse(text)
    except KeyError as exc:
        return _refuse(str(exc.args[0] if exc.args else exc))
    except ValueError as exc:
        return _refuse(str(exc))
    except RuntimeError as exc:                     # jason.locks.ResourceBusy: another process holds the run
        return _refuse(f"{exc}")


def _roster_note(act: str, text: str, roster: Roster | None) -> str:
    """When the profile names no officers, a role refusal says why nobody holds the role."""
    if roster is None or roster:
        return ""
    if act in WRITES and any(w in text for w in ("role", "may not", "only ")):
        return roster.note()
    return ""


def _one_item(args: argparse.Namespace, act: str) -> str:
    items = args.item or []
    if act == "start" or not items:
        return ""
    if len(items) > 1:
        raise ValueError("--item names one item for an act")
    return items[0]


def _no_definition(key: str, definitions: Any) -> str:
    known = [w.key for w in definitions.all_definitions()]
    return f"no workflow definition {key}: " + (", ".join(known) if known else "No workflows are registered.")


def _definitions(args: argparse.Namespace, definitions: Any) -> int:
    rows = [w for w in definitions.all_definitions() if not args.family or w.family == args.family]
    if args.json:
        print(_dump([{"key": w.key, "title": w.title, "family": w.family, "subject": w.subject, "steps": len(w.steps),
                      "dates": [d.name for d in w.dates], "legalClock": w.has_legal_clock(), "procedure": w.procedure}
                     for w in rows]))
        return 0
    if not rows:
        print("No workflows are registered." if not args.family else f"No workflows are registered in the family {args.family}.")
    else:
        print("\n".join(_definition_lines(rows)))
    for p in definitions.rejected():
        print(f"left out: {p}", file=sys.stderr)
    return 0


def _list(args: argparse.Namespace, api: Any, definitions: Any, root: Any) -> int:
    rows = api.runs(root, definition=args.definition or "", state=args.state)
    if args.json:
        print(_dump(rows))
        return 0
    if not rows:
        print("No runs." + ("" if definitions.all_definitions() else " No workflows are registered."))
        return 0
    print("\n".join(_list_lines(rows)))
    return 0


def _from_sop(args: argparse.Namespace) -> int:
    from jason.community.procedures import find, procedures

    try:
        from jason.community import community

        active = community()
    except Exception:  # noqa: BLE001 - no community chosen: the general procedures only
        active = None
    proc = find(args.from_sop, active)
    if proc is None:
        return _refuse(f"no procedure {args.from_sop}: " + ", ".join(p.key for p in procedures(active)))
    print(draft_definition(proc))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.workflows.types import RunState

    p = sub.add_parser("workflow", help="Durable workflows: list and start runs, open one (the resume check), attest, skip, "
                                        "pause, cancel, verify its hash chain, or draft a definition from a procedure "
                                        "(one act at a time; every write needs --by; writes only data/workflows)")
    add_common(p)
    p.add_argument("--list", action="store_true", help="list the runs (the default)")
    p.add_argument("--definition", metavar="KEY", help="with --list: one definition's runs")
    p.add_argument("--state", default="open", choices=("open", "all", *(s.value for s in RunState)),
                   help="with --list: open (not done or cancelled; the default), all, or one state")
    p.add_argument("--definitions", action="store_true", help="list the registered definitions")
    p.add_argument("--family", metavar="F", help="with --definitions: one family")
    p.add_argument("--start", metavar="KEY", help="start a draft run of a definition (with --subject, --label, --date, --by)")
    p.add_argument("--subject", metavar="S", help="with --start: what the run is about, such as campaign:KEY")
    p.add_argument("--label", metavar="L", default="", help="with --start: the run's name")
    p.add_argument("--date", action="append", metavar="NAME=YYYY-MM-DD", help="with --start: a date the definition asks for (repeat)")
    p.add_argument("--open", metavar="RUN", help="open a run: a draft starts its clocks, then the resume check appends what changed")
    p.add_argument("--show", metavar="RUN", help="a run as it stands now (reads only)")
    p.add_argument("--events", action="store_true", help="with --show: the run's events")
    p.add_argument("--attest", nargs=2, metavar=("RUN", "STEP"),
                   help="record a person's attestation, or the board's decision (with --record, --by; a decision also "
                        "--outcome; a branch --choice)")
    p.add_argument("--arrived", nargs=2, metavar=("RUN", "STEP"), help="note that what a wait step waits for has come (with --by)")
    p.add_argument("--skip", nargs=2, metavar=("RUN", "STEP"), help="skip a step its definition lets be skipped (with --reason, --by)")
    p.add_argument("--reopen", nargs=2, metavar=("RUN", "STEP"), help="open a done, skipped, or failed step again (with --reason, --by)")
    p.add_argument("--pause", metavar="RUN", help="pause a run (with --reason, --by)")
    p.add_argument("--resume", metavar="RUN", help="lift a pause (with --by)")
    p.add_argument("--note", metavar="RUN", help="add a note to a run (with --text, --by; --step for one step)")
    p.add_argument("--cancel", metavar="RUN", help="cancel a run, which stays listed (with --reason, --by, --yes)")
    p.add_argument("--verify", metavar="RUN", help="check a run's hash chain and name the first broken event")
    p.add_argument("--reindex", action="store_true", help="rebuild data/workflows/index.json from the events")
    p.add_argument("--from-sop", dest="from_sop", metavar="KEY",
                   help="print a DRAFT definition from a procedure (jason sop lists them); it is never registered")
    p.add_argument("--record", metavar="REF", help="with --attest: the record that shows it (minutes, a sent notice, a library id)")
    p.add_argument("--what", metavar="TEXT", help="with --attest or --arrived: what was done, in a few words")
    p.add_argument("--outcome", metavar="WORD", help="with --attest on a decision step: adopted, approved, denied, rejected, "
                                                     "withdrawn, tabled, or pending (only a final one finishes the step)")
    p.add_argument("--motion", metavar="TEXT", help="with --attest on a decision step: the motion (default: the step's title)")
    p.add_argument("--choice", metavar="KEY", help="with --attest on a branch step a person answers")
    p.add_argument("--item", action="append", metavar="ITEM", help="with --start: an item of the run (repeat); with an act "
                                                                   "on a per-item step: the item")
    p.add_argument("--step", metavar="STEP", help="with --note: the step it is about")
    p.add_argument("--reason", metavar="TEXT", help="why: a skip, a pause, a reopen, or a cancel")
    p.add_argument("--text", metavar="TEXT", help="with --note: the note")
    p.add_argument("--expect", type=int, metavar="N", help="the run's n you last saw; a run that moved on is refused")
    p.add_argument("--as-of", dest="as_of", metavar="YYYY-MM-DD", help="read the clocks as of this day (default: today)")
    p.add_argument("--by", default="", metavar="NAME", help="who is acting (required for every write; kept with when)")
    p.add_argument("--yes", action="store_true", help="confirm: --cancel always; --start and --open of a run with a legal clock")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_workflow)


__all__ = ["Roster", "cmd_workflow", "draft_definition", "register", "show_lines"]
