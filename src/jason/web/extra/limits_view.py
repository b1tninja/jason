"""The Limits screens' sources and write (docs/instance-limits.md, section 4 and phase 4).

- ``limits(args)`` is ``GET /api/limits``: the limits in force for **this community** (Setup > Limits), each row with its value in
  words, where it comes from, the allowed range and ceiling, the last change from the community's trail, why it exists, what
  happens when it is reached, whether the stored value was held to its range, and whether the signed-in person may change it. A
  signed-in officer, manager, or administrator reads it; an owner (the owner view, or no office) is refused, and nobody is
  refused to read it for not being an administrator.
- ``instance_limits(args)`` is ``GET /api/instance-limits``: the **instance layer** (Instance > Limits), each limit's instance value
  and ceiling, who set them and why, and the highest the code allows. One of jason's admins signed in as themselves
  (``status.require_admin``: 401 with no sign-in, 403 for anyone else and while an admin views as someone else). It reads
  the instance file and its own trail only: never a community's values or reasons.
- ``write(scope, body)`` is ``POST /api/write/limits/<instance|community>``, with ``by`` (the signed-in roster person; a different
  name is refused). ``{"act": "set", "changes": {KEY: "50MB"}, "ceiling": "", "reason": "...", "dryRun": true}`` or
  ``{"act": "reset", "keys": [KEY], "reason": "..."}``. **A dry run is the default**: nothing is written unless ``dryRun`` is
  ``false``. Each answer says what changes, what it affects, and who will be recorded (the person's name and role). Roles: the
  instance layer is the instance operator's (one of jason's admins as themselves); the community layer is the community
  administrator's (the roster's administrator), held to the operator's ceiling. An officer, a manager, an owner, and an admin viewing
  as someone else are refused (403). A refusal names the limit in words and the nearest allowed value (400). The write goes through
  ``jason.limits.set_limits`` / ``reset_limits``, which check the key, the layer's right, the bounds, the ceiling, and the role again.

No secret is read or returned; no file name, path, or owner is in a row. The trail's reasons are returned only to the layer that wrote
them: the community's own, to its signed-in people, and the instance's own, to the admin. Nothing here calls a network, a model, or a
provider.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

Args = dict[str, str]

KIND_ORDER = ("size", "count", "rate", "time", "concurrency", "switch", "cost")
GROUP_WORDS = {"size": "Size", "count": "Counts", "rate": "Rates", "time": "Time", "concurrency": "At once", "switch": "Switches",
               "cost": "Cost"}
SOURCE_WORDS = {"default": "built in", "env": "this machine's setting", "instance": "the operator", "community": "this community"}
CAVEATS = (
    "These are the limits in force. A limit is changed by a person, in this console or with `jason limits --set`, never by jason on its own.",
    "A limit applies to new acts. It never removes or hides what already exists.",
    "A limit can only make jason do less than the guards allow: the temp-drive guard and the machine's own checks still apply.",
)
CHANGE_ROLES = "Only the community's administrator changes a limit; officers and managers read this page."
NOT_YOURS = "Limits are for the board, the manager, and the administrator; the owner view does not show them."
ACTS = ("set", "reset")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _community() -> Any:
    from jason.community import community

    return community()


def _key_of(community: Any) -> str:
    slug = str(getattr(community, "slug", "") or "")
    if slug:
        return slug
    try:
        from jason.community.profile import profile_name

        return profile_name()
    except Exception:  # noqa: BLE001
        return ""


def _settings() -> Any:
    from jason.config import Settings

    try:
        return Settings.load()
    except Exception:  # noqa: BLE001 - no .env: the defaults, and nothing configured
        return None


def _abort(status: int, sentence: str) -> None:
    from flask import abort

    from jason.web import access

    abort(access.refusal(status, sentence))


def _last(rows: list[dict]) -> dict[str, Any]:
    """The newest ``set`` or ``reset`` line, shaped for a row; the trail's own words, never a path."""
    for r in reversed(rows):
        if r.get("kind") in ("set", "reset"):
            return {"kind": r["kind"], "at": r.get("at", ""), "by": r.get("by", ""), "reason": r.get("reason", ""),
                    "from": r.get("from"), "to": r.get("to"), "role": r.get("role", "")}
    return {}


def _units(l: Any, value: Any) -> str:
    return "" if value is None else l.format(value)


def _range_words(l: Any, minimum: Any, ceiling: Any) -> str:
    if l.unit == "switch":
        return "on or off" if ceiling else "off only (the operator or the code keeps it off)"
    return f"{l.format(minimum)} to {l.format(ceiling)}; built in {l.format(l.default)}"


