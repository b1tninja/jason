from datetime import date
from pathlib import Path

from jason.community.parcel_history import build_parcel_history
from jason.community.property_report import index_markdown, mermaid_conveyances, parcel_markdown
from jason.community.recorder import ChainStep, Conveyance, FiledInstrument, OwnershipHistory
from jason.community.reports import HeldUnits, PlanBlock, PublicReport
from jason.community.scans import placement, read_scan, scan_index
from jason.community.symbols import Building
from jason.community.tax import TaxBill
from jason.tasks.property_history import format_requests, property_tabs
from mystique.buildings import STREETS
from mystique.developers import DEVELOPERS

APN = "20111700170008"
PHASE_1 = PublicReport("130654SA", Building.BLDG_8, 1, 12, date(2007, 11, 15), "John Laing Homes", opened=date(2007, 9, 28), issued=date(2007, 9, 26))
BLOCKS = (PlanBlock(Building.BLDG_3, "024", 21, 12, ("20111700160000",)), PlanBlock(Building.BLDG_8, "017", 81, 12, ("20111700040000",)))
HELD = (HeldUnits("201010121565", date(2010, 10, 12), Building.BLDG_3, (25, 26, 27, 30)),)

CACHE = {
    "200709281723": FiledInstrument("200709281723", date(2007, 9, 28), "notice", ("WL HOMES LLC",), (), (), "306", "NOTICE OF COMPLETION"),
    "200709281724": FiledInstrument("200709281724", date(2007, 9, 28), "fee", ("WL HOMES LLC",), ("TAMARACK DENNY C", "TAMARACK MELISA S"), (), "685", "GRANT DEED"),
    "200709281725": FiledInstrument("200709281725", date(2007, 9, 28), "lien", ("TAMARACK DENNY C", "TAMARACK MELISA S"), ("JOHN LAING MTG L P",), (), "230", "DEED OF TRUST"),
    "201204201319": FiledInstrument("201204201319", date(2012, 4, 20), "fee", ("TAMARACK DENNY C", "TAMARACK MELISA S"), ("QUINCE MICA K", "QUINCE STEVAN A"), (), "685", "GRANT DEED"),
    "201408010234": FiledInstrument("201408010234", date(2014, 8, 1), "fee", ("QUINCE MICA K", "QUINCE STEVAN A"), ("REDWOOD EUGEN S",), (), "685", "GRANT DEED"),
    "201511130485": FiledInstrument("201511130485", date(2015, 11, 13), "fee", ("REDWOOD EUGEN S",), ("OSPREY MINA T T", "PLOVER DUNC V"), (), "685", "GRANT DEED"),
    "201710301395": FiledInstrument("201710301395", date(2017, 10, 30), "fee", ("OSPREY MINA T T", "PLOVER DUNC V"), ("OSPREY TRINA M T TR", "PLOVER DUNC V TR"), (), "685", "GRANT DEED"),
}


def _deed(number, grantors, grantees, priors=()):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return ChainStep(Conveyance(number, recorded, tuple(grantors), tuple(grantees), (), APN), tuple(priors))


def _bill(year, dollars):
    return TaxBill(str(year), f"{year} Secured Annual Bill", year=year, land_cents=dollars * 30, improvement_cents=dollars * 70)


def _history():
    return OwnershipHistory(
        APN,
        (
            _deed("201710301395", ("OSPREY MINA T T", "PLOVER DUNC V"), ("OSPREY TRINA M T TR", "PLOVER DUNC V TR"), ("201511130485",)),
            _deed("201511130485", ("REDWOOD EUGEN S",), ("OSPREY MINA T T", "PLOVER DUNC V"), ("201408010234",)),
            _deed("201408010234", ("QUINCE MICA K", "QUINCE STEVAN A"), ("REDWOOD EUGEN S",), ("201204201319",)),
            _deed("201204201319", ("TAMARACK DENNY C", "TAMARACK MELISA S"), ("QUINCE MICA K", "QUINCE STEVAN A"), ("200709281724",)),
            _deed("200709281724", ("WL HOMES LLC",), ("TAMARACK DENNY C", "TAMARACK MELISA S")),
        ),
        DEVELOPERS,
    )


