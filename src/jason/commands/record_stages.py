"""``jason record-stages``: the revision histories of the rule changes and the minutes, read from disk.

For each rule change (the profile's rows and the specification's drafts): its versions (drafted, proposed with its
text's source, adopted, the notice of the adoption), the 28-day and 15-day clocks of Civil Code 4360 with the record
found for each, and the members' 30 days to ask for a reversal vote (4365). For each meeting: its minutes' copies on
file, the 30-day clock (4950(a)), the later meetings whose minutes approve them, and corrections. Executive-session
minutes show only that they exist and their date.

``--rules`` or ``--minutes`` shows one series (both by default); ``--since`` starts the minutes there (default the
start of last year); ``--meeting DATE`` or ``--change KEY`` shows one; ``--json`` prints the rows a tool would. It
reads disk only and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any, Callable


def _data_dir(args: argparse.Namespace):
    from jason.config import Settings

    return Settings.load(getattr(args, "env", None)).ownership_db.parent


def cmd_record_stages(args: argparse.Namespace) -> int:
    from jason.community import community
    from jason.tasks import record_stages as task

    try:
        on = date.fromisoformat(args.as_of) if args.as_of else date.today()
        since = date.fromisoformat(args.since) if args.since else date(on.year - 1, 1, 1)
        meeting = date.fromisoformat(args.meeting) if args.meeting else None
    except ValueError as exc:
        print(f"a date is YYYY-MM-DD: {exc}", file=sys.stderr)
        return 2
    c, data_dir = community(), _data_dir(args)
    rules = args.rules or not args.minutes or bool(args.change)
    minutes = (args.minutes or not args.rules or meeting is not None) and not args.change
    if meeting is not None:
        rules, since = False, meeting
    if args.json:
        result = task.histories(c, data_dir, since=since, on=on, rules=rules, minutes=minutes)
        if args.change:
            result["ruleChanges"] = [r for r in result.get("ruleChanges", []) if r["key"] == args.change]
        if meeting is not None:
            result["minutes"] = [m for m in result.get("minutes", []) if m["date"] == meeting.isoformat()]
        print(json.dumps(result, indent=1))
        return 0
    from jason.tasks.schedule_evidence import Stores

    stores = Stores(data_dir, c)
    result: dict[str, Any] = {"asOf": on.isoformat()}
    rule_rows = minute_rows = None
    if rules:
        rule_rows = task.rule_change_histories(c, data_dir, on=on, stores=stores)
        if args.change:
            rule_rows = [h for h in rule_rows if h.key == args.change]
            if not rule_rows:
                known = ", ".join(r.key for r, _, _ in task.records(c)) or "none"
                print(f"no rule change {args.change!r} (known: {known})", file=sys.stderr)
                return 2
        else:
            result["ruleChangeLeads"] = task.leads(c, data_dir, stores=stores)
    if minutes:
        minute_rows = task.minutes_histories(c, data_dir, since=since, on=on, stores=stores)
        if meeting is not None:
            minute_rows = [h for h in minute_rows if h.day == meeting]
            if not minute_rows:
                print(f"no meeting on record on {meeting}", file=sys.stderr)
                return 2
        else:
            result["minutesSummary"] = task.minutes_summary(minute_rows, since=since)
    print("\n".join(task.lines(result, rule_rows, minute_rows)))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("record-stages", help="Revision histories of the rule changes (Civil Code 4360) and the minutes "
                                             "(4950): each version, its stage, the clocks, and the record of each; "
                                             "reads disk only")
    add_common(p)
    p.add_argument("--rules", action="store_true", help="only the rule changes")
    p.add_argument("--minutes", action="store_true", help="only the minutes")
    p.add_argument("--change", metavar="KEY", help="one rule change by its key")
    p.add_argument("--meeting", metavar="DATE", help="one meeting's minutes (YYYY-MM-DD)")
    p.add_argument("--since", metavar="DATE", help="minutes of meetings from this day (default January 1 last year)")
    p.add_argument("--as-of", metavar="DATE", help="read this day as today (YYYY-MM-DD)")
    p.add_argument("--json", action="store_true", help="the rows a tool would show, as JSON")
    p.set_defaults(func=cmd_record_stages)
