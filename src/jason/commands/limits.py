"""``jason limits``: the bounded numbers and switches jason runs on, with the value in force and where it came from (``jason.limits``).

Without a change flag it only reads: the table for the chosen community, one limit with every layer's value and the last lines of
its trail (``KEY``), the instance layer alone (``--scope instance``, which needs no community), or a trail (``--log``).

A change is a person's act, one layer at a time, and a dry run until ``--yes``:

    jason limits --set upload.max_bytes=50MB --scope community --reason "The disk is small" --by "A. Person"
    jason limits --set upload.max_bytes=50MB --ceiling 200MB --scope instance --reason ... --by ... --yes
    jason limits --reset upload.max_bytes --scope community --reason ... --by ... --yes

``--reason`` and ``--by`` are required with ``--set`` and ``--reset`` (stopped before anything is read, exit 2). A value is in the
unit's words (``50MB``, ``30m``, ``on``). More than one ``--set`` is one write with one reason. Exit 1 is a refused value, 2 a usage
error. The command needs no network, vault, or model. A job, a scheduled task, and the MCP server never call it.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable


def _words(r: dict[str, Any]) -> str:
    unit = "" if r["unit"] == "switch" else f" {r['unit']}"
    return f"{r['key']} = {r['value']}{unit}  [{r['source']}]{' (held to its range)' if r['clamped'] else ''}"


def _print_rows(rows: list[dict[str, Any]]) -> None:
    for r in rows:
        print(_words(r))
        rng = "" if r["minimum"] is None and r["maximum"] is None else f"; range {r['minimum']}-{r['maximum']} {r['unit']}"
        print(f"    default {r['default']}{rng}; set {r['env']}")
        print(f"    {r['description']}")
        if r["note"]:
            print(f"    note: {r['note']}")


def _split_pairs(items: list[str]) -> dict[str, str] | None:
    out: dict[str, str] = {}
    for item in items:
        key, eq, val = item.partition("=")
        if not eq or not key.strip():
            return None
        out[key.strip()] = val.strip()
    return out


def cmd_limits(args: argparse.Namespace) -> int:
    from jason import limits
    from jason.config import Settings

    sets = list(getattr(args, "set", None) or [])
    resets = list(getattr(args, "reset", None) or [])
    scope = getattr(args, "scope", "") or ""
    writing = bool(sets or resets)
    if writing:
        if scope not in limits.SCOPES:
            print("--set and --reset need --scope instance or --scope community", file=sys.stderr)
            return 2
        if not str(getattr(args, "reason", "") or "").strip() or not str(getattr(args, "by", "") or "").strip():
            print("--set and --reset need --reason and --by (a limit is changed by a named person, with a reason)", file=sys.stderr)
            return 2
        if sets and resets:
            print("--set and --reset are separate acts", file=sys.stderr)
            return 2
        pairs = _split_pairs(sets) if sets else {}
        if pairs is None:
            print("--set takes KEY=VALUE", file=sys.stderr)
            return 2
    elif scope and scope not in limits.SCOPES:
        print("--scope is instance or community", file=sys.stderr)
        return 2

    community = None
    if scope != "instance":
        try:
            from jason.community import community as active

            community = active()
        except Exception:  # noqa: BLE001 - no profile: the instance and the defaults (a write needs one)
            community = None

    if writing:
        yes = bool(getattr(args, "yes", False))
        try:
            if scope == "instance":
                print(f"instance: {limits.instance_file()}", file=sys.stderr)
            elif community is None:
                print("a community limit needs a community chosen (--community KEY)", file=sys.stderr)
                return 2
            elif not yes:
                from jason.tenancy import banner

                print(banner(), file=sys.stderr)
            common = dict(scope=scope, reason=args.reason, by=args.by, dry_run=not yes, community=community)
            if sets:
                out = limits.set_limits(pairs, ceiling=getattr(args, "ceiling", None), **common)
            else:
                out = limits.reset_limits(resets, **common)
        except limits.LimitRefused as exc:
            print(f"refused: {exc}" + (f" (nearest allowed: {exc.nearest})" if exc.nearest not in (None, "") else ""), file=sys.stderr)
            return 1
        except KeyError as exc:
            print(exc.args[0], file=sys.stderr)
            return 2
        if getattr(args, "json", False):
            print(json.dumps(out, indent=1, default=str))
            return 0
        print(("A dry run: nothing was written. Add --yes to apply." if out["dryRun"] else "Applied.") + f" ({out['scope']} layer: {out['path']})")
        for c in out["changes"]:
            print("  " + c["words"])
        print(f"  reason: {out['reason']}  by: {out['by']}  (recorded in {out['log']})")
        return 0

    if getattr(args, "log", False):
        if scope == "community" and community is None:
            print("a community trail needs a community chosen (--community KEY)", file=sys.stderr)
            return 2
        rows = limits.read_log("instance" if scope == "instance" else "community", key=args.key or "", community=community)
        if getattr(args, "json", False):
            print(json.dumps(rows, indent=1))
            return 0
        for r in rows:
            print(f"{r.get('at', '')}  {r.get('kind', '')}  {r.get('scope', '')}  {r.get('key', '')}: {r.get('from')} -> {r.get('to')}"
                  f"  by {r.get('by', '?')} via {r.get('via', '?')}: {r.get('reason', '')}")
        if not rows:
            print("no changes recorded")
        return 0

    if scope == "instance":
        rows = limits.instance_listing()
        if getattr(args, "json", False):
            print(json.dumps(rows, indent=1))
            return 0
        print(f"instance: {limits.instance_file()}")
        for r in rows:
            held = "not set" if r["value"] is None else f"{r['value']}" + (f" (ceiling {r['ceiling']})" if r["ceiling"] is not None else "")
            print(f"{r['key']}: {held}{'  [file unreadable]' if r['file'] == 'unreadable' else ''}"
                  f"{'  by ' + r['by'] if r['by'] else ''}")
        return 0

    try:
        settings = Settings.load()
    except Exception:  # noqa: BLE001 - the limits read without a complete .env
        settings = None
    rows = limits.listing(settings, community)
    if args.key:
        rows = [r for r in rows if r["key"] == args.key]
        if not rows:
            print(f"no limit {args.key}; the limits are {', '.join(l.key for l in limits.all_limits())}", file=sys.stderr)
            return 2
    if args.json:
        print(json.dumps(rows, indent=1))
        return 0
    _print_rows(rows)
    if args.key:
        r = rows[0]
        print(f"    why: {r['why']}")
        print(f"    when reached: {r['when_hit']}")
        print(f"    ceiling for this community: {r['ceiling']}; changes take effect: {r['restart']}")
        for t in limits.read_log("community", key=args.key, community=community, limit_lines=5) if community is not None else []:
            print(f"    {t.get('at', '')} {t.get('kind', '')} {t.get('from')} -> {t.get('to')} by {t.get('by', '?')}: {t.get('reason', '')}")
    return 0


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("limits", help="The bounded numbers jason runs on: the value in force and its source; --set/--reset change one "
                                      "(a dry run until --yes)")
    add_common(p)
    p.add_argument("key", nargs="?", help="one limit (none: all)")
    p.add_argument("--json", action="store_true", help="print JSON")
    p.add_argument("--scope", choices=("instance", "community"), default="",
                   help="the layer: with --set/--reset the layer changed; alone, instance prints the instance layer")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="set a limit in the layer (50MB, 30m, on); repeat for several, one write")
    p.add_argument("--ceiling", help="with one --set at the instance layer: the highest a community may set")
    p.add_argument("--reset", action="append", metavar="KEY", help="remove the layer's value so the layer above is in force")
    p.add_argument("--reason", help="why (required with --set/--reset; kept in the trail, so put no names in it)")
    p.add_argument("--by", help="who is changing it (a claim on a terminal; required with --set/--reset)")
    p.add_argument("--yes", action="store_true", help="apply the change (without it, a dry run)")
    p.add_argument("--log", action="store_true", help="print the layer's trail of changes")
    p.set_defaults(func=cmd_limits)
