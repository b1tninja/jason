"""``jason integrations``: each integration jason talks to and its connection's state (docs/integrations-design.md).

- ``list [--community C | --instance] [--json]``: each integration of the community (the active profile by default)
  or of the installation: its scope, state and why, account, where its credential goes in the vault and whether it is
  set, its capabilities on and off, its last check, and its sources' cadences with their last read. From disk only.
- ``check KEY [--community C] [--live] [--by NAME]``: the same reading for one integration; with ``--live``, a person
  at a terminal also runs its read through the service (``jason.integrations.checks``) and the outcome is recorded on
  the connection (``integrations.json``, under the store lock).

Never a credential's value: a credential is "set" or "not set", and a vault path names where it goes.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable

NO_VALUE = "From disk; a credential shows only as set or not set, never its value."


def at_terminal() -> bool:
    """Whether a person is at a terminal: stdin is a console. On Windows the NUL device also says it is a tty, so the
    console itself is asked (``GetConsoleMode`` answers only for a console)."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
        if sys.platform != "win32":
            return True
        import ctypes
        import msvcrt

        mode = ctypes.c_uint32()
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
        return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))
    except (AttributeError, OSError, ValueError):
        return False


def _settings(args: argparse.Namespace) -> Any:
    from jason.config import Settings

    try:
        return Settings.load(getattr(args, "env", None))
    except Exception:  # noqa: BLE001 - no .env: the default paths, and nothing configured
        return None


def _community_key(args: argparse.Namespace, *, instance: bool) -> str:
    """The community the command reads: the installation (``instance``), else ``--community`` or the active profile.
    Today the settings are the active profile's, so another community is read by making it the active one."""
    from jason.community.profile import profile_name
    from jason.integrations.connections import INSTANCE

    if instance:
        return INSTANCE
    active = profile_name()
    wanted = getattr(args, "community", None) or active
    if wanted != active:
        raise SystemExit(f"jason integrations: {wanted!r} is not the active profile ({active!r}); the settings are the "
                         f"active profile's, so run it with JASON_PROFILE={wanted}")
    return wanted


def _paths(args: argparse.Namespace, key: str):
    from jason.commands._shared import data_dir
    from jason.integrations.connections import store_path

    return data_dir(args), store_path(key, getattr(args, "env", None))


def _profile() -> Any:
    from jason.community import community

    return community


def _row(reading: Any) -> dict[str, Any]:
    """One integration's reading as JSON: no value, only names, states, and stamps."""
    integ, conn = reading.integration, reading.connection
    on = set(conn.capabilities or integ.default_capabilities())
    by_source = {r["key"]: r for r in reading.sources}
    over = {o.source_key: o for o in conn.overrides}
    return {
        "key": integ.key, "name": integ.name, "scope": integ.scope.value, "auth": integ.auth.value,
        "state": reading.state.value, "why": reading.why, "account": reading.account,
        "vaultPath": conn.vault_path, "credential": integ.credential,
        "credentialSet": reading.configured if integ.credential else None,
        "capabilities": [{"key": c.key, "label": c.label, "scopes": list(c.scopes), "writes": c.writes,
                          "on": c.key in on} for c in integ.capabilities],
        "rateLimit": {"published": integ.rate_limit.published, "source": integ.rate_limit.source,
                      "readOn": integ.rate_limit.read_on},
        "connectedBy": conn.connected_by, "connectedAt": conn.connected_at,
        "lastChecked": conn.last_checked, "lastCheck": conn.last_check, "check": integ.check,
        "cadences": [{"source": c.source_key, "command": "jason " + " ".join(c.argv), "cadence": c.words(),
                      "every": c.every, "cron": c.cron, "window": c.window, "outside": c.outside, "floor": c.floor,
                      "staleAfter": c.stale_after, "limit": c.limit, "note": c.note, "proposed": c.proposed,
                      "manual": c.manual,
                      "lastRead": (by_source.get(c.source_key) or {}).get("lastRead", ""),
                      "standing": (by_source.get(c.source_key) or {}).get("standing", ""),
                      "override": over[c.source_key].to_json() if c.source_key in over else None}
                     for c in integ.sources],
    }


