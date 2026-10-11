"""The control records: pure data and the parameter algebra, no disk and no profile.

A ``ControlType`` is written once, in jason, for any association (``jason.controls.catalog``). A ``Control`` is one
association's use of a type: the parameters as adopted, the scope it covers, the provision it rests on, jason's labeled
reading, and its state, with an append-only history. The design is docs/controls.md.

A control only adds. Every parameter has a direction in which it is stricter (``ParamKind``), and a floor below which no
control may go: the type's own (``ControlType.floor``) and the one its provision sets (``Basis.floor``). ``meets``
says whether a value is at least as strict as a floor; ``stricter`` picks the stricter of two values.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from typing import Any, Iterable, Mapping

from jason.community.base import OfficerRole


class ControlRefused(ValueError):
    """A control, a parameter, or an act the record will not take. Nothing was changed."""


class ControlFamily(Enum):
    MONEY = "money"
    CONTRACTS = "contracts"
    REVIEWS = "reviews"
    NOTICES = "notices"
    MEETINGS = "meetings"
    ONBOARDING = "onboarding"
    APPLYING = "applying"          # how a board wants signed plans applied (preferences, never safeguards)


class GovernsKind(Enum):
    """What a control type governs: a kind of approval, a workflow step, a send, or a spend."""

    APPROVAL_KIND = "approval kind"
    WORKFLOW_STEP = "workflow step"
    SEND = "send"
    SPEND = "spend"
    APPLY = "apply"                # how a signed plan is applied: a preference (``jason.controls.apply_prefs``)


@dataclass(frozen=True)
class Governs:
    """One thing a type governs. ``what`` is a category the thing carries ("payment", "reserve") or "*" for any."""

    kind: GovernsKind
    what: str = "*"


class ParamKind(Enum):
    """The shape of a parameter, and the direction in which it is stricter."""

    COUNT = "count"            # people needed: more is stricter
    ELIGIBLE = "eligible"      # the roles who may count: a narrower set is stricter ((): any board member)
    REQUIRED = "required"      # roles that must act: a wider set is stricter
    CENTS = "cents"            # an amount above which the control bites: lower is stricter
    DAYS = "days"              # a period: shorter is stricter
    CHOICE = "choice"          # one of ``options``, weakest first: later is stricter
    FLAG = "flag"              # on or off: on is stricter
    CEILING = "ceiling"        # a whole number at or under which the control acts: lower is stricter (0 is allowed)


@dataclass(frozen=True)
class ParamSpec:
    key: str
    kind: ParamKind
    title: str
    maximum: int | None = None            # a COUNT, CENTS, DAYS, or CEILING cannot exceed it (what jason can enforce)
    options: tuple[str, ...] = ()         # a CHOICE's values, weakest first
    minimum: int | None = None            # the least a whole number may be (default: 1 for a COUNT, else 0)


@dataclass(frozen=True)
class Cue:
    """One kind of words a provision uses. ``name`` is how the reading calls it; ``pattern`` is a regular expression
    matched without regard to case. Cues are general language ("shall be signed by"), never one association's words."""

    name: str
    pattern: str


@dataclass(frozen=True)
class FloorRead:
    """How the floor a provision sets on a COUNT parameter is read from its words, where one count is certain. Each
    pattern has a group ``n`` for the count (a number word or digits). The reader uses it only when every read in the
    sentence agrees and nothing offers an alternative (``or``) after the count; otherwise the floor is a person's to read."""

    param: str
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class Evidence:
    """When a provision speaks to a control type. Every cue in ``cues`` found in one sentence is a match; found only
    across the section, a question. A cue of ``unless`` found in the same sentence turns the match away (the words belong
    to another type). ``floor`` says how a count is read."""

    cues: tuple[Cue, ...]
    unless: tuple[Cue, ...] = ()
    floor: tuple[FloorRead, ...] = ()


