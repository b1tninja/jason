"""The property family's reads (src/jason/workflows/checks/property.py): each against a temporary data folder with made-up stores.

Every check is read-only (the folder is compared byte for byte before and after), reaches no network, names no profile, and
answers ``ok=False`` with a reason for a store it cannot read. Nothing here reads a real store: names are "A. Manager",
"Example Alarm", "123 Main St"; dates are in 2099.
"""

from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from jason.community.board_items import BoardItem, ItemCategory
from jason.tasks import board_items, contract_terms, deficiencies, inspections, paint_view, unit_records_view
from jason.workflows import checks
from jason.workflows.readers import CHECKS, StoreReaders
from jason.workflows.types import CheckResult
from test_paint_view import CATALOG, SCHEDULE, Stub
from test_workflows_support import data  # noqa: F401 - the `data` fixture

checks.load_all()

TODAY = date(2099, 6, 15)
NAMES = ("life-safety-standing", "life-safety-reports-read", "deficiency-confirmed", "deficiency-impairs-recorded",
         "deficiency-insurer-told", "deficiency-cleared", "deficiency-board-item", "loss-packet", "contract-window",
         "backflow-tester", "paint-catalog", "elevated-due", "backflow-assemblies", "contract-owed", "contract-statement",
         "improvement-findings", "program-standing")
ROW = "def-0a1b2c3d4e"


def tree(root: Path) -> dict[str, bytes]:
    """Every file under a folder, with its bytes: what a read must leave exactly as it was."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def view(subject="", dates=None):
    return SimpleNamespace(id="run-test", subject=subject, dates=dict(dates or {}), opened_at="2099-01-01T00:00:00Z")


def run(name, readers, subject="", item="", dates=None) -> CheckResult:
    return CHECKS[name](readers, view(subject, dates), item)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Any socket or HTTP use fails the test."""
    def refuse(*a, **kw):
        raise AssertionError("a check made a network call")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)


def readers_of(data_dir, community=None):
    data_dir.mkdir(parents=True, exist_ok=True)
    return StoreReaders(data_dir, community=community if community is not None else SimpleNamespace(), today=TODAY)


# --- the family ----------------------------------------------------------------------------------------------------------

def test_the_seventeen_reads_are_registered_once_by_name():
    assert set(NAMES) <= set(CHECKS) and len(NAMES) == 17
    before = dict(CHECKS)
    assert checks.load_all() and dict(CHECKS) == before


@pytest.mark.parametrize("name", NAMES)
def test_a_read_with_nothing_on_disk_is_not_ok_names_why_and_writes_nothing(data, name):
    readers = readers_of(data)
    res = run(name, readers, subject=ROW, item="unit-1")
    assert isinstance(res, CheckResult) and res.ok is False and res.message
    assert tree(data) == {}                                    # not a folder, not a file, not a lock


@pytest.mark.parametrize("name", NAMES)
def test_a_read_with_no_community_chosen_is_not_ok_and_never_raises(data, name, monkeypatch):
    import jason.community as community

    def none_chosen():
        raise RuntimeError("no community is chosen")

    monkeypatch.setattr(community, "community", none_chosen)
    data.mkdir(parents=True)
    res = run(name, StoreReaders(data, today=TODAY), subject=ROW, item="unit-1", dates={"term_ends": "2099-12-31"})
    assert res.ok is False and res.message


# --- the life-safety record ----------------------------------------------------------------------------------------------

def period(status, *reports):
    return inspections.Period(None, TODAY, status, reports=tuple(reports))


def system(key, *obligations, not_read=()):
    return inspections.SystemRecords(SimpleNamespace(key=key), obligations=tuple(obligations), not_read=tuple(not_read))


def obligation(standing, *periods):
    return inspections.ObligationRecords(None, None, periods=tuple(periods), calendar={"standing": standing} if standing else None)


def records(*systems, unplaced=(), listed=True):
    return inspections.Records(TODAY, systems=tuple(systems), unplaced=tuple(unplaced), listed=listed)


def filing():
    return inspections.Filing("Example Alarm", "report.pdf")


COV = inspections.Coverage


def stub_review(monkeypatch, found=None, raises=None):
    def review(data_dir, community, as_of=None):
        if raises:
            raise raises
        return found

    monkeypatch.setattr(inspections, "review", review)


