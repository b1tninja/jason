"""``jason workflow``: durable workflows from the terminal (docs/workflows-engine.md, section 7).

A workflow is a registered definition (``jason.workflows.definitions``); a run is its append-only event file under
``data/workflows``. One act at a time:

- ``--list [--definition KEY] [--state open|all|WORD] [--json]``, ``--definitions [--family F]``: read.
- ``--start KEY --subject S --label L --date NAME=YYYY-MM-DD ... --by NAME [--yes]``: a draft run (no clock runs yet).
- ``--open RUN --by NAME [--yes]``: a draft becomes active and the resume check runs; it appends only what changed.
- ``--show RUN [--events]``, ``--verify RUN``, ``--reindex``, ``--from-sop KEY``: read (``--reindex`` rewrites the cache
  ``data/workflows/index.json``; ``--from-sop`` prints a DRAFT definition from a procedure and registers nothing).
- ``--attest RUN STEP``, ``--arrived RUN STEP``, ``--skip RUN STEP``, ``--na RUN STEP``, ``--reopen RUN STEP``, ``--pause RUN``,
  ``--resume RUN``, ``--note RUN``, ``--cancel RUN``, ``--set-date RUN SLOT=YYYY-MM-DD``: a named person's act, each with
  ``--by``. ``--na`` records a step as not applicable (``--reason`` and ``--record``; not a skip, so a legal step may be
  recorded this way). ``--set-date`` gives a late or optional date slot a day after the start (``--record``; a correction
  also needs ``--reason``).
- ``--supply RUN --set NAME --item ID [--item ID ...] --by NAME [--item-date ID SLOT=YYYY-MM-DD --record REF] [--yes]``: give a
  named item set (``--set ""``, or leaving it out, is the run's own) more items while the run goes. An item is an opaque id,
  never a name or an address (the engine refuses one in its own words). Without ``--yes`` it checks everything and prints what
  would be recorded; nothing is written. The person must be on the roster. ``--item-date`` gives one item the date a slot reads
  for its own clocks (needs ``--record``; a later supply of the same id corrects it).
- ``--guide RUN[:STEP]`` (or ``DEFINITION.STEP`` for the definition's words alone) prints the step panel's sections as plain text
  (docs/workflows/person-steps.md, section 7.4): the enable state (with ``--for NAME``), the due line, Do this, Look at, The rule (the
  statute's words from the stored copy, then the reading, labeled), Check before you go on, The command, Done when, If you are blocked,
  If it does not apply, Ask, Learn more. Reads only; it never opens a run.
- ``--due --for NAME [--within DAYS] [--all]`` lists the person steps due, late, or open a while for a person (their offices from the
  roster), most urgent first, and what is escalated to their office (visibility only). Reads only; nothing is sent to anyone.
- ``--claim RUN STEP --by NAME [--release] --yes`` says you are on a step (or lets it go): a note, not an assignment. Without ``--yes`` it
  checks everything and writes nothing.

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

WRITES = ("start", "open", "attest", "arrived", "skip", "na", "set_date", "supply", "claim", "pause", "resume", "reopen", "note", "cancel")
ACTS = ("list", "definitions", "show", "verify", "reindex", "from_sop", "guide", "due") + WRITES


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
    bits = [f"{k}={detail[k]}" for k in ("what", "reason", "record", "outcome", "choice", "text", "item", "child", "slot", "day",
                                        "ok", "message")
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
        roles = "/".join(s.get("roles") or [s["role"]])
        na = "  (not applicable)" if s.get("na") else ""
        out.append(f" {mark} {s['id']:<22} {s['state']:<14} {s['kind']:<9} {roles:<14} {s['title']}{who}{rec}{na}")
        if s["reason"]:
            out.append(f"{'':27}{s['reason']}")
        for c in s["changed"]:
            out.append(f"{'':27}changed since: {c.get('address', '')} was {c.get('was', '')}, now {c.get('now', '')}")
        if s.get("remedy"):
            out.append(f"{'':27}stays recorded as failed; the step {s['remedy']} remedies it")
        if s.get("itemCounts"):
            out.append(f"{'':27}items: " + ", ".join(f"{n} {state}" for state, n in s["itemCounts"].items()))
        for it in s["items"]:
            out.append(f"{'':27}item {it['item']}: {it['state']}")
    for g in run.get("groups", ()):
        out.append(f"  group {g['key']} ({g['title']}): {g['state']}, {g['done']} of {g['total']} done, "
                   + ("expanded" if g["expanded"] else "collapsed"))
    open_slots = [d for d in run.get("dateSlots", ()) if d.get("settable")]
    if open_slots:
        out.append("  dates a person may set (--set-date): " + ", ".join(
            f"{d['name']}" + (f" (now {d['value']}; a correction needs a reason)" if d.get("value") else " (not set)") for d in open_slots))
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


def _slot_day(pair: str) -> tuple[str, str]:
    name, sep, value = pair.partition("=")
    if not sep or not name.strip() or not value.strip():
        raise ValueError(f"--set-date takes RUN SLOT=YYYY-MM-DD, not {pair!r}")
    return name.strip(), value.strip()


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
        if act == "guide":
            return _guide(args, root, today, readers)
        if act == "due":
            return _due(args, root, today, readers)
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
        elif act == "na":
            run, step = args.na
            out = api.not_applicable(root, run, step, by, roles_of=roles_of, reason=args.reason or "", record=args.record or "",
                                     item=item, readers=readers, expect=expect, today=today)
        elif act == "set_date":
            run, pair = args.set_date
            slot, day = _slot_day(pair)
            out = api.set_date(root, run, slot, day, by, roles_of=roles_of, record=args.record or "", reason=args.reason or "",
                               readers=readers, expect=expect, today=today)
        elif act == "supply":
            return _supply(args, api, root, roster, by, readers, today)
        elif act == "claim":
            return _claim(args, api, root, roster, by, readers, today)
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


def _supply_entries(args: argparse.Namespace) -> list[Any]:
    """The entries of a supply: each ``--item`` an id, and an id given ``--item-date`` an entry with its slot dates (the ids
    once, in the order given). Whether an id may be one, and whether a date is a day of a declared slot, is the engine's."""
    dates: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for item in args.item or ():
        if item not in order:
            order.append(item)
    for item, pair in getattr(args, "item_date", None) or ():
        slot, day = _slot_day(pair)
        if item not in order:
            order.append(item)
        dates.setdefault(item, {})[slot] = day
    return [{"id": i, "dates": dates[i]} if i in dates else i for i in order]


