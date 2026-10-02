"""Google Drive Activity API v2 (``driveactivity.googleapis.com/v2``): who did what to a Drive item, and when.

``activity:query`` takes one item (``itemName``) or a folder and everything under it (``ancestorName``), an optional
filter (time and action type), and pages with ``pageToken``. Each ``DriveActivity`` is parsed into an ``Activity``: the
time, the primary action and its detail (move parents, rename titles, permission changes, delete type), the actors, and
the targets. Actors are people ids (``people/<id>``); a name would need the People API and is not looked up.

The client only reads. It needs the ``drive.activity.readonly`` scope on the main Google token. A 403 or 404 on an item
means the signed-in account cannot see it; ``query`` raises ``ActivityNotVisible`` for that so a caller can report it as
the answer. The API also answers 200 with no activities for an item the account cannot see, so ``file_metadata``
(Drive ``files.get``, read-only) tells an unseen item from a quiet one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterator

import httpx

from jason.google.errors import GoogleError

API = "https://driveactivity.googleapis.com/v2"
DRIVE_API = "https://www.googleapis.com/drive/v3"


class ActionType(Enum):
    CREATE = "create"
    EDIT = "edit"
    MOVE = "move"
    RENAME = "rename"
    DELETE = "delete"
    RESTORE = "restore"
    PERMISSION_CHANGE = "permissionChange"
    COMMENT = "comment"
    DLP_CHANGE = "dlpChange"
    REFERENCE = "reference"
    SETTINGS_CHANGE = "settingsChange"
    APPLIED_LABEL_CHANGE = "appliedLabelChange"
    UNKNOWN = "unknown"

    @property
    def filter_case(self) -> str:
        """The name ``detail.action_detail_case`` takes in a filter."""
        return self.name


# The actions that change where a file is, whether it exists, or who can open it.
CUSTODY_ACTIONS: tuple[ActionType, ...] = (ActionType.DELETE, ActionType.MOVE, ActionType.RENAME,
                                           ActionType.PERMISSION_CHANGE, ActionType.RESTORE)


class ActorKind(Enum):
    USER = "user"
    DELETED_USER = "deleted user"
    UNKNOWN_USER = "unknown user"
    ANONYMOUS = "anonymous"
    IMPERSONATION = "impersonation"
    SYSTEM = "system"
    ADMINISTRATOR = "administrator"
    UNKNOWN = "unknown"


class DeleteType(Enum):
    TRASH = "TRASH"
    PERMANENT_DELETE = "PERMANENT_DELETE"
    UNSPECIFIED = "TYPE_UNSPECIFIED"


@dataclass(frozen=True)
class Actor:
    kind: ActorKind
    person: str | None = None          # "people/<id>"
    is_current_user: bool = False
    detail: str | None = None          # system event type, impersonated person

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind.value, "person": self.person, "isCurrentUser": self.is_current_user, "detail": self.detail}


@dataclass(frozen=True)
class ItemRef:
    """A Drive item named by an activity: a target, or a parent a move added or removed."""
    item_id: str | None
    title: str | None = None
    mime_type: str | None = None
    folder: bool = False
    owner: str | None = None           # "people/<id>", "drive <name>", or "domain <name>"

    def to_json(self) -> dict[str, Any]:
        return {"id": self.item_id, "title": self.title, "mimeType": self.mime_type, "folder": self.folder, "owner": self.owner}


@dataclass(frozen=True)
class PermissionRef:
    role: str
    grantee: str                       # "anyone", "people/<id>", "group <email>", "domain <name>"
    anyone: bool = False
    discoverable: bool = False

    def to_json(self) -> dict[str, Any]:
        return {"role": self.role, "grantee": self.grantee, "anyone": self.anyone, "discoverable": self.discoverable}


@dataclass(frozen=True)
class Activity:
    time: str | None
    action: ActionType
    actors: tuple[Actor, ...] = ()
    targets: tuple[ItemRef, ...] = ()
    added_parents: tuple[ItemRef, ...] = ()
    removed_parents: tuple[ItemRef, ...] = ()
    old_title: str | None = None
    new_title: str | None = None
    added_permissions: tuple[PermissionRef, ...] = ()
    removed_permissions: tuple[PermissionRef, ...] = ()
    delete_type: DeleteType | None = None
    create_kind: str | None = None     # new, upload, copy
    actions: tuple[ActionType, ...] = field(default=())

    @property
    def link_shared(self) -> bool:
        return any(p.anyone for p in self.added_permissions)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"time": self.time, "action": self.action.value,
                               "actors": [a.to_json() for a in self.actors],
                               "targets": [t.to_json() for t in self.targets]}
        if self.added_parents or self.removed_parents:
            out["move"] = {"added": [p.to_json() for p in self.added_parents],
                           "removed": [p.to_json() for p in self.removed_parents]}
        if self.old_title is not None or self.new_title is not None:
            out["rename"] = {"old": self.old_title, "new": self.new_title}
        if self.added_permissions or self.removed_permissions:
            out["permissions"] = {"added": [p.to_json() for p in self.added_permissions],
                                  "removed": [p.to_json() for p in self.removed_permissions],
                                  "anyoneLinkAdded": self.link_shared}
        if self.delete_type is not None:
            out["deleteType"] = self.delete_type.value
        if self.create_kind:
            out["createKind"] = self.create_kind
        if len(self.actions) > 1:
            out["actions"] = [a.value for a in self.actions]
        return out


class ActivityNotVisible(GoogleError):
    """HTTP 403 or 404: the signed-in account cannot see the item."""

    def __init__(self, item: str, status: int) -> None:
        super().__init__(f"HTTP {status}: {item} is not visible to the signed-in account")
        self.item = item
        self.status = status


def item_id(name: str | None) -> str | None:
    if not name:
        return None
    return name.split("/", 1)[1] if name.startswith("items/") else name


def _action_type(detail: dict[str, Any] | None) -> ActionType:
    for key in (detail or {}):
        try:
            return ActionType(key)
        except ValueError:
            continue
    return ActionType.UNKNOWN


def _actor(raw: dict[str, Any]) -> Actor:
    if "user" in raw:
        user = raw["user"] or {}
        if "knownUser" in user:
            known = user["knownUser"] or {}
            return Actor(ActorKind.USER, known.get("personName"), bool(known.get("isCurrentUser")))
        if "deletedUser" in user:
            return Actor(ActorKind.DELETED_USER)
        return Actor(ActorKind.UNKNOWN_USER)
    if "anonymous" in raw:
        return Actor(ActorKind.ANONYMOUS)
    if "impersonation" in raw:
        known = ((raw["impersonation"] or {}).get("impersonatedUser") or {}).get("knownUser") or {}
        return Actor(ActorKind.IMPERSONATION, known.get("personName"), bool(known.get("isCurrentUser")))
    if "system" in raw:
        return Actor(ActorKind.SYSTEM, detail=(raw["system"] or {}).get("type"))
    if "administrator" in raw:
        return Actor(ActorKind.ADMINISTRATOR)
    return Actor(ActorKind.UNKNOWN)


def _owner(raw: dict[str, Any] | None) -> str | None:
    if not raw:
        return None
    known = (raw.get("user") or {}).get("knownUser") or {}
    if known.get("personName"):
        return known["personName"]
    if raw.get("drive"):
        return f"drive {raw['drive'].get('title') or raw['drive'].get('name')}"
    if raw.get("domain"):
        return f"domain {raw['domain'].get('name')}"
    return None


def _item(raw: dict[str, Any] | None) -> ItemRef | None:
    item = (raw or {}).get("driveItem")
    if not item:
        return None
    folder = "driveFolder" in item or "folder" in item
    return ItemRef(item_id(item.get("name")), item.get("title"), item.get("mimeType"), folder, _owner(item.get("owner")))


def _permission(raw: dict[str, Any]) -> PermissionRef:
    role = raw.get("role") or "ROLE_UNSPECIFIED"
    discoverable = bool(raw.get("allowDiscovery"))
    if "anyone" in raw:
        return PermissionRef(role, "anyone", True, discoverable)
    if "user" in raw:
        person = ((raw["user"] or {}).get("knownUser") or {}).get("personName") or "unknown user"
        return PermissionRef(role, person, False, discoverable)
    if "group" in raw:
        return PermissionRef(role, f"group {(raw['group'] or {}).get('email')}", False, discoverable)
    if "domain" in raw:
        return PermissionRef(role, f"domain {(raw['domain'] or {}).get('name')}", False, discoverable)
    return PermissionRef(role, "unknown", False, discoverable)


def parse_activity(raw: dict[str, Any]) -> Activity:
    """One ``DriveActivity`` resource as an ``Activity``."""
    detail = raw.get("primaryActionDetail") or {}
    action = _action_type(detail)
    time = raw.get("timestamp") or (raw.get("timeRange") or {}).get("endTime")
    targets = tuple(t for t in (_item(x) for x in raw.get("targets") or []) if t)
    move = detail.get("move") or {}
    rename = detail.get("rename") or {}
    permission = detail.get("permissionChange") or {}
    delete = detail.get("delete")
    delete_type = None
    if delete is not None:
        try:
            delete_type = DeleteType(delete.get("type") or "TYPE_UNSPECIFIED")
        except ValueError:
            delete_type = DeleteType.UNSPECIFIED
    create = detail.get("create") or {}
    return Activity(
        time=time,
        action=action,
        actors=tuple(_actor(a) for a in raw.get("actors") or []),
        targets=targets,
        added_parents=tuple(p for p in (_item(x) for x in move.get("addedParents") or []) if p),
        removed_parents=tuple(p for p in (_item(x) for x in move.get("removedParents") or []) if p),
        old_title=rename.get("oldTitle"),
        new_title=rename.get("newTitle"),
        added_permissions=tuple(_permission(p) for p in permission.get("addedPermissions") or []),
        removed_permissions=tuple(_permission(p) for p in permission.get("removedPermissions") or []),
        delete_type=delete_type,
        create_kind=next(iter(create), None),
        actions=tuple(_action_type(a.get("detail")) for a in raw.get("actions") or []),
    )


def build_filter(since: str | None = None, actions: tuple[ActionType, ...] | None = None) -> str | None:
    """``since`` is RFC 3339 or YYYY-MM-DD (read as midnight UTC)."""
    parts = []
    if since:
        stamp = since if "T" in since else f"{since}T00:00:00Z"
        parts.append(f'time >= "{stamp}"')
    if actions:
        parts.append(f"detail.action_detail_case:({' '.join(a.filter_case for a in actions)})")
    return " AND ".join(parts) or None


class DriveActivityClient:
    def __init__(self, access_token: str, *, http: httpx.Client | None = None) -> None:
        if not access_token:
            raise GoogleError("missing access token")
        self._token = access_token
        self._owns_http = http is None
        self._http = http or httpx.Client(timeout=60.0)

    @classmethod
    def from_drive(cls, drive: Any) -> DriveActivityClient:
        """Share the Drive client's token (which carries ``drive.activity.readonly``) and connection."""
        token = drive._headers()["Authorization"].removeprefix("Bearer ").strip()
        client = cls(token, http=getattr(drive, "_http", None))
        client._owns_http = False
        return client

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> DriveActivityClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def query(self, *, item: str | None = None, ancestor: str | None = None, since: str | None = None,
              actions: tuple[ActionType, ...] | None = None, page_size: int = 100,
              limit: int | None = None) -> Iterator[Activity]:
        """Activities on one item, or under one folder, newest first. Exactly one of ``item`` and ``ancestor``."""
        if bool(item) == bool(ancestor):
            raise GoogleError("pass exactly one of item and ancestor")
        body: dict[str, Any] = {"pageSize": page_size}
        if item:
            body["itemName"] = f"items/{item_id(item)}"
        else:
            body["ancestorName"] = f"items/{item_id(ancestor)}"
        flt = build_filter(since, actions)
        if flt:
            body["filter"] = flt
        seen = 0
        while True:
            response = self._http.post(f"{API}/activity:query", json=body, headers=self._headers())
            if response.status_code in (403, 404):
                raise ActivityNotVisible(item or ancestor or "", response.status_code)
            if not response.is_success:
                try:
                    message = response.json().get("error", {}).get("message", "")
                except Exception:
                    message = response.text[:200]
                raise GoogleError(f"HTTP {response.status_code} activity:query: {message}")
            page = response.json() if response.content else {}
            for raw in page.get("activities") or []:
                yield parse_activity(raw)
                seen += 1
                if limit is not None and seen >= limit:
                    return
            token = page.get("nextPageToken")
            if not token:
                return
            body["pageToken"] = token

    def file_metadata(self, file_id: str) -> dict[str, Any] | None:
        """Drive's own metadata for the item (no owner names), or None when the account cannot see it."""
        response = self._http.get(
            f"{DRIVE_API}/files/{item_id(file_id)}",
            params={"fields": "id,name,mimeType,trashed,ownedByMe,shared,modifiedTime", "supportsAllDrives": "true"},
            headers=self._headers())
        if response.status_code in (403, 404):
            return None
        if not response.is_success:
            raise GoogleError(f"HTTP {response.status_code} files.get {file_id}")
        return response.json() if response.content else {}


__all__ = ["API", "Activity", "ActionType", "ActivityNotVisible", "Actor", "ActorKind", "CUSTODY_ACTIONS", "DeleteType",
           "DriveActivityClient", "ItemRef", "PermissionRef", "build_filter", "item_id", "parse_activity"]
