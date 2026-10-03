"""The duties, prohibitions, permissions, rights, and conditions in the governing documents, stored for review.

``run`` reads each outline on disk (``data/outlines``) with the phrase grammar (``jason.community.deontic``), marks
the sections an amendment set (``set_by``, from the living document when the document is kept as amended), and writes
``data/duties/<key>.json``. A person's review (confirmed, corrected, rejected, with a note) is kept by reading id and
survives a reread while the words stay the same; a reading whose words changed comes back unreviewed. ``tracking``
says whether a duty with a deadline or a recurrence is carried by one of the association's recurring deadlines
(``Community.obligations()``), the board calendar's events, or a notice rule (``Community.notice_rules()``); a duty no
row carries is a lead for a person, never a rule row. ``model_run`` asks the local model (free reading or hybrid) for
chosen passages and caches each answer by passage and words; ``evaluate`` scores any reader against a hand-labelled
gold set. Nothing here writes to PayHOA, Google, or anywhere but ``data/duties``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.community.deontic import (
    Bearer, DocumentDuty, DutyKind, NORMS, ReviewStatus, read_outline, sentences,
)
from jason.community.outlines import DocumentOutline


def duty_dir(data_dir: Path) -> Path:
    path = Path(data_dir) / "duties"
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_path(data_dir: Path, key: str) -> Path:
    return duty_dir(data_dir) / f"{key}.json"


# ---------------------------------------------------------------------------------------------------------------------
# Provenance


def provenance(data_dir: Path, key: str, community: Any = None) -> dict[str, str]:
    """Section number -> the instrument that last set its words, for a document kept as amended; empty otherwise or
    when its sources are not on disk (the living document is built from the copies saved by its last read)."""
    try:
        if community is None:
            from jason.community import community as active

            community = active()
        living = next((l for l in community.living_documents() if l.key == key), None)
        if living is None:
            return {}
        from jason.tasks.living_docs import build

        current = build(living, Path(data_dir)).current
    except Exception:
        return {}
    return {p.number: p.set_by for p in current.provisions if p.number and p.set_by and p.set_by != key}


def _set_by(section: str, sets: dict[str, str]) -> str:
    if section in sets:
        return sets[section]
    # A subsection set by an amendment of its parent ("4.15(m)(iii)" under a restated "4.15(m)").
    parents = [n for n in sets if section.startswith(n + "(") or section.startswith(n + ".")]
    return sets[max(parents, key=len)] if parents else ""


# ---------------------------------------------------------------------------------------------------------------------
# The store


def read_document(outline: DocumentOutline, *, sets: dict[str, str] | None = None) -> list[DocumentDuty]:
    """The grammar's readings of one outline (norms and definitions), each with the instrument that set its section."""
    sets = sets or {}
    return [replace(d, set_by=_set_by(d.section, sets)) if sets else d for d in read_outline(outline)]


