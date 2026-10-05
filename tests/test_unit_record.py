"""The unit record and the loss packet, over made-up data: no association's names appear here."""

import dataclasses
import json
import subprocess
import sys
from enum import Enum

from jason.community import Community
from jason.community.loss_packet import LadderStep, OpenQuestion, StepRecord, assemble
from jason.community.unit_record import (
    ComponentKind as K,
    ComponentStatus as S,
    CoverageReading,
    ImprovementEntry,
    OriginalSpec,
    Points,
    UnitCoverage,
    coverage,
    effective,
)

BANNED = ("covered", "not covered", "at fault", "your responsibility")

UC = UnitCoverage(
    declaration_kinds=(K.FLOORING, K.CABINETS),
    policy_kinds=(K.CABINETS, K.APPLIANCE),
    declaration_cite=("doc#1.1",),
    policy_cite=("pol#A",),
    differs_question="q-differ",
    builder_question="q-builder",
)

SPECS = (
    OriginalSpec("Plan A", "Kitchen flooring", K.FLOORING, "Vinyl plank", "drive:abc"),
    OriginalSpec("Plan A", "Kitchen cabinets", K.CABINETS, "Maple", "drive:abc"),
)


def entry(id, component, what, status=S.UPGRADE, date="2024-01-01", replaces="", **kw):
    return ImprovementEntry(id=id, unit="u1", component=component, kind=kw.pop("kind", K.FLOORING), what=what,
                            status=status, date=date, replaces=replaces, **kw)


def _strings(value, skip=("recited", "words")):
    if isinstance(value, Enum):
        yield value.value
    elif dataclasses.is_dataclass(value):
        for f in dataclasses.fields(value):
            if f.name not in skip:
                yield from _strings(getattr(value, f.name), skip)
    elif isinstance(value, dict):
        for k, v in value.items():
            if k not in skip:
                yield from _strings(v, skip)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _strings(v, skip)
    elif isinstance(value, str):
        yield value


def _guard(value):
    text = " ".join(_strings(value)).lower()
    for word in BANNED:
        assert word not in text, word


def test_effective_default_is_original():
    rows = effective("Plan A", SPECS, ())
    assert [r.status for r in rows] == [S.ORIGINAL, S.ORIGINAL]
    assert rows[0].value == "Vinyl plank" and rows[0].sources == ("drive:abc",)


def test_effective_newest_replacement_wins_and_other_plan_ignored():
    entries = (
        entry("1", "Kitchen flooring", "Tile", S.EQUIVALENT_REPLACEMENT, "2020-01-01"),
        entry("2", "Kitchen flooring", "Hardwood", S.UPGRADE, "2023-05-01"),
    )
    rows = effective("Plan A", SPECS, entries)
    floor = next(r for r in rows if r.component == "Kitchen flooring")
    assert (floor.value, floor.status) == ("Hardwood", S.UPGRADE)
    assert [e.id for e in floor.entries] == ["1", "2"]
    assert effective("Plan B", SPECS, ())[0:0] == ()


def test_effective_replaces_names_the_component_and_unmatched_is_added():
    entries = (
        entry("1", "Living room floor", "Bamboo", replaces="Kitchen flooring"),
        entry("2", "Patio heater", "Heater", S.PERSONAL_PROPERTY, kind=K.OTHER),
    )
    rows = effective("Plan A", SPECS, entries)
    assert {r.component: r.status for r in rows} == {
        "Kitchen flooring": S.UPGRADE,
        "Kitchen cabinets": S.ORIGINAL,
        "Patio heater": S.PERSONAL_PROPERTY,
    }


def test_effective_builder_option_keeps_its_status():
    rows = effective("Plan A", SPECS, (entry("1", "Kitchen cabinets", "Cherry", S.BUILDER_OPTION, kind=K.CABINETS),))
    assert next(r for r in rows if r.component == "Kitchen cabinets").status is S.BUILDER_OPTION


def test_no_specification_yields_no_original_rows():
    assert effective("Plan Z", SPECS, ()) == ()
    rows = effective("Plan Z", (), (entry("1", "Kitchen flooring", "Tile", S.EQUIVALENT_REPLACEMENT),))
    assert [r.status for r in rows] == [S.UNKNOWN]
    assert not any(r.status is S.ORIGINAL for r in effective("Plan Z", (), ()))


def test_coverage_original_and_equivalent_against_both_lists():
    for status in (S.ORIGINAL, S.EQUIVALENT_REPLACEMENT):
        decl, pol = coverage(K.CABINETS, status, UC)
        assert (decl.points, pol.points) == (Points.MASTER_POLICY, Points.MASTER_POLICY)
        assert decl.differs == pol.differs == ""
        assert decl.words_cites == ("doc#1.1",) and pol.words_cites == ("pol#A",)
        decl, pol = coverage(K.FLOORING, status, UC)
        assert (decl.points, pol.points) == (Points.MASTER_POLICY, Points.NOT_STATED)
        assert decl.differs == pol.differs == "q-differ"
        decl, pol = coverage(K.APPLIANCE, status, UC)
        assert (decl.points, pol.points) == (Points.NOT_STATED, Points.MASTER_POLICY)
        decl, pol = coverage(K.WINDOWS, status, UC)
        assert (decl.points, pol.points) == (Points.NOT_STATED, Points.NOT_STATED)
        assert decl.differs == ""


