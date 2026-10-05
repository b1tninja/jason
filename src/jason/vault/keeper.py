"""The Keeper backend of the vault: one Keeper record per vault path, over the keepersdk session in ``jason.secrets``.

**The mapping.** A vault path is a Keeper record whose **title is the path**
(``jason/community/<key>/payhoa/login``), kept in a folder named ``jason`` at the top of the signed-in user's vault (a
user folder or a shared folder; records in its subfolders count too). A record outside that folder is never read as a
vault entry, whatever its title, so a record shared in from someone else cannot stand in for one. Two records in the
folder with one title are an error, never a guess. A person sees the paths in Keeper's own app, and can move the
folder into a shared folder for a second administrator.

**The fields.** A secret is a typed ``login`` record: ``login``, ``password``, ``url``, and ``oneTimeCode`` (a TOTP
seed) are its standard fields, and every other field is a masked custom ``secret`` field labeled with its name. Reading
gives back the same names (``record_fields``), and a record written by hand reads the same way.

**Versions** are the record's Keeper revision: ``put(..., if_version=N)`` refuses a record whose revision is not ``N``,
and Keeper itself refuses an update made against an older revision. ``describe`` gives the record's last-modified time;
Keeper does not say who changed a record, so ``by`` is empty.

**Sign-in.** Every call opens the session the way ``jason.secrets.VaultSession`` does: a non-interactive store raises
``KeeperAuthRequired`` at once when Keeper wants a password, a code, or a device approval (``jason login`` in a
terminal). Nothing here prints or logs a value.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from jason.vault.paths import check_path, check_prefix, parse_path
from jason.vault.store import Secret, VaultEntry, VaultError, VersionConflict

FOLDER = "jason"
STANDARD_FIELDS = ("login", "password", "url", "oneTimeCode")


def record_fields(record: Any) -> dict[str, str]:
    """A Keeper record's fields by name: the standard login fields that are set, then each labeled custom field."""
    from jason.secrets import _field_value, extract_custom_fields

    out = {name: value for name in STANDARD_FIELDS if (value := _field_value(record, name))}
    out.update({label: value for label, value in extract_custom_fields(record).items() if value})
    return out


@dataclass(frozen=True)
class KeeperEntry:
    """A record in the vault folder: its UID, title (the path), and revision. No value."""

    uid: str
    title: str
    revision: int


class KeeperAdapter(Protocol):
    """What ``KeeperStore`` asks of Keeper. ``SdkKeeperAdapter`` is the real one; tests use a fake."""

    def entries(self) -> list[KeeperEntry]: ...

    def read(self, uid: str) -> tuple[dict[str, str], int | None]: ...   # fields, modified (ms since the epoch)

    def create(self, title: str, fields: Mapping[str, str], notes: str) -> str: ...

    def update(self, uid: str, fields: Mapping[str, str]) -> None: ...

    def remove(self, uid: str) -> None: ...

    def load_by_uid(self, uid: str) -> dict[str, str]: ...    # any record, by UID: the .env fallback and migrate


class SdkKeeperAdapter:
    """``KeeperAdapter`` over ``jason.secrets.VaultSession`` (keepersdk)."""

    def __init__(self, session: Any, *, folder: str = FOLDER) -> None:
        self._session = session
        self._folder_name = folder

    def __repr__(self) -> str:
        return f"SdkKeeperAdapter(folder={self._folder_name!r})"

    @property
    def _vault(self) -> Any:
        return self._session.online

    def _folder_uid(self, *, create: bool = False) -> str | None:
        vault = self._vault
        data = vault.vault_data
        named = [f for uid in data.root_folder.subfolders if (f := data.get_folder(uid)) and f.name == self._folder_name]
        if len(named) > 1:
            raise VaultError(f"{len(named)} Keeper folders are named {self._folder_name!r}; keep one")
        if named:
            return named[0].folder_uid
        if not create:
            return None
        from keepersdk.vault.folder_management import add_folder

        uid = add_folder(vault, self._folder_name)
        vault.sync_down()
        return uid

    def _record_uids(self) -> set[str]:
        uid = self._folder_uid()
        if uid is None:
            return set()
        data, found, todo = self._vault.vault_data, set(), [uid]
        while todo:
            folder = data.get_folder(todo.pop())
            if folder is None:
                continue
            found |= set(folder.records)
            todo.extend(folder.subfolders)
        return found

    def entries(self) -> list[KeeperEntry]:
        data = self._vault.vault_data
        out = []
        for uid in self._record_uids():
            info = data.get_record(uid)
            if info is not None:
                out.append(KeeperEntry(uid, info.title, int(info.revision)))
        return out

    def read(self, uid: str) -> tuple[dict[str, str], int | None]:
        record = self._vault.vault_data.load_record(uid)
        if record is None:
            raise LookupError("no Keeper record for that entry")
        return record_fields(record), int(getattr(record, "client_time_modified", 0) or 0) or None

    def load_by_uid(self, uid: str) -> dict[str, str]:
        return record_fields(self._session.load_record(uid))

    def create(self, title: str, fields: Mapping[str, str], notes: str) -> str:
        folder = self._folder_uid(create=True)
        custom = {k: v for k, v in fields.items() if k not in STANDARD_FIELDS}
        uid = self._session.create_login_record(
            title, password=fields.get("password", ""), login=fields.get("login", ""), url=fields.get("url", ""),
            notes=notes, folder_uid=folder, custom=custom, one_time_code=fields.get("oneTimeCode", ""),
            hidden_custom=True)
        self._vault.sync_down()
        return uid

    def update(self, uid: str, fields: Mapping[str, str]) -> None:
        from keepersdk.vault.record_management import update_record
        from keepersdk.vault.vault_record import TypedField, TypedRecord

        vault = self._vault
        record = vault.vault_data.load_record(uid)
        if not isinstance(record, TypedRecord):
            raise VaultError("the vault entry is not a typed Keeper record; replace it in Keeper")
        for name in STANDARD_FIELDS:
            field = next((f for f in record.fields if f.type == name), None)
            if field is None:
                if not fields.get(name):
                    continue
                field = TypedField.create_field(name)
                record.fields.append(field)
            field.value = [fields[name]] if fields.get(name) else []
        record.custom = []
        for label, value in fields.items():
            if label in STANDARD_FIELDS:
                continue
            field = TypedField.create_field("secret", label)
            field.value = [value]
            record.custom.append(field)
        update_record(vault, record)
        vault.sync_down()

    def remove(self, uid: str) -> None:
        from keepersdk.vault.record_management import delete_vault_objects
        from keepersdk.vault.vault_types import RecordPath

        vault = self._vault
        data, folder_uid = vault.vault_data, None
        root = self._folder_uid()
        todo = [root] if root else []
        while todo and folder_uid is None:
            folder = data.get_folder(todo.pop())
            if folder is None:
                continue
            if uid in folder.records:
                folder_uid = folder.folder_uid
            todo.extend(folder.subfolders)
        if folder_uid is None:
            raise LookupError("the vault entry is not in the vault folder")
        delete_vault_objects(vault, [RecordPath(folder_uid=folder_uid, record_uid=uid)])
        vault.sync_down()