def load_store(data_dir: Path, key: str) -> dict[str, Any]:
    path = store_path(data_dir, key)
    if not path.is_file():
        return {"source": key, "duties": [], "reviews": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def stored(data_dir: Path, key: str) -> list[DocumentDuty]:
    """The stored readings with each one's review applied (a correction replaces the fields it names)."""
    raw = load_store(data_dir, key)
    reviews = raw.get("reviews") or {}
    out = []
    for item in raw.get("duties") or ():
        duty = DocumentDuty.from_dict(item)
        out.append(_reviewed(duty, reviews.get(duty.id)))
    return out


def _reviewed(duty: DocumentDuty, review: dict[str, Any] | None) -> DocumentDuty:
    if not review:
        return duty
    changes: dict[str, Any] = {"review": ReviewStatus(review.get("status", "unreviewed")), "note": review.get("note", "")}
    if review.get("kind"):
        changes["kind"] = DutyKind(review["kind"])
    if review.get("bearer"):
        changes["bearer"] = Bearer(review["bearer"])
    if review.get("trackedBy"):
        changes["note"] = (changes["note"] + " " if changes["note"] else "") + f"[tracked by: {review['trackedBy']}]"
    return replace(duty, **changes)


def save(data_dir: Path, key: str, duties: list[DocumentDuty], *, reader: str = "grammar") -> dict[str, Any]:
    """Write ``duties`` for ``key``, keeping every review whose reading is still there; a review whose reading is gone
    (the words changed) is kept under ``orphaned`` for a person, never silently dropped."""
    from jason.locks import Resource, hold

    with hold(Resource.STORE, f"duties-{key}", timeout=60, purpose="jason duties"):
        old = load_store(data_dir, key)
        reviews = dict(old.get("reviews") or {})
        # A bearer the model filled (fill_bearers) stays with its reading while the words stay the same.
        hybrid = {item.get("id"): item for item in old.get("duties") or () if item.get("method") == "hybrid"}
        duties = [replace(d, bearer=Bearer(hybrid[d.id]["bearer"]), method="hybrid", note=hybrid[d.id].get("note", ""))
                  if d.id in hybrid and d.bearer is Bearer.UNSTATED else d for d in duties]
        # A permanent id the migration stored stays with its reading while the words stay the same.
        placed = {item.get("id"): item for item in old.get("duties") or () if item.get("pid")}
        duties = [replace(d, pid=placed[d.id]["pid"], version=placed[d.id].get("version", ""),
                          reading=placed[d.id].get("reading", "")) if d.id in placed and not d.pid else d
                  for d in duties]
        ids = {d.id for d in duties}
        orphaned = dict(old.get("orphaned") or {})
        for rid in list(reviews):
            if rid not in ids:
                orphaned[rid] = reviews.pop(rid)
        out = {"source": key, "reader": reader, "read": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "duties": [d.to_dict() for d in duties], "reviews": reviews, "orphaned": orphaned}
        store_path(data_dir, key).write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def review(data_dir: Path, key: str, duty_id: str, status: ReviewStatus, *, note: str = "", kind: DutyKind | None = None,
           bearer: Bearer | None = None, tracked_by: str = "", reviewer: str = "") -> dict[str, Any]:
    """Record a person's review of one reading. A correction names the kind or bearer it changes; ``tracked_by`` names
    what carries a timed duty (a recurring deadline, a calendar event, a notice rule, or a command) when the words alone
    do not show it."""
    from jason.locks import Resource, hold

    with hold(Resource.STORE, f"duties-{key}", timeout=60, purpose="jason duties --review"):
        raw = load_store(data_dir, key)
        ids = {DocumentDuty.from_dict(d).id for d in raw.get("duties") or ()}
        if duty_id not in ids:
            raise KeyError(f"no reading {duty_id} in {store_path(data_dir, key)}")
        entry = {"status": status.value, "note": note, "reviewer": reviewer,
                 "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if kind is not None:
            entry["kind"] = kind.value
        if bearer is not None:
            entry["bearer"] = bearer.value
        if tracked_by:
            entry["trackedBy"] = tracked_by
        raw.setdefault("reviews", {})[duty_id] = entry
        store_path(data_dir, key).write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return entry


def run(data_dir: Path, keys: Iterable[str] = (), *, community: Any = None) -> dict[str, Any]:
    """Read the chosen outlines (every governing outline but the annexations when none is named) and store them."""
    from jason.tasks.outlines import load

    outlines = {o.key: o for o in load(Path(data_dir))}
    chosen = list(keys) or [k for k, o in outlines.items() if o.kind not in ("annexation",)]
    missing = [k for k in chosen if k not in outlines]
    counts: dict[str, dict[str, int]] = {}
    for key in chosen:
        if key not in outlines:
            continue
        duties = read_document(outlines[key], sets=provenance(data_dir, key, community))
        save(data_dir, key, duties)
        counts[key] = dict(Counter(d.kind.value for d in duties))
    return {"documents": counts, "missing": missing}


# ---------------------------------------------------------------------------------------------------------------------
# What tracks a timed duty


_STOP = {"the", "and", "for", "with", "from", "that", "this", "shall", "must", "each", "every", "any", "all", "such", "which",
         "their", "its", "his", "her", "into", "upon", "within", "after", "before", "days", "year", "years", "association",
         "board", "owner", "owners", "member", "members", "directors", "unit", "units", "common", "area", "than", "least",
         "more", "less", "other", "party", "parties", "prior", "written", "provided", "provide", "cause"}


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


# The board calendar's events (``jason.community.board_calendar.EventKind``), by the words a duty uses for them.
CALENDAR_EVENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("board calendar: meeting notice", re.compile(r"\bnotice\b[^.]{0,80}\bmeetings?\b|\bmeetings?\b[^.]{0,80}\bnotice\b", re.I)),
    ("board calendar: hearing notice", re.compile(r"\bnotice\b[^.]{0,80}\bhearing\b|\bhearing\b[^.]{0,40}\bnotice\b", re.I)),
    ("board calendar: hearing decision", re.compile(r"\bdecision\b[^.]{0,80}\bhearing\b|\bhearing\b[^.]{0,80}\bdecision\b", re.I)),
    ("board calendar: regular meetings", re.compile(r"\bregular\s+meetings?\b[^.]{0,60}\bheld\b", re.I)),
    # jason's own models that carry a recurring deadline outside Community.obligations() (jason.tasks.deadlines).
    ("jason reserve-study: the studies on disk",
     re.compile(r"\breserve\s+study\b|\bvisual\s+inspection\b[^.]{0,80}\bmajor\s+components\b", re.I)),
    ("jason insurance: the policy register", re.compile(r"\b(?:renew|maintain|purchase|obtain)\w*\b[^.]{0,60}\binsurance\b", re.I)),
)


def _in_sections(section: str, listed: str) -> bool:
    """``section`` is one of the sections a notice provision names ("3.6(c), 3.6(d)"), or inside one of them."""
    for one in (s.strip() for s in listed.split(",")):
        if one and (section == one or section.startswith(one + "(") or section.startswith(one + ".")):
            return True
    return False


def tracking(duty: DocumentDuty, obligations: Iterable[Any] = (), notice_rules: Iterable[Any] = (),
             notice_provisions: Iterable[Any] = ()) -> str:
    """What carries ``duty``: a person's review, a notice provision of the notice catalog for its section, a recurring
    deadline's name, a calendar event, or a notice rule; "" when nothing does.

    A recurring deadline carries it when two of its name's words (or its only word) appear in the duty's words; a
    notice rule when two of its title's words do. This is a lead for a person, not a match to rely on."""
    marked = re.search(r"\[tracked by: ([^\]]+)\]", duty.note or "")
    if marked:
        return marked.group(1)                         # a person said what carries it
    if duty.notice:
        for p in notice_provisions:
            if getattr(p, "document", "") == duty.source and _in_sections(duty.section, getattr(p, "section", "")):
                return f"notice provision: {p.key}"
    words = _stems(duty.quote + " " + duty.action)
    for ob in obligations:
        name = _stems(getattr(ob, "name", ""))
        if name and len(name & words) >= min(2, len(name)):
            return f"obligation: {ob.name}"
    text = duty.quote + " " + duty.action
    for label, rx in CALENDAR_EVENTS:
        if rx.search(text):
            return label
    if duty.notice:
        for rule in notice_rules:
            title = _stems(getattr(rule, "title", ""))
            if title and len(title & words) >= min(2, len(title)):
                return f"notice rule: {rule.key}"
    return ""


def untracked(duties: Iterable[DocumentDuty], obligations: Iterable[Any] = (), notice_rules: Iterable[Any] = (),
              notice_provisions: Iterable[Any] = ()) -> list[tuple[DocumentDuty, str]]:
    """The duties with a deadline or a recurrence, each with what carries it ("" for nothing)."""
    obligations, notice_rules, notice_provisions = list(obligations), list(notice_rules), list(notice_provisions)
    return [(d, tracking(d, obligations, notice_rules, notice_provisions)) for d in duties
            if d.kind is DutyKind.DUTY and d.timed and d.review is not ReviewStatus.REJECTED]


# ---------------------------------------------------------------------------------------------------------------------
# The local model


def lead_sentences(outline: DocumentOutline) -> dict[int, str]:
    """Passage start -> the sentence that opens the list it belongs to (its nearest ancestor's last sentence, when that
    ends with a colon or breaks off unfinished)."""
    from jason.community.reference_model import passages

    leads: list[tuple[str, str]] = []
    out: dict[int, str] = {}
    for p in passages(outline, max_chars=1_000_000, min_chars=1):
        leads = [(sec, s) for sec, s in leads if p.section != sec and (p.section.startswith(sec + "(") or p.section.startswith(sec + "."))]
        if leads:
            out[p.start] = leads[-1][1]
        spans = sentences(p.text)
        if spans and p.section:
            last = p.text[spans[-1][0]:spans[-1][1]]
            if last.rstrip().endswith(":") or not re.search(r"[.!?\"'”)]\s*$", last):
                leads.append((p.section, " ".join(last.split())[:400]))
    return out


def model_store(data_dir: Path, model: str, strategy: str) -> Path:
    path = duty_dir(data_dir) / "model"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"{re.sub(r'[^A-Za-z0-9.-]+', '_', model)}-{strategy}.json"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def model_run(data_dir: Path, passage_ids: Iterable[str], *, strategy: str = "read", reader: Any = None, again: bool = False,
              log=print) -> dict[str, Any]:
    """Ask the model about each passage ("source@start") and cache its raw answer and timing by passage and words.
    ``strategy`` is "read" (free reading) or "review" (the grammar's candidates). Returns the cache."""
    import time

    from jason.community.duty_model import DutyModel
    from jason.community.reference_model import passages
    from jason.tasks.outlines import load

    reader = reader or DutyModel()
    outlines = {o.key: o for o in load(Path(data_dir))}
    path = model_store(data_dir, reader.model, strategy)
    cache = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"model": reader.model, "answers": {}}
    grammar: dict[str, list[DocumentDuty]] = {}
    rows: dict[str, dict[int, Any]] = {}
    leads: dict[str, dict[int, str]] = {}
    for pid in passage_ids:
        source, start = pid.rsplit("@", 1)
        outline = outlines[source]
        if source not in rows:
            rows[source] = {x.start: x for x in passages(outline, max_chars=1_000_000, min_chars=1)}
            leads[source] = lead_sentences(outline)
        p = rows[source][int(start)]
        lead = leads[source].get(p.start, "")
        digest = _digest(p.text + "|" + lead)
        if not again and cache["answers"].get(pid, {}).get("digest") == digest:
            continue
        where = {"source": source, "title": outline.title, "section": p.section, "caption": p.title, "lead": lead}
        began = time.monotonic()
        asked: list[int] = []
        if strategy == "review":
            if source not in grammar:
                grammar[source] = read_outline(outline)
            cands = candidates_in(grammar[source], p.start, p.start + len(p.text))
            asked = [c.marker_at for c in cands]
            raw = reader.review(p.text, cands, **where) if cands else '{"candidates": [], "missed": []}'
        else:
            raw = reader.read(p.text, **where)
        cache["answers"][pid] = {"digest": digest, "raw": raw, "seconds": round(time.monotonic() - began, 2),
                                 "candidates": asked}
        path.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        log(f"{pid} {cache['answers'][pid]['seconds']}s")
    return cache


