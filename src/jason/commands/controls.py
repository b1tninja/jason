"""``jason controls``: the safeguards a board opts into, and the ones jason suggests (docs/controls.md).

- ``--list [--family F] [--state S] [--json]``: every control, by family, with its state in words; read.
- ``--show KEY [--json]``: one control from the provision to its history: the provision whole, the floor, jason's reading
  (labeled as jason's), what it changes, the roster check, and the history; read.
- ``--roster-check KEY``: what the control needs, what is seated, and what is missing, by office and count (no names); read.
- ``--suggest [--document KEY ...] [--duties-read] [--record --by NAME] [--json]``: read the governing documents' sections
  as stored and print the controls they suggest, each with the provision's words whole, the floor (read only where one count
  is certain), jason's proposal and its reading; a weak match is a question, not a suggestion. It runs only once the duties
  are read (``Community.duties_read()``, or ``--duties-read`` from a person who has read and confirmed them). ``--record
  --by NAME`` appends the suggestions to the act log as suggested acts by jason; it adopts nothing.
- ``--propose KEY --by NAME``: put a suggested control before the board: a board item with the provision as its evidence, and
  the control becomes proposed. That is all a person may do with a suggestion here.

- ``--adopt KEY``, ``--decline KEY``, ``--defer KEY`` (each with ``--by NAME --meeting DATE --decision ID --reason TEXT``;
  ``--adopt`` also ``--effective DATE`` and, to adopt it with values, ``--param NAME=VALUE``; ``--decline`` and ``--defer``
  may say ``--again-on DATE``): record what the board decided at a meeting, on a control that is proposed. The secretary
  records it (``--by`` holds the secretary's office on the roster), and the decision is a person's, stated here with its
  meeting; jason decides nothing. Only adds: an adoption below a floor is refused. Without ``--yes`` it prints what would be
  recorded and writes nothing. It appends one act to the act log (``jason.controls.store.record``); a control is in force
  only from the effective date the board names, and only when the roster can satisfy it.

- ``--offer TYPE [--scope all|kind:KEY|family:SYSTEM] --by NAME``: record an apply preference (``where-apply``,
  ``who-may-apply``, ``pause-before-apply``, ``typed-count-over``, ``reminder-hours``) as a suggestion, so it can be proposed to
  the board and adopted like any control (``--param`` carries its value). Preferences are opt-in; the defaults hold until one is
  adopted; none lowers a signature count, removes a control, or lets the console apply a kind that is terminal-only, costs money,
  or sends mail or email (``jason.controls.apply_prefs``). There is no automatic apply.

This command never retires a control, and never decides one. A write needs ``--by``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from typing import Any, Callable

DECIDES = ("adopt", "decline", "defer")
WRITES = ("propose", "offer", *DECIDES)
ACTS = ("list", "show", "roster_check", "suggest", "propose", "offer", *DECIDES)


def _refuse(reason: str) -> int:
    print(f"jason controls: {reason}", file=sys.stderr)
    return 2


def _print_json(body: Any) -> None:
    from jason.commands._shared import to_json

    print(to_json(body))


def _day(args: argparse.Namespace) -> date | None:
    from jason.commands._shared import day

    return day(getattr(args, "as_of", None))


def cmd_controls(args: argparse.Namespace) -> int:
    from jason.commands._shared import data_dir
    from jason.community import community
    from jason.controls.types import ControlRefused

    chosen = [a for a in ACTS if getattr(args, a, None)]
    if len(chosen) > 1:
        return _refuse("one act at a time")
    act = chosen[0] if chosen else "list"
    if act in WRITES and not (args.by or "").strip():
        return _refuse(f"--{act.replace('_', '-')} names the person who asks for it: add --by NAME")
    if getattr(args, "record", False) and act != "suggest":
        return _refuse("--record goes with --suggest")
    if act not in DECIDES:
        stray = [f"--{n}" for n in ("meeting", "decision", "reason", "effective", "again_on", "param", "yes")
                 if getattr(args, n, None)]
        if act != "offer" and getattr(args, "scope", None):
            stray.append("--scope")
        if stray:
            return _refuse(f"{', '.join(s.replace('_', '-') for s in stray)} goes with --adopt, --decline, or --defer")
    root = data_dir(args)
    try:
        home = community()
        if act == "list":
            return _list(args, home, root)
        if act == "show":
            return _show(args, home, root)
        if act == "roster_check":
            return _roster(args, home, root)
        if act == "suggest":
            return _suggest(args, home, root)
        if act in DECIDES:
            return _decide(args, home, root, act)
        if act == "offer":
            return _offer(args, home, root)
        return _propose(args, home, root)
    except KeyError as exc:
        return _refuse(f"no control {exc.args[0] if exc.args else ''}".strip())
    except (ControlRefused, ValueError) as exc:
        return _refuse(str(exc))


# --- reads ---------------------------------------------------------------------------------------------------------------

def _list(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import view

    body = view.compose(home, root, family=args.family or "", state=args.state or "", today=_day(args))
    if args.json:
        _print_json(body)
        return 0
    print(f"{view.LABEL}. {body['counts']['total']} control(s): {body['heading']}.")
    if body["empty"]:
        print(body["empty"])
    for g in body["families"]:
        print(f"\n{g['title'].upper()}")
        for r in g["controls"]:
            cite = r["basis"]["citation"] or "no provision cited"
            print(f"  {r['key']}: {r['title']} [{r['stateWord']}] ({cite})")
            print(f"      {r['summary']}")
        for q in g["questions"]:
            print(f"  QUESTION {q['citation']}: {q['title']} (not a suggestion; {q['whyQuestion']})")
    return 0


def _show(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import view

    body = view.one(home, root, args.show, today=_day(args))
    if args.json:
        _print_json(body)
        return 0 if body["found"] else 2
    if not body["found"]:
        return _refuse(body["note"])
    c = body["control"]
    print(f"{c['title']} ({c['key']}): {c['stateWord']}")
    print(f"\n1 THE PROVISION: {c['basis']['citation'] or 'none cited'}")
    print(f'  "{c["basis"]["words"]}"' if c["basis"]["words"] else "  (cited, not quoted)")
    print("  " + (c["floor"]["note"] or f"The floor the provision sets: {c['floor']['provision']}"))
    if c["floor"]["catalog"]:
        print(f"  The catalog's floor: {c['floor']['catalog']}")
    if c["changed"]:
        print(f"  CHANGED since the control was recorded: now reads \"{c['changed']['now']}\"")
    if c["reading"]:
        print(f"\n2 WHAT JASON SUGGESTED\n  {c['reading']}")
    if c["decision"] or c["state"] in ("adopted", "declined", "deferred", "retired"):
        print(f"\n3 WHAT THE BOARD DECIDED\n  {c['summary']}; decision {(c['decision'] or {}).get('id', 'not named')}"
              + (f"; effective {c['effective']}" if c["effective"] else ""))
    print("\n4 WHAT IT CHANGES")
    for t in c["touches"]:
        print("  " + _touch(t))
    print(f"\n5 CAN THE ROSTER SATISFY IT\n  {_roster_line(c['roster'])}")
    print("\n6 HISTORY")
    for h in c["history"]:
        print(f"  {h['at'][:10]} {h['act']} by {h['by']}: {h['why']}" + (f" (decision {h['decision']})" if h.get("decision") else ""))
    return 0


def _touch(t: dict[str, Any]) -> str:
    if t.get("key"):
        return (f"{t['kind']} {t['key']}: the kind's own rule is {t['builtin']}; the control asks {t['with']}"
                + ("" if t["changes"] else " (unchanged)"))
    return f"{t['kind']} {t.get('what', '')}" + (f": {t['note']}" if t.get("note") else "")


def _roster_line(r: dict[str, Any]) -> str:
    if not r["read"]:
        return "the roster could not be read, so the check was not made"
    needs = "; ".join(f"{n['count']} {n['office']}" for n in r["needs"]) or "nothing named"
    seated = ", ".join(f"{s['count']} {s['office']}" for s in r["seated"]) or "no one"
    return f"needs {needs}. Seated: {seated}." + (f" Missing: {r['lacks']}." if r["lacks"] else " The roster can satisfy it.")


def _roster(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import view

    body = view.one(home, root, args.roster_check, today=_day(args))
    if not body["found"]:
        return _refuse(body["note"])
    check = body["control"]["roster"]
    if args.json:
        _print_json(check)
    else:
        print(_roster_line(check))
    return 0


# --- the reader ------------------------------------------------------------------------------------------------------------

def _suggest(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import suggest as reader

    confirmed = bool(getattr(args, "duties_read", False) or home.duties_read())
    documents = reader.ShelfDocuments(home, root, args.document or ())
    found = reader.suggest(home, documents, duties_read=confirmed, data_dir=root)
    recorded = None
    if args.record and not found.reason:
        if not (args.by or "").strip():
            return _refuse("--record names the person who asks for it: add --by NAME")
        recorded = reader.record(found, by=args.by, data_dir=root, community=home)
    if args.json:
        _print_json({"reason": found.reason, "known": found.known, "unread": found.unread, "ready": confirmed,
                     "suggestions": [s.as_dict() for s in found.suggested], "questions": [s.as_dict() for s in found.questions],
                     "recorded": list(recorded.recorded) if recorded else None})
        return 0
    if found.reason:
        print(f"jason suggests nothing: {found.reason}. Confirm them, then run this again (--duties-read, from a person "
              "who has read them).")
        return 0
    print(f"{len(found.suggested)} suggestion(s), {len(found.questions)} question(s) for the board or counsel"
          + (f"; {found.known} section(s) already have a control recorded from the same words" if found.known else "")
          + ". jason suggests; the board adopts. Nothing here is adopted.")
    for s in found.suggested:
        print(f"\nSUGGESTION {s.key or '(new)'}: {s.type.title} <- {s.basis.citation}"
              + (" [the provision's words changed since the control was recorded; the control stays as the board left it]"
                 if s.changed else ""))
        print(f'  The provision, whole: "{s.basis.words}"')
        print(f"  {s.floor_note}")
        print(f"  {s.reading}")
    for s in found.questions:
        print(f"\nQUESTION (not a suggestion): {s.type.title} <- {s.basis.citation}")
        print(f'  The provision, whole: "{s.basis.words}"')
        print(f"  {s.reading}")
    for line in found.unread:
        print(f"  not read: {line}")
    if recorded:
        print(f"\nRecorded {len(recorded.recorded)} suggested act(s) by jason at the request of {args.by}"
              + (f"; skipped {len(recorded.skipped)}" if recorded.skipped else "")
              + f"; kept {recorded.questions} question(s) and {recorded.changed} changed provision(s) for the screen.")
    else:
        print("\n--record --by NAME appends these to the act log as suggested acts. jason adopts nothing.")
    return 0


# --- the one write -----------------------------------------------------------------------------------------------------------

def _propose(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls.propose import propose

    out = propose(args.propose, by=args.by, data_dir=root, community=home)
    if args.json:
        _print_json(out)
        return 0
    print(f"{'Refreshed' if out['refreshed'] else 'Proposed'} {out['key']}: board item {out['item']}, "
          f"{out['board']['added']} added, {out['board']['updated']} refreshed; the control is {out['state']}, by {out['by']}. "
          "It is not adopted: the board decides at a meeting, and the secretary records the decision.")
    return 0


def _offer(args: argparse.Namespace, home: Any, root: Any) -> int:
    from jason.controls import apply_prefs

    made = apply_prefs.offer(args.offer, by=args.by, scope=apply_prefs.parse_scope(args.scope or "all"), data_dir=root,
                             community=home)
    print(f"Offered {made.key}: {made.type.title}, suggested by {args.by.strip()}. It adopts nothing: --propose {made.key} "
          f"--by NAME puts it before the board, and the secretary records the decision with --adopt {made.key} "
          "(--param NAME=VALUE for its value). Until then the default holds.")
    return 0


# --- the board's decision, recorded ----------------------------------------------------------------------------------------------

_AGAINST = {"adopt": frozenset({"denied", "tabled", "continued", "referred"}),
            "decline": frozenset({"approved", "tabled", "continued", "referred"})}
"""The outcomes of a recorded decision that contradict the act (a defer is the board not deciding, so none does)."""


def _parse_params(ctype: Any, items: list[str]) -> dict[str, Any]:
    """``--param NAME=VALUE`` as the value the record holds it. A whole number, true or false, a comma list of offices
    (``director,treasurer``; empty is any), or a choice. A name the type does not have is refused."""
    from jason.controls.types import ControlRefused, ParamKind

    out: dict[str, Any] = {}
    for item in items:
        name, eq, text = item.partition("=")
        name, text = name.strip(), text.strip()
        if not eq or not name:
            raise ControlRefused(f"--param is NAME=VALUE, not {item!r}")
        spec = ctype.spec(name)
        if spec.kind in (ParamKind.COUNT, ParamKind.CENTS, ParamKind.DAYS, ParamKind.CEILING):
            try:
                out[name] = int(text)
            except ValueError:
                raise ControlRefused(f"{name} is a whole number, not {text!r}") from None
        elif spec.kind is ParamKind.FLAG:
            if text.lower() not in ("true", "false"):
                raise ControlRefused(f"{name} is true or false, not {text!r}")
            out[name] = text.lower() == "true"
        elif spec.kind in (ParamKind.ELIGIBLE, ParamKind.REQUIRED):
            out[name] = [t.strip() for t in text.split(",") if t.strip()]
        else:
            out[name] = text
    return out


def _holds_secretary(home: Any, name: str) -> str:
    """"" when ``name`` holds the secretary's office on the roster, else why not. A roster that cannot be read refuses: the
    secretary records, and jason will not guess who that is."""
    from jason.community.base import OfficerRole

    try:
        roster = tuple(home.officers())
    except Exception:  # noqa: BLE001 - an unreadable roster names no one
        roster = ()
    if not roster:
        return "the roster could not be read, so jason cannot tell who the secretary is"
    who = name.strip().casefold()
    mine = [o for o in roster if str(o.name).strip().casefold() == who]
    if not mine:
        return f"{name} is not on the roster: the secretary records the board's decision"
    if not any(o.role is OfficerRole.SECRETARY for o in mine):
        return f"{name} does not hold the secretary's office: the secretary records the board's decision"
    return ""


def _check_decision(act: str, decision: str, meeting: str, root: Any) -> str:
    """What the decisions store says of ``decision``, as one phrase for the printout. A recorded decision that contradicts
    the act (an adoption of a motion recorded denied) or names another meeting is refused; one not recorded yet is said so."""
    from jason.controls.types import ControlRefused
    from jason.tasks import decisions

    if not decision:
        return "no decision id named"
    try:
        found = next((d for d in decisions.load(root) if d.id == decision), None)
    except Exception as exc:  # noqa: BLE001 - a store that cannot be read is said, not guessed at
        return f"the decisions store could not be read ({exc}); not checked"
    if found is None:
        return ("not in Decisions yet: the secretary records the decision there, or the control-adoption run's outcome check "
                "stays open")
    if found.meeting != meeting:
        raise ControlRefused(f"decision {decision} was recorded for the meeting of {found.meeting}, not {meeting}")
    said = (found.outcome or "").lower()
    if said in _AGAINST.get(act, frozenset()):
        raise ControlRefused(f"decision {decision} is recorded as {said}: it cannot be the board's decision to {act}")
    return f"in Decisions, recorded as {said or 'open'}"


def _decide(args: argparse.Namespace, home: Any, root: Any, act: str) -> int:
    from jason.controls import store
    from jason.controls.types import (ControlAct, ControlRefused, parameters_to_dict)

    key = getattr(args, act)
    by = (args.by or "").strip()
    meeting = (args.meeting or "").strip()
    decision = (args.decision or "").strip()
    reason = (args.reason or "").strip()
    effective = (args.effective or "").strip()
    again_on = (args.again_on or "").strip()
    params = args.param or []
    flag = f"--{act}"
    lack = _holds_secretary(home, by)
    if lack:
        return _refuse(f"{flag}: {lack}")
    if not meeting:
        return _refuse(f"{flag} records what the board decided at a meeting: add --meeting DATE (YYYY-MM-DD)")
    try:
        date.fromisoformat(meeting)
    except ValueError:
        return _refuse(f"--meeting is the meeting's date, YYYY-MM-DD, not {meeting!r}")
    if act in ("adopt", "decline") and not decision:
        return _refuse(f"{flag} names the decision the secretary recorded in Decisions: add --decision ID")
    if act != "adopt" and (effective or params):
        return _refuse(f"{flag}: --effective and --param go with --adopt")
    if act == "adopt":
        if not effective:
            return _refuse("--adopt names the date the control takes effect, which the board sets: add --effective DATE")
        try:
            date.fromisoformat(effective)
        except ValueError:
            return _refuse(f"--effective is YYYY-MM-DD, not {effective!r}")
        if again_on:
            return _refuse("--again-on goes with --decline or --defer")
    elif again_on:
        try:
            date.fromisoformat(again_on)
        except ValueError:
            return _refuse(f"--again-on is YYYY-MM-DD, not {again_on!r}")
    if act in ("decline", "defer") and not reason:
        return _refuse(f"{flag} says why: add --reason TEXT (the board's reason, as stated at the meeting)")

    current = store.get(key, root, "", home)                    # KeyError: no control (said by the caller)
    parameters = _parse_params(current.type, params) if params else None
    why = f"board decision at the meeting of {meeting}" + (f": {reason}" if reason else "")
    now = datetime.now(timezone.utc)
    row: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "key": key, "act": ControlAct(act).value, "by": by,
                           "why": why}
    for name, value in (("decision", decision), ("effective", effective), ("againOn", again_on)):
        if value:
            row[name] = value
    if parameters is not None:
        row["parameters"] = parameters_to_dict(current.type, parameters)
    try:
        after = store.apply_act(current, row)                    # pure: the same check the writer makes, so a dry run refuses too
    except ControlRefused as exc:
        raise ControlRefused(f"{flag} {key}: {exc}") from exc
    seen = _check_decision(act, decision, meeting, root)

    print(f"{'Recording' if args.yes else 'Would record (nothing is written without --yes)'}: the board's decision to {act} "
          f"{key} ({current.type.title})")
    print(f"  recorded by: {by} (secretary)")
    print(f"  the meeting: {meeting}; decision: {decision or 'none named'} ({seen})")
    if act == "adopt":
        print(f"  takes effect: {effective}")
        print("  as adopted: " + (_values(after) or "the control's own values (at the floor, nothing more)"))
    if again_on:
        print(f"  may be asked again on: {again_on}")
    print(f"  why: {why}")
    print(f"  the control goes from {current.state.value} to {after.state.value}. jason records a decision a person states; "
          "it decides nothing.")
    if not args.yes:
        print("Nothing recorded. Add --yes to append this act to the act log.")
        return 0
    done = store.record(ControlAct(act), key, by=by, why=why, parameters=parameters, decision=decision,
                        effective=effective or None, again_on=again_on, data_dir=root, profile="", community=home, now=now)
    print(f"Recorded: {key} is {done.state.value}" + (f", effective {done.effective.isoformat()}" if done.effective else "")
          + ". It binds only from the effective date, and only while the roster can satisfy it.")
    return 0


def _values(control: Any) -> str:
    from jason.controls.types import parameters_to_dict

    return "; ".join(f"{k} = {', '.join(v) if isinstance(v, list) else v}"
                     for k, v in parameters_to_dict(control.type, control.parameters).items())


def _preference_keys() -> tuple[str, ...]:
    from jason.controls.catalog import PREFERENCES

    return tuple(t.key for t in PREFERENCES)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    from jason.controls.view import FAMILIES, STATES

    summary = ("The safeguards the board opts into, and the ones jason suggests from the governing documents: list, show, "
               "suggest (and record), put one before the board, and record what the board decided (--adopt, --decline, "
               "--defer, by the secretary, with the meeting and the decision). jason suggests; the board adopts. This only "
               "records a decision a person states; it decides nothing, lowers no floor, and retires nothing")
    p = sub.add_parser("controls", help=summary, description=summary)
    add_common(p)
    p.add_argument("--list", action="store_true", help="list the controls (the default)")
    p.add_argument("--family", choices=FAMILIES, help="with --list: one family")
    p.add_argument("--state", choices=STATES, help="with --list: one state")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--show", metavar="KEY", help="one control, from its provision to its history")
    p.add_argument("--roster-check", dest="roster_check", metavar="KEY",
                   help="what the control needs, what is seated, and what is missing, by office")
    p.add_argument("--suggest", action="store_true",
                   help="read the governing documents and print the controls they suggest (after the duties are read)")
    p.add_argument("--document", action="append", metavar="KEY", help="with --suggest: read only this document (repeatable)")
    p.add_argument("--duties-read", dest="duties_read", action="store_true",
                   help="with --suggest: a person confirms the documents' duties were read and are right")
    p.add_argument("--record", action="store_true",
                   help="with --suggest and --by: append the suggestions to the act log as suggested acts by jason")
    p.add_argument("--propose", metavar="KEY",
                   help="put a suggested control before the board as a board item (with --by); it adopts nothing")
    p.add_argument("--adopt", metavar="KEY",
                   help="record that the board adopted a proposed control (with --by the secretary, --meeting, --decision, "
                        "--effective); adds only, refuses one below a floor; without --yes it writes nothing")
    p.add_argument("--decline", metavar="KEY",
                   help="record that the board declined a proposed control (with --by, --meeting, --decision, --reason)")
    p.add_argument("--defer", metavar="KEY",
                   help="record that the board deferred a proposed control (with --by, --meeting, --reason)")
    p.add_argument("--offer", metavar="TYPE", choices=_preference_keys(),
                   help="record an apply preference as a suggestion (with --by, and --scope); it adopts nothing")
    p.add_argument("--scope", metavar="SCOPE", help="with --offer: all (default), kind:KEY, or family:SYSTEM")
    p.add_argument("--meeting", metavar="DATE", help="with --adopt, --decline, --defer: the meeting's date (YYYY-MM-DD)")
    p.add_argument("--decision", metavar="ID", help="with --adopt, --decline, --defer: the id of the decision in Decisions")
    p.add_argument("--effective", metavar="DATE", help="with --adopt: the date the control takes effect (YYYY-MM-DD)")
    p.add_argument("--reason", metavar="TEXT", help="with --adopt, --decline, --defer: the board's reason as stated")
    p.add_argument("--again-on", dest="again_on", metavar="DATE",
                   help="with --decline or --defer: the date it may be asked again (YYYY-MM-DD)")
    p.add_argument("--param", action="append", metavar="NAME=VALUE",
                   help="with --adopt: a value as the board adopted it (repeatable; a list of offices is comma separated); "
                        "none below a floor")
    p.add_argument("--yes", action="store_true", help="with --adopt, --decline, --defer: write the act (default: print it only)")
    p.add_argument("--by", default="", metavar="NAME", help="who asks for the write (kept with when); the secretary for a decision")
    p.add_argument("--as-of", dest="as_of", metavar="DATE", help="read as of this day (YYYY-MM-DD); default today")
    p.set_defaults(func=cmd_controls)


__all__ = ["cmd_controls", "register"]
