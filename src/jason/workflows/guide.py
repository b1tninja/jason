"""What a person step shows the person who meets it: the words, the evidence, the rule, the command, and what done looks like
(docs/workflows/person-steps.md, sections 4.1 and 7). A pure derivation from the definition: a step with no ``Support`` is never empty,
because every field falls back to something the step already holds (the procedure step's ``do``, ``check``, and ``lessons``; the
step's ``command``, ``record``, ``evidence``, and ``clock``). Nothing is read from a store or a shelf here: the readers and the
authorities shelf are the caller's, and the page that recites a statute recites it from there, never from this module.

Guidance is general. It names kinds, topics, and questions, never an association's facts, and the validator (``problems``) refuses a
section number (the cite carries it), a link, an address, a phone number, or an amount in the words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from jason.workflows.nudge import ESCALATION, is_person_step
from jason.workflows.types import (
    OFFICES, Check, Cite, ClockBasis, Cmd, Enables, Guides, LookAt, Reminds, Role, StepDef, Support, Visibility, Workflow, parse_sop,
)

PLACEHOLDERS = ("NAME", "KEY", "RUN", "ID")
"""The four words a command may leave for the page or the person to fill. ``NAME`` and ``RUN`` are filled from the signed-in name and
the run; ``KEY`` and ``ID`` are always the person's to fill in."""

MAX_CHECKLIST = 8
MAX_LOOK_AT = 3
MAX_WORDS = 500

NOT_APPLICABLE_NONE = "This step is required: it has no not-applicable outcome."
BLOCKED_STANDING = "If you cannot do this now, add a note to the step naming what is needed and from whom."
SKIP_NONE_LEGAL = "Skip is not offered: this step is required by the law."

_PLACEHOLDER = re.compile(r"(?<![\w./-])[A-Z][A-Z0-9_]+(?![\w-])")
_TEXT_RULES = (
    (re.compile(r"@"), "an address or handle"),
    (re.compile(r"https?://|www\."), "a link"),
    (re.compile(r"(?<!\d)\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)"), "a phone number"),
    (re.compile(r"\$\s?\d"), "an amount"),
    (re.compile(r"§"), "a section sign"),
    (re.compile(r"\b[A-Z]{2,6}\s+\d{2,5}(?:\.\d+)?(?:\([a-z0-9]+\))*"), "a section number (the cite carries it)"),
)
_SHELF_KEY = re.compile(r"^[A-Z]{2,8} \d{1,5}(?:\.\d+)?[a-z]?(?:\([A-Za-z0-9]+\))*$")
_DOC_KEY = re.compile(r"^[A-Za-z0-9][\w.-]*#[\w.()-]+$")


def placeholders(text: str) -> list[str]:
    """The upper-case words in a command that stand for something to fill in, once each, in order."""
    return list(dict.fromkeys(_PLACEHOLDER.findall(text or "")))


def fill_command(text: str, *, name: str = "", run: str = "") -> tuple[str, list[str]]:
    """A command with ``NAME`` and ``RUN`` filled where known, and the placeholders still to fill in. A name with a space is quoted so
    the line copies as typed. ``KEY`` and ``ID`` are never filled."""
    left = []
    for word in placeholders(text):
        value = {"NAME": name, "RUN": run}.get(word, "")
        if value:
            shown = f'"{value}"' if re.search(r"\s", value) else value
            text = re.sub(rf"(?<![\w./-]){word}(?![\w-])", lambda _m, s=shown: s, text)
        else:
            left.append(word)
    return text, left


def kind_of_cite(key: str) -> str:
    """``shelf`` for a statute key (``CIV 9999(a)``), ``document`` for ``key#section``, ``""`` for neither."""
    key = (key or "").strip()
    if _SHELF_KEY.match(key):
        return "shelf"
    if _DOC_KEY.match(key):
        return "document"
    return ""


def text_problems(text: str, *, held: bool = False, public: bool = False) -> list[str]:
    """What is wrong with a sentence of guidance: too long, or carrying something that is not general. A held definition's words
    carry no ``@``, and a public title's no digit."""
    out = []
    text = text or ""
    if len(text) > MAX_WORDS:
        out.append(f"is {len(text)} characters; at most {MAX_WORDS}")
    for rule, what in _TEXT_RULES:
        if rule.search(text):
            out.append(f"carries {what}")
    if public and re.search(r"\d", text):
        out.append("carries a digit, and a step whose title is public names no matter")
    return out


# --- the validator for a Support --------------------------------------------------------------------------------------------------

