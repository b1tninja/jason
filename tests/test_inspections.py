"""jason.tasks.inspections: which inspection periods of each life safety system have a record on file.

Every system, vendor, row, report, and provision here is made up ("Oak Ridge", "Acme Fire", "Regulation 12");
none is an association's, and none is the law.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from jason.community.applicability import Fact, InstallationStandard, Is, SystemKind
from jason.community.authorities import Publication, PublicationText
from jason.community.fire_protection import (
    FIRE_ALARM_SYSTEM,
    NFPA_25_SPRINKLERS,
    RECORD_RULES,
    WATER_BASED,
    RecordRule,
)
from jason.community.life_safety import LifeSafetySystem
from jason.community.obligations import Obligation
from jason.tasks import inspections as task
from jason.tasks.inspections import Completion, Coverage, Filing, Report

AS_OF = date(2026, 10, 4)

RISERS = LifeSafetySystem("risers", "Sprinklers, buildings A and B", SystemKind.FIRE_SPRINKLER,
                          InstallationStandard.NFPA_13R, "the installer's letter of May 1, 2010", serves=("A", "B"),
                          servicer="Acme Fire", monitor="Acme Alarm")
TOWNHOUSES = LifeSafetySystem("townhouses", "Sprinklers, the townhouses", SystemKind.FIRE_SPRINKLER,
                              InstallationStandard.NFPA_13D, "the plan set, sheet FP-1", serves=("C",))
CLUBHOUSE = LifeSafetySystem("clubhouse", "Sprinklers, the clubhouse", SystemKind.FIRE_SPRINKLER, serves=("D",),
                             note="No plan or installer's record is on file.")
ALARM = LifeSafetySystem("alarm", "Fire alarm, buildings A and B", SystemKind.FIRE_ALARM, serves=("A", "B"),
                         servicer="Acme Alarm")
BACKFLOW = LifeSafetySystem("backflow", "Backflow assemblies", SystemKind.BACKFLOW, serves_label="the fire service",
                            servicer="Acme Backflow")

ALARM_TEST = Obligation("Alarm test", "made-up row", every_months=6, applies=FIRE_ALARM_SYSTEM)
ANNUAL = Obligation("Sprinkler annual inspection", "made-up row", every_years=1, first_due=date(2025, 6, 30),
                    applies=NFPA_25_SPRINKLERS)
QUARTERLY = Obligation("Sprinkler quarterly inspection", "made-up row", every_months=3, applies=NFPA_25_SPRINKLERS)
BACKFLOW_TEST = Obligation("Backflow test", "made-up row", every_years=1, applies=Is(Fact.SYSTEM, SystemKind.BACKFLOW))
BUDGET = Obligation("Budget report", "made-up row", month=12, day=1)


class _Profile:
    name = "Oak Ridge Owners Association"

    def __init__(self, systems=(), rows=(), assignments=()):
        self._systems, self._rows, self._assignments = tuple(systems), tuple(rows), tuple(assignments)

    def life_safety_systems(self):
        return self._systems

    def obligations(self):
        return self._rows

    def applicability_facts(self):
        return ()

    def assignments(self):
        return self._assignments

    region = ""


def _reading(ident, day, system="fire alarm", building=None, *, model="made-up-reader", name="", **fields):
    row = {"id": ident, "name": name or f"Report {ident}.pdf", "kind": "inspection_report", "model": model,
           "hasText": True, "confidential": False,
           "fields": {"inspection_date": day, "system": system, "building": building, **fields}}
    if model is None:
        row.pop("fields")
    return row


def _one(found, system, row):
    part = next(s for s in found.systems if s.system is system)
    return next(o for o in part.obligations if o.row is row)


def _standing(o):
    return [(p.label, p.status) for p in o.periods]


# --- Periods ------------------------------------------------------------------------------------------------------


def test_a_period_with_a_report_is_covered_one_without_is_not_on_file_and_the_running_one_is_not_yet_due():
    readings = [_reading("1", "2025-03-10", building="A"), _reading("2", "2025-03-10", building="B"),
                _reading("3", "2025-08-20", building="A"), _reading("4", "2025-08-21", building="B")]
    found = task.completeness(_Profile((ALARM,), (ALARM_TEST, BUDGET)), readings, as_of=AS_OF)
    o = _one(found, ALARM, ALARM_TEST)
    assert o.counted_from == date(2025, 3, 10) and o.counted_how == "the earliest record on file"
    assert _standing(o) == [("on 2025-03-10", Coverage.COVERED),
                            ("2025-03-11 to 2025-09-10", Coverage.COVERED),
                            ("2025-09-11 to 2026-03-10", Coverage.NOT_ON_FILE),
                            ("2026-03-11 to 2026-09-10", Coverage.NOT_ON_FILE),
                            ("2026-09-11 to 2027-03-10", Coverage.NOT_YET_DUE)]
    covered = o.periods[1]
    assert [(p.report.name, p.report.day, p.report.id, p.slots) for p in covered.reports] == [
        ("Report 3.pdf", date(2025, 8, 20), "3", ("A",)), ("Report 4.pdf", date(2025, 8, 21), "4", ("B",))]
    assert o.counts() == {"covered": 2, "partly on file": 0, "not on file": 2, "not yet due": 1}
    assert found.summary() == [{"system": "alarm", "obligation": "Alarm test", "cadence": "semiannually", "periods": 5,
                                "covered": 2, "partly on file": 0, "not on file": 2, "not yet due": 1, "note": ""}]
    assert not found.unplaced


def test_a_period_with_a_report_for_one_building_is_partly_on_file():
    readings = [_reading("1", "2025-03-10", building="A"), _reading("2", "2025-08-20", building="A")]
    o = _one(task.completeness(_Profile((ALARM,), (ALARM_TEST,)), readings, as_of=AS_OF), ALARM, ALARM_TEST)
    assert o.periods[0].status is Coverage.COVERED and not o.periods[0].missing     # the day the count opens on
    assert o.periods[1].status is Coverage.PARTLY and o.periods[1].missing == ("B",)
    text = "\n".join(task.lines(task.completeness(_Profile((ALARM,), (ALARM_TEST,)), readings, as_of=AS_OF)))
    assert "2025-03-11 to 2025-09-10: partly on file" in text and "nothing on file for building B" in text


def test_a_first_due_date_sets_the_periods_and_a_record_before_them_is_listed_apart():
    quiet = (ANNUAL,)                                    # one sprinkler obligation, so a report needs no interval
    readings = [_reading("1", "2025-05-02", "fire sprinkler", ["A", "B"]),
                _reading("0", "2019-01-15", "fire sprinkler", ["A", "B"])]
    o = _one(task.completeness(_Profile((RISERS,), quiet), readings, as_of=AS_OF), RISERS, ANNUAL)
    assert o.counted_from == date(2025, 6, 30) and o.counted_how == "the row's first due date"
    assert _standing(o) == [("2024-07-01 to 2025-06-30", Coverage.COVERED),
                            ("2025-07-01 to 2026-06-30", Coverage.NOT_ON_FILE),
                            ("2026-07-01 to 2027-06-30", Coverage.NOT_YET_DUE)]
    assert [p.report.id for p in o.earlier] == ["0"]
    # A first due date still ahead: one period, not yet due.
    later = Obligation("Sample test", "made-up row", every_years=10, first_due=date(2030, 1, 1), applies=NFPA_25_SPRINKLERS)
    o = _one(task.completeness(_Profile((RISERS,), (later,)), [], as_of=AS_OF), RISERS, later)
    assert _standing(o) == [("2020-01-02 to 2030-01-01", Coverage.NOT_YET_DUE)]


def test_a_row_with_nothing_to_count_from_lists_no_period_and_says_so():
    found = task.completeness(_Profile((ALARM,), (ALARM_TEST,)), [], as_of=AS_OF)
    o = _one(found, ALARM, ALARM_TEST)
    assert o.periods == () and o.counted_from is None and "no record is on file to count from" in o.counted_how
    assert any("no period can be listed" in line for line in task.lines(found))
    assert found.summary()[0]["periods"] == 0 and found.summary()[0]["note"] == o.counted_how
    assert "| Alarm test | semiannually | 0 | 0 | 0 | 0 | The row gives no first due date" in task.markdown(found)


def test_the_rows_own_date_or_a_payment_opens_the_count_and_covers_nothing():
    dated = Obligation("Alarm test", "made-up row", every_months=6, done_on=date(2025, 9, 1), applies=FIRE_ALARM_SYSTEM)
    o = _one(task.completeness(_Profile((ALARM,), (dated,)), [], as_of=AS_OF), ALARM, dated)
    assert o.counted_how == "the date the row gives for its last record"
    assert o.periods[0].status is Coverage.NOT_ON_FILE
    assert o.periods[0].note == "The row dates a record on 2025-09-01; no reading of it is on file."
    # The calendar counts a payment; the lens opens the count there and still shows nothing on file.
    calendar = [{"name": "Backflow test", "next": "2027-06-20", "standing": "upcoming", "lastDone": "2026-06-20",
                 "firstDone": "2025-06-20"}]
    found = task.completeness(_Profile((BACKFLOW,), (BACKFLOW_TEST,)), [], as_of=AS_OF, calendar=calendar)
    o = _one(found, BACKFLOW, BACKFLOW_TEST)
    assert o.counted_from == date(2025, 6, 20) and "payment" in o.counted_how
    assert [p.status for p in o.periods] == [Coverage.NOT_ON_FILE, Coverage.NOT_ON_FILE, Coverage.NOT_YET_DUE]
    assert "payment" in o.periods[0].note
    assert "jason deadlines: next 2027-06-20, upcoming, last 2026-06-20" in "\n".join(task.lines(found))


# --- Placing ------------------------------------------------------------------------------------------------------


def test_a_report_with_no_building_is_unplaced_never_guessed_into_a_slot():
    readings = [_reading("1", "2025-03-10", building="A"), _reading("2", "2025-08-20")]
    found = task.completeness(_Profile((ALARM,), (ALARM_TEST,)), readings, as_of=AS_OF)
    (lost,) = found.unplaced
    assert lost.id == "2" and "does not say which building" in lost.reason and "the field building" in lost.reason
    assert "made-up-reader" in lost.reason
    o = _one(found, ALARM, ALARM_TEST)
    assert all(p.report.id != "2" for period in o.periods for p in period.reports)
    assert o.periods[1].status is Coverage.NOT_ON_FILE              # the August report covers nothing


def test_a_report_with_no_system_or_no_date_or_no_reader_is_unplaced_with_the_field_it_lacks():
    readings = [_reading("1", "2025-03-10", system="other", building="A"),
                _reading("2", None, building="A"),
                _reading("3", "2025-03-10", model=None),
                _reading("4", "2025-03-10", system="elevator", building="A"),
                _reading("5", "2025-03-10", building="Z"),
                {"id": "6", "kind": "minutes", "model": "minutes", "fields": {}}]            # another kind: passed over
    found = task.completeness(_Profile((ALARM,), (ALARM_TEST,)), readings, as_of=AS_OF)
    reasons = {u.id: u.reason for u in found.unplaced}
    assert set(reasons) == {"1", "2", "3", "4", "5"}
    assert "does not say which system" in reasons["1"] and "the field system" in reasons["1"]
    assert "gives no inspection date: the field inspection_date" in reasons["2"]
    assert reasons["3"] == "not read: no reader has read it (jason models)"
    assert task.place(Report.of({"id": "8", "hasText": False}), (ALARM,))[2] == "not read: no text on disk"
    assert "the specification lists no such system" in reasons["4"]
    assert "building Z" in reasons["5"]
    assert not _one(found, ALARM, ALARM_TEST).periods


def test_a_system_not_divided_by_building_takes_a_report_of_its_kind():
    readings = [_reading("1", "2025-06-01", "backflow assembly"), _reading("2", "2026-05-20", "backflow", building="A")]
    o = _one(task.completeness(_Profile((BACKFLOW, ALARM), (BACKFLOW_TEST, ALARM_TEST)), readings, as_of=AS_OF),
             BACKFLOW, BACKFLOW_TEST)
    assert _standing(o) == [("on 2025-06-01", Coverage.COVERED), ("2025-06-02 to 2026-06-01", Coverage.COVERED),
                            ("2026-06-02 to 2027-06-01", Coverage.NOT_YET_DUE)]
    assert task.slots_of(BACKFLOW) == ("",) and task.slots_of(ALARM) == ("A", "B")
    # Two listed systems of one kind: a report that names no building could be either's.
    system, slots, why = task.place(Report.of(_reading("3", "2025-06-01", "fire sprinkler")), (RISERS, TOWNHOUSES))
    assert system is None and "does not say which building" in why


def test_where_several_obligations_apply_the_reading_must_say_which():
    rows = (QUARTERLY, ANNUAL)
    readings = [_reading("1", "2025-05-02", "fire sprinkler", ["A", "B"]),
                _reading("2", "2025-05-02", "fire sprinkler", ["A", "B"], interval_months=12),
                _reading("3", "2025-05-02", "fire sprinkler", ["A", "B"], interval_months=60)]
    found = task.completeness(_Profile((RISERS,), rows), readings, as_of=AS_OF)
    part = found.systems[0]
    assert {p.report.id: why for p, why in part.unassigned} == {
        "1": "2 obligations apply to the system, and the reader made-up-reader does not say which inspection it "
             "records: the field interval_months",
        "3": "the reading says every 60 months, and no obligation of the system runs so"}
    assert _one(found, RISERS, ANNUAL).periods[0].status is Coverage.COVERED
    assert _one(found, RISERS, ANNUAL).periods[0].reports[0].report.id == "2"
    assert not _one(found, RISERS, QUARTERLY).periods
    text = "\n".join(task.lines(found))
    assert "on file, not assigned to an obligation (2)" in text


# --- What does not apply, and what is undetermined ---------------------------------------------------------------


def test_an_obligation_that_does_not_apply_shows_its_deciding_fact_and_expects_nothing():
    found = task.completeness(_Profile((TOWNHOUSES, ALARM), (ANNUAL, ALARM_TEST)), [], as_of=AS_OF)
    part = next(s for s in found.systems if s.system is TOWNHOUSES)
    assert part.obligations == ()                                    # nothing is expected
    annual = next(f for f in part.does_not_apply if f.row is ANNUAL)
    assert "NFPA 13D" in annual.why() and "the plan set, sheet FP-1" in annual.why()
    assert all(row["system"] != "townhouses" for row in found.summary())
    text = "\n".join(task.lines(found))
    assert "no obligation with periods applies; nothing is expected of it here" in text
    assert "decided by the installation standard: NFPA 13D (profile, the plan set, sheet FP-1):" in text


def test_an_undetermined_obligation_shows_its_question_and_lists_no_period():
    found = task.completeness(_Profile((CLUBHOUSE,), (ANNUAL,)), [_reading("1", "2025-05-02", "fire sprinkler", "D")],
                              as_of=AS_OF)
    part = found.systems[0]
    assert part.obligations == () and [f.row for f in part.undetermined] == [ANNUAL]
    question = part.undetermined[0].question()
    assert question.startswith("Sprinklers, the clubhouse: which standard was it installed under?")
    assert found.questions == (question,)
    # The report is of the system, and no obligation is known to apply: on file, not assigned, never dropped.
    assert [p.report.id for p, _ in part.unassigned] == ["1"]
    text = "\n".join(task.lines(found))
    assert "undetermined (1)" in text and f"question: {question}" in text


def test_a_profile_that_lists_no_systems_says_so():
    found = task.completeness(_Profile((), (ANNUAL,)), [_reading("1", "2025-05-02", "fire sprinkler", "A")], as_of=AS_OF)
    assert not found.listed and found.systems == ()
    assert found.questions[0].startswith("Which life safety systems does the association have?")
    assert "the specification lists no such system" in found.unplaced[0].reason
    assert "The specification lists no life safety systems" in "\n".join(task.lines(found))


# --- Deficiencies, completions, filings --------------------------------------------------------------------------


def test_a_deficiency_is_shown_with_its_count_and_a_correction_only_when_a_later_reading_says_so():
    failed = _reading("1", "2025-03-10", building="A", result="failed", open_deficiencies=1,
                      deficiencies=[{"comment": "made-up", "status": "Open"}])
    again = _reading("2", "2025-08-20", building="A", result="incomplete")
    readings = [failed, again]
    o = _one(task.completeness(_Profile((ALARM,), (ALARM_TEST,)), readings, as_of=AS_OF), ALARM, ALARM_TEST)
    first = o.periods[0].reports[0]
    assert first.correction is None
    assert first.deficiency_text() == "1 deficiency reported, 1 open; no correction on file"
    assert o.periods[0].as_dict()["reports"][0]["correctionNote"] == "no correction on file"
    passed = _reading("3", "2026-02-01", building="A", result="passed")
    other = _reading("4", "2025-12-01", building="B", result="passed")                # another building: says nothing
    o = _one(task.completeness(_Profile((ALARM,), (ALARM_TEST,)), readings + [other, passed], as_of=AS_OF), ALARM, ALARM_TEST)
    first = o.periods[0].reports[0]
    assert first.correction.id == "3"
    assert "a later report on file reads passed with none open: Report 3.pdf (2026-02-01, library id 3)" in first.deficiency_text()
    assert o.periods[1].reports[0].deficiency_text() == ""             # no deficiency, nothing to say


def test_a_completion_counts_only_where_it_names_one_obligation_of_one_system():
    one = Completion("alarm-test", date(2025, 3, 1), "Pat Example", "the report in the binder", obligations=("Alarm test",))
    two = Completion("fire-safety", date(2025, 9, 1), "Pat Example", "done", obligations=("Alarm test", "Backflow test"))
    budget = Completion("budget", date(2025, 11, 1), "Pat Example", "mailed", obligations=("Budget report",))
    profile = _Profile((ALARM, BACKFLOW), (ALARM_TEST, BACKFLOW_TEST, BUDGET))
    found = task.completeness(profile, [], as_of=AS_OF, completions=[one, two, budget])
    o = _one(found, ALARM, ALARM_TEST)
    assert o.periods[0].status is Coverage.COVERED and o.periods[0].completions == (one,)
    assert "recorded done on 2025-03-01 by Pat Example (assignment alarm-test)" in "\n".join(task.lines(found))
    (lost,) = found.unplaced                                          # the budget's completion is no system's record
    assert lost.id == "fire-safety" and "covers 2 obligations" in lost.reason
    # One obligation that applies to two systems: the record does not say which.
    both = _Profile((ALARM, LifeSafetySystem("alarm-2", "Fire alarm, building E", SystemKind.FIRE_ALARM, serves=("E",))),
                    (ALARM_TEST,))
    found = task.completeness(both, [], as_of=AS_OF, completions=[one])
    assert "applies to 2 systems" in found.unplaced[0].reason


def test_a_filed_report_no_reading_covers_is_listed_as_not_read_under_its_vendors_system():
    filings = [Filing("Acme Backflow", "Test reports 2026.pdf", "2026-05-06", "Reports/Backflow", "f1"),
               Filing("Acme Pest", "Service report.pdf", "2026-05-07", "Reports/Pest", "f2")]
    found = task.completeness(_Profile((BACKFLOW, ALARM), (BACKFLOW_TEST, ALARM_TEST)), [], as_of=AS_OF, filings=filings)
    part = next(s for s in found.systems if s.system is BACKFLOW)
    assert [f.name for f in part.not_read] == ["Test reports 2026.pdf"] and part.not_read[0].systems == ("backflow",)
    assert found.other_filings == 1
    assert not _one(found, BACKFLOW, BACKFLOW_TEST).periods            # not read: it places nothing
    assert "filed, not read (1)" in "\n".join(task.lines(found))


def test_a_confidential_reports_name_is_held_back():
    row = {**_reading("9", "2025-03-10", building="A", name="Unit 12 entry list.pdf"), "confidential": True}
    report = Report.of(row)
    assert "Unit 12" not in report.label and "a confidential document" in report.label
    assert report.as_dict()["name"] == ""


# --- The record-keeping rule, recited ----------------------------------------------------------------------------

MADE_UP = Publication("Made-up regulation, final text", "https://example.org/made-up-regulation.pdf", "a test",
                      agency="Example Agency", text=PublicationText.REGULATION)
SHELF_TEXT = """
<<PAGE 1>>
§12. Frequencies.
(a) Systems shall be looked at.
§12.1. Inspections.
(a) Anyone may look.
NOTE: Authority cited: nothing.
12.2. Testing.
(a) Tests are done.
(b) Records of all made-up testing shall be kept
by the owner for nine years after the

