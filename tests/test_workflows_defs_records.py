"""The records family of workflow definitions (src/jason/workflows/defs/records.py), against the family page's tables
(docs/workflows/documents-records.md, section 2). The expected steps are written out here, not parsed from the page: for each
step its page kind, the kind it is built as, its role, and what it needs. A step is built as another kind only when the read,
job, or approvals kind the page names does not exist yet. Everything is made up ("A. Manager", 2099).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from jason.workflows import api, definitions
from jason.workflows import definitions_general as general
from jason.workflows.defs import records
from jason.workflows.readers import CHECKS, JOBS, StoreReaders
from jason.workflows.types import ClockBasis, Role, StepKind, StepRefused, Visibility, parse_sop
from test_workflows_support import data  # noqa: F401 - the `data` fixture

ROOT = Path(__file__).resolve().parent.parent
ROLE = {"M": Role.MANAGER, "S": Role.SECRETARY, "A": Role.ADMINISTRATOR, "N": Role.ANYONE, "J": Role.JASON}
KINDS = {k.value: k for k in StepKind}

# id (as the page names it), the kind the page gives it, the kind it is built as, its role, what it needs
EXPECTED = {
    "document-intake": """
        1  job      person   M -
        2  check    person   M 1
        3  person   person   N 2
        4  job      person   M 1
        5  person   person   N 4
        6  person   person   N 5
        7  job      person   M 5,6
        8  job      person   M 1
        9  job      person   M 8
        10 job      person   M 2,3,4,5,6,7,8,9
        11 person   person   N 10
        12 person   person   N 11
        13 job      person   M 10
        14 person   person   M 11,12
        15 plan     person   M 14
        16 job      person   M 14
        17 person   person   M 16
        18 decision decision S 17
        19 job      person   M 9
        20 job      person   M 14
        21 person   person   M 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20""",
    "ingest": """
        0 wait   wait   M -
        1 job    person M 0
        2 person person M 1
        3 job    person M 1
        4 job    person M 1
        5 job    person N 1
        6 job    person M 5
        7 plan   person M 6
        8 job    person M 1
        9 check  check J 7""",
    "record-slot": """
        1  check  check J -
        2  branch person N 1
        3  person person N 2
        4  job    person N 3
        5  check  person N 4
        6  branch person N 5
        7  person person N 4
        8  person person N 3
        9  person person N 2
        10 wait   wait   N 9
        11 person person N 3
        12 check  check J 1""",
    "split-document": """
        1 person person N -
        2 job    person N 1
        3 person person N 2
        4 check  check J 3
        5 branch branch N 4
        6 person person N 4,5
        7 job    person N 6
        8 person person N 1""",
    "onboard": """
        ST-0  branch   branch   M -
        ST-1  check    check   J -
        ST-2  person   person   A ST-1
        ST-3  job      person   M ST-2
        ST-4  check    person   M ST-2
        ST-5  person   person   A ST-1
        ST-6  person   person   A ST-1
        ST-7  check    check   J ST-4,ST-5,ST-6
        IN-1  check    person   M ST-7
        IN-2  person   person   N IN-1
        IN-3  person   person   M ST-7
        IN-4  wait     wait     M IN-3
        IN-5  person   person   M IN-4
        IN-6  job      person   M ST-7
        IN-7  check    check   J IN-1,IN-5,IN-6
        ES-1  person   person   M IN-7
        ES-2  person   person   N ES-1
        ES-3  person   person   N ST-7,ES-3b
        ES-3b branch   branch   N ST-7
        ES-4  person   person   N ES-3
        ES-5  person   person   M ES-3,ES-4
        ES-6  person   person   M ES-5
        ES-7  check    check   J ES-2,ES-6
        OP-1  person   person   M ST-7
        OP-2  person   person   N ES-3
        OP-3  person   person   A ST-6
        OP-4  check    check   J OP-1,OP-2,OP-3
        AD-1  person   person   M ES-6
        AD-2  person   person   N AD-1
        AD-3  check    check   J ST-7,IN-7,ES-7,OP-4
        AD-4  check    check   J AD-2,AD-3
        AD-5  person   person   M ST-7,IN-7,ES-7,OP-4,AD-4
        CM-1  person   person   M ST-7,ST-0
        CM-2  decision decision S CM-1
        CM-3  person   person   M CM-2
        CM-4  person   person   M CM-2""",
    "founding-documents": """
        1 person person M -
        2 job    person M 1
        3 person person N 2
        4 person person N 3
        5 person person M 4
        6 wait   wait   M 2""",
    "key-document": """
        1 check  check J -
        2 person person M 1
        3 wait   wait   M 2
        4 person person N 3
        5 check  person M 4
        6 person person N 5
        7 person person N 1""",
    "parcel-title": """
        1 job    person M -
        2 check  person M 1
        3 job    person M 2
        4 person person M 2
        5 job    person M 2""",
    "careful-reading": """
        1  check  person M -
        2  job    person M 1
        3  person person N 2
        4  job    person M 2
        5  job    person M 2
        6  job    person M 3
        7  job    person M 4,5,6
        8  job    person M 7
        9  check  person M 7
        10 person person M 9""",
    "records-production": """
        1  person person M -
        2  check  person M 1
        3  check  person M 1
        4  person person N 3
        5  person person M 1
        6  person person M 3
        7  wait   wait   M 6
        8  person person M 5,6,7
        9  person person M 6
        10 wait   wait   M 1""",
}
PROCEDURE = {"document-intake": "document-intake", "ingest": "ingest", "onboard": "onboard", "careful-reading": "careful-reading"}
OFFERED = list(EXPECTED)
STEPS = {"document-intake": 21, "ingest": 10, "record-slot": 12, "split-document": 8, "onboard": 36, "founding-documents": 6,
         "key-document": 7, "parcel-title": 5, "careful-reading": 10, "records-production": 10}
SUBJECT = {"document-intake": "document", "ingest": "source", "record-slot": "association", "split-document": "draft",
           "onboard": "association", "founding-documents": "association", "key-document": "entry", "parcel-title": "parcel",
           "careful-reading": "question", "records-production": "request"}


def table(key):
    rows = []
    for line in EXPECTED[key].strip().splitlines():
        n, page, built_, role, needs = line.split()
        rows.append((n, KINDS[page], KINDS[built_], ROLE[role], () if needs == "-" else tuple(needs.split(","))))
    return rows


def everything():
    return {w.key: w for w in (b() for b in records.BUILDERS)}


def offered():
    return {w.key: w for w in (b() for b in records.BUILDERS)}


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


def registries():
    from jason.approvals import registry

    return {k.key for k in registry.kinds()} | {a for k in registry.kinds() for a in k.aliases}


# --- the definitions against the page ---------------------------------------------------------------------------------

def test_the_builders_are_the_ten_definitions_and_the_tenth_is_held():
    assert list(offered()) == OFFERED and len(records.BUILDERS) == 10 and records.NOT_OFFERED == ()
    assert [k for k, w in offered().items() if w.visibility is Visibility.HELD] == ["records-production"]
    assert offered()["records-production"].held_title == "A records request"
    assert list(everything()) == list(EXPECTED)
    for key, w in everything().items():
        assert w.family == "records" and w.subject == SUBJECT[key], key
        assert w.procedure == PROCEDURE.get(key, ""), key
        assert w.title and w.title == w.title.strip()


@pytest.mark.parametrize("key", list(EXPECTED))
def test_each_definition_has_the_tables_steps_kinds_roles_and_needs(key):
    w = everything()[key]
    rows = table(key)
    assert [s.id for s in w.steps] == [f"{key}.{n}" for n, *_ in rows]
    assert len(w.steps) == STEPS[key]
    for (n, _, kind, role, needs), s in zip(rows, w.steps):
        assert s.kind is kind, s.id
        assert s.role is role, s.id
        assert s.needs == tuple(f"{key}.{x}" for x in needs), s.id
        assert s.why and s.title and s.title.strip() == s.title, f"{s.id} says why"


def test_the_step_count_is_the_sum_of_the_tables():
    assert sum(len(table(k)) for k in EXPECTED) == sum(len(w.steps) for w in everything().values()) == 125
    assert sum(len(w.steps) for w in offered().values()) == 125
    assert len(everything()["onboard"].steps) == 36                      # "about 35 steps by gate", with the start fork


def test_the_ids_keep_the_pages_numbers_and_the_gates_of_onboard_keep_their_prefix():
    ob = everything()["onboard"]
    assert {s.group for s in ob.steps} == {"ST", "IN", "ES", "OP", "AD", "CM"}
    for s in ob.steps:
        assert s.id.split(".", 1)[1].startswith(s.group + "-"), s.id
    assert {"onboard.ES-3b", "onboard.ST-0"} <= {s.id for s in ob.steps}
    assert {s.id for s in everything()["ingest"].steps} >= {"ingest.0"}               # the source arrives is step 0
    assert [p.key for p in ob.phases] == ["start", "ingest", "establish", "operate", "adopt", "change-of-manager"]
    assert sorted(x for p in ob.phases for x in p.steps) == sorted(s.id for s in ob.steps)


def test_a_step_is_built_as_another_kind_only_when_what_the_page_names_is_not_built_yet():
    differs = {f"{key}.{n}" for key in EXPECTED for n, page, built_, *_ in table(key) if page is not built_}
    assert differs
    wfs = everything()
    for sid in differs:
        s = wfs[sid.split(".")[0]].step(sid)
        found = re.search(r"Becomes an? (check|job|plan) step \(([^)]+)\)", s.why)
        # a branch built as a person's step (a per-slot branch) and the child-run steps say so in their own words
        if found is None:
            assert s.kind is StepKind.PERSON and (s.spawns or "branch" in s.why.lower()), sid
        else:
            assert s.kind is StepKind.PERSON and f"{found.group(1)}:{found.group(2)}" in records.WANTED, sid
        assert s.command or s.record or s.spawns, f"{sid} shows what a person runs or records"
        assert not s.job and not s.plan_kind and s.check is None, sid


def test_wanted_lists_each_unbuilt_read_job_and_kind_once_and_none_of_them_exists_yet():
    assert list(records.WANTED) == list(dict.fromkeys(records.WANTED)) and records.WANTED
    named = {f"{m.group(1)}:{m.group(2)}" for w in everything().values() for s in w.steps
             for m in re.finditer(r"Becomes an? (check|job|plan) step \(([^)]+)\)", s.why)}
    assert named == set(records.WANTED)
    kinds = registries()
    for want in records.WANTED:
        word, _, name = want.partition(":")
        assert word in ("check", "job", "plan"), want
        if word == "check":
            assert name not in CHECKS, f"{name} is built now: make the step a check"
        elif word == "job":
            assert name not in JOBS, f"{name} is built now: make the step a job"
        else:
            assert name not in kinds, f"{name} is registered now: make the step a plan"
    with pytest.raises(ValueError):
        records.becomes("job", "not-in-the-list")


CHECK_STEPS = {
    "ingest.9": "ingest-gate", "record-slot.1": "record-slots-read", "record-slot.12": "onboard-gates-read",
    "split-document.4": "split-review", "key-document.1": "key-document-status", "onboard.ST-1": "active-community",
    "onboard.ST-7": "onboard-gate-start", "onboard.IN-7": "onboard-gate-ingest", "onboard.ES-7": "onboard-gate-establish",
    "onboard.OP-4": "onboard-gate-operate", "onboard.AD-3": "onboard-checklist", "onboard.AD-4": "onboard-gate-adopt",
}
"""The steps built as a read, and the read each names (jason.workflows.checks.records)."""


def test_no_step_names_a_plan_or_a_job_and_each_check_step_is_jasons_and_names_a_registered_read():
    from jason.workflows import checks

    checks.load_all()
    found = {}
    for w in everything().values():
        for s in w.steps:
            assert s.kind not in (StepKind.PLAN, StepKind.JOB), s.id
            assert not s.job and not s.plan_kind, s.id
            if s.kind is StepKind.CHECK:
                found[s.id] = s.check.name
                assert s.role is Role.JASON and not s.record, s.id
                assert s.check.name in CHECKS, s.id
            else:
                assert s.check is None, s.id
    assert found == CHECK_STEPS and len(found) == 12
    assert not set(found.values()) & {w.partition(":")[2] for w in records.WANTED}, "a read built now is no longer wanted"


def test_the_reads_wanted_are_the_ones_no_existing_function_answers_safely():
    left = sorted(w for w in records.WANTED if w.startswith("check:"))
    assert left == [f"check:{n}" for n in (
        "designation-on-file", "document-kind-read", "key-document-verified", "parcel-strand-gaps", "profile-own-facts",
        "quotes-verified", "record-compare", "request-kinds-mapped", "scratch-room")]


def test_the_child_runs_name_definitions_that_exist():
    spawns = {s.id: s.spawns for w in everything().values() for s in w.steps if s.spawns}
    assert spawns == {
        "ingest.8": "document-intake", "record-slot.7": "split-document", "onboard.IN-1": "record-slot", "onboard.IN-5": "ingest",
        "onboard.ES-1": "founding-documents", "onboard.ES-2": "document-intake", "onboard.AD-2": "document-intake",
        "founding-documents.5": "key-document"}
    known = set(offered()) | {"owner-info-cycle", "control-adoption"}
    assert set(spawns.values()) <= known


# --- the registries and the shelf -------------------------------------------------------------------------------------

def test_every_definition_validates_against_the_real_registries():
    keys = set(offered()) | {g().key for g in general.GENERAL}
    for key, w in everything().items():
        assert definitions.validate(w, plan_kinds=registries(), jobs=set(JOBS), workflows=keys) == [], key
        assert definitions.validate(w) == [], key                                    # the approvals registry as it is read


def test_every_statute_a_law_clock_cites_is_on_the_real_shelf_when_there_is_one():
    shelf = ROOT / "data" / "authorities"
    if not (shelf / "CIV").is_dir():
        pytest.skip("the authorities shelf is not on this machine")
    resolve = general.shelf_resolver(ROOT / "data")
    cites = {c.cite for w in everything().values() for s in w.steps if (c := s.clock) and c.cite}
    assert {"CIV 4270(a)(3)", "CIV 5210(b)", "CIV 5210(b)(2)", "CIV 5210(a)", "CIV 5215"} <= cites
    for cite in sorted(cites):
        assert resolve(cite) is True, cite
    for w in everything().values():
        assert definitions.validate(w, plan_kinds=registries(), jobs=set(JOBS), resolve_law=resolve) == [], w.key


def test_the_sop_addresses_exist_and_a_workflow_does_not_drift_from_its_procedure():
    from jason.community.procedures import find

    wfs = list(everything().values())
    assert definitions.drift(wfs) == []
    addressed = {s.sop for w in wfs for s in w.steps if s.sop}
    assert addressed
    for address in addressed:
        key, index = parse_sop(address)
        assert key in {"document-intake", "ingest", "onboard", "careful-reading"}, address
        assert 1 <= index <= len(find(key).steps), address
    assert len(find("onboard").steps) == 19 and len(find("document-intake").steps) == 13
    assert len(find("ingest").steps) == 7 and len(find("careful-reading").steps) == 10


def test_a_step_addresses_the_procedure_step_that_has_its_command_or_its_words():
    from jason.community.procedures import find

    def text(address):
        key, index = parse_sop(address)
        s = find(key).steps[index - 1]
        return f"{s.do} {s.command} {s.check}".lower()

    pins = {  # step id -> a word of the procedure step it addresses
        "document-intake.1": "jason library", "document-intake.4": "recorder_", "document-intake.5": "standing",
        "document-intake.7": "jason living", "document-intake.8": "preflight", "document-intake.9": "segment",
        "document-intake.10": "jason intake --scan", "document-intake.13": "library-ocr", "document-intake.14": "intake --apply",
        "document-intake.15": "reread", "document-intake.16": "conflicts --leads", "document-intake.19": "jason cite",
        "document-intake.20": "jason rules", "document-intake.21": "jason lessons",
        "ingest.1": "jason ingest source", "ingest.2": "contract", "ingest.3": "qr", "ingest.4": "--model", "ingest.5": "--park",
        "ingest.7": "--apply", "ingest.8": "jason revisions", "ingest.9": "--gate",
        "onboard.ST-1": "jason which", "onboard.ST-2": "onboard --new", "onboard.ST-4": "jason spec", "onboard.ST-5": "google",
        "onboard.ST-6": "vault", "onboard.IN-1": "records --list", "onboard.IN-2": "records --read", "onboard.IN-3": "--request",
        "onboard.IN-6": "sync-catalog", "onboard.ES-3": "onboard --answer", "onboard.ES-3b": "jason-mcp", "onboard.OP-1": "data/spec",
        "onboard.OP-2": "board-roster", "onboard.OP-3": "cadence", "onboard.AD-1": "community subclass",
        "onboard.AD-3": "--checklist", "onboard.CM-1": "outgoing agreement", "onboard.CM-4": "change of manager",
        "record-slot.1": "records --list", "record-slot.4": "records --read", "split-document.6": "jason split",
        "careful-reading.1": "storage --check", "careful-reading.2": "index --plan", "careful-reading.3": "index --search",
        "careful-reading.4": "chronology", "careful-reading.5": "inspections", "careful-reading.6": "--recite",
        "careful-reading.7": "jason review", "careful-reading.8": "--as-of", "careful-reading.9": "verify-quotes",
        "careful-reading.10": "proposal",
    }
    wfs = everything()
    for sid, word in pins.items():
        s = wfs[sid.split(".")[0]].step(sid)
        assert s is not None and s.sop, sid
        assert word in text(s.sop), (sid, s.sop, word)
    # the page numbers steps 13 to 15 of the procedure differently from the procedure as it stands (integrations are 13,
    # the schedules 14, the Community subclass 15), so the addresses follow the procedure, not the page's parentheses
    assert wfs["onboard"].step("onboard.ST-6").sop == "onboard#13" and wfs["onboard"].step("onboard.AD-1").sop == "onboard#15"


def test_every_command_a_step_shows_names_a_command_that_exists():
    from jason.cli import build_parser

    parser = build_parser()
    commands = set(next(a for a in parser._actions if getattr(a, "choices", None) and "workflow" in a.choices).choices)
    for w in everything().values():
        for s in w.steps:
            for part in re.split(r";|\bor\b", s.command):
                part = part.strip()
                if part.startswith("jason ") and not part.startswith("jason-mcp"):
                    assert part.split()[1] in commands, (s.id, part)


# --- clocks -----------------------------------------------------------------------------------------------------------

def test_a_law_clock_cites_its_section_and_a_legal_step_has_no_skip():
    for w in everything().values():
        for s in w.steps:
            if s.clock is not None and s.clock.basis is ClockBasis.LAW:
                assert s.clock.cite.startswith("CIV "), s.id
                assert s.skip is None and s.is_legal, s.id
            if s.skip is not None:
                assert not s.is_legal and s.skip.reason_required, s.id


def test_the_law_clocks_are_the_pages_and_a_clock_the_law_does_not_date_has_no_date():
    law = {s.id: s.clock for w in everything().values() for s in w.steps if s.clock and s.clock.basis is ClockBasis.LAW}
    assert {i: c.cite for i, c in law.items()} == {
        "document-intake.5": "CIV 4270(a)(3)", "key-document.6": "CIV 4270(a)(3)", "records-production.1": "CIV 5210(b)",
        "records-production.3": "CIV 5210(a)", "records-production.6": "CIV 5215", "records-production.8": "CIV 5210(b)",
        "records-production.10": "CIV 5210(b)(2)"}
    dated = {i: (c.slot, c.days) for i, c in law.items() if c.slot}
    assert dated == {"records-production.1": ("received_on", 0), "records-production.8": ("received_on", 30),
                     "records-production.10": ("received_on", 30)}


def test_the_membership_list_clock_stays_out_until_counsel_reads_it():
    for w in everything().values():
        for s in w.steps:
            if s.clock is not None:
                assert "5210(b)(6)" not in s.clock.cite and "8330" not in s.clock.cite, s.id
    why = everything()["records-production"].step("records-production.10").why
    assert "5210(b)(6)" in why and "counsel" in why and "not a law clock" in why


def test_a_handover_has_no_stored_deadline_and_no_section_is_cited_for_one():
    ob = everything()["onboard"]
    for s in ob.steps:
        assert "5205" not in s.why and "5205" not in (s.clock.cite if s.clock else ""), s.id
        if s.clock is not None:
            assert s.clock.basis in (ClockBasis.PERSON, ClockBasis.DOCUMENTS) and not s.clock.cite, s.id
    assert "silent" in ob.step("onboard.CM-4").why and "silent" in ob.step("onboard.IN-4").why
    assert not ob.has_legal_clock()


def test_the_dates_each_run_asks_for_are_the_ones_its_clocks_read():
    for w in everything().values():
        slots = {d.name for d in w.dates}
        for s in w.steps:
            if s.clock is not None and s.clock.slot:
                assert s.clock.slot in slots, s.id
    rp = everything()["records-production"]
    assert [d.name for d in rp.dates] == ["received_on"] and rp.dates[0].required and rp.check_dates({}) == ["date received_on is required"]
    ob = everything()["onboard"]
    assert [d.name for d in ob.dates] == ["term_ends", "transition_on"] and not any(d.required for d in ob.dates)
    assert ob.check_dates({}) == [] and ob.check_dates({"term_ends": "2099-12-31", "transition_on": "2099-12-01"}) == []
    assert not any(d.required for k in ("ingest", "careful-reading") for d in everything()[k].dates)


def test_the_change_of_manager_decision_is_the_boards_and_the_secretary_records_it():
    ob = everything()["onboard"]
    cm2 = ob.step("onboard.CM-2")
    assert cm2.kind is StepKind.DECISION and cm2.role is Role.SECRETARY and cm2.record
    for s in ob.steps:
        if s.kind is StepKind.DECISION:
            assert s.role is Role.SECRETARY, s.id
    fork = ob.step("onboard.ST-0")
    paths = {c.key: c.steps for c in fork.choices}
    assert paths == {"new-association": (), "change-of-manager": tuple(f"onboard.CM-{i}" for i in range(1, 5))}
    for i in range(1, 5):
        assert "onboard.ST-0" in ob.step(f"onboard.CM-{i}").needs or "onboard.CM-1" in ob.step(f"onboard.CM-{i}").needs or \
            "onboard.CM-2" in ob.step(f"onboard.CM-{i}").needs


def test_the_two_alternative_branches_name_the_steps_that_belong_to_one_path_alone():
    ob = everything()["onboard"]
    assert {c.key: c.steps for c in ob.step("onboard.ES-3b").choices} == {"terminal": ("onboard.ES-3",), "conversation": ()}
    sd = everything()["split-document"]
    assert {c.key for c in sd.step("split-document.5").choices} == {"held", "library", "slots", "each-part"}


# --- privacy and the boundary -----------------------------------------------------------------------------------------

def test_no_title_or_subject_names_a_confidential_kind_and_no_text_names_an_executive_session():
    for w in everything().values():
        for s in w.steps:
            title = s.title.lower()
            for word in ("executive", "bank statement", "membership", "ballot", "owner histor", "owner's name"):
                assert word not in title, (s.id, word)
            blob = " ".join((s.why, s.record, s.command)).lower()
            for word in ("executive session", "executive-session", "bank statement", "ballot", "owner histor"):
                assert word not in blob, (s.id, word)
        assert w.subject in SUBJECT.values() and not any(c in w.subject for c in "/\\:")
        for d in w.dates:
            assert d.name and "name" not in d.name


def test_the_records_production_run_is_held_and_its_stated_reason_is_in_the_module():
    assert "records-production" in offered()
    doc = records.records_production.__doc__
    assert "Held" in doc and "executive-session" in doc
    assert all(s.title and not s.public_title for s in records.records_production().steps)
    got = [w.key for w in general.register_general()]
    assert "records-production" in got and definitions.find("records-production").visibility is Visibility.HELD


def test_the_definitions_name_no_association_street_or_person():
    text = repr(list(everything().values())).lower()
    for word in ("mystique", "main st", "oak ln", "a. owner", "b. owner", "example village", "sacramento", "placer", "$"):
        assert word not in text, word


def test_the_module_is_pure_data_and_imports_only_the_engines_types():
    path = ROOT / "src" / "jason" / "workflows" / "defs" / "records.py"
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names.add(node.module or "")
    stdlib = set(sys.stdlib_module_names)
    for name in names:
        top = name.split(".")[0]
        assert top in stdlib or top == "__future__" or name in ("jason.workflows.types", "jason.workflows.readers"), name
    text = path.read_text(encoding="utf-8").lower()
    for word in ("mystique", "jason_mystique", "jason.approvals", "jason.tasks", "jason.controls", "jason.community", "jason.web"):
        assert word not in text, word


def test_importing_it_adds_no_read_or_job_and_loads_no_profile_and_registers_nothing():
    code = """
