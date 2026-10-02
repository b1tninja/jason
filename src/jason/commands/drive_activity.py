"""``jason drive-activity``: read the Drive Activity record for files and folders (read-only)."""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    parser = sub.add_parser(
        "drive-activity",
        help="Who deleted, moved, renamed, or re-shared Drive items, from the Drive Activity API (read-only)",
        description="Reads Drive Activity for the agenda-linked Drive files missing from the association's Drive "
                    "listing (--missing), one file (--file), or everything under a folder (--folder). "
                    "Writes data/drive/activity-<name>.json. Never writes to Drive.",
    )
    add_common(parser)
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--missing", action="store_true",
                       help="agenda-linked Drive files and folders that are not in the association's Drive listing")
    which.add_argument("--file", metavar="ID", help="one Drive file id")
    which.add_argument("--folder", metavar="ID", help="a Drive folder id: activity on it and everything under it")
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="only activity on or after this date (UTC)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.set_defaults(func=lambda args: run(args, agent_factory))


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.config import Settings
    from jason.google.drive_activity import DriveActivityClient
    from jason.tasks.drive_activity import agenda_missing, file_report, folder_watch, summary_lines, write

    data_dir = Settings.load(args.env).payhoa_catalog.parent
    with agent_factory(args) as agent:
        client = DriveActivityClient.from_drive(agent.drive(interactive=getattr(args, "interactive", False)))
        if args.missing:
            report = agenda_missing(client, data_dir, since=args.since)
        elif args.file:
            report = file_report(client, args.file, since=args.since)
        else:
            report = folder_watch(client, args.folder, since=args.since)
    out = write(data_dir, report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(summary_lines(report)))
        print(f"wrote {out}")
    return 0


__all__ = ["register", "run"]