def test_coverage_owner_policy_and_ask():
    for status in (S.UPGRADE, S.PERSONAL_PROPERTY):
        assert coverage(K.CABINETS, status, UC) == (CoverageReading(Points.OWNERS_POLICY),) * 2
    for status in (S.BUILDER_OPTION, S.UNKNOWN):
        decl, pol = coverage(K.CABINETS, status, UC)
        assert decl.points is pol.points is Points.ASK_A_PERSON
    assert coverage(K.CABINETS, S.BUILDER_OPTION, UC)[0].differs == "q-builder"
    assert coverage(K.CABINETS, S.UNKNOWN, UC)[0].differs == ""


def test_coverage_with_no_lists_asks_a_person():
    decl, pol = coverage(K.CABINETS, S.ORIGINAL, None)
    assert decl.points is pol.points is Points.ASK_A_PERSON


LADDER = (
    LadderStep(1, "What is the item?", ("doc#1",), ("q1",)),
    LadderStep(2, "Where did the cause originate?", ("doc#2",)),
    LadderStep(3, "Is it an insured casualty above the deductible?", ("doc#3",)),
    LadderStep(4, "Whose negligence, and of what degree?", ("doc#4",)),
    LadderStep(5, "Who pays the deductible?", ("doc#5",), ("q2",)),
)
RECITED = {f"doc#{i}": f"words {i}, covered by nobody, at fault" for i in range(1, 6)}
QUESTIONS = (OpenQuestion("q1", "A question"), OpenQuestion("q2", "Another"), OpenQuestion("q3", "Unrelated"))


def test_assemble_confirmed_and_unconfirmed_steps():
    record = {1: StepRecord(("a photo",), "Pat", "2026-01-02")}
    packet = assemble("u1", "i1", record, LADDER, {"policy": 1}, ("a leak in 2022",), object(), recited=RECITED,
                      questions=QUESTIONS)
    assert [s.state for s in packet.steps] == ["confirmed"] + ["unconfirmed"] * 4
    assert packet.steps[0].confirmed_by == "Pat" and packet.steps[0].recited == ("words 1, covered by nobody, at fault",)
    assert not packet.confirmed and "Unconfirmed" in packet.note
    assert packet.steps[4].held == ""
    assert [q.key for q in packet.open_questions] == ["q1", "q2"]
    assert packet.history == ("a leak in 2022",)


def test_assemble_all_confirmed():
    record = {i: StepRecord((), "Pat", "2026-01-02") for i in range(1, 6)}
    packet = assemble("u1", "i1", record, LADDER, {"p": 1}, (), object(), recited=RECITED)
    assert packet.confirmed and packet.note == ""


def test_assemble_missing_provision_guideline_and_policy_become_held_notes():
    recited = dict(RECITED)
    del recited["doc#2"]
    packet = assemble("u1", "i1", None, LADDER, None, (), None, recited=recited)
    assert "doc#2" in packet.steps[1].held and packet.steps[1].recited == ()
    assert "No policy" in packet.steps[2].held
    assert "deductible guideline" in packet.steps[4].held
    assert packet.steps[0].held == ""
    assert all(s.state == "unconfirmed" for s in packet.steps)


def test_assemble_step_with_no_provisions_is_held():
    packet = assemble("u1", "i1", None, (LadderStep(1, "What is the item?"),), None)
    assert packet.steps[0].held


def test_wording_guard():
    record = {1: StepRecord(("a photo",), "Pat", "2026-01-02")}
    packet = assemble("u1", "i1", record, LADDER, None, ("a leak",), None, recited=RECITED, questions=QUESTIONS)
    _guard(packet)
    for kind in K:
        for status in S:
            _guard(coverage(kind, status, UC))
            _guard(coverage(kind, status, None))
    _guard(effective("Plan A", SPECS, (entry("1", "Kitchen flooring", "Tile"),)))
    # the guard is live: recited words are the one place such words may sit
    assert "covered" in " ".join(_strings(packet, skip=())).lower()


def test_community_defaults_are_empty():
    probe = object()
    assert Community.facts(probe) == ()
    assert Community.original_specs(probe) == ()
    assert Community.unit_coverage(probe) is None
    assert Community.loss_ladder(probe) == ()
    assert Community.open_questions(probe) == ()
    assert Community.deductible_policy(probe) is None
    assert Community.interior_reports(probe) == ()


def test_importing_jason_loads_no_profile():
    code = (
        "import sys, jason.community.facts, jason.community.unit_record, jason.community.loss_packet\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('mystique', 'jason_mystique')]\n"
        "print(json.dumps(bad))"
    )
    out = subprocess.run([sys.executable, "-c", "import json\n" + code], capture_output=True, text=True, check=True)
    assert json.loads(out.stdout) == []