def _supply_lines(out: dict[str, Any], by: str) -> list[str]:
    noun = lambda n: f"{n} item" + ("" if n == 1 else "s")  # noqa: E731
    where = f"the set {out['set']}" if out["set"] else "the run's own items"
    lines = [f"{out['run']}: would supply {noun(len(out['wouldAdd']))} to {where} in the name of {by}"
             + (f" ({len(out['alreadyThere'])} already there)" if out["alreadyThere"] else "")
             + "; nothing is written without --yes"]
    if out["wouldAdd"]:
        lines.append("  new: " + ", ".join(out["wouldAdd"]))
    if out["alreadyThere"]:
        lines.append("  already in the set: " + ", ".join(out["alreadyThere"]))
    if out["withDates"]:
        lines.append("  with their own dates: " + ", ".join(out["withDates"]))
    if out["record"]:
        lines.append(f"  record: {out['record']}")
    return lines


def _supply(args: argparse.Namespace, api: Any, root: Any, roster: Roster | None, by: str, readers: Any,
            today: date | None) -> int:
    """``--supply RUN --set NAME --item ID ...``: the engine's ``supply_items``, after the CLI's own checks (the person is on the
    roster). Without ``--yes`` the same checks run and nothing is written."""
    if not (roster and roster.roles_of(by)):
        return _refuse(f"{by} is not on the roster (the community's officers and jason's administrators), so no items are "
                       f"supplied in that name" + (f" ({roster.note()})" if roster is not None and not roster else ""))
    entries = _supply_entries(args)
    kw = dict(roles_of=roster.roles_of, record=args.record or "", readers=readers, expect=args.expect, today=today)
    run, name = args.supply, (args.item_set or "").strip()
    if not args.yes:
        out = api.supply_items(root, run, name, entries, by, dry_run=True, **kw)
        print(_dump(out) if args.json else "\n".join(_supply_lines(out, by)))
        return 0
    out = api.supply_items(root, run, name, entries, by, **kw)
    event = out["event"]
    print(_dump(out) if args.json else "\n".join(
        [_summary_line(out, f"{(event.get('detail') or {}).get('text', 'items supplied')} by {by}"), _event_line(event)]))
    return 0


