"""The requests area's loaders (docs/console/handoff-forms-and-arrivals.md, handoff-form-library.md, handoff-followups.md,
handoff-responses.md): who has answered, who has not, what is due, how a campaign is going, and the form library.
All read only, over what the MCP tools read (``jason.mcp.response_inbox``, ``jason.mcp.followups``) and the form library
(``jason.community.form_library``), so the console and a terminal show the same numbers.

- ``GET /api/responses`` (``?state=&channel=&unit=&request=&days=``): the arrivals the last ``jason responses --check``
  kept, with the channels' last checks.
- ``GET /api/response?id=gmail:ID``: one arrival, with its reading, the answers a person confirmed, its acts, and what is
  left. The reading, the keyed answers, and the acts are an owner's own words, so they open only where the viewer may see
  the owner's private material (P3: the private view, for the offices that open it); otherwise the arrival comes without
  them and says why. Each such opening is logged (``access/served.jsonl``), never its contents.
- ``GET /api/outstanding-responses`` (``?request=``): who was sent a copy and has no answer, by owner and unit, whichever
  way anyone answered.
- ``GET /api/campaign-status`` (``?code=``): a campaign's funnel by channel, who is outstanding, who is unreachable.
- ``GET /api/followups`` (``?days=&campaign=&kind=&state=``): the dated actions, each with its basis and its state.
- ``GET /api/form-library`` (``?tier=``): the forms the profile offers, each with its status and findings.

A signed-in person whose office opens the owners' names and units (P2) reads these; anyone else is refused with the
sentence ``access.may_see`` gives, and the owner view never reads them (``OWNER_SOURCES`` does not list them). Nothing is
sent, written, resent, or completed: a follow-up is done by a person at a terminal, and a reading is evidence, never an
answer until a person confirms it.
"""

from __future__ import annotations

from typing import Any

Args = dict[str, str]

HELD = ("The reading, the answers a person confirmed, and the acts on an arrival are the owner's own words. They open "
        "in the private view, for the offices that open owners' private material.")


def _need(level_name: str = "P2") -> Any:
    """The signed-in viewer, or abort: 401 with no sign-in, 403 where the offices do not open the level."""
    from flask import abort

    from jason.web import access

    viewer = access.signed_in()
    ok, why = access.may_see(viewer, access.Level[level_name])
    if not ok:
        abort(access.refusal(403, why))
    return viewer


def _int(args: Args, name: str, default: int) -> int:
    try:
        return max(0, int(args.get(name) or default))
    except ValueError:
        return default


def responses(args: Args) -> dict[str, Any]:
    from jason.mcp.response_inbox import new_responses

    _need()
    return new_responses(request=args.get("request", ""), channel=args.get("channel", ""), unit=args.get("unit", ""),
                         state=args.get("state") or "new", days=_int(args, "days", 0))


def response(args: Args) -> dict[str, Any]:
    from jason.mcp.response_inbox import response as tool
    from jason.web import access

    viewer = _need()
    out = tool(args.get("id", ""))
    if not out.get("found"):
        return out
    window = access.private_window()
    ok, _ = access.may_see(viewer, access.Level.P3, private=window is not None)
    if ok:
        try:
            access.served(viewer, access.Level.P3, address=f"api/response/{out['arrival'].get('id', '')}")
        except OSError:
            ok = False                     # an opening that cannot be logged is not served
    if ok:
        return {**out, "held": False}
    return {**out, "reading": None, "keyed": None, "acts": [], "held": True, "heldWhy": HELD}


def outstanding(args: Args) -> dict[str, Any]:
    from jason.mcp.response_inbox import outstanding_responses

    _need()
    return outstanding_responses(request=args.get("request", ""))


def campaign(args: Args) -> dict[str, Any]:
    from jason.mcp.followups import campaign_status

    _need()
    return campaign_status(code=args.get("code", ""))


def followups(args: Args) -> dict[str, Any]:
    from jason.mcp.followups import followups as tool

    _need()
    return tool(days=_int(args, "days", 30), campaign=args.get("campaign", ""), kind=args.get("kind", ""),
                state=args.get("state", ""))


def form_library(args: Args) -> dict[str, Any]:
    """The library as ``jason form-library --json`` prints it, with the seven checks' findings per form."""
    from jason.commands.form_library import form_json
    from jason.community import community
    from jason.community.form_library import Tier
    from jason.community.form_library.check import check
    from jason.community.form_library.resolve import resolve
    from jason.mcp.county import _data_dir

    _need()
    tier = (args.get("tier") or "").strip().lower()
    if tier and tier not in {t.value for t in Tier}:
        raise ValueError(f"no tier {tier!r}; the tiers are {', '.join(t.value for t in Tier)}")
    c = community()
    resolved = resolve(c)
    report = check(resolved, _data_dir(None), community=c)
    forms = [f for f in resolved.forms if not tier or f.tier.value == tier]
    return {"found": True, "chain": list(resolved.chain), "forms": [form_json(f, report) for f in forms],
            "problems": [p.as_dict() for p in resolved.problems]}


__all__ = ["campaign", "followups", "form_library", "outstanding", "response", "responses"]