def fill_bearers(data_dir: Path, key: str, *, reader: Any = None, log=print) -> dict[str, Any]:
    """Ask the model (the hybrid's review) about each passage of ``key`` where the grammar left a bearer unstated, and
    store the model's bearer for those readings only (``method="hybrid"``, noted). The grammar's kinds and timing stay:
    on the gold sets they measured better than the model's (docs/document-duties.md). A reviewed reading is not
    touched. Answers are cached, so a rerun asks only about changed passages."""
    from jason.community.duty_model import DutyModel
    from jason.community.reference_model import passages
    from jason.tasks.outlines import load

    reader = reader or DutyModel()
    outline = next(o for o in load(Path(data_dir)) if o.key == key)
    current = stored(data_dir, key)
    gaps = [d for d in current if d.kind in NORMS and d.bearer is Bearer.UNSTATED and d.review is ReviewStatus.UNREVIEWED]
    rows = passages(outline, max_chars=1_000_000, min_chars=1)
    ids = sorted({f"{key}@{p.start}" for p in rows for d in gaps if p.start <= d.marker_at < p.start + len(p.text)},
                 key=lambda pid: int(pid.rsplit("@", 1)[1]))
    model_run(data_dir, ids, strategy="review", reader=reader, log=log)
    filled = {d.marker_at: d.bearer for found in readings(data_dir, ids, "hybrid-fill", model=reader.model).values()
              for d in found if d.bearer is not Bearer.UNSTATED}
    from jason.locks import Resource, hold

    changed = 0
    with hold(Resource.STORE, f"duties-{key}", timeout=60, purpose="jason duties --fill-bearers"):
        raw = load_store(data_dir, key)
        for item in raw.get("duties") or ():
            duty = DocumentDuty.from_dict(item)
            if duty.bearer is Bearer.UNSTATED and duty.marker_at in filled and duty.id not in (raw.get("reviews") or {}):
                item["bearer"] = filled[duty.marker_at].value
                item["method"] = "hybrid"
                item["note"] = f"bearer read by {reader.model}; the words leave it out"
                changed += 1
        store_path(data_dir, key).write_text(json.dumps(raw, indent=1), encoding="utf-8")
    return {"document": key, "asked": len(ids), "unstated": len(gaps), "filled": changed}


