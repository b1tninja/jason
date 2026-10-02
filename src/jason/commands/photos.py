"""``jason photos``: take in the photos of an album shared in an agenda, keep them in jason's album and in Drive.

``--pick URL`` opens a Picker session for a person and saves what they pick; ``--publish SLUG`` and ``--to-drive SLUG``
are dry runs unless ``--yes``; ``--status`` lists the imported albums.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Callable


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("photos", help="Photos picked from a shared album: save, keep in jason's album, copy to Drive")
    add_common(p)
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--pick", metavar="URL", help="album share or short link from an agenda; a person picks its photos")
    what.add_argument("--publish", metavar="SLUG", help="keep the picked photos in an album jason created")
    what.add_argument("--to-drive", metavar="SLUG", dest="to_drive", help="copy the picked photos into a Drive folder")
    what.add_argument("--status", action="store_true", help="each imported album, published and in Drive")
    what.add_argument("--login", action="store_true", help="consent to the Photos scopes (with --interactive)")
    p.add_argument("--timeout", type=float, default=1800.0, help="seconds to wait for the person to pick (default 1800)")
    p.add_argument("--drive-folder", default="", help="Drive folder id for --to-drive (until the spec names one)")
    p.add_argument("--yes", action="store_true", help="make the change; without it --publish and --to-drive are dry runs")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=lambda args: run(args, agent_factory))


def _print(result: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return
    for k, v in result.items():
        print(f"{k}: {v}")


def run(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.community import mystique
    from jason.config import Settings
    from jason.tasks import photos as task

    if args.status:
        data_dir = Settings.load(getattr(args, "env", None)).payhoa_catalog.parent
        rows = task.status(data_dir)
        print(json.dumps(rows, indent=2) if args.json else "\n".join(task.status_lines(rows)))
        return 0

    community = mystique()
    with agent_factory(args) as agent:
        data_dir = agent.settings.payhoa_catalog.parent
        if args.login:
            with agent.photos():
                print("Photos token ready")
            return 0
        if args.pick:
            with agent.photos() as photos:
                result = task.pick(photos, data_dir, community, args.pick, timeout=args.timeout)
        elif args.publish and not args.yes:
            result = task.publish(None, data_dir, args.publish, yes=False, community=community)
        elif args.publish:
            with agent.photos() as photos:
                result = task.publish(photos, data_dir, args.publish, yes=True, community=community)
        else:
            folder_id = args.drive_folder or task.drive_folder(community)
            if not folder_id:
                print("no Drive folder: pass --drive-folder ID (PHOTOS_DRIVE_FOLDER in mystique/photos.py is empty)")
                return 2
            drive = agent.drive(interactive=getattr(args, "interactive", False)) if args.yes else None
            result = task.to_drive(drive, data_dir, args.to_drive, folder_id, yes=args.yes, community=community)
    _print(result, args.json)
    if result.get("dryRun"):
        print("dry run; pass --yes to make the change")
    elif args.publish:
        print(task.SHARING_NOTE)
    return 0


__all__ = ["register", "run"]
