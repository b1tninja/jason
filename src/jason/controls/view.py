"""What the Controls screen and ``jason controls`` show: each control as a row, the counts, the roster check, the places a
control bites, and the one-line notice at the point of an act (docs/console/screens/controls.md, "Data").

Reads only. Every state is a word made here (the page invents none); a suggestion never says it is in force; the
roster check names offices and counts, never a person. The provision's words are the stored ones, whole.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from jason.approvals import registry
from jason.approvals.registry import Approver
from jason.controls import effective, store, suggest
from jason.controls.catalog import CATALOG
from jason.controls.types import (Control, ControlFamily, ControlState, GovernsKind, ParamKind, history_to_dict,
                                  parameters_to_dict, scope_to_dict)

LABEL = "jason suggests; the board adopts"
READING_LABEL = suggest.LABEL
EMPTY = "jason has not read your governing documents. Ingest them from Onboarding."
CAVEATS = (
    "jason suggests; the board adopts. A control only adds to what the law, the governing documents, or a built-in rule "
    "already set, and is in force only from its effective date.",
    "The provision's words are the stored text, whole. jason's reading is jason's, not the provision.",
    "The roster check names offices and counts, never a person.",
)
FAMILY_TITLES = {ControlFamily.MONEY: "Money", ControlFamily.CONTRACTS: "Contracts", ControlFamily.REVIEWS: "Reviews",
                 ControlFamily.NOTICES: "Notices", ControlFamily.MEETINGS: "Meetings",
                 ControlFamily.ONBOARDING: "Onboarding"}
STATE_ORDER = ("adopted", "proposed", "suggested", "deferred", "declined", "retired")
FAMILIES = tuple(f.value for f in ControlFamily)
STATES = tuple(s.value for s in ControlState)


# --- words ---------------------------------------------------------------------------------------------------------------

def _short(title: str) -> str:
    return title.split(" (")[0].strip().lower()


def _value(spec: Any, value: Any) -> str:
    k = spec.kind
    if k in (ParamKind.ELIGIBLE, ParamKind.REQUIRED):
        return ", ".join(r.value for r in value) or "any board member"
    if k is ParamKind.CENTS:
        return f"${value / 100:,.2f}"
    if k is ParamKind.DAYS:
        return f"{value} days"
    if k is ParamKind.FLAG:
        return "yes" if value else "no"
    return str(value)


def describe(control: Control) -> str:
    """One line of what the control requires, from its parameters as they stand; what only the board sets is said so."""
    bits = []
    for p in control.type.parameters:
        if p.key in control.parameters:
            bits.append(f"{_short(p.title)}: {_value(p, control.parameters[p.key])}")
    open_ = [_short(control.type.spec(k).title) for k in control.type.board_sets if k not in control.parameters]
    if open_ and control.state in (ControlState.SUGGESTED, ControlState.PROPOSED):
        bits.append("the board sets: " + ", ".join(open_))
    return "; ".join(bits) or control.type.title


def standing(control: Control, now: effective.InForce) -> tuple[str, str]:
    """(a key for the glyph, the state in words). An adopted control is in force only from its date; a suggestion is never."""
    s = control.state
    if s is ControlState.ADOPTED:
        if now.ok:
            if now.lacks:
                return "in-force-roster-lacks", "adopted, in force; the roster cannot satisfy it, so the acts it governs are refused"
            return "in-force", f"adopted, in force since {control.effective.isoformat()}"
        if control.effective is None:
            return "adopted-not-in-force", "adopted, not in force: no effective date is set"
        return "adopted-not-in-force", f"adopted, not in force: takes effect {control.effective.isoformat()}" + (
            f" (the roster could not satisfy it now: {now.lacks})" if now.lacks else "")
    return s.value, {"suggested": "suggested", "proposed": "proposed to the board", "declined": "declined",
                     "deferred": "deferred", "retired": "retired"}[s.value]


# --- the roster ------------------------------------------------------------------------------------------------------------

def roster_of(community: Any) -> tuple[Any, ...] | None:
    """The offices people hold, or None when the profile's roster cannot be read (the check is then skipped, and said so)."""
    try:
        return tuple(community.officers())
    except Exception:  # noqa: BLE001 - a roster that cannot be read leaves the roster check out
        return None