# A candidate asked about that the grammar no longer reads: its verdict is set aside.
_GONE = DocumentDuty(source="", section="", start=-1, end=-1, quote="", kind=DutyKind.DEFINITION, bearer=Bearer.UNSTATED,
                     marker="gone", marker_at=-10)


def candidates_in(items: list[DocumentDuty], start: int, end: int) -> list[DocumentDuty]:
    return [d for d in items if start <= d.marker_at < end and d.kind in NORMS]


def readings(data_dir: Path, passage_ids: Iterable[str], strategy: str, *, model: str = "") -> dict[str, list[DocumentDuty]]:
    """Passage id -> the readings of one strategy: "grammar"; "model" (the cached free readings); "hybrid" (the cached
    reviews: the model's kind, bearer, and timing on the grammar's candidates, plus what it says they missed); or
    "hybrid-fill" (the grammar's kinds, the model filling only a bearer or timing the grammar left out)."""
    from jason.community.duty_model import merge_review, to_duties
    from jason.community.reference_model import passages
    from jason.tasks.outlines import load

    outlines = {o.key: o for o in load(Path(data_dir))}
    grammar: dict[str, list[DocumentDuty]] = {}
    cache: dict[str, Any] = {}
    if strategy != "grammar":
        from jason.community.ollama_extractor import DEFAULT_MODEL

        path = model_store(data_dir, model or DEFAULT_MODEL, "read" if strategy == "model" else "review")
        cache = json.loads(path.read_text(encoding="utf-8"))["answers"] if path.is_file() else {}
    out: dict[str, list[DocumentDuty]] = {}
    rows: dict[str, dict[int, Any]] = {}
    for pid in passage_ids:
        source, start = pid.rsplit("@", 1)
        outline = outlines[source]
        if source not in rows:
            rows[source] = {x.start: x for x in passages(outline, max_chars=1_000_000, min_chars=1)}
        p = rows[source][int(start)]
        if source not in grammar:
            grammar[source] = read_outline(outline)
        cands = candidates_in(grammar[source], p.start, p.start + len(p.text))
        if strategy == "grammar":
            out[pid] = cands
            continue
        answer = cache.get(pid) or {}
        raw = answer.get("raw")
        if raw is None:
            continue                                   # not asked: left out of the score, not scored as empty
        if strategy == "model":
            out[pid] = to_duties(raw, p.text, source=source, section=p.section, base=p.start)[0]
        else:
            # The candidates as they were asked, by marker: a grammar changed since cannot shift the model's verdicts.
            if answer.get("candidates") is not None:
                by_marker = {c.marker_at: c for c in cands}
                asked = [by_marker.get(at) for at in answer["candidates"]]
                extra = [c for c in cands if c.marker_at not in set(answer["candidates"])]
                cands = [c if c is not None else _GONE for c in asked]
                merged, _ = merge_review(raw, cands, p.text, source=source, section=p.section, base=p.start,
                                         fill_only=strategy == "hybrid-fill")
                out[pid] = [d for d in merged if d is not _GONE and d.marker != "gone"] + extra
                continue
            out[pid] = merge_review(raw, cands, p.text, source=source, section=p.section, base=p.start,
                                    fill_only=strategy == "hybrid-fill")[0]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Scoring against a gold set