def _scans(tmp_path: Path):
    folder = tmp_path / "payhoa-files" / "documents" / "Grant Deeds"
    folder.mkdir(parents=True)
    (folder / "GD 201204201319.pdf.md").write_text(
        "A.P.N.: 201-1170-017-0008 GRANT DEED DOCUMENTARY TRANSFER TAX $110.00; CITY TRANSFER TAX $275.00 "
        "Melisa S. Tamarack and Denny C. Tamarack hereby GRANTS to Stevan A. Quince and Mica K. Quince "
        "the following described property: UNIT 88 IN BUILDING 8 5623 Whimsical Lane #88",
        encoding="utf-8",
    )
    (folder / "GD 200709281724.pdf.md").write_text(
        "A.P.N.: 201-1170-004-0000 GRANT DEED WL HOMES, LLC hereby GRANTS to Melisa S. Tamarack "
        "PARCEL ONE: UNIT 88 IN BUILDING 8 mail to 5623 Whimsical Lane",
        encoding="utf-8",
    )
    (folder / "GD 201511130485.pdf.md").write_text(
        "A.P.N.: 201-1170-017-0009 GRANT DEED DOCUMENTARY TRANSFER TAX $236.50; CITY TRANSFER TAX $591.25 "
        "Eugen S Redwood hereby GRANTS to Dunc Vale Plover UNIT 89",
        encoding="utf-8",
    )
    return scan_index(tmp_path, STREETS)


def test_a_scan_prints_the_parcel_the_unit_the_address_and_the_price(tmp_path: Path):
    scans = _scans(tmp_path)
    quince = scans["201204201319"]
    assert quince.unit_parcels == ("20111700170008",)
    assert quince.units == (88,)
    assert quince.addresses == ("5623 WHIMSICAL",)
    assert quince.price_cents == 10_000_000
    assert quince.source == "payhoa"
    tamarack = scans["200709281724"]
    assert tamarack.parent_parcels == ("20111700040000",) and tamarack.unit_parcels == ()
    assert placement(quince, "201-1170-017-0008", BLOCKS) == "parcel number"
    assert placement(tamarack, "201-1170-017-0008", BLOCKS) == "plan unit"
    assert placement(tamarack, "201-1170-017-0009", BLOCKS, "5619 WHIMSICAL LN") == "other unit"
    assert placement(tamarack, "201-1170-024-0013", (), "5623 WHIMSICAL LN") == "address"
    assert placement(scans["201511130485"], "201-1170-017-0008", BLOCKS) == "other parcel"
    # Watt reused units 21 to 32: a scan that prints only "Unit 24" places nothing on building 3.
    folder = tmp_path / "payhoa-files" / "documents" / "Grant Deeds"
    (folder / "GD 202112270972.pdf.md").write_text("GRANT DEED Watt Communities hereby GRANTS UNIT 24 IN BUILDING 4", encoding="utf-8")
    watt = read_scan("202112270972", folder / "GD 202112270972.pdf.md", "payhoa")
    assert watt.units == (24,) and watt.parent_parcels == ()
    assert placement(watt, "201-1170-024-0004", BLOCKS) == ""
    # A 2007 deed with the wrong parent for the block does not place either.
    (folder / "GD 200710260220.pdf.md").write_text("A.P.N.: 201-1170-004-0000 GRANT DEED UNIT 24", encoding="utf-8")
    other = read_scan("200710260220", folder / "GD 200710260220.pdf.md", "payhoa")
    assert placement(other, "201-1170-024-0004", BLOCKS) == ""


def _build(tmp_path: Path):
    bills = [_bill(y, v) for y, v in ((2013, 102_462), (2014, 104_511), (2015, 169_000), (2016, 215_000), (2017, 219_300))]
    return build_parcel_history(
        APN,
        history=_history(),
        developers=DEVELOPERS,
        address="5623 WHIMSICAL LN",
        building=8,
        report=PHASE_1,
        blocks=BLOCKS,
        held=HELD,
        bills=bills,
        scans=_scans(tmp_path),
        load=CACHE.get,
        notes=lambda number: ("checked",) if number == "201204201319" else (),
    )


