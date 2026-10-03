"""Who may use this installation of jason, above any one community: its admins, the managers of a portfolio of
communities, and the installation's own console sign-in.

A community (a profile) keeps its own officers and its own Google Sign-In (``Community.officers``,
``Community.sign_in``). jason itself keeps the people who work across communities, in private files under
``data/access`` (``JASON_ACCESS_DIR`` when set), never checked in:

- ``admins.json``: ``[{"name": "...", "email": "..."}]``. jason's overall administrators: they may sign in to every
  community's console, and with ``jason-web --dev`` view it as any person or office (writes refused meanwhile).
- ``managers.json``: ``[{"name": "...", "email": "...", "communities": ["mystique", ...]}]``. A manager of a portfolio
  is the manager (``OfficerRole.MANAGER``, approving "the manager") of each community in their list; ``"*"`` is every
  community.
- ``sign_in.json``: the installation's own sign-in clients, in the shape of a community's ``sign_in.json``: for
  admins and managers whose accounts are not in a community's Workspace (a management company's own domain), and
  for a community that sets up none of its own.

Admin is not an office: it reaches no community's approvals. Being an admin or a manager decides who may sign in and
what the console offers them; what anyone may approve is still the community's roster.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jason.community.base import IdentityProvider, Officer, OfficerRole, SignInProvider

ALL = "*"


@dataclass(frozen=True)
class Admin:
    """One of jason's overall administrators (``admins.json``)."""

    name: str
    email: str


@dataclass(frozen=True)
class Manager:
    """A manager of a portfolio of communities (``managers.json``): the profile keys they manage, or ``"*"``."""

    name: str
    email: str
    communities: tuple[str, ...] = ()

    def manages(self, community: str) -> bool:
        return ALL in self.communities or community in self.communities


def access_dir() -> Path:
    env = os.environ.get("JASON_ACCESS_DIR", "").strip()
    if env:
        return Path(env)
    from jason.config import data_root

    return data_root() / "access"


def _rows(name: str, root: Path | None = None) -> list[dict[str, Any]]:
    path = (root or access_dir()) / f"{name}.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _person(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("name", "") or "").strip(), str(row.get("email", "") or "").strip().lower()


def admins(root: Path | None = None) -> tuple[Admin, ...]:
    return tuple(Admin(n, e) for n, e in map(_person, _rows("admins", root)) if n and e)


def managers(root: Path | None = None) -> tuple[Manager, ...]:
    out = []
    for row in _rows("managers", root):
        name, email = _person(row)
        given = row.get("communities", [])
        communities = tuple(str(c).strip() for c in (given if isinstance(given, list) else [given]) if str(c).strip())
        if name and email:
            out.append(Manager(name, email, communities))
    return tuple(out)


def officers_with_managers(officers: Any, community: str, root: Path | None = None) -> tuple[Officer, ...]:
    """The community's officers, and each manager whose portfolio holds ``community`` as its manager (approving "the
    manager"), unless that person already holds the manager's seat there."""
    rows = list(officers)
    for m in managers(root):
        if not m.manages(community):
            continue
        if any(o.role is OfficerRole.MANAGER and (o.name == m.name or (o.email and o.email.lower() == m.email))
               for o in rows):
            continue
        rows.append(Officer(OfficerRole.MANAGER, m.name, ("the manager",), m.email))
    return tuple(rows)


def community_officers() -> tuple[Officer, ...]:
    """The active community's officers with its portfolio managers (``officers_with_managers``)."""
    from jason.community import community
    from jason.community.profile import profile_name

    return officers_with_managers(community().officers(), profile_name())


def providers_from(rows: Any) -> tuple[SignInProvider, ...]:
    """``sign_in.json`` rows as ``SignInProvider`` records; a row with an unknown provider or no record is skipped."""
    out = []
    for i, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            continue
        uid = str(row.get("record_uid", "") or "").strip()
        try:
            kind = IdentityProvider(str(row.get("provider", "google") or "google").strip().lower())
        except ValueError:
            continue
        if not uid:
            continue
        domains = row.get("domains", [])
        out.append(SignInProvider(key=str(row.get("key", "") or f"{kind.value}-{i + 1}").strip(), record_uid=uid,
                                  provider=kind, label=str(row.get("label", "") or "").strip(),
                                  domains=tuple(str(d).strip().lower() for d in (domains if isinstance(domains, list) else [domains])
                                                if str(d).strip())))
    return tuple(out)


def installation_sign_in(root: Path | None = None) -> tuple[SignInProvider, ...]:
    return providers_from(_rows("sign_in", root))


def write_sign_in(path: Path, provider: SignInProvider) -> Path:
    """Add or replace (by ``key``) one provider in a ``sign_in.json``; the file is private and never checked in."""
    rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    rows = [r for r in rows if isinstance(r, dict) and r.get("key") != provider.key]
    row: dict[str, Any] = {"key": provider.key, "provider": provider.provider.value, "record_uid": provider.record_uid}
    if provider.domains:
        row["domains"] = list(provider.domains)
    if provider.label:
        row["label"] = provider.label
    rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return path


__all__ = ["ALL", "Admin", "Manager", "access_dir", "admins", "community_officers", "installation_sign_in", "managers",
           "officers_with_managers", "providers_from",
           "write_sign_in"]
