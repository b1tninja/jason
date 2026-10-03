"""The private facts' layout per profile, and ``jason spec --migrate``.

Each profile's private facts are its own (``jason.community.private``): ``<spec>/<profile>.json`` for the answers
onboarding records, and ``<spec>/<profile>/<topic>.json`` for each topic. The default profile's topics were kept at
``<spec>/<topic>.json`` before; they are still read for it, and only for it, until they are copied.

``plan`` lists, read-only, what ``apply`` would do with each top-level topic file: copy it into the default profile's
folder, leave it (the copy is already there and the same), or hold it (a different copy is there; a person settles it).
``apply`` first copies every file it will copy into ``<spec>/backups/migrate-<stamp>/``, then copies each one. It never
moves, rewrites, or deletes a source: once copied, the profile's folder is read first, and a person removes the old
files when satisfied. A profile's own facts file (``<profile>.json``, or any file holding answered facts or leads) is
not a topic and is left where it is. Nothing is written to PayHOA, Google, or the mail.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Action(str, Enum):
    COPY = "copy"              # the profile's folder has no copy: copy it
    SAME = "same"              # an identical copy is there: nothing to do
    HOLD = "hold"              # a different copy is there: kept as it is, for a person to settle
    SKIP = "skip"              # a profile's own facts file, not a topic


@dataclass(frozen=True)
class Step:
    source: Path
    target: Path | None
    action: Action
    why: str = ""

    def line(self, root: Path) -> str:
        """The step in words, by path only: never a value from the file."""
        rel = _rel(self.source, root)
        if self.target is None:
            return f"{self.action.value} {rel} ({self.why})"
        return f"{self.action.value} {rel} -> {_rel(self.target, root)}" + (f" ({self.why})" if self.why else "")


def _rel(path: Path, root: Path) -> str:
    try:
        return f"{root.name}/{path.relative_to(root).as_posix()}"
    except ValueError:
        return str(path)


def _own_facts_file(path: Path, profiles: set[str]) -> str:
    """Why ``path`` is a profile's own facts file and not a topic, or ""."""
    from jason.community.onboarding import FACTS, LEADS

    if path.stem in profiles:
        return "a profile's own facts file"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if isinstance(value, dict) and (FACTS in value or LEADS in value):
        return "holds onboarding answers: a profile's own facts file"
    return ""


def plan(spec: Path | None = None, *, profile: str = "") -> list[Step]:
    """What ``apply`` would do with each top-level ``*.json`` in the private facts folder, read-only. ``profile`` is the
    profile the files belong to: the default profile, whose files these were."""
    from jason.community import private

    root = Path(spec) if spec is not None else private.spec_dir()
    owner = profile or private.default_profile()
    profiles = {owner, private.profile_of()}
    steps: list[Step] = []
    if not root.is_dir():
        return steps
    for source in sorted(p for p in root.glob("*.json") if p.is_file()):
        why = _own_facts_file(source, profiles)
        if why:
            steps.append(Step(source, None, Action.SKIP, why))
            continue
        target = root / owner / source.name
        if not target.exists():
            steps.append(Step(source, target, Action.COPY))
        elif target.is_file() and target.read_bytes() == source.read_bytes():
            steps.append(Step(source, target, Action.SAME, "already copied"))
        else:
            steps.append(Step(source, target, Action.HOLD, "a different copy is there; settle it by hand"))
    return steps


def apply(steps: list[Step], spec: Path | None = None, *, now: datetime | None = None) -> Path | None:
    """Copy each ``COPY`` step, after copying its source into ``<spec>/backups/migrate-<stamp>/``. Returns the backup
    folder, or None when there was nothing to copy. Sources are never moved or changed."""
    from jason.community import private

    root = Path(spec) if spec is not None else private.spec_dir()
    copies = [s for s in steps if s.action is Action.COPY and s.target is not None]
    if not copies:
        return None
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    backup = root / "backups" / f"migrate-{stamp}"
    backup.mkdir(parents=True, exist_ok=True)
    for step in copies:
        shutil.copy2(step.source, backup / step.source.name)
    for step in copies:
        assert step.target is not None
        if step.target.exists():                     # appeared since the plan: never overwritten
            continue
        step.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(step.source, step.target)
    return backup


def where(profile: str = "", spec: Path | None = None) -> list[tuple[str, Path]]:
    """Each topic the profile has and the file it is read from (its own folder, or the default profile's old file)."""
    from jason.community import private

    root = Path(spec) if spec is not None else private.spec_dir()
    who = private.profile_of(profile)
    default = who == private.default_profile()
    names = {p.stem for p in (root / who).glob("*.json") if p.is_file()} if (root / who).is_dir() else set()
    if default:
        names |= {s.source.stem for s in plan(root, profile=who) if s.action is not Action.SKIP}
    out = []
    for name in sorted(names):
        own, old = root / who / f"{name}.json", root / f"{name}.json"
        out.append((name, old if default and not own.is_file() and old.is_file() else own))
    return out


__all__ = ["Action", "Step", "apply", "plan", "where"]