def test_the_life_safety_standing_tallies_each_obligation_and_each_period(data, monkeypatch):
    readers = readers_of(data)
    (data / "documents").mkdir()
    (data / "documents" / "readings.json").write_text("[]", encoding="utf-8")
    before = tree(data)
    stub_review(monkeypatch, records(
        system("alarm", obligation("overdue", period(COV.NOT_ON_FILE), period(COV.COVERED, object())),
               obligation("done", period(COV.COVERED, object()))),
        system("sprinkler", obligation(None, period(COV.NOT_YET_DUE)))))
    res = run("life-safety-standing", readers)
    assert res.ok and "3 obligation(s) for 2 system(s)" in res.message
    assert "1 overdue" in res.message and "1 done" in res.message and "1 none on record" in res.message
    assert "2 covered" in res.message and "1 not on file" in res.message and "1 not yet due" in res.message
    assert any(e.startswith("file:documents/readings.json@") for e in res.evidence)
    narrowed = run("life-safety-standing", readers, item="sprinkler")                 # an item that is a system's key narrows
    assert "1 obligation(s) for 1 system(s)" in narrowed.message
    assert "3 obligation(s)" in run("life-safety-standing", readers, item="2099-Q2").message   # a period leaves the record whole
    assert tree(data) == before


def test_the_life_safety_standing_is_not_ok_without_systems_obligations_or_a_readable_record(data, monkeypatch):
    readers = readers_of(data)
    stub_review(monkeypatch, records(listed=False))
    assert "lists no life-safety system" in run("life-safety-standing", readers).message
    stub_review(monkeypatch, records(system("alarm")))
    assert "no obligation applies" in run("life-safety-standing", readers).message
    stub_review(monkeypatch, raises=ValueError("readings.json is damaged"))
    res = run("life-safety-standing", readers)
    assert res.ok is False and "cannot be read: ValueError" in res.message and "damaged" in res.message


def test_the_reports_read_wants_every_filed_report_read_and_one_on_file(data, monkeypatch):
    readers = readers_of(data)
    stub_review(monkeypatch, records(system("alarm", obligation("done", period(COV.COVERED, object(), object())))))
    res = run("life-safety-reports-read", readers)
    assert res.ok and res.message == "2 report(s) placed, 0 not placed, 0 filed and not read"
    stub_review(monkeypatch, records(system("alarm", obligation("done", period(COV.COVERED, object())), not_read=[filing()])))
    res = run("life-safety-reports-read", readers)
    assert res.ok is False and "1 filed and not read" in res.message and "jason models --filed" in res.message
    stub_review(monkeypatch, records(system("alarm", obligation("done"))))
    assert run("life-safety-reports-read", readers).ok is False                       # nothing on file to read
    stub_review(monkeypatch, records(system("alarm", obligation("done")), unplaced=[SimpleNamespace(id="r1")]))
    assert run("life-safety-reports-read", readers).ok is True                         # a report no period holds is for `place`


# --- the deficiency register ---------------------------------------------------------------------------------------------

def act(name, day="2099-06-02", **more):
    return {"act": name, "by": "A. Manager", "at": f"{day}T10:00:00+00:00", **more}


def seed(data_dir, *acts, ident=ROW):
    path = data_dir / deficiencies.STORE
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"id": ident, "system": "alarm", "buildings": [], "location": "Stair 2", "device": "Waterflow switch",
           "comment": "Switch does not trip", "report": {"day": "2099-05-01"}, "acts": list(acts)}
    path.write_text(json.dumps({"deficiencies": [row]}), encoding="utf-8")


def test_confirmed_wants_a_persons_confirmation_on_the_register(data):
    readers = readers_of(data)
    seed(data, act("proposed", "2099-06-01"))
    res = run("deficiency-confirmed", readers, ROW)
    assert res.ok is False and "only proposed" in res.message and res.evidence
    seed(data, act("proposed", "2099-06-01"), act("confirmed", "2099-06-02"))
    before = tree(data)
    res = run("deficiency-confirmed", readers, ROW)
    assert res.ok and res.message == f"{ROW}: the confirmation is on the register, dated 2099-06-02"
    assert any(e.startswith("file:life-safety/deficiencies.json@") for e in res.evidence)
    assert tree(data) == before


def test_a_check_names_neither_who_acted_nor_the_deficiencys_words(data):
    readers = readers_of(data)
    seed(data, act("confirmed"), act("impairs", "2099-06-03"), act("insurer told", "2099-06-04", record="msg-17", on="2099-06-04"),
         act("cleared", "2099-06-09", record="lib-9", kind="invoice lines", on="2099-06-08"))
    for name in ("deficiency-confirmed", "deficiency-impairs-recorded", "deficiency-insurer-told", "deficiency-cleared"):
        res = run(name, readers, ROW)
        assert res.ok, name
        assert "A. Manager" not in res.message and "Waterflow" not in res.message and "Stair" not in res.message, name


def test_the_impairment_answer_is_never_in_what_the_check_says(data):
    readers = readers_of(data)
    seed(data, act("confirmed"))
    assert run("deficiency-impairs-recorded", readers, ROW).ok is False
    seed(data, act("confirmed"), act("impairs", "2099-06-03"))
    yes = run("deficiency-impairs-recorded", readers, ROW)
    seed(data, act("confirmed"), act("does not impair", "2099-06-03"))
    no = run("deficiency-impairs-recorded", readers, ROW)
    assert yes.ok and no.ok and yes.message == no.message == f"{ROW}: an answer on impairment is recorded, dated 2099-06-03"
    assert yes.evidence != no.evidence                                                 # the hash changes; the words do not appear