7

<<PAGE 2>>
next test.
(c) Tags go on last.
§13. Licenses.
"""
KEPT = RecordRule("kept", "Regulation 12.2(b)", "records of testing", MADE_UP.title, r"§?\s*12\.2\.\s", r"\(b\)\s",
                  r"\(c\)\s", applies=WATER_BASED)
ABSENT = RecordRule("absent", "Regulation 12.1(b)", "records of inspections", MADE_UP.title, r"§?\s*12\.1\.\s", r"\(b\)\s",
                    r"\(c\)\s|NOTE:", applies=WATER_BASED)


def _shelf(tmp_path, text=SHELF_TEXT):
    folder = tmp_path / "authorities" / "publications"
    folder.mkdir(parents=True)
    (folder / MADE_UP.text_filename).write_text(text, encoding="utf-8")
    return tmp_path


def test_a_provision_is_recited_from_the_shelf_across_a_page_break(tmp_path):
    found = task.recite(_shelf(tmp_path), KEPT, publications=(MADE_UP,))
    assert found.found
    assert found.words == ("(b) Records of all made-up testing shall be kept by the owner for nine years after the "
                           "next test.")
    assert "Made-up regulation, final text (Example Agency)" in found.source and MADE_UP.text_filename in found.source


def test_a_provision_the_shelf_does_not_print_is_said_to_be_missing_and_not_quoted(tmp_path):
    root = _shelf(tmp_path)
    missing = task.recite(root, ABSENT, publications=(MADE_UP,))
    assert not missing.found and missing.words == ""
    assert missing.reason == "the shelf's copy prints the section without this provision"
    nowhere = RecordRule("x", "Regulation 99(a)", "nothing", MADE_UP.title, r"§99\.\s", r"\(a\)\s", r"\(b\)\s")
    assert task.recite(root, nowhere, publications=(MADE_UP,)).reason == "the shelf's copy does not print the section"
    assert "is not on disk" in task.recite(tmp_path / "empty", KEPT, publications=(MADE_UP,)).reason
    assert "no publication titled" in task.recite(root, KEPT, publications=()).reason
    found = task.completeness(_Profile((RISERS, ALARM), (ANNUAL, ALARM_TEST)), [], as_of=AS_OF,
                              recitals=[task.recite(root, KEPT, publications=(MADE_UP,)), missing])
    kept, absent = found.recitals
    assert kept.reaches == ("Sprinklers, buildings A and B",)            # a water-based system; not the alarm
    text = "\n".join(task.lines(found))
    assert "Regulation 12.2(b) (records of testing)" in text and "\"(b) Records of all made-up testing" in text
    assert "Its words are not on the authorities shelf" in text and "cited and not quoted" in text
    assert "a reading: by the row's condition" in text


def test_the_record_rules_name_their_citations_and_a_publication_on_the_shelf_list():
    from jason.community.authorities import PUBLICATIONS

    titles = {p.title for p in PUBLICATIONS}
    assert [r.citation for r in RECORD_RULES] == ["19 CCR 904.1(b)", "19 CCR 904.2(c)", "NFPA 25 4.3.5 (California amendment)"]
    assert all(r.publication in titles for r in RECORD_RULES)
    assert len({r.key for r in RECORD_RULES}) == len(RECORD_RULES)


# --- The stores, the page, and the command ------------------------------------------------------------------------


def _data(tmp_path):
    (tmp_path / "documents").mkdir()
    readings = [_reading("1", "2025-03-10", building="A"), _reading("2", "2025-03-10", building="B"),
                {"id": "7", "name": "Minutes.pdf", "kind": "minutes", "model": "minutes", "hasText": True}]
    (tmp_path / "documents" / "readings.json").write_text(json.dumps({"readings": readings}), encoding="utf-8")
    (tmp_path / "schedule").mkdir()
    done = {"key": "alarm-test", "due": "2025-09-10", "done": "2025-09-02", "by": "Pat Example", "evidence": "the binder"}
    (tmp_path / "schedule" / "done.jsonl").write_text(json.dumps(done) + "\n", encoding="utf-8")
    (tmp_path / "drive").mkdir()
    log = [{"vendor": "Acme Alarm", "name": "Alarm report.pdf", "kind": "inspection_report", "file_id": "f1",
            "at": "2026-03-01T10:00:00+00:00", "where": "Reports/Fire Protection", "sha256": "aa"},
           {"vendor": "Acme Alarm", "name": "Invoice.pdf", "kind": "invoice", "file_id": "f2", "sha256": "bb"}]
    (tmp_path / "drive" / "vendor-files.jsonl").write_text("\n".join(json.dumps(r) for r in log) + "\n", encoding="utf-8")
    return tmp_path


class _Assignment:
    key = "alarm-test"
    covers = ("obligation:Alarm test", "CIV 0000")


def test_review_reads_the_stores_and_writes_nothing(tmp_path):
    root = _data(tmp_path)
    before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
    found = task.review(root, _Profile((ALARM,), (ALARM_TEST,), (_Assignment(),)), as_of=AS_OF)
    o = _one(found, ALARM, ALARM_TEST)
    assert [p.status for p in o.periods[:2]] == [Coverage.COVERED, Coverage.COVERED]
    assert o.periods[1].completions[0].by == "Pat Example"             # the person's completion of September 2, 2025
    assert o.calendar["standing"] == "no store shows it"                # the calendar's own row, beside the periods
    assert [f.name for f in found.systems[0].not_read] == ["Alarm report.pdf"]
    assert [r.rule.citation for r in found.recitals] == [r.citation for r in RECORD_RULES]
    assert all(not r.found and "not on disk" in r.reason for r in found.recitals)   # no shelf in this folder
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*")) == before
    data = json.loads(json.dumps(found.as_dict()))
    assert data["community"] == "Oak Ridge Owners Association" and data["asOf"] == "2026-10-04"
    assert data["systems"][0]["obligations"][0]["periods"][0]["status"] == "covered"
    assert data["summary"][0]["covered"] == 2 and data["caveats"]


def test_the_page_says_it_is_generated_and_is_a_summary_not_the_record(tmp_path):
    root = _data(tmp_path)
    found = task.review(root, _Profile((ALARM, TOWNHOUSES), (ALARM_TEST, ANNUAL), (_Assignment(),)), as_of=AS_OF)
    path = task.write(root, found)
    assert path == root / "reports" / "life-safety-records.md"
    page = path.read_text(encoding="utf-8")
    assert page.startswith("# Life safety records on file: Oak Ridge Owners Association")
    assert "Generated by jason on " in page and "It is a summary, not the record" in page
    assert "| Fire alarm, buildings A and B | Alarm test | semiannually | 2 | 0 | 2 | 1 |  |" in page
    assert "| on 2025-03-10 | covered |" in page and "### Does not apply" in page and "## Record keeping" in page
    assert "Decided by the installation standard: NFPA 13D" in page


def test_the_command_prints_the_periods_and_writes_only_when_asked(tmp_path, monkeypatch, capsys):
    from jason.cli import build_parser
    from jason.community import community

    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("PAYHOA_CATALOG", raising=False)
    args = build_parser().parse_args(["inspections", "--as-of", "2026-10-04"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "life safety records on file, as of 2026-10-04" in out
    assert "does not apply (" in out and "Record keeping" in out and "Unplaced (0)" in out
    assert not (tmp_path / "reports").exists()                          # read-only unless --write
    first = community().life_safety_systems()[0]
    args = build_parser().parse_args(["inspections", "--system", first.key, "--json"])
    assert args.func(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert [s["system"]["key"] for s in data["systems"]] == [first.key]
    args = build_parser().parse_args(["inspections", "--system", "no-such-system"])
    assert args.func(args) == 2
    capsys.readouterr()
    args = build_parser().parse_args(["inspections", "--as-of", "2026-10-04", "--write"])
    assert args.func(args) == 0
    page = (tmp_path / "reports" / "life-safety-records.md").read_text(encoding="utf-8")
    assert "It is a summary, not the record" in page


def test_the_calendar_gives_each_obligation_one_row_and_where_its_count_starts(tmp_path):
    from jason.tasks.deadlines import calendar, obligation_rows

    dated = Obligation("Alarm test", "made-up row", every_months=6, done_on=date(2025, 9, 1), applies=FIRE_ALARM_SYSTEM)
    profile = _Profile((ALARM,), (dated, QUARTERLY))
    rows = obligation_rows(tmp_path, profile, today=AS_OF)
    assert [(r["name"], r["next"], r["standing"], r["firstDone"]) for r in rows] == [
        ("Alarm test", "2026-03-01", "overdue", "2025-09-01"),
        ("Sprinkler quarterly inspection", None, "no store shows it", None)]
    # The calendar's own rows are the same rows: one scheduler.
    same = {r["name"]: r for r in calendar(tmp_path, profile, today=AS_OF)["obligations"]}
    assert all(same[r["name"]]["next"] == r["next"] and same[r["name"]]["standing"] == r["standing"] for r in rows)


def test_report_of_reads_only_the_readings_own_fields():
    report = Report.of({"id": "drive-abc", "name": "Bldg A report 2025-03-10.pdf", "period": "2025-03-10", "model": "m",
                        "fields": {"system": "Fire Alarm", "buildings": ["A", "B"], "interval_months": "6"}})
    assert report.day is None                                           # not the file's name, not its period
    assert report.kind is SystemKind.FIRE_ALARM and report.buildings == ("A", "B") and report.interval_months == 6
    assert report.where == "Drive" and "Drive id drive-abc" in report.label
    with pytest.raises(AttributeError):
        report.day = date(2025, 3, 10)                                  # a reading is not edited into place