def problems(sd: StepDef, wf: Workflow, *, resolve_law: Any = None, reads: Iterable[str] | None = None,
             lessons: Iterable[str] | None = None, integrations: Iterable[str] | None = None) -> list[tuple[str, str]]:
    """The (code, message) problems with a step's ``Support``; none for a step with none. A registry that is not given is not checked
    (the reads, the lessons, the integrations, the shelf), never guessed."""
    sup = sd.support
    out: list[tuple[str, str]] = []
    if sup is None:
        return out

    def bad(code: str, message: str) -> None:
        out.append((code, message))

    if not isinstance(sup, Support):
        return [("support", f"support is a Support record, not {type(sup).__name__}")]
    g, e, r = sup.guides, sup.enables, sup.reminds
    for name, value, kind in (("guides", g, Guides), ("enables", e, Enables), ("reminds", r, Reminds)):
        if not isinstance(value, kind):
            return [("support", f"support.{name} is a {kind.__name__}")]
    if not is_person_step(sd):
        bad("support", f"a {sd.kind.value} step has no person to guide: a Support belongs to a person or decision step, or a wait only a note ends")
    held = wf.visibility is Visibility.HELD
    public = bool(sd.public_title)

    def words(field_name: str, text: Any) -> None:
        if not isinstance(text, str):
            bad("support", f"{field_name} is text")
            return
        for why in text_problems(text, held=held, public=public):
            bad("support-text", f"{field_name} {why}")

    for field_name in ("instruction", "why", "done_when", "blocked", "not_applicable"):
        words(f"guides.{field_name}", getattr(g, field_name))
    words("enables.access_note", e.access_note)
    for i, text in enumerate(e.in_hand):
        words(f"enables.in_hand[{i}]", text)
    if len(g.look_at) > MAX_LOOK_AT:
        bad("support-look", f"at most {MAX_LOOK_AT} look-at reads (the panel is a place to act, not a report); {len(g.look_at)} given")
    known_reads = set(reads) if reads is not None else None
    for i, look in enumerate(g.look_at):
        if not isinstance(look, LookAt) or not look.label.strip() or not look.read.strip():
            bad("support-look", f"look_at[{i}] is a LookAt with a label and the name of a read")
            continue
        words(f"look_at[{i}].label", look.label)
        if known_reads is not None and look.read not in known_reads:
            bad("support-look", f"look_at[{i}] reads {look.read!r}, which is not a registered guide read")
    if len(g.checklist) > MAX_CHECKLIST:
        bad("support-check", f"at most {MAX_CHECKLIST} checklist items; {len(g.checklist)} given")
    for i, item in enumerate(g.checklist):
        if not isinstance(item, Check) or not item.text.strip():
            bad("support-check", f"checklist[{i}] is a Check with one line of text")
            continue
        words(f"checklist[{i}]", item.text)
    if any(isinstance(c, Check) and c.required for c in g.checklist) and not (sd.record or g.done_when):
        bad("support-check", "a required checklist item needs a record or a done_when: the attestation records what was checked")
    for i, cmd in enumerate(g.commands):
        if not isinstance(cmd, Cmd) or not cmd.text.strip():
            bad("support-command", f"commands[{i}] is a Cmd with the command's text")
            continue
        unknown = [w for w in placeholders(cmd.text) if w not in PLACEHOLDERS]
        if unknown:
            bad("support-command", f"commands[{i}] has the placeholder {', '.join(unknown)}; the known ones are {', '.join(PLACEHOLDERS)}")
        if held and "@" in cmd.text:
            bad("support-text", f"commands[{i}] carries an address, and a held definition's words carry none")
        words(f"commands[{i}].note", cmd.note)
    if lessons is not None:
        known = set(lessons)
        for key in g.lessons:
            if key not in known:
                bad("support-lesson", f"lesson {key!r} does not exist")
    if len(set(g.lessons)) != len(g.lessons):
        bad("support-lesson", "a lesson is named once")
    for i, cite in enumerate(g.cites):
        if not isinstance(cite, Cite):
            bad("support-cite", f"cites[{i}] is a Cite")
            continue
        kind = kind_of_cite(cite.key)
        if not kind:
            bad("support-cite", f"cites[{i}] {cite.key!r} is neither a shelf key (CIV 9999(a)) nor key#section")
        elif kind == "shelf" and resolve_law is not None and resolve_law(cite.key) is False:
            bad("support-cite", f"the section {cite.key} does not resolve on the authorities shelf")
        words(f"cites[{i}].reading", cite.reading)
    if len({c.key for c in g.cites if isinstance(c, Cite)}) != len(g.cites):
        bad("support-cite", "a cite is named once")
    for role in g.ask:
        if not isinstance(role, Role) or role not in OFFICES:
            bad("support-ask", f"ask names an office (never a person, jason, scheduler, or anyone): {role!r}")
    if e.integrations:
        known_ints = set(integrations) if integrations is not None else None
        for key in e.integrations:
            if known_ints is not None and key not in known_ints:
                bad("support-enable", f"integration {key!r} is not one jason knows")
    for name in ("second_person", "terminal"):
        if getattr(e, name) not in (None, True, False):
            bad("support-enable", f"enables.{name} is true, false, or left to derive")
    if sd.is_legal:
        if r.snoozable is True:
            bad("support-remind", "a legal step is never snoozable")
        if r.escalate_after_hours not in (None, 0):
            bad("support-remind", "a legal clock escalates the day it falls: escalate_after_hours is 0")
    for name in ("lead_days", "after_hours", "escalate_after_hours"):
        value = getattr(r, name)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            bad("support-remind", f"reminds.{name} is a whole number of at least 0")
    if r.escalate_to is not None and (not isinstance(r.escalate_to, Role) or r.escalate_to not in OFFICES):
        bad("support-remind", f"escalate_to is an office (jason, scheduler, and anyone are not offices): {r.escalate_to!r}")
    if r.per_item and sd.repeat.value == "once":
        bad("support-remind", "per_item is for a step that repeats per item")
    return out