def test_the_insurer_told_and_cleared_read_the_records_a_person_linked(data):
    readers = readers_of(data)
    seed(data, act("confirmed"), act("impairs"))
    assert "no record shows the insurer was told" in run("deficiency-insurer-told", readers, ROW).message
    cleared = run("deficiency-cleared", readers, ROW)
    assert cleared.ok is False and "no clearing record is linked" in cleared.message
    seed(data, act("confirmed"), act("insurer told", record="msg-17", on="2099-06-04", inLibrary=False),
         act("cleared", record="lib-9", kind="invoice lines", on="2099-06-08"))
    told = run("deficiency-insurer-told", readers, ROW)
    assert told.ok and told.message == f"{ROW}: told on 2099-06-04, record msg-17 (not in the library)"
    done = run("deficiency-cleared", readers, ROW)
    assert done.ok and done.message == f"{ROW}: cleared on 2099-06-08 by invoice lines lib-9"


def test_the_board_item_is_on_the_list_for_a_confirmed_row_only(data):
    readers = readers_of(data)
    seed(data, act("proposed"))
    res = run("deficiency-board-item", readers, ROW)
    assert res.ok is False and "only proposed" in res.message
    seed(data, act("confirmed"), act("impairs"))
    assert "is not on the board's list" in run("deficiency-board-item", readers, ROW).message
    board_items.save(data, [BoardItem(deficiencies.item_id(ROW), "A deficiency", "", "Decide", ItemCategory.SAFETY)])
    before = tree(data)
    res = run("deficiency-board-item", readers, ROW)
    assert res.ok and res.message == f"board item life-safety-{ROW} is on the board's list, open"
    assert "urgent" not in res.message and "high" not in res.message                   # the priority rises with an impairment (P2)
    assert len(res.evidence) == 2 and tree(data) == before


def test_a_register_that_is_missing_unreadable_or_has_no_such_row_is_not_ok(data):
    readers = readers_of(data)
    for name in NAMES[2:7]:
        assert run(name, readers, ROW).message == "the deficiency register is not on disk"
    path = data / deficiencies.STORE
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    before = tree(data)
    for name in NAMES[2:7]:
        res = run(name, readers, ROW)
        assert res.ok is False and "cannot be read: JSONDecodeError" in res.message, name
    seed(data, act("confirmed"))
    for name in NAMES[2:7]:
        res = run(name, readers, "def-other")
        assert res.ok is False and "no deficiency def-other is in the register" in res.message, name
    assert run("deficiency-confirmed", readers, "", ROW).ok                           # the item may name the row when the subject does not
    assert tree(data) != before                                                         # only the seeding changed it


# --- the loss packet -----------------------------------------------------------------------------------------------------

PACKET = {"found": True, "policy": {"key": "master"}, "steps": [
    {"step": 1, "state": "confirmed", "held": ""}, {"step": 2, "state": "unconfirmed", "held": "Provision not found on file: X."},
    {"step": 3, "state": "unconfirmed", "held": ""}, {"step": 4, "state": "unconfirmed", "held": ""},
    {"step": 5, "state": "unconfirmed", "held": "The board has not adopted a deductible guideline."}]}


def test_the_loss_packet_counts_steps_and_names_no_unit_or_owner(data, monkeypatch):
    readers = readers_of(data)
    seen = []

    def packet(root, community, unit, incident="", *, address=""):
        seen.append((unit, incident, address))
        return PACKET

    monkeypatch.setattr(unit_records_view, "loss_packet_view", packet)
    res = run("loss-packet", readers, "incident:inc-77", item="u-12")
    assert res.ok and res.message == "5 step(s) assembled: 1 confirmed by a person, 2 with a held note; a master policy is on file"
    assert "u-12" not in res.message and "inc-77" not in res.message
    assert seen == [("u-12", "inc-77", "")]                                             # the unit by id; no address is asked for
    assert run("loss-packet", readers, "inc-78", item="u-12") and seen[-1][1] == "inc-78"
    assert run("loss-packet", readers, "inc-77", item="").message.startswith("the packet is for one unit")
    monkeypatch.setattr(unit_records_view, "loss_packet_view", lambda *a, **k: {"found": False, "note": "the specification holds no loss ladder"})
    assert run("loss-packet", readers, "inc-77", item="u-12").message == "the specification holds no loss ladder"
    monkeypatch.setattr(unit_records_view, "loss_packet_view", lambda *a, **k: {**PACKET, "steps": [], "policy": None})
    assert run("loss-packet", readers, "inc-77", item="u-12").message == "the ladder has no steps"

    def broken(*a, **k):
        raise OSError("the unit's packet file is locked")

    monkeypatch.setattr(unit_records_view, "loss_packet_view", broken)
    res = run("loss-packet", readers, "inc-77", item="u-12")
    assert res.ok is False and "cannot be read: OSError" in res.message


