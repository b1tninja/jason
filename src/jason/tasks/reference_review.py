"""Read chosen sections with the local model for the references the grammar missed, and keep what checks out.

``run`` picks passages (a section's own words, ``jason.community.reference_model.passages``) from the outlines on disk,
asks the shared local model for each one's references, keeps a proposal only when its quote is in the section, sets
aside what the grammar already found there, and writes the rest to ``data/outlines/model/references.json`` with each
one's status (``jason.tasks.outlines.resolve``). The grammar's ``references.json`` is not touched: a model reference is
a lead for a person until one reads it. A passage read before with the same words is skipped unless asked again, so
repeated runs work through the documents. ``preflight`` runs first; the model is asked only through Ollama on this
machine, one request at a time under the GPU lock, and the store is written under its store lock.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.community.content import ModelUnavailable
from jason.community.outlines import DocumentOutline, normalize_number
from jason.community.reference_model import (
    Catalog, ModelReference, Passage, ReferenceModel, catalog, dedupe, parse_answer, passages, verify,
)
from jason.tasks.outlines import load, outline_dir, references, resolve

STORE_KEY = "model-references"


def store_path(data_dir: Path) -> Path:
    # A subfolder: jason.tasks.outlines.load reads every *.json beside the outlines as an outline.
    path = outline_dir(data_dir) / "model"
    path.mkdir(parents=True, exist_ok=True)
    return path / "references.json"


def load_store(data_dir: Path) -> dict[str, Any]:
    path = store_path(data_dir)
    if not path.is_file():
        return {"model": "", "passages": {}, "references": [], "dropped": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _inside(section: str, wanted: str) -> bool:
    """A passage of section ``section`` is inside ``wanted`` (a number or a title): 7.2 takes 7.2(a) and 7.2.1."""
    if section == wanted or section.lower() == wanted.lower():
        return True
    return any(section.startswith(wanted + s) for s in ("(", "."))


def choose(outlines: list[DocumentOutline], picks: Iterable[str] = (), *, limit: int = 20, skip: dict[str, str] | None = None,
           max_chars: int = 6000) -> list[Passage]:
    """The passages to read: every outline's, or those of the picked documents ("owners-manual") and sections
    ("bylaws#7.2", which takes its subsections), in document order, up to ``limit`` (0 is no limit). ``skip`` maps a
    passage id to the digest of the words read before; an unchanged passage there is left out."""
    by_key = {o.key: o for o in outlines}
    wanted: list[tuple[str, str]] = []
    for pick in picks:
        key, _, section = pick.partition("#")
        if key not in by_key:
            raise ValueError(f"no outline {key}; outlined: {', '.join(sorted(by_key))}")
        wanted.append((key, normalize_number(section) if section and section[0].isdigit() else section))
    keys = list(dict.fromkeys(k for k, _ in wanted)) or [o.key for o in outlines]
    out: list[Passage] = []
    for key in keys:
        sections = [s for k, s in wanted if k == key]
        for p in passages(by_key[key], max_chars=max_chars):
            if sections and not any(s == "" or _inside(p.section, s) for s in sections):
                continue
            if skip and skip.get(p.id) == _digest(p.text):
                continue
            out.append(p)
            if limit and len(out) >= limit:
                return out
    return out


def review(outlines: list[DocumentOutline], chosen: list[Passage], reader: ReferenceModel, *, known: Catalog | None = None,
           log=print) -> dict[str, Any]:
    """Ask the model about each passage; verify, normalize, and dedupe its answer against the grammar."""
    known = known or catalog(outlines)
    by_key = {o.key: o for o in outlines}
    grammar = references(outlines)
    read: list[dict[str, Any]] = []
    added: list[ModelReference] = []
    already: list[ModelReference] = []
    dropped: list[dict[str, Any]] = []
    stopped = ""
    for p in chosen:
        outline = by_key[p.source]
        try:
            answer = reader.read(p, known)
        except ModelUnavailable as exc:
            # Keep what was read so far; the caller saves it and reports the stop.
            stopped = str(exc)
            break
        proposals, malformed, error = parse_answer(answer)
        kept, bad = verify(p, proposals, outline, known)
        new, old = dedupe(kept, grammar)
        added += new
        already += old
        entry = {"id": p.id, "source": p.source, "section": p.section, "title": p.title[:90], "chars": len(p.text),
                 "trimmed": p.trimmed, "digest": _digest(p.text), "proposed": len(proposals), "added": len(new),
                 "known": len(old), "dropped": len(bad), "malformed": malformed + (1 if error else 0)}
        if error:
            bad.append({"source": p.source, "source_section": p.section, "reason": error})
        dropped += [{**d, "passage": p.id} for d in bad]
        read.append(entry)
        log(f"{p.source} {p.section or '(no section)'}: {len(proposals)} proposed, {len(new)} new, {len(old)} the grammar has, "
            f"{len(bad)} dropped" + (f", {entry['malformed']} malformed" if entry["malformed"] else ""))
    return {"read": read, "added": added, "known": already, "dropped": dropped, "stopped": stopped}


def run(data_dir: Path, *, picks: Iterable[str] = (), limit: int = 20, again: bool = False, reader: ReferenceModel | None = None,
        outlines: list[DocumentOutline] | None = None, log=print) -> dict[str, Any]:
    """Read the chosen passages and merge what the model added into the store. Raises ``ModelUnavailable`` (from
    ``preflight``) before reading anything when the local model cannot run, or after saving what was read when it stops
    answering partway."""
    from jason.locks import Resource, hold

    outlines = outlines if outlines is not None else load(data_dir)
    reader = reader or ReferenceModel()
    store = load_store(data_dir)
    skip = None if again else {pid: entry.get("digest", "") for pid, entry in store.get("passages", {}).items()}
    chosen = choose(outlines, picks, limit=limit, skip=skip)
    result: dict[str, Any] = {"model": reader.model, "chosen": len(chosen), "read": [], "added": [], "known": [], "dropped": [],
                              "path": str(store_path(data_dir))}
    if not chosen:
        return result
    reader.preflight()
    found = review(outlines, chosen, reader, log=log)
    rows = [{**row, "said": m.said, "passage": m.passage} for row, m in zip(resolve([m.reference for m in found["added"]], outlines, data_dir), found["added"])]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ids = {e["id"] for e in found["read"]}
    with hold(Resource.STORE, STORE_KEY, timeout=60, purpose="model references"):
        store = load_store(data_dir)
        store["model"] = reader.model
        store["updated"] = now
        for e in found["read"]:
            store.setdefault("passages", {})[e["id"]] = {**e, "read": now}
        # A passage read again replaces what it said before.
        store["references"] = [r for r in store.get("references", []) if r.get("passage") not in ids] + rows
        store["dropped"] = [r for r in store.get("dropped", []) if r.get("passage") not in ids] + found["dropped"]
        store_path(data_dir).write_text(json.dumps(store, indent=1), encoding="utf-8")
    result.update(read=found["read"], added=rows, known=[m.to_dict() for m in found["known"]], dropped=found["dropped"],
                  stored=len(store["references"]), passagesRead=len(store["passages"]))
    if found["stopped"]:
        raise ModelUnavailable(f"{found['stopped']} (after {len(found['read'])} of {len(chosen)} passages; those are saved)")
    return result


__all__ = ["run", "review", "choose", "store_path", "load_store"]