def _lines(rows: list[dict[str, Any]], heading: str) -> list[str]:
    out = [heading, NO_VALUE, ""]
    for r in rows:
        out.append(f"{r['key']}  {r['name']}  [{r['state']}]")
        out.append(f"  {r['scope']}; {r['auth']}; {r['why']}")
        cred = "set" if r["credentialSet"] else "not set"
        where = f" (vault path {r['vaultPath']})" if r["vaultPath"] else ""
        out.append(f"  account: {r['account'] or '-'}   credential: {cred if r['credential'] else 'none needed'}{where}")
        on = [c["key"] + (" (writes)" if c["writes"] else "") for c in r["capabilities"] if c["on"]]
        off = [c["key"] + (" (writes)" if c["writes"] else "") for c in r["capabilities"] if not c["on"]]
        out.append(f"  capabilities on: {', '.join(on) or '-'}" + (f"; off: {', '.join(off)}" if off else ""))
        out.append(f"  last check: {r['lastChecked'] + ' ' + r['lastCheck'] if r['lastChecked'] else 'never'}")
        for c in r["cadences"]:
            read = f"last read {c['lastRead']}" if c["lastRead"] else "never read"
            standing = f", {c['standing']}" if c["standing"] and c["lastRead"] else ""
            out.append(f"  - {c['source']}: {c['command']}; {c['cadence']}; {read}{standing}")
            if c["override"]:
                o = c["override"]
                out.append(f"      changed by {o.get('by') or '?'} {o.get('at') or ''}: "
                           + (o.get("every") or o.get("cron") or ("paused" if o.get("paused") else "")))
        out.append("")
    return out


def cmd_list(args: argparse.Namespace) -> int:
    from jason.integrations.connections import readings
    from jason.integrations.registry import Scope

    instance = bool(args.instance)
    key = _community_key(args, instance=instance)
    root, path = _paths(args, key)
    scope = Scope.INSTANCE if instance else Scope.COMMUNITY
    rows = [_row(r) for r in readings(key, scope=scope, settings=_settings(args), root=root, path=path,
                                     profile=_profile())]
    if args.json:
        print(json.dumps({"community": key, "scope": scope.value, "integrations": rows}, indent=1))
    else:
        what = "the installation" if instance else key
        print("\n".join(_lines(rows, f"Integrations of {what} ({scope.value}):")).rstrip())
    return 0


def cmd_check(args: argparse.Namespace, agent_factory: Callable[[Any], Any]) -> int:
    from jason.integrations import checks
    from jason.integrations.connections import readings, record_check
    from jason.integrations.registry import Scope, integration

    try:
        integ = integration(args.key)
    except KeyError as exc:
        print(f"jason integrations: {exc.args[0]}", file=sys.stderr)
        return 2
    key = _community_key(args, instance=integ.scope is Scope.INSTANCE)
    root, path = _paths(args, key)
    settings = _settings(args)
    [reading] = [r for r in readings(key, scope=integ.scope, settings=settings, root=root, path=path,
                                     profile=_profile()) if r.integration.key == integ.key]
    row = _row(reading)
    if not args.live:
        print("\n".join(_lines([row], f"{integ.name} for {key}, from disk:")).rstrip())
        if integ.key in checks.LIVE:
            print(f"\nA live read ({integ.check}) runs with --live, by a person at a terminal.")
        return 0
    if integ.key not in checks.LIVE:
        print(f"jason integrations: {integ.key} has no live check yet; its stores' last reads above are the evidence.",
              file=sys.stderr)
        return 2
    if not at_terminal():
        print("jason integrations: a live check calls the service, so a person runs it at a terminal (stdin is not "
              "one).", file=sys.stderr)
        return 2
    if integ.key in checks.NEEDS_AGENT:
        with agent_factory(args) as agent:
            ok, words, state = checks.run_live(integ.key, agent)
    else:
        ok, words, state = checks.run_live(integ.key, None)
    conn = record_check(key, integ, ok=ok, words=words, state=state, path=path, by=args.by or "")
    print(f"{integ.name} for {key}: {'ok' if ok else 'failed'}: {words}")
    print(f"Recorded on the connection: {conn.state.value}, checked {conn.last_checked} ({path}).")
    return 0 if ok else 1


def register(sub: Any, add_common: Callable[[Any], None], agent_factory: Callable[[Any], Any]) -> None:
    p = sub.add_parser("integrations", help="Each service jason talks to: its connection's state, account, capabilities, "
                                            "last check, and cadences (never a credential's value)")
    nested = p.add_subparsers(dest="integrations_action", required=True)

    ls = nested.add_parser("list", help="each integration of the community, or of the installation, from disk")
    add_common(ls)
    who = ls.add_mutually_exclusive_group()
    who.add_argument("--community", metavar="C", help="the community (default the active profile)")
    who.add_argument("--instance", action="store_true", help="the installation's integrations")
    ls.add_argument("--json", action="store_true", help="print JSON")
    ls.set_defaults(func=cmd_list)

    ck = nested.add_parser("check", help="one integration's reading from disk; --live runs its read through the service")
    add_common(ck)
    ck.add_argument("key", help="the integration (jason integrations list names them)")
    ck.add_argument("--community", metavar="C", help="the community (default the active profile)")
    ck.add_argument("--live", action="store_true",
                    help="also read through the service (a person at a terminal); the outcome is recorded")
    ck.add_argument("--by", default="", metavar="NAME", help="with --live: who ran it, recorded on a first connection")
    ck.set_defaults(func=lambda args: cmd_check(args, agent_factory), instance=False)