def test_the_loss_packet_assembles_for_real_over_a_ladder_and_writes_nothing(data):
    from jason.community.loss_packet import LadderStep

    ladder = (LadderStep(1, "What happened?", ()), LadderStep(2, "Which policy applies?", ()))
    community = SimpleNamespace(loss_ladder=lambda: ladder, open_questions=lambda: (), deductible_policy=lambda: None)
    readers = readers_of(data, community)
    res = run("loss-packet", readers, "inc-1", item="u-1")
    assert res.ok and res.message == "2 step(s) assembled: 0 confirmed by a person, 2 with a held note; no master policy is on file"
    assert tree(data) == {}
    none = readers_of(data / "other", SimpleNamespace(loss_ladder=lambda: (), open_questions=lambda: (), deductible_policy=lambda: None))
    assert run("loss-packet", none, "inc-1", item="u-1").message == "the specification holds no loss ladder"


# --- a contract's notice windows -----------------------------------------------------------------------------------------

def seed_terms(data_dir, key="contract-a", terms=None):
    folder = data_dir / contract_terms.STORE
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.json").write_text(json.dumps({"key": key, "terms": terms or []}), encoding="utf-8")


def clause(section, quote, window, delivery=("certified mail",)):
    return {"id": f"contract-a#{section}:abc", "section": section, "quote": quote, "window_days": list(window), "delivery": list(delivery)}


DAYS = "Notice of non-renewal must be given at least sixty (60) days prior to expiration, but no more than ninety (90) days prior."
MONTHS = "Notice must be given at least three (3) months, and no more than six (6) months, before the term ends."


def test_a_contract_window_counts_both_edges_from_the_terms_end_with_the_delivery(data):
    readers = readers_of(data)
    seed_terms(data, terms=[clause("4.1", DAYS, (60, 90)), clause("4.2", MONTHS, (3, 6), delivery=())])
    before = tree(data)
    res = run("contract-window", readers, "contract:contract-a", dates={"term_ends": "2099-12-31"})
    assert res.ok
    assert "term ends 2099-12-31" in res.message
    assert "section 4.1: opens 2099-10-02 (earliest), closes 2099-11-01 (latest), certified mail; today it is not yet open" in res.message
    assert "section 4.2: opens 2099-06-30 (earliest), closes 2099-09-30 (latest), delivery not named; today it is not yet open" in res.message
    assert any(e.startswith("file:contracts/terms/contract-a.json@") for e in res.evidence)
    assert run("contract-window", readers, "contract-a", dates={"term_ends": "2099-12-31"}).ok          # the bare key is the subject too
    only = run("contract-window", readers, "contract-a", item="4.2", dates={"term_ends": "2099-12-31"})
    assert "4.1" not in only.message and "4.2" in only.message
    mid = run("contract-window", StoreReaders(data, community=SimpleNamespace(), today=date(2099, 10, 10)), "contract-a",
              item="4.1", dates={"term_ends": "2099-12-31"})
    assert "today it is open" in mid.message
    late = run("contract-window", StoreReaders(data, community=SimpleNamespace(), today=date(2099, 12, 1)), "contract-a",
               dates={"term_ends": "2099-12-31"})
    assert "today it is closed" in late.message
    assert tree(data) == before


def test_a_contract_window_that_cannot_be_counted_is_not_ok(data):
    readers = readers_of(data)
    dates = {"term_ends": "2099-12-31"}
    assert "no term_ends date" in run("contract-window", readers, "contract-a").message
    assert "no contract terms have been read" in run("contract-window", readers, "contract-a", dates=dates).message
    seed_terms(data, terms=[clause("4.1", DAYS, (60, 90))])
    assert "no terms reading has the run's contract" in run("contract-window", readers, "contract-b", dates=dates).message
    seed_terms(data, terms=[{"id": "x", "section": "1", "quote": "A term.", "window_days": None}])
    assert "no notice window with two edges" in run("contract-window", readers, "contract-a", dates=dates).message
    seed_terms(data, terms=[clause("4.3", "At least 60 and no more than 90 days or 3 months before.", (60, 90))])
    unclear = run("contract-window", readers, "contract-a", dates=dates)
    assert unclear.ok is False and "unclear unit of time" in unclear.message
    (data / contract_terms.STORE / "contract-a.json").write_text("{broken", encoding="utf-8")
    assert "cannot be read: JSONDecodeError" in run("contract-window", readers, "contract-a", dates=dates).message


# --- the backflow tester -------------------------------------------------------------------------------------------------

def program(*lists):
    return SimpleNamespace(tester=SimpleNamespace(name="Pat Tester", business="Example Plumbing", certificate="XX1234567"),
                           lists=tuple(SimpleNamespace(name=n, url="") for n in (lists or ("List A",))))


def seed_lists(data_dir, fetched="2099-06-01", *lists):
    path = data_dir / "backflow" / "tester-lists.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched": fetched, "lists": list(lists)}), encoding="utf-8")


