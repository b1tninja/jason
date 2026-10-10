"""Choose and load the association profile: the specification package for one community.

jason is the implementation; a profile is the data for one association (its buildings, rules,
folders, and documents) as a `Community` subclass in a package. Mystique Community Association is
the profile ``mystique``. Which profile is active is ``resolve_community()``: the ``--community`` flag, then
``JASON_COMMUNITY``, then ``JASON_PROFILE`` (the old name), then the project's .env, then the user config
(``jason use KEY``), then the compatibility shim for the built-in default (docs/tenancy.md, section 3).

A profile package is found, in order, at ``JASON_PROFILE_DIR``; at ``profiles/<name>/`` or
``<name>/`` in a folder above this file; or as an installed package registered under the
``jason.profiles`` entry point group. It is imported as ``jason_<name>``. Its ``PROFILE``
attribute names the class; a package without one must export exactly one `Community` subclass.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import re
import sys
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType
from typing import Any

from jason.community.base import Community

DEFAULT_PROFILE = "mystique"
ENTRY_POINT_GROUP = "jason.profiles"
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_LOADED: dict[str, Community] = {}


class ProfileNotFound(LookupError):
    """No package for the named profile."""


class CommunityNotChosen(ProfileNotFound):
    """No community is chosen, and the compatibility shim does not apply: the command stops (exit code 2) and says
    which profiles are installed. jason never guesses between them."""


COMMUNITY_VAR = "JASON_COMMUNITY"
ALIAS_VAR = "JASON_PROFILE"               # the old name of the same setting; still read
VIA_VAR = "JASON_COMMUNITY_VIA"           # set with the global --community flag, so the source reads as the flag
SHIM_VAR = "JASON_DEFAULT_COMMUNITY_SHIM"  # 0 turns the built-in default off
NOTICED_VAR = "JASON_COMMUNITY_NOTICED"   # once per process tree: which notices have been printed
FLAG_SOURCE = "--community flag"
_OFF = ("0", "false", "no", "off")


@dataclass(frozen=True)
class Resolved:
    """Which community, and where the choice came from. ``alias`` is a choice made with the old name
    ``JASON_PROFILE``; ``shim`` one the code made (the only installed profile, or the built-in default)."""

    name: str
    source: str
    alias: bool = False
    shim: bool = False


def installed_profiles() -> list[dict[str, Any]]:
    """Every profile this checkout can load, by the same search as ``profile_package``: the folders beside jason
    (``profiles/<name>/`` and ``<name>/`` with a package inside), ``JASON_PROFILE_DIR``, and the ``jason.profiles``
    entry points. Each with where it was found. Loads none of them and reads no setting of which is active."""
    found: dict[str, dict[str, Any]] = {}
    here = Path(__file__).resolve().parents[3]
    for folder in (here / "profiles", here):
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir()):
            if child.is_dir() and _NAME.match(child.name) and (child / "__init__.py").is_file() and child.name not in ("src", "tests", "docs", "scripts", "ui", "data"):
                found.setdefault(child.name, {"name": child.name, "where": str(child)})
    custom = os.environ.get("JASON_PROFILE_DIR", "").strip()
    if custom and Path(custom).is_dir():
        found.setdefault(Path(custom).name, {"name": Path(custom).name, "where": custom})
    try:
        for ep in entry_points(group=ENTRY_POINT_GROUP):
            found.setdefault(ep.name, {"name": ep.name, "where": f"entry point {ep.value}"})
    except Exception:  # an environment without importlib.metadata groups
        pass
    return list(found.values())


def profiles() -> list[dict[str, Any]]:
    """``installed_profiles()`` with whether each is the active one. Loads none of them; when no community can be
    resolved (``CommunityNotChosen``) none is active."""
    try:
        active = profile_name()
    except CommunityNotChosen:
        active = ""
    return [{**row, "active": row["name"] == active} for row in installed_profiles()]


def _dotenv(path: Path) -> dict[str, str]:
    try:
        from dotenv import dotenv_values

        if not path.is_file():
            return {}
        return {k.upper(): str(v).strip().strip("'\"") for k, v in dotenv_values(path).items() if v}
    except Exception:  # noqa: BLE001 - an unreadable .env sets nothing
        return {}


def _file_sources() -> list[tuple[str, dict[str, str]]]:
    """The two .env files in the order a choice is looked for: the project's, then the user config."""
    try:
        from jason.config import resolve_env_path, user_config_path

        return [("project .env", _dotenv(resolve_env_path(None))), ("user config", _dotenv(user_config_path()))]
    except Exception:  # noqa: BLE001
        return []


def _shim_on(files: list[tuple[str, dict[str, str]]]) -> bool:
    value = os.environ.get(SHIM_VAR, "").strip()
    if not value:
        value = next((v[SHIM_VAR] for _, v in files if v.get(SHIM_VAR)), "")
    return value.strip().lower() not in _OFF


