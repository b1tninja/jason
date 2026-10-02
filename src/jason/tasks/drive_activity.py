"""What happened to Drive items: the Drive Activity record for files, and for everything under a folder.

``activity_for`` reads the activity of a set of Drive ids since a date, optionally only some actions. It answers the
custody question a legal-hold watch asks: has anything held been deleted, moved, or re-shared. An id the association's
account cannot see (HTTP 403 or 404) is reported as not visible; that is the answer, not an error.

``agenda_missing`` applies it to the Drive files the board's agendas link that are not in the association's Drive
listing (``data/meetings/agenda-links.json``, targets with ``inDrive`` false). Each one gets a standing: not visible
(most likely owned by a personal account and not shared), permanently deleted, in the trash, or visible, with its last
action, moves, sharing changes, and the actors by people id. ``folder_watch`` reads everything under one folder.

Every result is written to ``data/drive/activity-<name>.json``. Nothing here writes to Drive.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.agenda_links import LinkKind
from jason.google.drive_activity import (
    Activity,
    ActionType,
    ActivityNotVisible,
    DeleteType,
    DriveActivityClient,
    item_id,
)

AGENDA_LINKS = Path("meetings") / "agenda-links.json"
OUT_DIR = Path("drive")
DRIVE_KINDS: tuple[LinkKind, ...] = (LinkKind.DRIVE_FILE, LinkKind.DRIVE_FOLDER, LinkKind.GOOGLE_DOC)


class Standing(Enum):
    NOT_VISIBLE = "not visible to the association account"
    PERMANENTLY_DELETED = "permanently deleted"
    TRASHED = "in the trash"
    VISIBLE = "visible"


@dataclass
class ItemActivity:
    """One Drive id's activity, newest first, or the fact that the account cannot see it."""
    item: str
    visible: bool
    activities: list[Activity] = field(default_factory=list)
    metadata: dict[str, Any] | None = None
    status: int | None = None          # the HTTP status when not visible
    probed: bool = False               # Drive metadata was asked for (None then means Drive would not show it)

    def of(self, *actions: ActionType) -> list[Activity]:
        return [a for a in self.activities if a.action in actions]

    @property
    def last(self) -> Activity | None:
        return self.activities[0] if self.activities else None

    @property
    def standing(self) -> Standing:
        deletes = self.of(ActionType.DELETE)
        if any(a.delete_type is DeleteType.PERMANENT_DELETE for a in deletes):
            return Standing.PERMANENTLY_DELETED
        # The Activity API answers 200 with nothing for an item the account cannot see; Drive's 404 settles it.
        if self.metadata is None and (not self.visible or (self.probed and not self.activities)):
            return Standing.NOT_VISIBLE
        if self.metadata and self.metadata.get("trashed"):
            return Standing.TRASHED
        last_custody = next((a for a in self.activities if a.action in (ActionType.DELETE, ActionType.RESTORE)), None)
        if last_custody is not None and last_custody.action is ActionType.DELETE:
            return Standing.TRASHED
        return Standing.VISIBLE if (self.visible or self.metadata is not None) else Standing.NOT_VISIBLE

    def summary(self) -> dict[str, Any]:
        people: dict[str, bool] = {}
        for activity in self.activities:
            for actor in activity.actors:
                key = actor.person or actor.kind.value
                people[key] = people.get(key, False) or actor.is_current_user
        last = self.last
        deletes = self.of(ActionType.DELETE)
        return {
            "id": self.item,
            "standing": self.standing.value,
            "visible": self.standing is not Standing.NOT_VISIBLE,
            "httpStatus": self.status,
            "metadata": self.metadata,
            "activityCount": len(self.activities),
            "lastAction": ({"time": last.time, "action": last.action.value,
                            "actors": [a.to_json() for a in last.actors]} if last else None),
            "trashedOrDeleted": [{"time": a.time, "type": a.delete_type.value if a.delete_type else None,
                                  "actors": [x.to_json() for x in a.actors]} for a in deletes],
            "restored": [a.time for a in self.of(ActionType.RESTORE)],
            "moved": [a.to_json() for a in self.of(ActionType.MOVE)],
            "renamed": [a.to_json() for a in self.of(ActionType.RENAME)],
            "sharingChanged": [a.to_json() for a in self.of(ActionType.PERMISSION_CHANGE)],
            "anyoneLinkAdded": any(a.link_shared for a in self.activities),
            "actors": [{"person": k, "isCurrentUser": v} for k, v in people.items()],
        }


def item_activity(client: DriveActivityClient, drive_id: str, *, since: str | None = None,
                  actions: tuple[ActionType, ...] | None = None, probe: bool = True) -> ItemActivity:
    drive_id = item_id(drive_id) or drive_id
    metadata = client.file_metadata(drive_id) if probe else None
    try:
        activities = list(client.query(item=drive_id, since=since, actions=actions))
    except ActivityNotVisible as exc:
        return ItemActivity(drive_id, False, metadata=metadata, status=exc.status, probed=probe)
    activities.sort(key=lambda a: a.time or "", reverse=True)
    return ItemActivity(drive_id, True, activities, metadata, probed=probe)


