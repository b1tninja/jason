"""The ``owner-info-tags`` kind: ``jason owner-info --apply --payhoa`` as an approval.

The planner calls ``owner_info_apply.plan_apply`` (one live read, the planner the CLI calls) and turns its result into
items:

- **approvable**: each tag write (``owner_info.plan_writes``), with its rule (Civil Code 4040(a)(2) for the default
  mail tag, the earlier-elections rule, or the response policy's ``delivery`` row) and its evidence; and each owner's
  pending PayHOA request that nothing but its writes keeps open, as a completion that depends on those writes (the
  board's stated exception in AGENTS.md: the request is marked complete and the board's comment emailed to the owner);
- **held for the board**: the unit occupancy writes the response policy holds (``occupancy-vs-tag``), each with its
  board item. Never approvable;
- **for a person** and **confirm with the owner**: what a request's answer asks that jason does not write, and the
  policy's person and confirm findings. Never approvable;
- **informational**: each pending request that stays open, and why.

Each item's basis is a digest of the live state it relies on: a member's tag rows, a unit's tags, a request's status,
answers, and findings. The applier writes the approved tags (``owner_info_apply.execute_each``), then completes a
request only when every write it waits on was made and ``requests_left`` leaves it nothing, as the CLI does.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jason.approvals.engine import Live, Planned
from jason.approvals.model import (Change, ChangeOp, Evidence, ItemClass, PlanItem, Result, digest, item_id)

KEY = "owner-info-tags"


@dataclass
class Context:
    """The planner's own, in memory, for the applier: the plan and which write or request each item is."""
    plan: Any                                          # owner_info_apply.ApplyPlan
    writes: dict[str, Any] = field(default_factory=dict)       # item id -> owner_info.Write
    requests: dict[str, int] = field(default_factory=dict)     # completion item id -> submission id


def _profile() -> tuple[Any, Any]:
    from jason.community import community
    from jason.tasks.owner_info_apply import owner_information

    c = community()
    forms = owner_information(c)
    if forms is None:
        raise LookupError("the profile has no owner-information form (Community.owner_information)")
    return c, forms


def plan(live: Live, scope: dict[str, Any]) -> Planned:
    """Read PayHOA once and plan, writing nothing. What it read of each request its evidence names is kept as the
    plan's snapshot (``Planned.snapshots``), stamped with when it was read."""
    from jason.community.tags import TagPurpose
    from jason.tasks import owner_info_apply

    community, forms = _profile()
    today = live.today or date.today()
    data_dir = live.data_dir
    if data_dir is None:
        from jason.config import data_dir as profile_data_dir

        data_dir = profile_data_dir(live.env)
    read_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p = owner_info_apply.plan_apply(live.client, live.org_id, community=community, forms=forms,
                                    cycle=forms.OWNER_INFO_CYCLE, data_dir=Path(data_dir), today=today, payhoa=True,
                                    env=live.env)
    # an owner's reported occupancy is P2 (docs/console/security-and-privacy.md), as contact details are
    private = frozenset(t.answer for t in community.payhoa_tags() if t.purpose is TagPurpose.OCCUPANCY and t.answer)
    return build(p, cycle=forms.OWNER_INFO_CYCLE, today=today, read_at=read_at,
                 form=getattr(forms, "OWNER_INFO", None), private=private)


# --- the plan's snapshot of what it read --------------------------------------------------------------------------------

_CONTACT_READS = ("email", "phone", "address", "contact")          # ReadAs values that hold contact details


