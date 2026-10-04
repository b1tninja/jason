"""Manager reviews kept, not overwritten: ``data/reviews/<task>/<collection or "none">/<digest>.json``.

``data/briefs/<name>.md`` is the latest pack for a task and is written over each time. This store keeps every pack
that differed, so the same draft reviewed under two collections, or again after the law or a document changed, gives
two records that can be compared (docs/ingestion-and-review.md, "A review").

- **The key.** ``review_digest``: a SHA-256 over the question, the draft, the collection's key, and each source's id
  with a digest of its text. The same pack gives the same record; a pack whose sources changed gives a new one.
- **The record.** The task, its audience, the collection, the as-of date, the question, each source (id, tier,
  standing, file, section, and a digest of its passage: the words stay in their own stores), the pack's gaps, and
  ``runs``: each model answer for that pack with its model and how its quotes checked (``prompts.verify``). A pack
  written without ``--run`` has no runs; a second run is appended, never written over the first.
- **Confidentiality.** A review of a confidential collection is itself confidential and the record says so.
  ``history`` leaves such records out unless asked, so a tool built on it holds them back by default.
- **The lock.** A record is read, changed, and written back under the store lock (``Resource.STORE``, "reviews").

A stored review is a draft for the board, as the review is: it decides nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.context_pack import ContextPack
from jason.community.passage_index import Standing
from jason.community.prompts import Checked

REVIEWS = "reviews"
NO_COLLECTION = "none"
SCHEMA = 1
DIGEST_CHARS = 16              # of the digest, in the record's file name
CONFIDENTIAL_WHY = ("a review of a confidential collection is confidential: for directors and counsel, never an owner, "
                    "the newsletter, or an open meeting")
# The standing of a source that carries none (a pack not built by ``assemble``): by the tier's letter. The draft under
# review has no standing.
_STANDING = {"S": Standing.AUTHORITY, "G": Standing.RECORD, "R": Standing.RECORD, "F": Standing.PAGE}


def text_digest(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def collection_key(pack: ContextPack) -> str:
    return pack.collection.key if pack.collection is not None else NO_COLLECTION


def source_rows(pack: ContextPack) -> list[dict[str, Any]]:
    """Each source as the record keeps it: what it is and a digest of its words, never the words."""
    def standing(source: Any) -> str:
        found = source.standing or _STANDING.get(source.id[0])
        return found.value if found else ""

    return [{"id": s.id, "tier": int(s.tier), "standing": standing(s), "file": s.file or s.title,
             "section": s.section or s.place, "digest": text_digest(s.text)} for s in pack.sources]


def review_digest(pack: ContextPack) -> str:
    """What makes this pack this pack: the question, the draft, the collection, and each source's id and words."""
    identity = [pack.ask, pack.draft, collection_key(pack), [[s.id, text_digest(s.text)] for s in pack.sources]]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()


def _safe(part: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", part).strip("-.") or NO_COLLECTION


def review_path(data_dir: Path, pack: ContextPack) -> Path:
    return (Path(data_dir) / REVIEWS / pack.task.kind.slug / _safe(collection_key(pack))
            / f"{review_digest(pack)[:DIGEST_CHARS]}.json")


def _read(path: Path) -> dict[str, Any]:
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def store(pack: ContextPack, data_dir: Path, *, checked: Checked | None = None, model: str = "",
          as_of: date | None = None) -> Path:
    """Keep this pack's record, and with ``checked`` add the model's answer to its runs. A record already there for the
    same digest keeps its as-of date and its earlier runs."""
    from jason.locks import Resource, hold

    path = review_path(data_dir, pack)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    collection = pack.collection
    confidential = bool(collection is not None and collection.confidential)
    with hold(Resource.STORE, REVIEWS, purpose=f"keep a review of {pack.task.kind.slug}"):
        before = _read(path)
        record: dict[str, Any] = {
            "schema": SCHEMA, "task": pack.task.kind.slug, "audience": pack.task.audience.value,
            "collection": collection_key(pack),
            "collectionKind": collection.kind.value if collection is not None else "",
            "collectionTitle": collection.title if collection is not None else "",
            "collectionIncluded": bool(pack.collection_included),
            "confidential": confidential, "confidentialWhy": CONFIDENTIAL_WHY if confidential else "",
            "digest": review_digest(pack), "asOf": before.get("asOf") or (as_of or date.today()).isoformat(),
            "lastWritten": now, "ask": pack.ask, "draftDigest": text_digest(pack.draft) if pack.draft else "",
            "sources": source_rows(pack), "gaps": list(pack.gaps), "runs": list(before.get("runs") or []),
        }
        if checked is not None:
            record["runs"].append({"at": now, "model": model, "answer": checked.answer, "grounded": checked.grounded,
                                   "ungrounded": checked.ungrounded, "unknownSources": checked.unknown_sources})
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch = path.with_suffix(".json.tmp")
        scratch.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(scratch, path)
    return path


def history(data_dir: Path, task: str, *, include_confidential: bool = False) -> list[dict[str, Any]]:
    """The stored reviews of one task (its slug), oldest first: the date, the collection, the digest, and how the
    latest answer's quotes checked (``verified`` is None with no answer, and False for an answer that quoted nothing).
    A confidential review is left out unless ``include_confidential``. Reads only."""
    rows: list[dict[str, Any]] = []
    root = Path(data_dir) / REVIEWS / task
    for path in sorted(root.glob("*/*.json")) if root.is_dir() else []:
        record = _read(path)
        if not record or (record.get("confidential") and not include_confidential):
            continue
        runs = record.get("runs") or []
        last = runs[-1] if runs else None
        rows.append({
            "asOf": record.get("asOf", ""), "collection": record.get("collection", NO_COLLECTION),
            "digest": str(record.get("digest", ""))[:DIGEST_CHARS], "confidential": bool(record.get("confidential")),
            "collectionIncluded": bool(record.get("collectionIncluded")), "ask": record.get("ask", ""),
            "sources": len(record.get("sources") or []), "runs": len(runs),
            "model": last.get("model", "") if last else "",
            "grounded": last.get("grounded") if last else None,
            "ungrounded": len(last.get("ungrounded") or []) if last else None,
            # Verified: it quoted, and every quote was found in the source it cites. An answer with no quote is not.
            "verified": bool(last.get("grounded") and not last.get("ungrounded") and not last.get("unknownSources")) if last else None,
            "path": str(path),
        })
    rows.sort(key=lambda r: (r["asOf"], r["collection"], r["digest"]))
    return rows


__all__ = ["CONFIDENTIAL_WHY", "NO_COLLECTION", "REVIEWS", "collection_key", "history", "review_digest", "review_path",
           "source_rows", "store", "text_digest"]
