"""The community's private facts, kept apart from its specification so the specification can be shared.

The specification (the profile's package) holds rules: patterns, ranges, kinds, the law. A private fact (an account
number, a person's name or address, a settlement figure, counsel's direct contact) lives under ``<data>/spec``, which is
never checked in, and each profile has its own:

- ``spec/<profile>.json``: the profile's own facts file, the answers onboarding records (``facts``, ``leads``);
- ``spec/<profile>/<topic>.json``: one file per topic (``bank_accounts``, ``cases``, ``holds``, ``senders``,
  ``utility_accounts``), read by ``facts(topic)``.

``facts(name)`` reads the active profile's; a missing file is an empty answer, so a checkout without the private data
still runs, with those facts absent. A second association never reads the first one's topics.

The default profile's topic files were kept at ``spec/<topic>.json`` before the topics were per profile. They are still
read for the default profile (and only for it) when its own folder has no copy; ``jason spec --migrate`` copies them
into ``spec/<profile>/``. The folder is ``JASON_SPEC_DIR`` when set, else ``spec`` in the data folder beside this
checkout (``jason.config.data_root``).
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


def spec_dir() -> Path:
    """The private facts folder that holds every profile's facts."""
    env = os.environ.get("JASON_SPEC_DIR")
    if env:
        return Path(env)
    from jason.config import data_root

    return data_root() / "spec"


def default_profile() -> str:
    from jason.community.profile import DEFAULT_PROFILE

    return DEFAULT_PROFILE


def profile_of(profile: str = "") -> str:
    """``profile``, else the active profile's name (reading it loads no profile), else the default profile's."""
    if profile:
        return profile
    try:
        from jason.community.profile import profile_name

        return profile_name()
    except Exception:  # noqa: BLE001 - a name that is not a profile's reads as the default, as the data folder does
        return default_profile()


def profile_dir(profile: str = "") -> Path:
    """``<spec>/<profile>/``: the profile's topic files."""
    return spec_dir() / profile_of(profile)


def legacy_path(name: str) -> Path:
    """``<spec>/<name>.json``: where the default profile's topic was kept before topics were per profile."""
    return spec_dir() / f"{name}.json"


def path_of(name: str, profile: str = "", *, folder: Path | None = None) -> Path:
    """The file ``facts(name, profile=profile)`` reads: the profile's own facts file when ``name`` is the profile,
    else its topic file, else (the default profile only) the legacy topic file. The topic file's path when none
    exists. ``folder`` is the private facts folder when not ``spec_dir()`` (a writer given its own)."""
    who = profile_of(profile)
    root = Path(folder) if folder is not None else spec_dir()
    if name == who:
        return root / f"{who}.json"
    own = root / who / f"{name}.json"
    if not own.is_file() and who == default_profile():
        legacy = root / f"{name}.json"
        if legacy.is_file():
            return legacy
    return own


@lru_cache(maxsize=None)
def _read(path: str, mtime: float) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def facts(name: str, default: Any = None, *, profile: str = "") -> Any:
    """The profile's private facts named ``name`` (a topic, or the profile's own name for its own facts file), or
    ``default`` (an empty dict when not given) when there are none. ``profile`` is the active one by default; a profile's
    own module names itself, so its facts never depend on which profile is active."""
    path = path_of(name, profile)
    if not path.is_file():
        return {} if default is None else default
    return _read(str(path), path.stat().st_mtime)


def write(name: str, value: Any, *, profile: str = "") -> Path:
    """Save a private fact topic in the profile's own folder (used when moving facts out of the specification)."""
    who = profile_of(profile)
    path = spec_dir() / f"{who}.json" if name == who else spec_dir() / who / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


__all__ = ["default_profile", "facts", "legacy_path", "path_of", "profile_dir", "profile_of", "spec_dir", "write"]
