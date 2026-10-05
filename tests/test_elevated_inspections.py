"""jason.community.elevated_inspections: each building's Civil Code 5551 record, its (k) and (l) answers, and its next
due day under the section's cycle, or the question in its place.

Every building, person, and report here is made up; none is an association's.
"""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest

from jason.community.applicability import Answer, CommonInterest, ElevatedElements, Fact, Facts, FactValue, Source
from jason.community.elevated_inspections import (
    CYCLE_YEARS,
    FIRST_DUE,
    ElevatedElementsInspection,
    InspectorLicense,
    building_lines,
    calendar_rows,
    from_rows,
    years_after,
)
from jason.community.obligations import Standing
from jason.tasks.deadlines import calendar

RESP = ElevatedElements.ASSOCIATION_RESPONSIBLE
TODAY = date(2026, 10, 5)

INSPECTED = ElevatedElementsInspection("A", "building A", attached_units=12, responsibility=RESP, elements=4,
                                       inspected_on=date(2023, 11, 17), inspector="Ferris Quillon",
                                       license=InspectorLicense.ARCHITECT, license_number="C-00000",
                                       report="Sample report, 2023", permit_application_on=date(2006, 5, 1))
NEW_BUILDING = ElevatedElementsInspection("B", "building B", attached_units=8, responsibility=RESP,
                                          permit_application_on=date(2021, 3, 1),
                                          occupancy_certificate_on=date(2022, 6, 15))
TWO_UNITS = ElevatedElementsInspection("C", "building C", attached_units=2, responsibility=ElevatedElements.NONE)
UNREAD = ElevatedElementsInspection("D", "building D", attached_units=6, responsibility=RESP,
                                    report="Sample report, 2023")
OLD_UNINSPECTED = ElevatedElementsInspection("E", "building E", attached_units=6, responsibility=RESP,
                                             permit_application_on=date(2007, 1, 1))


def _community(*records, condo: bool = True):
    facts = (FactValue(Fact.COMMON_INTEREST, CommonInterest.CONDOMINIUM, Source.PROFILE, "the declaration"),) if condo else ()
    return SimpleNamespace(elevated_elements_inspections=lambda: records, applicability_facts=lambda: facts,
                           region="", obligations=lambda: (), insurance=lambda: SimpleNamespace(policies=()))


def test_a_record_is_entered_with_its_symbols_and_its_report():
    with pytest.raises(ValueError, match="report"):
        ElevatedElementsInspection("A", "building A", inspected_on=date(2023, 11, 17))
    with pytest.raises(TypeError, match="ElevatedElements"):
        ElevatedElementsInspection("A", "building A", responsibility="yes")
    with pytest.raises(TypeError, match="InspectorLicense"):
        ElevatedElementsInspection("A", "building A", license="architect")
    with pytest.raises(TypeError, match="count"):
        ElevatedElementsInspection("A", "building A", attached_units="12")
    with pytest.raises(TypeError, match="date"):
        ElevatedElementsInspection("A", "building A", permit_application_on="2021-03-01")


def test_an_inspected_building_is_next_due_nine_years_on():
    due = INSPECTED.due()
    assert due.day == date(2032, 11, 17) and due.under.startswith("(b)(1), (i)") and not due.question
    assert INSPECTED.standing(TODAY) is Standing.UPCOMING
    assert INSPECTED.permit_rule().answer is Answer.DOES_NOT_APPLY
    assert INSPECTED.units_rule().answer is Answer.APPLIES
    assert INSPECTED.questions() == ()
    assert "Ferris Quillon, licensed architect C-00000" in INSPECTED.last()


def test_a_building_permitted_from_2020_is_first_due_six_years_after_its_certificate():
    assert NEW_BUILDING.permit_rule().answer is Answer.APPLIES
    due = NEW_BUILDING.due()
    assert due.day == date(2028, 6, 15) and due.under.startswith("(k)")
    without = ElevatedElementsInspection("B", "building B", attached_units=8, responsibility=RESP,
                                         permit_application_on=date(2021, 3, 1))
    assert without.due().day is None and "certificate of occupancy" in without.due().question
    assert without.standing(TODAY) is Standing.UNKNOWN


def test_an_older_building_with_no_inspection_was_due_january_1_2025():
    due = OLD_UNINSPECTED.due()
    assert due.day == FIRST_DUE and due.under.startswith("(i)")
    assert OLD_UNINSPECTED.standing(TODAY) is Standing.OVERDUE


def test_an_unknown_date_is_a_question_not_a_guess():
    due = UNREAD.due()
    assert due.day is None and due.under == "(i) or (k)"
    questions = UNREAD.questions()
    assert any("has not been read into the record" in q and "5551(e)(5)(A)" in q for q in questions)
    assert any("permit application's date" in q for q in questions)
    assert UNREAD.standing(TODAY) is Standing.UNKNOWN
    # An inspection on record with no licensed professional is a finding too: (b)(1) names the license.
    unlicensed = ElevatedElementsInspection("A", "building A", inspected_on=date(2023, 11, 17), report="r")
    assert any("licensed structural or civil engineer or architect" in q for q in unlicensed.questions())
    # (k) undetermined no longer changes a building already inspected, so it is not asked of it.
    assert not any("(k)" in q for q in unlicensed.questions())