def test_a_parcel_history_reads_each_deed_as_a_process_with_its_price_and_base(tmp_path: Path):
    item = _build(tmp_path)
    assert item.unit == 88 and item.phase == 1 and item.developer == "John Laing Homes"
    assert [step.process for step in item.steps] == ["developer closing", "resale", "resale", "resale", "restatement"]
    root, quince, redwood, osprey, trust = item.steps
    assert root.complete and root.developer == "John Laing Homes" and root.placement == "scan: plan unit"
    assert [r.role for r in root.related] == ["notice of completion", "buyer lien"]
    assert [r.role for r in osprey.related] == []  # the next number was someone else's grant
    assert quince.price_cents == 10_000_000 and quince.placement == "scan: parcel number"
    assert quince.reassesses and quince.bill_year is None  # the 2013 bill is the first on file
    assert redwood.bill_year == 2015 and redwood.enrolled_cents == 16_900_000 and redwood.placement == "handoff"
    assert osprey.placement == "scan prints another parcel"
    assert not trust.reassesses and trust.process == "restatement"
    assert item.sales == (root, quince, redwood, osprey)
    assert item.last_sale is osprey
    assert osprey.price_or_base == (21_500_000, "deed") and redwood.price_or_base == (16_900_000, "base")
    assert root.unpriced == "tax line not readable on the scan" and redwood.unpriced == "no scan on disk"
    assert quince.unpriced == "" and trust.unpriced == ""
    assert not item.open and item.verified == 2
    assert [finding.check for finding in item.findings] == []
    assert [(event.year, event.kind) for event in item.events] == [(2015, "sale"), (2016, "sale")]
    assert quince.notes == ("checked",)


def test_the_markdown_and_the_diagram_carry_the_process_the_price_and_the_related_filings(tmp_path: Path):
    item = _build(tmp_path)
    text = parcel_markdown(item)
    assert text.startswith("# 5623 WHIMSICAL LN")
    assert "unit 88 under the 2007 plan" in text and "phase 1" in text
    assert "| 2 | 2012-04-20 | 201204201319 | resale |" in text
    assert "$100,000" in text and "≈ $169,000 (base)" in text and "| no scan on disk |" in text
    assert "| 200709281724 | notice of completion | 200709281723 |" in text
    assert "Proposition 8 restoration" not in text
    assert "Clean." in text
    diagram = mermaid_conveyances(item)
    assert "class d200709281724 developer;" in diagram
    assert "class d201710301395 restatement;" in diagram
    assert "d200709281724 -->|scan: parcel number| d201204201319" in diagram
    assert "r200709281723 -. notice of completion .-> d200709281724" in diagram
    assert "classDef foreclosure" in diagram
    index = index_markdown((item,))
    assert "[201-1170-017-0008](20111700170008.md)" in index
    assert "1 chains reach the developer" in index


def test_an_open_parcel_draws_an_unknown_node_and_lists_in_open_items(tmp_path: Path):
    history = OwnershipHistory(
        "20111700170011",
        (
            _deed("202206150517", ("LINNET ALEKS",), ("HAZEL MORGAN",), ("202006121161",)),
            _deed("202006121161", ("MERLIN REGAN P JR",), ("LINNET ALEKS",)),
        ),
        DEVELOPERS,
    )
    item = build_parcel_history("20111700170011", history=history, developers=DEVELOPERS, address="5611 WHIMSICAL LN", report=PHASE_1, blocks=BLOCKS)
    assert item.open
    diagram = mermaid_conveyances(item)
    assert "unknown -.-> d202006121161" in diagram
    tabs = property_tabs((item,))
    assert tabs["Open items"][1][0] == "201-1170-017-0011"
    placed = FiledInstrument("202006121161", date(2020, 6, 12), "fee", ("MERLIN REGAN P JR",), ("LINNET ALEKS",), (), "685", "GRANT DEED")
    empty = build_parcel_history(
        "20111700170011", history=None, developers=DEVELOPERS, address="5611 WHIMSICAL LN",
        placed=lambda apn: (placed,) if apn == "20111700170011" else (),
    )
    assert empty.open and empty.findings[0].check == "root"
    assert empty.candidates == (placed,)
    assert "no deed stored" in mermaid_conveyances(empty)
    assert "## Placed on this parcel, not yet on the chain" in parcel_markdown(empty)
    assert "| 202006121161 | 2020-06-12 | 685 GRANT DEED | MERLIN REGAN P JR | LINNET ALEKS |  |" in parcel_markdown(empty)


