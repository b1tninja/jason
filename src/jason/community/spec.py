"""Load the active profile package (`jason.community.profile`). The facts are classes in that package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason.community.base import Community, TransactionRule
from jason.community.symbols import Utility


def find_spec_root(marker: str | None = None) -> Path:
    """The active profile's package folder (``mystique/``), or the named one's."""
    from jason.community.profile import profile_root

    root = profile_root(marker)
    if root is None:
        raise FileNotFoundError(f"profile {marker or 'active'} is an installed package, not a folder")
    return root


def spec_module(name: str):
    """One module of the active profile's package (``templates``, ``forms``, ...)."""
    from jason.community.profile import profile_module

    return profile_module(name)


def load_mystique() -> Community:
    """A new instance of the active profile's `Community` class (named for the first profile)."""
    from jason.community.profile import profile_class, profile_package

    return profile_class(profile_package())()


def first_utility(
    tx: dict[str, Any],
    rules: tuple[TransactionRule, ...] | list[TransactionRule],
) -> Utility | None:
    """First listed rule that matches and is not blocked by an earlier hit."""
    hits = [rule.utility for rule in rules if rule.matches(tx)]
    for rule in rules:
        if rule.utility not in hits:
            continue
        if any(block in hits for block in rule.blocked_by):
            continue
        return rule.utility
    return None
