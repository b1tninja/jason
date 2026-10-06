"""Resolve a community's forms: the library's definitions for its jurisdictions, with its slots, adjustments, and
bindings applied, then its own forms (docs/form-library-design.md, "How a profile uses the library").

``resolve(community)`` asks the community five questions, each with an empty default: ``jurisdictions()`` (the chain,
most general first), ``form_slots()``, ``form_adjustments()`` (``Adjust`` and ``Add`` rows), ``form_bindings()`` (``Bind``
rows), and ``custom_forms()``. It returns a ``Resolved``: one ``ResolvedForm`` for each form, with its tier, what was
adjusted, what was refused, and its status:

- **ready**: the library's form with the community's slots in it;
- **adjusted**: the same with adjustments applied (each recorded);
- **not offered**: a slot is not given, or a family form's binding is incomplete. The form is not made, and the missing
  piece is named;
- **failing**: the form cannot be made (no handler, or one that is not registered). It is not made either.

An adjustment the check refuses is left out and recorded: the form keeps the law's words. Whether the form is also
*failing* in the report's sense (a required item not carried, a recital that does not resolve) is the check's to say
(``check.check``); it does not stop ``forms()``, so a machine whose shelf lacks a statute still makes the forms it did.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from jason.community.forms import FormTemplate
from jason.community.form_library import handlers as handler_table
from jason.community.form_library.tiers import (
    LIBRARY,
    Add,
    Bind,
    Channel,
    Check,
    Clock,
    Finding,
    FormDefinition,
    Library,
    Required,
    SetBy,
    Severity,
    Status,
    Tier,
    TOKEN,
)


@dataclass(frozen=True)
class ResolvedForm:
    """One form as this community has it."""

    definition: FormDefinition
    template: FormTemplate
    status: Status
    clocks: tuple[Clock, ...] = ()                       # the governing clocks: the definition's, then the community's
    channels: tuple[Channel, ...] = ()
    required_content: tuple[Required, ...] = ()
    forbidden: tuple[str, ...] = ()                      # question fields a binding bars
    binding: Bind | None = None
    slot_values: tuple[tuple[str, str], ...] = ()
    missing: tuple[str, ...] = ()                        # why it is not offered: "slot RETURN_BY_MAIL", "binding: section"
    applied: tuple[str, ...] = ()                        # what the community's adjustments changed, in words
    refused: tuple[Finding, ...] = ()                    # adjustments the library will not apply
    handler_problems: tuple[str, ...] = ()
    member_clock: str = ""
    acknowledgment: str = ""

    @property
    def key(self) -> str:
        return self.definition.key

    @property
    def tier(self) -> Tier:
        return self.definition.tier

    @property
    def offered(self) -> bool:
        return self.status in (Status.READY, Status.ADJUSTED)


@dataclass(frozen=True)
class Resolved:
    """A community's forms, and the problems found while resolving them (an unknown jurisdiction, a key two forms share)."""

    chain: tuple[str, ...]
    forms: tuple[ResolvedForm, ...]
    problems: tuple[Finding, ...] = ()

    def templates(self) -> tuple[FormTemplate, ...]:
        """The templates of the forms this community offers, as ``Community.forms()`` returns them."""
        return tuple(f.template for f in self.forms if f.offered)

    def get(self, key: str) -> ResolvedForm | None:
        """A form by the library's key (``records-request``) or by its template's (``records``)."""
        return next((f for f in self.forms if f.key == key), None) or next(
            (f for f in self.forms if f.template.key.value == key), None)

    def by_tier(self, tier: Tier) -> tuple[ResolvedForm, ...]:
        return tuple(f for f in self.forms if f.tier is tier)


def fill_slots(text: str, values: Mapping[str, str]) -> str:
    """``{SLOT}`` replaced by its value, for the slots given; any other ``{TOKEN}`` (a per-send value) is left."""
    return TOKEN.sub(lambda m: values[m.group(1)] if m.group(1) in values else m.group(0), text or "")


def _fill_template(template: FormTemplate, values: Mapping[str, str]) -> FormTemplate:
    if not values:
        return template
    questions = tuple(replace(q, help=fill_slots(q.help, values)) if q.help else q for q in template.questions)
    return replace(template, description=fill_slots(template.description, values),
                   preamble=tuple(fill_slots(p, values) for p in template.preamble),
                   attestation=fill_slots(template.attestation, values), questions=questions)


def _refusal(form: str, item: str, message: str) -> Finding:
    return Finding(form, Check.ADJUSTMENTS, Severity.FAIL, item, message)


