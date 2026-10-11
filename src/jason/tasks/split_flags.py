"""What the splitter's rail can say of each segment before the review (docs/pdf-splitter.md, "Flags before the review").

Disk only, and cheap: it reads the draft and the page facts already measured (``split_session.read_facts``) and cuts nothing, hashes no
part, and calls no service. The review (``split_session.review``) is still the one that cuts each part and compares its bytes; these
are the readings a person can see while still marking.

For each segment (a top-level document, and a nested one) it reports:

- ``blankOnly``: every page of the segment is blank (a separator or a stray sheet), by the page facts;
- ``nearDuplicateOf`` / ``repeatedBy``: the segment's pages repeat another segment's. A page repeats another when its page hash
  (``PageFact.phash``: a hash of its words, or the mean-hash of its picture) is the same, or for a picture within ``HAMMING_BITS`` of
  the 256 bits. The segment is a near-duplicate when at least ``NEAR_SHARE`` of its non-blank pages repeat pages of one other segment;
  the later segment names the earlier one;
- ``sideways``: the pages whose text, as displayed, runs up or down the page (``PageFact.sideways``), each with the degrees that turn it
  upright. A page with no text layer is never called sideways: nothing was measured;
- ``overPartLimit``: the segment, cut into its own file, would be about ``estimatedBytes`` (the file's size in proportion to the pages),
  over the ``upload.max_bytes`` limit a slot's upload is held to. An estimate, and said so;
- ``slotFilled``: the segment's chosen slot already holds a file (the collision the review would show), read from the record checklist;
- ``mayHoldMore``: pages inside the segment, not marked, that the segmentation's own cue table scores as likely starts of a document
  (``PageFact.start_score``, at or above the suggestion floor), and that no person rejected. A reading, not a boundary: nothing is marked.

``measured`` says how many pages had their facts read; a flag that needs a page's facts is silent for a page not yet measured and the
answer says so. No file name, page text, or hash is returned: only keys, page numbers, counts, and degrees.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jason import limits
from jason.community import split_suggest
from jason.community.split_session import PageFact
from jason.tasks import record_slots as rs

NEAR_SHARE = 0.8             # the share of a segment's non-blank pages that repeat another segment's for it to be called a near-duplicate
HAMMING_BITS = 26            # of 256 bits (about a tenth): two picture hashes this close are one picture, scanned twice
MAY_HOLD_MAX = 5             # the strongest pages named for "may hold more than one document"
CAVEATS = (
    "These are readings of the draft and the page facts, not decisions: nothing is marked, moved, or written. A flag names pages and "
    "counts, never a file or its words.",
    "Over the limit is an estimate from the file's size in proportion to the pages; the review cuts each part and says exactly.",
)


def same_page(a: str, b: str) -> bool:
    """Whether two page hashes are one page: equal words, or pictures within ``HAMMING_BITS``."""
    if not a or not b or a[:2] != b[:2]:
        return False
    if a.startswith("t:"):
        return a == b
    try:
        return bin(int(a[2:], 16) ^ int(b[2:], 16)).count("1") <= HAMMING_BITS
    except ValueError:
        return False


def _share(mine: list[str], theirs: list[str]) -> float:
    if not mine:
        return 0.0
    return sum(1 for h in mine if any(same_page(h, t) for t in theirs)) / len(mine)


def _slot_holds(computed: list[Any], slot_key: str, period: str) -> bool:
    found = next((c for c in computed if c.slot.key == slot_key), None)
    if found is None:
        return False
    return any(h.kind.value != "folder" and (not period or not h.period or h.period == period) for h in found.holders)


def flags(sid: str, *, community: Any = None, root: Path | None = None, profile: str | None = None) -> dict[str, Any]:
    """The pre-review flags of every segment of a draft (see the module). Reads the draft and the measured page facts only."""
    from jason.tasks import split_session as ss

    root = ss._root(root)
    profile = rs._profile(profile, community)
    session = ss.load(root, sid)
    facts = ss.read_facts(root, session.source.sha256)
    by_page: dict[int, PageFact] = {f.n: f for f in facts}
    boundary_pages = {b.page for b in session.ordered()}
    rejected = {s.page for s in session.suggestions if s.state == "rejected"}
    cap = int(limits.value("upload.max_bytes", community=community))
    segments = session.segments()
    tops = [s for s in segments if s.level == 0]
    hashes: dict[str, list[str]] = {}
    for seg in tops:
        hashes[seg.key] = [by_page[p].phash for p in range(seg.start, seg.end + 1) if p in by_page and by_page[p].phash]
    rows: list[dict[str, Any]] = []
    computed: list[Any] | None = None
    for seg in segments:
        pages = list(range(seg.start, seg.end + 1))
        known = [by_page[p] for p in pages if p in by_page and not by_page[p].pending]
        lab = session.label_of(seg.start)
        row: dict[str, Any] = {"segment": seg.key, "level": seg.level, "start": seg.start, "end": seg.end, "pages": len(pages),
                               "measured": len(known)}
        row["blankOnly"] = bool(known) and len(known) == len(pages) and all(f.blank == "blank" for f in known)
        row["sideways"] = [{"page": f.n, "turn": f.turn, "fix": f.fix} for f in known if f.sideways]
        estimate = round(session.source.size * len(pages) / max(session.pages, 1))
        row["estimatedBytes"] = estimate
        row["overPartLimit"] = estimate > cap
        row["partLimit"] = cap
        twin, repeated = "", []
        if seg.level == 0:
            mine = hashes.get(seg.key, [])
            order = [s.key for s in tops]
            for other in tops:
                if other.key == seg.key:
                    continue
                share = _share(mine, hashes.get(other.key, []))
                if share >= NEAR_SHARE:
                    if order.index(other.key) < order.index(seg.key):
                        twin = twin or other.key
                    else:
                        repeated.append(other.key)
        row["nearDuplicateOf"] = twin or None
        row["repeatedBy"] = repeated
        maybe = [{"page": p, "score": round(by_page[p].start_score, 2)} for p in pages[1:]
                 if p in by_page and p not in boundary_pages and p not in rejected and by_page[p].start_score >= split_suggest.FLOOR]
        maybe.sort(key=lambda m: -m["score"])
        row["mayHoldMore"] = maybe[:MAY_HOLD_MAX] if seg.level == 0 else []
        slot = lab.get("slot") or ""
        row["slot"] = slot
        if slot and computed is None:
            try:
                computed = rs.compute(community, root, profile)
            except Exception:  # noqa: BLE001 - a checklist that cannot be read says nothing about a slot
                computed = []
        row["slotFilled"] = bool(slot) and _slot_holds(computed or [], slot, lab.get("period") or "")
        row["flagged"] = bool(row["blankOnly"] or row["sideways"] or row["overPartLimit"] or row["nearDuplicateOf"] or row["repeatedBy"]
                              or row["mayHoldMore"] or row["slotFilled"])
        rows.append(row)
    counts = {
        "blankOnly": sum(1 for r in rows if r["blankOnly"]), "nearDuplicate": sum(1 for r in rows if r["nearDuplicateOf"]),
        "sideways": sum(len(r["sideways"]) for r in rows if r["level"] == 0), "overPartLimit": sum(1 for r in rows if r["overPartLimit"]),
        "mayHoldMore": sum(1 for r in rows if r["mayHoldMore"]), "slotFilled": sum(1 for r in rows if r["slotFilled"]),
    }
    parts_limit = int(limits.value("split.max_parts", community=community))
    return {"id": sid, "version": session.version, "segments": rows, "counts": counts,
            "measured": {"pages": len(by_page), "of": session.pages, "complete": len(by_page) >= session.pages},
            "parts": {"count": len(tops), "limit": parts_limit, "over": len(tops) > parts_limit},
            "caveats": list(CAVEATS)}


__all__ = ["CAVEATS", "HAMMING_BITS", "MAY_HOLD_MAX", "NEAR_SHARE", "flags", "same_page"]