def rows_for_community(community: Any, settings: Any, *, may_change: bool, trail: dict[str, list[dict]] | None = None) -> list[dict]:
    """One row for each limit: this community's effective value and everything the table shows. ``may_change`` is whether the
    signed-in person is the community's administrator."""
    from jason import limits

    out = []
    held = trail or {}
    for l in limits.all_limits():
        e = l.effective(settings, community)
        last = _last(held.get(l.key, []))
        why_not = ""
        if "community" not in l.scopes:
            why_not = "Only the code sets this." if "instance" not in l.scopes else "Only the operator sets this."
        elif not may_change:
            why_not = CHANGE_ROLES
        elif l.unit != "switch" and e.ceiling == l.minimum:
            why_not = "The operator's limit leaves no room: this is the lowest allowed."
        out.append({
            "key": l.key, "kind": l.kind, "unit": l.unit, "description": l.description, "value": e.value,
            "words": l.format(e.value), "source": e.source, "sourceWords": SOURCE_WORDS.get(e.source, e.source),
            "default": l.default, "defaultWords": l.format(l.default), "minimum": l.minimum, "maximum": l.maximum,
            "ceiling": e.ceiling, "ceilingWords": l.format(e.ceiling),
            "rangeWords": _range_words(l, l.minimum, e.ceiling), "direction": l.direction, "scopes": list(l.scopes),
            "clamped": e.clamped, "note": e.note, "unreadable": list(e.unreadable), "set": dict(e.set), "lastChange": last,
            "why": l.why, "whenHit": l.when_hit, "restart": l.restart, "override": l.override,
            "overrideMax": l.override_max, "overrideMaxWords": l.format(l.override_max) if l.override_max is not None else "",
            "editable": not why_not, "readOnlyWhy": why_not,
        })
    return out


def _grouped(rows: list[dict]) -> list[dict]:
    present = [k for k in KIND_ORDER if any(r["kind"] == k for r in rows)]
    return [{"kind": k, "name": GROUP_WORDS[k], "keys": [r["key"] for r in rows if r["kind"] == k],
             "open": any(r.get("source", "default") != "default" or r.get("clamped") or r.get("value") is not None and "top" in r
                         for r in rows if r["kind"] == k)} for k in present]


def _host_free(root: Any) -> dict[str, Any]:
    """The room on the drive jason keeps this community's files on, beside any size limit (reads only)."""
    from jason import storage

    free = storage.free_bytes(root) if root is not None else None
    return {"drive": storage.drive_of(root) if root is not None else "", "free": free,
            "freeWords": "" if free is None else (f"{free / storage.GB:.1f} GB" if free >= storage.GB else f"{free // 1024 ** 2} MB")}


def _data_root() -> Any:
    try:
        from jason.mcp.county import _data_dir

        return Path(_data_dir(None))
    except Exception:  # noqa: BLE001
        return None


def limits(args: Args) -> dict[str, Any]:
    """``GET /api/limits``: this community's limits, for a signed-in officer, manager, or administrator."""
    from jason import limits as lim
    from jason.web import access

    viewer = access.signed_in()
    if not (viewer.admin or viewer.offices):
        _abort(403, NOT_YOURS)
    community = _community()
    try:
        trail = {}
        for r in lim.read_log("community", community=community):
            trail.setdefault(r.get("key", ""), []).append(r)
    except Exception:  # noqa: BLE001 - no trail yet, or no community chosen: no last change
        trail = {}
    may = bool(viewer.admin and not viewer.acting)
    rows = rows_for_community(community, _settings(), may_change=may, trail=trail)
    return {"found": True, "asOf": _now(), "scope": "community", "community": _key_of(community), "canChange": may,
            "role": lim.ROLE_COMMUNITY if may else "", "limits": rows, "groups": _grouped(rows), "host": _host_free(_data_root()),
            "unreadable": sorted({u for r in rows for u in r["unreadable"]}), "caveats": list(CAVEATS)}


def instance_limits(args: Args) -> dict[str, Any]:
    """``GET /api/instance-limits``: the instance layer, for one of jason's admins as themselves."""
    from jason import limits as lim
    from jason.web.extra.status import require_admin

    require_admin()
    listing = {r["key"]: r for r in lim.instance_listing()}
    trail: dict[str, list[dict]] = {}
    for r in lim.read_log("instance"):
        trail.setdefault(r.get("key", ""), []).append(r)
    rows = []
    for l in lim.all_limits():
        r = listing[l.key]
        ceiling = r["ceiling"] if r["ceiling"] is not None else r["value"]
        rows.append({
            "key": l.key, "kind": l.kind, "unit": l.unit, "description": l.description, "default": l.default,
            "defaultWords": l.format(l.default), "minimum": l.minimum, "maximum": l.maximum, "top": l.top, "topWords": l.format(l.top),
            "value": r["value"], "words": _units(l, r["value"]),
            "ceiling": r["ceiling"], "ceilingWords": _units(l, r["ceiling"]),
            "communitiesMayGoUpTo": l.top if ceiling is None else ceiling,
            "rangeWords": _range_words(l, l.minimum, l.top),
            "set": {"by": r["by"], "at": r["at"], "reason": r["reason"]} if r["value"] is not None else {},
            "lastChange": _last(trail.get(l.key, [])), "file": r["file"], "scopes": list(l.scopes),
            "why": l.why, "whenHit": l.when_hit, "restart": l.restart,
            "editable": "instance" in l.scopes, "readOnlyWhy": "" if "instance" in l.scopes else "Only the code sets this.",
        })
    return {"found": True, "asOf": _now(), "scope": "instance", "path": str(lim.instance_file()), "canChange": True,
            "role": lim.ROLE_INSTANCE, "limits": rows, "groups": _grouped(rows), "host": _host_free(_data_root()),
            "caveats": list(CAVEATS) + ["This is the instance layer: a value and a ceiling for every community. A community's own "
                                        "values and reasons are not shown here."]}