def a_list(name, *texts, error=""):
    out = {"name": name, "url": "", "dated": "2099-05-01", "entries": [{"text": t, "id": "AB1234567"} for t in texts]}
    return {**out, "error": error} if error else out


def test_the_tester_check_passes_only_on_fetched_fresh_lists_that_carry_the_tester(data):
    readers = readers_of(data, SimpleNamespace(backflow_program=lambda: program("List A", "List B")))
    assert run("backflow-tester", readers).message.startswith("the tester lists have not been fetched")
    both = a_list("List A", "TESTER PAT EXAMPLE PLUMBING"), a_list("List B", "TESTER PAT EXAMPLE PLUMBING INC")
    seed_lists(data, "2099-06-01", *both)
    before = tree(data)
    res = run("backflow-tester", readers)
    assert res.ok and res.message == "2 list(s): 2 listed" and "Tester" not in res.message and "Pat" not in res.message
    assert any(e.startswith("file:backflow/tester-lists.json@") for e in res.evidence)
    assert tree(data) == before
    seed_lists(data, "2099-06-01", both[0], a_list("List B", "TESTER PAT OTHER BUSINESS"))
    other = run("backflow-tester", readers)
    assert other.ok and "1 listed, 1 listed under another business" in other.message      # said, and passes
    seed_lists(data, "2099-06-01", both[0], a_list("List B", "SOMEONE ELSE ENTIRELY"))
    gone = run("backflow-tester", readers)
    assert gone.ok is False and "the tester is not on every list" in gone.message
    seed_lists(data, "2099-06-01", both[0], a_list("List B", error="HTTP 500, not a PDF"))
    assert "a list was not fetched" in run("backflow-tester", readers).message
    seed_lists(data, "2097-06-01", *both)
    assert run("backflow-tester", readers).ok is False and "older than 365 days" in run("backflow-tester", readers).message
    path = data / "backflow" / "tester-lists.json"
    path.write_text("[", encoding="utf-8")
    assert "cannot be read: JSONDecodeError" in run("backflow-tester", readers).message


def test_the_tester_check_needs_a_program_and_a_tester(data):
    assert run("backflow-tester", readers_of(data, SimpleNamespace(backflow_program=lambda: None))).message == (
        "the specification sets no backflow program")
    none = SimpleNamespace(tester=None, lists=())
    assert run("backflow-tester", readers_of(data, SimpleNamespace(backflow_program=lambda: none))).message == (
        "the program names no tester to check")


# --- the paint catalog ---------------------------------------------------------------------------------------------------

def seed_catalog(data_dir):
    path = data_dir / paint_view.CATALOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched": "2020-01-01T00:00:00+00:00", "colors": CATALOG}), encoding="utf-8")


def test_the_paint_catalog_tallies_each_color_against_the_copy_on_disk(data):
    readers = readers_of(data, Stub(SCHEDULE))
    missing = run("paint-catalog", readers)
    assert missing.ok is False and "no catalog copy is on disk" in missing.message and "jason paint --refresh" in missing.message
    assert tree(data) == {}                                                             # nothing fetched, nothing written
    seed_catalog(data)
    before = tree(data)
    res = run("paint-catalog", readers)
    assert res.ok and res.message.startswith("5 color(s): ")
    for word in ("1 archived", "1 not checked", "1 not found", "1 ok", "1 renamed"):
        assert word in res.message
    assert "3 need a person" in res.message
    assert any(e.startswith("file:paint/sherwin-williams-colors.json@") for e in res.evidence)
    assert run("paint-catalog", readers, item="SW 1001").message.startswith("1 color(s): 1 renamed")
    assert run("paint-catalog", readers, item="TRIM").message.startswith("1 color(s): 1 archived")
    assert run("paint-catalog", readers, item="SW 0000").message == "no scheduled color matches"
    assert tree(data) == before


def test_the_paint_catalog_is_not_ok_without_a_schedule_or_with_a_damaged_copy(data):
    assert run("paint-catalog", readers_of(data, Stub())).message == "the association has no color schedule"
    path = data / paint_view.CATALOG_FILE
    path.parent.mkdir(parents=True)
    path.write_text("{damaged", encoding="utf-8")
    res = run("paint-catalog", readers_of(data, Stub(SCHEDULE)))
    assert res.ok is False and "no catalog copy is on disk" in res.message               # a damaged copy is a missing one


# --- the elevated-elements due day ---------------------------------------------------------------------------------------

