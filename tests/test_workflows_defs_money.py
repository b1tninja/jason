"""The money family of general workflow definitions (src/jason/workflows/defs/money.py; docs/workflows/money.md, section 2, and the
three screen pages monthly-review, county-tax-cycle, and delinquency-process).

Everything here is plainly fake ("A. Manager", 2099 dates, "123 Main St"). The expected step tables are written out below from
the page, not read back from the module: each row is (the page's word for the step, its kind here, its role). A page row of
kind ``check`` is a ``check`` step (role jason) when ``jason.workflows.checks.money`` builds its read, else a ``person`` step
whose ``why`` says what it becomes; a page row of kind ``job`` is a ``person`` step: a money job is only a descriptor of a
command a person runs (``jason.workflows.jobs``), so no step names one.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
import shelf_support

from jason.approvals import registry
from jason.workflows import api, definitions, jobs, store
from jason.workflows import definitions_general as general
from jason.workflows.defs import all_builders, money
from jason.workflows.readers import CHECKS, JOBS, StoreReaders
from jason.workflows.types import CheckResult, ClockBasis, Elapsed, Repeat, Role, StepKind as K, StepRefused, Visibility, parse_sop
from test_workflows_support import data  # noqa: F401 - the `data` fixture

P, C, J, PL, D, W, B = K.PERSON, K.CHECK, K.JOB, K.PLAN, K.DECISION, K.WAIT, K.BRANCH
M, TR, SE, PR, DI, AN = (Role.MANAGER, Role.TREASURER, Role.SECRETARY, Role.PRESIDENT, Role.DIRECTOR, Role.ANYONE)
JA = Role.JASON

SHELF = Path(__file__).resolve().parents[1] / "data"

EXPECTED = {
    "bill-attach": (
        ("snap", C, JA), ("fetch", P, M), ("queue", C, JA), ("srcs", P, M), ("dry", P, M), ("plan", PL, TR),
        ("work", P, M), ("inv", P, M), ("hand", P, M),
    ),
    "payment-investigation": (
        ("class", C, JA), ("tried", C, JA), ("rule", P, M), ("proof", P, TR), ("keep", P, TR), ("redry", P, M),
        ("attach", PL, TR), ("policy", D, SE), ("mail", W, M), ("out", B, M), ("esc", P, TR),
    ),
    "monthly-review": (
        ("sync", P, M), ("attach", W, M), ("recon", C, JA), ("stmt", C, JA), ("bva", C, JA), ("ie", C, JA),
        ("regs", C, JA), ("inv", P, TR), ("xfer", P, TR), ("path", B, TR), ("rev", P, DI), ("rat", D, SE),
        ("rec", P, SE),
    ),
    "delinquency-account": (
        ("det", P, TR), ("chg", P, TR), ("app", P, TR), ("pol", P, M), ("notice", PL, M), ("plan", W, M),
        ("meet", D, SE), ("mc", P, M), ("wait30", W, M), ("floor", P, TR), ("lienvote", D, SE), ("rec", P, PR),
        ("copy", P, M), ("pay", B, M), ("rel", P, M), ("enf", W, M), ("adr", P, M), ("fclose", D, SE),
        ("alt", D, SE), ("hand", P, M), ("off", D, SE), ("close", P, M),
    ),
    "fiscal-year": (
        ("open", P, M), ("win", C, JA), ("R1", C, JA), ("R2", D, SE), ("R3", P, M), ("R4", D, SE), ("R5", D, SE),
        ("B1", P, TR), ("B2", C, JA), ("B3", B, TR), ("B4", B, TR), ("B5", D, SE), ("B6", D, SE), ("B7", P, M),
        ("D1", P, M), ("D2", P, M), ("D3", P, TR), ("D4", C, JA), ("D5", C, JA), ("D6", D, SE), ("D7", W, M),
        ("D8", P, M), ("D9", P, M), ("D10", P, AN), ("D11", P, M), ("D12", P, M), ("D13", W, M), ("D14", P, M),
        ("F1", B, TR), ("F2", D, SE), ("F3", P, TR), ("F4", P, M), ("C1", P, M),
    ),
    "reserve-borrowing": (
        ("spend", B, TR), ("sig", P, TR), ("appr", D, SE), ("note", C, JA), ("fnd", D, SE), ("rst", W, TR),
        ("late", D, SE), ("sa", D, SE), ("lit", P, M),
    ),
    "insurance-renewal": (
        ("due", C, JA), ("quote", P, M), ("min", C, JA), ("dec", D, SE), ("bind", P, M), ("chg", B, M), ("mem", P, M),
        ("sum", C, JA), ("read", C, JA), ("ovr", C, JA),
    ),
    "county-tax-cycle": (
        ("sync", P, M), ("stand", C, JA), ("bill", C, JA), ("pdf", P, TR), ("mail", P, TR), ("due", W, TR),
        ("pay", P, TR), ("rcpt", P, TR), ("att", PL, TR), ("cls", C, JA),
    ),
}
"""Step counts (the page's tables): 9, 11, 13, 22, 33, 9, 10, 10."""

COUNTS = {"bill-attach": 9, "payment-investigation": 11, "monthly-review": 13, "delinquency-account": 22, "fiscal-year": 33,
          "reserve-borrowing": 9, "insurance-renewal": 10, "county-tax-cycle": 10}


def build(key: str):
    for b in money.BUILDERS:
        wf = b()
        if wf.key == key:
            return wf
    raise KeyError(key)


def sid(key: str, word: str) -> str:
    return money.step_id(key, word)


ALL = tuple(EXPECTED)


@pytest.fixture(autouse=True)
def fresh():
    definitions.reset()
    yield
    definitions.reset()


def shelf_resolver():
    shelf_support.require(SHELF)
    resolve = shelf_support.resolver(SHELF)
    if resolve is None or resolve("CIV 5500") is not True:
        pytest.skip("the statutes are not on the authorities shelf here")
    return resolve


# --- the tables ---------------------------------------------------------------------------------------------------------

def test_the_expected_tables_match_the_page_counts():
    assert {k: len(v) for k, v in EXPECTED.items()} == COUNTS
    assert tuple(EXPECTED) == tuple(sorted(EXPECTED, key=list(COUNTS).index))


@pytest.mark.parametrize("key", ALL)
def test_each_definition_has_the_steps_kinds_and_roles_of_the_page(key):
    wf = build(key)
    assert (wf.key, wf.family) == (key, "money")
    assert len(wf.steps) == COUNTS[key]
    assert [(s.kind, s.role) for s in wf.steps] == [(k, r) for _, k, r in EXPECTED[key]]
    assert [s.id for s in wf.steps] == [f"{key}.{i}" for i in range(1, COUNTS[key] + 1)]       # <key>.<n>, in the page's order
    assert money.table_ids(key) == {w: f"{key}.{i}" for i, (w, _, _) in enumerate(EXPECTED[key], 1)}
    assert all(isinstance(s.role, Role) for s in wf.steps)


@pytest.mark.parametrize("key", ALL)
def test_titles_and_whys_are_words_and_ids_are_unique(key):
    wf = build(key)
    assert wf.title and wf.subject
    assert len({s.id for s in wf.steps}) == len(wf.steps)
    assert all(s.title.strip() for s in wf.steps)
    assert not any(s.why != s.why.strip() for s in wf.steps)


def test_the_keys_are_the_pages_and_the_family_is_the_builders_with_the_delinquency_account_held():
    assert set(money.KEYS) == set(COUNTS)
    assert [b().key for b in money.BUILDERS] == list(COUNTS) and money.LEFT_OUT == ()
    held = [b().key for b in money.BUILDERS if b().visibility is Visibility.HELD]
    assert held == ["delinquency-account"] and build("delinquency-account").held_title == "A delinquent account"


# --- validity against the real registries ----------------------------------------------------------------------------------

@pytest.mark.parametrize("key", ALL)
def test_it_validates_against_the_real_registries(key):
    wf = build(key)
    assert definitions.validate(wf, jobs=set(JOBS)) == []                       # the approvals kinds, from the real registry
    assert definitions.validate(wf, plan_kinds={k.key for k in registry.kinds()}, jobs=set(JOBS)) == []


@pytest.mark.parametrize("key", ALL)
def test_every_law_clock_resolves_on_the_shelf(key):
    resolve = shelf_resolver()
    wf = build(key)
    assert definitions.validate(wf, jobs=set(JOBS), resolve_law=resolve) == []
    cites = [s.clock.cite for s in wf.steps if s.clock and s.clock.basis is ClockBasis.LAW] + [c.cite for c in wf.clocks if c.basis is ClockBasis.LAW]
    assert all(resolve(c) is True for c in cites)


BUILT = {
    "bill-attach": {"snap": "bill-snapshot-fresh", "queue": "bill-queue-read"},
    "payment-investigation": {"class": "payee-class-read", "tried": "stores-tried-read", "mail": "bill-mail-arrived"},
    "monthly-review": {"attach": "bill-handed", "recon": "review-reconciliations", "stmt": "review-statements", "bva": "review-budget",
                       "ie": "review-income-expense", "regs": "review-registers"},
    "fiscal-year": {"win": "fiscal-window", "R1": "reserve-study-due", "B2": "reserve-plan-match", "D4": "disclosure-insurance-summary",
                    "D5": "disclosure-reserve-summary", "D13": "disclosure-delivery-read"},
    "reserve-borrowing": {"note": "reserve-notice", "rst": "reserve-restored"},
    "insurance-renewal": {"due": "insurance-due", "min": "insurance-limits", "sum": "insurance-summary", "read": "insurance-changed",
                          "ovr": "insurance-answer"},
    "county-tax-cycle": {"stand": "tax-standing", "bill": "tax-bill-files", "cls": "tax-years-closed"},
}
"""The twenty-seven reads (jason.workflows.checks.money) and the step each one is the check of: a check step, or a wait step the
read ends. No branch names a read: ``insurance-renewal.chg`` is the manager's answer, with ``read`` a suggestion before it."""


@pytest.mark.parametrize("key", ALL)
def test_each_check_a_step_names_is_a_registered_read_and_no_step_names_a_job(key):
    from jason.workflows import checks

    checks.load_all()
    wf = build(key)
    named = {s.id: getattr(s.check, "name", None) for s in wf.steps if s.check is not None}
    assert named == {money.step_id(key, word): name for word, name in BUILT.get(key, {}).items()}
    assert all(name in CHECKS for name in named.values())
    assert not [s.id for s in wf.steps if s.kind is J or s.job]
    assert all(s.check is not None for s in wf.steps if s.kind is C)                  # a check step names its read
    assert all(s.role is JA for s in wf.steps if s.kind is C)
    assert {s.plan_kind for s in wf.steps if s.plan_kind} <= {"payhoa-attach-bills", "payhoa-mailroom-send"}
    assert {s.plan_kind for s in wf.steps if s.plan_kind} <= {k.key for k in registry.kinds()}


def test_it_adds_no_job_and_what_it_still_wants_is_not_there_yet_while_what_it_built_is_no_longer_wanted():
    from jason.workflows import checks

    checks.load_all()
    names = {w.split(":")[0].split(" ", 1)[1] for w in money.WANTED}
    built = {name for words in BUILT.values() for name in words.values()}
    assert len(built) == 27
    assert not names & set(CHECKS) and not names & set(JOBS)
    assert built <= set(CHECKS) and not built & names


@pytest.mark.parametrize("key", ALL)
def test_a_legal_step_has_no_skip_rule_and_a_branch_names_its_paths(key):
    wf = build(key)
    assert all(s.skip is None for s in wf.steps if s.is_legal)
    assert all(s.choices for s in wf.steps if s.kind is B)
    ids = {s.id for s in wf.steps}
    assert all(x in ids for s in wf.steps for c in s.choices for x in c.steps)
    assert all(x in ids for ph in wf.phases for x in ph.steps)


@pytest.mark.parametrize("key", ALL)
def test_the_sop_addresses_it_names_exist(key):
    from jason.community.procedures import find

    wf = build(key)
    assert definitions.drift([wf]) == []
    for s in wf.steps:
        if s.sop:
            name, index = parse_sop(s.sop)
            assert 1 <= index <= len(find(name).steps)
    assert not wf.procedure or find(wf.procedure) is not None


def test_the_page_maps_no_money_procedure_so_none_is_named():
    """money.md section 1: no Procedure row covers the six tasks. When one is written, its address is added to the steps."""
    for key in ALL:
        wf = build(key)
        assert wf.procedure == "" and not [s.id for s in wf.steps if s.sop]


def test_wanted_lists_every_name_a_why_asks_for_and_nothing_else():
    asked = set()
    for key in ALL:
        for s in build(key).steps:
            asked |= {f"{k} {name}" for k, name in re.findall(r"wanted: (check|job|plan) ([\w-]+)", s.why)}
    listed = {w.split(":")[0] for w in money.WANTED}
    registered = {a for a in asked if a.startswith("job ") and a.split()[1] in JOBS}        # a described job (jobs.READY) is not wanted
    assert listed == asked - registered
    assert {a.split()[1] for a in registered} == {d.name for d in jobs.DESCRIPTORS if d.family == "money"}
    assert {a.split()[1] for a in listed if a.startswith("job ")} == {
        "bill-sources-read", "tax-documents-keep", "books-sync", "packet-build"} <= set(jobs.UNDESCRIBED)
    assert len(money.WANTED) == len(listed)
    assert all(re.match(r"^(check|job|plan) [\w-]+: .+", w) for w in money.WANTED)


@pytest.mark.parametrize("key", ALL)
def test_a_person_step_made_of_a_check_or_job_says_what_it_becomes(key):
    for s in build(key).steps:
        if "wanted:" in s.why:
            assert s.kind in (P, W, B, PL)
            assert re.search(r"becomes a (check|job|plan) step when|a read of \S+ will end it", s.why), s.id


# --- the clocks -----------------------------------------------------------------------------------------------------------

def test_the_county_tax_clocks_are_the_bills_never_the_law():
    wf = build("county-tax-cycle")
    clocks = [s.clock for s in wf.steps if s.clock] + list(wf.clocks)
    assert clocks and not [c for c in clocks if c.basis is ClockBasis.LAW]
    assert {c.basis for c in clocks} <= {ClockBasis.DOCUMENTS, ClockBasis.PROPOSED_POLICY}
    assert [c.basis for c in wf.clocks] == [ClockBasis.DOCUMENTS] * 4
    assert all("county's bill" in c.label for c in wf.clocks)
    assert "RTC" not in repr(wf) and "Revenue and Taxation" in wf.step(sid("county-tax-cycle", "due")).clock.label
    assert not wf.has_legal_clock()
    assert wf.check_dates({}) == []                                          # every installment date is optional until the bill is read


def test_a_date_jason_adds_a_statutes_days_to_says_so():
    for key in ALL:
        wf = build(key)
        computed = [c for c in (*[s.clock for s in wf.steps if s.clock], *wf.clocks)
                    if c and c.basis is ClockBasis.LAW and c.slot and c.days]
        for c in computed:
            assert money.COMPUTED in c.label
    assert money.COMPUTED == "computed by jason from the statute's day-count, the earliest day"


def test_the_delinquency_clocks_are_the_statutes_day_counts():
    wf = build("delinquency-account")
    want = {"wait30": ("CIV 5660", "notice_mailed", 30), "copy": ("CIV 5675(e)", "recorded_on", 10),
            "rel": ("CIV 5685(a)", "paid_on", 21), "enf": ("CIV 5700(a)", "recorded_on", 30),
            "plan": ("CIV 5665(b)", "notice_mailed", 15)}
    for word, (cite, slot, days) in want.items():
        c = wf.step(sid("delinquency-account", word)).clock
        assert (c.basis, c.cite, c.slot, c.days) == (ClockBasis.LAW, cite, slot, days), word
    assert (wf.clocks[0].cite, wf.clocks[0].slot, wf.clocks[0].days) == ("CIV 5665(b)", "request_postmarked", 45)
    assert wf.step(sid("delinquency-account", "wait30")).elapsed is Elapsed.ENDS
    assert wf.has_legal_clock() and all(not d.required for d in wf.dates)


def test_the_fiscal_year_clocks():
    wf = build("fiscal-year")
    f4 = wf.step(sid("fiscal-year", "F4")).clock
    assert (f4.basis, f4.cite, f4.slot, f4.days) == (ClockBasis.LAW, "CIV 5305", "fiscal_year_end", 120)
    win = wf.step(sid("fiscal-year", "win")).clock
    assert (win.cite, win.slot, win.days) == ("CIV 5300(a)", "fiscal_year_end", -90)
    assert wf.step(sid("fiscal-year", "D12")).clock.cite == "CIV 5320(a)"
    assert wf.step(sid("fiscal-year", "B7")).clock.cite == "CIV 5615"
    assert [d.name for d in wf.dates if d.required] == ["fiscal_year_end"]
    assert wf.step(sid("fiscal-year", "B6")).clock.basis is ClockBasis.PROPOSED_POLICY       # the law is silent on the day
    assert wf.check_dates({}) == ["date fiscal_year_end is required"]


def test_the_reserve_borrowing_restoration_is_a_year_from_the_transfer():
    wf = build("reserve-borrowing")
    c = wf.step(sid("reserve-borrowing", "rst")).clock
    assert (c.basis, c.cite, c.slot) == (ClockBasis.LAW, "CIV 5515(d)", "transfer_on") and c.days in (365, 366)
    assert wf.step(sid("reserve-borrowing", "rst")).kind is W and wf.step(sid("reserve-borrowing", "rst")).elapsed is Elapsed.OVERDUE


def test_the_insurance_window_is_a_proposed_number_and_the_notice_is_the_laws():
    wf = build("insurance-renewal")
    due = wf.step(sid("insurance-renewal", "due")).clock
    assert (due.basis, due.slot, due.days) == (ClockBasis.PROPOSED_POLICY, "term_end", -90) and "proposed" in due.label
    assert wf.step(sid("insurance-renewal", "mem")).clock.cite == "CIV 5810"


def test_a_proposed_number_is_labeled_proposed():
    for key in ALL:
        for s in build(key).steps:
            if s.clock and s.clock.basis is ClockBasis.PROPOSED_POLICY:
                assert "proposed" in s.clock.label.lower(), s.id


# --- the monthly review's three paths --------------------------------------------------------------------------------------

def test_the_monthly_review_has_the_boards_the_directors_and_the_subcommittee_paths_and_the_secretary_ratifies():
    wf = build("monthly-review")
    path = wf.step(sid("monthly-review", "path"))
    assert [c.key for c in path.choices] == ["meeting", "every-director", "subcommittee"]
    rat, rev, rec = (wf.step(sid("monthly-review", w)) for w in ("rat", "rev", "rec"))
    by = {c.key: c.steps for c in path.choices}
    assert by["meeting"] == () and by["every-director"] == by["subcommittee"] == (rat.id,)
    assert (rat.kind, rat.role, rat.clock.cite, rat.clock.slot) == (D, SE, "CIV 5501", "next_meeting")
    assert rev.repeat is Repeat.PER_ITEM and rev.role is DI and rev.record and rev.needs == (path.id,)
    assert (rec.role, set(rec.needs)) == (SE, {rev.id, rat.id})
    for word, cite in (("recon", "CIV 5500(a)"), ("stmt", "CIV 5500(d)"), ("bva", "CIV 5500(c)"), ("ie", "CIV 5500(e)"),
                       ("regs", "CIV 5500(f)")):
        s = wf.step(sid("monthly-review", word))
        assert (s.clock.basis, s.clock.cite, s.role) == (ClockBasis.LAW, cite, JA) and s.skip is None           # each is a read now
    assert wf.step(sid("monthly-review", "xfer")).clock.cite == "CIV 5502(a)"
    assert [d.name for d in wf.dates] == ["month_end", "next_meeting"] and [d.required for d in wf.dates] == [True, False]


# --- the other branches and the plans ------------------------------------------------------------------------------------

def test_a_payment_investigation_has_the_five_outcomes_and_the_paths_they_open():
    wf = build("payment-investigation")
    out = wf.step(sid("payment-investigation", "out"))
    assert {c.key for c in out.choices} == {"attached-bill", "attached-receipt-only", "not-our-bill", "waiting-for-mail", "escalated"}
    paths = {c.key: {wf.step(x).id for x in c.steps} for c in out.choices}
    ids = money.table_ids("payment-investigation")
    assert paths["attached-receipt-only"] == {ids["policy"]} and paths["waiting-for-mail"] == {ids["mail"]}
    assert paths["escalated"] == {ids["esc"]} and paths["attached-bill"] == paths["not-our-bill"] == set()
    assert wf.step(ids["attach"]).plan_kind == "payhoa-attach-bills"
    assert wf.step(ids["policy"]).role is SE and wf.step(ids["mail"]).kind is W


def test_bill_attach_plans_the_attach_with_the_registered_kind_and_hands_over_before_the_review():
    wf = build("bill-attach")
    plan = wf.step(sid("bill-attach", "plan"))
    assert (plan.kind, plan.plan_kind, plan.role) == (PL, "payhoa-attach-bills", TR)
    assert wf.step(sid("bill-attach", "snap")).skip is None and wf.step(sid("bill-attach", "hand")).skip is None
    assert wf.step(sid("bill-attach", "hand")).clock.basis is ClockBasis.PERSON and wf.step(sid("bill-attach", "hand")).clock.slot == "review_on"
    assert [d.required for d in wf.dates] == [False] and wf.check_dates({}) == []
    assert not wf.has_legal_clock()


def test_a_mailed_notice_is_a_mailroom_plan_and_the_votes_are_the_secretarys():
    wf = build("delinquency-account")
    ids = money.table_ids("delinquency-account")
    assert (wf.step(ids["notice"]).kind, wf.step(ids["notice"]).plan_kind) == (PL, "payhoa-mailroom-send")
    for word in ("lienvote", "fclose", "meet"):
        assert wf.step(ids[word]).kind is D and wf.step(ids[word]).role is SE
    assert wf.step(ids["lienvote"]).skip is None and wf.step(ids["fclose"]).skip is None
    assert wf.step(ids["rec"]).role is PR and set(wf.step(ids["rec"]).needs) == {ids["lienvote"]}      # the vote and the recording are two steps
    assert {c.key for c in wf.step(ids["pay"]).choices} == {"paid", "unpaid"}


def test_the_fiscal_year_branches_the_increase_and_the_reviewed_statement():
    wf = build("fiscal-year")
    ids = money.table_ids("fiscal-year")
    b3 = {c.key: c.steps for c in wf.step(ids["B3"]).choices}
    assert b3 == {"increase": (ids["B4"], ids["B5"], ids["B7"]), "no-increase": ()}
    assert {c.key: c.steps for c in wf.step(ids["B4"]).choices} == {"within-limit": (), "over-limit": (ids["B5"],)}
    assert {c.key: c.steps for c in wf.step(ids["F1"]).choices} == {"applies": (ids["F2"], ids["F3"], ids["F4"]), "does-not-apply": ()}
    assert wf.step(ids["D6"]).role is SE and wf.step(ids["D6"]).kind is D           # the board's statements, entered by a person
    assert set(wf.step(ids["C1"]).needs) == {ids["D14"], ids["F4"]}


# --- registering ---------------------------------------------------------------------------------------------------------

def test_register_general_registers_them_beside_the_existing_two_with_the_delinquency_account_held():
    assert definitions.find("bill-attach") is None                           # importing registered nothing
    first = general.register_general()
    keys = [w.key for w in first]
    assert keys[:2] == ["owner-info-cycle", "control-adoption"]
    mine = [b().key for b in money.BUILDERS]
    assert all(k in keys for k in mine)
    assert definitions.find("delinquency-account").visibility is Visibility.HELD
    assert [k for k in keys if k in COUNTS] == mine
    again = general.register_general()
    assert [w.key for w in again] == keys
    assert {b().key for b in all_builders()} >= set(mine)


def test_register_general_checks_the_money_rows_against_the_registries():
    from jason.workflows.types import InvalidWorkflow

    with pytest.raises(InvalidWorkflow) as bad:
        general.register_general(plan_kinds={"owner-info-tags"})
    assert "payhoa-attach-bills" in str(bad.value) or "plan kind" in str(bad.value)
    with pytest.raises(InvalidWorkflow) as bad:
        general.register_general(resolve_law=lambda cite: cite != "CIV 5300(a)")
    assert "CIV 5300(a)" in str(bad.value)


def test_the_held_definition_validates_and_registers():
    wf = money.delinquency_account()
    assert definitions.validate(wf, jobs=set(JOBS)) == []
    assert definitions.register(wf, jobs=set(JOBS)) is wf and definitions.find("delinquency-account") is wf
    assert wf.subject == "account" and "executive" in money.__doc__.lower() and not any(s.public_title for s in wf.steps)


def test_the_definitions_name_no_association_and_no_parcel_or_person():
    for key in ALL:
        text = repr(build(key)).lower()
        for word in ("mystique", "example village", "123 main", "apn 0"):
            assert word not in text, (key, word)
        assert not re.search(r"\b\d{3}-\d{3}-\d{3}", text), key


def test_importing_the_module_loads_nothing_beyond_the_engine_types():
    import subprocess
    import sys

    code = ("import sys\n"
            "import jason.workflows.types, jason.workflows.readers\n"
            "before = set(sys.modules)\n"
            "import jason.workflows.defs.money\n"
            "print(sorted(set(sys.modules) - before))\n")
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1] == "['jason.workflows.defs', 'jason.workflows.defs.money']"


