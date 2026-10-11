"""The effective approver: the stricter of a kind's built-in rule and the controls the board adopted.

A control only adds (docs/controls.md, section 1). ``validate`` refuses one that would go below its type's floor, the
floor its own provision sets, or the built-in rule of the kind it names. ``effective_approver`` then combines every
control in force that governs a kind with the kind's own ``Approver`` by taking the stricter in each respect, so even a
control that slipped past ``validate`` cannot weaken a kind.

A control is *in force* (``in_force``) when it is adopted and its effective date has come. From that day it BINDS,
whether or not the roster can satisfy it: a safeguard never falls back to the kind's own rule. When the roster cannot
satisfy a binding control on a plan it applies to, the act is refused with the reason (``Effective.refusals``: "a control
the board adopted on DATE requires two signers; the roster lacks a second director"). One adopted but whose date has not
come is listed in ``Effective.waiting`` and binds nothing; the roster lack, if any, is a warning in its reason.
A roster of ``None`` is a roster that was not read: that check is skipped.

The engine asks ``requires_second``, ``refusals``, and ``signer_refusals`` (who may sign: the offices a control names,
checked against the roster when a person signs and again before apply). They read the controls only when a source is configured
(``store.configured``): no controls, no change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Iterable, Mapping

from jason.approvals import registry
from jason.approvals.registry import Approver
from jason.community.base import OfficerRole
from jason.controls.types import (Control, ControlRefused, ControlState, GovernsKind, ParamKind, ScopeKind, meets,
                                  normalize, stricter)

# The offices that are the board's: who counts as a signer when a control names no offices. The manager is not one.
BOARD_ROLES: tuple[OfficerRole, ...] = tuple(r for r in OfficerRole if r is not OfficerRole.MANAGER)


def _has(control: Control, key: str) -> bool:
    return any(p.key == key for p in control.type.parameters)


def _cents(cents: int) -> str:
    return f"${cents / 100:,.2f}"


# --- validate ------------------------------------------------------------------------------------------------------------

def validate(control: Control, *, kinds: Iterable[Any] | None = None) -> list[str]:
    """Why this control cannot be taken, empty when it can: an unknown parameter, a value out of range, one below the
    catalog's floor or below the floor its provision sets, an office that cannot sign, a scope that names no kind, or
    a rule weaker than the built-in rule of the one kind it names."""
    out: list[str] = []
    ctype = control.type
    for key in control.basis.floor:
        if not _has(control, key):
            out.append(f"the provision's floor names {key}, which {ctype.key} does not have")
    values: dict[str, Any] = {}
    for key, raw in control.parameters.items():
        try:
            spec = ctype.spec(key)
            values[key] = normalize(spec, raw)
        except ControlRefused as exc:
            out.append(str(exc))
    if out:
        return out
    for key, value in values.items():
        spec = ctype.spec(key)
        for floor, source in ((ctype.floor.get(key), "the catalog's floor"),
                              (control.basis.floor.get(key), f"the floor in {control.basis.citation or 'its provision'}")):
            if floor is None:
                continue
            floor = normalize(spec, floor)
            if not meets(spec, value, floor):
                out.append(f"{key} is {_plain(value)}, below {source} ({_plain(floor)}): a control only adds")
    roles, must = control.value("roles") or (), control.value("must_include") or ()
    if roles and must and not set(must) <= set(roles):
        out.append("an office that must sign is not among the offices that may")
    if _has(control, "signers"):
        n = control.value("signers") or 1
        if len(must) > n:
            out.append(f"{len(must)} offices must sign but the control asks for {n} signer(s)")
    if ctype.governs_approvals and control.scope.kind is ScopeKind.KIND:
        known = {k.key: k for k in (kinds if kinds is not None else registry.kinds())}
        for k in list(known.values()):
            known.update({a: k for a in getattr(k, "aliases", ())})
        kind = known.get(control.scope.value)
        if kind is None and ctype.categories(GovernsKind.WORKFLOW_STEP):
            pass                      # a type that also governs workflow steps: the scope may name a step pattern
        elif kind is None:
            out.append(f"no action kind {control.scope.value}: a control names a kind the engine has")
        elif kind.approver is Approver.TWO_PERSON and _weaker_than_two(control):
            out.append(f"{kind.key} is a two-person kind: a control cannot ask for less than two, "
                       "or only above an amount")
    if ctype.governs_apply:                     # a preference for applying: its scope and its floors (apply_prefs)
        from jason.controls import apply_prefs

        out += apply_prefs.problems(control, kinds)
    return out


def _weaker_than_two(control: Control) -> bool:
    if _has(control, "signers"):
        return (control.value("signers") or 1) < 2 or control.value("over_cents") is not None
    if _has(control, "required"):
        return not control.value("required")
    return False


def _plain(value: Any) -> str:
    if isinstance(value, tuple):
        return ", ".join(getattr(v, "value", str(v)) for v in value) or "any"
    return str(value)


def ensure_valid(control: Control, *, kinds: Iterable[Any] | None = None) -> Control:
    problems = validate(control, kinds=kinds)
    if problems:
        raise ControlRefused(f"{control.key}: " + "; ".join(problems))
    return control


# --- in force ------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class InForce:
    """``ok``: the control binds (adopted, its date reached). ``lacks``: what the roster lacks to satisfy it, "" when it
    can; it never changes ``ok``: before the date it is a warning, from the date it refuses the act."""

    ok: bool
    reason: str = ""
    lacks: str = ""

    def __bool__(self) -> bool:
        return self.ok


def _holders(roster: Iterable[Any]) -> dict[OfficerRole, set[str]]:
    out: dict[OfficerRole, set[str]] = {}
    for o in roster:
        out.setdefault(o.role, set()).add(str(o.name).strip().casefold())
    return out


def _noun(roles: tuple[OfficerRole, ...]) -> str:
    if not roles:
        return "board member"
    return roles[0].value if len(roles) == 1 else "signer among " + ", ".join(r.value for r in roles)


def roster_problem(control: Control, roster: Iterable[Any] | None) -> str:
    """What the roster lacks to satisfy the control, "" when it can. One person who holds two offices counts once."""
    if roster is None:
        return ""
    held = _holders(roster)
    if _has(control, "signers"):
        need = control.value("signers") or 1
        roles = control.value("roles") or ()
        eligible = set().union(*(held.get(r, set()) for r in (roles or BOARD_ROLES)))
        if len(eligible) < need:
            noun = _noun(roles)
            return (f"the roster has no {noun}" if not eligible
                    else f"the roster lacks a {'second' if len(eligible) == 1 else 'further'} {noun}")
    for p in control.type.parameters:
        if p.kind is ParamKind.REQUIRED:
            for role in control.value(p.key) or ():
                if not held.get(role):
                    return f"the roster has no {role.value}"
    return ""


def in_force(control: Control, today: date, roster: Iterable[Any] | None = None) -> InForce:
    """Whether the control binds today: adopted and its effective date reached. The roster does not decide that; what it
    lacks is reported in ``lacks``."""
    if control.state is not ControlState.ADOPTED:
        return InForce(False, f"{control.state.value}, not adopted")
    if control.effective is None:
        return InForce(False, "adopted, no effective date set")
    lack = roster_problem(control, roster)
    if control.effective > today:
        return InForce(False, f"adopted, not in force until {control.effective.isoformat()}", lack)
    return InForce(True, "", lack)


# --- the effective approver ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Waiting:
    control: Control
    reason: str


@dataclass(frozen=True)
class Effective:
    """What a kind requires of its approvers once the controls in force are counted.

    ``second_always``/``second_above_cents``: a second, distinct person signs on every plan, or on a plan costing more
    than the amount (an amount not known counts as above it). ``roles``: the offices that may sign (empty: any).
    ``must_include``: offices that must be among the signers. ``controls``: the ones that bind; ``waiting``: adopted but
    the date not reached, with why (and a warning when the roster could not satisfy it). ``refusals``: why the act
    cannot proceed, one for each binding control the roster cannot satisfy on this plan. ``why`` is the sentence the plan
    shows."""

    kind: str
    builtin: Approver
    second_always: bool = False
    second_above_cents: int | None = None
    roles: tuple[OfficerRole, ...] = ()
    must_include: tuple[OfficerRole, ...] = ()
    controls: tuple[Control, ...] = ()
    waiting: tuple[Waiting, ...] = ()
    why: str = ""
    clash: str = ""                     # two controls name offices with no one in common: nobody may sign
    refusals: tuple[str, ...] = ()

    @property
    def signers(self) -> int:
        return 2 if self.second_always else 1

    def second_needed(self, amount_cents: int | None = None) -> bool:
        if self.second_always:
            return True
        if self.second_above_cents is None:
            return False
        return amount_cents is None or amount_cents > self.second_above_cents

    @property
    def stricter_than_builtin(self) -> bool:
        return bool(self.controls)


def applies(control: Control, kind: Any, scope: Mapping[str, Any] | None,
            categories: Iterable[str] = ()) -> bool:
    """Whether the control governs this approval kind. A scope that names the kind, its family (the system it works in),
    or the plan's account is the board's own choice and always applies; a scope of all applies to the kinds in the
    categories its type governs (a payment type: kinds that carry "payment")."""
    ctype = control.type
    if not ctype.governs_approvals:
        return False
    s = control.scope
    if s.kind is ScopeKind.KIND:
        return s.value == kind.key or s.value in getattr(kind, "aliases", ())
    if s.kind is ScopeKind.FAMILY:
        return s.value == kind.system
    if s.kind is ScopeKind.ACCOUNT:
        return str((scope or {}).get("account") or "") == s.value
    wanted = ctype.categories(GovernsKind.APPROVAL_KIND)
    return "*" in wanted or bool(wanted & set(categories))


def effective_approver(kind_key: str, scope: Mapping[str, Any] | None = None, *, controls: Iterable[Control] = (),
                       roster: Iterable[Any] | None = None, today: date | None = None, kind: Any = None,
                       categories: Iterable[str] | None = None, amount_cents: int | None = None) -> Effective:
    """The kind's built-in rule combined with every adopted control in force that governs it: the stricter in each
    respect, never the weaker. ``scope`` is the plan's. ``categories`` are the kind's (default: ``kind.categories`` when
    the kind carries any). ``amount_cents`` is the plan's, so a threshold control the roster cannot satisfy refuses only
    a plan it applies to (an amount not known counts as above any threshold)."""
    kind = kind or registry.get(kind_key)
    today = today or date.today()
    cats = frozenset(categories if categories is not None else (getattr(kind, "categories", ()) or ()))
    always = kind.approver is Approver.TWO_PERSON
    above: int | None = None
    roles: tuple[OfficerRole, ...] = ()
    must: tuple[OfficerRole, ...] = ()
    bound: list[Control] = []
    waiting: list[Waiting] = []
    refused: list[str] = []
    clash = ""
    parts: list[str] = ["two persons: the kind's own rule" if always else "one person: the kind's own rule"]
    for c in sorted(controls, key=lambda c: (-c.scope.specificity, c.key)):
        if c.state is not ControlState.ADOPTED or not applies(c, kind, scope, cats):
            continue
        r = in_force(c, today, roster)
        if not r:
            warn = f"; the roster could not satisfy it now: {r.lacks}" if r.lacks else ""
            waiting.append(Waiting(c, r.reason + warn))
            continue
        second, threshold, c_roles, c_must = _asks(c)
        if second:
            if threshold is None:
                always = True
            else:
                above = threshold if above is None else min(above, threshold)
        if c_roles:
            narrowed = stricter(c.type.spec("roles"), roles, c_roles)
            if narrowed:
                roles = narrowed
            else:
                clash = f"{c.key} and an earlier control name offices with no one in common"
        must = tuple(sorted(set(must) | set(c_must), key=lambda x: x.value))
        bound.append(c)
        on = c.adopted_at
        if r.lacks and (second or c_must) and (threshold is None or amount_cents is None or amount_cents > threshold):
            refused.append(f"a control the board adopted on {on or c.effective} requires "
                           f"{_summary(c, second, threshold, c_must)}; {r.lacks}")
        parts.append(f"{_summary(c, second, threshold, c_must)}: the board adopted this"
                     + (f" on {on}" if on else "") + f" ({c.type.title})")
    return Effective(kind.key, kind.approver, always, None if always else above, roles, must, tuple(bound),
                     tuple(waiting), "; ".join(parts + ([clash] if clash else [])), clash, tuple(refused))


def _asks(c: Control) -> tuple[bool, int | None, tuple[OfficerRole, ...], tuple[OfficerRole, ...]]:
    """What one control asks of an approval: (a second person, above this amount (None: always), who may sign, who must)."""
    if _has(c, "signers"):
        return ((c.value("signers") or 1) >= 2, c.value("over_cents"), tuple(c.value("roles") or ()),
                tuple(c.value("must_include") or ()))
    if _has(c, "required"):
        return bool(c.value("required")), None, (), ()
    if _has(c, "asked"):
        return True, c.value("over_cents"), (), tuple(c.value("asked") or ())
    return False, None, (), ()


def _summary(c: Control, second: bool, threshold: int | None, must: tuple[OfficerRole, ...]) -> str:
    bits = []
    if second:
        bits.append("two signers" if threshold is None else f"a second signer above {_cents(threshold)}")
    if must:
        bits.append(" and ".join(r.value for r in must) + " must sign")
    return ", ".join(bits) or c.type.title.lower()


def touches(control: Control, kinds: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    """Where the control would bite once in force: each approval kind it applies to (with the kind's own rule beside what
    the control asks, and whether that is stricter), and each workflow step, send, or spend its type governs. Works for any
    state, a suggestion included ("what turning it on changes"): it reads the registry and the control, and nothing else.
    A governed category no registered kind carries is listed as such, never dropped."""
    out: list[dict[str, Any]] = []
    second, threshold, c_roles, c_must = _asks(control)
    ask = _summary(control, second, threshold, c_must)
    for g in control.type.governs:
        if g.kind is not GovernsKind.APPROVAL_KIND:
            out.append({"kind": g.kind.value, "what": g.what})
            continue
        found = False
        for kind in (kinds if kinds is not None else registry.kinds()):
            if not applies(control, kind, None, getattr(kind, "categories", ()) or ()):
                continue
            found = True
            two = kind.approver is Approver.TWO_PERSON
            row = {"kind": g.kind.value, "key": kind.key, "title": kind.title,
                   "builtin": "two persons" if two else "one person",
                   "with": ask, "changes": bool((second and not two) or c_roles or c_must)}
            if row not in out:
                out.append(row)
        if not found:
            out.append({"kind": g.kind.value, "key": None, "what": g.what,
                        "note": "no registered approval kind carries this category, so a control scoped to all binds "
                                "nothing yet; scope it to a kind or a family"})
    return out


_MUST_TAIL = " must be among the signers"
_NOT_ELIGIBLE = " does not hold an office that may sign"


def signature_problems(effective: Effective, signers: Iterable[str], roster: Iterable[Any] | None) -> list[str]:
    """Why these named signers do not meet the effective rule's offices, empty when they do. A signer's offices are the
    roster's rows under the same name (trimmed, case folded); a name not on the roster holds none. The engine asks it
    through ``signer_refusals``, once for each control in force."""
    if not (effective.roles or effective.must_include):
        return []
    if roster is None:
        return ["the roster was not read, so the offices that may sign cannot be checked"]
    held = _holders(roster)
    names = [s.strip() for s in signers]
    out = []
    if effective.roles:
        allowed = set().union(*(held.get(r, set()) for r in effective.roles))
        out += [f"{n}{_NOT_ELIGIBLE}" for n in names if n.casefold() not in allowed]
    for role in effective.must_include:
        if not any(n.casefold() in held.get(role, set()) for n in names):
            out.append(f"the {role.value}{_MUST_TAIL}")
    return out


def signer_refusals(kind_key: str, scope: Mapping[str, Any] | None, signers: Iterable[str], *, final: bool = True,
                    amount_cents: int | None = None, controls: Iterable[Control] | None = None,
                    roster: Iterable[Any] | None = None, today: date | None = None, data_dir: Path | None = None,
                    kind: Any = None) -> list[str]:
    """Why these signers do not meet the offices a control in force asks of this plan, each reason naming the control
    by the day the board adopted it. Empty, reading nothing, when no controls source is configured.

    Each control is checked on its own, so a signer must satisfy every one (two controls with no office in common leave
    no one who may sign). ``roles`` (the offices that may sign) binds every signer named. ``must_include`` (offices that
    must be among the signers) binds the signers as a whole, so it is asked only when ``final``: the set is complete,
    and a first signature need not be the required office when a second person follows. A control that asks only above
    an amount is not asked of a plan at or below it (an amount not known counts as above). A roster that cannot be
    read leaves the offices unchecked, as the roster check does (``roster_problem``); the controls themselves still bind."""
    if controls is None:
        from jason.controls import store

        if not store.configured(data_dir):
            return []
        controls = store.load(data_dir=data_dir)
        if roster is None:
            roster = _community_roster()
    if roster is None:
        return []
    names = [s for s in signers if (s or "").strip()]
    got = effective_approver(kind_key, scope, controls=tuple(controls), roster=roster, today=today, kind=kind,
                             amount_cents=amount_cents)
    out: list[str] = []
    for c in got.controls:
        second, threshold, c_roles, c_must = _asks(c)
        if threshold is not None and amount_cents is not None and amount_cents <= threshold:
            continue
        if not (c_roles or c_must):
            continue
        own = Effective(got.kind, got.builtin, roles=c_roles, must_include=c_must if final else ())
        lead = f"a control the board adopted on {c.adopted_at or c.effective}"
        missing: list[str] = []
        for p in signature_problems(own, names, roster):
            if p.endswith(_MUST_TAIL):
                missing.append(p[:-len(_MUST_TAIL)])
            elif p.endswith(_NOT_ELIGIBLE):
                offices = " or ".join(f"the {r.value}" for r in c_roles)
                out.append(f"{lead} allows only {offices} to sign; {p[:-len(_NOT_ELIGIBLE)]} does not hold "
                           f"{'that office' if len(c_roles) == 1 else 'one of those offices'}")
            else:
                out.append(f"{lead}: {p}")
        if missing:
            out.append(f"{lead} requires {' and '.join(missing)} among the signers")
    return list(dict.fromkeys(out))


def _resolved(kind_key: str, scope: Mapping[str, Any] | None, *, amount_cents: int | None,
              controls: Iterable[Control] | None, roster: Iterable[Any] | None, today: date | None,
              data_dir: Path | None, kind: Any) -> Effective | None:
    """The effective approver, or None (reading nothing) when no controls source is configured. The roster is read from
    the active community only when controls are found and none was given; one that cannot be read is not checked."""
    if controls is None:
        from jason.controls import store

        if not store.configured(data_dir):
            return None
        controls = store.load(data_dir=data_dir)
        if roster is None:
            roster = _community_roster()
    return effective_approver(kind_key, scope, controls=tuple(controls), roster=roster, today=today, kind=kind,
                              amount_cents=amount_cents)


def requires_second(kind_key: str, scope: Mapping[str, Any] | None = None, *, amount_cents: int | None = None,
                    controls: Iterable[Control] | None = None, roster: Iterable[Any] | None = None,
                    today: date | None = None, data_dir: Path | None = None, kind: Any = None) -> bool:
    """Whether the controls the board adopted require a second, distinct person on this plan, beyond the kind's own
    rule. False, reading nothing, when no controls source is configured."""
    got = _resolved(kind_key, scope, amount_cents=amount_cents, controls=controls, roster=roster, today=today,
                    data_dir=data_dir, kind=kind)
    return got is not None and got.second_needed(amount_cents)


def refusals(kind_key: str, scope: Mapping[str, Any] | None = None, *, amount_cents: int | None = None,
             controls: Iterable[Control] | None = None, roster: Iterable[Any] | None = None,
             today: date | None = None, data_dir: Path | None = None, kind: Any = None) -> list[str]:
    """Why the act cannot proceed under the controls in force: each binding control the roster cannot satisfy on this
    plan. Empty, reading nothing, when no controls source is configured."""
    got = _resolved(kind_key, scope, amount_cents=amount_cents, controls=controls, roster=roster, today=today,
                    data_dir=data_dir, kind=kind)
    return list(got.refusals) if got is not None else []


def _community_roster() -> tuple[Any, ...] | None:
    try:
        from jason.community import community

        return tuple(community().officers())
    except Exception:  # noqa: BLE001 - a roster that cannot be read leaves the roster check out
        return None


# --- workflow steps ------------------------------------------------------------------------------------------------------
#
# A workflow step's role and its own gates come from its definition. An adopted control can add to them (docs/controls.md,
# section 5): a board resolution on record before the step, a second and different person to confirm it, and a narrower set
# of offices that may record it. It only adds: nothing here lets a step be done by fewer or by anyone the definition refuses.
#
# What a type governs is ``Governs(WORKFLOW_STEP, what)``, where ``what`` is a pattern (``fnmatch``, case sensitive) for a
# step id ("example-cycle.2", "example-cycle.*") or for a workflow key ("example-cycle": every step of it), or "*" for any. A
# control scoped to a kind names the pattern itself, and one scoped to a family names a workflow family: the board's own choice
# always applies. The gates bind from the control's effective date, like the approvals' (``in_force``).

APPROVING = frozenset({"approved", "adopted"})
"""The outcomes of a decision that count as a resolution on record."""


@dataclass(frozen=True)
class StepGate:
    """One gate one control adds to one step. ``gate``: ``resolution``, ``second``, or ``roles`` (with the offices in
    ``roles``). ``reason`` is the sentence the run page shows and the refusal says. ``lacks``: what the roster lacks to
    satisfy it, "" when it can. ``future``: the control is adopted but its date has not come, so it binds nothing yet."""

    control: Control
    gate: str
    reason: str
    roles: tuple[OfficerRole, ...] = ()
    lacks: str = ""
    future: bool = False


@dataclass(frozen=True)
class StepGates:
    """The extra gates the controls in force add to one step. ``resolution``/``second``: some control asks. ``roles``: the
    offices that may record it, narrowed (empty: the definition's own role alone). ``gates``: every gate with the control it
    comes from, those not yet in force marked ``future``. ``controls``: the ones that bind; ``waiting``: adopted, date not
    reached. ``refusals``: why the step cannot proceed, one for each binding gate the roster cannot satisfy."""

    workflow: str
    step: str
    role: str = ""
    resolution: bool = False
    second: bool = False
    roles: tuple[OfficerRole, ...] = ()
    gates: tuple[StepGate, ...] = ()
    controls: tuple[Control, ...] = ()
    waiting: tuple[Waiting, ...] = ()
    refusals: tuple[str, ...] = ()
    clash: str = ""

    @property
    def any(self) -> bool:
        return bool(self.gates)


def _step_matches(pattern: str, workflow_key: str, step_id: str) -> bool:
    return pattern == "*" or fnmatchcase(step_id, pattern) or fnmatchcase(workflow_key, pattern)


def step_applies(control: Control, workflow_key: str, step_id: str, family: str = "") -> bool:
    """Whether the control governs this workflow step: its type governs steps, and its scope (a step pattern, a workflow
    family) or, scoped to all, one of the type's step patterns names the step."""
    patterns = control.type.categories(GovernsKind.WORKFLOW_STEP)
    if not patterns:
        return False
    s = control.scope
    if s.kind is ScopeKind.KIND:
        return _step_matches(s.value, workflow_key, step_id)
    if s.kind is ScopeKind.FAMILY:
        return bool(family) and s.value == family
    if s.kind is ScopeKind.ACCOUNT:
        return False
    return any(_step_matches(p, workflow_key, step_id) for p in patterns)


def _step_asks(c: Control) -> tuple[bool, bool, tuple[OfficerRole, ...]]:
    """What one control asks of a step: (a resolution first, a second person, the offices that may record it)."""
    resolution = bool(c.value("resolution_first")) if _has(c, "resolution_first") else False
    second = _asks(c)[0]
    roles: set[OfficerRole] = set(c.value("roles") or ()) if _has(c, "roles") else set()
    if _has(c, "recorded_by"):
        roles |= set(c.value("recorded_by") or ())
    return resolution, second, tuple(sorted(roles, key=lambda r: r.value))


def _gate_sentence(c: Control, gate: str, roles: tuple[OfficerRole, ...], future: bool) -> str:
    """The sentence a gate is shown and refused with. A control not yet in force says it will, and from when."""
    on = c.adopted_at or (c.effective.isoformat() if c.effective else "")
    who = f"a control the board adopted{' on ' + on if on else ''}"
    when = f", from {c.effective.isoformat() if c.effective else 'a date not set'}," if future else ""
    require = f"will require{when}" if future else "requires"
    if gate == "resolution":
        return (f"{who} {require} a board resolution on record before this step: cite the id of the decision recorded in "
                "Decisions in the record")
    if gate == "second":
        return f"{who} {require} a second, different person to confirm this step"
    names = " or ".join(f"the {r.value}" for r in roles)
    return f"{who} {'will allow' + when if future else 'allows'} only {names} to record this step"


def _step_lack(gate: str, roles: tuple[OfficerRole, ...], role: str, roster: Iterable[Any] | None,
               step_roles: Iterable[str] = ()) -> str:
    """What the roster lacks to satisfy a gate on a step whose definition names ``role`` (and, for a step several roles may
    act on, ``step_roles``); "" when it can or when the roster was not read. A second person holds one of the step's roles too
    (the engine asks it of each person who acts)."""
    if roster is None:
        return ""
    held = _holders(roster)
    if gate == "roles":
        if not any(held.get(r) for r in roles):
            return "the roster has no " + " or ".join(r.value for r in roles)
        return ""
    if gate == "second":
        words = [r for r in dict.fromkeys((role, *step_roles)) if r]
        offices = []
        for word in words:
            try:
                offices.append(OfficerRole(word))
            except ValueError:
                continue
        if not offices:
            return ""
        people = set().union(*(held.get(o, set()) for o in offices))
        names = " or ".join(o.value for o in offices)
        if len(people) < 2:
            return f"the roster has no {names}" if not people else f"the roster lacks a second {names}"
    return ""


def step_gates(workflow_key: str, step_id: str, role: str = "", *, controls: Iterable[Control] = (),
               roster: Iterable[Any] | None = None, today: date | None = None, family: str = "",
               step_roles: Iterable[str] = ()) -> StepGates:
    """The gates the adopted controls add to one step: those in force bind from their date (the roster that cannot satisfy
    one refuses the act, never weakens it), those adopted but not yet in force are listed as ``waiting`` and as ``future``
    gates and bind nothing. A control that is not adopted is never here. Pure: no store is read."""
    today = today or date.today()
    role = role.value if hasattr(role, "value") else str(role or "")
    gates: list[StepGate] = []
    bound: list[Control] = []
    waiting: list[Waiting] = []
    refused: list[str] = []
    roles: tuple[OfficerRole, ...] = ()
    clash = ""
    resolution = second = False
    for c in sorted(controls, key=lambda c: (-c.scope.specificity, c.key)):
        if c.state is not ControlState.ADOPTED or not step_applies(c, workflow_key, step_id, family):
            continue
        asks_resolution, asks_second, c_roles = _step_asks(c)
        if not (asks_resolution or asks_second or c_roles):
            continue
        now = in_force(c, today, roster)
        future = not now.ok
        if future:
            waiting.append(Waiting(c, now.reason))
        else:
            bound.append(c)
        for gate, asked, offices in (("resolution", asks_resolution, ()), ("second", asks_second, ()),
                                     ("roles", bool(c_roles), c_roles)):
            if not asked:
                continue
            lack = "" if future else _step_lack(gate, offices, role, roster, step_roles)
            row = StepGate(c, gate, _gate_sentence(c, gate, offices, future), offices, lack, future)
            gates.append(row)
            if lack:
                refused.append(f"{row.reason}; {lack}")
            if not future:
                resolution = resolution or gate == "resolution"
                second = second or gate == "second"
                if gate == "roles":
                    common = tuple(r for r in roles if r in offices) if roles else offices
                    if common:
                        roles = common
                    else:
                        clash = f"{c.key} and an earlier control name offices with no one in common"
    return StepGates(workflow_key, step_id, role, resolution, second, roles, tuple(gates), tuple(bound), tuple(waiting),
                     tuple(dict.fromkeys(refused)), clash)


def _decided(text: str, ids: Iterable[str]) -> bool:
    return any(re.search(rf"(?<![\w-]){re.escape(i)}(?![\w-])", text, re.IGNORECASE) for i in ids)


def approved_decisions(data_dir: Path | str | None) -> frozenset[str]:
    """The ids of the decisions on record with an approving outcome (``APPROVING``). Reads the decisions store and writes
    nothing; a store that cannot be read has none."""
    if data_dir is None:
        return frozenset()
    try:
        from jason.tasks import decisions

        return frozenset(d.id for d in decisions.load(Path(data_dir)) if (d.outcome or "").lower() in APPROVING and d.id)
    except Exception:  # noqa: BLE001 - a decision store that cannot be read counts as no resolution on record
        return frozenset()


def step_unmet(gates: StepGates, *, by: str, held: Iterable[str] = (), first_by: str = "", texts: Iterable[str] = (),
               data_dir: Path | str | None = None, approved: Iterable[str] | None = None) -> list[str]:
    """Why this person's attestation, skip, or not-applicable record may not be recorded now, each reason the sentence the run page shows; empty
    when every gate in force is met. ``held``: the offices ``by`` holds. ``first_by``: who made the first of two, when one is
    waiting. ``texts``: the words the act and the run carry, where a resolution is cited by the id of a decision that is on
    record with an approving outcome. Date reached, from the control's day: a gate not yet in force is never asked."""
    out: list[str] = []
    mine = {h.strip().casefold() for h in held}
    texts = tuple(texts)
    ids: frozenset[str] | None = None if approved is None else frozenset(approved)
    for g in gates.gates:
        if g.future:
            continue
        if g.lacks:
            out.append(f"{g.reason}; {g.lacks}")
            continue
        if g.gate == "roles":
            if not mine & {r.value for r in g.roles}:
                out.append(g.reason)
        elif g.gate == "resolution":
            if ids is None:
                ids = approved_decisions(data_dir)
            if not any(_decided(t, ids) for t in texts):
                out.append(g.reason)
        elif g.gate == "second" and first_by and first_by.strip().casefold() == by.strip().casefold():
            out.append(f"{g.reason}; {first_by} made the first, so a different person confirms")
    if gates.clash:
        out.append(gates.clash)
    return list(dict.fromkeys(out))


def workflow_gate(ask: Any) -> Any:
    """The gate the workflow engine is given by default (``jason.workflows.api``): the controls the board adopted, read when a
    person attests, skips, or records a step as not applicable. Reads nothing, and so adds nothing, when no controls source is configured, or none
    governs this step. Returns the engine's ``GateVerdict``: the refusals (each a sentence), and whether a second person
    must confirm."""
    from jason.controls import store
    from jason.workflows.types import GateVerdict

    root = Path(ask.data_dir)
    if not store.configured(root):
        return GateVerdict()
    controls = store.load(data_dir=root)
    if not any(c.state is ControlState.ADOPTED and step_applies(c, ask.workflow, ask.step, ask.family) for c in controls):
        return GateVerdict()
    got = step_gates(ask.workflow, ask.step, ask.role, controls=controls, roster=_community_roster(), today=ask.today,
                     family=ask.family, step_roles=getattr(ask, "step_roles", ()))
    if not got.any:
        return GateVerdict()
    unmet = step_unmet(got, by=ask.by, held=ask.roles, first_by=ask.first_by, texts=ask.texts, data_dir=root)
    return GateVerdict(tuple(unmet), got.second)


__all__ = ["APPROVING", "BOARD_ROLES", "Effective", "InForce", "StepGate", "StepGates", "Waiting", "applies",
           "approved_decisions", "effective_approver", "ensure_valid", "in_force", "refusals", "requires_second",
           "roster_problem", "signature_problems", "signer_refusals", "step_applies", "step_gates", "step_unmet",
           "touches", "validate", "workflow_gate"]