import sys, json
from jason.workflows import readers, definitions
before = (sorted(readers.CHECKS), sorted(readers.JOBS))
modules = set(sys.modules)
from jason.workflows.defs import records
assert (sorted(readers.CHECKS), sorted(readers.JOBS)) == before, 'it added a read or a job'
print(json.dumps({'profile': sorted(m for m in sys.modules if 'mystique' in m), 'n': len(definitions.all_definitions()),
                  'new': sorted(set(sys.modules) - modules)}))
"""
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["profile"] == [] and got["n"] == 0
    assert [m for m in got["new"] if m.startswith("jason")] == ["jason.workflows.defs", "jason.workflows.defs.records"], got["new"]


# --- registering ------------------------------------------------------------------------------------------------------

def test_register_general_registers_the_offered_ones_with_the_two_built_before_and_no_clash():
    got = [w.key for w in general.register_general()]
    assert got.count("owner-info-cycle") == 1 and got.count("control-adoption") == 1
    for key in OFFERED:
        assert got.count(key) == 1 and definitions.find(key) is not None, key
    assert len(set(got)) == len(got)
    assert [w.key for w in general.register_general()] == got                              # idempotent
    known = {w.key for w in definitions.all_definitions()}
    assert {s.spawns for w in definitions.all_definitions() for s in w.steps if s.spawns} <= known


def test_workflow_definitions_lists_the_family(data, capsys, monkeypatch):
    from jason.cli import build_parser

    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: data)
    args = build_parser().parse_args(["workflow", "--definitions", "--family", "records", "--json"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    for key in OFFERED:
        assert key in out, key


# --- runs over them ---------------------------------------------------------------------------------------------------

MANAGER, SECRETARY, ADMIN, MEMBER, VISITOR = "J. Manager", "S. Secretary", "A. Admin", "M. Member", "V. Visitor"
PEOPLE = {MANAGER: {"manager"}, SECRETARY: {"secretary", "director"}, ADMIN: {"administrator"}, MEMBER: {"director"}, VISITOR: ()}
DAY = date(2099, 3, 2)


def roles_of(by):
    return PEOPLE.get(by, ())


def readers_for(data):
    return StoreReaders(data, community=object(), today=DAY)


def act(data, rid, fn, key, step, by=MANAGER, **more):
    return getattr(api, fn)(data, rid, f"{key}.{step}", by, roles_of=roles_of, readers=readers_for(data), today=DAY, **more)


def reopen(data, rid, by=MANAGER):
    return api.open_run(data, rid, by, readers=readers_for(data), roles_of=roles_of, today=DAY)


def states(data, rid, key):
    return {s["id"].split(".", 1)[1]: s["state"] for s in api.show(data, rid, today=DAY)["steps"]}


def test_a_parcel_title_run_goes_from_start_to_done_on_a_temporary_data_folder(data):
    general.register_general()
    key = "parcel-title"
    out = api.start(data, key, "parcel:EXAMPLE-1", "A parcel", {}, MANAGER, today=DAY)          # no legal clock: no yes
    rid = out["run"]["id"]
    assert out["run"]["state"] == "draft"
    reopen(data, rid)
    assert states(data, rid, key) == {"1": "needs a person", "2": "not started", "3": "not started", "4": "not started", "5": "not started"}
    with pytest.raises(StepRefused, match="manager"):
        act(data, rid, "attest", key, "1", by=VISITOR, record="x")
    with pytest.raises(StepRefused, match="record"):
        act(data, rid, "attest", key, "1")
    with pytest.raises(StepRefused, match="not a wait step"):
        act(data, rid, "arrived", key, "1")
    act(data, rid, "attest", key, "1", record="3 conveyances read")
    reopen(data, rid)
    act(data, rid, "attest", key, "2", record="1 gap found")
    reopen(data, rid)
    assert states(data, rid, key)["3"] == "needs a person" and states(data, rid, key)["5"] == "needs a person"
    with pytest.raises(StepRefused, match="reason"):
        act(data, rid, "skip", key, "4")
    act(data, rid, "skip", key, "3", reason="the gap is a known one")
    act(data, rid, "skip", key, "4", reason="names are not needed")
    act(data, rid, "attest", key, "5", record="the report exported")
    final = api.show(data, rid, today=DAY)
    assert final["state"] == "done" and all(s["state"] in ("done", "skipped") for s in final["steps"])
    assert api.verify(data, rid)["ok"]
    assert not list(data.rglob("*.pdf"))                                                     # a run writes only its own events


def test_onboard_a_new_association_skips_the_change_of_manager_block_and_the_fork_is_a_persons_answer(data, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "example")
    general.register_general()
    key = "onboard"
    rid = api.start(data, key, "association:example", "A new association", {}, MANAGER, today=DAY)["run"]["id"]
    reopen(data, rid)
    st = states(data, rid, key)
    assert st["ST-0"] == "needs a person" and st["ST-1"] == "done" and st["CM-1"] == "not started"     # the active community is the run's
    with pytest.raises(StepRefused, match="choose one of"):
        act(data, rid, "attest", key, "ST-0", choice="neither")
    act(data, rid, "attest", key, "ST-0", choice="new-association")
    reopen(data, rid)
    st = states(data, rid, key)
    assert st["ST-0"] == "done" and all(st[f"CM-{i}"] == "skipped" for i in range(1, 5))
    shown = {s["id"]: s for s in api.show(data, rid, today=DAY)["steps"]}
    assert "new-association" in shown["onboard.CM-2"]["reason"]
    # a gate is a person's reading: the administrator's steps are the administrator's alone
    with pytest.raises(StepRefused, match="administrator"):
        act(data, rid, "attest", key, "ST-5", record="the sign-ins made")


def test_onboard_a_change_of_manager_keeps_the_block_and_the_secretary_alone_records_the_boards_decision(data, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "example")
    general.register_general()
    key = "onboard"
    dates = {"term_ends": "2099-12-31", "transition_on": "2099-11-15"}
    rid = api.start(data, key, "association:example", "A change of manager", dates, MANAGER, today=DAY)["run"]["id"]
    reopen(data, rid)
    act(data, rid, "attest", key, "ST-0", choice="change-of-manager")
    with pytest.raises(StepRefused, match="not a person's|done by its result"):
        act(data, rid, "attest", key, "ST-1", record="the active profile, named")             # a read, not a person's word
    reopen(data, rid)
    st = states(data, rid, key)
    assert st["ST-1"] == "done"
    assert st["CM-1"] == "not started" and st["CM-2"] == "not started" and st["ST-0"] == "done"
    clocks = {c["key"]: c for c in api.show(data, rid, today=DAY)["clocks"]}
    assert clocks["onboard.CM-1"]["due"] == "2099-12-31" and clocks["onboard.CM-1"]["basis"] == "documents"
    assert clocks["onboard.CM-4"]["due"] == "2099-11-15" and clocks["onboard.CM-4"]["basis"] == "person"
    assert not any(c["basis"] == "law" for c in clocks.values())


def test_onboard_a_wrong_community_blocks_the_steps_after_the_first_read(data, monkeypatch):
    monkeypatch.setenv("JASON_COMMUNITY", "another")
    general.register_general()
    key = "onboard"
    rid = api.start(data, key, "association:example", "A new association", {}, MANAGER, today=DAY)["run"]["id"]
    reopen(data, rid)
    act(data, rid, "attest", key, "ST-0", choice="new-association")
    reopen(data, rid)
    shown = {s["id"]: s for s in api.show(data, rid, today=DAY)["steps"]}
    assert shown["onboard.ST-1"]["state"] == "failed" and "another" in shown["onboard.ST-1"]["reason"]
    assert shown["onboard.ST-2"]["state"] in ("blocked", "not started")


def test_a_record_slot_run_started_with_two_slots_is_done_slot_by_slot(data, monkeypatch):
    from jason.workflows.types import CheckResult

    general.register_general()
    monkeypatch.setitem(CHECKS, "record-slots-read", lambda readers, view, item="": CheckResult(True, (), "2 slots read"))
    key = "record-slot"
    rid = api.start(data, key, "association:example", "The checklist", {}, MANAGER, items=["slot-1", "slot-2"], today=DAY)["run"]["id"]
    reopen(data, rid)
    reopen(data, rid)
    s2 = next(s for s in api.show(data, rid, today=DAY)["steps"] if s["id"] == f"{key}.2")
    assert {i["item"] for i in s2["items"]} == {"slot-1", "slot-2"} and s2["state"] == "needs a person"
    act(data, rid, "attest", key, "2", by=MEMBER, item="slot-1", record="a file")
    s2 = next(s for s in api.show(data, rid, today=DAY)["steps"] if s["id"] == f"{key}.2")
    assert dict((i["item"], i["state"]) for i in s2["items"]) == {"slot-1": "done", "slot-2": "needs a person"}
    with pytest.raises(StepRefused, match="item"):
        act(data, rid, "attest", key, "2", by=MEMBER, record="a file")                     # say which slot