def evaluate(gold: list[dict[str, Any]], found: dict[str, list[DocumentDuty]], texts: dict[str, str]) -> dict[str, Any]:
    """Precision and recall of ``found`` (passage id -> readings) against ``gold`` (the gold file's passages), and the
    accuracy of bearer, deadline, recurrence, and notice on the readings whose kind matched.

    A reading matches a gold item when its marker sits inside the item's quote (three characters either side); each is
    matched once, a same-kind reading first. An optional gold item absorbs a reading without counting either way.
    ``texts`` maps a passage id to its words (to place the quotes). Passages ``found`` has no entry for are skipped."""
    from jason.community.reference_model import find_quote

    tp = fp = fn = detected = 0
    fields = {"bearer": [0, 0], "deadline": [0, 0], "recurrence": [0, 0], "notice": [0, 0]}
    by_kind: dict[str, list[int]] = {k.value: [0, 0, 0] for k in NORMS}          # tp, fp, fn
    errors: list[str] = []
    scored = 0
    for entry in gold:
        pid = entry["id"]
        if pid not in found:
            continue
        scored += 1
        base = int(pid.rsplit("@", 1)[1])
        text = texts[pid]
        preds = [d for d in found[pid] if d.kind in NORMS]
        items = []
        for it in entry["items"]:
            span = find_quote(text, it["quote"])
            if span is None:
                raise ValueError(f"{pid}: gold quote not in the passage: {it['quote']}")
            items.append((base + span[0], base + span[1], it))
        used: set[int] = set()
        for gs, ge, it in items:
            kinds = [it["kind"], *it.get("alt", [])]
            near = [k for k, d in enumerate(preds) if k not in used and gs - 3 <= d.marker_at <= ge + 3]
            same = [k for k in near if preds[k].kind.value in kinds]
            pick = (same or near or [None])[0]
            if pick is None:
                if not it.get("optional"):
                    fn += 1
                    by_kind[it["kind"]][2] += 1
                    errors.append(f"{pid} missed {it['kind']}: {it['quote']}")
                continue
            used.add(pick)
            d = preds[pick]
            if it.get("optional"):
                continue
            detected += 1
            if d.kind.value in kinds:
                tp += 1
                by_kind[it["kind"]][0] += 1
                for name, ok in (("bearer", d.bearer.value in it["bearer"]),
                                 ("deadline", (d.deadline is not None) == bool(it.get("deadline"))),
                                 ("recurrence", d.recurrence_months == it.get("recurrence", 0)),
                                 ("notice", d.notice == bool(it.get("notice")))):
                    fields[name][0] += ok
                    fields[name][1] += 1
                    if not ok:
                        errors.append(f"{pid} {name} wrong ({getattr(d, name) if name != 'deadline' else d.deadline}): {it['quote']}")
            else:
                fn += 1
                fp += 1
                by_kind[it["kind"]][2] += 1
                by_kind[d.kind.value][1] += 1
                errors.append(f"{pid} kind {d.kind.value} for {it['kind']}: {it['quote']}")
        for k, d in enumerate(preds):
            if k not in used:
                fp += 1
                by_kind[d.kind.value][1] += 1
                errors.append(f"{pid} extra {d.kind.value} [{d.marker}]: {' '.join(d.quote.split())[:120]}")
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"passages": scored, "tp": tp, "fp": fp, "fn": fn, "detected": detected, "precision": round(precision, 3),
            "recall": round(recall, 3), "f1": round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0,
            "fields": {k: f"{a}/{b}" for k, (a, b) in fields.items()},
            "byKind": {k: {"tp": a, "fp": b, "fn": c} for k, (a, b, c) in by_kind.items()}, "errors": errors}