# --- one run, the simplest definition ---------------------------------------------------------------------------------------

MANAGER, TREASURER_, SECRETARY_ = "A. Manager", "T. Treasurer", "S. Secretary"
ROLES = {MANAGER: {"manager"}, TREASURER_: {"treasurer", "director"}, SECRETARY_: {"secretary", "director"}}
DAY = date(2099, 1, 5)


def roles_of(by):
    return ROLES.get(by, ())


def drive(data, key, word, by, **more):
    return api.attest(data, RID[0], money.step_id(key, word), by, roles_of=roles_of, readers=StoreReaders(data), today=DAY, **more)


RID = [""]


def passing(monkeypatch, *names):
    """The named reads answer ok, so a run can be driven without the stores they read (their own tests read the stores)."""
    for name in names:
        monkeypatch.setitem(CHECKS, name, lambda r, v, i="", n=name: CheckResult(True, (), f"{n} read"))


def _insurance_run(data, monkeypatch, suggestion):
    """An insurance-renewal run driven to the question 'did coverage change or lapse', the read having said ``suggestion``."""
    key = "insurance-renewal"
    passing(monkeypatch, "insurance-due", "insurance-limits", "insurance-summary")
    monkeypatch.setitem(CHECKS, "insurance-changed", lambda r, v, i="": (
        CheckResult(True, (), f"suggested {suggestion}", choice=suggestion) if suggestion else CheckResult(True, (), "no suggestion: no decision")))
    general.register_general()
    out = api.start(data, key, "policy:ending-2099", "Example policy", {"term_end": "2099-06-30"}, MANAGER, yes=True, today=DAY)
    RID[0] = out["run"]["id"]

    def reopen():
        api.open_run(data, RID[0], MANAGER, readers=StoreReaders(data), roles_of=roles_of, yes=True, today=DAY)

    def states():
        return {s["id"]: s["state"] for s in api.show(data, RID[0], today=DAY)["steps"]}

    reopen()
    assert states()[sid(key, "due")] == "done" and states()[sid(key, "quote")] == "needs a person"      # the read answered at open
    with pytest.raises(StepRefused):
        drive(data, key, "due", MANAGER, record="by a person's word")                                    # a read is done by its result
    with pytest.raises(StepRefused):
        drive(data, key, "dec", SECRETARY_, outcome="approved", record="the minutes")                    # not yet: it needs the proposals
    drive(data, key, "quote", MANAGER, record="the agent's proposal, in the library")
    reopen()                                                                                             # the reads run again
    assert states()[sid(key, "min")] == "done"                                                           # the limits read passed on its own
    with pytest.raises(StepRefused):
        drive(data, key, "dec", MANAGER, outcome="approved", record="the minutes")                        # only the secretary records the decision
    drive(data, key, "dec", SECRETARY_, outcome="approved", record="the minutes of 2099-03-10", motion="renew as quoted")
    drive(data, key, "bind", MANAGER, record="the declarations are in Drive; the premium is paid")
    reopen()                                                                                             # the reads run again
    return key, reopen, states