def test_the_tabs_have_a_header_and_one_row_per_fact(tmp_path: Path):
    item = _build(tmp_path)
    tabs = property_tabs((item,))
    assert list(tabs) == ["Parcels", "Deed chain", "Related documents", "Sale prices", "Tax calendar", "Audit", "Open items", "Members", "Liens and notices", "Tax standing", "Owner events", "Solar"]
    assert tabs["Tax standing"][1][2] == "gap in the bills"  # the fixture bills carry values, not totals
    assert tabs["Members"][1][2] == "no member on file"
    assert len(tabs["Parcels"]) == 2 and tabs["Parcels"][1][0] == "201-1170-017-0008"
    assert len(tabs["Deed chain"]) == 6
    assert tabs["Deed chain"][2][4] == "201204201319" and tabs["Deed chain"][2][12] == 100000.0
    assert tabs["Deed chain"][1][13] == "tax line not readable on the scan"  # the Tamarack scan prints no tax line
    assert tabs["Sale prices"][3][7] == 169000.0 and tabs["Sale prices"][3][8] == "base"  # Quince to Redwood, priced from the base
    assert len(tabs["Related documents"]) == 3
    from jason.tasks.property_history import merge_county_tabs

    merged = merge_county_tabs(tabs, {"Sale prices": [["x"]], "Deed history": [["h"], ["r"]], "Ownership": [["o"]]})
    assert merged["Sale prices"] is tabs["Sale prices"]
    assert merged["Community deeds"] == [["h"], ["r"]] and merged["Assessor current"] == [["o"]]
    assert len(tabs["Sale prices"]) == 5
    assert tabs["Tax calendar"][1][2] == 2015
    assert len(tabs["Audit"]) == 1 and len(tabs["Open items"]) == 1
    requests = format_requests({"Parcels": 7}, {"Parcels": 22})
    assert [next(iter(request)) for request in requests] == ["updateSheetProperties", "repeatCell", "repeatCell", "autoResizeDimensions"]
    assert requests[-1]["autoResizeDimensions"]["dimensions"]["endIndex"] == 22


def test_a_hand_read_price_replaces_a_garbled_extract(tmp_path: Path):
    from jason.community.scans import hand_read_prices

    folder = tmp_path / "payhoa-files" / "documents" / "Grant Deeds"
    folder.mkdir(parents=True)
    (folder / "GD 200810170269.pdf.md").write_text("A.P.N.: 201-1170-016-0000 GRANT DEED DOCUMENTARY TRANSFER TAX $2&6,5O UNIT 28", encoding="utf-8")
    (tmp_path / "deed-prices.csv").write_text(
        "number,county_tax_cents,city_tax_cents,price_cents,exempt,source,note\n"
        "200810170269,23650,59125,21500000,,scan read by hand,Sample\n"
        "201112080254,0,,,true,scan read by hand,no tax due\n"
        "bad,1,2,3,,x,y\n",
        encoding="utf-8",
    )
    prices = hand_read_prices(tmp_path / "deed-prices.csv")
    assert set(prices) == {"200810170269", "201112080254"}
    assert prices["201112080254"].exempt and prices["201112080254"].price_cents is None
    scans = scan_index(tmp_path)
    assert scans["200810170269"].price_cents == 21_500_000
    assert scans["200810170269"].units == (28,)


def test_the_members_section_reads_payhoa_against_the_newest_deed(tmp_path: Path):
    from jason.community.members import occupancies

    unit = {
        "id": 1, "title": "5623 WHIMSICAL LN",
        "owners": [{"membershipId": 7, "unitOccupancyId": 3, "deletedAt": None}],
        "occupancies": [{"id": 3, "unitId": 1, "fromDate": "2024-01-14T01:42:08.000000Z", "toDate": None}],
    }
    periods = occupancies([unit], {7: "Dunc Plover"})
    bills = [_bill(y, v) for y, v in ((2013, 102_462), (2014, 104_511))]
    item = build_parcel_history(APN, history=_history(), developers=DEVELOPERS, address="5623 WHIMSICAL LN", bills=bills, periods=periods)
    assert item.membership is not None and item.membership.verdict == "agrees"
    text = parcel_markdown(item)
    assert "## PayHOA members" in text and "**agrees** since 2024-01-14" in text
    assert "| 2024-01-14 | current | Dunc Plover |" in text


