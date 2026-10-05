"""Finding a credential: the vault path first, then today's ``.env`` record UID, and moving the second to the first.

``credential(community, integration, name)`` reads ``jason/<scope>/<community>/<integration>/<name>``. Until
``jason vault migrate`` has copied a record there, it falls back to the Keeper record that ``.env`` names
(``<x>_record_uid``, ``LEGACY``) and logs one line naming the key, never its value, so nothing breaks before the move.
A miss in both is ``CredentialMissing``: a miss, never a guess.

``plan_migration`` lists each ``*_record_uid`` key with the path it moves to; ``migrate`` copies the planned ones
(create only: an entry already at the path is left alone). Neither prints a value or a record UID.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum

from jason.vault.paths import INSTANCE, vault_path
from jason.vault.store import Secret, SecretStore, VersionConflict

log = logging.getLogger("jason.vault")

VENDOR_PORTAL = "vendor-portal"
SUFFIX = "_record_uid"


@dataclass(frozen=True)
class LegacyRecord:
    """A ``.env`` key that names a Keeper record today, and the vault path it moves to."""

    env_key: str
    integration: str
    name: str
    instance: bool = False      # the installation's, not a community's

    def path(self, community: str) -> str:
        return vault_path(INSTANCE if self.instance else community, self.integration, self.name)


# The keys config.py and .env.example name. A vendor portal's "<key>_record_uid" maps by the profile's portal rows
# (``legacy_record``), so no portal is named here.
LEGACY: tuple[LegacyRecord, ...] = (
    LegacyRecord("payhoa_record_uid", "payhoa", "login"),
    LegacyRecord("payhoa_test_record_uid", "payhoa", "test-login"),
    LegacyRecord("smud_record_uid", "smud", "login"),
    LegacyRecord("idoxs_record_uid", "idoxs", "login"),
    LegacyRecord("accela_record_uid", "accela", "login"),
    LegacyRecord("google_oauth_record_uid", "google-workspace", "oauth-client"),
    LegacyRecord("google_signin_record_uid", "signin", "oauth-client", instance=True),
    LegacyRecord("postscanmail_record_uid", "postscanmail", "api-key"),
    LegacyRecord("zoom_record_uid", "zoom", "app"),
)


class CredentialMissing(LookupError):
    """Neither the vault path nor an ``.env`` record UID gives the credential."""


def legacy_record(env_key: str, portal_keys: Iterable[str] = ()) -> LegacyRecord | None:
    """The row for ``env_key``: a known key, or a vendor portal's (``<portal key>_record_uid``); None for any other."""
    key = env_key.lower()
    known = next((r for r in LEGACY if r.env_key == key), None)
    if known is not None:
        return known
    if key.endswith(SUFFIX):
        stem = key[: -len(SUFFIX)]
        if stem in {p.lower() for p in portal_keys}:
            return LegacyRecord(key, VENDOR_PORTAL, stem.replace("_", "-"))
    return None


def legacy_key(integration: str, name: str) -> str:
    """The ``.env`` key that names this credential's Keeper record today, or ""."""
    known = next((r for r in LEGACY if r.integration == integration and r.name == name), None)
    if known is not None:
        return known.env_key
    if integration == VENDOR_PORTAL:
        return name.replace("-", "_") + SUFFIX
    return ""


_noted: set[str] = set()


def _note_fallback(env_key: str, path: str) -> None:
    if env_key in _noted:
        return
    _noted.add(env_key)
    log.warning("deprecated: %s in .env names this credential; `jason vault migrate` moves it to %s", env_key, path)


