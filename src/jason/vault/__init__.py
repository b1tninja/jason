"""The credential vault: one ``SecretStore`` interface, secrets named by path (docs/integrations-design.md, The vault).

- ``paths``: ``jason/<scope>/<community or "instance">/<integration>/<name>``, ``vault_path`` and its checks.
- ``store``: the ``SecretStore`` protocol, ``Secret`` (a value that never shows itself), ``VaultEntry``, and
  ``MemoryStore`` for tests.
- ``keeper``: ``KeeperStore``, the backend now: a Keeper record titled with the path, in a folder named ``jason``.
- ``resolver``: ``credential`` (the vault path first, then today's ``.env`` record UID) and the migration plan.

Not to be confused with Google Vault (``jason.google.vault``, legal holds). Importing this package loads no profile
and opens no Keeper session.
"""

from __future__ import annotations

from jason.vault.paths import INSTANCE, InvalidVaultPath, Scope, VaultPath, check_path, parse_path, vault_path
from jason.vault.resolver import (
    LEGACY,
    CredentialMissing,
    LegacyRecord,
    MigrationState,
    MigrationStep,
    credential,
    legacy_key,
    legacy_record,
    migrate,
    plan_migration,
)
from jason.vault.store import MemoryStore, Secret, SecretStore, VaultEntry, VaultError, VersionConflict

__all__ = [
    "CredentialMissing",
    "INSTANCE",
    "InvalidVaultPath",
    "LEGACY",
    "LegacyRecord",
    "MemoryStore",
    "MigrationState",
    "MigrationStep",
    "Scope",
    "Secret",
    "SecretStore",
    "VaultEntry",
    "VaultError",
    "VaultPath",
    "VersionConflict",
    "check_path",
    "credential",
    "legacy_key",
    "legacy_record",
    "migrate",
    "parse_path",
    "plan_migration",
    "vault_path",
]
