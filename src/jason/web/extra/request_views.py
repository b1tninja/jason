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

**A director sees counts only** (the board's decision of 2026-10-10), decided here on the server by
``access.counts_only(viewer)``: a viewer whose only office is director, or an admin viewing the console as one. Each
loader then returns the counts, states, ages, and dates, and never an owner's name or unit: ``responses`` the inbox's
counts by state and by channel with no arrival; ``response`` is refused; ``outstanding-responses`` and ``campaign-status``
the funnel's counts with no owner list; ``followups`` each item with its count and no ``names``, its wording made generic
where it would name an owner, and a unit taken out of a resend command. Every such response carries ``countsOnly`` and
``countsOnlyWhy``, and a last scrub (``OWNER_KEYS``) drops any owner key that shaping missed. Every other office sees what
it saw before.
"""

from __future__ import annotations

import re
from typing import Any

Args = dict[str, str]

HELD = ("The reading, the answers a person confirmed, and the acts on an arrival are the owner's own words. They open "
        "in the private view, for the offices that open owners' private material.")
COUNTS_ONLY_WHY = "A director sees counts and states; names and units open to the offices that act on them."
REFUSED_ARRIVAL = ("A director's view of requests is counts only, so one arrival (its sender, unit, and attachments) opens "
                   "to the offices that act on it: ask the president, the secretary, the treasurer, or the manager.")
# Keys that name an owner or a unit, as the tools spell them. A counts-only response never carries one; counts are named
# differently (``notResponded``, ``outstandingCount``, ``neverAskedCount``, ``unreachable.count``).
OWNER_KEYS = frozenset({"names", "owners", "who", "owner", "name", "unit", "units", "summary", "attachments",
                        "unreachableOwners", "answeredCopies", "membershipId", "sentToUnit", "sentToOwner", "readUnit"})
# Keys that are a list of owners in one tool's output and a count in another's (``outstanding``, ``neverAsked``): dropped
# only where they are a list.
OWNER_LISTS = frozenset({"neverAsked", "outstanding"})
_ONLY = re.compile(r'\s*--only "[^"]*"')
_CLOCK = re.compile(r"^([^:]+): .*?'s request, (.*)$")


def counts_scrub(value: Any) -> Any:
    """``value`` without any key in ``OWNER_KEYS``, and without a list under a key in ``OWNER_LISTS``, at any depth: the
    last guard behind a counts-only response, so a field a tool adds later is dropped, not shown."""
    if isinstance(value, dict):
        return {k: counts_scrub(v) for k, v in value.items()
                if k not in OWNER_KEYS and not (k in OWNER_LISTS and isinstance(v, (list, tuple)))}
    if isinstance(value, (list, tuple)):
        return [counts_scrub(v) for v in value]
    return value


def _counts_only(out: dict[str, Any]) -> dict[str, Any]:
    return {**counts_scrub(out), "countsOnly": True, "countsOnlyWhy": COUNTS_ONLY_WHY}


def _is_counts_only(viewer: Any) -> bool:
    from jason.web import access

    return access.counts_only(viewer)


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

    viewer = _need()
    out = new_responses(request=args.get("request", ""), channel=args.get("channel", ""), unit=args.get("unit", ""),
                        state=args.get("state") or "new", days=_int(args, "days", 0))
    if not _is_counts_only(viewer):
        return out
    by_channel: dict[str, int] = {}
    for row in out.get("arrivals") or []:
        channel = str(row.get("channel") or "unknown")
        by_channel[channel] = by_channel.get(channel, 0) + 1
    kept = {k: v for k, v in out.items() if k in ("found", "reason", "state", "count", "inbox", "checked", "note", "caveats")}
    return _counts_only({**kept, "byChannel": by_channel})


def response(args: Args) -> dict[str, Any]:
    from jason.mcp.response_inbox import response as tool
    from jason.web import access

    viewer = _need()
    if _is_counts_only(viewer):
        from flask import abort

        abort(access.refusal(403, REFUSED_ARRIVAL))
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

    viewer = _need()
    out = outstanding_responses(request=args.get("request", ""))
    if not _is_counts_only(viewer):
        return out
    rows = []
    for req in out.get("requests") or []:
        rows.append({**req, "outstandingCount": len(req.get("outstanding") or []),
                     "neverAskedCount": None if req.get("neverAsked") is None else len(req["neverAsked"])})
    return _counts_only({**out, "requests": rows} if "requests" in out else out)


def campaign(args: Args) -> dict[str, Any]:
    from jason.mcp.followups import campaign_status

    viewer = _need()
    out = campaign_status(code=args.get("code", ""))
    if not _is_counts_only(viewer):
        return out
    shaped = []
    for f in out.get("campaigns") or []:
        waiting, lost = dict(f.get("outstanding") or {}), dict(f.get("unreachable") or {})
        waiting["neverAskedCount"] = waiting.pop("neverAsked", None)
        nxt = f.get("nextFollowUp")
        shaped.append({**f, "outstanding": waiting, "unreachable": lost,
                       "nextFollowUp": _item(nxt) if isinstance(nxt, dict) else nxt})
    return _counts_only({**out, "campaigns": shaped} if "campaigns" in out else out)


def _item(row: dict[str, Any]) -> dict[str, Any]:
    """One follow-up without an owner: its count stays, its names go, a ``what`` that names an owner becomes the same act
    on "a" form or request, and a resend command loses the units it was told to resend to."""
    out = {k: v for k, v in row.items() if k != "names"}
    command = str(out.get("command") or "")
    out["command"] = _ONLY.sub("", command)
    if out.get("source") == "inbox":
        out["what"] = ("Read a returned form that came in" if "--read" in command else
                       "Confirm the reading of a returned form" if "--confirm" in command else
                       "Record a confirmed answer in PayHOA")
    elif out.get("source") == "person":
        # A person's own follow-up is free text; jason cannot tell whether it names an owner, so a counts-only viewer
        # reads that one exists, its kind, state, and date, not its words (the user's call, 2026-10-10).
        out["what"], out["why"] = "A follow-up a person added", ""
    elif out.get("source") == "clock":
        found = _CLOCK.match(str(out.get("what") or ""))
        out["what"] = f"{found.group(1)}: a request, {found.group(2)}" if found else "A request is on its clock"
    return out


def followups(args: Args) -> dict[str, Any]:
    from jason.mcp.followups import followups as tool

    viewer = _need()
    out = tool(days=_int(args, "days", 30), campaign=args.get("campaign", ""), kind=args.get("kind", ""),
               state=args.get("state", ""))
    if not _is_counts_only(viewer):
        return out
    return _counts_only({**out, "items": [_item(i) for i in out["items"]]} if isinstance(out.get("items"), list) else out)


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