class KeeperStore:
    """``SecretStore`` over Keeper: a record titled with the vault path, in the ``jason`` folder."""

    name = "keeper"

    def __init__(self, adapter: KeeperAdapter) -> None:
        self._adapter = adapter

    def __repr__(self) -> str:
        return f"KeeperStore({self._adapter!r})"

    @classmethod
    def from_session(cls, session: Any, *, folder: str = FOLDER) -> KeeperStore:
        """Over an existing ``VaultSession`` (one login for the vault and the .env fallback)."""
        return cls(SdkKeeperAdapter(session, folder=folder))

    @classmethod
    def from_settings(cls, settings: Any, *, interactive: bool = False, folder: str = FOLDER) -> KeeperStore:
        """A store with its own session. ``interactive=False`` (the default) fails fast with ``KeeperAuthRequired``."""
        from jason.secrets import VaultSession

        return cls.from_session(VaultSession.from_settings(settings, interactive=interactive), folder=folder)

    def load_by_uid(self, uid: str) -> dict[str, str]:
        """A Keeper record's fields by UID: how an ``.env``-named record is read before it is migrated."""
        return self._adapter.load_by_uid(uid)

    def _find(self, path: str) -> KeeperEntry | None:
        found = [e for e in self._adapter.entries() if e.title == path]
        if len(found) > 1:
            raise VaultError(f"{len(found)} Keeper records in the vault folder are titled {path}; keep one")
        return found[0] if found else None

    def get(self, path: str) -> Secret | None:
        entry = self._find(check_path(path))
        if entry is None:
            return None
        fields, _ = self._adapter.read(entry.uid)
        return Secret(fields)

    def put(self, path: str, value: Mapping[str, str], if_version: int | None = None, *, by: str = "") -> int:
        path = check_path(path)
        fields = dict(Secret(value))
        if not fields:
            raise ValueError(f"{path}: a secret has at least one field with a value")
        entry = self._find(path)
        current = entry.revision if entry else 0
        if if_version is not None and if_version != current:
            raise VersionConflict(path, if_version, current)
        if entry is None:
            note = f"jason vault entry {path} (docs/integrations-design.md, The vault)."
            self._adapter.create(path, fields, note + (f" Written by {by}." if by else ""))
        else:
            self._adapter.update(entry.uid, fields)
        after = self._find(path)
        return after.revision if after else 0

    def delete(self, path: str) -> bool:
        entry = self._find(check_path(path))
        if entry is None:
            return False
        self._adapter.remove(entry.uid)
        return True

    def list(self, prefix: str) -> list[str]:
        prefix = check_prefix(prefix)
        names = set()
        for entry in self._adapter.entries():
            if not entry.title.startswith(prefix):
                continue
            try:
                names.add(parse_path(entry.title).path)
            except ValueError:
                continue            # a record in the folder whose title is not a vault path
        return sorted(names)

    def describe(self, path: str) -> VaultEntry:
        path = check_path(path)
        entry = self._find(path)
        if entry is None:
            return VaultEntry(path, False)
        _, modified = self._adapter.read(entry.uid)
        changed = datetime.fromtimestamp(modified / 1000, tz=timezone.utc) if modified else None
        return VaultEntry(path, True, entry.revision, changed, "")


__all__ = ["FOLDER", "KeeperAdapter", "KeeperEntry", "KeeperStore", "SdkKeeperAdapter", "record_fields"]
