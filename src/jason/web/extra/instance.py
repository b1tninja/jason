"""The administrator's Instance screens (docs/console/handoff-instance-and-integrations.md): the service
(``GET /api/instance-service``), the integrations (``GET /api/instance-integrations``), and the schedules
(``GET /api/instance-schedules``). Read only.

Each answers only one of jason's admins, signed in as themselves (``status.require_admin``: 401 with no sign-in, 403 for
anyone else and while an admin views the console as someone else), and never the owner view (``OWNER_SOURCES`` does not
list them).

They read what ``jason serve status``, ``jason integrations list --json``, and ``jason cadence --json`` read, and
nothing more: heartbeat files and locks, the connections' stored rows and the stores' own stamps, and the schedules table
opened read-only. They call no Google, PayHOA, Keeper, or network, write nothing, and never seed a schedule (a community
whose scheduler has not run is "never seeded", with the command that seeds it).

**No secret is read or returned.** An integration row carries its vault *path* (a name) and whether a credential is set,
never a value. The vault is asked only with ``?vault=1``, by the administrator, and answers names only; without it a
credential held only in the vault reads "not set" from the ``.env`` test, and the row says the vault was not asked.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Args = dict[str, str]

SERVICE_COMMAND = "jason serve"
SEED_COMMAND = "jason cadence"
VAULT_NOT_ASKED = ("The vault was not asked: a credential held only in the vault reads \"not set\" here. Ask it with "
                   "the vault button, or `jason vault status` at a terminal.")
CAVEATS = (
    "Read from disk only: heartbeats, locks, the connections' stored rows, and the schedules table opened read-only. "
    "Nothing here calls Google, PayHOA, Keeper, or the network, and nothing here writes.",
    "No credential is read or shown, only its vault path and whether it is set. Credentials go in at a terminal "
    "(`jason integrations import`, `jason login`); a live check is a person's act at a terminal (`--live --by NAME`).",
    "A schedule runs only after a person adopts it, never faster than its floor, and never for a write.",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _profiles() -> dict[str, Path]:
    from jason import serve

    return {name: serve.profile_data_dir(name) for name in serve.profile_names()}


def _admin() -> None:
    from jason.web.extra.status import require_admin

    require_admin()


def service(args: Args) -> dict[str, Any]:
    """``GET /api/instance-service``: each community's heartbeat, judged (``none``, ``running``, ``draining``,
    ``stale``, ``stopped``), who holds its worker lock, a drain request, the lanes' current jobs, and the next runs."""
    from jason import serve

    _admin()
    rows = serve.status(_profiles())
    return {"found": any(r["state"] != "none" for r in rows), "asOf": _now(), "staleAfterSeconds": serve.STALE_AFTER,
            "beatSeconds": serve.BEAT_SECONDS, "command": SERVICE_COMMAND, "communities": rows, "caveats": list(CAVEATS)}


def integrations(args: Args) -> dict[str, Any]:
    """``GET /api/instance-integrations[?scope=instance][&vault=1]``: the integrations of the active community, or of
    the installation, as ``jason integrations list --json`` prints them."""
    from jason.commands.integrations import reading_json
    from jason.community import community
    from jason.community.profile import profile_name
    from jason.config import Settings, data_dir
    from jason.integrations.connections import INSTANCE, readings, store_path
    from jason.integrations.registry import Scope

    _admin()
    instance = (args.get("scope") or "").lower() == "instance"
    key = INSTANCE if instance else profile_name()
    scope = Scope.INSTANCE if instance else Scope.COMMUNITY
    try:
        settings = Settings.load()
    except Exception:  # noqa: BLE001 - no .env: the default paths, and nothing configured
        settings = None
    root = data_dir()
    vault = None
    asked = (args.get("vault") or "") in ("1", "true", "yes")
    if asked:
        from jason.vault.keeper import vault_names

        vault = vault_names(settings)
    rows = [reading_json(r) for r in readings(key, scope=scope, settings=settings, root=root,
                                              path=store_path(key), profile=community, vault=vault)]
    answered = bool(asked and vault is not None and vault.answered)
    return {"found": True, "asOf": _now(), "community": key, "scope": scope.value, "integrations": rows,
            "vault": {"asked": asked, "answered": answered,
                      "why": "" if answered else (vault.problem if asked else VAULT_NOT_ASKED)},
            "caveats": list(CAVEATS)}


def schedules(args: Args) -> dict[str, Any]:
    """``GET /api/instance-schedules``: every community's cadences in one list, each with its default, floor, window,
    where the setting came from, and its next run (``jason cadence --json``), read without seeding."""
    from zoneinfo import ZoneInfo

    from jason import scheduler as sc

    _admin()
    out = []
    for name, data_dir in _profiles().items():
        zone_name = sc.zone_of(name)
        rows = sc.read_schedules(data_dir)
        out.append({"community": name, "zone": zone_name, "seeded": rows is not None, "command": SEED_COMMAND,
                    "schedules": sc.listing(data_dir, zone=ZoneInfo(zone_name), rows=rows) if rows is not None else []})
    return {"found": any(c["seeded"] for c in out), "asOf": _now(), "communities": out, "caveats": list(CAVEATS)}


__all__ = ["CAVEATS", "integrations", "schedules", "service"]