def apply_clock(form: str, clocks: tuple[Clock, ...], new: Clock, floor: tuple[Clock, ...] | None = None
                ) -> tuple[tuple[Clock, ...], str, Finding | None]:
    """One community clock put among the form's: (the clocks, what was done in words, a refusal). A profile cannot set a
    statutory clock; a clock the documents set names its section; a clock that takes the place of a statutory one must be
    shown to run no longer (``Clock.no_longer_than``) than the statute's, which is the ``floor`` (the definition's own
    clocks) however many times the clock has been replaced; one that replaces a policy clock may be anything."""
    item = f"clock {new.name}"
    if new.set_by is SetBy.STATUTE:
        return clocks, "", _refusal(form, item, "a community cannot set a statutory clock; the statute does")
    if new.set_by is SetBy.DOCUMENTS and not new.section.strip():
        return clocks, "", _refusal(form, item, "a clock the documents set names the section it rests on")
    statute = next((c for c in (clocks if floor is None else floor) if c.name == new.name and c.set_by is SetBy.STATUTE), None)
    if statute is not None and not new.no_longer_than(statute):
        return clocks, "", _refusal(form, item, f"{new.words()} is not shown to run no longer than the statute's "
                                                f"({statute.words()}): a statutory clock is never lengthened")
    base = next((c for c in clocks if c.name == new.name), None)
    if base is None:
        return (*clocks, new), f"clock added: {new.words()}", None
    stricter = statute is not None and (new.number, new.kind) != (statute.number, statute.kind)
    held = replace(new, note=f"stricter than {statute.words()}") if stricter else new
    verb = "stricter clock governs" if stricter else "clock replaced"
    return tuple(held if c.name == new.name else c for c in clocks), f"{verb}: {held.words()} (was {base.words()})", None


def _carriers(required: tuple[Required, ...], field: str) -> list[str]:
    return [r.item for r in required if field in r.carried_by]


def _apply_change(defn: FormDefinition, change: Any, template: FormTemplate, clocks: tuple[Clock, ...],
                  channels: tuple[Channel, ...], required: tuple[Required, ...], forbidden: tuple[str, ...]
                  ) -> tuple[FormTemplate, tuple[Clock, ...], tuple[Channel, ...], list[str], list[Finding]]:
    done: list[str] = []
    refused: list[Finding] = []
    form = defn.key
    if isinstance(change, Add):
        q = change.question
        have = [x.field for x in template.questions]
        if q.field in forbidden:
            refused.append(_refusal(form, f"question {q.field}", "a binding forbids this question"))
        elif q.field in have:
            refused.append(_refusal(form, f"question {q.field}", "the form already has a question with this field"))
        elif change.after and change.after not in have:
            refused.append(_refusal(form, f"question {q.field}", f"there is no question {change.after!r} to put it after"))
        else:
            at = have.index(change.after) + 1 if change.after else len(have)
            template = replace(template, questions=(*template.questions[:at], q, *template.questions[at:]))
            done.append(f"question added: {q.field} ({q.title})")
        return template, clocks, channels, done, refused
    for field in change.remove:
        why = _carriers(required, field)
        refused.append(_refusal(form, f"question {field}", "an adjustment never removes a question the library's form carries"
                                + (f" (it carries: {'; '.join(why)})" if why else "")))
    for field, _title in change.reword:
        why = _carriers(required, field)
        refused.append(_refusal(form, f"question {field}", "an adjustment never rewords a question the library's form carries"
                                + (f" (it carries: {'; '.join(why)})" if why else "")))
    for recital in change.drop_recitals:
        refused.append(_refusal(form, f"recital {recital}", "an adjustment never drops a recital"))
    for clock in change.clocks:
        clocks, note, refusal = apply_clock(form, clocks, clock, defn.association_clocks)
        if refusal:
            refused.append(refusal)
        else:
            done.append(note)
    if change.preamble:
        template = replace(template, preamble=(*template.preamble, *change.preamble))
        done.append(f"{len(change.preamble)} preamble paragraph(s) added")
    if change.channels is not None:
        channels = tuple(change.channels)
        done.append("channels set: " + ", ".join(c.value for c in channels))
    if change.code:
        if template.code and template.code != change.code:
            refused.append(_refusal(form, "marker code", f"the form's code is {template.code}: copies already sent carry it"))
        elif template.code != change.code:
            template = replace(template, code=change.code)
            done.append(f"marker code set: {change.code}")
    return template, clocks, channels, done, refused