def roster_check(control: Control, roster: Iterable[Any] | None) -> dict[str, Any]:
    """What the control needs, what is seated, and what is missing, by office and count. Never a name."""
    if roster is None:
        return {"read": False, "needs": [], "seated": [], "missing": [], "lacks": ""}
    held = effective._holders(roster)
    seated = [{"office": r.value, "count": len(names)} for r, names in sorted(held.items(), key=lambda kv: kv[0].value)]
    needs: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    if effective._has(control, "signers"):
        need = control.value("signers") or 1
        roles = control.value("roles") or ()
        noun = effective._noun(roles)
        needs.append({"office": noun, "count": need})
        eligible = set().union(*(held.get(r, set()) for r in (roles or effective.BOARD_ROLES)))
        if len(eligible) < need:
            missing.append({"office": noun})
    for p in control.type.parameters:
        if p.kind is ParamKind.REQUIRED:
            for role in control.value(p.key) or ():
                if not any(n["office"] == role.value for n in needs):
                    needs.append({"office": role.value, "count": 1})
                if not held.get(role):
                    missing.append({"office": role.value})
    return {"read": True, "needs": needs, "seated": seated, "missing": missing,
            "lacks": effective.roster_problem(control, roster)}


# --- a control as a row ------------------------------------------------------------------------------------------------

def _decision(root: Path, control: Control) -> dict[str, Any] | None:
    """The decision the secretary recorded: its id, and (open session only) its meeting, outcome, and vote counts."""
    if not control.decision:
        return None
    out: dict[str, Any] = {"id": control.decision}
    try:
        from jason.tasks import decisions

        d = next((x for x in decisions.load(root) if x.id == control.decision), None)
        if d is not None and not decisions.is_executive(d):
            out.update({"meeting": d.meeting, "outcome": d.outcome, "tally": decisions.tally(d.votes)})
    except Exception:  # noqa: BLE001 - a decision that cannot be read is still named by its id
        pass
    return out


def row(control: Control, *, today: date, roster: Iterable[Any] | None, root: Path,
        items: Mapping[str, Any] | None = None, changed: Mapping[str, Any] | None = None,
        kinds: Iterable[Any] | None = None) -> dict[str, Any]:
    from jason.controls.propose import item_id

    roster = tuple(roster) if roster is not None else None
    now = effective.in_force(control, today, roster)
    glyph, word = standing(control, now)
    ctype = control.type
    item = (items or {}).get(item_id(control.key))
    provision_floor = parameters_to_dict(ctype, control.basis.floor) if control.basis.floor else None
    floor_read = bool(provision_floor)
    return {
        "key": control.key, "type": ctype.key, "title": ctype.title, "family": ctype.family.value,
        "familyTitle": FAMILY_TITLES[ctype.family], "scope": scope_to_dict(control.scope),
        "parameters": parameters_to_dict(ctype, control.parameters), "summary": describe(control),
        "boardSets": [k for k in ctype.board_sets if k not in control.parameters],
        "state": control.state.value, "standing": glyph, "stateWord": word,
        "inForce": {"ok": now.ok, "reason": now.reason, "lacks": now.lacks},
        "basis": {"citation": control.basis.citation, "words": control.basis.words, "floor": provision_floor},
        "floor": {"provision": provision_floor, "catalog": parameters_to_dict(ctype, ctype.floor) or None,
                  "read": floor_read,
                  "note": "" if floor_read else "floor: read by a person (jason reads a floor only where one count is certain)"},
        "reading": control.reading, "readingLabel": READING_LABEL if control.reading else "",
        "touches": effective.touches(control, kinds),
        "proposedAs": item.id if item is not None else None,
        "proposedStatus": item.status.value if item is not None else None,
        "decision": _decision(root, control), "effective": control.effective.isoformat() if control.effective else "",
        "history": [history_to_dict(h) for h in control.history],
        "roster": roster_check(control, roster), "missing": [m["office"] for m in roster_check(control, roster)["missing"]],
        "changed": (changed or {}).get(control.key),
    }


