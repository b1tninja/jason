"""The read side of community facts, a unit's effective record, and the loss packet (docs/unit-records-backend.md).

Disk only: the profile's facts, specifications, coverage lists and ladder, a unit's stored entries and packet
confirmations, and the words of each provision as the shelf holds them. Nothing calls PayHOA, Google, or a model. jason
informs and decides nothing: a reading points to a document, and the carrier decides coverage and the board and counsel
decide responsibility.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.facts import FactStatus, ScopeKind, coverage_by_plan
from jason.community.loss_packet import LadderStep, OpenQuestion, StepRecord, assemble
from jason.community.unit_record import ComponentKind, ComponentStatus, ImprovementEntry, OriginalSpec, coverage, effective

CAVEAT = "A reading is evidence, not a pin; the carrier decides coverage and the board and counsel decide responsibility."


def plain(value: Any) -> Any:
    """A record as JSON: enums as their words, tuples as lists, dataclasses as objects."""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [plain(v) for v in value]
    return value


def _unit_dir(root: Path, unit: str) -> Path:
    from jason.community.profile import profile_name

    safe = "".join(c for c in unit if c.isalnum() or c in "-_")
    if not safe:
        raise ValueError("a unit id is required")
    return Path(root) / profile_name() / "units" / safe


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _recite(expression: str, community: Any, root: Path, shelf: Any) -> dict[str, Any]:
    from jason.tasks.cite import resolve

    got = resolve(expression, community=community, data_dir=root, shelf=shelf)
    return {"expression": expression, "found": bool(got.get("found")), "citation": got.get("citation", ""),
            "text": got.get("text", "") if got.get("found") else "", "reason": "" if got.get("found") else got.get("reason", "")}


def facts_view(root: Path, community: Any, *, topic: str = "", q: str = "", scope: str = "", status: str = "") -> dict[str, Any]:
    """The community's facts, filtered by topic, words, scope kind, or status, with the coverage of each plan."""
    facts = tuple(community.facts())
    if not facts:
        return {"found": False, "note": "the specification holds no community facts", "facts": [], "topics": [], "coverage": []}
    words = q.strip().casefold()
    shown = [
        f for f in facts
        if (not topic or topic in f.topics)
        and (not scope or f.scope.kind.value == scope)
        and (not status or f.status.value == status)
        and (not words or words in f.statement.casefold() or any(words in a.casefold() for a in f.answers))
    ]
    questions = {oq.key: oq for oq in community.open_questions()}
    from jason.approvals.docref import refs_from_strings

    rows = []
    for f in shown:
        row = plain(f)
        row["sourceRefs"] = refs_from_strings(f.sources, data_dir=Path(root)) if f.sources else []
        rows.append(row)
    plans = sorted({s.plan for s in community.original_specs()})
    return {
        "found": True,
        "facts": rows,
        "total": len(facts),
        "topics": sorted({t for f in facts for t in f.topics}),
        "statuses": [s.value for s in FactStatus],
        "scopes": [s.value for s in ScopeKind],
        "coverage": plain(coverage_by_plan(facts, plans)),
        "openQuestions": [plain(oq) for oq in questions.values()],
        "caveat": "A fact marked assumed is a default, not a record.",
    }


def _entries(root: Path, unit: str, *, owner: bool) -> tuple[list[ImprovementEntry], int]:
    raw = _read_json(_unit_dir(root, unit) / "entries.json", [])
    out: list[ImprovementEntry] = []
    held = 0
    for row in raw if isinstance(raw, list) else []:
        try:
            known = {f.name for f in fields(ImprovementEntry)}  # a stored row may carry more (a visibility history)
            entry = ImprovementEntry(
                **{**{k: v for k, v in row.items() if k in known}, "kind": ComponentKind(row["kind"]),
                   "status": ComponentStatus(row.get("status", "upgrade")),
                   "photos": tuple(row.get("photos") or ()), "docs": tuple(row.get("docs") or ())})
        except (KeyError, TypeError, ValueError):
            continue
        if entry.visibility == "private" and not owner:
            held += 1
            continue
        out.append(entry)
    return out, held


def unit_record_view(root: Path, community: Any, unit: str, *, plan: str = "", owner: bool = False) -> dict[str, Any]:
    """A unit's effective components against the declaration's and the policy's lists. Without a plan every component is
    unknown (``effective``'s rule); a private entry is the owner's alone and is counted, never listed."""
    root = Path(root)
    entries, held = _entries(root, unit, owner=owner)
    specs: tuple[OriginalSpec, ...] = tuple(community.original_specs())
    unit_coverage = community.unit_coverage()
    components = effective(plan, specs, entries) if plan else effective("", specs, entries)
    rows = []
    for c in components:
        decl, pol = coverage(c.kind, c.status, unit_coverage)
        row = plain(c)
        row["declaration"], row["policy"] = plain(decl), plain(pol)
        rows.append(row)
    questions = {oq.key: oq for oq in community.open_questions()}
    keys = {r[side]["differs"] for r in rows for side in ("declaration", "policy") if r[side].get("differs")}
    return {
        "found": True,
        "unit": unit,
        "plan": plan,
        "planMatched": bool(plan and any(s.plan == plan for s in specs)),
        "components": rows,
        "privateHeld": held,
        "openQuestions": [plain(questions[k]) for k in sorted(keys) if k in questions],
        "caveat": CAVEAT,
    }


def loss_packet_view(root: Path, community: Any, unit: str, incident: str = "", *, address: str = "") -> dict[str, Any]:
    """The five-step ladder with each provision's words recited from the shelf, the master policy, the unit's history, and
    a person's confirmations. A provision the shelf cannot find is a held note, never a paraphrase."""
    from jason.mcp.county import incident_history, insurance_policies
    from jason.tasks.cite import cite

    root = Path(root)
    ladder: tuple[LadderStep, ...] = tuple(community.loss_ladder())
    if not ladder:
        return {"found": False, "note": "the specification holds no loss ladder", "steps": []}
    shelf = cite(community, root)
    recited: dict[str, str] = {}
    for expression in sorted({p for row in ladder for p in row.provisions}):
        got = _recite(expression, community, root, shelf)
        if got["found"] and got["text"]:
            recited[expression] = got["text"]
    policies = insurance_policies(data_dir=root)
    policy = next((p for p in policies.get("policies") or [] if p.get("key") == "master"), None)
    history: list[str] = []
    if address:
        for event in incident_history(address=address, limit=20, data_dir=root).get("events") or []:
            title = event.get("title") or event.get("summary") or event.get("what") or ""
            if title:
                history.append(f"{event.get('date') or event.get('at') or ''} {title}".strip())
    saved = _read_json(_unit_dir(root, unit) / "packets" / f"{incident or 'unit'}.json", {})
    record = {int(k): StepRecord(**v) for k, v in (saved.get("steps") or {}).items() if isinstance(v, dict)}
    questions = tuple(community.open_questions())
    packet = assemble(unit, incident, record, ladder, policy, history, community.deductible_policy(),
                      recited=recited, questions=questions)
    out = plain(packet)
    out["found"] = True
    out["policy"] = None if policy is None else {k: policy.get(k) for k in ("key", "kind", "carrier", "number", "renewal", "deductibleCents")}
    out["caveat"] = CAVEAT
    return out
