"""Read the library's files of some kinds with the document models and print the fill rates; writes nothing.

    python scripts/eval_models.py grant_deed amendment [--show 5] [--field number] [--json]

Unlike ``jason models`` it does not save ``data/documents/readings.json``,
so several people (or agents) can measure their kinds at once. ``--show``
prints the incomplete files; ``--field`` prints the files where that field
came back empty, with the text around where it should have been.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from jason.community.document_models import ModelContext, read
from jason.community.symbols import DocumentKind
from jason.tasks.library import distinct, load, text_for


def _empty(value) -> bool:
    """Not read: None, an empty string, or an empty collection. ``False`` and ``0`` are readings."""
    if value is None:
        return True
    if isinstance(value, (bool, int, float)):
        return False
    return value in ("", [], {}) or (isinstance(value, list) and not any(v is not None and v != "" for v in value))


def evaluate(root: Path, kinds: list[str], community) -> dict:
    out = {}
    rows = [r for r in distinct(load(root)) if r["kind"] in kinds]
    for kind in kinds:
        entries = []
        for row in (r for r in rows if r["kind"] == kind):
            text = text_for(root, row["id"])
            entry = {"id": row["id"], "name": row["name"], "confidential": row["confidential"], "hasText": bool(text.strip()),
                     "vision": (root / "library" / "text" / f"{row['id']}.vision.txt").is_file()}
            if text.strip():
                try:
                    reading = read(DocumentKind(kind), text, ModelContext(community, root, date.today(), row["name"], row.get("period") or "",
                                                                         bool(row["confidential"])))
                except Exception as exc:
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                    reading = None
                if reading is not None:
                    entry.update(reading.as_dict())
            entries.append(entry)
        read_rows = [e for e in entries if e.get("model")]
        filled = Counter()
        for e in read_rows:
            for key, value in (e.get("fields") or {}).items():
                filled[key] += 0 if _empty(value) else 1
        out[kind] = {
            "files": len(entries), "text": sum(e["hasText"] for e in entries), "read": len(read_rows),
            "complete": sum(bool(e.get("complete")) for e in read_rows), "errors": [e["name"] for e in entries if e.get("error")],
            "fill": {k: f"{filled[k]}/{len(read_rows)}" for k in sorted(filled)},
            "findings": dict(Counter(f["code"] for e in read_rows for f in e.get("findings") or []).most_common()),
            "entries": entries,
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kinds", nargs="+")
    parser.add_argument("--show", type=int, default=0)
    parser.add_argument("--field", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--data", default=str(Path(__file__).resolve().parents[1] / "data"))
    args = parser.parse_args(argv)
    from jason.community import load_mystique

    result = evaluate(Path(args.data), args.kinds, load_mystique())
    if args.json:
        print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "entries"} for k, v in result.items()}, indent=1))
        return 0
    for kind, r in result.items():
        print(f"{kind}: files {r['files']} text {r['text']} read {r['read']} complete {r['complete']} errors {len(r['errors'])}")
        print("  fill: " + ", ".join(f"{k} {v}" for k, v in r["fill"].items()))
        print("  findings: " + ", ".join(f"{k} {v}" for k, v in r["findings"].items()))
        for e in r["errors"]:
            print(f"  error: {e}")
        if args.show:
            for e in [e for e in r["entries"] if e.get("model") and not e.get("complete")][: args.show]:
                print(f"  incomplete: {e['name']} ({e['id']}) missing {e.get('missing')}")
        if args.field:
            for e in [e for e in r["entries"] if e.get("model") and _empty((e.get("fields") or {}).get(args.field))][: args.show or 10]:
                print(f"  empty {args.field}: {e['name']} ({e['id']}){' vision' if e['vision'] else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
