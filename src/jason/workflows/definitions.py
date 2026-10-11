"""The registry of workflow definitions, and the check each one passes before it registers.

A definition is a row, like a rule row. The general ones are registered here (none yet); a community's own are added by
``extra`` (a provider other code calls later, such as a ``Community.workflows()`` method with an empty default): a row with
the same key overrides the earlier one. Importing this module loads no profile and registers nothing by itself.

``validate`` refuses (docs/workflows-engine.md, section 2): a step id repeated; a ``needs`` that names no step; a cycle; a
legal step (a law clock, or ``legal=True``) with a skip rule; a ``plan`` step whose approvals kind is not registered; a
``job`` step whose job is not; a ``spawns`` that names no definition; a ``law`` clock that cites nothing or whose section
does not resolve; a step whose ``roles`` are not distinct ``Role`` values (the primary ``role`` is not repeated among them);
a ``na`` (not-applicable outcome) on a branch or with bad roles (a legal step may carry one though it has no skip rule); a
``waits_on_child`` with no ``spawns``; a date slot that repeats, or has a bad timing or roles; a held definition with no ``held_title`` (or one with a digit or ``@``
in it, or on a definition that is not held); a ``public_title`` step on a definition that is not held. Round three adds: a
``remedy_of`` that is not a check among the step's ``needs``; a step with an item set or per-item ``needs`` that does not repeat,
``item_needs`` that are not ``needs`` or do not repeat over the same set, a per-item branch whose path steps do not; a per-item
clock on a step that does not repeat (or on the whole run); an ``ends_by_note`` that is not a wait, names a check, or lets a date
end it; and step groups declared twice or a step whose group is not among the declared ones. Each registry (the approvals kinds, the jobs, the definitions, the statutes) is an argument, so a test
supplies its own; with none given, the approvals kinds are read from ``jason.approvals.registry`` when first needed, and
a registry that is not given and cannot be read is skipped, never guessed. A definition that fails does not register,
and the failure names the row.
"""

from __future__ import annotations

import re
from typing import Callable, Collection, Iterable

from jason.workflows.types import (
    ClockBasis, DateTiming, Elapsed, InvalidWorkflow, Problem, Repeat, Role, StepKind, Visibility, Workflow, parse_sop,
)

LawResolver = Callable[[str], "bool | None"]
ProcedureFinder = Callable[[str], object]


def default_plan_kinds() -> frozenset[str] | None:
    """The approvals kinds' keys and aliases, or ``None`` when the registry cannot be read."""
    try:
        from jason.approvals import registry

        keys = set()
        for kind in registry.kinds():
            keys.add(kind.key)
            keys.update(kind.aliases)
        return frozenset(keys)
    except Exception:  # noqa: BLE001 - an unreadable registry is a skip, not a guess
        return None


