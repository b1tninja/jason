"""The limits in force, read only (docs/instance-limits.md, section 5). One tool, ``limits``. It reads the registry and the files
on disk for the **server's community** (no argument names another), and it changes nothing: no tool here sets, resets, or proposes
a value as a setting, and a model that thinks a limit is too low says so in words and a person decides. It serves no secret, no
path, and no trail: not the reasons people gave, who changed a limit, nor any file name.
"""

from __future__ import annotations

from typing import Any

CAVEAT = ("These are the limits in force; they are changed by a person, in the console or with `jason limits --set`. This tool "
          "reads them and never changes one.")


def _community() -> Any:
    from jason.community import community

    return community()


def limits(key: str = "") -> dict[str, Any]:
    """The limits in force for this server's community: each limit's value in words, where it comes from (built in, this machine's
    setting, the operator, or this community), the allowed range and the highest this community may set, whether a stored value was
    held to its range, why the limit exists, and what happens when it is reached. ``key`` (for example ``upload.max_bytes``) narrows
    the answer to one limit. Reads disk only; it takes no community (the server was started for one) and it never changes a limit."""
    from jason import limits as lim
    from jason.config import Settings

    try:
        settings = Settings.load()
    except Exception:  # noqa: BLE001 - the limits read without a complete .env
        settings = None
    try:
        community = _community()
        wanted = key.strip()
        rows = []
        for l in lim.all_limits():
            if wanted and l.key != wanted:
                continue
            e = l.effective(settings, community)
            rows.append({"key": l.key, "unit": l.unit, "value": e.value, "words": l.format(e.value), "source": e.source,
                         "default": l.default, "defaultWords": l.format(l.default), "minimum": l.minimum, "maximum": l.maximum,
                         "ceiling": e.ceiling, "ceilingWords": l.format(e.ceiling), "clamped": e.clamped, "note": e.note,
                         "why": l.why, "whenHit": l.when_hit, "passOnce": bool(l.override),
                         "passOnceMax": l.override_max})
        if wanted and not rows:
            return {"found": False, "key": wanted, "limits": [l.key for l in lim.all_limits()], "caveats": [CAVEAT]}
        return {"found": True, "limits": rows, "caveats": [CAVEAT]}
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"found": False, "error": f"{type(exc).__name__}: {exc}", "caveats": [CAVEAT]}


TOOLS = (limits,)