@dataclass(frozen=True)
class ControlType:
    """A safeguard the catalog offers. ``floor`` is what the law or a built-in rail already requires, as data keyed by
    parameter: a control may not go below it. A floor that is one association's (what its bylaws require) is the
    control's own ``Basis.floor``, never the catalog's. ``sources`` are the kinds of provision that suggest it.

    ``evidence`` is the words (any one ``Evidence`` row) that suggest the type (``jason.controls.suggest``); a type with
    none is never suggested from the documents. ``proposal`` is jason's proposal for the parameters, labeled as one wherever
    it is shown; ``board_sets`` are the parameters it leaves to the board (an amount is never invented)."""

    key: str
    title: str
    family: ControlFamily
    governs: tuple[Governs, ...]
    parameters: tuple[ParamSpec, ...]
    floor: Mapping[str, Any] = field(default_factory=dict)
    sources: tuple[str, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    proposal: Mapping[str, Any] = field(default_factory=dict)
    board_sets: tuple[str, ...] = ()

    def spec(self, key: str) -> ParamSpec:
        for p in self.parameters:
            if p.key == key:
                return p
        raise ControlRefused(f"{self.key} has no parameter {key}: " + ", ".join(p.key for p in self.parameters))

    @property
    def governs_approvals(self) -> bool:
        return any(g.kind is GovernsKind.APPROVAL_KIND for g in self.governs)

    @property
    def governs_apply(self) -> bool:
        """An apply preference (``jason.controls.apply_prefs``): it never touches who signs or how many."""
        return any(g.kind is GovernsKind.APPLY for g in self.governs)

    def categories(self, kind: GovernsKind = GovernsKind.APPROVAL_KIND) -> frozenset[str]:
        return frozenset(g.what for g in self.governs if g.kind is kind)


class ScopeKind(Enum):
    ALL = "all"
    FAMILY = "family"      # a family of approval kinds: the system a kind works in
    KIND = "kind"          # one approval kind
    ACCOUNT = "account"    # one account (the plan's scope names it)


@dataclass(frozen=True)
class Scope:
    kind: ScopeKind = ScopeKind.ALL
    value: str = ""

    @property
    def specificity(self) -> int:
        return {ScopeKind.ALL: 0, ScopeKind.FAMILY: 1, ScopeKind.KIND: 2, ScopeKind.ACCOUNT: 2}[self.kind]


class ControlState(Enum):
    SUGGESTED = "suggested"
    PROPOSED = "proposed"
    ADOPTED = "adopted"
    DECLINED = "declined"
    DEFERRED = "deferred"
    RETIRED = "retired"


class ControlAct(Enum):
    SUGGEST = "suggest"
    PROPOSE = "propose"
    ADOPT = "adopt"
    DECLINE = "decline"
    DEFER = "defer"
    RETIRE = "retire"


# Every allowed move: the act and the states it may start from. A suggestion starts a control; nothing else does.
MOVES: dict[ControlAct, tuple[frozenset[ControlState | None], ControlState | None]] = {
    ControlAct.SUGGEST: (frozenset({None}), ControlState.SUGGESTED),
    ControlAct.PROPOSE: (frozenset({ControlState.SUGGESTED, ControlState.DEFERRED, ControlState.DECLINED}),
                         ControlState.PROPOSED),
    ControlAct.ADOPT: (frozenset({ControlState.PROPOSED}), ControlState.ADOPTED),
    ControlAct.DECLINE: (frozenset({ControlState.PROPOSED, ControlState.DEFERRED}), ControlState.DECLINED),
    ControlAct.DEFER: (frozenset({ControlState.PROPOSED}), ControlState.DEFERRED),
    ControlAct.RETIRE: (frozenset({ControlState.ADOPTED}), ControlState.RETIRED),
}


@dataclass(frozen=True)
class Basis:
    """The provision a control rests on: its citation, its words as stored (recited whole; empty means cited, not
    quoted), and the floor it sets as data (``{"signers": 2}``), which binds the control as the catalog's floor does."""

    citation: str
    words: str = ""
    floor: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoryEntry:
    """One act, as recorded: who, when, why. Append only."""

    act: ControlAct
    by: str
    at: str
    why: str
    decision: str = ""
    again_on: str = ""


@dataclass(frozen=True)
class Control:
    """One association's control. ``parameters`` are normalized (``normalize``) and read-only by convention."""

    key: str
    type: ControlType
    parameters: Mapping[str, Any] = field(default_factory=dict)
    scope: Scope = field(default_factory=Scope)
    basis: Basis = field(default_factory=lambda: Basis(""))
    reading: str = ""                      # jason's reading, labeled as such wherever it is shown
    state: ControlState = ControlState.SUGGESTED
    decision: str = ""                     # the decision id the secretary recorded
    effective: date | None = None
    history: tuple[HistoryEntry, ...] = ()

    def value(self, key: str) -> Any:
        """The parameter as adopted, else its floor, else None (also None for a parameter the type does not have)."""
        if not any(p.key == key for p in self.type.parameters):
            return None
        if key in self.parameters:
            return self.parameters[key]
        return floor_of(self, key)

    @property
    def adopted_at(self) -> str:
        """The day the board adopted it (the adopting act's date), else the effective date, else ""."""
        for h in reversed(self.history):
            if h.act is ControlAct.ADOPT:
                return h.at[:10]
        return self.effective.isoformat() if self.effective else ""


# --- the parameter algebra -------------------------------------------------------------------------------------------

def _role(raw: Any) -> OfficerRole:
    if isinstance(raw, OfficerRole):
        return raw
    try:
        return OfficerRole(str(raw).strip().lower())
    except ValueError:
        raise ControlRefused(f"{raw!r} is not an office: " + ", ".join(r.value for r in OfficerRole)) from None


def normalize(spec: ParamSpec, raw: Any) -> Any:
    """The parameter's value as the record holds it (roles as ``OfficerRole`` in a sorted tuple), or ``ControlRefused``."""
    k = spec.kind
    if k in (ParamKind.COUNT, ParamKind.CENTS, ParamKind.DAYS, ParamKind.CEILING):
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ControlRefused(f"{spec.key} is a whole number")
        if raw < (spec.minimum if spec.minimum is not None else (1 if k is ParamKind.COUNT else 0)):
            raise ControlRefused(f"{spec.key} is {raw}: too low")
        if spec.maximum is not None and raw > spec.maximum:
            raise ControlRefused(f"{spec.key} is {raw}: jason enforces at most {spec.maximum}")
        return raw
    if k in (ParamKind.ELIGIBLE, ParamKind.REQUIRED):
        if isinstance(raw, (str, OfficerRole)) or not isinstance(raw, Iterable):
            raise ControlRefused(f"{spec.key} is a list of offices")
        return tuple(sorted({_role(r) for r in raw}, key=lambda r: r.value))
    if k is ParamKind.CHOICE:
        if raw not in spec.options:
            raise ControlRefused(f"{spec.key} is {raw!r}: one of " + ", ".join(spec.options))
        return raw
    if not isinstance(raw, bool):
        raise ControlRefused(f"{spec.key} is true or false")
    return raw


def meets(spec: ParamSpec, value: Any, floor: Any) -> bool:
    """Whether ``value`` is at least as strict as ``floor`` (a floor of None asks nothing)."""
    if floor is None:
        return True
    k = spec.kind
    if k is ParamKind.COUNT or k is ParamKind.FLAG:
        return value >= floor
    if k in (ParamKind.CENTS, ParamKind.DAYS, ParamKind.CEILING):
        return value is not None and value <= floor
    if k is ParamKind.ELIGIBLE:
        return True if not floor else bool(value) and set(value) <= set(floor)
    if k is ParamKind.REQUIRED:
        return set(floor) <= set(value or ())
    return spec.options.index(value) >= spec.options.index(floor)       # CHOICE


def stricter(spec: ParamSpec, a: Any, b: Any) -> Any:
    """The stricter of two values; None is no value, and the other wins."""
    if a is None:
        return b
    if b is None:
        return a
    k = spec.kind
    if k is ParamKind.COUNT or k is ParamKind.FLAG:
        return max(a, b)
    if k in (ParamKind.CENTS, ParamKind.DAYS, ParamKind.CEILING):
        return min(a, b)
    if k is ParamKind.ELIGIBLE:
        if not a:
            return b
        if not b:
            return a
        return tuple(sorted(set(a) & set(b), key=lambda r: r.value))
    if k is ParamKind.REQUIRED:
        return tuple(sorted(set(a) | set(b), key=lambda r: r.value))
    return a if spec.options.index(a) >= spec.options.index(b) else b


def floor_of(control: Control, key: str) -> Any:
    """The strictest floor on ``key``: the type's, then the provision's (a basis floor is normalized as a value is)."""
    spec = control.type.spec(key)
    out = control.type.floor.get(key)
    if out is not None:
        out = normalize(spec, out)
    basis = control.basis.floor.get(key)
    if basis is not None:
        out = stricter(spec, out, normalize(spec, basis))
    return out


def with_state(control: Control, state: ControlState, **changes: Any) -> Control:
    return replace(control, state=state, **changes)


# --- the JSON the record is kept as -----------------------------------------------------------------------------------

def _plain(spec: ParamSpec, value: Any) -> Any:
    return [r.value for r in value] if spec.kind in (ParamKind.ELIGIBLE, ParamKind.REQUIRED) else value


def parameters_to_dict(ctype: ControlType, params: Mapping[str, Any]) -> dict[str, Any]:
    return {k: _plain(ctype.spec(k), normalize(ctype.spec(k), v)) for k, v in params.items()}


def parameters_from_dict(ctype: ControlType, raw: Mapping[str, Any] | None) -> dict[str, Any]:
    return {k: normalize(ctype.spec(k), v) for k, v in (raw or {}).items()}


def _day(raw: Any) -> date | None:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        raise ControlRefused(f"{raw!r} is not a date (YYYY-MM-DD)") from None


def _enum(cls: type[Enum], raw: Any, what: str) -> Any:
    try:
        return cls(raw)
    except ValueError:
        raise ControlRefused(f"{raw!r} is not a {what}: " + ", ".join(str(m.value) for m in cls)) from None


def scope_to_dict(scope: Scope) -> dict[str, str]:
    return {"kind": scope.kind.value, "value": scope.value}


def scope_from_dict(raw: Mapping[str, Any] | None) -> Scope:
    raw = raw or {}
    kind = _enum(ScopeKind, raw.get("kind", "all"), "scope")
    value = str(raw.get("value") or "")
    if kind is not ScopeKind.ALL and not value:
        raise ControlRefused(f"a scope of {kind.value} names which")
    return Scope(kind, value)


def history_to_dict(h: HistoryEntry) -> dict[str, str]:
    return {k: v for k, v in {"act": h.act.value, "by": h.by, "at": h.at, "why": h.why, "decision": h.decision,
                              "againOn": h.again_on}.items() if v}


def history_from_dict(raw: Mapping[str, Any]) -> HistoryEntry:
    return HistoryEntry(_enum(ControlAct, raw.get("act"), "control act"), str(raw.get("by") or ""),
                        str(raw.get("at") or ""), str(raw.get("why") or ""), str(raw.get("decision") or ""),
                        str(raw.get("againOn") or ""))


def to_dict(c: Control) -> dict[str, Any]:
    return {"key": c.key, "type": c.type.key, "parameters": parameters_to_dict(c.type, c.parameters),
            "scope": scope_to_dict(c.scope),
            "basis": {"citation": c.basis.citation, "words": c.basis.words, "floor": dict(c.basis.floor)},
            "reading": c.reading, "state": c.state.value, "decision": c.decision,
            "effective": c.effective.isoformat() if c.effective else "",
            "history": [history_to_dict(h) for h in c.history]}


def from_dict(raw: Mapping[str, Any]) -> Control:
    """A control from its JSON. An unknown type, parameter, state, or scope is ``ControlRefused``, never a guess."""
    from jason.controls.catalog import get

    key = str(raw.get("key") or "").strip()
    if not key:
        raise ControlRefused("a control has a key")
    ctype = get(str(raw.get("type") or ""))
    basis = raw.get("basis") or {}
    return Control(key, ctype, parameters_from_dict(ctype, raw.get("parameters")), scope_from_dict(raw.get("scope")),
                   Basis(str(basis.get("citation") or ""), str(basis.get("words") or ""),
                         dict(basis.get("floor") or {})),
                   str(raw.get("reading") or ""), _enum(ControlState, raw.get("state", "suggested"), "state"),
                   str(raw.get("decision") or ""), _day(raw.get("effective")),
                   tuple(history_from_dict(h) for h in raw.get("history") or ()))


__all__ = ["Basis", "Control", "ControlAct", "ControlFamily", "ControlRefused", "ControlState", "ControlType", "Cue",
           "Evidence", "FloorRead", "Governs", "GovernsKind", "HistoryEntry", "MOVES", "ParamKind", "ParamSpec", "Scope",
           "ScopeKind", "floor_of",
           "from_dict", "meets", "normalize", "parameters_from_dict", "parameters_to_dict", "stricter", "to_dict",
           "with_state"]
