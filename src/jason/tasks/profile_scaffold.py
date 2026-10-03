"""``jason onboard --new KEY``: a new association's profile package, written from jason's general templates.

The templates are ``src/jason/templates/profile/*.tmpl``. They name no association: each ``{{VARIABLE}}`` is filled
from what the person gave (the key, the name, the county) and the day. The package holds:

- ``__init__.py`` and ``community.py``: a ``Community`` subclass that holds the identity it was given, every other
  method reading a module of rule rows;
- one module per rule-row family a profile usually has (documents, anchors, pins, the declaration, books, outlines,
  living documents, conflicts, parcels, buildings, developers, the board and banking, obligations, the schedule,
  notices, transactions, insurance, utilities, vendors, cases, letter templates, response clocks, lessons, forms), each
  empty, with a docstring saying what goes there and where jason's docs describe it;
- ``docs/README.md``, the instance reference;
- ``notes/``, the private notes, with a ``.gitignore`` that keeps everything in it out of git.

Beside the package, ``data/spec/<key>.json`` holds the profile's private facts, empty. ``write`` refuses to overwrite a
package or a private facts file, and refuses a key that collides with a record address's book or a document key the
active profile maps, another profile, or a jason-mcp tool set (``collisions``). Nothing is written to PayHOA, Google,
or the mail, and no other profile is changed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

TEMPLATES = Path(__file__).resolve().parents[1] / "templates" / "profile"
SUFFIX = ".tmpl"
_VARIABLE = re.compile(r"\{\{([A-Z_]+)\}\}")
# jason-mcp's tool sets: a profile key that reads as one invites JASON_PROFILE and --profile to be confused.
MCP_TOOL_SETS = ("all", "board", "governance", "onboarding")
# A key whose class would shadow the base class it subclasses.
RESERVED = ("community",)


class ScaffoldRefused(ValueError):
    """The scaffold was not written, with every reason."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


@dataclass(frozen=True)
class Scaffold:
    key: str
    name: str
    region: str
    package: Path
    spec: Path
    files: tuple[Path, ...]


def class_name(key: str) -> str:
    """``example_village`` -> ``ExampleVillage``."""
    return "".join(part[:1].upper() + part[1:] for part in key.split("_") if part)


def default_directory(key: str) -> Path:
    """Beside the default profile's package (the folder above it), else the folder above jason's source."""
    from jason.community.profile import DEFAULT_PROFILE, profile_root

    explicit = os.environ.get("JASON_PROFILE_DIR", "")
    root = None
    if not explicit:
        try:
            root = profile_root(DEFAULT_PROFILE)
        except Exception:  # noqa: BLE001
            root = None
    base = root.parent if root is not None else Path(__file__).resolve().parents[3]
    return base / key


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _aliases(community: Any) -> set[str]:
    """The document keys, parts, and aliases the active profile's record addresses and citations answer to."""
    out: set[str] = set()
    try:
        from jason.community.books import entries_of

        for e in entries_of(community):
            out |= {_norm(str(e.document)), _norm(str(e.key)), _norm(str(getattr(e, "part", "") or ""))}
    except Exception:  # noqa: BLE001 - a profile that cannot answer has no aliases to collide with
        pass
    try:
        for d in community.citable_documents():
            out.add(_norm(str(getattr(d, "key", "") or "")))
            out |= {_norm(str(a)) for a in getattr(d, "aliases", ()) or ()}
    except Exception:  # noqa: BLE001
        pass
    out.discard("")
    return out


def _known_profile(key: str) -> str:
    """Why ``key`` names a profile jason can already load, or ""."""
    import sys
    from importlib.metadata import entry_points

    from jason.community.profile import DEFAULT_PROFILE, ENTRY_POINT_GROUP, package_name, profile_root

    if key == DEFAULT_PROFILE:
        return f"{key!r} is the default profile"
    if package_name(key) in sys.modules:
        return f"a profile {key!r} is already loaded"
    explicit = os.environ.get("JASON_PROFILE_DIR", "").strip()
    if explicit:
        if Path(explicit).name == key:
            return f"JASON_PROFILE_DIR already points at a profile named {key!r}"
    else:
        try:
            root = profile_root(key)
        except Exception:  # noqa: BLE001
            root = None
        if root is not None:
            return f"a profile {key!r} already exists at {root}"
    if any(point.name == key for point in entry_points(group=ENTRY_POINT_GROUP)):
        return f"an installed package registers the profile {key!r}"
    return ""


