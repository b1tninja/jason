"""Where jason's Google refresh tokens are kept, and how a command reads them from any working directory.

A refresh token is a credential, so the credential vault (Keeper) is its system of record. The local file
(``secrets/google-token.json`` and its siblings) is a per-checkout cache: a git worktree or another working directory has
none, and used to fail with ``GoogleAuthRequired`` although the vault held the means to sign in.

``GoogleTokenStore`` is the small interface: ``load(name)`` gives ``{"refresh_token", "scopes"}`` or None, and
``save(name, refresh_token, scopes)`` stores one. A *name* is one of ``NAMES``: ``drive`` (the Drive, Docs, Sheets, Gmail,
Calendar and Forms scopes together), ``tasks``, ``vault`` and ``photos``, each a token of its own so granting a new API
never asks the others to consent again.

- ``VaultTokenStore``: the vault path ``jason/community/<profile>/google-workspace/token/<name>``, fields
  ``refresh_token`` and ``scopes`` (space separated). One token set per community; an account label is not added until a
  community signs in with more than one Google account (docs/integrations-design.md, build step 3).
- ``FileTokenStore``: the files as before, where ``google_oauth_token_file`` puts them.
- ``LayeredTokenStore``: the two together. **Reads are vault first, then the file.** The vault is the record every checkout
  shares, so a worktree finds the token there and a token a person re-authorized on another machine wins over a stale
  local copy. The file is the fallback when the vault holds nothing at the path, **and when the vault cannot be reached
  and the file has a token that covers the scopes** (logged by error name only). A vault that cannot be reached and a
  file that cannot answer is the vault's own error (``KeeperAuthRequired``), never a silent miss. **Writes go to both**
  (the vault when reachable; an unreachable vault is logged and the file still has it).

No token, and no part of one, is ever printed, logged, or put in an error message here.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jason.vault.paths import vault_path

log = logging.getLogger("jason.google.tokens")

INTEGRATION = "google-workspace"
TOKEN_PREFIX = "token"
DRIVE, TASKS, VAULT, PHOTOS = "drive", "tasks", "vault", "photos"
NAMES = (DRIVE, TASKS, VAULT, PHOTOS)

_FILE_NAME = re.compile(r"google-(?P<name>.+)-token\.json")


def name_of_file(file_name: str) -> str:
    """The token's name from its file name: ``google-token.json`` is ``drive``, ``google-tasks-token.json`` is ``tasks``."""
    found = _FILE_NAME.fullmatch(Path(file_name).name)
    return found.group("name") if found else DRIVE


def file_name_of(name: str) -> str:
    return "google-token.json" if name == DRIVE else f"google-{name}-token.json"


def scopes_of(name: str) -> tuple[str, ...]:
    """The scopes the token of this name is asked for now."""
    from jason.google import scopes

    return {DRIVE: scopes.GOOGLE_SCOPES, TASKS: scopes.TASKS_SCOPES, VAULT: scopes.VAULT_SCOPES,
            PHOTOS: scopes.PHOTOS_SCOPES}.get(name, scopes.GOOGLE_SCOPES)


def covers(token: Mapping[str, Any] | None, scopes: tuple[str, ...]) -> bool:
    return bool(token) and set(scopes).issubset(set(token.get("scopes") or ()))   # type: ignore[union-attr]


class GoogleTokenStore(Protocol):
    def load(self, name: str) -> dict[str, Any] | None: ...

    def save(self, name: str, refresh_token: str, scopes: list[str]) -> None: ...


class FileTokenStore:
    """The local token files, beside ``google_oauth_token_file``."""

    def __init__(self, drive_file: str | Path) -> None:
        self._drive = Path(drive_file)

    def path_of(self, name: str) -> Path:
        return self._drive if name == DRIVE else self._drive.with_name(file_name_of(name))

    def load(self, name: str) -> dict[str, Any] | None:
        path = self.path_of(name)
        if not path.is_file():
            return None
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        refresh = str(saved.get("refresh_token") or "") if isinstance(saved, dict) else ""
        return {"refresh_token": refresh, "scopes": list(saved.get("scopes") or [])} if refresh else None

    def save(self, name: str, refresh_token: str, scopes: list[str]) -> None:
        path = self.path_of(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"refresh_token": refresh_token, "scopes": list(scopes)}, indent=2), encoding="utf-8")


