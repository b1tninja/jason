"""``jason calendar``: the board's meetings, notice deadlines, hearings, and recurring deadlines on Google Calendar.

A dry run by default: it reads the calendar and prints what jason plans beside what is there. ``--yes`` creates the
missing events and patches the changed ones. Nothing is deleted, and an event jason did not make is never changed.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser("calendar", help="Put the board's meetings, hearings, and deadlines on Google Calendar (dry run unless --yes)")
    parser.add_argument("--calendar", default="primary", help="Calendar ID (default: primary)")
    parser.add_argument("--months", type=int, default=None, help="Months ahead to plan (default: the specification's)")
    parser.add_argument("--list-calendars", action="store_true", help="List the calendars the account sees and stop")
    parser.add_argument("--plan-only", action="store_true", help="Print the plan from disk without reading the calendar")
    parser.add_argument("--yes", action="store_true", help="Create the missing events and patch the changed ones")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    add_common(parser)

    def run(args: Any) -> int:
        from jason.google.calendar import GoogleCalendar
        from jason.tasks.board_calendar import plan, sync, sync_lines

        with agent_factory(args) as agent:
            data_dir = agent.settings.payhoa_catalog.parent
            planned = plan(data_dir, agent.community, months=args.months, today=date.today())
            if args.plan_only:
                rows = [e.row() for e in planned["events"]]
                if args.json:
                    print(json.dumps({"events": rows, "notes": planned["notes"]}, indent=2))
                else:
                    for e in rows:
                        print(f"{e['start'][:16].replace('T', ' ')}  {e['summary']}  [{e['key']}]")
                    for note in planned["notes"]:
                        print(f"* {note}")
                return 0
            interactive = bool(getattr(args, "interactive", False))
            calendar = GoogleCalendar.from_drive(agent.drive(interactive=interactive))
            with calendar:
                if args.list_calendars:
                    rows = [{k: c.get(k) for k in ("id", "summary", "accessRole", "primary", "timeZone")} for c in calendar.calendars()]
                    print(json.dumps(rows, indent=2) if args.json else "\n".join(
                        f"{r['id']}  {r['summary']}  ({r['accessRole']}{', primary' if r.get('primary') else ''})" for r in rows))
                    return 0
                result = sync(calendar, args.calendar, planned, write=args.yes)
            print(json.dumps(result, indent=2, default=str) if args.json else "\n".join(sync_lines(result)))
        return 0

    parser.set_defaults(func=run)