def collisions(key: str, *, community: Any = None) -> list[str]:
    """Every reason ``key`` cannot name a new profile; empty when it can. ``community`` is the profile whose document
    keys and aliases are checked (the active one by default)."""
    from jason.community.books import Book
    from jason.community.profile import ProfileNotFound, _checked

    try:
        key = _checked(key)
    except ProfileNotFound:
        return [f"{key!r} is not a profile name: lowercase letters, digits, and _ , starting with a letter"]
    reasons = []
    if key in {b.value for b in Book}:
        reasons.append(f"{key!r} is a book's record address key (jason://{key}/...)")
    if community is None:
        try:
            from jason.community import community as active

            community = active()
        except Exception:  # noqa: BLE001 - no active profile: nothing to collide with
            community = None
    if community is not None and key in _aliases(community):
        reasons.append(f"{key!r} is a document key or alias the active profile's record addresses answer to")
    if key in MCP_TOOL_SETS:
        reasons.append(f"{key!r} is a jason-mcp tool set (--profile {key})")
    if key in RESERVED:
        reasons.append(f"{key!r} would name the profile's class after the base class")
    known = _known_profile(key)
    if known:
        reasons.append(known)
    return reasons


def _check_name(name: str) -> list[str]:
    if not name.strip():
        return ["--name is required: the association's name as its notices give it"]
    if any(ch in name for ch in '\\"\n\r\t') or any(ord(ch) < 32 for ch in name):
        return [f"{name!r}: the name holds a quote, backslash, or control character"]
    return []


def values_for(key: str, name: str, *, county: str = "", today: date | None = None) -> dict[str, str]:
    from jason.tasks.onboarding_lookup import county_key, region_for

    region = region_for(county)
    return {
        "KEY": key, "NAME": name.strip(), "CLASS": class_name(key), "DATE": (today or date.today()).isoformat(),
        "COUNTY": (county_key(county).replace("-", " ").title() + " County") if county.strip() else "",
        "NAME_LITERAL": repr(name.strip()), "KEY_LITERAL": repr(key), "REGION_LITERAL": repr(region),
        "CORPORATE_LITERAL": repr(""),
    }


def render(text: str, values: dict[str, str]) -> str:
    """Fill each ``{{VARIABLE}}``; an unknown one is an error, so a template's typo never reaches a profile."""
    def fill(m: re.Match) -> str:
        if m.group(1) not in values:
            raise KeyError(f"template variable {m.group(1)} has no value")
        return values[m.group(1)]

    return _VARIABLE.sub(fill, text)


def rendered(values: dict[str, str]) -> dict[Path, str]:
    """Each template's path inside the package and its filled text. A Python file is compiled to prove it."""
    out: dict[Path, str] = {}
    for path in sorted(TEMPLATES.rglob(f"*{SUFFIX}")):
        rel = path.relative_to(TEMPLATES)
        target = rel.with_name(rel.name[: -len(SUFFIX)])
        text = render(path.read_text(encoding="utf-8"), values)
        if target.suffix == ".py":
            compile(text, str(target), "exec")
        out[target] = text
    return out


def write(key: str, name: str, *, county: str = "", directory: Path | None = None, spec_dir: Path | None = None,
          community: Any = None, today: date | None = None) -> Scaffold:
    """Write the new profile's package and its empty private facts. Raises ``ScaffoldRefused`` with every reason, and
    writes nothing, when the key collides, the name is unusable, or the package or private facts file exists."""
    from jason.community.private import spec_dir as default_spec_dir

    key = key.strip().lower()
    reasons = collisions(key, community=community) + _check_name(name)
    package = Path(directory) if directory is not None else default_directory(key)
    if package.exists() and (not package.is_dir() or any(package.iterdir())):
        reasons.append(f"{package} exists; jason never overwrites a profile package")
    spec = (Path(spec_dir) if spec_dir is not None else default_spec_dir()) / f"{key}.json"
    if spec.exists():
        reasons.append(f"{spec} exists; jason never overwrites private facts")
    if reasons:
        raise ScaffoldRefused(reasons)
    values = values_for(key, name, county=county, today=today)
    files = rendered(values)
    written: list[Path] = []
    for rel, text in files.items():
        target = package / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(target)
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(json.dumps({"facts": {}}, indent=1) + "\n", encoding="utf-8")
    from jason.tasks.onboarding_lookup import region_for

    return Scaffold(key, values["NAME"], region_for(county), package, spec, tuple(written))


def environment(scaffold: Scaffold) -> list[str]:
    """The settings that make the new profile the active one, as .env lines."""
    import jason.community.profile as profiles

    lines = [f"JASON_PROFILE={scaffold.key}"]
    package = scaffold.package.resolve()
    above = set(Path(profiles.__file__).resolve().parents)
    found = package.name == scaffold.key and (package.parent in above
                                              or (package.parent.name == "profiles" and package.parent.parent in above))
    if not found:
        lines.append(f"JASON_PROFILE_DIR={scaffold.package}")
    return lines


__all__ = ["MCP_TOOL_SETS", "RESERVED", "Scaffold", "ScaffoldRefused", "TEMPLATES", "class_name", "collisions",
           "default_directory", "environment", "render", "rendered", "values_for", "write"]