def activity_for(client: DriveActivityClient, ids: Iterable[str], since: str | None = None, *,
                 actions: tuple[ActionType, ...] | None = None, probe: bool = True) -> dict[str, ItemActivity]:
    """Each id's activity since ``since`` (YYYY-MM-DD or RFC 3339), only ``actions`` when given.

    Pass ``CUSTODY_ACTIONS`` to ask only whether an item was deleted, moved, renamed, restored, or re-shared.
    """
    keys = dict.fromkeys(item_id(i) or i for i in ids)
    return {i: item_activity(client, i, since=since, actions=actions, probe=probe) for i in keys}


def missing_targets(data_dir: Path) -> list[dict[str, Any]]:
    """The agenda links to Drive items that are not in the association's Drive listing."""
    path = Path(data_dir) / AGENDA_LINKS
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing; run `jason meetings` agenda links first")
    targets = json.loads(path.read_text(encoding="utf-8")).get("targets") or []
    kinds = {k.value for k in DRIVE_KINDS}
    return [t for t in targets if t.get("inDrive") is False and t.get("kind") in kinds and t.get("key")]


def agenda_missing(client: DriveActivityClient, data_dir: Path, *, since: str | None = None) -> dict[str, Any]:
    targets = missing_targets(data_dir)
    found = activity_for(client, [t["key"] for t in targets], since)
    rows = []
    for target in targets:
        row = found[item_id(target["key"]) or target["key"]].summary()
        row.update({"kind": target["kind"], "names": target.get("names") or [], "url": target.get("url"),
                    "agendas": sorted({l.get("date") for l in target.get("labels") or [] if l.get("date")})})
        rows.append(row)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["standing"]] = counts.get(row["standing"], 0) + 1
    return {"builtAt": _now(), "name": "agenda-missing", "since": since, "items": len(rows), "standings": counts,
            "files": rows}


def file_report(client: DriveActivityClient, drive_id: str, *, since: str | None = None) -> dict[str, Any]:
    found = item_activity(client, drive_id, since=since)
    return {"builtAt": _now(), "name": f"file-{found.item}", "since": since, **found.summary(),
            "activities": [a.to_json() for a in found.activities]}


def folder_watch(client: DriveActivityClient, folder_id: str, *, since: str | None = None,
                 actions: tuple[ActionType, ...] | None = None) -> dict[str, Any]:
    """Everything done under one folder since a date, newest first."""
    folder_id = item_id(folder_id) or folder_id
    base = {"builtAt": _now(), "name": f"folder-{folder_id}", "folder": folder_id, "since": since}
    try:
        activities = sorted(client.query(ancestor=folder_id, since=since, actions=actions),
                            key=lambda a: a.time or "", reverse=True)
    except ActivityNotVisible as exc:
        return {**base, "standing": Standing.NOT_VISIBLE.value, "httpStatus": exc.status, "activities": []}
    if not activities and client.file_metadata(folder_id) is None:
        return {**base, "standing": Standing.NOT_VISIBLE.value, "httpStatus": None, "activities": []}
    counts: dict[str, int] = {}
    for activity in activities:
        counts[activity.action.value] = counts.get(activity.action.value, 0) + 1
    return {**base, "standing": Standing.VISIBLE.value, "count": len(activities), "byAction": counts,
            "trashedOrDeleted": sum(1 for a in activities if a.action is ActionType.DELETE),
            "anyoneLinkAdded": sum(1 for a in activities if a.link_shared),
            "activities": [a.to_json() for a in activities]}


def write(data_dir: Path, report: dict[str, Any]) -> Path:
    out = Path(data_dir) / OUT_DIR / f"activity-{report['name']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return out


def summary_lines(report: dict[str, Any]) -> list[str]:
    lines = []
    if "files" in report:
        lines.append(f"{report['items']} agenda-linked Drive items not in the association's Drive listing")
        for standing, n in sorted(report["standings"].items()):
            lines.append(f"  {standing}: {n}")
        for row in report["files"]:
            last = row["lastAction"]
            what = f"last {last['action']} {last['time']}" if last else "no activity visible"
            flags = [f for f, on in (("moved", row["moved"]), ("sharing changed", row["sharingChanged"]),
                                     ("anyone link", row["anyoneLinkAdded"])) if on]
            name = (row["names"] or [row["id"]])[0]
            lines.append(f"- {name} [{row['standing']}] {what}" + (f" ({', '.join(flags)})" if flags else ""))
    elif "folder" in report:
        lines.append(f"folder {report['folder']} [{report['standing']}]: {report.get('count', 0)} activities"
                     + (f" since {report['since']}" if report["since"] else ""))
        for action, n in sorted((report.get("byAction") or {}).items()):
            lines.append(f"  {action}: {n}")
    else:
        last = report["lastAction"]
        lines.append(f"file {report['id']} [{report['standing']}]: {report['activityCount']} activities"
                     + (f", last {last['action']} {last['time']}" if last else ""))
    return lines


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


__all__ = ["DRIVE_KINDS", "ItemActivity", "Standing", "activity_for", "agenda_missing", "file_report", "folder_watch",
           "item_activity", "missing_targets", "summary_lines", "write"]
