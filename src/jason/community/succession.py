"""Where a former statute went, and how a current one changed: the stored readings of lawlibrary's law history.

``jason law-history --export`` (``jason.tasks.law_history``) asks lawlibrary for the Davis-Stirling Act's
recodification (Stats. 2012, Ch. 180, AB 805, operative January 1, 2014: former Civil Code 1350 to 1378 moved to 4000
to 6150) and for every change to the Act between legislative sessions, and keeps both under
``data/authorities/history``. This module reads them from disk; it never calls lawlibrary.

A successor row is a reading of an official source, and says which: the Law Revision Commission's enacted
disposition table (the pin), its Comment on the new section (a second reading), or a similarity candidate where both
are silent (a lead only). A document that cites "Civil Code 1363" is read against the row for the subdivision it
names when there is one, else against every row of the section.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HISTORY_DIR = "authorities/history"
FORMER_FILE = "former-sections.json"
CHANGES_FILE = "changes.json"
ACT = "davis-stirling"
# "Civil Code", "Civil Code Section", "CIV", "§" before the number ("Civil Code" first: "CIV" would take its "Civ").
_CITED = r"^(?:Civil\s+Code|CIV)\b\.?\s*(?:Section|§)?\s*"


@dataclass(frozen=True)
class Successor:
    former: str                 # "CIV 1363(g)"
    section: str                # "1363"
    part: str                   # "(g)", "(intro. cl.)", or ""
    targets: tuple[str, ...]    # ("CIV 5855",)
    succession: str             # continued, continued_with_changes, not_continued, ...
    source: str                 # disposition_table, commission_comment, similarity
    act: str
    report: str                 # the official document's title
    url: str

    @property
    def official(self) -> bool:
        return self.source != "similarity"


def _rows(data_dir: Path) -> list[Successor]:
    path = Path(data_dir) / HISTORY_DIR / FORMER_FILE
    if not path.is_file():
        return []
    found: list[Successor] = []
    for section in json.loads(path.read_text(encoding="utf-8")).get("sections", []):
        for row in section.get("rows") or []:
            former, report = row.get("former") or {}, row.get("report") or {}
            found.append(Successor(
                str(former.get("citation") or ""), str(former.get("section") or ""), str(former.get("part") or ""),
                tuple(str(t.get("citation") or "") for t in row.get("targets") or []), str(row.get("succession") or ""),
                str(row.get("source") or ""), str(row.get("act") or ""), str(report.get("title") or ""), str(report.get("url") or "")))
    return found


def successors(data_dir: Path, section: str, part: str = "", *, act: str = ACT) -> list[Successor]:
    """The rows for a former section (``"1363"``), narrowed to a subdivision (``"(g)"`` or ``"g"``) when one is given."""
    number = re.sub(_CITED, "", section.strip(), flags=re.I)
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(\([^)]*\).*)?", number)
    if not m:
        return []
    number, inline = m.group(1), m.group(2) or ""
    part = part or inline
    rows = [r for r in _rows(data_dir) if r.section == number and r.act == act]
    if part:
        want = "(" + part.strip("()").strip() + ")"
        narrowed = [r for r in rows if r.part.startswith(want)]
        return narrowed or rows
    return rows


def now_at(data_dir: Path, section: str, *, limit: int = 6) -> str:
    """Where a cited former section is now, in words: "1363(g) is now CIV 5855" or "1365 is now CIV 5300, 5305, ...";
    "" when the history has not been exported or the table places nothing."""
    rows = successors(data_dir, section)
    if not rows:
        return ""
    targets: list[str] = []
    for r in rows:
        for t in r.targets:
            base = re.sub(r"\(.*$", "", t).strip()
            if base and base not in targets:
                targets.append(base)
    if not targets:
        kinds = sorted({r.succession for r in rows})
        return f"{section} was not continued ({', '.join(kinds)})"
    sources = sorted({r.source.replace("_", " ") for r in rows if r.targets})
    shown = ", ".join(t.replace("CIV ", "") for t in targets[:limit]) + (", ..." if len(targets) > limit else "")
    return f"{section} is now CIV {shown} ({' and '.join(sources)})"


# What the Commission's Comment says when a new section keeps an old one's effect: a renumbering or a rewording, not
# a change of law. "Continued" alone is the disposition table's word; it does not say whether the substance changed.
SAME_EFFECT = frozenset({"continued_without_change", "continued_without_substantive_change"})
CHANGED = frozenset({"continued_with_changes", "generalized", "restated", "superseded"})
RECODIFIED = "Stats. 2012, Ch. 180"


def predecessors(data_dir: Path, section: str, *, act: str = ACT) -> list[Successor]:
    """The former rows a current section (``"5855"``) continues."""
    number = re.sub(_CITED, "", section.strip(), flags=re.I)
    number = re.sub(r"\(.*$", "", number).strip()
    return [r for r in _rows(data_dir) if r.act == act and any(re.sub(r"\(.*$", "", t).strip() == f"CIV {number}" for t in r.targets)]


@dataclass(frozen=True)
class Standing:
    """Where a current section came from, and what changed in it since."""

    section: str
    origin: str                          # continued, continued_with_changes, new (2014), added (later), unknown
    former: tuple[str, ...]              # the former provisions it continues
    changed_from: tuple[str, ...]        # the former provisions the Comment says it continues with changes
    amendments: tuple[dict[str, Any], ...]

    @property
    def same_effect(self) -> bool:
        """A renumbered or reworded continuation with no amendment since: not a change to review."""
        return self.origin == "continued" and not self.amendments


def standing(data_dir: Path, section: str, *, since: str = "") -> Standing:
    """A current section's origin in the 2014 recodification and its amendments since (from ``since``'s edition on)."""
    number = re.sub(r"\(.*$", "", re.sub(_CITED, "", section.strip(), flags=re.I)).strip()
    rows = predecessors(data_dir, number)
    history = changes(data_dir, number)
    added = next((c for c in history if c.get("change") == "added"), None)
    amendments = tuple(c for c in history if c.get("change") in ("amended", "repealed", "revised", "renoted")
                       and (not since or str(c.get("after") or "") >= since))
    comments = [r for r in rows if r.source == "commission_comment"]
    changed = tuple(dict.fromkeys(r.former for r in comments if r.succession in CHANGED))
    if rows:
        origin = "continued_with_changes" if changed else "continued"
    elif added and RECODIFIED in str(added.get("statute") or ""):
        origin = "new"
    elif added:
        origin = "added"                 # added after the recodification (CIV 5551, SB 326 of 2019); the change is the addition
    else:
        origin = "unknown"
    return Standing(number, origin, tuple(dict.fromkeys(r.former for r in rows)), changed, amendments)


def _number_key(number: str) -> tuple[int, ...]:
    """"1365.2.5" as (1365, 2, 5): section numbers compare part by part."""
    return tuple(int(p) for p in re.findall(r"\d+", number or "")) or (0,)


def _amendment(c: dict[str, Any]) -> str:
    bill = f" ({c['bill']})" if c.get("bill") else ""
    when = f", operative {c['operative']}" if c.get("operative") else ""
    return f"{c.get('change')} by {c.get('statute') or 'an act with no history note'}{bill}{when}"


def version_note(data_dir: Path, section: str) -> str:
    """A current section's history in one line, or "" before the history is exported: where it came from in the
    2014 recodification (same effect, or with changes), when it was added if later, and each amendment since."""
    st = standing(data_dir, section)
    parts: list[str] = []
    if st.origin == "continued_with_changes":
        parts.append(f"continues former {', '.join(st.changed_from[:3])} with changes (2014)")
    elif st.origin == "continued" and st.former:
        parts.append(f"continues former {', '.join(st.former[:3])}{', ...' if len(st.former) > 3 else ''} (2014)")
    elif st.origin == "new":
        parts.append("new in the 2014 recodification")
    elif st.origin == "added":
        added = next((c for c in changes(data_dir, st.section) if c.get("change") == "added"), {})
        parts.append(f"added by {added.get('statute') or '?'}{' (' + added['bill'] + ')' if added.get('bill') else ''}")
    parts += [_amendment(c) for c in st.amendments]
    return "; ".join(parts)


def changed_in(data_dir: Path, cited: str) -> list[tuple[str, str]]:
    """The sections a citation such as "CIV 5850-5855; CIV 5200" covers whose law changed (amended, continued with
    changes, or added after 2014), each with its ``version_note``. A renumbering with the same effect is left out."""
    sections = {str(c.get("section") or "") for c in changes(data_dir)} - {""}
    wanted: list[str] = []
    for m in re.finditer(r"(\d{4}(?:\.\d+)*)(?:\s*(?:-|to|through)\s*(\d{4}(?:\.\d+)*))?", cited or ""):
        lo, hi = _number_key(m.group(1)), _number_key(m.group(2) or m.group(1))
        wanted += sorted((s for s in sections if lo <= _number_key(s) <= hi), key=_number_key)
    found: list[tuple[str, str]] = []
    for s in dict.fromkeys(wanted):
        st = standing(data_dir, s)
        if st.amendments or st.origin in ("continued_with_changes", "added"):
            found.append((s, version_note(data_dir, s)))
    return found


def changes(data_dir: Path, section: str = "", *, since: str = "") -> list[dict[str, Any]]:
    """The stored changes between sessions, oldest first: every one, or one section's ("5855" or "CIV 5855")."""
    path = Path(data_dir) / HISTORY_DIR / CHANGES_FILE
    if not path.is_file():
        return []
    number = re.sub(_CITED, "", section.strip(), flags=re.I)
    rows = [c for block in json.loads(path.read_text(encoding="utf-8")).get("changes", []) for c in block.get("changes") or []]
    if number:
        rows = [c for c in rows if str(c.get("section") or "") == number]
    if since:
        rows = [c for c in rows if str(c.get("after") or "") >= since]
    return rows


__all__ = ["Successor", "Standing", "successors", "predecessors", "standing", "now_at", "changes", "version_note", "changed_in", "SAME_EFFECT", "CHANGED", "HISTORY_DIR",
           "FORMER_FILE", "CHANGES_FILE"]
