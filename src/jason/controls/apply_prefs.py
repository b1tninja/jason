"""Apply preferences: how a board wants a signed plan applied (docs/console/approval-clarity.md, section 5).

Five preferences, each a control-like row in the catalog (``jason.controls.catalog.PREFERENCES``) adopted the way a control is
(a decision the secretary records, an effective date, a history, the act log): where apply happens (a terminal only, or a
console button), who may apply, a pause after the last signature, a typed count over some number of changes, and a reminder for
a plan that waits. They are opt-in; **until one is adopted the default holds**: a terminal only, any board member or the
manager, no pause, no typed count, a reminder after 24 hours.

They are preferences and not safeguards. They never touch who signs or how many (``effective_approver`` never reads them), and
they never loosen anything the code or the law already sets. The floors, which no choice and no hand-edited facts file can pass:

- the console never applies a kind that is **terminal-only**, that has a **cost**, or that **sends** something to people (mail
  or email). ``console_floor`` says why; a console choice for such a kind is refused when it is adopted (scoped to the kind) and
  is floored back to a terminal when it is read (scoped to all or to a family). The Mailroom send stays at the terminal
  whatever is chosen;
- a preference stays within the engine's rules: a pause only delays an apply, a typed count only adds a step, who may apply only
  narrows (the offices the signers hold are asked by ``effective_approver`` and the controls, and are not read here).

Like every control, a preference binds from its effective date, and where several apply to a kind (one for all, one for a
family, one for the kind) the stricter wins in each respect: a terminal over a console, the longer pause, the lower number for a
typed count, the sooner reminder. ``effective`` reads nothing, and so changes nothing, when no controls source is configured.

Only the enforcement lives here; the engine (``jason.approvals.engine``) asks it before an apply, the web route before it signs
in, and the plan view shows ``words``. Reminders only surface a waiting plan ("reminder due"); nothing is sent. There is no
automatic apply, not even as a flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from jason.approvals import registry
from jason.controls.catalog import PREFERENCES, get as type_of
from jason.controls.types import (Basis, Control, ControlAct, ControlRefused, ControlState, Scope, ScopeKind, stricter)



class Where(str, Enum):
    """Where a signed plan is applied. The catalog's choice lists these values, weakest first (a terminal is the stricter)."""

    CONSOLE = "console"
    TERMINAL = "terminal"


class Who(str, Enum):
    """Who may apply a signed plan. ``CLASH`` is not a choice: two preferences that leave no one."""

    BOARD_OR_MANAGER = "board_or_manager"
    ANY_SIGNER = "any_signer"
    NOT_SIGNER = "not_signer"
    CLASH = "clash"


WHERE = tuple(w.value for w in Where)
WHO = tuple(w.value for w in Who if w is not Who.CLASH)
DEFAULT_REMINDER_HOURS = 24
KEYS = tuple(t.key for t in PREFERENCES)

WHERE_DEFAULT = "At a terminal only: a person runs the command; there is no apply button."
WHO_WORDS = {
    Who.BOARD_OR_MANAGER: "Any board member or the manager.",
    Who.ANY_SIGNER: "Only a person who signed this plan.",
    Who.NOT_SIGNER: "A board member or the manager who did not sign this plan (the person who signed does not also apply).",
}


# --- the floors ----------------------------------------------------------------------------------------------------------

def console_floor(kind: Any) -> str:
    """Why the console may never apply this kind, whatever a board prefers; "" when it may. A kind that is terminal-only (a
    mailing cannot be recalled), has a cost, or sends mail or email."""
    if kind.terminal_only:
        return f"{kind.key} is applied only by a person at a terminal ({kind.cli})"
    if kind.has_cost:
        return f"{kind.key} costs money ({kind.cost})"
    if getattr(kind, "has_sends", False):
        return f"{kind.key} sends something to people ({kind.sends})"
    return ""


def governs(control: Control, kind: Any) -> bool:
    """Whether a preference covers this kind: scoped to all, to the kind (by key or alias), or to its family (the system it
    writes to)."""
    if not control.type.governs_apply:
        return False
    s = control.scope
    if s.kind is ScopeKind.ALL:
        return True
    if s.kind is ScopeKind.KIND:
        return s.value == kind.key or s.value in getattr(kind, "aliases", ())
    if s.kind is ScopeKind.FAMILY:
        return s.value == kind.system
    return False


