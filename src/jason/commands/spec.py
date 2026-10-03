"""``jason spec``: where the active profile's private facts are read from, and ``--migrate`` to the per-profile layout.

Private facts are each profile's own (``jason.community.private``): ``data/spec/<profile>.json`` for onboarding's
answers and ``data/spec/<profile>/<topic>.json`` for each topic. With no flags, ``jason spec`` prints each topic of the
active profile and the file it is read from, by path only, never a value.

``--migrate`` copies the default profile's topic files kept at ``data/spec/<topic>.json`` into
``data/spec/<default profile>/``: a dry run listing each step by path, unless ``--yes``. With ``--yes`` every file to
copy is first copied into ``data/spec/backups/migrate-<stamp>/``. No source is moved, changed, or deleted, and a
different copy already in the profile's folder is held for a person to settle (``jason.tasks.spec_layout``).
"""

from __future__ import annotations

import argparse
from typing import Any, Callable


def cmd_spec(args: argparse.Namespace) -> int:
    from jason.community import private
    from jason.tasks import spec_layout as layout

    root = private.spec_dir()
    if args.migrate:
        steps = layout.plan(root)
        if not steps:
            print(f"Nothing to migrate: {root} holds no topic files.")
            return 0
        print(f"Private facts in {root}; the default profile's topics go to {root.name}/{private.default_profile()}/")
        for step in steps:
            print(f"  {step.line(root)}")
        copies = sum(1 for s in steps if s.action is layout.Action.COPY)
        if not args.yes:
            print(f"Dry run: {copies} to copy. Run again with --yes to copy them (a backup first; no source changes).")
            return 0
        backup = layout.apply(steps, root)
        if backup is None:
            print("Nothing copied.")
            return 0
        print(f"Copied {copies}; the sources are backed up in {backup}. The profile's folder is now read first; "
              f"remove the old files by hand once satisfied.")
        return 0
    who = private.profile_of()
    print(f"Private facts in {root} for the profile {who}")
    own = root / f"{who}.json"
    print(f"  own facts file: {own.name}" + ("" if own.is_file() else " (none yet)"))
    found = layout.where(who, root)
    if not found:
        print(f"  topics: none ({root.name}/{who}/ holds none)")
    for name, path in found:
        old = path.parent == root
        print(f"  {name}: {path.relative_to(root).as_posix()}" + (" (old layout: jason spec --migrate)" if old else ""))
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("spec", help="Where the active profile's private facts are read from; --migrate to the per-profile layout")
    add_common(p)
    p.add_argument("--migrate", action="store_true",
                   help="copy the default profile's topic files (data/spec/TOPIC.json) into data/spec/PROFILE/; a dry run "
                        "unless --yes")
    p.add_argument("--yes", action="store_true", help="with --migrate: copy, after a backup of each file copied")
    p.set_defaults(func=cmd_spec)