def test_the_elevated_due_day_fails_for_a_building_with_no_date_and_passes_when_every_one_has_one(data, monkeypatch):
    from jason.community import elevated_inspections

    rows = [{"name": "Exterior elevated elements inspection, Building 1", "next": "2099-09-01"},
            {"name": "Exterior elevated elements inspection, Building 2", "next": "2098-01-01"}]
    monkeypatch.setattr(elevated_inspections, "calendar_rows", lambda community, today, **k: rows)
    readers = readers_of(data)
    res = run("elevated-due", readers)
    assert res.ok and res.message == "2 building(s) reached: 2 with a due day, the earliest 2098-01-01, 1 past"
    assert run("elevated-due", readers, item="building 1").message.startswith("1 building(s) reached: 1 with a due day, the earliest 2099-09-01")
    rows.append({"name": "Exterior elevated elements inspection, Building 3", "next": None})
    unknown = run("elevated-due", readers)
    assert unknown.ok is False and "1 with no date on record (a question for a person)" in unknown.message
    assert run("elevated-due", readers, item="Building 9").message == "no building the section reaches has a record matching the item"
    rows.clear()
    assert run("elevated-due", readers).message == "no building the section reaches has a record"
    assert tree(data) == {}


# --- the backflow assemblies ---------------------------------------------------------------------------------------------

def assembly(service, serial, *, passed="", failed="", ids=()):
    from jason.community.backflow import AssemblyType, BackflowAssembly, Service

    return BackflowAssembly(Service(service), AssemblyType.RP, 1.5, serial, "Bldg. 9 rear", ids=ids, last_passed=passed,
                            last_failed=failed)


def backflow_program(*assemblies, counts=(), notices=()):
    from jason.community.backflow import BackflowProgram

    return BackflowProgram("Example Backflow Program", "Example Water District", assemblies=tuple(assemblies), notices=tuple(notices),
                           counts=tuple(counts))


def test_the_assemblies_are_counted_by_service_test_and_differing_source_and_name_no_device(data):
    from jason.community.backflow import ProgramNotice

    program_ = backflow_program(
        assembly("domestic", "SN-1001", passed="2099-03-01", ids=(("County", "AB1"),)),
        assembly("irrigation", "SN-1002", passed="2098-03-01", failed="2099-04-01", ids=(("County", "AB2"),)),
        assembly("irrigation", "SN-1003", ids=(("County", "AB3"),)),
        counts=(("Example Water District", "irrigation", 3, "letter.pdf"), ("Example Water District", "domestic", 2, "letter.pdf")),
        notices=(ProgramNotice("Example Backflow Program", "dated", 30, (("dated", "2099-05-01"),)),))
    readers = readers_of(data, SimpleNamespace(backflow_program=lambda: program_))
    before = tree(data)
    res = run("backflow-assemblies", readers)
    assert res.ok
    assert res.message == ("3 assembly(ies): 1 domestic, 2 irrigation; 2 with a passed test on record, 1 whose last recorded test "
                           "failed, 1 with no test on record; 2 count(s) from another source differ from the assemblies' (none "
                           "picked); 1 notice(s)")
    for word in ("SN-1001", "Bldg", "AB1", "County", "Example Water"):
        assert word not in res.message
    assert tree(data) == before


def test_the_assemblies_are_not_ok_without_a_program_or_without_an_assembly(data):
    assert run("backflow-assemblies", readers_of(data, SimpleNamespace(backflow_program=lambda: None))).message == (
        "The specification sets no backflow program (Community.backflow_program).")
    empty = readers_of(data, SimpleNamespace(backflow_program=lambda: backflow_program()))
    assert run("backflow-assemblies", empty).message == "the program lists no assembly"


# --- what a contract's counterparty owes ----------------------------------------------------------------------------------

def test_owed_counts_the_deliverables_by_who_owes_them_and_says_it_does_not_read_whether_they_are_on_file(data):
    readers = readers_of(data)
    seed_terms(data, terms=[
        {"id": "c#1", "section": "3.1", "deliverable": True, "party": "counterparty", "deadline": {"text": "within 30 days"}},
        {"id": "c#2", "section": "3.2", "deliverable": True, "party": "counterparty", "recurrence_months": 1},
        {"id": "c#3", "section": "3.3", "deliverable": True, "party": "association"},
        {"id": "c#4", "section": "4.1", "deliverable": False, "party": "counterparty", "quote": "A term."}])
    before = tree(data)
    res = run("contract-owed", readers, "contract:contract-a")
    assert res.ok and res.message.startswith("3 deliverable(s) among 4 term(s): 1 association, 2 counterparty; 2 with a stated time; ")
    assert "not read here" in res.message and any(e.startswith("file:contracts/terms/contract-a.json@") for e in res.evidence)
    only = run("contract-owed", readers, "contract-a", item="3.1")
    assert only.ok and only.message.startswith("1 deliverable(s) among 1 term(s): 1 counterparty; 1 with a stated time")
    missing = run("contract-owed", readers, "contract-a", item="9.9")
    assert missing.ok is False and missing.message == "the reading holds no term for 9.9"
    assert tree(data) == before


