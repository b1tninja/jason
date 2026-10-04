"""General code reaches the active profile through ``community()``, never the older name ``mystique()`` (AGENTS.md,
"Dependencies point one way"; lesson ``profile-old-name``). The alias stays defined in ``jason.community`` for other
callers; jason's own code does not import or call it. ``RATCHET`` holds the files not yet converted, with their
count; a count may only go down, and a converted file leaves the ratchet."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "jason"
DEFINED_IN = "community/__init__.py"           # where the alias itself is defined and exported
RATCHET: dict[str, int] = {}                    # every file converted (2026-10-04)


def _uses(tree: ast.AST) -> int:
    """Imports of ``mystique`` from ``jason.community`` and calls of a bare ``mystique(...)``."""
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "jason.community":
            n += sum(1 for a in node.names if a.name == "mystique")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "mystique":
            n += 1
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "mystique":
            n += 1
    return n


def _found() -> dict[str, int]:
    out = {}
    for path in SRC.rglob("*.py"):
        rel = path.relative_to(SRC).as_posix()
        if rel == DEFINED_IN:
            continue
        n = _uses(ast.parse(path.read_text(encoding="utf-8")))
        if n:
            out[rel] = n
    return out


def test_general_code_calls_community_not_the_old_name():
    found = _found()
    worse = {k: v for k, v in found.items() if v > RATCHET.get(k, 0)}
    assert not worse, ("call `from jason.community import community as active` and `active()`, not mystique(): "
                       + ", ".join(f"{k} ({v})" for k, v in sorted(worse.items())))


def test_the_ratchet_only_goes_down():
    found = _found()
    lower = {k: (v, found.get(k, 0)) for k, v in RATCHET.items() if found.get(k, 0) < v}
    assert not lower, ("fewer mystique() uses than RATCHET allows; lower or remove the entry: "
                       + ", ".join(f"{k} {was} -> {now}" for k, (was, now) in sorted(lower.items())))


def test_the_alias_is_still_defined():
    from jason.community import community, mystique

    assert mystique() is community()