def _claim(args: argparse.Namespace, api: Any, root: Any, roster: Roster | None, by: str, readers: Any, today: date | None) -> int:
    """``--claim RUN STEP --by NAME [--release] --yes``: a note that says you are on a step. Without ``--yes`` the same checks run and
    nothing is written. The person must be on the roster."""
    if not (roster and roster.roles_of(by)):
        return _refuse(f"{by} is not on the roster (the community's officers and jason's administrators), so no claim is made in that name"
                       + (f" ({roster.note()})" if roster is not None and not roster else ""))
    run, step = args.claim
    kw = dict(roles_of=roster.roles_of, release=bool(args.release), readers=readers, expect=args.expect, today=today)
    if not args.yes:
        out = api.claim(root, run, step, by, dry_run=True, **kw)
        print(_dump(out) if args.json else f"{run}: would record that {out['text']} on {step}; nothing is written without --yes")
        return 0
    out = api.claim(root, run, step, by, **kw)
    event = out["event"]
    print(_dump(out) if args.json else "\n".join(
        [_summary_line(out, f"{by} {event['detail'].get('text', 'claimed')} {step}"), _event_line(event)]))
    return 0


def _community_or_none() -> Any:
    try:
        from jason.community import community

        return community()
    except Exception:  # noqa: BLE001 - no community chosen: the general procedures only
        return None


def _holders() -> Any:
    """The roster by office (the community's officers and jason's administrators); a roster that cannot be read is an unknown one."""
    from jason.tasks.step_guide import Holders

    try:
        officers = _officers()
    except Exception:  # noqa: BLE001
        officers = ()
    try:
        admins = _admins()
    except Exception:  # noqa: BLE001
        admins = ()
    return Holders.from_officers(officers, admins)


def _first_by(events: list[Any], step_id: str) -> str:
    from jason.workflows import api

    return api.pending_first(events, step_id, "attest")