# --- what a preference may be --------------------------------------------------------------------------------------------

def problems(control: Control, kinds: Iterable[Any] | None = None) -> list[str]:
    """Why this preference cannot be taken, empty when it can (called by ``effective.validate``): a scope that names an
    account or a kind the engine lacks, an adoption that names no value, two values that contradict, or a console choice
    for a kind the floors close to the console."""
    out: list[str] = []
    s, key = control.scope, control.type.key
    kind = None
    if s.kind is ScopeKind.ACCOUNT:
        out.append("a preference for applying names a kind or a family of kinds, not an account")
    if s.kind is ScopeKind.KIND:
        known = {k.key: k for k in (kinds if kinds is not None else registry.kinds())}
        for k in list(known.values()):
            known.update({a: k for a in getattr(k, "aliases", ())})
        kind = known.get(s.value)
        if kind is None:
            out.append(f"no action kind {s.value}: a preference names a kind the engine has")
    adopted = control.state is ControlState.ADOPTED
    given = control.parameters
    if key == "where-apply":
        if adopted and "where" not in given:
            out.append("an adoption names where apply happens (where)")
        if given.get("where") == Where.CONSOLE and kind is not None and console_floor(kind):
            out.append(f"the console cannot apply {kind.key}, whatever a board prefers: {console_floor(kind)}")
    elif key == "who-may-apply":
        if adopted and "who" not in given:
            out.append("an adoption names who may apply (who)")
    elif key == "pause-before-apply":
        if adopted and not (given.get("minutes") or given.get("until_next_day")):
            out.append("an adoption names the pause (minutes, or until_next_day)")
    elif key == "typed-count-over":
        if adopted and "over" not in given:
            out.append("an adoption names the number of changes above which the count is typed (over)")
    elif key == "reminder-hours":
        if given.get("off") and "hours" in given:
            out.append("a reminder is either off or due after some hours, not both")
        elif adopted and not (given.get("off") or "hours" in given):
            out.append("an adoption names the hours (hours), or that there is no reminder (off)")
    return out


# --- the effective preferences ---------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class ApplyPrefs:
    """What applies to one kind now. ``where``: ``terminal`` or ``console``; ``who``: one of ``WHO``, or ``clash`` (two
    preferences leave no one). ``who_adopted``: a control set it, so the roster is asked who may apply. ``pause_minutes`` /
    ``pause_until_next_day``: the pause after the last signature. ``typed_count_over``: None is off. ``reminder_hours``: None
    is no reminder. ``floored``: the console was chosen and the floors closed it, with why. ``sources``: for each setting
    the keys of the controls that set it, and ``adopted``: the day each was adopted. ``waiting``: adopted, date not reached."""

    kind: str
    where: Where = Where.TERMINAL
    who: Who = Who.BOARD_OR_MANAGER
    who_adopted: bool = False
    pause_minutes: int = 0
    pause_until_next_day: bool = False
    typed_count_over: int | None = None
    reminder_hours: int | None = DEFAULT_REMINDER_HOURS
    floored: str = ""
    floor: str = ""
    clash: str = ""
    sources: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    adopted: Mapping[str, str] = field(default_factory=dict)
    waiting: tuple[tuple[str, str, str], ...] = ()          # (control key, setting, why not yet)

    @property
    def pausing(self) -> bool:
        return bool(self.pause_minutes or self.pause_until_next_day)


def _spec(type_key: str, param: str):
    return type_of(type_key).spec(param)


def _day(c: Control) -> str:
    return c.adopted_at or (c.effective.isoformat() if c.effective else "")


