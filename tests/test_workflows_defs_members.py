"""The members' family of workflow definitions (src/jason/workflows/defs/members.py), against the family page's tables
(docs/workflows/members-cycles.md, sections 2.2 to 2.6). The expected steps are written out here, not parsed from the page:
for each step its page kind, the kind it is built as, its role, and what it needs. A step is built as another kind only when
the read, job, or approvals kind the page names does not exist yet. Everything is made up ("A. Admin", 2099).
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
import shelf_support

from jason.workflows import api, definitions
from jason.workflows import definitions_general as general
from jason.workflows.defs import members
from jason.workflows.readers import CHECKS, JOBS, StoreReaders
from jason.workflows.types import ClockBasis, Role, StepKind, StepRefused, parse_sop
from test_workflows_support import data  # noqa: F401 - the `data` fixture

ROOT = Path(__file__).resolve().parent.parent
ROLE = {"M": Role.MANAGER, "S": Role.SECRETARY, "A": Role.ADMINISTRATOR, "J": Role.JASON, "N": Role.ANYONE}

# id, the kind the page gives it, the kind it is built as, its role, what it needs (ids as the page numbers them)
EXPECTED = {
    "notice-delivery": """
        1  check    check     J  -
        2  job      person    M  1
        3  wait     wait      M  1
        4  job      person    M  3
        5  person   person    S  4
        6  wait     wait      M  4
        7  plan     person    M  6
        8  person   person    M  7
        9  wait     wait      M  7
        10 check    check     J  9
        11 check    check     J  10
        12 decision decision  S  11
        13 check    check     J  11""",
    "mailroom-letter": """
        1 check  check  J -
        2 job    person M 1
        3 person person M 2
        4 plan   plan   M 2,3
        5 wait   wait   M 4
        6 check  check  J 4
        7 wait   wait   M 6""",
    "respond-sweep": """
        1 job    person M -
        2 check  check  J 1
        3 plan   person M 2
        4 person person M 2
        5 check  check  J 1
        6 person person A 2""",
    "respond-request": """
        1  check    check    J -
        2  person   person   M 1
        3  check    check    J 1
        4  decision decision S 3
        5  job      person   M 1
        6  job      person   M 1
        7  person   person   M 6
        8  branch   branch   M 2
        10 person   person   M 8
        11 person   person   M 10
        12 wait     wait     M 10
        13 person   person   M 11,12
        14 person   person   M 8
        15 person   person   M 8
        16 decision decision S 15
        17 person   person   M 16
        18 person   person   M 17
        19 branch   branch   S 18
        20 person   person   M 8
        21 wait     wait     M 6
        22 person   person   M 13,14,18,20""",
    "respond-policy": """
        1 job      person   M -
        2 person   person   M 1
        3 branch   branch   S 2
        4 decision decision S 3
        5 person   person   A 4
        6 plan     person   M 5""",
    "owner-document": """
        1  person person N -
        2  check  check  J 1
        3  person person N 2
        4  check  check  J 2
        5  plan   person N 3
        6  person person S 5
        7  job    person N 6
        8  person person N 5
        9  branch branch N 8,6
        10 check  check  J 9""",
    "form-campaign": """
        1   check    check    J -
        2   check    check    J 1
        3   branch   branch   M 1
        4   person   person   M 3
        5   person   person   M 4
        6   person   person   M 5
        6.6 decision decision S 6
        6.7 plan     plan     M 6,6.6
        7   check    check    J 5
        8   person   person   M 6,6.6,6.7""",
    "form-library-review": """
        1 job      person   A -
        2 person   person   A 1
        3 decision decision S 2
        4 job      person   A -""",
}
PROCEDURE = {"notice-delivery": "notice-delivery", "mailroom-letter": "mailroom-letter", "respond-sweep": "respond",
             "respond-request": "respond", "respond-policy": "respond", "owner-document": "owner-document",
             "form-campaign": "", "form-library-review": "law-review"}
KINDS = {k.value: k for k in StepKind}


def table(key):
    rows = []
    for line in EXPECTED[key].strip().splitlines():
        n, page, built, role, needs = line.split()
        rows.append((n, KINDS[page], KINDS[built], ROLE[role], () if needs == "-" else tuple(needs.split(","))))
    return rows


def built():
    return {w.key: w for w in (b() for b in members.BUILDERS)}


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


def registries():
    from jason.approvals import registry

    return {k.key for k in registry.kinds()} | {a for k in registry.kinds() for a in k.aliases}


# --- the definitions against the page ---------------------------------------------------------------------------------

def test_the_builders_are_the_eight_definitions_the_page_names_besides_the_cycle():
    wfs = built()
    assert list(wfs) == list(EXPECTED) and len(members.BUILDERS) == 8
    assert "owner-info-cycle" not in wfs
    for key, w in wfs.items():
        assert w.family == "members" and w.procedure == PROCEDURE[key], key


@pytest.mark.parametrize("key", list(EXPECTED))
def test_each_definition_has_the_tables_steps_kinds_roles_and_needs(key):
    w = built()[key]
    rows = table(key)
    assert [s.id for s in w.steps] == [f"{key}.{n}" for n, *_ in rows]
    for (n, _, kind, role, needs), s in zip(rows, w.steps):
        assert s.kind is kind, s.id
        assert s.role is role, s.id
        assert s.needs == tuple(f"{key}.{x}" for x in needs), s.id
        assert s.why, f"{s.id} says why"
        assert s.title.strip() == s.title and s.title


def test_the_ids_keep_the_pages_numbers_so_there_is_no_request_step_9_and_the_group_steps_have_dotted_ids():
    ids = {s.id for w in built().values() for s in w.steps}
    assert "respond-request.8" in ids and "respond-request.10" in ids and "respond-request.9" not in ids
    assert {"form-campaign.6.6", "form-campaign.6.7"} <= ids
    assert sum(len(table(k)) for k in EXPECTED) == sum(len(w.steps) for w in built().values()) == 77


def test_a_step_is_built_as_another_kind_only_when_what_the_page_names_is_not_built_yet():
    wfs = built()
    differs = {f"{key}.{n}" for key in EXPECTED for n, page, kind, *_ in table(key) if page is not kind}
    assert differs
    for sid in differs:
        s = wfs[sid.split(".")[0]].step(sid)
        assert s.kind is StepKind.PERSON, sid                         # shown with its command, attested by a person
        assert sid in members.BECOMES and "becomes" in s.why and members.BECOMES[sid].split()[1] in s.why, sid
        assert s.command or s.record, f"{sid} shows what a person runs or records"
    # the two steps that are the kind the page gives them and still wait for a kind: the cancel's wait and the form offer
    assert set(members.BECOMES) - differs == {"mailroom-letter.5", "form-campaign.5"}
    # no read is left to build: the five that remained are checks now (jason.workflows.checks.members)
    assert not [v for v in members.BECOMES.values() if v.startswith("check ")]


def test_wanted_lists_each_unbuilt_read_job_and_kind_once_and_none_of_them_exists_yet():
    assert list(members.WANTED) == list(dict.fromkeys(members.WANTED)) and set(members.WANTED) == set(members.BECOMES.values())
    assert members.WANTED
    kinds = registries()
    for want in members.WANTED:
        word, _, name = want.partition(" ")
        assert word in ("check", "job", "kind", "case"), want
        if word == "check":
            assert name not in CHECKS, f"{name} is built now: make the step a check"
        elif word == "job":
            assert name not in JOBS, f"{name} is built now: make the step a job"
        elif word == "kind":
            assert name not in kinds, f"{name} is registered now: make the step a plan"


def test_plans_jobs_and_checks_name_only_what_is_registered_and_the_module_adds_nothing():
    kinds = registries()
    plans = {s.plan_kind for w in built().values() for s in w.steps if s.kind is StepKind.PLAN}
    assert plans == {"payhoa-mailroom-send", "owner-info-tags"} and plans <= kinds
    assert not [s.id for w in built().values() for s in w.steps if s.kind is StepKind.JOB]
    from jason.workflows import checks

    checks.load_all()                                  # the members' reads live in jason.workflows.checks.members
    names = {s.check.name for w in built().values() for s in w.steps if s.check is not None}
    assert names == {"outstanding-read", "notice-requirement-read", "notice-owed-zero", "notice-proof", "notice-kept-text",
                     "mailroom-pages", "mailroom-batch-read", "requests-read", "answers-on-time", "request-classified",
                     "form-offered", "clock-authority-recited", "references-fill", "notice-elements", "kept-text-unchanged",
                     "form-stale"} and names <= set(CHECKS)
    # a step built as a check is jason's, and every one of them stays among the checks the page names
    for w in built().values():
        for s in w.steps:
            if s.check is not None:
                assert s.kind is StepKind.CHECK and s.role is Role.JASON and not s.job and not s.plan_kind, s.id
    # a plan step is never a person step with a plan kind, and no other step carries a kind or a job
    for w in built().values():
        for s in w.steps:
            assert bool(s.plan_kind) == (s.kind is StepKind.PLAN) and not s.job, s.id


# --- the registries and the shelf -------------------------------------------------------------------------------------

def test_every_definition_validates_against_the_real_registries():
    wfs = built()
    keys = set(wfs) | {g().key for g in general.GENERAL}
    for key, w in wfs.items():
        assert definitions.validate(w, plan_kinds=registries(), jobs=set(JOBS), workflows=keys) == [], key
        assert definitions.validate(w) == [], key                                    # the approvals registry as it is read


def test_every_statute_a_law_clock_cites_is_on_the_real_shelf_when_there_is_one():
    shelf_support.require(ROOT / "data")
    resolve = shelf_support.resolver(ROOT / "data")
    cites = {c.cite for w in built().values() for s in w.steps if (c := s.clock) and c.cite}
    assert {"CIV 4045(a)(3)", "CIV 4041(b)(1)", "CIV 4530(a)(1)", "CIV 4360(a)", "CIV 5205(f)", "CIV 5215(d)"} <= cites
    for cite in sorted(cites):
        assert resolve(cite) is True, cite
    for w in built().values():
        assert definitions.validate(w, plan_kinds=registries(), jobs=set(JOBS), resolve_law=resolve) == [], w.key


def test_the_sop_addresses_exist_and_a_workflow_does_not_drift_from_its_procedure():
    from jason.community.procedures import find

    wfs = list(built().values())
    assert definitions.drift(wfs) == []
    addressed = {s.sop for w in wfs for s in w.steps if s.sop}
    assert addressed
    for address in addressed:
        key, index = parse_sop(address)
        assert key in {"notice-delivery", "mailroom-letter", "respond", "owner-document", "owner-info-cycle", "law-review"}
        assert 1 <= index <= len(find(key).steps), address
    # the pins: the index is a position, so these steps are the ones with the same command
    def command(address):
        key, index = parse_sop(address)
        return find(key).steps[index - 1].command

    w = built()
    assert "--sync" in command(w["notice-delivery"].step("notice-delivery.4").sop)
    assert "--mark-general" in command(w["notice-delivery"].step("notice-delivery.5").sop)
    assert "--proof" in command(w["notice-delivery"].step("notice-delivery.11").sop)
    assert "--send" in command(w["mailroom-letter"].step("mailroom-letter.4").sop)
    assert "--cancel" in command(w["mailroom-letter"].step("mailroom-letter.5").sop)
    assert "--sync" in command(w["mailroom-letter"].step("mailroom-letter.7").sop)
    assert "--prices" in command(w["mailroom-letter"].step("mailroom-letter.1").sop)
    assert "--sources" in command(w["respond-request"].step("respond-request.5").sop)
    assert "--measure" in command(w["respond-sweep"].step("respond-sweep.6").sop)
    assert "section-refs" in command(w["owner-document"].step("owner-document.2").sop)
    assert "--to-doc" in command(w["owner-document"].step("owner-document.5").sop)
    assert "--leads" in command(w["form-library-review"].step("form-library-review.1").sop)


# --- clocks -----------------------------------------------------------------------------------------------------------

def test_a_law_clock_cites_its_section_and_a_legal_step_has_no_skip():
    for w in built().values():
        for s in w.steps:
            if s.clock is not None and s.clock.basis is ClockBasis.LAW:
                assert s.clock.cite.startswith("CIV "), s.id
                assert s.skip is None and s.is_legal, s.id
            if s.skip is not None:
                assert not s.is_legal, s.id


def test_the_law_clocks_are_the_pages_and_a_clock_the_law_does_not_date_has_no_date():
    law = {s.id: s.clock for w in built().values() for s in w.steps if s.clock and s.clock.basis is ClockBasis.LAW}
    assert {i: c.cite for i, c in law.items()} == {
        "notice-delivery.5": "CIV 4045(a)(3)", "respond-request.10": "CIV 5210(b)", "respond-request.11": "CIV 5215(d)",
        "respond-request.12": "CIV 5205(f)", "respond-request.13": "CIV 5210(b)(1)", "respond-request.14": "CIV 4530(a)(1)",
        "respond-request.17": "CIV 4765(a)(4)", "respond-policy.3": "CIV 4360(a)", "form-campaign.6.7": "CIV 4041(b)(1)"}
    # only a calendar offset from a day the run knows is dated: the resale documents (10 days), a rule change (28 days
    # before), and the entry of the answers (30 days before the reports); a records request's business days are not
    dated = {i: (c.slot, c.days) for i, c in law.items() if c.slot}
    assert dated == {"respond-request.14": ("received_on", 10), "respond-policy.3": ("decide_on", -28),
                     "form-campaign.6.7": ("reports_mailed", -30)}


def test_the_membership_list_clock_stays_out_until_counsel_reads_it():
    for w in built().values():
        for s in w.steps:
            if s.clock is not None:
                assert "5210(b)(6)" not in s.clock.cite and "8330" not in s.clock.cite, s.id
    why = built()["respond-request"].step("respond-request.13").why
    assert "5210(b)(6)" in why and "counsel" in why


def test_a_proposed_number_is_labeled_proposed_and_no_skip_lacks_a_reason():
    for w in built().values():
        for s in w.steps:
            if s.clock is not None and s.clock.basis is ClockBasis.PROPOSED_POLICY and s.clock.label:
                assert s.clock.basis is not ClockBasis.LAW
            if s.skip is not None:
                assert s.skip.reason_required, s.id


def test_the_dates_each_run_asks_for_are_the_ones_its_clocks_read():
    for w in built().values():
        slots = {d.name for d in w.dates}
        for s in w.steps:
            if s.clock is not None and s.clock.slot:
                assert s.clock.slot in slots, s.id
    wf = built()["respond-request"]
    assert [d.name for d in wf.dates] == ["received_on"] and wf.dates[0].required
    assert wf.check_dates({}) == ["date received_on is required"]
    assert all(not d.required for k in ("notice-delivery", "mailroom-letter", "form-campaign", "respond-policy") for d in built()[k].dates)


def test_the_branches_name_the_steps_that_belong_to_one_path_alone():
    r = built()["respond-request"]
    paths = {c.key: c.steps for c in r.step("respond-request.8").choices}
    assert paths["records"] == tuple(f"respond-request.{n}" for n in (10, 11, 12, 13))
    assert paths["resale"] == ("respond-request.14",) and paths["staff"] == ("respond-request.20",)
    assert paths["board"] == tuple(f"respond-request.{n}" for n in (15, 16, 17, 18, 19)) and paths["executive-session"] == ()
    f = built()["form-campaign"]
    assert {c.key: c.steps for c in f.step("form-campaign.3").choices} == {
        "owner-information": ("form-campaign.6.6", "form-campaign.6.7"), "response-clock": ()}
    assert {s.id: s.spawns for w in built().values() for s in w.steps if s.spawns} == {
        "respond-request.6": "owner-document", "respond-request.17": "owner-document", "respond-policy.6": "owner-document",
        "owner-document.9": "notice-delivery", "form-campaign.2": "form-library-review"}


# --- purity and the boundary ------------------------------------------------------------------------------------------

def test_the_module_is_pure_data_and_imports_only_the_engines_types_and_named_check():
    path = ROOT / "src" / "jason" / "workflows" / "defs" / "members.py"
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
    code = (
        "import sys, json\n"
        "from jason.workflows import readers, definitions\n"
        "before = (sorted(readers.CHECKS), sorted(readers.JOBS))\n"
        "modules = set(sys.modules)\n"
        "from jason.workflows.defs import members\n"
        "assert (sorted(readers.CHECKS), sorted(readers.JOBS)) == before, 'it added a read or a job'\n"
        "print(json.dumps({'profile': sorted(m for m in sys.modules if 'mystique' in m), 'n': len(definitions.all_definitions()),\n"
        "  'new': sorted(set(sys.modules) - modules)}))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["profile"] == [] and got["n"] == 0                             # nothing registered by an import
    assert set(got["new"]) <= {"jason.workflows.defs", "jason.workflows.defs.members"}, got["new"]


def test_the_definitions_name_no_association_street_or_person():
    text = repr(list(built().values())).lower()
    for word in ("mystique", "main st", "oak ln", "a. owner", "b. owner", "example village"):
        assert word not in text, word


# --- registering ------------------------------------------------------------------------------------------------------

def register_mine():
    """The two built before and these eight, each checked as ``register_general`` checks it, so a test of this family does not
    depend on another family's definitions being valid at the moment it runs."""
    rows = (*general.GENERAL, *members.BUILDERS)
    keys = {r().key for r in rows}
    return [definitions.register(r(), jobs=set(JOBS), workflows=keys) for r in rows]