# --- the derived guide ----------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class GuideSpec:
    """A step's guidance as the definition gives it, with every empty field filled from what the step already holds. ``authored`` lists
    (in the screen's order) the parts a person wrote, so the definition page can show the gap."""

    instruction: str
    why: str
    look_at: tuple[LookAt, ...]
    evidence: tuple[str, ...]
    checklist: tuple[Check, ...]
    commands: tuple[Cmd, ...]
    lessons: tuple[str, ...]
    cites: tuple[Cite, ...]
    done_when: str
    record: str
    blocked: str
    not_applicable: str
    na_declared: bool
    skippable: bool
    ask: tuple[Role, ...]
    in_hand: tuple[str, ...]
    access_note: str
    integrations: tuple[str, ...]
    second_person: bool
    terminal: bool
    sop: str
    sop_key: str
    sop_index: int
    authored: tuple[str, ...] = field(default_factory=tuple)

    @property
    def required_checks(self) -> int:
        return sum(1 for c in self.checklist if c.required)


def authored(sd: StepDef) -> tuple[str, ...]:
    """The parts of a step's guidance a person wrote, in the screen's order, as plain words ("instruction", "rule", "checklist",
    "look-at", ...). Empty for a step with no ``Support``."""
    sup = sd.support
    if sup is None:
        return ()
    g, e, r = sup.guides, sup.enables, sup.reminds
    parts = (("instruction", bool(g.instruction)), ("rule", bool(g.cites)), ("checklist", bool(g.checklist)), ("look-at", bool(g.look_at)),
             ("commands", bool(g.commands)), ("done-when", bool(g.done_when)), ("blocked", bool(g.blocked)),
             ("not-applicable", bool(g.not_applicable)), ("ask", bool(g.ask)), ("lessons", bool(g.lessons)),
             ("enables", e != type(e)()), ("reminds", r != type(r)()))
    return tuple(name for name, present in parts if present)


def spec(sd: StepDef, procedure: Any = None) -> GuideSpec:
    """The guidance for a step, authored or derived. ``procedure`` is the ``Procedure`` the workflow was built over (the caller finds it;
    this module reads no registry), used for the procedure step's ``do``, ``check``, and ``lessons`` when the step names its ``sop``."""
    sup = sd.support
    g = sup.guides if sup is not None else None
    e = sup.enables if sup is not None else None
    parsed = parse_sop(sd.sop) if sd.sop else None
    key, index = parsed if parsed else ("", 0)
    pstep = None
    steps = getattr(procedure, "steps", None)
    if steps is not None and index and 1 <= index <= len(steps):
        pstep = steps[index - 1]
    instruction = (g.instruction if g and g.instruction else (getattr(pstep, "do", "") or sd.title))
    checklist = tuple(g.checklist) if g and g.checklist else ((Check(pstep.check),) if getattr(pstep, "check", "") else ())
    if g and g.commands:
        commands = tuple(g.commands)
    else:
        commands = (Cmd(sd.command),) if sd.command else ()
    lessons = tuple(g.lessons) if g and g.lessons else tuple(getattr(pstep, "lessons", ()) or ())
    if g and g.cites:
        cites = tuple(g.cites)
    elif sd.clock is not None and sd.clock.basis is ClockBasis.LAW and sd.clock.cite:
        cites = (Cite(sd.clock.cite),)
    else:
        cites = ()
    done_when = g.done_when if g and g.done_when else (f"Done when you can point to: {sd.record}." if sd.record else "")
    na_declared = sd.na is not None
    skippable = sd.skip is not None and not sd.is_legal
    if g and g.not_applicable:
        not_applicable = g.not_applicable
    elif na_declared:
        who = " or ".join(r.value for r in (sd.na.roles or sd.acting_roles))
        not_applicable = f"The {who} may record this step as not applicable, with a reason and the record that shows it."
    elif skippable:
        not_applicable = "This step has no not-applicable outcome; it may be skipped with a reason."
    else:
        not_applicable = NOT_APPLICABLE_NONE
    asks = tuple(g.ask) if g and g.ask else tuple(dict.fromkeys(r for r in sd.acting_roles if r in OFFICES))
    if not (g and g.ask):
        row = ESCALATION.get(sd.role.value)
        if row is not None and row not in asks:
            asks = asks + (row,)
    terminal = e.terminal if e is not None and e.terminal is not None else (bool(commands) and all(c.terminal_only for c in commands))
    return GuideSpec(
        instruction=instruction, why=(g.why if g and g.why else sd.why),
        look_at=tuple(g.look_at) if g else (), evidence=tuple(sd.evidence), checklist=checklist, commands=commands, lessons=lessons,
        cites=cites, done_when=done_when, record=sd.record, blocked=(g.blocked if g and g.blocked else BLOCKED_STANDING),
        not_applicable=not_applicable, na_declared=na_declared, skippable=skippable, ask=asks,
        in_hand=tuple(e.in_hand) if e else (), access_note=(e.access_note if e else ""), integrations=tuple(e.integrations) if e else (),
        second_person=bool(e.second_person) if e is not None else False, terminal=terminal,
        sop=sd.sop, sop_key=key, sop_index=index, authored=authored(sd))