def resolve(kind: Any, controls: Iterable[Control], today: date) -> ApplyPrefs:
    """The kind's preferences from the controls given: those adopted and in force (their date reached), the stricter of any
    two in each respect, then the floors. Pure."""
    from jason.controls.effective import in_force

    bound: dict[str, list[Control]] = {}
    waiting: list[tuple[str, str, str]] = []
    for c in sorted(controls, key=lambda c: (-c.scope.specificity, c.key)):
        if c.state is not ControlState.ADOPTED or c.type.key not in KEYS or not governs(c, kind):
            continue
        now = in_force(c, today)
        if now.ok:
            bound.setdefault(c.type.key, []).append(c)
        else:
            waiting.append((c.key, c.type.key, now.reason))
    sources = {k: tuple(c.key for c in v) for k, v in bound.items()}
    adopted = {k: min(_day(c) for c in v) for k, v in bound.items()}

    where, floored = Where.TERMINAL, ""
    chosen = [c.value("where") for c in bound.get("where-apply", ()) if c.value("where")]
    if chosen:
        where = chosen[0]
        for w in chosen[1:]:
            where = stricter(_spec("where-apply", "where"), where, w)
        where = Where(where)
    floor = console_floor(kind)
    if where is Where.CONSOLE and floor:
        where, floored = Where.TERMINAL, floor

    asked = {Who(c.value("who")) for c in bound.get("who-may-apply", ()) if c.value("who")}
    clash = ""
    if {Who.ANY_SIGNER, Who.NOT_SIGNER} <= asked:
        who, clash = Who.CLASH, ("two preferences the board adopted leave no one who may apply: one allows only a person who "
                               "signed, the other only a person who did not")
    else:
        who = (Who.NOT_SIGNER if Who.NOT_SIGNER in asked else Who.ANY_SIGNER if Who.ANY_SIGNER in asked
               else Who.BOARD_OR_MANAGER)

    pauses = bound.get("pause-before-apply", ())
    minutes = max([c.value("minutes") or 0 for c in pauses], default=0)
    next_day = any(bool(c.value("until_next_day")) for c in pauses)

    overs = [c.value("over") for c in bound.get("typed-count-over", ()) if c.value("over") is not None]
    over = min(overs) if overs else None

    reminders = bound.get("reminder-hours", ())
    hours = [c.value("hours") for c in reminders if c.value("hours")]
    if hours:
        remind: int | None = min(hours)
    elif any(c.value("off") for c in reminders):
        remind = None
    else:
        remind = DEFAULT_REMINDER_HOURS
    return ApplyPrefs(kind.key, where, who, bool(asked), minutes, next_day, over, remind, floored, floor, clash,
                      sources, adopted, tuple(waiting))


def effective(kind: Any, *, controls: Iterable[Control] | None = None, today: date | None = None,
              data_dir: Path | None = None) -> ApplyPrefs:
    """The preferences for a kind (an ``ActionKind`` or its key). With no controls source configured the defaults hold and
    nothing is read."""
    if isinstance(kind, str):
        kind = registry.get(kind)
    if controls is None:
        from jason.controls import store

        if not store.configured(data_dir):
            return resolve(kind, (), today or date.today())
        controls = store.load(data_dir=data_dir)
    return resolve(kind, tuple(controls), today or date.today())


# --- enforcement -----------------------------------------------------------------------------------------------------------

def where_refusal(prefs: ApplyPrefs, kind: Any) -> str:
    """Why the console may not apply this kind now, "" when it may (the server's ``--allow-apply`` is asked separately)."""
    if prefs.where is Where.CONSOLE:
        return ""
    if prefs.floored:
        return (f"the board chose the console, but the console never applies this kind: {prefs.floored}. A person applies it "
                f"at a terminal: {kind.cli}")
    return ("apply is at a terminal: the board has not adopted a console button for this kind (jason controls). A person "
            f"applies it at a terminal: {kind.cli if kind.terminal_only else 'jason approvals apply ID --yes --by NAME'}")