def _rank(r: Mapping[str, Any]) -> tuple[int, int, str]:
    order = ["in-force", "in-force-roster-lacks", "adopted-not-in-force"]
    first = STATE_ORDER.index(r["state"])
    sub = order.index(r["standing"]) if r["standing"] in order else 0
    return first, sub, r["title"]


def _check(family: str, state: str) -> None:
    if family and family not in FAMILIES:
        raise ValueError(f"family is one of {', '.join(FAMILIES)}")
    if state and state not in STATES:
        raise ValueError(f"state is one of {', '.join(STATES)}")


def counts_of(rows: list[dict[str, Any]], questions: int = 0, refused: int = 0) -> dict[str, int]:
    by = {s: sum(1 for r in rows if r["state"] == s) for s in STATES}
    forced = sum(1 for r in rows if r["standing"] in ("in-force", "in-force-roster-lacks"))
    return {"total": len(rows), "adopted": by["adopted"], "inForce": forced, "adoptedNotInForce": by["adopted"] - forced,
            "proposed": by["proposed"], "suggested": by["suggested"], "declined": by["declined"],
            "deferred": by["deferred"], "retired": by["retired"], "questions": questions, "refused": refused}


def heading(c: Mapping[str, int]) -> str:
    bits = []
    if c["adopted"]:
        bits.append(f"{c['adopted']} adopted" + (f" ({c['inForce']} in force, {c['adoptedNotInForce']} not in force)"
                                                 if c["adoptedNotInForce"] else " (in force)"))
    for key, word in (("proposed", "proposed to the board"), ("suggested", "suggested"), ("deferred", "deferred"),
                      ("declined", "declined"), ("retired", "retired"), ("questions", "question(s) for the board or counsel"),
                      ("refused", "refused")):
        if c[key]:
            bits.append(f"{c[key]} {word}")
    return "; ".join(bits) or "no controls yet"


def _items(root: Path) -> dict[str, Any]:
    from jason.tasks import board_items

    try:
        return {i.id: i for i in board_items.load(root)}
    except Exception:  # noqa: BLE001 - a board list that cannot be read leaves the links out, not the controls
        return {}


# --- the list ---------------------------------------------------------------------------------------------------------------

def compose(community: Any, data_dir: Path, *, family: str = "", state: str = "", today: date | None = None,
            profile: str = "") -> dict[str, Any]:
    """Every control now (the facts', the profile's, and the act log folded in), grouped by family, with the counts. The
    suggestions are the ones recorded as ``suggested`` acts; the questions are the last reading's."""
    _check(family, state)
    today = today or date.today()
    root = Path(data_dir)
    controls = store.load(root, profile, community)
    roster = roster_of(community)
    items = _items(root)
    readings = suggest.load_readings(root)
    changed = {c["key"]: c for c in readings.get("changed", []) if c.get("key")}
    rows = [row(c, today=today, roster=roster, root=root, items=items, changed=changed) for c in controls]
    questions = [{**q, "kind": "question", "familyTitle": FAMILY_TITLES[ControlFamily(q["family"])]}
                 for q in readings.get("questions", [])]
    total = counts_of(rows, len(questions), 0)
    shown = [r for r in rows if (not family or r["family"] == family) and (not state or r["state"] == state)]
    shown.sort(key=lambda r: (FAMILIES.index(r["family"]),) + _rank(r))
    asked = [q for q in questions if (not family or q["family"] == family) and not state]
    groups = []
    for f in ControlFamily:
        mine = [r for r in shown if r["family"] == f.value]
        qs = [q for q in asked if q["family"] == f.value]
        if mine or qs:
            groups.append({"family": f.value, "title": FAMILY_TITLES[f], "controls": mine, "questions": qs})
    empty = not rows and not questions and not readings.get("read")
    return {"found": True, "asOf": today.isoformat(), "label": LABEL, "readingLabel": READING_LABEL,
            "counts": total, "heading": heading(total), "families": groups, "controls": shown, "questions": asked,
            "refused": [], "read": readings.get("read") or "", "empty": EMPTY if empty else "",
            "rosterRead": roster is not None, "caveats": list(CAVEATS),
            "types": [{"key": t.key, "title": t.title, "family": t.family.value} for t in CATALOG]}


