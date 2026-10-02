"""The board as PayHOA tags it: each membership carrying the "Board Member" tag, current and archived.

PayHOA's people list (``GET /organizations/{orgId}/people-list``) carries each membership's ``tags``, one entry per tag
applied (``tag``, ``taggableId`` = the membership id). ``GET /organizations/{orgId}/tags/member`` is only the catalog
of tag names, with one holder each, so it cannot list the board. ``sync`` pages through the active and the archived
members and keeps the tagged ones in ``data/payhoa/board-members.json``: the membership id, the name, the email,
whether the member is a PayHOA admin, and the last login. An archived member tagged Board Member is a former director.

The tag is what the board keeps in PayHOA, not the record of an election or appointment: the minutes and the
election results are. jason only reads PayHOA.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path("payhoa") / "board-members.json"
TAG = "Board Member"


def _name(row: dict[str, Any], known: dict[int, str]) -> str:
    profile = row.get("profile") or {}
    parts = [profile.get(k) for k in ("givenNames", "firstName")] + [profile.get(k) for k in ("familyName", "lastName")]
    name = " ".join(p for p in parts if p) or profile.get("name") or profile.get("displayName") or ""
    return name or known.get(int(row["id"]), "") or (row.get("user") or {}).get("name", "")


def _known_names(data_dir: Path) -> dict[int, str]:
    db = Path(data_dir) / "payhoa.db"
    if not db.is_file():
        return {}
    with sqlite3.connect(db) as con:
        return {int(i): n for i, n in con.execute("select id, name from people") if n}


def sync(client: Any, org_id: int, data_dir: Path) -> dict[str, Any]:
    known = _known_names(data_dir)
    out: dict[str, list[dict[str, Any]]] = {"current": [], "former": []}
    for status, bucket in (("active", "current"), ("archived", "former")):
        for row in client.iter_people(org_id, per_page=100, status=status):
            if not any(t.get("tag") == TAG for t in row.get("tags") or []):
                continue
            if not _name(row, known):                        # the list's profile can be empty; the detail's is not
                row = {**row, "profile": (client.get_member(org_id, row["id"]) or {}).get("profile") or {}}
            out[bucket].append({"membershipId": row["id"], "name": _name(row, known), "email": row.get("email") or "",
                                "admin": bool(row.get("isAdmin")), "lastLogin": (row.get("lastLogin") or "")[:10],
                                "archivedAt": (row.get("archivedAt") or "")[:10]})
    result = {"syncedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tag": TAG, **out}
    path = Path(data_dir) / STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def load(data_dir: Path) -> dict[str, Any]:
    path = Path(data_dir) / STORE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"current": [], "former": []}


def current_names(data_dir: Path) -> list[str]:
    return [m["name"] or m["email"] for m in load(data_dir).get("current", [])]


__all__ = ["TAG", "current_names", "load", "sync"]