def _make(defn: FormDefinition, given: Mapping[str, str], changes: tuple[Any, ...], bind: Bind | None,
          community: Any) -> ResolvedForm:
    values = {name: given[name] for name in defn.slots if name in given}
    missing = [f"slot {name}" for name in defn.slots if name not in given]
    if defn.tier is Tier.FAMILY:
        gaps = (bind or Bind(defn.key)).missing(defn.bindable)
        missing += [f"binding: {gap}" for gap in gaps]
    template = _fill_template(defn.template, values)
    clocks, channels = defn.association_clocks, defn.channels
    required = defn.required_content + (bind.required if bind else ())
    forbidden = bind.forbidden if bind else ()
    applied: list[str] = []
    refused: list[Finding] = []
    if bind is not None:
        for clock in bind.clocks:
            clocks, note, refusal = apply_clock(defn.key, clocks, clock, defn.association_clocks)
            if refusal:
                refused.append(refusal)
                if clock.name in defn.bindable:
                    missing.append(f"binding: clock {clock.name} (refused)")
            else:
                applied.append(f"binding {note}")
        if forbidden:
            applied.append("forbidden by the binding: " + ", ".join(forbidden))
        if bind.section:
            applied.append(f"bound to {bind.section}" + (f", decided by {bind.decider}" if bind.decider else ""))
    for change in changes:
        template, clocks, channels, done, bad = _apply_change(defn, change, template, clocks, channels, required, forbidden)
        applied += done
        refused += bad
    problems = tuple(handler_table.problems(defn, community))
    if missing:
        status = Status.NOT_OFFERED
    elif problems:
        status = Status.FAILING
    else:
        status = Status.ADJUSTED if applied else Status.READY
    return ResolvedForm(defn, template, status, clocks, channels, required, forbidden, bind, tuple(sorted(values.items())),
                        tuple(dict.fromkeys(missing)), tuple(applied), tuple(refused), problems,
                        fill_slots(defn.member_clock, values), fill_slots(defn.acknowledgment, values))


def resolve(community: Any, library: Library | None = None) -> Resolved:
    """The community's forms: see the module's docstring. Reads nothing from disk; a profile's answers are in memory."""
    lib = library or LIBRARY
    chain = tuple(str(k) for k in (getattr(community, "jurisdictions", lambda: ("US", "CA"))() or ()))
    given = {s.name: s.value for s in (getattr(community, "form_slots", lambda: ())() or ()) if str(s.value).strip()}
    changes = tuple(getattr(community, "form_adjustments", lambda: ())() or ())
    binds: dict[str, Bind] = {}
    problems: list[Finding] = []
    for b in getattr(community, "form_bindings", lambda: ())() or ():
        if b.form in binds:
            problems.append(Finding(b.form, Check.LIBRARY, Severity.FAIL, "binding", "bound twice; the first stands"))
        else:
            binds[b.form] = b

    chosen: dict[str, FormDefinition] = {}
    for key in chain:
        if not lib.known(key):
            problems.append(Finding("", Check.LIBRARY, Severity.FAIL, f"jurisdiction {key}",
                                    "the library holds no forms for it (a jurisdiction is a pack: jason.community.form_library.<key>)"))
            continue
        for d in lib.definitions(key):
            chosen[d.key] = d                           # a later, more specific jurisdiction's form replaces an earlier one's

    for item in getattr(community, "custom_forms", lambda: ())() or ():
        d = item if isinstance(item, FormDefinition) else FormDefinition(template=item, tier=Tier.CUSTOM)
        if d.tier is not Tier.CUSTOM:
            problems.append(Finding(d.key, Check.LIBRARY, Severity.FAIL, "tier", f"a community's own form is custom, not {d.tier.value}"))
        elif d.key in chosen:
            problems.append(Finding(d.key, Check.LIBRARY, Severity.FAIL, "key",
                                    "a library form already has this key; the library's form stands, so a custom form takes another"))
        else:
            chosen[d.key] = d

    for name in sorted({c.form for c in changes} - set(chosen)):
        problems.append(Finding(name, Check.ADJUSTMENTS, Severity.FAIL, "adjustment", "names a form this community does not have"))
    for name in sorted(set(binds) - set(chosen)):
        problems.append(Finding(name, Check.ADJUSTMENTS, Severity.FAIL, "binding", "names a form this community does not have"))

    forms = tuple(_make(d, given, tuple(c for c in changes if c.form == d.key), binds.get(d.key), community)
                  for d in chosen.values())
    by_template: dict[str, list[str]] = {}
    for f in forms:
        by_template.setdefault(f.template.key.value, []).append(f.key)
    for form_key, keys in by_template.items():
        if len(keys) > 1:
            problems.append(Finding("", Check.LIBRARY, Severity.FAIL, f"template key {form_key}",
                                    f"{', '.join(keys)} share one FormKey: a return could not tell them apart"))
    return Resolved(chain, forms, tuple(problems))


__all__ = ["Resolved", "ResolvedForm", "apply_clock", "fill_slots", "resolve"]