def one(community: Any, data_dir: Path, key: str, *, today: date | None = None, profile: str = "") -> dict[str, Any]:
    """One control with its provision as the documents hold it now: the six bands' data. A provision whose words changed since
    the control was recorded carries ``changed`` (was and now); the control stays as the board left it."""
    if not key:
        raise ValueError("key names a control (GET /api/controls lists them)")
    today = today or date.today()
    root = Path(data_dir)
    try:
        control = store.get(key, root, profile, community)
    except KeyError:
        return {"found": False, "key": key, "note": f"no control {key}"}
    readings = suggest.load_readings(root)
    changed = {c["key"]: c for c in readings.get("changed", []) if c.get("key")}
    out = row(control, today=today, roster=roster_of(community), root=root, items=_items(root), changed=changed)
    now = _current_words(community, root, control)
    if now.get("found") and control.basis.words and suggest.digest_of(now["words"]) != suggest.digest_of(control.basis.words):
        out["changed"] = {"was": control.basis.words, "now": now["words"], "changedOn": now.get("changedOn") or "",
                          "basis": "the governing documents' date", "citation": control.basis.citation}
    return {"found": True, "control": out, "provision": now, "label": LABEL, "readingLabel": READING_LABEL,
            "caveats": list(CAVEATS)}


def _current_words(community: Any, root: Path, control: Control) -> dict[str, Any]:
    """The provision as the documents hold it now, by its citation (best effort: the cite shelf, disk only)."""
    if not control.basis.citation:
        return {"found": False, "note": "the control cites no provision"}
    try:
        from jason.tasks.cite import resolve

        got = resolve(control.basis.citation, community=community, data_dir=root)
    except Exception as exc:  # noqa: BLE001 - a shelf that cannot be read leaves the stored words, said so
        return {"found": False, "note": f"the documents could not be read: {type(exc).__name__}"}
    if not got.get("found"):
        return {"found": False, "note": got.get("detail") or got.get("reason") or "not found",
                "citation": control.basis.citation}
    version = got.get("version") or {}
    return {"found": True, "citation": got.get("citation") or control.basis.citation, "words": got.get("text") or "",
            "address": got.get("address") or "", "changedOn": version.get("dated") or "",
            "setBy": version.get("setByTitle") or "", "outline": got.get("outline") or []}


# --- the notice at the point of an act -------------------------------------------------------------------------------------

def _notice(c: Control, why: str = "") -> dict[str, Any]:
    return {"key": c.key, "title": c.type.title, "adoptedOn": c.adopted_at,
            "effective": c.effective.isoformat() if c.effective else "", "effect": describe(c),
            "link": f"#/controls?key={c.key}", **({"reason": why} if why else {})}


def _subjects() -> set[str]:
    out = {k.key for k in registry.kinds()} | {a for k in registry.kinds() for a in k.aliases}
    for t in CATALOG:
        out |= {g.what for g in t.governs if g.kind is not GovernsKind.APPROVAL_KIND}
    return out