def _guide(args: argparse.Namespace, root: Any, today: date | None, readers: Any) -> int:
    """``--guide RUN[:STEP]`` or ``--guide DEFINITION.STEP``: the step panel's sections as plain text, in the panel's order."""
    from jason.tasks import step_guide
    from jason.workflows import definitions, nudge, store

    day = today or date.today()
    target = (args.guide or "").strip()
    run_id, _, step_id = target.partition(":")
    community = _community_or_none()
    holders = _holders()
    person = (getattr(args, "for_person", "") or getattr(args, "by", "") or "").strip()
    who = step_guide.Person(person, holders.roles_of(person)) if person else None
    view = sv = None
    events: list[Any] = []
    try:
        definition = store.locate(root, run_id)
    except store.NoSuchRun:
        definition = ""
    if definition:
        wf = definitions.get(definition)
        events, view = step_guide.folded(root, wf, run_id, day, readers)
        people = [s for s in wf.steps if nudge.is_person_step(s)]
        step_id = step_id or (view.current if wf.step(view.current) is not None and nudge.is_person_step(wf.step(view.current))
                              else (people[0].id if people else ""))
        if wf.step(step_id) is None:
            return _refuse(f"no step {step_id!r} in {wf.key}: " + ", ".join(s.id for s in people))
    else:
        wf = next((w for w in definitions.all_definitions() if w.step(target)), None)
        if wf is None:
            return _refuse(f"{target!r} is neither a run (jason workflow --list) nor a step of a definition (jason workflow --definitions)")
        step_id = target
    sd = wf.step(step_id)
    if not nudge.is_person_step(sd):
        return _refuse(f"{sd.id} is a {sd.kind.value} step: jason's, not a person's, so it has no guide "
                       "(a guide is for a person step, a decision, or a wait only a note ends)")
    proc = None
    if wf.procedure:
        try:
            from jason.community.procedures import find

            proc = find(wf.procedure, community)
        except Exception:  # noqa: BLE001 - no procedure is no derived text
            proc = None
    position = next(i for i, s in enumerate(wf.steps, 1) if s.id == sd.id)
    backup = getattr(community, "backup_for", None)
    enable = nud = None
    if view is not None:
        sv = view.step(sd.id)
        offices = {r.value for r in sd.acting_roles if r.value not in ("anyone", "jason", "scheduler")}
        n = nudge.step_nudge(wf, sd, view, day, vacant=holders.vacant(offices), claims=nudge.claims_of(events))
        nud = step_guide.nudge_dict(n, who_account=person)
        if who is not None:
            enable = step_guide.enable_dict(wf, sd, sv, view, who, holders, procedure=proc, first_by=_first_by(events, sd.id),
                                            backup_for=backup)
    guide = step_guide.guide_dict(root, wf, sd, view, sv, day=day, readers=readers, roster=holders, who=who, name=person,
                                  run_id=run_id if definition else "", community=community, procedure=proc, backup_for=backup)
    if args.json:
        print(_dump({"definition": wf.key, "run": run_id if definition else "", "step": sd.id, "n": position, "title": sd.title,
                     "enable": enable, "nudge": nud, "guide": guide}))
        return 0
    lines = step_guide.text_lines(sd.title, position, len(wf.steps), guide, enable, nud)
    if who is None and view is not None:
        lines.insert(1, "  (name a person with --for NAME to see whether they can act on it now)")
    print("\n".join(lines))
    return 0


def _due(args: argparse.Namespace, root: Any, today: date | None, readers: Any) -> int:
    """``--due --for NAME``: the lines for a person (``jason.tasks.step_guide.due_report``). Reads only."""
    from jason.tasks import step_guide

    person = (getattr(args, "for_person", "") or getattr(args, "by", "") or "").strip()
    if not person:
        return _refuse("--due is for a person: give --for NAME (their offices come from the roster)")
    report = step_guide.due_report(root, today or date.today(), person=person, holders=_holders(), readers=readers,
                                   within=args.within, everything=bool(args.all_steps))
    print(_dump(report) if args.json else "\n".join(step_guide.due_lines(report)))
    return 0


