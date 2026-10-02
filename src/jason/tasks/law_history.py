"""Export the Davis-Stirling Act's history from lawlibrary: where each former section went, and every change since.

Two readings, kept under ``data/authorities/history`` and read by ``jason.community.succession``:

- ``former-sections.json``: each former Civil Code section of the Act (1350 to 1378, repealed by Stats. 2012,
  Ch. 180, AB 805, operative January 1, 2014) with its successor rows, each naming its source: the Law Revision
  Commission's enacted disposition table, its Comment on the new section, or a similarity candidate;
- ``changes.json``: every change to the current Act (4000 to 6150) and the former one between the legislative sessions
  lawlibrary holds (from 2011): added, amended, repealed, with the statute, effective and operative dates, and a short
  word count of the change.

Two pages render them for a person and for the AnythingLLM ``authorities`` catalog: the recodification table and the
change list. A page is a reading of the official sources; the statute text is the law.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.succession import ACT, CHANGES_FILE, FORMER_FILE, HISTORY_DIR

CODE = "CIV"
CURRENT = ("4000", "6150")
FORMER = ("1350", "1378")
SINCE = "2011"


def _key(number: str) -> tuple[float, ...]:
    try:
        return tuple(float(p) for p in re.sub(r"[^\d.]", "", number).split(".") if p)
    except ValueError:
        return (0.0,)


def export(library: Any, root: Path) -> dict[str, Any]:
    """Ask lawlibrary for the recodification and the changes; write the JSON and the two pages."""
    out = Path(root) / HISTORY_DIR
    out.mkdir(parents=True, exist_ok=True)
    sections = library.recodification(CODE, ACT)
    blocks = [library.changes(CODE, [CURRENT, FORMER], since=SINCE)]
    stamp = date.today().isoformat()
    (out / FORMER_FILE).write_text(json.dumps({"exported": stamp, "act": ACT, "sections": sections}, indent=1, default=str),
                                   encoding="utf-8")
    (out / CHANGES_FILE).write_text(json.dumps({"exported": stamp, "since": SINCE, "changes": blocks}, indent=1, default=str),
                                    encoding="utf-8")
    (out / "davis-stirling-recodification.md").write_text(recodification_page(sections, stamp), encoding="utf-8")
    (out / "davis-stirling-changes.md").write_text(changes_page(blocks, stamp), encoding="utf-8")
    rows = [r for s in sections for r in s.get("rows") or [] if r.get("act") == ACT]
    changes = [c for b in blocks for c in b.get("changes") or []]
    return {"sections": len(sections), "rows": len(rows), "official": sum(r.get("source") != "similarity" for r in rows),
            "changes": len(changes), "path": str(out)}


def recodification_page(sections: list[dict[str, Any]], stamp: str) -> str:
    acts = next((r for s in sections for r in s.get("recodifications") or [] if r.get("act") == ACT), {})
    lines = [
        "# Davis-Stirling Act recodification: where each former Civil Code section went", "",
        f"- Act: {acts.get('title', 'Davis-Stirling Common Interest Development Act')}; former CIV {FORMER[0]}-{FORMER[1]} moved to "
        f"CIV {CURRENT[0]}-{CURRENT[1]} by {acts.get('statute', 'Stats. 2012, Ch. 180')} ({acts.get('bill', 'AB 805')}), operative "
        f"{acts.get('operative', '2014-01-01')}",
        f"- Sources: the California Law Revision Commission's disposition table ({', '.join(acts.get('tables') or [])}) and its "
        f"Comments ({acts.get('comments', '')}); a similarity row is only a candidate",
        f"- Read with lawlibrary; exported {stamp}. This page is a reading of those sources; the statute text is the law.", "",
        "A governing document written before 2014 cites the former numbers (\"Civil Code 1363\", \"Section 1365 of the Civil "
        "Code\"). The rows below give the section or subdivision that continues each one, and how.", "",
    ]
    for section in sorted(sections, key=lambda s: _key(str(s.get("section") or ""))):
        rows = [r for r in section.get("rows") or [] if r.get("act") == ACT]
        lines.append(f"## Former CIV {section.get('section')}")
        if not rows:
            lines += ["", "- no row in the table or the Comments", ""]
            continue
        lines.append("")
        for r in rows:
            targets = ", ".join(t.get("citation", "") for t in r.get("targets") or []) or "nothing"
            report = r.get("report") or {}
            where = f"line {report.get('line')}" if report.get("line") else ""
            lines.append(f"- {r['former']['citation']} -> {targets}: {str(r.get('succession', '')).replace('_', ' ')} "
                         f"({str(r.get('source', '')).replace('_', ' ')}{', ' + where if where else ''})")
        lines.append("")
    return "\n".join(lines)


def changes_page(blocks: list[dict[str, Any]], stamp: str) -> str:
    by_edition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        for c in block.get("changes") or []:
            by_edition[str(c.get("after") or "")].append(c)
    lines = [
        "# Davis-Stirling Act: every change between legislative sessions", "",
        f"- Spans: CIV {CURRENT[0]}-{CURRENT[1]} (the Act since 2014) and the former CIV {FORMER[0]}-{FORMER[1]}",
        f"- Sessions compared: each edition lawlibrary holds from {SINCE}, with the history note each section carries",
        f"- Read with lawlibrary; exported {stamp}. A change is the difference between two published editions; the statute "
        "text is the law, and an act amended twice between two editions shows only its latest note.", "",
    ]
    for edition in sorted(by_edition):
        rows = sorted(by_edition[edition], key=lambda c: _key(str(c.get("section") or "")))
        counts = defaultdict(int)
        for c in rows:
            counts[str(c.get("change") or "")] += 1
        lines += [f"## {edition} edition ({', '.join(f'{n} {k}' for k, n in sorted(counts.items()))})", ""]
        for c in rows:
            when = c.get("operative") or c.get("effective") or ""
            diff = c.get("diff") or {}
            words = ""
            if isinstance(diff, dict) and (diff.get("inserted") or diff.get("deleted")):
                words = f"; +{diff.get('inserted', 0)}/-{diff.get('deleted', 0)} words"
            summary = f"; {c.get('summary')}" if c.get("summary") else ""
            bill = f" ({c.get('bill')})" if c.get("bill") else ""
            lines.append(f"- {c.get('citation')}: {c.get('change')}, {c.get('statute') or 'no history note'}{bill}"
                         f"{', operative ' + when if when else ''}{words}{summary}")
        lines.append("")
    return "\n".join(lines)


__all__ = ["export", "recodification_page", "changes_page"]