def _ovr_message(data, key):
    events = store.read(data, key, RID[0]).events
    return [e.detail.get("message", "") for e in events if e.kind.value == "check-ran" and e.step == sid(key, "ovr")][-1]


def test_an_insurance_renewal_the_manager_answers_agreeing_with_the_read_runs_to_done(data, monkeypatch):
    key, reopen, states = _insurance_run(data, monkeypatch, "unchanged")
    assert states()[sid(key, "read")] == "done" and states()[sid(key, "chg")] == "needs a person"       # the read only suggests
    assert states()[sid(key, "sum")] == "done" and states()[sid(key, "ovr")] in ("blocked", "not started")
    with pytest.raises(StepRefused):
        drive(data, key, "chg", TREASURER_, choice="unchanged", record="not the manager's step")        # a person holding the role
    with pytest.raises(StepRefused):
        drive(data, key, "chg", MANAGER, choice="maybe", record="not a path")
    drive(data, key, "chg", MANAGER, choice="unchanged", record="memberNoticeNeeded is no; the term matches the term before")
    reopen()
    assert states()[sid(key, "chg")] == "done" and states()[sid(key, "ovr")] == "done"
    assert states()[sid(key, "mem")] == "skipped"                                                        # the member notice is on the changed path
    assert _ovr_message(data, key) == "the answer unchanged agrees with the read's suggestion"
    final = api.show(data, RID[0], today=DAY)
    assert final["state"] == "done"
    assert {s["id"] for s in final["steps"] if s["state"] == "skipped"} == {sid(key, "mem")}