class VaultTokenStore:
    """The credential vault: ``jason/community/<community>/google-workspace/token/<name>``."""

    def __init__(self, store: Any, community: str, *, by: str = "") -> None:
        self._store, self.community, self._by = store, community, by

    def path_of(self, name: str) -> str:
        return vault_path(self.community, INTEGRATION, f"{TOKEN_PREFIX}/{name}")

    def load(self, name: str) -> dict[str, Any] | None:
        secret = self._store.get(self.path_of(name))
        refresh = secret.first("refresh_token") if secret else ""
        return {"refresh_token": refresh, "scopes": secret.first("scopes").split()} if refresh else None

    def save(self, name: str, refresh_token: str, scopes: list[str], *, if_version: int | None = None) -> None:
        fields = {"refresh_token": refresh_token, "scopes": " ".join(scopes)}
        self._store.put(self.path_of(name), fields, if_version, by=self._by)


@dataclass(frozen=True)
class Location:
    """Where a token would be read from: ``where`` is ``vault``, ``file`` or ``missing``. ``token`` is the token itself
    (never printed); ``problem`` is the vault's error name when it could not be read."""

    where: str
    token: dict[str, Any] | None = None
    problem: str = ""
    problem_error: Exception | None = None

    def __repr__(self) -> str:
        return f"Location({self.where!r}, problem={self.problem!r})"


class LayeredTokenStore:
    """Vault first, then the file; saves go to both. ``vault`` may be None (no vault session): the file alone."""

    def __init__(self, vault: VaultTokenStore | None, file: FileTokenStore) -> None:
        self.vault, self.file = vault, file

    def locate(self, name: str, scopes: tuple[str, ...] | None = None) -> Location:
        """The first source holding a token that covers ``scopes`` (any token when ``scopes`` is None); failing that
        the first token held at all (the caller sees the shortfall). A vault that cannot be read with no covering file
        token is its own error, kept in ``problem_error``."""
        wanted = scopes if scopes is not None else ()
        from_vault: dict[str, Any] | None = None
        error: Exception | None = None
        if self.vault is not None:
            try:
                from_vault = self.vault.load(name)
            except Exception as exc:  # noqa: BLE001 - KeeperAuthRequired and the like: the file may still answer
                error = exc
        from_file = self.file.load(name)
        for where, token in (("vault", from_vault), ("file", from_file)):
            if token and covers(token, wanted):
                if where == "file" and error is not None:
                    log.warning("the vault did not answer (%s); the token is read from the local file for %s",
                                type(error).__name__, name)
                return Location(where, token, type(error).__name__ if error else "", error)
        if error is not None:
            return Location("missing", None, type(error).__name__, error)
        for where, token in (("vault", from_vault), ("file", from_file)):
            if token:
                return Location(where, token)
        return Location("missing")

    def load(self, name: str, scopes: tuple[str, ...] | None = None) -> dict[str, Any] | None:
        """The token for ``name``: vault first, then the file. A vault error is raised unless the file answers."""
        found = self.locate(name, scopes)
        if found.problem_error is not None and not covers(found.token, scopes or ()):
            raise found.problem_error
        return found.token

    def save(self, name: str, refresh_token: str, scopes: list[str]) -> tuple[str, ...]:
        """Store the token in the file and, when reachable, the vault. The places stored."""
        self.file.save(name, refresh_token, scopes)
        placed = ["file"]
        if self.vault is not None:
            try:
                self.vault.save(name, refresh_token, scopes)
                placed.append("vault")
            except Exception as exc:  # noqa: BLE001 - the sign-in worked; the vault copy is reported, not fatal
                log.warning("the token for %s is saved in the local file only: the vault did not take it (%s)",
                            name, type(exc).__name__)
        return tuple(placed)


