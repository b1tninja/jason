"""Choose and load the association profile: the specification package for one community.

jason is the implementation; a profile is the data for one association (its buildings, rules,
folders, and documents) as a `Community` subclass in a package. Mystique Community Association is
the profile ``mystique``. The active profile is ``JASON_PROFILE`` (environment or .env), else
``mystique``.

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
from importlib.metadata import entry_points
from pathlib import Path
from types import ModuleType

from jason.community.base import Community

DEFAULT_PROFILE = "mystique"
ENTRY_POINT_GROUP = "jason.profiles"
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_LOADED: dict[str, Community] = {}


class ProfileNotFound(LookupError):
    """No package for the named profile."""


def profile_name() -> str:
    """The active profile: ``JASON_PROFILE`` from the environment, then from .env, else ``mystique``."""
    name = os.environ.get("JASON_PROFILE", "").strip()
    if not name:
        name = _env_file_value("JASON_PROFILE")
    return _checked(name or DEFAULT_PROFILE)


def _env_file_value(key: str) -> str:
    try:
        from dotenv import dotenv_values

        from jason.config import resolve_env_path

        path = resolve_env_path(None)
        if not path.is_file():
            return ""
        values = dotenv_values(path)
    except Exception:
        return ""
    for k, v in values.items():
        if k.upper() == key and v:
            return str(v).strip().strip("'\"")
    return ""


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
    for parent in here.parents:
        for candidate in (parent / "profiles" / name, parent / name):
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
