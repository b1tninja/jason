"""What in jason rests on a law that changed: every citation of a changed Davis-Stirling section, for a person to review.

jason cites the Act in its docs, its duty registry, its document models' findings and constants, and its specification.
When a legislative session amends a section, each of those citations may now say the wrong thing (CIV 5855's written
decision went from 15 days to 14 in 2025). The sweep reads the stored law history (``jason law-history --export``)
and lists, per changed section, what changed and every place jason cites it.

A change here is a change of law, not of number. The 2014 recodification renumbered the Act: a section the Law
Revision Commission's Comment says continues a former one "without change" or "without substantive change" is the
same law under a new number, and is not listed unless it was amended since. A section the Comment says continues a
former one "with changes" is listed when the sweep reaches back to the recodification. A citation of a former section
(1350 to 1378) is listed with where that section went. The sweep edits nothing; a person decides what to update.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.succession import now_at, standing

# A Civil Code citation as jason writes it: "CIV 5855", "CIV 5855(c)", "Civil Code 5855", "Civil Code Section 1363(g)",
# "Civ. Code § 5850". A bare number is not read; it is too often something else.
CITATION = re.compile(r"(?:\bCIV|Civil\s+Code|Civ\.\s*Code)\s*(?:Section\s*|§+\s*)?(\d{4}(?:\.\d+)?)((?:\([a-z0-9]{1,4}\))*)")
# jason's own text. The profile's package (``Community.root``) is scanned beside it when it sits in the project.
SCANNED = (("docs", "**/*.md"), ("src/jason", "**/*.py"), (".", "AGENTS.md"), (".", "SKILLS.md"), (".", "README.md"))
CURRENT = (4000.0, 6150.0)
FORMER = (1350.0, 1378.0)


@dataclass
class Cite:
    path: str
    line: int
    text: str


@dataclass
class Entry:
    section: str
    kind: str                          # amended, continued_with_changes, new, added, former
    summary: str
    changes: list[dict[str, Any]] = field(default_factory=list)
    cites: list[Cite] = field(default_factory=list)


def _scanned(project: Path, profile_root: Path | None) -> tuple[tuple[str, str], ...]:
    """`SCANNED`, and the profile's package (its specification cites the Act too) when it sits inside ``project``; a
    profile installed elsewhere is its own repository and is not read."""
    if profile_root is None:
        return SCANNED
    try:
        folder = Path(profile_root).resolve().relative_to(project.resolve()).as_posix()
    except ValueError:
        return SCANNED
    return (*SCANNED[:2], (folder, "**/*.py"), *SCANNED[2:])        # after jason's own code, as always


def citations(project: Path, profile_root: Path | None = None) -> dict[str, list[Cite]]:
    """Every Civil Code citation in jason's own text, and the profile's (``profile_root``, ``Community.root``), by section
    number."""
    found: dict[str, list[Cite]] = defaultdict(list)
    for base, pattern in _scanned(project, profile_root):
        for path in sorted((project / base).glob(pattern)):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for m in CITATION.finditer(line):
                    found[m.group(1) + (m.group(2) or "")].append(Cite(path.relative_to(project).as_posix(), n, line.strip()[:160]))
    return found


def sweep(project: Path, data_dir: Path, *, since: str = "", profile_root: Path | None = None) -> list[Entry]:
    """The changed sections jason cites, oldest change first within each; ``since`` is an edition year ("2025").
    ``profile_root`` is the active profile's package (``Community.root``), read beside jason's own text."""
    cites = citations(project, profile_root)
    by_section: dict[str, list[Cite]] = defaultdict(list)
    for cited, where in cites.items():
        by_section[re.sub(r"\(.*$", "", cited)] .extend(where)
    entries: list[Entry] = []
    for section, where in sorted(by_section.items(), key=lambda kv: float(kv[0])):
        number = float(section)
        if FORMER[0] <= number <= FORMER[1]:
            subs = sorted({c for c in cites if re.sub(r"\(.*$", "", c) == section and c != section})
            places = "; ".join(filter(None, (now_at(data_dir, s) for s in subs or [section])))
            entries.append(Entry(section, "former", places or f"former CIV {section}: no stored successor", [], where))
            continue
        if not CURRENT[0] <= number <= CURRENT[1]:
            continue
        st = standing(data_dir, section, since=since)
        recodification_in_window = not since or since <= "2013"
        if st.amendments:
            last = st.amendments[-1]
            summary = "; ".join(f"{c.get('after')}: {c.get('change')} by {c.get('statute') or '?'}"
                                f"{' (' + c['bill'] + ')' if c.get('bill') else ''}"
                                f"{', ' + c['summary'] if c.get('summary') else ''}" for c in st.amendments)
            entries.append(Entry(section, "amended", summary, list(st.amendments), where))
        elif recodification_in_window and st.origin == "continued_with_changes":
            entries.append(Entry(section, st.origin, f"continues {', '.join(st.changed_from)} with changes (Law Revision Commission "
                                                     "Comment)", [], where))
        elif recodification_in_window and st.origin in ("new", "added"):
            entries.append(Entry(section, st.origin, "a new section in the 2014 recodification" if st.origin == "new"
                                 else "added after the recodification", [], where))
    return entries


def write(entries: list[Entry], out_dir: Path, *, since: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    (out_dir / "law-sweep.json").write_text(json.dumps({"swept": stamp, "since": since,
                                                         "entries": [asdict(e) for e in entries]}, indent=1, default=str), encoding="utf-8")
    lines = [f"# What in jason rests on a changed law (since the {since or 'first'} edition)", "",
             f"- Swept {stamp} from data/authorities/history (`jason law-history --export`).",
             "- A section the 2014 recodification renumbered without a change of substance, and not amended since, is not listed.",
             "- Each citation is a place a person should read again; the sweep changes nothing.", ""]
    for kind, heading in (("amended", "Amended"), ("continued_with_changes", "Continued with changes in 2014"),
                          ("new", "New in 2014"), ("added", "Added after 2014"), ("former", "Former sections still cited")):
        chosen = [e for e in entries if e.kind == kind]
        if not chosen:
            continue
        lines += [f"## {heading} ({len(chosen)} sections)", ""]
        for e in chosen:
            label = f"former CIV {e.section}" if kind == "former" else f"CIV {e.section}"
            files = sorted({c.path for c in e.cites})
            lines.append(f"### {label}: {len(e.cites)} citations in {len(files)} files")
            lines += ["", f"- {e.summary}"]
            for c in e.cites[:40]:
                lines.append(f"- `{c.path}:{c.line}`")
            if len(e.cites) > 40:
                lines.append(f"- and {len(e.cites) - 40} more")
            lines.append("")
    path = out_dir / "law-sweep.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


__all__ = ["Cite", "Entry", "citations", "sweep", "write", "CITATION"]
