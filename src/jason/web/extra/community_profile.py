"""The community-profile source: what the public owner page shows, read from the active profile alone.

``community_profile(args)`` answers the association's names and slug, its site pages (``site_pages()``), the mailing
address a letter reaches it at (``mail_addresses()``, the current one only), the contact addresses owners may write to
(``google_groups()`` by purpose, never a person's address), the calendar the console embeds (``jason.web.sources.embeds``,
falling back to ``calendar_id()``), and the Civil Code 5200 record kinds with whether each is on file
(``records_inventory``). Every field is a ``Community`` method's answer; a method the profile leaves at its empty default
gives an empty field, and the page shows nothing for it. Nothing here names an association. Reads disk only; ``write`` refuses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

Args = dict[str, str]

# Group purposes an owner may write to. Accounts payable, the paper-mail feed, and "other" are internal.
PUBLIC_PURPOSES = ("GENERAL", "BOARD", "MANAGEMENT", "ARCHITECTURAL")


def _call(obj: Any, name: str, default: Any) -> Any:
    """``obj.name()`` (or the attribute when it is not callable), or ``default`` when it is missing or raises."""
    value = getattr(obj, name, None)
    if value is None:
        return default
    try:
        return value() if callable(value) else value
    except Exception:
        return default


def _pages(community: Any, site: str) -> list[dict[str, str]]:
    rows = []
    for ref in _call(community, "site_pages", ()) or ():
        page = getattr(ref, "page", None)
        key = str(getattr(page, "value", page) or "")
        path = str(getattr(ref, "path", "") or "")
        if not key:
            continue
        rows.append({"page": key, "label": key.replace("_", " ").capitalize(), "path": path, "url": f"{site.rstrip('/')}{path}" if site and path else ""})
    return rows


def _mailing(community: Any) -> list[dict[str, str]]:
    rows = []
    for address in _call(community, "mail_addresses", ()) or ():
        kind = getattr(address, "kind", None)
        if getattr(kind, "name", "") != "CURRENT":
            continue  # a former manager's or the site's address is not where to write
        rows.append({"kind": str(getattr(kind, "value", "")), "label": str(getattr(address, "label", "")), "zip": str(getattr(address, "zip", "") or "")})
    return rows


def _contacts(community: Any) -> list[dict[str, str]]:
    rows = []
    for group in _call(community, "google_groups", ()) or ():
        purpose = getattr(group, "purpose", None)
        if getattr(purpose, "name", "") not in PUBLIC_PURPOSES:
            continue
        rows.append({"label": str(getattr(group, "name", "")), "purpose": str(getattr(purpose, "value", "")), "kind": str(getattr(purpose, "name", "")).lower(),
                     "email": str(getattr(group, "address", ""))})
    return rows


def _calendar(community: Any) -> tuple[str, str]:
    try:
        from jason.web import sources

        found = sources.embeds({"limit": "0"})
        return str(found.get("calendarId") or ""), str(found.get("timeZone") or "")
    except Exception:
        return str(_call(community, "calendar_id", "") or ""), ""


def _records() -> dict[str, Any]:
    """The 5200 record kinds a member may inspect, each with its citation and whether something is on file. The shelf's
    folders, rules, and notes are the board's view and stay off the public page."""
    try:
        from jason.mcp.county import records_inventory

        rows = records_inventory().get("records", [])
    except Exception as exc:
        return {"kinds": [], "onFile": 0, "total": 0, "note": f"records inventory unavailable ({type(exc).__name__})"}
    kinds = []
    for r in rows:
        on_file = bool(r.get("documents") or r.get("files")) and not r.get("gap")
        kinds.append({"record": str(r.get("record", "")), "citation": str(r.get("citation", "")), "meaning": str(r.get("meaning", "")), "onFile": on_file})
    return {"kinds": kinds, "onFile": sum(1 for k in kinds if k["onFile"]), "total": len(kinds), "note": ""}


def community_profile(args: Args) -> dict[str, Any]:
    from jason.community import community

    c = community()
    theme = _call(c, "theme", None)
    name = str(c.name or "")
    # The association's public site: a profile fact the base class does not yet carry; empty means paths only.
    site = str(_call(c, "site", "") or "")
    calendar_id, time_zone = _calendar(c)
    return {
        "found": True,
        "slug": str(c.slug or ""),
        "name": name,
        "corporateName": str(_call(c, "corporate_name", "") or ""),
        "wordmark": str(getattr(theme, "wordmark", "") or name),
        "site": site,
        "pages": _pages(c, site),
        "mailing": _mailing(c),
        "contacts": _contacts(c),
        "calendarId": calendar_id,
        "timeZone": time_zone,
        "records": _records(),
        "asOf": datetime.now(timezone.utc).date().isoformat(),
        "caveats": ["Read from the association's records by jason. A record on file is pinned to a document, not reviewed.",
                    "Association records may not be used for a purpose unrelated to a member's interest as a member (CIV 5230)."],
    }


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    raise ValueError("the community profile is read from the profile; it is not written from the console")