def pause_ends(signed: datetime | None, prefs: ApplyPrefs, tz: tzinfo | None = None) -> datetime | None:
    """When the pause after the last signature ends, or None when there is none (or the plan is not signed). The next day
    begins at midnight in ``tz`` (the machine's own by default)."""
    if signed is None or not prefs.pausing:
        return None
    ends = []
    if prefs.pause_minutes:
        ends.append(signed + timedelta(minutes=prefs.pause_minutes))
    if prefs.pause_until_next_day:
        local = signed.astimezone(tz) if tz is not None else signed.astimezone()
        ends.append((local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
    return max(ends)


def pause_words(prefs: ApplyPrefs) -> str:
    bits = []
    if prefs.pause_minutes:
        bits.append(f"{prefs.pause_minutes} minute{'s' if prefs.pause_minutes != 1 else ''} after the last signature")
    if prefs.pause_until_next_day:
        bits.append("until the next day")
    if not bits:
        return "No pause: a signed plan can be applied as soon as it is signed."
    return "A pause of " + " and ".join(bits) + " before the plan is applied; until then it can be withdrawn."


def left(ends: datetime, now: datetime) -> str:
    """How long until ``ends``, in words."""
    seconds = max(0, int((ends - now).total_seconds()))
    if seconds < 90:
        return "less than a minute" if seconds < 60 else "1 minute"
    minutes = (seconds + 59) // 60
    if minutes < 120:
        return f"{minutes} minutes"
    hours = (minutes + 59) // 60
    return f"{hours} hours" if hours < 48 else f"{hours // 24} days"


def pause_problem(prefs: ApplyPrefs, signed: datetime | None, now: datetime, tz: tzinfo | None = None) -> str:
    """"" once the pause has ended (or there is none), else why the plan is not offered for apply yet."""
    ends = pause_ends(signed, prefs, tz)
    if ends is None or now >= ends:
        return ""
    on = prefs.adopted.get("pause-before-apply", "")
    return (f"a pause before apply is in force (the board adopted it{' on ' + on if on else ''}): this plan can be applied "
            f"after {ends.astimezone(timezone.utc).isoformat(timespec='seconds')}, {left(ends, now)} from now. Until then "
            "it can be withdrawn")


def who_problems(prefs: ApplyPrefs, by: str, signers: Iterable[str], roster: Iterable[Any] | None) -> list[str]:
    """Why ``by`` may not apply, empty when they may. Asked only when a control set who may apply: the default (any board
    member or the manager) is kept by the sign-in on the console and the person at the terminal, and is not checked against
    the roster, so a name not on it is not refused where no control is adopted."""
    from jason.approvals.model import same_person
    from jason.controls.effective import _holders

    if prefs.who is Who.CLASH:
        return [prefs.clash]
    if not prefs.who_adopted:
        return []
    on = prefs.adopted.get("who-may-apply", "")
    lead = f"a preference the board adopted{' on ' + on if on else ''}"
    out: list[str] = []
    named = [s for s in signers if (s or "").strip()]
    if roster is not None:
        held = _holders(roster)
        if held and by.strip().casefold() not in set().union(*held.values()):
            out.append(f"{lead} lets only a board member or the manager apply a signed plan; {by} holds no such office on "
                       "the roster")
    signed = any(same_person(by, s) for s in named)
    if prefs.who is Who.ANY_SIGNER and not signed:
        out.append(f"{lead} lets only a person who signed this plan apply it; {by} did not sign it")
    if prefs.who is Who.NOT_SIGNER and signed:
        out.append(f"{lead} does not let a person who signed this plan also apply it; {by} signed it, so another board "
                   "member or the manager applies")
    return out


def typed_needed(prefs: ApplyPrefs, changes: int) -> bool:
    return prefs.typed_count_over is not None and changes > prefs.typed_count_over


def typed_problem(prefs: ApplyPrefs, changes: int, typed: int | None) -> str:
    """"" when no count is asked or the typed one is right, else why the apply is refused."""
    if not typed_needed(prefs, changes):
        return ""
    on = prefs.adopted.get("typed-count-over", "")
    lead = (f"a preference the board adopted{' on ' + on if on else ''} asks the person applying to type the number of changes "
            f"when a plan makes more than {prefs.typed_count_over}")
    if typed is None:
        return f"{lead}: type the number this plan makes (in a terminal, --count N; the dry run lists them)"
    if typed != changes:
        return f"{lead}: {typed} is not the number of changes this plan makes"
    return ""


def reminder_due(prefs: ApplyPrefs, waiting_hours: float) -> bool:
    return prefs.reminder_hours is not None and waiting_hours >= prefs.reminder_hours


# --- in words --------------------------------------------------------------------------------------------------------------

def _row(prefs: ApplyPrefs, key: str, setting: str, title: str, words: str) -> dict[str, Any]:
    sources = prefs.sources.get(key, ())
    return {"setting": setting, "title": title, "words": words, "default": not sources,
            "source": "the default; the board has not adopted one" if not sources
            else f"the board adopted this{' on ' + prefs.adopted[key] if prefs.adopted.get(key) else ''}",
            "controls": list(sources)}


def rows(prefs: ApplyPrefs) -> list[dict[str, Any]]:
    """The five settings in plain words, each with where it comes from, for the plan view and ``jason approvals show``."""
    where = ("From the console, once the server allows apply (jason-web started with --allow-apply)."
             if prefs.where is Where.CONSOLE else WHERE_DEFAULT)
    if prefs.floored:
        where += f" The board chose the console, but it never applies this kind: {prefs.floored}."
    elif prefs.where is Where.TERMINAL and prefs.floor and not prefs.sources.get("where-apply"):
        where += f" The console never applies this kind in any case: {prefs.floor}."
    typed = (f"Above {prefs.typed_count_over} changes the person applying types the number of changes."
             if prefs.typed_count_over is not None else "No typed count.")
    remind = (f"A reminder is due {prefs.reminder_hours} hours after the last signature. It only appears on the screens; "
              "nothing is sent." if prefs.reminder_hours is not None else "No reminder.")
    return [
        _row(prefs, "where-apply", "where", "Where apply happens", where),
        _row(prefs, "who-may-apply", "who", "Who may apply",
             prefs.clash if prefs.who is Who.CLASH else WHO_WORDS[prefs.who]),
        _row(prefs, "pause-before-apply", "pause", "A pause before apply", pause_words(prefs)),
        _row(prefs, "typed-count-over", "typed", "A typed count", typed),
        _row(prefs, "reminder-hours", "reminder", "A reminder for a signed plan", remind),
    ]


def as_dict(prefs: ApplyPrefs) -> dict[str, Any]:
    """The preferences as the plan view reads them (plain values and words); nothing private."""
    return {"kind": prefs.kind, "where": prefs.where.value, "who": prefs.who.value, "pauseMinutes": prefs.pause_minutes,
            "pauseUntilNextDay": prefs.pause_until_next_day, "typedCountOver": prefs.typed_count_over,
            "reminderHours": prefs.reminder_hours, "consoleFloor": prefs.floor, "consoleFloored": bool(prefs.floored),
            "clash": prefs.clash, "rows": rows(prefs),
            "waiting": [{"control": k, "setting": s, "why": w} for k, s, w in prefs.waiting]}


# --- offering one ----------------------------------------------------------------------------------------------------------

READING = ("A preference for how a signed plan is applied, not a safeguard: it never lowers a signature count, removes a "
           "control, or lets the console apply a kind that is terminal-only, costs money, or sends mail or email. Until the "
           "board adopts it, the default holds.")


def parse_scope(text: str) -> Scope:
    """``all``, ``kind:KEY``, or ``family:SYSTEM`` as a scope."""
    text = (text or "all").strip()
    if text == "all":
        return Scope()
    head, _, value = text.partition(":")
    if head not in ("kind", "family") or not value.strip():
        raise ControlRefused(f"a scope is all, kind:KEY, or family:SYSTEM, not {text!r}")
    return Scope(ScopeKind.KIND if head == "kind" else ScopeKind.FAMILY, value.strip())


def offer(type_key: str, *, by: str, scope: Scope | None = None, data_dir: Path | None = None, community: Any = None,
          now: datetime | None = None) -> Control:
    """Record a preference as a suggestion (a ``suggest`` act in the log), so the board can be asked about it. It adopts
    nothing: the same lifecycle as any control (``jason controls --propose``, then the secretary records the decision with
    ``--adopt``)."""
    from jason.controls import store

    ctype = type_of(type_key)
    if not ctype.governs_apply:
        raise ControlRefused(f"{type_key} is not an apply preference: " + ", ".join(KEYS))
    scope = scope or Scope()
    key = type_key if scope.kind is ScopeKind.ALL else f"{type_key}--{scope.kind.value}-{scope.value}"
    control = Control(key, ctype, {}, scope, Basis("the board's choice of how a signed plan is applied"), READING)
    return store.record(ControlAct.SUGGEST, key, by=by, why=f"offered by {by.strip()} for the board to consider",
                        control=control, data_dir=data_dir, community=community, now=now)


__all__ = ["ApplyPrefs", "DEFAULT_REMINDER_HOURS", "KEYS", "READING", "WHERE", "WHO", "Where", "Who", "as_dict", "console_floor", "effective",
           "governs", "left", "offer", "parse_scope", "pause_ends", "pause_problem", "pause_words", "problems",
           "reminder_due", "resolve", "rows", "typed_needed", "typed_problem", "where_refusal", "who_problems"]