def test_owed_is_not_ok_without_a_reading_or_with_no_term_and_says_zero_when_none_is_owed(data):
    readers = readers_of(data)
    assert run("contract-owed", readers, "contract-a").message == "no contract terms have been read yet (jason contract-terms)"
    seed_terms(data, terms=[{"id": "c#1", "section": "1", "deliverable": False, "party": "association"}])
    assert "no terms reading has the run's contract" in run("contract-owed", readers, "contract-b").message
    assert run("contract-owed", readers, "contract-a").message.startswith("0 deliverable(s) among 1 term(s): none; 0 with a stated time")
    seed_terms(data, terms=[])
    assert run("contract-owed", readers, "contract-a").message == "the reading holds no term"
    (data / contract_terms.STORE / "contract-a.json").write_text("{broken", encoding="utf-8")
    assert "cannot be read: JSONDecodeError" in run("contract-owed", readers, "contract-a").message


# --- the managing agent's written statement ------------------------------------------------------------------------------

def seed_readings(data_dir, *rows):
    path = data_dir / "documents" / "readings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"readAt": "2099-01-01", "readings": list(rows)}), encoding="utf-8")


def reading_row(ident, *codes, items=None):
    return {"id": ident, "name": "Example Management Agreement.pdf", "kind": "contract", "findings": [{"code": c} for c in codes],
            "fields": {"manager_statement": items if items is not None else []}}


def test_the_statement_is_read_from_the_agreements_own_text_and_a_miss_is_not_a_finding_that_none_exists(data):
    readers = readers_of(data)
    assert run("contract-statement", readers, "library-77").message == "no document readings are on disk (jason models)"
    seed_readings(data, reading_row("77", "manager-statement", "manager-statement-incomplete", items=["a", "b", "c"]),
                  reading_row("78", "manager-disclosure"), reading_row("79", "term-ended"))
    before = tree(data)
    ok = run("contract-statement", readers, "contract:library-77")
    assert ok.ok and "3 of 5 item(s) stated" in ok.message and "even when the answer is none" in ok.message
    assert "90 days before the agreement is a person's to read" in ok.message
    assert any(e.startswith("file:documents/readings.json@") for e in ok.evidence)
    assert run("contract-statement", readers, "77").ok                                      # the bare library id is the subject too
    absent = run("contract-statement", readers, "library-78")
    assert absent.ok is False and "carries no statement" in absent.message and "a person confirms one is on file" in absent.message
    other = run("contract-statement", readers, "library-79")
    assert other.ok is False and "does not take the document for a management agreement" in other.message
    assert "no document reading is stored" in run("contract-statement", readers, "library-99").message
    assert "no contract key" in run("contract-statement", readers, "").message
    assert "Example Management" not in ok.message + absent.message + other.message
    assert tree(data) == before
    (data / "documents" / "readings.json").write_text("[", encoding="utf-8")
    assert "cannot be read: JSONDecodeError" in run("contract-statement", readers, "library-77").message


# --- an improvement request's entry in the unit's manual -----------------------------------------------------------------

def seed_entries(data_dir, unit, *entries):
    folder = unit_records_view._unit_dir(data_dir, unit)
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{"id": f"e{n}", "unit": unit, "component": "flooring", "kind": "flooring", "what": "New floor", "visibility": "shared", **e}
            for n, e in enumerate(entries)]
    (folder / "entries.json").write_text(json.dumps(rows), encoding="utf-8")


def test_the_findings_pass_when_a_shared_entry_links_to_the_request_and_count_what_stays_private(data):
    readers = readers_of(data)
    assert run("improvement-findings", readers, "imp-1", item="").message.startswith("the findings are read for one unit")
    assert run("improvement-findings", readers, "", item="u-1").message == "the run has no request id as its subject"
    assert run("improvement-findings", readers, "imp-1", item="u-1").message == "no entries are on file for the unit"
    seed_entries(data, "u-1", {"approval": "improvement:imp-1"}, {"approval": ""}, {"approval": "improvement:imp-2"},
                 {"approval": "improvement:imp-1", "visibility": "private"})
    before = tree(data)
    res = run("improvement-findings", readers, "request:imp-1", item="u-1")
    assert res.ok and res.evidence == ()
    assert res.message == ("3 entr(ies) shared with the association, 1 linking to this request, 1 with no approval reference; "
                           "1 private, counted and not read; the other four findings need the request store and the change rules (not built)")
    for word in ("u-1", "imp-1", "New floor", "flooring"):
        assert word not in res.message
    miss = run("improvement-findings", readers, "imp-9", item="u-1")
    assert miss.ok is False and miss.message.startswith("no entry shared with the association links to this request (3 entr(ies)")
    assert tree(data) == before
    seed_entries(data, "u-1", {"approval": "improvement:imp-1", "visibility": "private"})
    hidden = run("improvement-findings", readers, "imp-1", item="u-1")
    assert hidden.ok is False and "0 entr(ies) shared" in hidden.message and "1 private, counted and not read" in hidden.message
    assert run("improvement-findings", readers, "imp-1", item="../").ok is False


# --- a maintenance program's standing ------------------------------------------------------------------------------------