def _one_item(args: argparse.Namespace, act: str) -> str:
    items = args.item or []
    if act in ("start", "supply") or not items:
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
    p.add_argument("--na", nargs=2, metavar=("RUN", "STEP"),
                   help="record a step as not applicable, which is not a skip (with --reason, --record, --by); only a step "
                        "whose definition declares the outcome")
    p.add_argument("--set-date", dest="set_date", nargs=2, metavar=("RUN", "SLOT=YYYY-MM-DD"),
                   help="give a late or optional date slot a day after the start (with --record, --by; a correction also "
                        "--reason)")
    p.add_argument("--supply", metavar="RUN",
                   help="give an item set more items while the run goes (with --set, --item, --by; --item-date and --record for an "
                        "item's own dates). An item is an opaque id, never a name or an address. Without --yes it checks and "
                        "prints what would be recorded and writes nothing")
    p.add_argument("--set", dest="item_set", default="", metavar="NAME",
                   help="with --supply: the item set (omit for the run's own items)")
    p.add_argument("--item-date", dest="item_date", action="append", nargs=2, metavar=("ITEM", "SLOT=YYYY-MM-DD"),
                   help="with --supply: the day a date slot reads for this item's own clocks (needs --record; repeat)")
    p.add_argument("--guide", metavar="RUN[:STEP]",
                   help="print a person step's guide as plain text: do this, look at, the rule, the checklist, the command, done when, "
                        "if blocked, if it does not apply, ask, learn more (RUN:STEP, a run alone for its current step, or "
                        "DEFINITION.STEP for the definition's words; with --for NAME for whether they can act now). Reads only")
    p.add_argument("--due", action="store_true",
                   help="list the person steps due, late, or open a while for --for NAME, and what is escalated to their office. "
                        "Reads only; nothing is sent")
    p.add_argument("--for", dest="for_person", metavar="NAME", help="with --due or --guide: the person (their offices come from the roster)")
    p.add_argument("--within", type=int, metavar="DAYS", help="with --due: keep a due-soon or open line only if its date is within this many days")
    p.add_argument("--all", dest="all_steps", action="store_true", help="with --due: also the person's open steps that are quiet")
    p.add_argument("--claim", nargs=2, metavar=("RUN", "STEP"),
                   help="say you are on a step (with --by, --yes): a note on the step, not an assignment; without --yes it checks and "
                        "writes nothing")
    p.add_argument("--release", action="store_true", help="with --claim: let the step go (only the person who claimed it)")
    p.add_argument("--reopen", nargs=2, metavar=("RUN", "STEP"), help="open a done, skipped, or failed step again (with --reason, --by)")
    p.add_argument("--pause", metavar="RUN", help="pause a run (with --reason, --by)")
    p.add_argument("--resume", metavar="RUN", help="lift a pause (with --by)")
    p.add_argument("--note", metavar="RUN", help="add a note to a run (with --text, --by; --step for one step)")
    p.add_argument("--cancel", metavar="RUN", help="cancel a run, which stays listed (with --reason, --by, --yes)")
    p.add_argument("--verify", metavar="RUN", help="check a run's hash chain and name the first broken event")
    p.add_argument("--reindex", action="store_true", help="rebuild data/workflows/index.json from the events")
    p.add_argument("--from-sop", dest="from_sop", metavar="KEY",
                   help="print a DRAFT definition from a procedure (jason sop lists them); it is never registered")
    p.add_argument("--record", metavar="REF", help="with --attest, --na, --set-date, or --supply: the record that shows it (minutes, a sent "
                                                   "notice, a library id)")
    p.add_argument("--what", metavar="TEXT", help="with --attest or --arrived: what was done, in a few words")
    p.add_argument("--outcome", metavar="WORD", help="with --attest on a decision step: adopted, approved, denied, rejected, "
                                                     "withdrawn, tabled, or pending (only a final one finishes the step)")
    p.add_argument("--motion", metavar="TEXT", help="with --attest on a decision step: the motion (default: the step's title)")
    p.add_argument("--choice", metavar="KEY", help="with --attest on a branch step a person answers")
    p.add_argument("--item", action="append", metavar="ITEM", help="with --start: an item of the run (repeat); with --supply: an item id to "
                                                                   "add (repeat); with an act on a per-item step: the item")
    p.add_argument("--step", metavar="STEP", help="with --note: the step it is about")
    p.add_argument("--reason", metavar="TEXT", help="why: a skip, a not-applicable record, a pause, a reopen, a cancel, or a "
                                                    "date correction")
    p.add_argument("--text", metavar="TEXT", help="with --note: the note")
    p.add_argument("--expect", type=int, metavar="N", help="the run's n you last saw; a run that moved on is refused")
    p.add_argument("--as-of", dest="as_of", metavar="YYYY-MM-DD", help="read the clocks as of this day (default: today)")
    p.add_argument("--by", default="", metavar="NAME", help="who is acting (required for every write; kept with when)")
    p.add_argument("--yes", action="store_true", help="confirm: --cancel and --supply always; --start and --open of a run with a legal clock")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.set_defaults(func=cmd_workflow)


__all__ = ["Roster", "cmd_workflow", "draft_definition", "register", "show_lines"]