def test_register_general_registers_the_two_built_before_and_the_eight_together_without_a_clash():
    from jason.workflows.types import InvalidWorkflow

    try:
        registered = general.register_general()
    except InvalidWorkflow as exc:
        if any(p.row.split(".")[0] in EXPECTED for p in exc.problems):
            raise
        pytest.skip(f"another family's definition is invalid for now: {exc}")
    got = [w.key for w in registered]
    assert got.count("owner-info-cycle") == 1 and got.count("control-adoption") == 1
    for key in EXPECTED:
        assert got.count(key) == 1 and definitions.find(key) is not None, key
    assert len(set(got)) == len(got) >= 10
    assert [w.key for w in general.register_general()] == got                              # idempotent
    assert [w.key for w in register_mine()] == [r().key for r in (*general.GENERAL, *members.BUILDERS)]
    # a definition that spawns another names one that is registered
    known = {w.key for w in definitions.all_definitions()}
    assert {s.spawns for w in definitions.all_definitions() for s in w.steps if s.spawns} <= known


def test_workflow_definitions_lists_the_family(data, capsys, monkeypatch):
    from jason.cli import build_parser

    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("jason.commands._shared.data_dir", lambda args=None: data)
    args = build_parser().parse_args(["workflow", "--definitions", "--family", "members", "--json"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    for key in EXPECTED:
        assert key in out, key


# --- a run over the simplest one ---------------------------------------------------------------------------------------

ADMIN, MANAGER, SECRETARY, VISITOR = "A. Admin", "J. Manager", "S. Secretary", "V. Visitor"
PEOPLE = {ADMIN: {"administrator"}, MANAGER: {"manager"}, SECRETARY: {"secretary", "director"}, VISITOR: ()}
DAY = date(2099, 1, 12)


def roles_of(by):
    return PEOPLE.get(by, ())


def readers_for(data):
    return StoreReaders(data, community=object(), today=DAY)


class Community:
    """The few things the request reads ask of a profile: topic rules and senders (none)."""

    def topic_rules(self):
        return ()

    def senders(self):
        return ()


def store_a_request(data, ident=101):
    """One made-up records request in the PayHOA requests store, received 2099-01-05, so the classifying read has one to find."""
    import sqlite3

    data.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(data / "payhoa.db")
    con.execute("create table units(id integer, label text)")
    con.execute("create table requests(id integer, form_name text, unit_id integer, status text, created_at text, raw_json text)")
    con.execute("insert into units values (1, '101 Main St')")
    raw = {"createdAt": "2099-01-05T18:00:00Z", "comments": [], "answers": [
        {"question": {"label": "Title"}, "answer": "Records request"}, {"question": {"label": "Message"}, "answer": "Copies of the budget records"}]}
    con.execute("insert into requests values (?, 'General Request', 1, 'open', '2099-01-05T18:00:00Z', ?)", (ident, json.dumps(raw)))
    con.commit()
    con.close()


def test_a_run_of_the_form_library_review_starts_opens_and_a_person_attests_a_person_step(data):
    register_mine()
    out = api.start(data, "form-library-review", "period:2099", "Library review 2099", {}, ADMIN, today=DAY)
    rid = out["run"]["id"]
    assert out["run"]["state"] == "draft"
    api.open_run(data, rid, ADMIN, readers=readers_for(data), roles_of=roles_of, today=DAY)
    shown = api.show(data, rid, today=DAY)
    state = {s["id"]: s["state"] for s in shown["steps"]}
    assert state["form-library-review.1"] == "needs a person" and state["form-library-review.4"] == "needs a person"
    assert state["form-library-review.2"] == "not started" and shown["state"] == "active"
    # the right role, and a record: the administrator reads the Act's changes
    with pytest.raises(StepRefused, match="administrator"):
        api.attest(data, rid, "form-library-review.1", MANAGER, roles_of=roles_of, readers=readers_for(data), today=DAY, record="x")
    with pytest.raises(StepRefused, match="record"):
        api.attest(data, rid, "form-library-review.1", ADMIN, roles_of=roles_of, readers=readers_for(data), today=DAY)
    api.attest(data, rid, "form-library-review.1", ADMIN, roles_of=roles_of, readers=readers_for(data), today=DAY,
               record="2 forms stale since their as-of")
    api.open_run(data, rid, ADMIN, readers=readers_for(data), roles_of=roles_of, today=DAY)
    state = {s["id"]: s["state"] for s in api.show(data, rid, today=DAY)["steps"]}
    assert state["form-library-review.1"] == "done" and state["form-library-review.2"] == "needs a person"
    # a decision is the secretary's alone, and a step with no rule cannot be skipped by someone else
    assert state["form-library-review.3"] == "not started"
    with pytest.raises(StepRefused, match="skip"):
        api.skip(data, rid, "form-library-review.4", ADMIN, roles_of=roles_of, reason="none", readers=readers_for(data), today=DAY)
    assert api.verify(data, rid)["ok"]


def test_a_request_run_with_a_legal_clock_needs_yes_and_a_chosen_path_skips_the_others(data):
    register_mine()
    store_a_request(data)

    def readers():
        return StoreReaders(data, community=Community(), today=DAY)

    with pytest.raises(StepRefused, match="legal clock"):
        api.start(data, "respond-request", "request:101", "A records request", {"received_on": "2099-01-05"}, MANAGER, today=DAY)
    with pytest.raises(StepRefused, match="received_on"):
        api.start(data, "respond-request", "request:101", "A records request", {}, MANAGER, yes=True, today=DAY)
    rid = api.start(data, "respond-request", "request:101", "A records request", {"received_on": "2099-01-05"}, MANAGER,
                    yes=True, today=DAY)["run"]["id"]
    api.open_run(data, rid, MANAGER, readers=readers(), roles_of=roles_of, yes=True, today=DAY)
    # the classifying step is jason's check: it reads the stored request, and no person attests it
    assert {s["id"].split(".", 1)[1]: s["state"] for s in api.show(data, rid, today=DAY)["steps"]}["1"] == "done"
    with pytest.raises(StepRefused, match="done by its result"):
        api.attest(data, rid, "respond-request.1", MANAGER, roles_of=roles_of, readers=readers(), today=DAY, record="by hand")

    def act(fn, step, by=MANAGER, **more):
        return getattr(api, fn)(data, rid, f"respond-request.{step}", by, roles_of=roles_of, readers=readers(), today=DAY, **more)

    act("skip", "2", reason="the kind was not read as other")
    # the clock's authority is jason's check now: it reads the shelf and the documents, and no person attests it
    with pytest.raises(StepRefused, match="done by its result"):
        act("attest", "3", record="the authority recited")
    with pytest.raises(StepRefused, match="secretary"):
        act("skip", "4", by=VISITOR, reason="x")
    act("skip", "4", by=SECRETARY, reason="the authority read gave a clock")
    act("attest", "8", choice="staff")
    api.open_run(data, rid, MANAGER, readers=readers(), roles_of=roles_of, today=DAY)
    state = {s["id"].split(".", 1)[1]: s["state"] for s in api.show(data, rid, today=DAY)["steps"]}
    for n in ("10", "11", "12", "13", "14", "15", "16", "17", "18", "19"):
        assert state[n] == "skipped", n
    assert state["20"] == "needs a person" and state["8"] == "done"
    # the closing step needs the staff answer, and the skipped paths do not hold it
    assert state["22"] == "not started"
    act("attest", "20", record="answered in the thread")
    api.open_run(data, rid, MANAGER, readers=readers(), roles_of=roles_of, today=DAY)
    assert {s["id"].split(".", 1)[1]: s["state"] for s in api.show(data, rid, today=DAY)["steps"]}["22"] == "needs a person"
    # a legal step cannot be skipped
    with pytest.raises(StepRefused, match="cannot be skipped"):
        act("skip", "13", reason="no")