def seed_portal(data_dir, key, *days, customer="cust-1"):
    from jason.tasks import vendor_portals

    path = vendor_portals.portal_root(data_dir, key) / customer / vendor_portals.ACCOUNT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"customer": {"customer_id": customer, "name": "A. Owner", "address": "123 Main St"},
                                "services": [{"day": d} for d in days]}), encoding="utf-8")


def test_the_standing_reads_implementation_only_and_says_document_and_adoption_are_not_read(data):
    community = SimpleNamespace(vendor_portals=lambda: (SimpleNamespace(key="pest"),))
    readers = readers_of(data, community)
    assert "no portal data on disk" in run("program-standing", readers, "program:pest").message
    seed_portal(data, "pest", "2099-05-20", "2099-03-01")
    before = tree(data)
    res = run("program-standing", readers, "program:pest")
    assert res.ok
    assert res.message == ("implementation: 2 visit(s) on record, the latest 2099-05-20, current; document: not read (no program "
                           "catalog); adoption: no act read (a vendor's approval is not one)")
    assert "not adopted" not in res.message and "A. Owner" not in res.message and "123 Main" not in res.message
    assert any(e.startswith("glob:vendors/pest/*/account.json@") for e in res.evidence)
    assert run("program-standing", readers, "", item="pest").ok                       # the item may name the portal
    old = run("program-standing", StoreReaders(data, community=community, today=date(2100, 1, 1)), "pest")
    assert old.ok and "not current (the latest visit is over 120 days old; proposed)" in old.message
    assert "declares no vendor portal for this program" in run("program-standing", readers, "program:other").message
    assert tree(data) == before
    seed_portal(data, "pest")                                                           # an account with no visit
    none = run("program-standing", readers, "pest")
    assert none.ok is False and "no visit on record" in none.message


# --- every read leaves the data folder as it was -------------------------------------------------------------------------

def test_every_read_leaves_a_populated_data_folder_byte_identical(data, monkeypatch):
    from jason.community import elevated_inspections

    seed(data, act("confirmed"), act("impairs"), act("insurer told", record="msg-17", on="2099-06-04"))
    board_items.save(data, [BoardItem(deficiencies.item_id(ROW), "A deficiency", "", "Decide", ItemCategory.SAFETY)])
    seed_terms(data, terms=[clause("4.1", DAYS, (60, 90))])
    seed_lists(data, "2099-06-01", a_list("List A", "TESTER PAT EXAMPLE PLUMBING"))
    seed_catalog(data)
    stub_review(monkeypatch, records(system("alarm", obligation("done", period(COV.COVERED, object())))))
    monkeypatch.setattr(elevated_inspections, "calendar_rows", lambda c, t, **k: [{"name": "B1", "next": "2099-09-01"}])
    monkeypatch.setattr(unit_records_view, "loss_packet_view", lambda *a, **k: PACKET)
    seed_terms(data, terms=[clause("4.1", DAYS, (60, 90)), {"id": "d", "section": "5", "deliverable": True, "party": "counterparty"}])
    seed_readings(data, reading_row("a", "manager-statement", items=["x"]))
    seed_entries(data, "u-1", {"approval": "improvement:imp-1"})
    seed_portal(data, "pest", "2099-06-01")
    from dataclasses import replace

    flow = replace(backflow_program(assembly("domestic", "SN-1", passed="2099-03-01")), tester=program().tester, lists=program().lists)
    community = SimpleNamespace(backflow_program=lambda: flow, paint_schedules=lambda: (SCHEDULE,),
                                vendor_portals=lambda: (SimpleNamespace(key="pest"),))
    readers = readers_of(data, community)
    before = tree(data)
    subjects = {"contract-window": "contract-a", "contract-owed": "contract-a", "contract-statement": "library-a",
                "improvement-findings": "imp-1", "program-standing": "pest"}
    subject = lambda name: subjects.get(name, ROW)                                      # noqa: E731
    items = {"loss-packet": "u-1", "improvement-findings": "u-1"}
    results = {name: run(name, readers, subject(name), items.get(name, ""), {"term_ends": "2099-12-31"}) for name in NAMES}
    assert tree(data) == before
    assert all(r.ok for n, r in results.items() if n not in ("deficiency-cleared", "life-safety-reports-read")), {
        n: r.message for n, r in results.items() if not r.ok}
    assert results["deficiency-cleared"].ok is False


def test_the_module_imports_no_profile_and_nothing_that_reaches_out():
    import ast

    text = (Path(__file__).resolve().parent.parent / "src" / "jason" / "workflows" / "checks" / "property.py").read_text(encoding="utf-8")
    names = {n.module or "" for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ImportFrom)}
    names |= {a.name for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Import) for a in n.names}
    assert not [n for n in names if "mystique" in n or n.split(".")[0] in {"payhoa", "requests", "httpx", "subprocess", "anthropic"}]
    assert not [n for n in names if n.startswith("jason.google") or n.startswith("jason.zoom") or n.startswith("jason.web")]
