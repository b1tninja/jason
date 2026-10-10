"""``jason use`` / ``jason which`` / ``jason communities``: which community this machine's commands serve (docs/tenancy.md).

- ``jason use``: the current community and where the choice came from. Needs no community to be chosen.
- ``jason use KEY``: save KEY as the current context: writes ``JASON_COMMUNITY=KEY`` to the user config
  (``~/.jason/.env``) and prints exactly what it wrote. A person's command; it refuses a profile this machine does not
  have. A choice nearer than the user config (``--community``, ``JASON_COMMUNITY``, ``JASON_PROFILE``, the project's
  .env) still wins, and it says so.
- ``jason use --list`` (also ``jason communities``): the installed profiles, the current one marked.
- ``jason which``: the same as ``jason use`` with no key.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable


def _current() -> tuple[object | None, str]:
    from jason.community.profile import CommunityNotChosen, resolve_community

    try:
        return resolve_community(), ""
    except CommunityNotChosen as exc:
        return None, str(exc)


def _show(args: argparse.Namespace) -> int:
    from jason.config import data_dir

    resolved, why = _current()
    if resolved is None:
        print(f"Error: {why}", file=sys.stderr)
        return 2
    print(f"community: {resolved.name} (from {resolved.source})")
    try:
        print(f"data: {data_dir(getattr(args, 'env', None))}")
    except Exception as exc:  # noqa: BLE001
        print(f"data: unknown ({exc})")
    return 0


def _list(args: argparse.Namespace) -> int:
    from jason.community.profile import installed_profiles

    resolved, _ = _current()
    current = resolved.name if resolved is not None else ""
    rows = installed_profiles()
    if not rows:
        print("no profile is installed")
        return 0
    for row in sorted(rows, key=lambda r: r["name"]):
        mark = "*" if row["name"] == current else " "
        print(f"{mark} {row['name']}  ({row['where']})")
    if resolved is None:
        print("no community is chosen: jason use KEY")
    return 0


def cmd_use(args: argparse.Namespace) -> int:
    from jason.community.profile import COMMUNITY_VAR, installed_profiles
    from jason.config import set_user_config_value, user_config_path

    if getattr(args, "list", False):
        return _list(args)
    key = (getattr(args, "key", "") or "").strip().lower()
    if not key:
        return _show(args)
    names = sorted(row["name"] for row in installed_profiles())
    if key not in names:
        print(f"Error: no profile {key!r} is installed here (installed: {', '.join(names) or 'none'})", file=sys.stderr)
        return 2
    path = set_user_config_value(COMMUNITY_VAR, key)
    print(f"wrote {COMMUNITY_VAR}={key} to {path}")
    resolved, _ = _current()
    if resolved is not None and resolved.name != key:
        print(f"note: {resolved.name} is still chosen, from {resolved.source}, which comes before the user config "
              f"({user_config_path()})", file=sys.stderr)
    return 0


def cmd_which(args: argparse.Namespace) -> int:
    return _show(args)


def cmd_communities(args: argparse.Namespace) -> int:
    return _list(args)


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("use", help="The community this machine's commands serve: show it and where it came from; "
                                   "`use KEY` saves it in the user config (JASON_COMMUNITY); `--list` the installed ones")
    add_common(p)
    p.add_argument("key", nargs="?", default="", help="the profile to make current (no key: show the current one)")
    p.add_argument("--list", action="store_true", help="the installed profiles, the current one marked")
    p.set_defaults(func=cmd_use)
    w = sub.add_parser("which", help="The community in use, where the choice came from, and its data folder")
    add_common(w)
    w.set_defaults(func=cmd_which)
    c = sub.add_parser("communities", help="The profiles installed on this machine, the current one marked")
    add_common(c)
    c.set_defaults(func=cmd_communities)


__all__ = ["cmd_communities", "cmd_use", "cmd_which", "register"]