def test_an_insurance_renewal_the_manager_may_answer_over_the_read_and_the_run_records_it(data, monkeypatch):
    key, reopen, states = _insurance_run(data, monkeypatch, "unchanged")
    drive(data, key, "chg", MANAGER, choice="changed", record="the carrier's letter says the deductible rose")
    reopen()
    assert states()[sid(key, "ovr")] == "done" and states()[sid(key, "mem")] == "needs a person"        # the changed path opens the notice
    message = _ovr_message(data, key)
    assert message.startswith("the person overrode the read: answered changed where the read suggested unchanged")
    assert "a record came with it" in message
    drive(data, key, "mem", MANAGER, record="the ledger row insurance-change")
    final = api.show(data, RID[0], today=DAY)
    assert final["state"] == "done" and not [s for s in final["steps"] if s["state"] == "skipped"]


def test_an_insurance_renewal_the_manager_answers_by_hand_when_the_read_has_no_suggestion(data, monkeypatch):
    key, reopen, states = _insurance_run(data, monkeypatch, "")
    assert states()[sid(key, "read")] == "done" and states()[sid(key, "chg")] == "needs a person"        # a read with nothing to say never blocks
    drive(data, key, "chg", MANAGER, choice="changed", record="the board's decision was to let the policy lapse")
    reopen()
    assert "given by hand" in _ovr_message(data, key) and "no suggestion to compare" in _ovr_message(data, key)
    assert states()[sid(key, "mem")] == "needs a person"