def _fields(kind: type) -> set[str]:
    import dataclasses

    return {f.name for f in dataclasses.fields(kind)}


def _only(row: Any, kind: type, where: str) -> dict[str, Any]:
    """A mapping whose keys are all fields of ``kind``; an unknown key is refused by name (a typo never drops guidance silently)."""
    if not isinstance(row, dict):
        raise ValueError(f"{where} is an object")
    unknown = sorted(set(row) - _fields(kind))
    if unknown:
        raise ValueError(f"{where} has no field {', '.join(unknown)} (the fields are {', '.join(sorted(_fields(kind)))})")
    return dict(row)


def from_mapping(data: Any) -> Support:
    """A ``Support`` from JSON-like data (a stored word turns into its symbol before a task sees it): roles by their words, lists as
    tuples. An unknown field anywhere is refused by name, and so is a role that is not a ``Role``."""
    from jason.workflows.types import Check as _Check, Cmd as _Cmd

    top = _only(data, Support, "support")
    g = _only(top.get("guides", {}), Guides, "support.guides")
    e = _only(top.get("enables", {}), Enables, "support.enables")
    r = _only(top.get("reminds", {}), Reminds, "support.reminds")

    def roles(values: Any, where: str) -> tuple[Role, ...]:
        out = []
        for v in values or ():
            role = Role.parse(v)
            if role is None:
                raise ValueError(f"{where}: {v!r} is not a role")
            out.append(role)
        return tuple(out)

    def rows(values: Any, kind: type, where: str) -> tuple[Any, ...]:
        return tuple(kind(**_only(v, kind, f"{where}[{i}]")) if not isinstance(v, kind) else v for i, v in enumerate(values or ()))

    guides = Guides(**{**g, "look_at": rows(g.get("look_at"), LookAt, "look_at"), "checklist": rows(g.get("checklist"), _Check, "checklist"),
                       "commands": rows(g.get("commands"), _Cmd, "commands"), "cites": rows(g.get("cites"), Cite, "cites"),
                       "lessons": tuple(g.get("lessons") or ()), "ask": roles(g.get("ask"), "ask")})
    enables = Enables(**{**e, "in_hand": tuple(e.get("in_hand") or ()), "integrations": tuple(e.get("integrations") or ())})
    esc = r.get("escalate_to")
    reminds = Reminds(**{**r, "escalate_to": None if esc in (None, "") else roles([esc], "escalate_to")[0]})
    return Support(enables=enables, reminds=reminds, guides=guides)


def coverage_words(sd: StepDef) -> str:
    """The guidance a person wrote for a step, in words for the definition page ("instruction, rule, checklist, look-at"); "derived"
    when it has none (the panel then shows the minimum it can derive)."""
    got = authored(sd)
    return ", ".join(got) if got else "derived"


__all__ = ["BLOCKED_STANDING", "GuideSpec", "MAX_CHECKLIST", "MAX_LOOK_AT", "NOT_APPLICABLE_NONE", "PLACEHOLDERS", "SKIP_NONE_LEGAL",
           "authored", "coverage_words", "fill_command", "from_mapping", "kind_of_cite", "placeholders", "problems", "spec", "text_problems"]
