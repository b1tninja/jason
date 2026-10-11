"""The registry of workflow definitions, and the check each one passes before it registers.

A definition is a row, like a rule row. The general ones are registered here (none yet); a community's own are added by
``extra`` (a provider other code calls later, such as a ``Community.workflows()`` method with an empty default): a row with
the same key overrides the earlier one. Importing this module loads no profile and registers nothing by itself.

``validate`` refuses (docs/workflows-engine.md, section 2): a step id repeated; a ``needs`` that names no step; a cycle; a
legal step (a law clock, or ``legal=True``) with a skip rule; a ``plan`` step whose approvals kind is not registered; a
``job`` step whose job is not; a ``spawns`` that names no definition; a ``law`` clock that cites nothing or whose section
does not resolve. Each registry (the approvals kinds, the jobs, the definitions, the statutes) is an argument, so a test
supplies its own; with none given, the approvals kinds are read from ``jason.approvals.registry`` when first needed, and
a registry that is not given and cannot be read is skipped, never guessed. A definition that fails does not register,
and the failure names the row.
"""

from __future__ import annotations

from typing import Callable, Collection, Iterable

from jason.workflows.types import (
    ClockBasis, InvalidWorkflow, Problem, Role, StepKind, Workflow, parse_sop,
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
        if s.kind is StepKind.DECISION and s.role in (Role.ANYONE, Role.JASON, Role.SCHEDULER):
            bad(s.id, "role", "a decision is recorded by an office (the secretary), not by anyone or by jason")
        if s.kind is StepKind.PERSON and s.role in (Role.JASON, Role.SCHEDULER):
            bad(s.id, "role", "a person's step is not jason's")
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
    for d in workflow.dates:
        if d.after and d.after not in slots:
            bad(d.name, "date", f"date {d.name} comes after {d.after}, which is not a slot")

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
