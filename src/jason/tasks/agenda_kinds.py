"""Document kinds from the agenda items that used a file: a classification method beside the name, phrase, and model.

A file the name rules leave unclassified is decided by its agenda uses (``data/meetings/agenda-items.json``) only when
the evidence is strong enough to record:

- **agenda item and text**: the items narrow the kinds (a claim brings letters, estimates, a police report), and a
  phrase rule over the file's own words picks one of them. The text is the file's, or a byte-identical copy's: a Drive
  file's MD5 matches a Gmail attachment or a PayHOA library file on disk (``Digests``), whose text is read;
- **every use agrees**: two or more agenda items used the file, and every one brings the same single kind.

Anything short of that is a suggestion, kept with its evidence and not recorded as a kind. A file the name rules name
one kind and the agendas use as another is listed as a conflict for a person; the name rule stands. The result is
``data/meetings/agenda-kinds.json``; the library's classification and jason's Drive labels read its decisions.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.content import CONTENT_RULES, classify_text
from jason.community.symbols import DocumentKind

OUT = Path("meetings") / "agenda-kinds.json"
METHOD_TEXT = "agenda item and phrase rule"
METHOD_AGREE = "agenda item (every use agrees)"
# What a letter itself can be: counsel's letter, a letter, an engagement letter (the contract), a notice. A letter's title
# naming another kind (a grant deed it forwards) is a quotation.
LETTER_KINDS = frozenset({DocumentKind.LEGAL_CORRESPONDENCE, DocumentKind.CORRESPONDENCE, DocumentKind.CONTRACT, DocumentKind.NOTICE})
COMMUNICATION = re.compile(r"\bemail\b|\bletter\b|\bltr\b|\bmail - |correspondence|\bmemo\b", re.I)
METHOD_TEXT_ONLY = "phrase rule over the agenda file's text"


def _uses(data_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Each related document (where, ref) with every use: the meeting, the item, and the kinds it brings."""
    path = Path(data_dir) / "meetings" / "agenda-items.json"
    if not path.is_file():
        return {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for m in json.loads(path.read_text(encoding="utf-8")).get("meetings", []):
        for item in m["items"]:
            for r in item["related"]:
                if not r.get("ref") or r.get("relation") == "received":
                    continue                          # a received candidate is not a use
                d = out.setdefault((r["where"], r["ref"]), {"where": r["where"], "ref": r["ref"], "name": r["name"], "path": r.get("path"),
                                                             "nameKind": r.get("nameKind"), "uses": []})
                label = " / ".join(p for p in (item["item"], item["subitem"]) if p)
                d["uses"].append({"date": m["date"], "item": label, "relation": r["relation"], "expects": item["expects"]})
    return out


def _local_copies(data_dir: Path) -> dict[str, Path]:
    """MD5 -> a file on disk (Gmail attachments, PayHOA library files)."""
    from jason.tasks.digests import Digests

    digests = Digests(data_dir)
    out: dict[str, Path] = {}
    files = Path(data_dir) / "gmail" / "files.json"
    if files.is_file():
        raw = json.loads(files.read_text(encoding="utf-8"))
        for f in raw if isinstance(raw, list) else raw.get("files", []):
            p = Path(data_dir) / str(f.get("path", "")).replace("\\", "/")
            md5, _ = digests.of(p)
            if md5:
                out.setdefault(md5, p)
    lib = Path(data_dir) / "library" / "files"
    if lib.is_dir():
        for p in lib.rglob("*"):
            if p.is_file():
                md5, _ = digests.of(p)
                if md5:
                    out.setdefault(md5, p)
    digests.save()
    return out


FILES = Path("meetings") / "agenda-files"
FETCHABLE = ("application/pdf", "application/vnd.google-apps.document")


def fetch(drive: Any, data_dir: Path, *, limit: int = 200, log: Any = None) -> dict[str, int]:
    """Read (never change) the undecided agenda files that are in Drive and have no copy on disk: a PDF is downloaded,
    a Google Doc exported as PDF, into ``data/meetings/agenda-files/<Drive id>.pdf``. The next ``resolve`` reads them."""
    path = Path(data_dir) / OUT
    if not path.is_file():
        return {"wanted": 0, "fetched": 0, "failed": 0}
    listing = Path(data_dir) / "drive" / "files.json"
    raw = json.loads(listing.read_text(encoding="utf-8")) if listing.is_file() else []
    mime = {r["id"]: r.get("mimeType", "") for r in (raw if isinstance(raw, list) else raw.get("files", []))}
    wanted = [s for s in json.loads(path.read_text(encoding="utf-8")).get("suggested", [])
              if s["where"] == "Drive" and not s.get("hadText") and mime.get(s["ref"]) in FETCHABLE][:limit]
    root = Path(data_dir) / FILES
    counts = {"wanted": len(wanted), "fetched": 0, "failed": 0}
    for s in wanted:
        dest = root / f"{s['ref']}.pdf"
        if dest.is_file():
            continue
        try:
            if mime[s["ref"]] == "application/pdf":
                drive.download(s["ref"], dest)
            else:
                drive.export_pdf(s["ref"], dest)
            counts["fetched"] += 1
        except Exception as exc:  # one file refused does not stop the rest
            counts["failed"] += 1
            if log:
                log(f"{s['name']}: {exc}")
    return counts


def _text(data_dir: Path, doc: dict[str, Any], drive_md5: dict[str, str], copies: dict[str, Path]) -> tuple[str, str]:
    """The document's words and where they came from: the library's text cache, a file fetched for this, or a local
    copy's PDF text layer."""
    fetched = Path(data_dir) / FILES / f"{doc['ref']}.pdf"
    if doc["where"] == "Drive" and fetched.is_file():
        try:
            from jason.tasks.utilities import pdf_text

            text = pdf_text(fetched)
            if text.strip():
                return text, "fetched file"
        except Exception:
            pass
        ocr = fetched.with_name(fetched.name + ".md")        # a scan's text, written by `ocr_folder`
        if ocr.is_file():
            text = ocr.read_text(encoding="utf-8", errors="replace").split("\n", 2)[-1]
            if text.strip():
                return text, "OCR of the fetched scan"
    if doc["where"] == "PayHOA library":
        cached = Path(data_dir) / "library" / "text" / f"{doc['ref']}.txt"
        if cached.is_file():
            return cached.read_text(encoding="utf-8", errors="replace"), "library text"
    path = None
    if doc["where"] == "Drive":
        path = copies.get(drive_md5.get(doc["ref"], ""))
    elif doc["where"] == "Gmail" and doc.get("path"):
        path = Path(data_dir) / doc["path"]
    if path is None or not path.is_file() or path.suffix.lower() != ".pdf":
        return "", ""
    try:
        from jason.tasks.utilities import pdf_text

        return pdf_text(path), f"text of the copy {path.name}"
    except Exception:
        return "", ""


def resolve(data_dir: Path, community: Any = None) -> dict[str, Any]:
    uses = _uses(data_dir)
    drive_md5: dict[str, str] = {}
    listing = Path(data_dir) / "drive" / "files.json"
    if listing.is_file():
        raw = json.loads(listing.read_text(encoding="utf-8"))
        drive_md5 = {r["id"]: r["md5"] for r in (raw if isinstance(raw, list) else raw.get("files", [])) if r.get("md5")}
    copies = _local_copies(data_dir)
    decided, suggested, conflicts = [], [], []
    for doc in uses.values():
        expects = [tuple(u["expects"]) for u in doc["uses"] if u["expects"]]
        if not expects:
            continue
        evidence = [f"{u['date']} {u['item']} ({u['relation']})" for u in doc["uses"]][:6]
        if doc["nameKind"]:
            if not any(doc["nameKind"] in e for e in expects):
                conflicts.append({**_short(doc), "nameKind": doc["nameKind"], "agendaExpects": sorted({k for e in expects for k in e})[:6],
                                  "uses": evidence})
            continue
        candidates = [k for k in expects[0] if all(k in e for e in expects[1:])] or list(expects[0])
        text, source = _text(data_dir, doc, drive_md5, copies)
        if text.strip():
            rules = tuple(r for r in CONTENT_RULES if r.kind.value in candidates)
            kind, why = classify_text(text, rules)
            if kind is not None:
                decided.append({**_short(doc), "kind": kind.value, "method": METHOD_TEXT, "confidence": 0.8,
                                "evidence": f"{why} in the {source}; used at " + "; ".join(evidence[:3])})
                continue
            # The item's kinds miss; the document's own words may still name a kind the item did not bring (a renewal
            # letter under "Insurance Renewal", counsel's letter under "Maintenance"). The text decides; the agenda only
            # says where the board used it.
            # Only a title's words, and never for an email or letter: a communication quotes other documents' titles,
            # and body phrases such as "date:" and "phone" name nothing.
            kind, why = classify_text(text)
            if kind is not None and (not why.startswith("title") or
                                     (COMMUNICATION.search(doc["name"]) and kind not in LETTER_KINDS)):
                kind = None
            if kind is not None:
                decided.append({**_short(doc), "kind": kind.value, "method": METHOD_TEXT_ONLY, "confidence": 0.7,
                                "evidence": f"{why} in the {source}; outside the item's kinds ({', '.join(candidates[:3])}); "
                                            "used at " + "; ".join(evidence[:3])})
                continue
        common = [k for k in expects[0] if all(k in e for e in expects)]
        # Two uses at least: one item's single kind is where the board put the file once, not what it is.
        if len(common) == 1 and len(expects) > 1:
            decided.append({**_short(doc), "kind": common[0], "method": METHOD_AGREE, "confidence": 0.6,
                            "evidence": "used at " + "; ".join(evidence[:3])})
            continue
        suggested.append({**_short(doc), "candidates": candidates[:4], "hadText": bool(text.strip()), "uses": evidence})
    result = {"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "decided": decided, "suggested": suggested,
              "conflicts": conflicts}
    out = Path(data_dir) / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def _short(doc: dict[str, Any]) -> dict[str, Any]:
    return {"where": doc["where"], "ref": doc["ref"], "name": doc["name"], "path": doc.get("path")}


def decisions(data_dir: Path, where: str) -> dict[str, dict[str, Any]]:
    """The recorded agenda-item kinds for one place ("Drive", "PayHOA library", "Gmail"), by ref."""
    path = Path(data_dir) / OUT
    if not path.is_file():
        return {}
    return {d["ref"]: d for d in json.loads(path.read_text(encoding="utf-8")).get("decided", []) if d["where"] == where}


def summary_lines(result: dict[str, Any], *, limit: int = 15) -> list[str]:
    by_method: dict[str, int] = defaultdict(int)
    for d in result["decided"]:
        by_method[d["method"]] += 1
    lines = [f"decided {len(result['decided'])} (" + ", ".join(f"{v} by {k}" for k, v in by_method.items()) + f"); "
             f"{len(result['suggested'])} left as suggestions; {len(result['conflicts'])} named one kind and used as another", ""]
    for d in result["decided"][:limit]:
        lines.append(f"- {d['name'][:60]} -> {d['kind']} [{d['method']}] {d['evidence'][:110]}")
    if result["conflicts"]:
        lines += ["", "For a person: named one kind, used as another (the name rule stands):"]
        for c in result["conflicts"][:limit]:
            lines.append(f"- {c['name'][:60]}: named {c['nameKind']}, used as {', '.join(c['agendaExpects'][:3])} ({c['uses'][0]})")
    return lines


__all__ = ["METHOD_AGREE", "METHOD_TEXT", "METHOD_TEXT_ONLY", "decisions", "resolve", "summary_lines"]