def gold_texts(data_dir: Path, gold: list[dict[str, Any]]) -> dict[str, str]:
    from jason.community.reference_model import passages
    from jason.tasks.outlines import load

    outlines = {o.key: o for o in load(Path(data_dir))}
    out = {}
    for entry in gold:
        source, start = entry["id"].rsplit("@", 1)
        out[entry["id"]] = next(p.text for p in passages(outlines[source], max_chars=1_000_000, min_chars=1)
                                if p.start == int(start))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Lines for the command


def describe(d: DocumentDuty) -> str:
    timing = []
    if d.deadline is not None:
        timing.append(d.deadline.text)
    if d.recurrence:
        timing.append(d.recurrence)
    bits = [f"[{d.kind.value}] {d.bearer.value}"]
    if d.bearer is Bearer.UNSTATED and d.passive:
        bits.append("(passive)")
    if d.inherited:
        bits.append("(list item)")
    head = " ".join(bits)
    line = f"{d.source}#{d.section} {head}: {' '.join(d.quote.split())[:200]}"
    if timing:
        line += f"  | when: {'; '.join(timing)}"
    if d.trigger:
        line += f"  | trigger: {d.trigger[:80]}"
    if d.set_by:
        line += f"  | set by {d.set_by}"
    if d.review is not ReviewStatus.UNREVIEWED:
        line += f"  | {d.review.value}" + (f": {d.note}" if d.note else "")
    return line


__all__ = ["duty_dir", "store_path", "provenance", "read_document", "load_store", "stored", "save", "review", "run",
           "tracking", "untracked", "lead_sentences", "model_run", "readings", "evaluate", "gold_texts", "describe",
           "candidates_in", "CALENDAR_EVENTS"]