def test_a_death_record_and_a_persons_note_show_on_the_parcel(tmp_path: Path):
    from jason.community.ownership import OwnershipRecord
    from jason.community.parcel_history import parcel_notes

    (tmp_path / "parcel-notes.csv").write_text(
        "apn,date,note,source\n"
        "201-1170-022-0099,2026-09-28,Robin Sample still lives here; her husband Kit died in 2021.,Jamie Director\n"
        "bad,,ignored,\n",
        encoding="utf-8",
    )
    notes = parcel_notes(tmp_path / "parcel-notes.csv")
    assert list(notes) == ["20111700220099"] and notes["20111700220099"][0].source == "Jamie Director"
    current = OwnershipRecord("20111700220099", "202102080001", date(2021, 2, 8), (), (), "DETH")
    assert current.conveys is False
    item = build_parcel_history(
        "20111700220099", history=None, developers=DEVELOPERS, address="999 MACON DR",
        current=current, notes_for_parcel=notes["20111700220099"],
    )
    assert item.current_type == "DETH" and not item.current_conveys
    text = parcel_markdown(item)
    assert "a death record the assessor lists" in text
    assert "## Notes" in text and "Robin Sample still lives here" in text and "Jamie Director" in text
    assert property_tabs((item,))["Parcels"][1][-1].startswith("Robin Sample")


def test_a_common_area_is_held_by_the_association_and_skips_the_developer_checks(tmp_path: Path):
    from jason.community.ownership import OwnershipRecord

    land = ChainStep(Conveyance("200605041076", date(2006, 5, 4), ("REYNEN & BARDIS COMMUNITIES INC",), ("WL HOMES LLC",), (), "20111700170013"))
    grant = ChainStep(Conveyance("200709281731", date(2007, 9, 28), ("WL HOMES LLC",), ("MYSTIQUE COMMUNITY ASSN",), (), "20111700170013"), ("200605041076",))
    history = OwnershipHistory("20111700170013", (grant, land), DEVELOPERS)
    current = OwnershipRecord("20111700170013", "200709281731", date(2007, 9, 28), ("WL HOMES LLC",), ("MYSTIQUE COMMUNITY ASSN",), "GD")
    item = build_parcel_history("20111700170013", history=history, developers=DEVELOPERS, address="5649 WHIMSICAL LN", current=current, association=True)
    assert item.association and not item.open and item.membership is None
    assert [finding.check for finding in item.findings] == []
    text = parcel_markdown(item)
    assert "a common area of the association" in text
    assert "**Held by** MYSTIQUE COMMUNITY ASSN since 2007-09-28 under 200709281731" in text
    assert "no member is on title" in text
    assert "common area, clean" in index_markdown((item,))
    assert property_tabs((item,))["Parcels"][1][-4].startswith("common area")


def test_the_unpriced_reason_names_the_cause():
    from jason.community.consideration import DeedPrice
    from jason.community.parcel_history import unpriced_reason
    from jason.community.scans import DeedScan

    def scan(price):
        return DeedScan("1", Path("x.pdf.md"), "payhoa", (), (), (), (), price)

    assert unpriced_reason(None, True, "resale") == "no scan on disk"
    assert unpriced_reason(None, False, "restatement") == ""
    assert unpriced_reason(scan(DeedPrice(0, 0, False, None)), True, "developer closing") == "tax declared separately, not on the deed"
    assert unpriced_reason(scan(DeedPrice(0, None, True, None)), True, "reo resale") == "exempt from transfer tax"
    assert unpriced_reason(scan(DeedPrice(None, None, False, None)), True, "foreclosure") == "trustee's deed prints the bid, not a tax"
    assert unpriced_reason(scan(DeedPrice(26180, 70000, False, None)), True, "resale") == "county and city figures disagree"
    assert unpriced_reason(scan(DeedPrice(None, None, False, None)), True, "resale") == "tax line not readable on the scan"
    assert unpriced_reason(scan(DeedPrice(11000, 27500, False, 10_000_000)), True, "resale") == ""