def validate(workflow: Workflow, *, plan_kinds: Collection[str] | None = None, jobs: Collection[str] | None = None,
             workflows: Collection[str] | None = None, resolve_law: LawResolver | None = None) -> list[Problem]:
    """The problems with a definition; none means it may register. ``plan_kinds`` defaults to the approvals registry,
    ``jobs`` and ``workflows`` are skipped when not given, and ``resolve_law`` (a function from a cite to true, false, or
    ``None`` for "cannot tell") is skipped when not given."""
    out: list[Problem] = []
    key = workflow.key

    def bad(row: str, code: str, message: str) -> None:
        out.append(Problem(row or key, code, message))

    if not key:
        bad("(definition)", "key", "a definition has a key")
    _visibility(workflow, bad)
    seen: set[str] = set()
    for s in workflow.steps:
        if s.id in seen:
            bad(s.id, "duplicate", f"step id {s.id} repeats")
        seen.add(s.id)
    ids = {s.id for s in workflow.steps}
    kinds = plan_kinds if plan_kinds is not None else default_plan_kinds()
    slots = {d.name for d in workflow.dates}

    for s in workflow.steps:
        for need in s.needs:
            if need not in ids:
                bad(s.id, "needs", f"needs {need}, which is not a step of {key}")
            elif need == s.id:
                bad(s.id, "cycle", "needs itself")
        if s.kind is StepKind.PLAN:
            if not s.plan_kind:
                bad(s.id, "plan", "a plan step names its approvals kind")
            elif kinds is not None and s.plan_kind not in kinds:
                bad(s.id, "plan", f"plan kind {s.plan_kind} is not a registered approvals kind")
        if s.kind is StepKind.JOB:
            if not s.job:
                bad(s.id, "job", "a job step names its job")
            elif jobs is not None and s.job not in jobs:
                bad(s.id, "job", f"job {s.job} is not a registered job")
        if s.spawns and workflows is not None and s.spawns not in workflows and s.spawns != key:
            bad(s.id, "spawns", f"spawns {s.spawns}, which is not a definition")
        if s.is_legal and s.skip is not None:
            bad(s.id, "legal-skip", "a legal step has no skip rule")
        _roles(s.id, "roles", s.roles, bad, primary=s.role)
        every = [r for r in (s.role, *s.roles) if isinstance(r, Role)]
        if s.kind is StepKind.DECISION and any(r in (Role.ANYONE, Role.JASON, Role.SCHEDULER) for r in every):
            bad(s.id, "role", "a decision is recorded by an office (the secretary), not by anyone or by jason")
        if s.kind is StepKind.PERSON and any(r in (Role.JASON, Role.SCHEDULER) for r in every):
            bad(s.id, "role", "a person's step is not jason's")
        if s.na is not None:
            _roles(s.id, "na", s.na.roles, bad)
            if s.kind is StepKind.BRANCH:
                bad(s.id, "na", "a branch step has no not-applicable outcome: its path is chosen")
        if s.waits_on_child and not s.spawns:
            bad(s.id, "waits", "waits_on_child needs a step that spawns a child run")
        if s.clock is not None:
            _clock(s.id, s.clock, slots, resolve_law, bad)
        if s.sop and parse_sop(s.sop) is None:
            bad(s.id, "sop", f"sop {s.sop!r} is not procedure-key#index")
        for choice in s.choices:
            for sid in choice.steps:
                if sid not in ids:
                    bad(s.id, "choice", f"path {choice.key} names {sid}, which is not a step")
        if s.kind is StepKind.BRANCH and not s.choices:
            bad(s.id, "choice", "a branch step defines its paths")
    for i, c in enumerate(workflow.clocks):
        _clock(f"{key} clock {i}", c, slots, resolve_law, bad)
    for ph in workflow.phases:
        for sid in ph.steps:
            if sid not in ids:
                bad(ph.key, "phase", f"phase {ph.key} names {sid}, which is not a step")
    _round_three(workflow, bad)
    names: set[str] = set()
    for d in workflow.dates:
        if d.name in names:
            bad(d.name, "date", f"date slot {d.name} repeats")
        names.add(d.name)
        if d.after and d.after not in slots:
            bad(d.name, "date", f"date {d.name} comes after {d.after}, which is not a slot")
        if not isinstance(d.timing, DateTiming):
            bad(d.name, "date", f"date {d.name} has a timing that is not a DateTiming")
        _roles(d.name, "date", d.roles, bad)

    # a cycle: depth-first over needs
    state: dict[str, int] = {}
    needs = {s.id: [n for n in s.needs if n in ids and n != s.id] for s in workflow.steps}

    def visit(node: str, path: list[str]) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            bad(node, "cycle", "a cycle in needs: " + " -> ".join(path[path.index(node):] + [node]))
            return
        state[node] = 1
        for nxt in needs.get(node, ()):
            visit(nxt, path + [node])
        state[node] = 2

    for sid in needs:
        visit(sid, [])
    return out


_SET_NAME = re.compile(r"^[a-z][a-z0-9-]{0,39}$")


