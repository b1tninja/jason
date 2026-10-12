"""The property family of general workflow definitions (src/jason/workflows/defs/property.py; docs/workflows/property-safety-vendors.md).

The nine definitions are checked against the real registries (the approvals kinds, the job names, the procedures, and the
statutes on the shelf when it is here), against a table of what each should be (step count, kind, role), and with one small
run on a temporary data folder over made-up names ("A. Manager", "S. Secretary", 2099). No network, no profile.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import shelf_support

from jason.community import procedures
from jason.workflows import api, definitions
from jason.workflows import definitions_general as general
from jason.workflows.defs import property as prop
from jason.workflows.readers import CHECKS, JOBS
from jason.workflows.types import ClockBasis, Role, StepKind, parse_sop
from test_workflows_support import data  # noqa: F401 - the `data` fixture

KEYS = ("life-safety-period", "deficiency", "backflow-annual", "elevated-elements", "contract-notice-window",
        "improvement-request", "paint-cycle", "loss-claim", "maintenance-program")
SHELF = Path(__file__).resolve().parents[1] / "data"
KIND = {"P": StepKind.PERSON, "C": StepKind.CHECK, "J": StepKind.JOB, "PL": StepKind.PLAN, "D": StepKind.DECISION,
        "W": StepKind.WAIT, "B": StepKind.BRANCH}
ROLE = {"M": Role.MANAGER, "S": Role.SECRETARY, "PRES": Role.PRESIDENT, "J": Role.JASON}

# The page's step ids in its table's order, each with its kind and its role.
EXPECTED: dict[str, tuple[tuple[str, str, str], ...]] = {
    "life-safety-period": (
        ("read", "C", "J"), ("applies", "B", "M"), ("ask", "PL", "M"), ("send", "P", "M"), ("wait-reply", "W", "M"),
        ("proposal", "D", "S"), ("entry", "P", "M"), ("visit", "W", "M"), ("file", "P", "M"), ("read-report", "C", "J"),
        ("place", "P", "S"), ("authority", "P", "M"), ("deficiencies", "P", "M"), ("keep", "P", "M")),
    "deficiency": (
        ("propose", "P", "M"), ("confirm", "C", "J"), ("impairs", "C", "J"), ("route", "B", "M"), ("tell-insurer", "C", "J"),
        ("estimate", "W", "M"), ("repair-decision", "D", "S"), ("repair", "W", "M"), ("clear", "C", "J"), ("lift", "P", "M"),
        ("board-item", "C", "J")),
    "backflow-annual": (
        ("notice-in", "P", "M"), ("assemblies", "C", "J"), ("ask-program", "P", "M"), ("tester", "C", "J"), ("hire", "P", "M"),
        ("test", "W", "M"), ("receipt", "P", "M"), ("failed", "B", "M"), ("repair-retest", "W", "M"), ("file", "P", "M"),
        ("record", "P", "S"), ("next", "W", "M")),
    "elevated-elements": (
        ("reach", "B", "M"), ("facts", "P", "M"), ("due", "C", "J"), ("engage", "D", "S"), ("list", "W", "M"),
        ("inspect", "W", "M"), ("read", "P", "M"), ("threat", "B", "M"), ("preventive", "P", "M"), ("reserve", "P", "M"),
        ("keep", "P", "M"), ("next", "W", "M")),
    "contract-notice-window": (
        ("read", "P", "M"), ("confirm-term", "P", "M"), ("window", "C", "J"), ("owed", "C", "J"), ("licence", "P", "M"),
        ("statement", "C", "J"), ("review", "D", "S"), ("choice", "B", "M"), ("draft", "P", "M"), ("approve", "P", "PRES"),
        ("send", "P", "M"), ("ack", "W", "M"), ("renew", "P", "S"), ("transition", "P", "PRES")),
    "improvement-request": (
        ("receive", "P", "M"), ("track", "B", "M"), ("need", "P", "M"), ("ack", "P", "M"), ("complete", "P", "M"),
        ("missing", "P", "M"), ("wait-owner", "W", "M"), ("review", "P", "M"), ("agenda", "P", "M"), ("vote", "D", "S"),
        ("letter", "P", "M"), ("reconsider", "B", "M"), ("conditions", "P", "S"), ("work", "W", "M"), ("verify", "P", "M"),
        ("manual", "P", "M"), ("findings", "C", "J")),
    "paint-cycle": (
        ("refresh", "P", "M"), ("watch", "C", "J"), ("substitute", "D", "S"), ("dates", "P", "M"), ("scope", "P", "M"),
        ("bids", "W", "M"), ("award", "D", "S"), ("notice", "P", "M"), ("record", "P", "M"), ("doc", "P", "M"),
        ("request", "B", "M")),
    "loss-claim": (
        ("record", "P", "M"), ("history", "P", "M"), ("mitigate", "P", "M"), ("policy", "P", "M"), ("notify", "P", "M"),
        ("packet", "C", "J"), ("confirm-step", "P", "M"), ("guideline", "D", "S"), ("ask-owner", "P", "M"),
        ("outcome", "W", "M"), ("members", "B", "M"), ("close", "P", "M")),
    "maintenance-program": (
        ("standing", "C", "J"), ("adopt", "D", "S"), ("sync", "P", "M"), ("read", "P", "M"), ("ask", "P", "M"),
        ("licence", "P", "M"), ("vacate", "B", "M"), ("vacate-notice", "P", "M"), ("complaint", "P", "M"),
        ("renewal", "B", "M"), ("review", "P", "S")),
}
SOPS = {
    "life-safety-period.3": "duty-schedule#5", "life-safety-period.11": "duty-schedule#4", "backflow-annual.11": "duty-schedule#4",
    "contract-notice-window.1": "ingest#2", "contract-notice-window.2": "onboard#18", "contract-notice-window.3": "onboard#18",
    "contract-notice-window.14": "onboard#19",
}
LAW_CITES = {
    "life-safety-period": set(), "deficiency": set(), "backflow-annual": {"HSC 116800"},
    "elevated-elements": {"CIV 5551(l)", "CIV 5551(b)(1)", "CIV 5551(e)(5)(A)", "CIV 5551(e)(5)(F)", "CIV 5551(g)(1)", "CIV 5551(f)",
                          "CIV 5551(i)"},
    "contract-notice-window": {"CIV 5375"},
    "improvement-request": {"CIV 4765(a)", "CIV 4766(b)(1)", "CIV 4920(a)", "CIV 4765(a)(4)", "CIV 4765(a)(5)",
                            "CIV 714(e)(2)(B)", "CIV 4745(e)"},
    "paint-cycle": set(), "loss-claim": {"CIV 5810"}, "maintenance-program": {"CIV 4785(b)"},
}


# The seventeen steps that are read-only checks, with the read each names (src/jason/workflows/checks/property.py).
CHECK_STEPS = {
    "life-safety-period.1": "life-safety-standing", "life-safety-period.10": "life-safety-reports-read",
    "deficiency.2": "deficiency-confirmed", "deficiency.3": "deficiency-impairs-recorded", "deficiency.5": "deficiency-insurer-told",
    "deficiency.9": "deficiency-cleared", "deficiency.11": "deficiency-board-item", "backflow-annual.4": "backflow-tester",
    "elevated-elements.3": "elevated-due", "contract-notice-window.3": "contract-window", "paint-cycle.2": "paint-catalog",
    "loss-claim.6": "loss-packet", "backflow-annual.2": "backflow-assemblies", "contract-notice-window.4": "contract-owed",
    "contract-notice-window.6": "contract-statement", "improvement-request.17": "improvement-findings",
    "maintenance-program.1": "program-standing",
}


@pytest.fixture(autouse=True)
def fresh():
    from jason.workflows import checks

    checks.load_all()                                             # the reads a check step names register themselves
    definitions.reset()
    yield
    definitions.reset()


def built() -> dict[str, object]:
    return {w.key: w for w in (b() for b in prop.BUILDERS)}


def number(key: str, name: str) -> str:
    return f"{key}.{prop.ORDER[key].index(name) + 1}"


# --- the family -----------------------------------------------------------------------------------------------------

def test_the_nine_definitions_are_built_with_the_pages_keys_and_the_aggregator_finds_them():
    assert tuple(w.key for w in (b() for b in prop.BUILDERS)) == KEYS
    assert set(EXPECTED) == set(KEYS) == set(prop.ORDER) and prop.LEFT_OUT == ()
    from jason.workflows.defs import all_builders

    assert set(prop.BUILDERS) <= set(all_builders())
    assert all(w.family == "property" for w in built().values())


@pytest.mark.parametrize("key", KEYS)
def test_a_definition_has_the_pages_steps_in_order_with_their_kinds_and_roles(key):
    wf = built()[key]
    rows = EXPECTED[key]
    assert len(wf.steps) == len(rows) == len(prop.ORDER[key])
    assert tuple(n for n, _, _ in rows) == prop.ORDER[key]
    for i, (step, (name, kind, role)) in enumerate(zip(wf.steps, rows), start=1):
        assert step.id == f"{key}.{i}", name
        assert step.kind is KIND[kind] and step.role is ROLE[role], name
        assert step.title and step.why or step.record or step.command, name


@pytest.mark.parametrize("key", KEYS)
def test_it_validates_against_the_real_registries(key):
    wf = built()[key]
    problems = definitions.validate(wf, jobs=set(JOBS), workflows=set(KEYS), resolve_law=shelf_support.resolver(SHELF))
    assert problems == []
    assert definitions.drift([wf]) == []                       # every sop address names a step of an existing procedure


def test_the_sop_addresses_are_the_mapped_ones_and_exist():
    found = {s.id: s.sop for wf in built().values() for s in wf.steps if s.sop}
    assert found == SOPS
    for address in SOPS.values():
        key, index = parse_sop(address)
        proc = procedures.find(key)
        assert proc is not None and 1 <= index <= len(proc.steps)
    assert all(wf.procedure == "" for wf in built().values())  # the family has no Procedure row of its own yet


def test_only_a_registered_plan_kind_a_plan_step_and_no_job_or_check_beyond_the_registries():
    from jason.approvals import registry

    kinds = {k.key for k in registry.kinds()}
    plans = {s.id: s.plan_kind for wf in built().values() for s in wf.steps if s.kind is StepKind.PLAN}
    assert plans == {"life-safety-period.3": "gmail-drafts"} and set(plans.values()) <= kinds
    for wf in built().values():
        for s in wf.steps:
            assert not s.job or s.job in JOBS
            assert s.check is None or s.check.name in CHECKS
    assert not {s.id for wf in built().values() for s in wf.steps if s.kind is StepKind.JOB}
    checks = {s.id: s for wf in built().values() for s in wf.steps if s.kind is StepKind.CHECK}
    assert {i: s.check.name for i, s in checks.items()} == CHECK_STEPS
    assert all(s.role is Role.JASON and s.skip is None for s in checks.values())     # jason reads; nobody skips a read
    assert not any(s.check is not None for wf in built().values() for s in wf.steps if s.kind is not StepKind.CHECK)


def test_spawns_name_definitions_of_the_family_and_only_where_the_page_opens_a_child_run():
    spawning = {s.id: s.spawns for wf in built().values() for s in wf.steps if s.spawns}
    assert spawning == {"life-safety-period.13": "deficiency", "paint-cycle.11": "improvement-request",
                        "maintenance-program.10": "contract-notice-window"}
    assert set(spawning.values()) <= set(KEYS)


# A branch's paths: the steps that run on that path alone (the others are skipped when another path is chosen).
PATHS: dict[tuple[str, str], dict[str, tuple[str, ...]]] = {
    ("life-safety-period", "applies"): {"applies": ("ask", "send", "wait-reply", "proposal", "entry", "visit", "file", "read-report",
                                                    "place", "authority", "deficiencies", "keep"), "does-not-apply": ()},
    ("deficiency", "route"): {"impairs": ("tell-insurer", "lift"), "does-not-impair": ()},
    ("backflow-annual", "failed"): {"failed": ("repair-retest",), "passed": ()},
    ("elevated-elements", "reach"): {"reaches": ("facts", "due", "engage", "list", "inspect", "read", "threat", "preventive", "reserve",
                                                 "keep", "next"), "does-not-reach": ()},
    ("elevated-elements", "threat"): {"threat": ("preventive",), "none": ()},
    ("contract-notice-window", "choice"): {"end": ("draft", "approve", "send", "ack", "transition"), "renew": ("renew",)},
    ("improvement-request", "track"): {"ordinary": (), "accessibility": (), "solar": (), "charger": (), "rebuild": ()},
    ("improvement-request", "reconsider"): {"asked": (), "not-asked": ()},
    ("paint-cycle", "request"): {"request": (), "none": ()},
    ("loss-claim", "members"): {"yes": (), "no": ()},
    ("maintenance-program", "vacate"): {"yes": ("vacate-notice",), "no": ()},
    ("maintenance-program", "renewal"): {"renew": (), "none": ()},
}


def test_every_branch_has_the_paths_the_page_names_and_only_its_own_steps_on_each():
    found = {(wf.key, s.id.split(".")[0] and prop.ORDER[wf.key][int(s.id.split(".")[1]) - 1]): s for wf in built().values()
             for s in wf.steps if s.kind is StepKind.BRANCH}
    assert set(found) == set(PATHS)
    for (key, name), want in PATHS.items():
        got = {c.key: c.steps for c in found[(key, name)].choices}
        assert got == {k: tuple(number(key, n) for n in names) for k, names in want.items()}, (key, name)


# --- the clocks -----------------------------------------------------------------------------------------------------

def all_clocks(wf):
    return [(s.id, s.clock) for s in wf.steps if s.clock] + [(f"{wf.key} run", c) for c in wf.clocks]


@pytest.mark.parametrize("key", KEYS)
def test_a_law_clock_cites_exactly_the_sections_the_page_names_and_a_legal_step_has_no_skip(key):
    wf = built()[key]
    cites = {c.cite for _, c in all_clocks(wf) if c.basis is ClockBasis.LAW}
    assert cites == LAW_CITES[key]
    for s in wf.steps:
        if s.is_legal:
            assert s.skip is None, s.id
    assert wf.has_legal_clock() == bool(LAW_CITES[key])


def test_no_fire_code_regulation_is_a_law_clock_and_the_ones_the_page_cites_are_documents():
    cited = {}
    for wf in built().values():
        for sid, c in all_clocks(wf):
            if "CCR" in c.cite:
                cited[sid] = c
    assert {c.cite for c in cited.values()} == {"19 CCR 904(a)(1)", "19 CCR 904.2(j)", "19 CCR 904.2(c)", "19 CCR 904.2(k)",
                                                 "19 CCR 904.2(d)"}
    assert all(c.basis is ClockBasis.DOCUMENTS for c in cited.values())


def test_every_law_clock_cite_is_on_the_shelf_when_the_shelf_is_here():
    shelf_support.require(SHELF)
    resolve = shelf_support.resolver(SHELF)
    if resolve is None or resolve("CIV 5551(b)(1)") is None:
        pytest.skip("the authorities shelf is not here")
    for key, cites in LAW_CITES.items():
        for cite in cites:
            assert resolve(cite) is True, f"{key}: {cite}"


def test_a_contract_notice_window_has_both_edges_on_the_documents_and_the_notice_inside_them():
    wf = built()["contract-notice-window"]
    by = {s.id: s for s in wf.steps}
    opens, closes = by[number("contract-notice-window", "window")].clock, by[number("contract-notice-window", "review")].clock
    send = by[number("contract-notice-window", "send")].clock
    assert (opens.basis, opens.slot) == (ClockBasis.DOCUMENTS, "window_opens")
    assert (closes.basis, closes.slot) == (ClockBasis.DOCUMENTS, "window_closes") and send.slot == "window_closes"
    assert send.basis is ClockBasis.DOCUMENTS and "both edges" in send.label
    slots = {d.name: d for d in wf.dates}
    assert slots["window_closes"].after == "window_opens" and not any(d.required for d in wf.dates)
    # the management agreement's statement is a law clock counted back, and says it is the earliest day
    statement = by[number("contract-notice-window", "statement")].clock
    assert (statement.basis, statement.cite, statement.days) == (ClockBasis.LAW, "CIV 5375", -90)
    assert "earliest" in statement.label
    why = by[number("contract-notice-window", "statement")].why                     # the subject the read looks a reading up by
    assert "library-ID" in why and "subject not recognized" in why


def test_a_relocation_notice_has_the_laws_two_edges_labeled_earliest_and_latest():
    wf = built()["maintenance-program"]
    by = {s.id: s for s in wf.steps}
    first, last = by[number("maintenance-program", "vacate")].clock, by[number("maintenance-program", "vacate-notice")].clock
    assert (first.cite, first.slot, first.days) == ("CIV 4785(b)", "relocation_on", -30) and "earliest" in first.label
    assert (last.cite, last.slot, last.days) == ("CIV 4785(b)", "relocation_on", -15) and "latest" in last.label
    assert by[number("maintenance-program", "vacate-notice")].skip is None


def test_a_request_run_clocks_a_statute_day_only_where_a_person_sets_the_track_s_date():
    wf = built()["improvement-request"]
    assert [(c.cite, c.slot) for c in wf.clocks] == [("CIV 714(e)(2)(B)", "solar_by"), ("CIV 4745(e)", "charger_by")]
    required = [d.name for d in wf.dates if d.required]
    assert required == ["received_on"]                            # the others are set by track, never for an ordinary request
    assert wf.check_dates({"received_on": "2099-10-01"}) == []
    assert wf.check_dates({"received_on": "2099-10-01", "solar_by": "2099-09-01"})            # a day before receipt is refused


def test_a_deficiency_is_always_a_board_item_and_cannot_skip_it():
    wf = built()["deficiency"]
    item = wf.step(number("deficiency", "board-item"))
    assert item.skip is None and item.needs == (number("deficiency", "confirm"),)
    assert "every confirmed deficiency" in item.why
    route = wf.step(number("deficiency", "route"))
    paths = {c.key: c.steps for c in route.choices}
    assert paths["impairs"] == (number("deficiency", "tell-insurer"), number("deficiency", "lift")) and paths["does-not-impair"] == ()


# --- privacy and the boundary ---------------------------------------------------------------------------------------

def test_a_loss_or_a_request_is_about_an_opaque_subject_and_asks_for_no_unit_or_name():
    wf = built()
    assert wf["loss-claim"].subject == "incident" and wf["improvement-request"].subject == "request"
    for key in ("loss-claim", "improvement-request"):
        for s in wf[key].steps:
            title = s.title.lower()
            assert not any(w in title for w in ("owner's name", "address", "street")), s.id
    first = wf["improvement-request"].step("improvement-request.1")
    assert "never an address or a name" in first.record
    assert "never an address or a name" in wf["loss-claim"].step("loss-claim.1").record


def test_it_names_no_association_and_no_amount():
    text = " ".join(repr(wf) for wf in built().values()).lower() + " ".join(prop.WANTED).lower()
    for word in ("mystique", "sacramento", "$"):
        assert word not in text


def test_wanted_is_a_tuple_of_strings_each_with_a_kind_and_a_purpose():
    assert isinstance(prop.WANTED, tuple) and prop.WANTED and all(isinstance(w, str) for w in prop.WANTED)
    assert all(w.split(":", 1)[0] in {"check", "job", "plan", "template", "command", "role"} and " -- " in w for w in prop.WANTED)
    assert not (set(CHECKS) | set(JOBS)) & {w.split(":", 1)[1].split(" -- ")[0] for w in prop.WANTED}
    wanted_checks = {w.split(":", 1)[1].split(" -- ")[0] for w in prop.WANTED if w.startswith("check:")}
    assert wanted_checks == {"improvement-findings-conflicts", "program-standing-catalog", "deliverable-on-file"}
    assert not wanted_checks & set(CHECK_STEPS.values())
    for step in (s for wf in built().values() for s in wf.steps if s.id in CHECK_STEPS):
        assert "(check:" not in step.why and "check:" + CHECK_STEPS[step.id] not in step.why, step.id    # no becomes-text left


def test_the_module_adds_nothing_to_the_readers_registries():
    import sys

    before = (dict(CHECKS), dict(JOBS))
    import importlib

    importlib.reload(sys.modules["jason.workflows.defs.property"])
    assert (dict(CHECKS), dict(JOBS)) == before
    assert not {m for m in sys.modules if m.startswith("jason.workflows.defs.property")} - {"jason.workflows.defs.property"}


# --- registration ---------------------------------------------------------------------------------------------------

def test_register_general_registers_all_nine_beside_the_existing_two():
    got = [w.key for w in general.register_general()]
    assert {"owner-info-cycle", "control-adoption", *KEYS} <= set(got)
    for key in KEYS:
        assert definitions.find(key) is not None


def test_register_general_checks_the_family_against_a_shelf_that_refuses_a_cite():
    with pytest.raises(Exception) as err:
        general.register_general(resolve_law=lambda cite: False)
    assert "does not resolve" in str(err.value)


# --- one run, end to end --------------------------------------------------------------------------------------------

MANAGER, SECRETARY = "A. Manager", "S. Secretary"
ROLES = {MANAGER: {"manager"}, SECRETARY: {"secretary", "director"}}
DAY = date(2099, 6, 2)


def seed_register(data, ident, acts):
    """A made-up register row with the acts a person has recorded so far (the register is the only store the checks read)."""
    import json

    from jason.tasks import deficiencies

    path = data / deficiencies.STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"id": ident, "system": "alarm", "buildings": [], "location": "", "device": "", "comment": "", "report": {}, "acts": acts}
    path.write_text(json.dumps({"deficiencies": [row]}), encoding="utf-8")


def seed_board_item(data, ident):
    from jason.community.board_items import BoardItem, ItemCategory
    from jason.tasks import board_items, deficiencies

    board_items.save(data, [BoardItem(deficiencies.item_id(ident), "A deficiency", "", "Decide", ItemCategory.SAFETY)])


def test_a_deficiency_run_follows_the_register_from_proposed_to_the_board_item_with_the_insurer_path_skipped(data):
    from jason.workflows.readers import StoreReaders

    general.register_general()
    n = lambda name: number("deficiency", name)               # noqa: E731
    roles_of = lambda by: ROLES.get(by, ())                   # noqa: E731
    readers = StoreReaders(data, today=DAY)
    ident = "def-0a1b2c3d"
    seed_register(data, ident, [{"act": "proposed", "by": "jason", "at": "2099-06-01T10:00:00+00:00"}])
    out = api.start(data, "deficiency", ident, "Waterflow switch, Bldg. 1", {}, MANAGER, today=DAY)
    rid = out["run"]["id"]
    api.open_run(data, rid, MANAGER, readers=readers, roles_of=roles_of, today=DAY)

    def state(name):
        return next(s for s in api.show(data, rid, today=DAY, readers=readers)["steps"] if s["id"] == n(name))["state"]

    def message(name):
        return next(s for s in api.show(data, rid, today=DAY, readers=readers)["steps"] if s["id"] == n(name))["reason"]

    def again():
        api.open_run(data, rid, MANAGER, readers=readers, roles_of=roles_of, today=DAY)

    assert state("propose") == "needs a person" and state("confirm") == "not started"
    api.attest(data, rid, n("propose"), MANAGER, roles_of=roles_of, record="the proposed row def-0a1b2c3d", readers=readers, today=DAY)
    again()
    assert state("confirm") == "failed" and "only proposed" in message("confirm")                                              # a check: the register has no confirmation yet
    with pytest.raises(Exception, match="check step"):
        api.attest(data, rid, n("confirm"), MANAGER, roles_of=roles_of, record="confirmed", readers=readers, today=DAY)

    # a person records the acts in the register (jason life-safety ...); the run follows when it is opened again
    acts = [{"act": "proposed", "by": "jason", "at": "2099-06-01T10:00:00+00:00"},
            {"act": "confirmed", "by": "A. Manager", "at": "2099-06-02T10:00:00+00:00"}]
    seed_register(data, ident, acts)
    again()
    assert state("confirm") == "done" and state("impairs") == "failed"
    assert "A. Manager" not in message("confirm")                                   # who acted is not in what the run shows
    acts.append({"act": "does not impair", "by": "A. Manager", "at": "2099-06-02T10:05:00+00:00"})
    seed_register(data, ident, acts)
    again()
    assert state("impairs") == "done"
    api.attest(data, rid, n("route"), MANAGER, roles_of=roles_of, choice="does-not-impair", readers=readers, today=DAY)
    again()

    assert state("tell-insurer") == "skipped" and state("lift") == "skipped"      # the path the answer did not take
    assert state("estimate") in ("needs a person", "waiting")
    assert state("board-item") == "failed"                                           # confirmed, but the board has no item yet
    seed_board_item(data, ident)
    again()
    assert state("board-item") == "done"
    view = api.show(data, rid, today=DAY, readers=readers)
    assert view["definition"] == "deficiency" and view["state"] != "done"