def token_store(settings: Any, store: Any = None, community: str = "") -> LayeredTokenStore:
    """The layered store for this installation's token files and, when ``store`` (a ``SecretStore``) is given, the
    community's vault."""
    if store is not None and not community:
        from jason.community.profile import profile_name

        community = profile_name()
    vault = VaultTokenStore(store, community) if store is not None else None
    return LayeredTokenStore(vault, FileTokenStore(settings.google_oauth_token_file))


# ----- status and migration (jason vault) -----


def status_lines(tokens: LayeredTokenStore) -> list[str]:
    """One line a token name: where it is read from, how many scopes it holds, and whether they cover the scopes asked
    now. Never the token."""
    lines = []
    for name in NAMES:
        asked = scopes_of(name)
        found = tokens.locate(name, asked)
        if found.token is None:
            tail = f" (the vault was not read: {found.problem})" if found.problem else ""
            lines.append(f"  {name}: missing{tail}")
            continue
        held = found.token.get("scopes") or []
        fit = "covers the scopes asked now" if covers(found.token, asked) else f"lacks scopes asked now (needs {len(asked)})"
        tail = f"; the vault was not read: {found.problem}" if found.problem else ""
        lines.append(f"  {name}: read from the {found.where}, {len(held)} scopes, {fit}{tail}")
    return lines


@dataclass(frozen=True)
class TokenStep:
    name: str
    path: str
    state: str          # "copy", "in vault", "no file", "not checked"
    scopes: int = 0


def plan_token_migration(tokens: LayeredTokenStore, community: str, *, checked: bool = True) -> list[TokenStep]:
    """Each local token file and whether the vault already holds its path. ``checked`` False when the vault did not
    answer. The ``google-token.before-scopes-*.json`` backups are superseded tokens and are never copied."""
    steps = []
    assert tokens.vault is not None, "a migration needs a vault"
    for name in NAMES:
        path = tokens.vault.path_of(name)
        local = tokens.file.load(name)
        if local is None:
            steps.append(TokenStep(name, path, "no file"))
            continue
        state = "not checked"
        if checked:
            try:
                state = "in vault" if tokens.vault.load(name) else "copy"
            except Exception:  # noqa: BLE001 - plan without the vault
                state = "not checked"
        steps.append(TokenStep(name, path, state, len(local.get("scopes") or [])))
    return steps


def plan_token_lines(steps: list[TokenStep]) -> list[str]:
    lines = ["Google tokens: copy each local token file to its vault path (a path already set is left alone)."]
    for s in steps:
        what = {"copy": "copy", "in vault": "already in the vault", "no file": "no local file",
                "not checked": "copy unless already set"}[s.state]
        lines.append(f"  {s.name} -> {s.path}: {what}" + (f" ({s.scopes} scopes)" if s.scopes else ""))
    return lines


def migrate_tokens(steps: list[TokenStep], tokens: LayeredTokenStore, *, by: str = "") -> list[tuple[TokenStep, str]]:
    """Copy each planned local token to the vault, create only. Outcome words only; never a token."""
    from jason.vault.store import VersionConflict

    assert tokens.vault is not None, "a migration needs a vault"
    out = []
    for s in steps:
        if s.state not in ("copy", "not checked"):
            continue
        local = tokens.file.load(s.name)
        if local is None:
            out.append((s, "local file not found"))
            continue
        try:
            tokens.vault.save(s.name, local["refresh_token"], list(local.get("scopes") or []), if_version=0)
        except VersionConflict:
            out.append((s, "already in the vault"))
            continue
        out.append((s, "copied"))
    return out


__all__ = ["DRIVE", "FileTokenStore", "GoogleTokenStore", "INTEGRATION", "LayeredTokenStore", "Location", "NAMES",
           "PHOTOS", "TASKS", "TOKEN_PREFIX", "TokenStep", "VAULT", "VaultTokenStore", "covers", "file_name_of",
           "migrate_tokens", "name_of_file", "plan_token_lines", "plan_token_migration", "scopes_of", "status_lines",
           "token_store"]