def resolve_community() -> Resolved:
    """Which community this process serves, and where that came from. Pure: it reads the environment and the two
    .env files and loads no profile. In order, the first that is set wins:

    1. the global ``--community KEY`` flag (it sets ``JASON_COMMUNITY`` and ``JASON_COMMUNITY_VIA``);
    2. ``JASON_COMMUNITY`` in the environment;
    3. ``JASON_PROFILE`` in the environment (the old name, still read);
    4. the project's .env, ``JASON_COMMUNITY`` then ``JASON_PROFILE``;
    5. the user config (``jason use KEY`` writes ``JASON_COMMUNITY`` there), the same two keys;
    6. the compatibility shim: the only installed profile; else the built-in ``DEFAULT_PROFILE`` unless
       ``JASON_DEFAULT_COMMUNITY_SHIM=0``.

    With none of these and the shim off, raises ``CommunityNotChosen`` naming the installed profiles."""
    named = os.environ.get(COMMUNITY_VAR, "").strip()
    if named:
        return Resolved(_checked(named), os.environ.get(VIA_VAR, "").strip() or COMMUNITY_VAR)
    old = os.environ.get(ALIAS_VAR, "").strip()
    if old:
        return Resolved(_checked(old), f"{ALIAS_VAR} (old name)", alias=True)
    files = _file_sources()
    for label, values in files:
        if values.get(COMMUNITY_VAR):
            return Resolved(_checked(values[COMMUNITY_VAR]), f"{label}, {COMMUNITY_VAR}")
        if values.get(ALIAS_VAR):
            return Resolved(_checked(values[ALIAS_VAR]), f"{label}, {ALIAS_VAR} (old name)", alias=True)
    names = [row["name"] for row in installed_profiles()]
    if len(names) == 1:
        return Resolved(names[0], "the only installed profile", shim=True)
    if _shim_on(files):
        return Resolved(DEFAULT_PROFILE, "built-in default", shim=True)
    have = ", ".join(sorted(names)) or "none"
    raise CommunityNotChosen(
        f"no community chosen, and this machine has {len(names)} ({have}).\n"
        "Choose one: jason --community KEY ...   or   jason use KEY   (or set JASON_COMMUNITY)")


def announce(resolved: Resolved, *, stream: Any = None) -> None:
    """The one-line notices a choice calls for, once per process tree: the shim in use, or the old setting name."""
    out = stream if stream is not None else sys.stderr
    done = os.environ.get(NOTICED_VAR, "").split(",")
    for kind, on in (("shim", resolved.shim), ("alias", resolved.alias)):
        if not on or kind in done:
            continue
        done.append(kind)
        os.environ[NOTICED_VAR] = ",".join(d for d in done if d)
        if kind == "shim":
            print(f"community: {resolved.name} ({resolved.source}; set JASON_COMMUNITY or run `jason use KEY`)", file=out)
        else:
            print(f"community: JASON_PROFILE is the old name of {COMMUNITY_VAR}; {resolved.name} is chosen by it "
                  f"({resolved.source})", file=out)


def profile_name() -> str:
    """The active profile's name: ``resolve_community()``'s answer, with its one-line notices (the shim, the old setting
    name). Loads no profile. Raises ``CommunityNotChosen`` when none is chosen and the shim is off."""
    resolved = resolve_community()
    announce(resolved)
    return resolved.name


def _checked(name: str) -> str:
    name = name.strip().lower()
    if not _NAME.match(name):
        raise ProfileNotFound(f"not a profile name: {name!r}")
    return name


def package_name(name: str) -> str:
    """The module name a profile is imported under (``jason_mystique``)."""
    return f"jason_{_checked(name)}"


def profile_root(name: str | None = None) -> Path | None:
    """The folder holding the profile package, or None when it is an installed package."""
    name = _checked(name or profile_name())
    explicit = os.environ.get("JASON_PROFILE_DIR", "").strip()
    if explicit:
        root = Path(explicit)
        if (root / "__init__.py").is_file():
            return root
        raise ProfileNotFound(f"JASON_PROFILE_DIR has no __init__.py: {root}")
    here = Path(__file__).resolve()
    jason_tree = here.parents[1]                   # src/jason: its own subpackages are never a profile
    for parent in here.parents:
        for candidate in (parent / "profiles" / name, parent / name):
            if candidate.resolve().is_relative_to(jason_tree):
                continue
            if (candidate / "__init__.py").is_file():
                return candidate
    return None


def profile_package(name: str | None = None) -> ModuleType:
    """Import the profile package (once) and return it."""
    name = _checked(name or profile_name())
    module_name = package_name(name)
    if module_name in sys.modules:
        return sys.modules[module_name]
    root = profile_root(name)
    if root is not None:
        spec = importlib.util.spec_from_file_location(
            module_name, root / "__init__.py", submodule_search_locations=[str(root)]
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {root}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
        return module
    for point in entry_points(group=ENTRY_POINT_GROUP):
        if point.name == name:
            module = importlib.import_module(point.value.split(":")[0])
            sys.modules[module_name] = module
            return module
    raise ProfileNotFound(f"no profile {name!r}: set JASON_PROFILE_DIR, add profiles/{name}/, or install a package "
                          f"registered under the {ENTRY_POINT_GROUP!r} entry points")


def profile_class(module: ModuleType) -> type[Community]:
    """The package's `Community` class: ``PROFILE``, else its one exported subclass."""
    named = getattr(module, "PROFILE", None)
    if isinstance(named, type) and issubclass(named, Community):
        return named
    found = {value for value in vars(module).values()
             if isinstance(value, type) and issubclass(value, Community) and value is not Community}
    if len(found) != 1:
        raise ProfileNotFound(f"{module.__name__} must set PROFILE to its Community class")
    return found.pop()


def load_profile(name: str | None = None) -> Community:
    """One instance of the profile's `Community` class, cached by name."""
    name = _checked(name or profile_name())
    if name not in _LOADED:
        _LOADED[name] = profile_class(profile_package(name))()
    return _LOADED[name]


def profile_module(module: str, name: str | None = None) -> ModuleType:
    """One module of the profile package (``forms``, ``templates``, ...)."""
    package = profile_package(name)
    return importlib.import_module(f"{package.__name__}.{module}")
