"""Vault paths: ``jason/<scope>/<community or "instance">/<integration>/<name>`` (docs/integrations-design.md, The vault).

The scope is ``community`` or ``instance``. An instance secret's owner segment is the word ``instance``, so a community
can never be named ``instance``. The name may hold more than one segment (``token/<account>``). Every segment is
lower case; a community and an integration are slugs (letters, digits, hyphens), and a name segment may also hold
``.``, ``_``, ``@``, and ``+`` (an account's address). A path names a secret; it is not one, and may be printed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

ROOT = "jason"
INSTANCE = "instance"
MAX_LENGTH = 255

_SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
_NAME_SEGMENT = re.compile(r"[a-z0-9](?:[a-z0-9._@+-]{0,126}[a-z0-9])?")


class Scope(str, Enum):
    """Whose secret it is: one community's, or the installation's."""

    COMMUNITY = "community"
    INSTANCE = "instance"


class InvalidVaultPath(ValueError):
    """A vault path, or a part of one, that does not follow the scheme."""


@dataclass(frozen=True)
class VaultPath:
    """A parsed vault path. ``str()`` gives the path."""

    scope: Scope
    owner: str          # the community's key, or "instance"
    integration: str
    name: str           # one or more segments joined by "/"

    @property
    def path(self) -> str:
        return f"{ROOT}/{self.scope.value}/{self.owner}/{self.integration}/{self.name}"

    def __str__(self) -> str:
        return self.path


def _slug(value: str, what: str) -> str:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        raise InvalidVaultPath(f"{what} {value!r} is not a lower-case slug (letters, digits, hyphens)")
    return value


def _name(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise InvalidVaultPath("a vault name is empty")
    for segment in value.split("/"):
        if not _NAME_SEGMENT.fullmatch(segment):
            raise InvalidVaultPath(f"name segment {segment!r} is not lower case letters, digits, and . _ @ + -")
    return value


def vault_path(community: str, integration: str, name: str) -> str:
    """The path of ``name`` for ``integration``: a community's (``community`` is its key) or the installation's
    (``community`` is ``"instance"``)."""
    owner = _slug(community, "community")
    scope = Scope.INSTANCE if owner == INSTANCE else Scope.COMMUNITY
    vp = VaultPath(scope, owner, _slug(integration, "integration"), _name(name))
    if len(vp.path) > MAX_LENGTH:
        raise InvalidVaultPath(f"a vault path is at most {MAX_LENGTH} characters")
    return vp.path


def parse_path(path: str) -> VaultPath:
    """``path`` as a ``VaultPath``, or ``InvalidVaultPath`` saying what is wrong."""
    if not isinstance(path, str):
        raise InvalidVaultPath("a vault path is a string")
    if len(path) > MAX_LENGTH:
        raise InvalidVaultPath(f"a vault path is at most {MAX_LENGTH} characters")
    parts = path.split("/")
    if len(parts) < 5 or parts[0] != ROOT:
        raise InvalidVaultPath(f"{path!r} is not jason/<scope>/<community or instance>/<integration>/<name>")
    try:
        scope = Scope(parts[1])
    except ValueError:
        raise InvalidVaultPath(f"scope {parts[1]!r} is not community or instance") from None
    owner = _slug(parts[2], "community")
    if scope is Scope.INSTANCE and owner != INSTANCE:
        raise InvalidVaultPath("an instance path's owner segment is \"instance\"")
    if scope is Scope.COMMUNITY and owner == INSTANCE:
        raise InvalidVaultPath("\"instance\" is not a community's key")
    return VaultPath(scope, owner, _slug(parts[3], "integration"), _name("/".join(parts[4:])))


def check_path(path: str) -> str:
    """``path`` when it follows the scheme; ``InvalidVaultPath`` otherwise."""
    return parse_path(path).path


def check_prefix(prefix: str) -> str:
    """A listing prefix: ``jason/`` or a longer prefix of a path."""
    if not isinstance(prefix, str) or not (prefix == ROOT or prefix.startswith(ROOT + "/")):
        raise InvalidVaultPath(f"a listing prefix starts with {ROOT}/")
    segments = prefix.split("/")
    if any(not s for s in segments[:-1]) or any(s in (".", "..") for s in segments):
        raise InvalidVaultPath("a listing prefix holds no empty, '.', or '..' segment")
    return prefix


__all__ = ["INSTANCE", "InvalidVaultPath", "ROOT", "Scope", "VaultPath", "check_path", "check_prefix", "parse_path",
           "vault_path"]