def test_the_insurance_answer_is_a_person_step_with_a_read_before_it_and_a_record_after_it():
    wf = build("insurance-renewal")
    chg, read, ovr = (wf.step(sid("insurance-renewal", w)) for w in ("chg", "read", "ovr"))
    assert chg.kind is B and chg.check is None and chg.role is M and not chg.is_legal      # a branch with no read to decide it
    assert read.id in chg.needs and ovr.needs == (chg.id,)
    assert read.kind is C and getattr(read.check, "name", "") == "insurance-changed"
    assert ovr.kind is C and getattr(ovr.check, "name", "") == "insurance-answer"
    assert [c.key for c in chg.choices] == ["changed", "unchanged"]
    assert [s.id for s in wf.steps][:8] == [f"insurance-renewal.{i}" for i in range(1, 9)]              # nothing renumbered: new steps came last


@pytest.mark.parametrize("path, ratified", [("meeting", False), ("every-director", True), ("subcommittee", True)])
def test_a_monthly_review_asks_for_the_ratification_only_on_the_independent_paths(data, monkeypatch, path, ratified):
    key = "monthly-review"
    passing(monkeypatch, "review-reconciliations", "review-budget", "review-statements", "review-income-expense", "review-registers")
    general.register_general()
    out = api.start(data, key, "month:2099-09", "September", {"month_end": "2099-09-30"}, MANAGER, yes=True, today=DAY)
    RID[0] = out["run"]["id"]
    api.open_run(data, RID[0], MANAGER, readers=StoreReaders(data), roles_of=roles_of, yes=True, today=DAY)
    for word in ("sync", "attach"):
        api.skip(data, RID[0], sid(key, word), MANAGER, roles_of=roles_of, reason="the board reviews the stored books", readers=StoreReaders(data), today=DAY)
    api.open_run(data, RID[0], MANAGER, readers=StoreReaders(data), roles_of=roles_of, yes=True, today=DAY)       # the reads run now
    states0 = {s["id"]: s["state"] for s in api.show(data, RID[0], today=DAY)["steps"]}
    assert {states0[sid(key, w)] for w in ("recon", "bva", "stmt", "ie", "regs")} == {"done"}                # done by their reads
    drive(data, key, "xfer", TREASURER_, record="xfer read")
    api.skip(data, RID[0], sid(key, "inv"), TREASURER_, roles_of=roles_of, reason="no finding", readers=StoreReaders(data), today=DAY)
    drive(data, key, "path", TREASURER_, choice=path, record=path)
    drive(data, key, "rev", TREASURER_, record="A. Treasurer, 2099-10-09, all parts")
    states = {s["id"]: s["state"] for s in api.show(data, RID[0], today=DAY)["steps"]}
    if ratified:
        assert states[sid(key, "rat")] == "needs a person"
        assert states[sid(key, "rec")] in ("blocked", "not started")
        with pytest.raises(StepRefused):
            drive(data, key, "rat", MANAGER, outcome="approved", record="the minutes")
        drive(data, key, "rat", SECRETARY_, outcome="approved", record="the minutes of 2099-10-20", motion="ratify the review")
    else:
        assert states[sid(key, "rat")] == "skipped"
    drive(data, key, "rec", SECRETARY_, record="jason://min/2099-10-20")
    assert api.show(data, RID[0], today=DAY)["state"] == "done"