def credential(community: str, integration: str, name: str, *, store: SecretStore | None = None,
               record_uids: Mapping[str, str] | None = None,
               load_record: Callable[[str], Mapping[str, str]] | None = None,
               instance: bool | None = None) -> Secret:
    """The credential at its vault path, else the Keeper record its ``.env`` key names (logged as deprecated).

    ``community`` is the profile's key; an installation's credential (``instance=True``, or a ``LEGACY`` row marked
    instance) reads ``jason/instance/instance/...``. ``record_uids`` is ``Settings.record_uids``; ``load_record`` reads
    a Keeper record's fields by UID (``KeeperStore.load_by_uid``). A ``KeeperAuthRequired`` from either is raised.
    """
    env_key = legacy_key(integration, name)
    row = legacy_record(env_key) if env_key else None
    if instance is None:
        instance = bool(row and row.instance)
    path = vault_path(INSTANCE if instance else community, integration, name)
    if store is not None:
        found = store.get(path)
        if found:
            return found
    uid = (record_uids or {}).get(env_key, "") if env_key else ""
    if uid and load_record is not None:
        fields = Secret(load_record(uid))
        if fields:
            _note_fallback(env_key, path)
            return fields
    where = f" or {env_key} in .env" if env_key else ""
    raise CredentialMissing(f"no credential at {path}{where}")


class MigrationState(str, Enum):
    COPY = "copy"                  # planned: the .env record goes to the path
    IN_VAULT = "in vault"          # the path is already set; left alone
    NOT_CHECKED = "not checked"    # the vault did not answer; would copy if the path is empty
    UNMAPPED = "unmapped"          # a *_record_uid key with no path: a person decides


@dataclass(frozen=True)
class MigrationStep:
    env_key: str
    path: str
    state: MigrationState


def plan_migration(community: str, record_uids: Mapping[str, str], *, portal_keys: Iterable[str] = (),
                   store: SecretStore | None = None) -> tuple[list[MigrationStep], str]:
    """Each ``*_record_uid`` key that is set, with its path and whether it is already in the vault. Returns the steps
    and, when the vault did not answer, why (the step's state is then ``NOT_CHECKED``)."""
    portals = tuple(portal_keys)
    steps: list[MigrationStep] = []
    problem = ""
    for key in sorted(k for k, v in record_uids.items() if v and k.lower().endswith(SUFFIX)):
        row = legacy_record(key, portals)
        if row is None:
            steps.append(MigrationStep(key, "", MigrationState.UNMAPPED))
            continue
        path = row.path(community)
        state = MigrationState.COPY
        if store is None:
            state = MigrationState.NOT_CHECKED
        elif not problem:
            try:
                state = MigrationState.IN_VAULT if store.describe(path).is_set else MigrationState.COPY
            except Exception as exc:  # noqa: BLE001 - KeeperAuthRequired and the like: plan without the vault
                problem = f"{type(exc).__name__}: {exc}"
                state = MigrationState.NOT_CHECKED
        else:
            state = MigrationState.NOT_CHECKED
        steps.append(MigrationStep(key, path, state))
    return steps, problem


@dataclass(frozen=True)
class MigrationResult:
    step: MigrationStep
    outcome: str        # "copied", "already in the vault", "source record not found", "source record is empty"


def migrate(steps: Iterable[MigrationStep], store: SecretStore, record_uids: Mapping[str, str],
            load_record: Callable[[str], Mapping[str, str]], *, by: str = "") -> list[MigrationResult]:
    """Copy each planned step's record to its path, create only: a path already set is left as it is."""
    results = []
    for step in steps:
        if step.state not in (MigrationState.COPY, MigrationState.NOT_CHECKED):
            continue
        try:
            fields = Secret(load_record(record_uids[step.env_key]))
        except LookupError:
            results.append(MigrationResult(step, "source record not found"))
            continue
        if not fields:
            results.append(MigrationResult(step, "source record is empty"))
            continue
        try:
            store.put(step.path, fields, if_version=0, by=by)
        except VersionConflict:
            results.append(MigrationResult(step, "already in the vault"))
            continue
        results.append(MigrationResult(step, "copied"))
    return results


__all__ = ["CredentialMissing", "LEGACY", "LegacyRecord", "MigrationResult", "MigrationState", "MigrationStep",
           "VENDOR_PORTAL", "credential", "legacy_key", "legacy_record", "migrate", "plan_migration"]
