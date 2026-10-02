from datetime import date

from jason.community.association_record import RecordedAssociation
from jason.community.filings import CLOSES, OPENS, Encumbrance, Process, Step
from jason.community.governing import GoverningRecord
from jason.community.records_request import request_markdown, request_rows
from jason.community.symbols import DeveloperDelivery


def _record():
    governing = (
        GoverningRecord("200709200938", date(2007, 9, 20), "220 AMENDED RESTRICTION", "restatement or amendment", DeveloperDelivery.DECLARATION, ("WL HOMES LLC",), None, (), "John Laing Homes"),
        GoverningRecord("201905221469", date(2019, 5, 22), "320 DECLARATION OF ANNEXATION", "annexation", DeveloperDelivery.DECLARATION, ("WATT",), 4, (), "Watt Communities at Mystique", superseded_by="202003021215"),
        GoverningRecord("202003021215", date(2020, 3, 2), "220 AMENDED RESTRICTION", "annexation", DeveloperDelivery.DECLARATION, ("WATT",), 4, (), "Watt Communities at Mystique"),
    )
    lien = Encumbrance(Process.ASSESSMENT_LIEN, ("OWNER JANE",), ("MYSTIQUE COMMUNITY ASSN",), (
        Step("201606270001", date(2016, 6, 27), "386 NOTICE OF ASSOCIATION LIEN", OPENS, ("OWNER JANE",), ("MYSTIQUE COMMUNITY ASSN",)),
        Step("201712270001", date(2017, 12, 27), "655 RELEASE OF ASSESSMENT OF ASSOCIATION LIEN", CLOSES, ("MYSTIQUE COMMUNITY ASSN",), ("OWNER JANE",)),
    ))
    return RecordedAssociation(governing, (), (lien,), (), (), ())


def test_the_request_lists_what_is_missing_prices_it_and_marks_estimates():
    rows = request_rows(_record(), on_disk={"202003021215"}, pages={"200709200938": 63})
    assert [row.number for row in rows] == ["200709200938", "201606270001", "201712270001", "201905221469"]  # by priority, then date
    restated = rows[0]
    assert restated.priority == 1 and restated.certified and restated.pages == 63 and not restated.pages_estimated
    assert restated.cost_cents == 900 + 100 * 62 and restated.book == "20070920" and restated.page == "0938"
    rescinded = rows[3]
    assert rescinded.priority == 3 and "rescinded and superseded by 202003021215" in rescinded.why and rescinded.pages_estimated and rescinded.page_count == 7
    assert rescinded.cost_cents == 800 + 600
    lien = rows[1]
    assert lien.role == "assessment lien" and "collections file" in lien.why and lien.page_count == 4 and lien.cost_cents == 1100
    text = request_markdown(rows, title="T")
    assert text.startswith("# T\n\n4 recorded instruments") and "| 1 | 200709200938 | 20070920 | 0938 | 2007-09-20 |" in text and "7* |" in text
    assert "$8.00 for the first page" in text and "3636 American River Drive" in text
    assert request_rows(_record(), on_disk={"202003021215"}, include_liens=False)[-1].number == "201905221469"


def test_a_model_read_copy_stays_listed_at_the_lowest_priority_for_verification():
    rows = request_rows(_record(), on_disk=set(), model_read={"200709200938": {"file": "CCRs.pdf", "model": "qwen3.5:9b", "read": "2026-09-28"}})
    read = next(row for row in rows if row.number == "200709200938")
    assert read.priority == 4 and read.model_read == "CCRs.pdf" and read.why.startswith("a copy on disk, CCRs.pdf, reads as this instrument to qwen3.5:9b")
    assert rows[-1] is read and "verify that copy before ordering" in request_markdown(rows, title="T")