def _text(value: Any) -> str:
    """An answer as one line: a list joined, a mapping as name: value, nothing as ""."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (list, tuple, set)):
        return "; ".join(t for t in (_text(v) for v in value) if t)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_text(v)}" for k, v in value.items() if _text(v))
    return str(value)


def request_digest(status: str, answers: dict[str, Any]) -> str:
    """What the plan read of a request, as one digest: its status and its answers."""
    return digest({"status": status or "", "answers": digest(answers or {})})


def snapshot(sid: int, p: Any, *, read_at: str = "", form: Any = None, private: frozenset[str] = frozenset()
             ) -> dict[str, Any]:
    """One request as the plan read it: its status, its unit, and its answers, each answer flagged ``p2`` when it is
    an owner's contact detail (the form's question reads as an email, a phone, an address, or a contact) or another
    P2 answer (``private``). Kept whole on disk; ``jason.approvals.evidence`` masks P2 before it leaves the server."""
    c = next((x for x in p.contexts if int(x.submission) == int(sid)), None)
    answers = dict(c.answers) if c is not None else {}
    status = str(p.statuses.get(sid) or "")
    questions = {q.field: q for q in getattr(form, "questions", ()) or ()}
    fields = []
    for name, value in answers.items():
        q = questions.get(str(name).split(".", 1)[0])
        reads = getattr(getattr(q, "reads_as", None), "value", "")
        fields.append({"name": str(name), "title": getattr(q, "title", "") or "", "value": _text(value),
                       "p2": reads in _CONTACT_READS or str(name).split(".", 1)[0] in private})
    return {"label": f"PayHOA request {sid}", "kind": "payhoa_submission", "readAt": read_at,
            "digest": request_digest(status, answers), "status": status, "unit": getattr(c, "unit", "") or "",
            "unitId": int(getattr(c, "unit_id", 0) or 0), "fields": fields}


def _stamp(items: list[PlanItem], p: Any, *, read_at: str, form: Any, private: frozenset[str]
           ) -> dict[str, dict[str, Any]]:
    """Stamp each request's evidence with when it was read and the digest of what was read, and return the plan's
    snapshot of those requests by address."""
    snaps: dict[str, dict[str, Any]] = {}
    for item in items:
        stamped = []
        for e in item.evidence:
            found = re.fullmatch(r"payhoa:submission:(\d+)", e.address or "")
            if found is None:
                stamped.append(e)
                continue
            snap = snaps.get(e.address) or snapshot(int(found.group(1)), p, read_at=read_at, form=form,
                                                     private=private)
            snaps[e.address] = snap
            stamped.append(Evidence(e.label, e.address, read_at, snap["digest"]))
        item.evidence = tuple(stamped)
    return snaps


# --- the items ----------------------------------------------------------------------------------------------------------

def _tag_text(t: Any) -> str:
    return str(t.get("tag") if isinstance(t, dict) else t)


def _member_state(p: Any, membership_id: int) -> list[list[Any]]:
    person = next((x for x in p.people if int(x.get("id") or 0) == int(membership_id)), {})
    return sorted([_tag_text(t), int(t.get("id") or 0) if isinstance(t, dict) else 0] for t in person.get("tags") or [])


def _unit_state(p: Any, unit_id: int) -> list[str]:
    unit = next((u for u in p.units if int(u.get("id") or 0) == int(unit_id)), {})
    return sorted(_tag_text(t) for t in unit.get("tags") or [])


def _target(w: Any) -> str:
    return f"{'unit' if w.kind.startswith('unit') else 'member'}:{w.target}"


def _state(p: Any, w: Any) -> Any:
    return _unit_state(p, w.target) if w.kind.startswith("unit") else _member_state(p, w.target)


def _change(p: Any, w: Any) -> Change:
    scope = "unit" if w.kind.startswith("unit") else "member"
    names = _unit_state(p, w.target) if scope == "unit" else [n for n, _ in _member_state(p, w.target)]
    adding = w.kind.endswith("+")
    after = sorted(set(names) | {w.value}) if adding else [n for n in names if n != w.value]
    return Change(ChangeOp.ADD if adding else ChangeOp.REMOVE, f"{scope} tags", w.value, ", ".join(names),
                  ", ".join(after))


def _request_evidence(text: str) -> tuple[Evidence, ...]:
    found = re.search(r"payhoa:(\d+)", text or "")
    return (Evidence(f"PayHOA request {found.group(1)}", f"payhoa:submission:{found.group(1)}"),) if found else ()


def _rule(w: Any) -> tuple[str, tuple[Evidence, ...]]:
    """The rule a write recites, and its evidence (``owner_info.plan_writes`` gives each write's reason)."""
    if "no election on file" in w.why:
        return "CIV 4040(a)(2)", (Evidence("Civil Code 4040(a)(2): no election, first-class mail", "CIV 4040(a)(2)"),)
    if "written election of" in w.why:
        return ("the earlier-elections rule (Community.owner_information: EARLIER_ELECTIONS)",
                _request_evidence(w.why) or (Evidence("An earlier written election", "jason owner-info --out FILE"),))
    return "the response policy's delivery row (owner_responses.RULES: delivery)", _request_evidence(w.why)


def _unit_of(p: Any, t: Any) -> int:
    row = next((r for r in p.rows if r.membership_id == t.membership_id and r.unit == t.unit), None)
    return int(row.unit_id) if row is not None else 0


def build(p: Any, *, cycle: Any = None, today: date | None = None, read_at: str = "", form: Any = None,
          private: frozenset[str] = frozenset()) -> Planned:
    """The items, from an ``owner_info_apply.ApplyPlan``. Pure: reads nothing. ``read_at`` is when ``p`` was read;
    each request's evidence carries it with a digest of what was read, and ``Planned.snapshots`` keeps the requests as
    read (``snapshot``)."""
    from jason.approvals.audit import mask
    from jason.tasks.owner_info_apply import requests_left

    ctx = Context(p)
    items: list[PlanItem] = []
    write_items: dict[int, PlanItem] = {}
    for w in p.writes:
        target = _target(w)
        rule, evidence = _rule(w)
        item = PlanItem(item_id(KEY, w.kind, target, w.value), w.kind, target, w.label, w.value, w.why, group=w.label,
                        change=_change(p, w), rule=rule, evidence=evidence,
                        basis=digest({"state": _state(p, w), "why": w.why}))
        items.append(item)
        write_items[id(w)] = item
        ctx.writes[item.id] = w
    for h in p.held:
        w = h.write
        target = _target(w)
        board = (Evidence(f"Board item {h.board_item}", f"board-item:{h.board_item}"),) if h.board_item else ()
        items.append(PlanItem(item_id(KEY, w.kind, target, w.value), w.kind, target, w.label, w.value,
                              mask(f"{h.text}: held for the board by the response policy ({h.rule})"), group=w.label,
                              change=_change(p, w), rule=f"owner_responses.RULES: {h.rule}",
                              evidence=board + _request_evidence(w.why),
                              basis=digest({"state": _state(p, w), "why": w.why}), klass=ItemClass.HELD_FOR_BOARD,
                              board_item=h.board_item))
    answers = {c.submission: c.answers for c in p.contexts}
    findings = {sid: {f.rule: f for f in fs} for sid, fs in p.findings.items()}
    counts = Counter()
    for t in requests_left(p, []):
        sid, group, target = t.submission_id, f"{t.unit}: {t.name}", f"submission:{t.submission_id}"
        unit_id = _unit_of(p, t)
        status = p.statuses.get(sid) or ""
        state = {"status": status, "answers": digest(answers.get(sid, {})),
                 "findings": sorted(f"{f.outcome.value}: {f.rule}" for f in p.findings.get(sid, [])),
                 "left": sorted(t.left)}
        evidence = (Evidence(f"PayHOA request {sid}", f"payhoa:submission:{sid}"),)
        deps = tuple(write_items[id(w)].id for w in p.writes
                     if (w.kind.startswith("member") and w.target == t.membership_id)
                     or (w.kind.startswith("unit") and w.target == unit_id))
        if not t.left:
            item = PlanItem(item_id(KEY, "complete request", target, "complete"), "complete request", target, group,
                            "complete", "nothing is left but its writes: once they are made, the request is marked "
                            "complete and the board's comment is emailed to the owner", group=group,
                            change=Change(ChangeOp.SET, "request status", "complete", status, "complete"),
                            rule="the board's owner-information completion rule (AGENTS.md)", evidence=evidence,
                            basis=digest(state), depends_on=deps)
            items.append(item)
            ctx.requests[item.id] = sid
            counts["completions"] += 1
            continue
        for line in t.left:
            rule = line.split(": ", 1)[1] if ": " in line else ""
            found = findings.get(sid, {}).get(rule)
            if line.startswith("confirm: "):
                klass = ItemClass.CONFIRM_WITH_OWNER
            elif line.startswith("person: ") or line.startswith("a person enters"):
                klass = ItemClass.FOR_A_PERSON
            else:
                continue                               # a board question: in the request's informational item
            why = found.text if found else "an answer asks what jason does not write: a person enters it in PayHOA"
            items.append(PlanItem(item_id(KEY, klass.value, target, line), klass.value.replace("_", " "), target,
                                  group, line, mask(why), group=group,
                                  rule=f"owner_responses.RULES: {rule}" if found else "owner_info.FOR_A_PERSON",
                                  evidence=evidence, basis=digest(state), klass=klass))
            counts[klass.value] += 1
        items.append(PlanItem(item_id(KEY, "request stays open", target, "open"), "request stays open", target, group,
                              "; ".join(t.left), "only a request with nothing left is completed (the board's rule); "
                              "what is left: " + mask("; ".join(t.left)), group=group,
                              rule="the board's owner-information completion rule (AGENTS.md)", evidence=evidence,
                              basis=digest(state), klass=ItemClass.INFORMATIONAL, depends_on=deps))
        counts["requestsStayOpen"] += 1
    clock = None
    if cycle is not None:
        ahead = [(name, day, left) for name, day, left in cycle.deadlines(today or date.today()) if left >= 0]
        if ahead:
            name, day, left = min(ahead, key=lambda x: x[1])
            clock = {"what": name, "due": day.isoformat(), "daysLeft": left}
    summary = {"writes": len(p.writes), "held": len(p.held), "byOp": dict(Counter(w.kind for w in p.writes)),
               "completions": counts["completions"], "requestsStayOpen": counts["requestsStayOpen"],
               "forAPerson": counts[ItemClass.FOR_A_PERSON.value],
               "confirmWithOwner": counts[ItemClass.CONFIRM_WITH_OWNER.value], "testAccountsLeftOut": p.left_out,
               "completionComment": p.comment, "cost": "No charge: PayHOA tag changes and request status"}
    snaps = _stamp(items, p, read_at=read_at, form=form, private=private)
    return Planned(items, scope={"payhoa": True, "cycle": getattr(cycle, "year", None)},
                   title="Owner information: PayHOA tags and request completions", summary=summary,
                   evidence=(Evidence("The same plan as a dry run", "jason owner-info --apply --payhoa"),
                             Evidence("Civil Code 4040, 4041", "CIV 4041"),
                             Evidence("The response policy's findings", "jason owner-info --responses")),
                   clock=clock, context=ctx, read_at=read_at, snapshots=snaps)


# --- apply --------------------------------------------------------------------------------------------------------------

def _uncertain(exc: BaseException) -> bool:
    """A request that went out with no answer back (a timeout, a dropped connection): PayHOA may have taken it."""
    try:
        from payhoa.exceptions import PayhoaError
    except ImportError:  # pragma: no cover - payhoa is installed beside jason
        PayhoaError = ()  # type: ignore[assignment]
    if PayhoaError and isinstance(exc, PayhoaError):
        return False
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


def apply(live: Live, planned: Planned, items: list[PlanItem], recorder: Any) -> None:
    """Write the approved tags, then complete each approved request whose writes were all made and that
    ``requests_left`` leaves nothing; any other request stays open."""
    from jason.tasks.owner_info import complete
    from jason.tasks.owner_info_apply import execute_each, requests_left

    ctx: Context = planned.context
    p = ctx.plan
    chosen = [(i, ctx.writes[i.id]) for i in items if i.id in ctx.writes]
    by_write = {id(w): i for i, w in chosen}
    results = execute_each(live.client, live.org_id, [w for _, w in chosen], member_tag_rows=p.member_tag_rows,
                           before=lambda group: recorder.applying([by_write[id(w)].id for w in group]))
    applied: set[str] = set()
    for r in results:
        i = by_write[id(r.write)]
        if r.satisfied:
            recorder.done(i.id, Result.APPLIED, r.detail or "written")
            applied.add(i.id)
        elif r.error is not None:
            recorder.done(i.id, Result.UNCERTAIN if _uncertain(r.error) else Result.FAILED, r.detail)
        else:
            recorder.done(i.id, Result.NOT_APPLIED, r.detail)
    made = {id(r.write) for r in results if r.satisfied}
    pending = [w for w in p.writes if id(w) not in made]      # not approved, failed, or not attempted
    left = {t.submission_id: t for t in requests_left(p, pending)}
    for i in items:
        sid = ctx.requests.get(i.id)
        if sid is None:
            continue
        waits = [d for d in i.depends_on if d not in applied]
        if waits:
            recorder.done(i.id, Result.BLOCKED, f"stays open: waits on writes not made ({', '.join(waits)})")
            continue
        t = left.get(sid)
        if t is None:
            recorder.done(i.id, Result.NOT_APPLIED, "the request is no longer pending in PayHOA")
            continue
        if t.left:
            recorder.done(i.id, Result.BLOCKED, "stays open: " + "; ".join(t.left))
            continue
        recorder.applying([i.id])
        try:
            complete(live.client, live.org_id, t, p.comment)
        except Exception as exc:  # noqa: BLE001 - recorded on the item
            recorder.done(i.id, Result.UNCERTAIN if _uncertain(exc) else Result.FAILED,
                          f"{type(exc).__name__}: {exc}")
            continue
        recorder.done(i.id, Result.APPLIED, "marked complete; the owner is thanked")


__all__ = ["Context", "KEY", "apply", "build", "plan", "request_digest", "snapshot"]
