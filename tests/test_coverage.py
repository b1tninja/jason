"""Every cached index document read against the known processes, and the leftovers sorted by pattern."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace as NS

from jason.community import mystique
from jason.community.coverage import Bucket, coverage
from jason.community.filings import Process
from jason.community.recorder import FiledInstrument


def _doc(number, day, code, name, grantors, grantees, kind="fee", refs=()):
    return FiledInstrument(number, day, kind, tuple(grantors), tuple(grantees), tuple(refs), code, name)


def test_beside_step_tells_a_re_recording_from_a_second_unit_and_a_companion():
    from jason.community.processes import COMPANION, RERECORDING, SAME_DAY_TWIN, beside_step

    step = _doc("202111301838", date(2021, 11, 30), "685", "GRANT DEED", ["WATT COMMUNITIES AT MYSTIQUE LLC"], ["VELLACOTT CALDER C"])
    same_day = _doc("202111301835", date(2021, 11, 30), "685", "GRANT DEED", ["WATT COMMUNITIES AT MYSTIQUE LLC"], ["VELLACOTT CALDER C"])
    later = _doc("202112270972", date(2021, 12, 27), "685", "GRANT DEED", ["WATT COMMUNITIES AT MYSTIQUE LLC"], ["VELLACOTT CALDER C"])
    spouse = _doc("202111301834", date(2021, 11, 30), "685", "GRANT DEED", ["VELLACOTT DELPHINE R"], ["VELLACOTT CALDER C"])
    loan = _doc("202111301839", date(2021, 11, 30), "230", "DEED OF TRUST", ["VELLACOTT CALDER C"], ["BIG BANK"])
    grantees = step.grantees
    assert beside_step(same_day, step.number, step, grantees)[0] == SAME_DAY_TWIN
    assert beside_step(later, step.number, step, grantees) == (RERECORDING, "same parties as chain step 202111301838, 27 days apart")
    assert beside_step(spouse, step.number, step, grantees)[0] == COMPANION
    assert beside_step(loan, step.number, step, grantees) is None and beside_step(step, step.number, step, grantees) is None
    cites = _doc("202201201503", date(2022, 1, 20), "685", "GRANT DEED", ["WATT COMMUNITIES LLC"], ["WINTERBOURNE PIA TAVISH"], refs=("202112281302",))
    assert beside_step(cites, "202112281302", None, ("WINTERBOURNE PIA TAVISH",)) == (RERECORDING, "cites chain step 202112281302")


def test_coverage_places_every_document_and_sorts_the_leftovers():
    community = mystique()
    developer = "WATT COMMUNITIES AT MYSTIQUE LLC"
    step1 = NS(number="202001010001", recorded=date(2020, 1, 1), process="deed", grantees=("DOE JANE",), related=(NS(number="202001010002", role="purchase loan"),))
    step2 = NS(number="202301010001", recorded=date(2023, 1, 1), process="deed", grantees=("LEE MIN",), related=())
    lien = NS(encumbrance=NS(process=Process.MECHANICS_LIEN, steps=(NS(number="202106010001"),)), where="on the unit")
    history = NS(
        apn="201-1170-022-0013", association=False, steps=(step1, step2), liens=(lien,),
        owner_events=(NS(number="202201010009", kind="homestead declared"),), candidates=(NS(number="202201010010"),),
        solar=NS(notices=(NS(number="202007090001"),)),
    )
    record = NS(
        governing=(NS(number="200709120758", role="declaration"),), unplaced=(),
        placed=(NS(steps=(NS(number="202107090215"),)),), against=(), construction=(), notices=(NS(number="202001010099"),),
    )
    docs = (
        _doc("202001010001", date(2020, 1, 1), "685", "GRANT DEED", [developer], ["DOE JANE"]),
        _doc("202001010002", date(2020, 1, 1), "376", "DEED OF TRUST", ["DOE JANE"], ["BIG BANK"]),
        _doc("202301010001", date(2023, 1, 1), "685", "GRANT DEED", ["DOE JANE"], ["LEE MIN"]),
        _doc("202106010001", date(2021, 6, 1), "389", "NOTICE OF CLAIM OR MECHANICS LIEN", ["DOE JANE"], ["ROOFER INC"]),
        _doc("202201010009", date(2022, 1, 1), "457", "DECLARATION OF HOMESTEAD", ["DOE JANE"], []),
        _doc("202007090001", date(2020, 7, 9), "549", "NOTICE", ["DOE JANE"], ["ULTRALIGHT RESIDENTIAL SOLAR LLC"]),
        _doc("200709120758", date(2007, 9, 12), "324", "DECLARATION OF RESTRICTION", ["WL HOMES LLC"], []),
        _doc("202107090215", date(2021, 7, 9), "401", "UTILITY BILLING LIEN", ["MYSTIQUE COMMUNITY ASSOCIATION"], ["CITY"]),
        _doc("201001010001", date(2010, 1, 1), "685", "GRANT DEED", ["CORIN OSTWICK FAMILY PTP L P"], ["MYSTIQUE BLDRS LLC"]),
        # A re-recording: the same parties as a chain step, days later, citing it.
        _doc("202001080001", date(2020, 1, 8), "685", "GRANT DEED", [developer], ["DOE JANE"], refs=("202001010001",)),
        # A companion: a family transfer the day of the second sale.
        _doc("202301010002", date(2023, 1, 1), "685", "GRANT DEED", ["LEE MIN"], ["LEE SOO"]),
        # The owner's other property, before tenure.
        _doc("201501010001", date(2015, 1, 1), "685", "GRANT DEED", ["DOE JANE"], ["BUYER BOB"]),
        # The owner's other property during tenure: a conveyance the parcel history does not hold.
        _doc("202106150001", date(2021, 6, 15), "685", "GRANT DEED", ["DOE JANE"], ["BUYER ANN"]),
        # A lien naming an owner during tenure that no parcel process holds.
        _doc("202107150001", date(2021, 7, 15), "368", "UCC FINANCING STATEMENT", ["DOE JANE"], ["MELLON FINL SERVS"]),
        # The developer elsewhere, and the developer's insolvency.
        _doc("199906230974", date(1999, 6, 23), "320", "DECLARATION OF ANNEXATION", ["WL HOMES LLC"], []),
        _doc("200905040767", date(2009, 5, 4), "385", "NOTICE OF ACTION", ["WL HOMES LLC"], ["ROOFING CO"]),
        # Nobody the community knows.
        _doc("185805200159", date(1858, 5, 20), "689", "QUITCLAIM DEED", ["ZELLBY QUINTUS G"], ["CROWHURST ULRIC B C"]),
    )
    result = coverage(
        (history,), record, docs, developers=community.developers(), association=community.index_association(),
        project=community.index_project(), land_chain=("201001010001",), examples=3,
    )
    placed = {n: p.bucket for n, p in result.placed.items()}
    assert placed["202001010001"] is Bucket.CHAIN and placed["202001010002"] is Bucket.RELATED
    assert placed["202106010001"] is Bucket.LIEN and placed["202201010009"] is Bucket.OWNER_EVENT and placed["202201010010"] is Bucket.CANDIDATE
    assert placed["202007090001"] is Bucket.SOLAR_NOTICE and placed["200709120758"] is Bucket.GOVERNING
    assert placed["202107090215"] is Bucket.ASSOCIATION and placed["202001010099"] is Bucket.ASSOCIATION and placed["201001010001"] is Bucket.LAND_CHAIN
    assert placed["202001080001"] is Bucket.RERECORDING and placed["202301010002"] is Bucket.COMPANION
    assert placed["201501010001"] is Bucket.OWNER_OTHER and placed["202106150001"] is Bucket.OWNER_OTHER
    assert placed["202107150001"] is Bucket.UNRESOLVED and "during tenure" in result.placed["202107150001"].why
    assert placed["199906230974"] is Bucket.DEVELOPER_OTHER and placed["200905040767"] is Bucket.DEVELOPER_INSOLVENCY
    assert placed["185805200159"] is Bucket.NOISE
    assert result.total == len(docs) and result.counts["names no community party"] == 1
    payload = result.as_dict()
    assert payload["documents"] == len(docs) and "chain step" not in payload["examples"]
    example = payload["examples"]["re-recording of a chain step"][0]
    assert example["number"] == "202001080001" and example["apn"] == "201-1170-022-0013" and "cites chain step" in example["why"]