# --- the write ---------------------------------------------------------------------------------------------------------------

def _viewer_for(scope: str) -> tuple[Any, str]:
    """The signed-in person and the role they act in for ``scope``, or abort: 401 with no sign-in; 403 while viewing as someone
    else and for anyone who is not the layer's administrator."""
    from jason import limits as lim
    from jason.web import access

    viewer = access.signed_in()
    if viewer.acting:
        _abort(403, f"Viewing as {viewer.label} (admin view): a limit is changed as yourself. Go back to yourself first.")
    if not viewer.admin:
        _abort(403, CHANGE_ROLES if scope == "community" else "Only one of jason's administrators, signed in as themselves, "
                                                              "changes the instance's limits.")
    return viewer, lim.ROLE_INSTANCE if scope == "instance" else lim.ROLE_COMMUNITY


def _who(viewer: Any) -> str:
    """The signed-in account's subject (a Google subject), else the account's name: what the access log records."""
    return str(getattr(viewer, "bind", "") or getattr(viewer, "account", "") or "")


def _by(viewer: Any, given: Any) -> str:
    name = " ".join(str(viewer.name or viewer.account or "").split())
    said = " ".join(str(given or "").split())
    if said and said.casefold() != name.casefold():
        raise ValueError(f"signed in as {name}: the change goes on the record under the signed-in name, not {said}")
    return name


def _changes(body: dict[str, Any]) -> dict[str, Any]:
    changes = body.get("changes")
    if isinstance(changes, dict) and changes:
        return {str(k): v for k, v in changes.items()}
    if body.get("limit") and "value" in body:
        return {str(body["limit"]): body["value"]}
    raise ValueError("a set names the limits and their values: {\"changes\": {\"upload.max_bytes\": \"50MB\"}}")


def write(scope: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/limits/<scope>``. See the module's description. A dry run unless ``dryRun`` is ``false``."""
    from jason import limits as lim

    if scope not in lim.SCOPES:
        raise KeyError(scope)
    act = str(body.get("act") or "").strip()
    if act not in ACTS:
        raise ValueError(f"act is one of {', '.join(ACTS)}")
    viewer, role = _viewer_for(scope)
    by = _by(viewer, body.get("by"))
    reason = " ".join(str(body.get("reason") or "").split())
    if not reason:
        raise ValueError("A reason is required: a limit is changed by a named person who says why. Do not put names in it; it is kept.")
    dry = body.get("dryRun") is not False
    community = _community() if scope == "community" else None
    kw = dict(scope=scope, reason=reason, by=by, via="console:google", who=_who(viewer), role=role, dry_run=dry,
              community=community, settings=_settings())
    try:
        if act == "set":
            out = lim.set_limits(_changes(body), ceiling=body.get("ceiling") or None, **kw)
        else:
            keys = body.get("keys") or ([body["limit"]] if body.get("limit") else [])
            if not keys or not all(isinstance(k, str) for k in keys):
                raise ValueError("a reset names the limits: {\"keys\": [\"upload.max_bytes\"]}")
            out = lim.reset_limits(list(keys), **kw)
    except lim.LimitRefused as exc:
        raise ValueError("Refused: " + exc.describe() + " Nothing was changed.") from exc
    except KeyError as exc:
        raise ValueError(str(exc.args[0] if exc.args else exc)) from exc
    out = {k: v for k, v in out.items() if k not in ("path", "log")}
    out.update({"ok": True, "act": act, "recordedAs": {"by": by, "role": role}, "scope": scope,
                "note": ("A dry run: nothing was written. Confirm to apply it." if dry else "Applied. The new value is in force from "
                                                                                          "the next job."),
                "caveats": list(CAVEATS)})
    return out


__all__ = ["CAVEATS", "instance_limits", "limits", "rows_for_community", "write"]