def _round_three(workflow: Workflow, bad) -> None:
    """The rules for remedies, item sets, per-item needs, branches and clocks, notes that end a wait, and step groups."""
    key = workflow.key
    by_id = {s.id: s for s in workflow.steps}

    def repeats(step) -> bool:
        return step.repeat is not Repeat.ONCE

    for s in workflow.steps:
        if s.remedy_of:
            target = by_id.get(s.remedy_of)
            if target is None:
                bad(s.id, "remedy", f"remedy_of {s.remedy_of}, which is not a step of {key}")
            elif s.remedy_of not in s.needs:
                bad(s.id, "remedy", f"remedy_of {s.remedy_of}: a remedy needs the check it remedies")
            elif target.kind is not StepKind.CHECK:
                bad(s.id, "remedy", f"remedy_of {s.remedy_of}: only a check is remedied, and it is a {target.kind.value} step")
        if s.item_set and not _SET_NAME.match(s.item_set):
            bad(s.id, "items", f"item set {s.item_set!r} is a lower-case word (letters, digits, hyphens)")
        if s.item_aware and not repeats(s):
            bad(s.id, "items", "a step with an item set or per-item needs repeats per item (repeat is not once)")
        for need in s.item_needs:
            target = by_id.get(need)
            if need not in s.needs:
                bad(s.id, "items", f"item_needs {need}, which the step does not need")
            elif target is not None and (not repeats(target) or target.item_set != s.item_set):
                bad(s.id, "items", f"reads {need} item by item, but {need} does not repeat over the same items")
        if s.kind is StepKind.BRANCH and s.item_aware:
            for choice in s.choices:
                for sid in choice.steps:
                    target = by_id.get(sid)
                    if target is not None and (not repeats(target) or target.item_set != s.item_set):
                        bad(s.id, "items", f"per-item path {choice.key} names {sid}, which does not repeat over the same items")
        if s.clock is not None and s.clock.per_item and not repeats(s):
            bad(s.id, "clock", "a per-item clock is for a step that repeats per item")
        if s.ends_by_note:
            if s.kind is not StepKind.WAIT:
                bad(s.id, "wait", "ends_by_note is for a wait step")
            if s.check is not None:
                bad(s.id, "wait", "a wait that ends by a person's note names no check to read it by")
            if s.elapsed is not Elapsed.OVERDUE:
                bad(s.id, "wait", "a wait that ends by a person's note is not ended by a date (elapsed stays overdue)")
    for i, c in enumerate(workflow.clocks):
        if c.per_item:
            bad(f"{key} clock {i}", "clock", "a clock on the whole run is not per item")
    declared: set[str] = set()
    for g in workflow.groups:
        if not g.key:
            bad(key, "group", "a step group has a key")
        elif g.key in declared:
            bad(g.key, "group", f"step group {g.key} repeats")
        declared.add(g.key)
    if workflow.groups:
        for s in workflow.steps:
            if s.group and s.group not in declared:
                bad(s.id, "group", f"group {s.group} is not among the definition's step groups")


HELD_TITLE_CHARS = 80
_HELD_TITLE_FORBIDDEN = re.compile(r"[\d@\n\r]")


def _visibility(workflow: Workflow, bad) -> None:
    """Who sees the definition and its runs. A ``held`` definition names the general words it shows outside the private view
    (``held_title``: one short line with no digit or ``@``, so no address, parcel, or case number can ride in it); only a
    held definition has one, and only a held definition may mark a step's title public."""
    key = workflow.key
    if not isinstance(workflow.visibility, Visibility):
        bad(key, "visibility", f"{workflow.visibility!r} is not a Visibility")
        return
    held = workflow.visibility is Visibility.HELD
    title = (workflow.held_title or "").strip()
    if held and not title:
        bad(key, "held", "a held definition gives the general words it shows outside the private view (held_title)")
    if title and not held:
        bad(key, "held", "held_title belongs to a held definition only")
    if title and (len(title) > HELD_TITLE_CHARS or _HELD_TITLE_FORBIDDEN.search(title)):
        bad(key, "held", f"held_title is one line of at most {HELD_TITLE_CHARS} characters with no digit or @: {title!r}")
    for s in workflow.steps:
        if s.public_title and not held:
            bad(s.id, "held", "public_title is for the steps of a held definition")


def _roles(row, code, roles, bad, primary=None) -> None:
    """``roles`` must be ``Role`` values, each once (and not the step's primary, which is already one of its roles)."""
    seen = []
    for r in roles:
        if not isinstance(r, Role):
            bad(row, code, f"{r!r} is not a Role")
        elif r in seen:
            bad(row, code, f"role {r.value} repeats")
        elif primary is not None and r is primary:
            bad(row, code, f"role {r.value} is the step's primary role; roles lists the others")
        seen.append(r)