def test_the_section_is_asked_with_the_buildings_facts_over_the_associations():
    base = Facts((FactValue(Fact.COMMON_INTEREST, CommonInterest.CONDOMINIUM, Source.PROFILE, "the declaration"),
                  FactValue(Fact.ATTACHED_UNITS, 12, Source.PROFILE, "the largest building")))
    assert INSPECTED.reaches(base).answer is Answer.APPLIES
    verdict = TWO_UNITS.reaches(base)
    assert verdict.answer is Answer.DOES_NOT_APPLY
    assert all(v.value != 12 for v in verdict.deciding if v.fact is Fact.ATTACHED_UNITS)
    unknown = ElevatedElementsInspection("F", "building F")
    assert unknown.reaches(base).answer is Answer.UNDETERMINED
    assert set(unknown.reaches(base).missing) == {Fact.ELEVATED_ELEMENTS, Fact.ATTACHED_UNITS}
    assert INSPECTED.reaches(Facts()).answer is Answer.UNDETERMINED     # no kind of development stated
    assert unknown.units_rule().answer is Answer.UNDETERMINED


def test_years_after_lands_a_leap_day_on_february_28():
    assert years_after(date(2024, 2, 29), 9) == date(2033, 2, 28)
    assert years_after(date(2023, 11, 17), CYCLE_YEARS) == date(2032, 11, 17)


def test_the_calendar_lists_each_building_the_section_reaches(tmp_path):
    community = _community(INSPECTED, NEW_BUILDING, TWO_UNITS, UNREAD)
    rows = calendar_rows(community, TODAY)
    assert [r["name"] for r in rows] == [f"Exterior elevated elements inspection, {label}"
                                         for label in ("building A", "building B", "building D")]
    by = {r["name"].rsplit(", ", 1)[1]: r for r in rows}
    assert by["building A"]["next"] == "2032-11-17" and by["building A"]["standing"] == Standing.UPCOMING.value
    assert by["building A"]["lastDone"] == "2023-11-17"
    assert by["building B"]["next"] == "2028-06-15" and "(k)" in by["building B"]["note"]
    assert by["building D"]["next"] is None and by["building D"]["standing"] == "date not on record"
    assert "question:" in by["building D"]["note"]
    result = calendar(tmp_path, community, today=TODAY)
    names = [r["name"] for r in result["obligations"]]
    assert "Exterior elevated elements inspection, building D" in names
    assert any("never guessed" in c for c in result["caveats"])
    # An undetermined reach is said, not dropped: the building is listed with the question.
    rows = calendar_rows(_community(INSPECTED, condo=False), TODAY)
    assert len(rows) == 1 and "whether 5551 reaches it is undetermined" in rows[0]["note"]


def test_the_calendar_stands_without_the_buildings(tmp_path):
    community = SimpleNamespace(obligations=lambda: (), insurance=lambda: SimpleNamespace(policies=()))
    names = [r["name"] for r in calendar(tmp_path, community, today=TODAY)["obligations"]]
    assert not any(n.startswith("Exterior elevated elements") for n in names)


def test_building_lines_say_each_answer_and_the_questions():
    text = "\n".join(building_lines(_community(INSPECTED, NEW_BUILDING, TWO_UNITS, UNREAD), TODAY))
    assert "building A (12 attached units, 4 elevated elements)" in text
    assert "5551 reaches it: applies" in text and "5551 reaches it: does not apply" in text
    assert "(k): applies (the permit application of 2021-03-01 is on or after 2020-01-01)" in text
    assert "next due: 2032-11-17 under (b)(1), (i)" in text and "[upcoming]" in text
    assert "next due: not on record ((i) or (k))" in text
    assert "Questions for a person, by building (2)" in text
    assert "next due: none asked; the section does not reach it" in text
    # A building the section does not reach raises no question, though its own dates are unknown.
    base = Facts((FactValue(Fact.COMMON_INTEREST, CommonInterest.CONDOMINIUM, Source.PROFILE, "the declaration"),))
    assert TWO_UNITS.questions(base) == () and TWO_UNITS.questions() != ()
    empty = "\n".join(building_lines(_community(), TODAY))
    assert "lists no buildings' inspections (Community.elevated_elements_inspections())" in empty


def test_rows_become_records_with_symbols():
    records = from_rows([{"building": 3, "attached_units": "12", "responsibility": "association_responsible",
                          "inspected_on": "2023-11-17", "license": "architect", "report": "r"},
                         {"building": "", "note": "skipped"}], building_of=int)
    [record] = records
    assert record.building == 3 and record.label == "building 3" and record.attached_units == 12
    assert record.responsibility is RESP and record.license is InspectorLicense.ARCHITECT
    with pytest.raises(ValueError, match="not a date"):
        from_rows([{"building": 1, "inspected_on": "November 2023", "report": "r"}])
    with pytest.raises(ValueError):
        from_rows([{"building": 1, "responsibility": "maybe"}])
    assert json.dumps(record.as_dict()) and record.as_dict()["due"]["day"] == "2032-11-17"


def test_the_profile_reads_its_buildings_from_the_fixture():
    from jason.community import community
    from jason.community.symbols import Building

    found = community().elevated_elements_inspections()
    assert [r.building for r in found] == [Building.BLDG_1, Building.BLDG_2, Building.BLDG_3, Building.BLDG_4]
    assert found[0].license is InspectorLicense.ARCHITECT and found[0].due().day == date(2032, 11, 17)
    assert found[3].due().day is None


def test_jason_applies_prints_the_buildings(capsys, tmp_path):
    from jason.commands.applies import cmd_applies

    args = SimpleNamespace(env=None, data_dir=str(tmp_path), system=None, all=False, as_of="2026-10-05",
                           questions=False, file_questions=False, json=False)
    assert cmd_applies(args) == 0
    out = capsys.readouterr().out
    assert "Exterior elevated elements (Civil Code 5551), by building" in out
    assert "building 1 (12 attached units, 4 elevated elements)" in out
    args.json = True
    assert cmd_applies(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert [b["label"] for b in data["buildings"]] == ["building 1", "building 2", "building 3", "building 4"]
    assert data["buildings"][1]["permitRule"]["answer"] == "applies"