def notices(community: Any, data_dir: Path, subject: str, *, today: date | None = None, profile: str = "",
            amount_cents: int | None = None) -> dict[str, Any]:
    """Where a control bites, for the one-line notice: the effective rule of an approval kind (the kind's own rule and every
    control in force, stricter in each respect) with the sentence a plan shows; the controls adopted but not yet in force
    (the muted form, never as required); and the acts refused because the roster cannot satisfy a control in force. For a
    workflow step, a send, or a spend, the adopted controls that govern it. A suggestion, a proposal, a declined, deferred,
    or retired control is never in a notice. Read only."""
    subject = (subject or "").strip()
    if not subject:
        raise ValueError("subject names an approval kind, a workflow step, or a send")
    today = today or date.today()
    root = Path(data_dir)
    controls = store.load(root, profile, community)
    roster = roster_of(community)
    try:
        kind = registry.get(subject)
    except KeyError:
        kind = None
    if kind is not None:
        eff = effective.effective_approver(kind.key, controls=controls, roster=roster, today=today, kind=kind,
                                           amount_cents=amount_cents)
        return {"found": True, "subject": kind.key, "subjectKind": "approval kind", "title": kind.title,
                "builtin": "two persons" if kind.approver is Approver.TWO_PERSON else "one person",
                "why": eff.why, "stricter": eff.stricter_than_builtin,
                "second": {"always": eff.second_always, "aboveCents": eff.second_above_cents},
                "roles": [r.value for r in eff.roles], "mustInclude": [r.value for r in eff.must_include],
                "controls": [_notice(c) for c in eff.controls],
                "waiting": [_notice(w.control, w.reason) for w in eff.waiting],
                "refusals": list(eff.refusals), "clash": eff.clash, "asOf": today.isoformat(),
                "caveats": ["The server refuses the same act whatever the page shows."]}
    if subject not in _subjects():
        raise ValueError(f"subject is an approval kind, a workflow step, or a send; {subject!r} is none the catalog knows")
    bound, waiting, refused = [], [], []
    for c in controls:
        if c.state is not ControlState.ADOPTED or not any(
                g.what == subject and g.kind is not GovernsKind.APPROVAL_KIND for g in c.type.governs):
            continue
        r = effective.in_force(c, today, roster)
        if r.ok:
            bound.append(_notice(c))
            if r.lacks:
                refused.append(f"a control the board adopted on {c.adopted_at or c.effective} requires "
                               f"{describe(c)}; {r.lacks}")
        else:
            waiting.append(_notice(c, r.reason + (f"; the roster could not satisfy it now: {r.lacks}" if r.lacks else "")))
    return {"found": True, "subject": subject, "subjectKind": "step or send", "title": subject, "controls": bound,
            "waiting": waiting, "refusals": refused, "asOf": today.isoformat(),
            "caveats": ["The server refuses the same act whatever the page shows."]}


def step_controls(data_dir: Path, workflow_key: str, family: str, steps: Iterable[tuple[str, str]], *,
                  today: date | None = None, pending: Mapping[str, str] | None = None,
                  community: Any = None) -> dict[str, list[dict[str, Any]]]:
    """The controls that bite on a run's steps, for the run page: ``{step id: [{key, title, why, gate, state, effective}]}``,
    one row for each gate a control adds. ``steps`` are (step id, the role its definition names). ``why`` is the sentence the
    engine refuses with. ``state``: ``in force``, ``waiting`` (adopted, the date not reached: binds nothing yet), or
    ``refused`` (in force, and the roster cannot satisfy it). A second-person row carries ``firstBy`` when a first of two is
    waiting (``pending``: step id to the person). Empty, reading no store but the controls', when none is configured or none
    governs a step: a run page with no controls is as it was."""
    root = Path(data_dir)
    if not store.configured(root):
        return {}
    controls = [c for c in store.load(root, "", community) if c.state is ControlState.ADOPTED]
    wanted = [(sid, role) for sid, role in steps if any(effective.step_applies(c, workflow_key, sid, family) for c in controls)]
    if not wanted:
        return {}
    roster = roster_of(community) if community is not None else effective._community_roster()
    today = today or date.today()
    out: dict[str, list[dict[str, Any]]] = {}
    for sid, role in wanted:
        got = effective.step_gates(workflow_key, sid, role, controls=controls, roster=roster, today=today, family=family)
        rows = []
        for g in got.gates:
            state = "waiting" if g.future else ("refused" if g.lacks else "in force")
            row = {"key": g.control.key, "title": g.control.type.title, "why": g.reason + (f"; {g.lacks}" if g.lacks else ""),
                   "gate": g.gate, "state": state, "effective": g.control.effective.isoformat() if g.control.effective else ""}
            if g.gate == "roles":
                row["roles"] = [r.value for r in g.roles]
            if g.gate == "second" and not g.future and (pending or {}).get(sid):
                row["firstBy"] = pending[sid]
            rows.append(row)
        if rows:
            out[sid] = rows
    return out


__all__ = ["CAVEATS", "EMPTY", "FAMILIES", "LABEL", "READING_LABEL", "STATES", "compose", "counts_of", "describe",
           "heading", "notices", "one", "roster_check", "roster_of", "row", "standing", "step_controls"]