def _clock(row, clock, slots, resolve_law, bad) -> None:
    if clock.slot and clock.slot not in slots:
        bad(row, "clock", f"clock reads date {clock.slot}, which is not a date slot")
    if clock.basis is ClockBasis.LAW:
        if not clock.cite:
            bad(row, "law", "a law clock cites its section")
        elif resolve_law is not None and resolve_law(clock.cite) is False:
            bad(row, "law", f"the section {clock.cite} does not resolve on the authorities shelf")


def drift(workflows: Iterable[Workflow], find: ProcedureFinder | None = None) -> list[Problem]:
    """A workflow and its procedure must not drift: a step's ``sop`` (``key#index``, counted from 1 as ``jason sop``
    numbers them) must address a step that still exists, and a workflow's ``procedure`` key must exist."""
    if find is None:
        from jason.community.procedures import find as find_procedure

        find = find_procedure
    out: list[Problem] = []
    for w in workflows:
        if w.procedure and find(w.procedure) is None:
            out.append(Problem(w.key, "drift", f"procedure {w.procedure} no longer exists"))
        for s in w.steps:
            if not s.sop:
                continue
            parsed = parse_sop(s.sop)
            if parsed is None:
                out.append(Problem(s.id, "drift", f"sop {s.sop!r} is not procedure-key#index"))
                continue
            key, index = parsed
            proc = find(key)
            steps = getattr(proc, "steps", None)
            if proc is None or steps is None:
                out.append(Problem(s.id, "drift", f"procedure {key} no longer exists"))
            elif not 1 <= index <= len(steps):
                out.append(Problem(s.id, "drift", f"procedure {key} has {len(steps)} steps; step {index} no longer exists"))
    return out


# --- the registry ---------------------------------------------------------------------------------------------------

_registered: dict[str, Workflow] = {}
_providers: list[tuple[Callable[[], Iterable[Workflow]], dict]] = []


def register(workflow: Workflow, *, check: bool = True, plan_kinds: Collection[str] | None = None,
             jobs: Collection[str] | None = None, workflows: Collection[str] | None = None,
             resolve_law: LawResolver | None = None) -> Workflow:
    """Add a definition. A definition with problems raises ``InvalidWorkflow`` naming each row, and is not added. A key
    already taken is replaced (a community overrides a general row)."""
    if check:
        problems = validate(workflow, plan_kinds=plan_kinds, jobs=jobs, workflows=workflows, resolve_law=resolve_law)
        if problems:
            raise InvalidWorkflow(problems)
    _registered[workflow.key] = workflow
    return workflow


def unregister(key: str) -> None:
    _registered.pop(key, None)


def extra(provider: Callable[[], Iterable[Workflow]], **checks) -> None:
    """Add a source of definitions, read when the registry is asked (never at import): a community's
    ``Community.workflows()`` once that method exists. Its rows are checked as they are read; a row that fails is left out
    and listed by ``rejected``. ``checks`` are the registries ``validate`` takes (``plan_kinds``, ``jobs``,
    ``resolve_law``), for a source whose rows are checked against its own."""
    if all(p is not provider for p, _ in _providers):
        _providers.append((provider, checks))


def reset() -> None:
    """Forget everything registered and every provider (for a test)."""
    _registered.clear()
    _providers.clear()


def _evaluate() -> tuple[dict[str, Workflow], list[Problem]]:
    """The registered rows with each provider's valid rows, and the problems of the rows left out. Nothing is kept
    between calls: what a provider offers can depend on the community asked, so no answer is held at module level."""
    merged = dict(_registered)
    rejected: list[Problem] = []
    for provider, checks in list(_providers):
        for w in provider() or ():
            problems = validate(w, **checks)
            if problems:
                rejected.extend(problems)
                continue
            merged[w.key] = w
    return merged, rejected


def all_definitions() -> tuple[Workflow, ...]:
    return tuple(_evaluate()[0].values())


def rejected() -> tuple[Problem, ...]:
    """The problems of the provider rows ``all_definitions`` leaves out, read fresh."""
    return tuple(_evaluate()[1])


def find(key: str) -> Workflow | None:
    return next((w for w in all_definitions() if w.key == key), None)


def get(key: str) -> Workflow:
    w = find(key)
    if w is None:
        raise KeyError(f"no workflow definition {key}: " + ", ".join(x.key for x in all_definitions()))
    return w


__all__ = ["all_definitions", "default_plan_kinds", "drift", "extra", "find", "get", "register", "rejected", "reset",
           "unregister", "validate"]
