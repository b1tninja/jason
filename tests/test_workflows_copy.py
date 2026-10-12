"""The words a workflow definition shows people carry no internals: no constant name, no snake_case identifier, no class name, and a
role word that is an engine's own name ("jason") takes no article. Built from the definitions themselves (every general family),
nothing registered.
"""

from __future__ import annotations

import dataclasses
import enum
import re
from datetime import date

import pytest

from jason.workflows import fold
from jason.workflows.defs import all_builders
from jason.workflows.definitions_general import GENERAL
from jason.workflows.types import (
    ClockBasis, ClockDef, DateSlot, Elapsed, Event, EventKind, Role, StepDef, StepKind, StepState, Workflow, role_words,
)

HUMAN = frozenset({"title", "why", "record", "label", "held_title", "text", "in_hand", "access_note", "instruction", "note",
                   "done_when", "blocked", "not_applicable", "reading"})
"""The fields of a definition a person reads (a step's title, why, and record; a clock's or a date's label; the guide's words). The
others (ids, commands, slot names, check names, evidence addresses, choice keys) are for the machine or a terminal."""
CAPS = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
SNAKE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
CAMEL = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")


def definitions() -> list[Workflow]:
    return [build() for build in (*GENERAL, *all_builders())]


def human_strings(obj, path: str, out: list[tuple[str, str]], field: str = "") -> None:
    if isinstance(obj, str):
        if field in HUMAN:
            out.append((path, obj))
    elif isinstance(obj, enum.Enum):
        return
    elif dataclasses.is_dataclass(obj):
        for f in dataclasses.fields(obj):
            human_strings(getattr(obj, f.name), f"{path}.{f.name}", out, f.name)
    elif isinstance(obj, (list, tuple)):
        for i, x in enumerate(obj):
            human_strings(x, f"{path}[{i}]", out, field)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            human_strings(v, f"{path}[{k}]", out, field)


def internals(wf: Workflow) -> list[str]:
    """Every identifier-looking word in a human field of the definition. A choice key a step's own text names (it is the button's
    word) is let through."""
    found = []
    for sd in wf.steps:
        keys = {c.key for c in sd.choices}
        strings: list[tuple[str, str]] = []
        human_strings(sd, f"{wf.key}.{sd.id}", strings)
        for path, text in strings:
            for rx in (CAPS, SNAKE, CAMEL):
                found += [f"{path}: {word}" for word in rx.findall(text) if word not in keys]
    strings = []
    human_strings(dataclasses.replace(wf, steps=()), wf.key, strings)
    for path, text in strings:
        for rx in (CAPS, SNAKE, CAMEL):
            found += [f"{path}: {word}" for word in rx.findall(text)]
    return found


def test_the_definitions_are_all_built():
    assert len(definitions()) > 40                       # a scan of nothing proves nothing


def test_no_title_label_why_or_record_names_a_constant_a_snake_case_internal_or_a_class():
    bad = [line for wf in definitions() for line in internals(wf)]
    assert bad == [], "internals shown to people:\n" + "\n".join(bad)


def test_the_scan_sees_what_it_is_meant_to():
    probe = ClockDef(ClockBasis.PROPOSED_POLICY, "term_end", -90, label="90 days before the term end: WINDOW_DAYS")
    wf = Workflow("p", "P", "f", "unit", steps=(StepDef("p.1", "Do it", StepKind.PERSON, role=Role.MANAGER, clock=probe,
                                                         why="Standing words are CollectionStanding: OWED_NO_LIEN; max_age_hours"),),
                  dates=(DateSlot("term_end"),))
    got = internals(wf)
    assert any("WINDOW_DAYS" in g for g in got) and any("CollectionStanding" in g for g in got)
    assert any("OWED_NO_LIEN" in g for g in got) and any("max_age_hours" in g for g in got)


def test_the_insurance_renewal_clock_says_its_window_in_words():
    wf = next(w for w in definitions() if w.key == "insurance-renewal")
    clock = next(sd.clock for sd in wf.steps if sd.clock is not None and "term ends" in sd.clock.label)
    assert clock.label == ("90 days before the term ends; the association's schedule may set its own "
                           "(proposed policy, not adopted by the board)")
    assert "WINDOW_DAYS" not in clock.label


@pytest.mark.parametrize("role,words", [(Role.JASON, "jason"), (Role.SCHEDULER, "scheduler"), (Role.ANYONE, "anyone"),
                                        (Role.MANAGER, "the manager"), (Role.VICE_PRESIDENT, "the vice president"),
                                        ("treasurer", "the treasurer"), ("jason", "jason")])
def test_the_engines_own_names_take_no_article(role, words):
    assert role_words(role) == words


def test_a_wait_that_jason_records_does_not_read_for_the_jason():
    sd = StepDef("w.1", "Wait for the example arrival", StepKind.WAIT, role=Role.JASON, ends_by_note=True, elapsed=Elapsed.ENDS)
    wf = Workflow("w", "W", "f", "unit", steps=(sd,))
    opened = Event(n=1, kind=EventKind.OPENED, by="A. Manager", at="2099-01-01T09:00:00Z", detail={"definition": "w", "subject": "s", "label": "L"})
    view = fold.state([opened], wf, date(2099, 1, 2))
    waiting = view.step("w.1")
    assert waiting.state is StepState.WAITING and "for jason to record a note" in waiting.reason and "the jason" not in waiting.reason
