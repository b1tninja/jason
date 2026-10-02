"""Community specification: Mystique facts stay out of task code."""

from jason.community import (
    Building,
    BuildingRange,
    DocumentRule,
    Parity,
    Street,
    Utility,
    assign_building,
    mystique,
)


def test_reserve_components_keep_cost_center_and_life():
    from jason.community import ComponentMajor, CostCenter, KnownFile

    community = mystique()
    rows = community.reserve_components()
    assert len(rows) == 73
    assert {row.cost_center for row in rows} == set(CostCenter)
    sheet = community.known_file(KnownFile.RESERVE_COMPONENTS)
    assert sheet.drive_id == "1olOFGoQL3EAwIlTujWE_arO00tNolsPI_bNw9tAhwok"
    bark = next(row for row in rows if row.description.startswith("490 - Bark"))
    assert bark.cost_center is CostCenter.COMMON
    assert bark.major is ComponentMajor.LANDSCAPING
    assert bark.useful_life_years == 3
    assert bark.remaining_life_years == 0
    assert bark.cost_cents == 404200
    mains = [row for row in rows if row.major is ComponentMajor.PLUMBING]
    assert mains and all(row.cost_cents is None for row in mains)


def test_mystique_org_and_rules_come_from_the_spec():
    community = mystique()
    assert community.name == "Mystique Community Association"
    assert community.org_id == 27889
    assert DocumentRule.INSURANCE_CURRENT in community.document_rules()
    assert community.insurance_workbook_id().startswith("1Z-")
    from jason.community import KnownFile, MembershipTab, PayhoaFolder, PublicDrive, SitePage

    alpr = community.known_file(KnownFile.ALPR_POLICY)
    policies = community.library_folder(PayhoaFolder.POLICIES)
    assert alpr.payhoa_folder is PayhoaFolder.POLICIES
    assert policies.drive is PublicDrive.POLICIES
    membership = community.known_file(KnownFile.MEMBERSHIP)
    assert membership.drive_id.startswith("1LFw")
    assert community.corporate_name == "MYSTIQUE COMMUNITY ASSOCIATION"
    assert len(community.units()) == 81
    assert community.units()[0] == "20111700220010"
    assert community.common_areas() == (
        "20111700170013",
        "20111700180000",
        "20111700190000",
        "20111700220017",
        "20111700230024",
        "20111700240013",
        "20111700250024",
        "20111700260024",
        "20111700270024",
        "20111700280024",
    )
    assert community.parcels() == community.units() + community.common_areas()
    assert community.ccrs.cite() == "CC&Rs"
    # The Restated Declaration; its recital F rescinds the September 12, 2007 declaration (200709120758).
    assert community.ccrs.recorder_number == "200709200938"
    assert community.ccrs.recorded.isoformat() == "2007-09-20"
    assert community.ccrs.drive_id.startswith("1hJc")
    assert [row.drive_id[:4] for row in community.ccrs.instruments] == ["1hJc", "1yzs", "1ArM", "1Sz8"]
    assert community.ccrs.amendments[0].recorder_number == "202001170712"
    assert community.ccrs.amendments[0].sections == ("4.15(o)",)
    assert community.ccrs.amendments[1].sections == ("4.15(a)", "4.15(m)(iii)", "4.15(n)")
    assert community.ccrs.amendments[1].recorder_number == "202312060284"
    assert MembershipTab.ROSTER.value == "Roster"
    assert policies.payhoa_id == 1018661
    assert policies.path == "Governing Documents/Policies/"
    insurance = next(rule for rule in community.sync_rules if rule.id is DocumentRule.INSURANCE_CURRENT)
    assert insurance.drive is PublicDrive.INSURANCE
    from jason.community.documents import profile
    from jason.community.records import citation
    from jason.community.symbols import AssociationRecord, DocumentCategory, DocumentKind

    assert AssociationRecord.GOVERNING_DOCUMENTS in policies.records
    assert citation(AssociationRecord.GOVERNING_DOCUMENTS) == "CIV 5200(a)(11)"
    assert community.ccrs.record is AssociationRecord.GOVERNING_DOCUMENTS
    assert community.ccrs.document_kind is DocumentKind.DECLARATION
    assert community.ccrs.category is DocumentCategory.GOVERNING
    assert community.ccrs.amendments[0].document_kind is DocumentKind.AMENDMENT
    assert community.classify_document("CCRs - 2nd Amendment") is DocumentKind.AMENDMENT
    assert community.classify_document("CCRs.pdf") is DocumentKind.DECLARATION
    assert community.classify_document("ALPR Policy.pdf", PayhoaFolder.POLICIES) is DocumentKind.POLICY
    assert community.classify_document("FLOOD POLICY 26-27 BLDG 1.pdf") is DocumentKind.INSURANCE_POLICY
    assert community.classify_document("notes.txt") is None
    assert community.classify_document("Treasurer's Report 2026-08.pdf") is DocumentKind.TREASURER_REPORT
    assert community.classify_document("Treasurer's Report - 2026-08_Redacted.pdf", PayhoaFolder.FINANCIALS) is DocumentKind.TREASURER_REPORT
    assert community.classify_document("Treasurer's Report- 2024-03_Redacted.pdf") is DocumentKind.TREASURER_REPORT
    assert profile(DocumentKind.TREASURER_REPORT).record is AssociationRecord.INTERIM_FINANCIAL
    bylaws = next(row for row in community.pins() if row.title == "Bylaws")
    assert bylaws.kind is DocumentKind.BYLAWS
    assert bylaws.record is AssociationRecord.GOVERNING_DOCUMENTS
    flood = next(row for row in community.pins() if row.title.startswith("FLOOD POLICY 26-27 BLDG 1"))
    assert flood.record is AssociationRecord.EXECUTED_CONTRACT
    assert flood.group("term") == "26-27"
    assert flood.group("building") == "1"
    assert AssociationRecord.EXECUTED_CONTRACT in insurance.records
    assert AssociationRecord.MINUTES in community.known_file(KnownFile.MINUTES_2026_07_07).records
    assert community.library_folder(PayhoaFolder.PLANS).records == ()
    from datetime import date

    from jason.community import PolicyKind

    catalog = community.insurance()
    flood = catalog.flood_policy(Building.BLDG_3)
    assert flood.kind is PolicyKind.FLOOD
    # The real policy number stays in the private specification; check its form, not the number.
    assert len(flood.number) == 10 and flood.number.startswith("50100") and flood.number.isdigit()
    assert flood.renewal == date(2026, 12, 3)
    assert flood.location_prints_building
    from jason.community import InsuranceVisit

    assert catalog.match("Insurance/2021") == 2021
    assert catalog.visit("Insurance/2021") is InsuranceVisit.YEAR_FOLDER
    assert catalog.visit("Insurance/2024/FLOOD POLICY 25-26 BLDG 5.pdf") is InsuranceVisit.YEAR_FOLDER
    assert catalog.visit("Insurance/FLOOD POLICY 26-27 BLDG 1.pdf") is InsuranceVisit.ROOT_FILE
    assert catalog.visit("Insurance/notes.txt") is InsuranceVisit.SKIP
    assert community.document_sync_rules()["rules"][0]["payhoa"] == "Governing Documents/"
    meetings = community.library_folder(PayhoaFolder.MEETINGS_2026)
    assert meetings.payhoa_id == 2643621
    insurance_page = next(page for page in community.site_pages() if page.page is SitePage.INSURANCE)
    assert PayhoaFolder.INSURANCE in insurance_page.payhoa_folders
    roots = {root.payhoa_folder for root in community.drive_roots()}
    assert PayhoaFolder.GOVERNING_DOCUMENTS in roots


def test_public_reports_catalog_each_phase_and_its_files():
    from datetime import date

    from jason.community.reports import catalog_reports, report_file_number
    from jason.mcp.county import list_public_reports

    community = mystique()
    reports = community.public_reports()
    assert tuple(item.phase for item in reports) == (1, 2, 3, 4, 5, 6, 7, 8)
    assert sum(item.units for item in reports) == 81
    assert reports[0].file_number == "130654SA"
    assert reports[0].annexation is None
    assert reports[0].assessment_cents is None
    assert reports[0].opened == date(2007, 9, 28)
    assert reports[0].issued == date(2007, 9, 26)
    assert reports[0].first_conveyance == date(2007, 11, 15)
    assert reports[1].issued == date(2008, 2, 1)
    assert reports[1].assessment_cents == 28_500
    catalog = catalog_reports(reports, community.pins())
    phase_1 = catalog[0]
    assert report_file_number("130654SA-F00_2.PDF") == "130654SA"
    assert [row.title for row in phase_1.copies] == ["130654SA-F00_2.PDF"]
    assert phase_1.annexations == ()
    phase_3 = catalog[2]
    assert {row.title for row in phase_3.copies} == {"154410SA-A01.pdf"}  # phase 3 is building 1; its Bureau file is 154410SA
    assert any(row.title == "Annexation - Phase 3.pdf" for row in phase_3.annexations)
    assert any("AMENDED" in row.title for row in phase_3.annexations)
    phase_8 = catalog[7]
    assert phase_8.report.related[0].role == "bond_release"
    assert any(row.title == "Annexation - Phase 8.pdf" for row in phase_8.annexations)
    listed = list_public_reports()
    assert listed[0]["opened"] == "2007-09-28"
    assert listed[0]["issued"] == "2007-09-26"
    assert listed[1]["opened"] == ""
    assert listed[1]["issued"] == "2008-02-01"
    assert listed[3]["fileNumber"] == "160779SA"
    assert listed[3]["building"] == 7
    assert listed[3]["assessmentCents"] == 27_500
    assert len(listed[4]["copies"]) == 3


def test_three_developers_are_pinned_on_the_community():
    community = mystique()
    developers = community.developers()
    assert tuple(item.name for item in developers) == (
        "John Laing Homes",
        "Mystique Builders",
        "Watt Communities at Mystique",
    )
    assert community.index_project() == "MYSTIQUE"
    assert community.index_association() == "MYSTIQUE COMMUNITY"


def test_developer_file_locates_the_subdivider_documents():
    import pytest

    from jason.community.documents import deliver, pin
    from jason.community.symbols import DeveloperDelivery, DocumentKind

    community = mystique()
    located = community.developer_file()
    final_map = located[DeveloperDelivery.SUBDIVISION_MAP]
    assert [row.title for row in final_map] == ["Final Map of JMA North Natomas Parcel 4.pdf"]
    assert final_map[0].record is None
    assert len(located[DeveloperDelivery.CONDOMINIUM_PLAN]) == 3
    assert len(located[DeveloperDelivery.COMMON_AREA_DEED]) == 21
    numbers = community.deed_numbers()
    assert len(numbers) == 20
    assert numbers[0] == "200605041076"
    assert "202203180704" in numbers
    assert numbers.count("200709281731") == 1
    assert "200709120758" not in numbers
    assert "GD 202608170212.pdf" not in {row.title for row in community.pins()}
    assert any(row.title == "Annexation - Phase 8.pdf" for row in located[DeveloperDelivery.DECLARATION])
    assert len(located[DeveloperDelivery.PUBLIC_REPORT]) == 11
    assert any(row.title == "John Laing Homes" for row in located[DeveloperDelivery.MAINTENANCE_PLANS])
    assert community.classify_document("DR18-052_PLANS.pdf") is DocumentKind.PLAN_SET
    for item in (
        DeveloperDelivery.NOTICE_OF_COMPLETION,
        DeveloperDelivery.BOND,
        DeveloperDelivery.WARRANTY,
        DeveloperDelivery.CONTRACT,
        DeveloperDelivery.BOOKS,
        DeveloperDelivery.MINUTES,
        DeveloperDelivery.RECIPROCAL_INSTRUMENT,
    ):
        assert located[item] == ()
    with pytest.raises(ValueError, match="not an association record"):
        pin("Final Map of JMA North Natomas Parcel 4.pdf", "11Ih", DocumentKind.MAP)
    row = deliver("Final Map of JMA North Natomas Parcel 4.pdf", "11Ih", DocumentKind.MAP, DeveloperDelivery.SUBDIVISION_MAP)
    assert row.delivery is DeveloperDelivery.SUBDIVISION_MAP


def test_odd_and_even_addresses_are_different_buildings():
    community = mystique()
    odd = community.building_for_address("3007 ENCHANTED WALK")
    even = community.building_for_address("3006 ENCHANTED WALK")
    assert odd is not None and odd.number is Building.BLDG_2
    assert odd.street is Street.ENCHANTED_WALK and odd.parity is Parity.ODD
    assert even is not None and even.number is Building.BLDG_3
    assert community.building_for_address("5655 WHIMSICAL LN") is None
    assert community.building_for_address("3024 MACON DR").number is Building.BLDG_1


def test_path_pattern_names_the_year_segment():
    from jason.community.documents import PathPattern

    pattern = PathPattern("Financials/{year}/")
    hit = pattern.match("Financials/2026/Treasurer's Report - 2026-08_Redacted.pdf")
    assert hit is not None
    assert hit.group("year") == "2026"
    assert pattern.match("Confidential/Complete Financial Statements/2026/Treasurer's Report - 2026-08.pdf") is None
    complete = PathPattern("Confidential/Complete Financial Statements/{year}/")
    complete_hit = complete.match("Confidential/Complete Financial Statements/2026/Treasurer's Report - 2026-08.pdf")
    assert complete_hit is not None and complete_hit.group("year") == "2026"
    either = PathPattern("{Financials,Resale Documents}/{year}/Treasurer*Report*")
    resale = either.match("Resale Documents/2026/Treasurer's Report - 2026-03_Redacted.pdf")
    assert resale is not None and resale.group("year") == "2026"


def test_assign_building_helper_rejects_overlap():
    ranges = (
        BuildingRange(Building.BLDG_1, Street.MACON_DR, 1, 10, Parity.ANY),
        BuildingRange(Building.BLDG_2, Street.MACON_DR, 1, 10, Parity.ANY),
    )
    assert assign_building("4 MACON DR", ranges) is None
    loaded = mystique()
    assert loaded.building_for_address("3040 MESMERIZING WALK").number is Building.BLDG_7
    utilities = [rule.utility for rule in loaded.transaction_rules()]
    assert utilities[0] is Utility.SMUD
    assert Utility.CITY_OF_SACRAMENTO in utilities
    from jason.payhoa_tx import is_city_sac_transaction, is_smud_transaction

    smud = {"description": "ORIG CO NAME:SMUD", "transactionRule": {"name": "SMUD"}}
    city = {"description": "CITY OF SACRAMENTO UTILITIES"}
    assert is_smud_transaction(smud)
    assert not is_city_sac_transaction(smud)
    assert is_city_sac_transaction(city)


def test_a_whimsical_address_on_a_phase_block_is_that_phase():
    from jason.community.reports import parcel_block, phases_for_blocks

    reports = mystique().public_reports()
    situated = (
        ("201-1170-022-0010", Building.BLDG_1),
        ("20111700220016", None),
        ("20111700230022", Building.BLDG_2),
        ("20111700230023", None),
        ("20111700240001", Building.BLDG_3),
        ("20111700240012", None),
        ("20111700250022", Building.BLDG_4),
        ("20111700250023", None),
        ("20111700260014", Building.BLDG_5),
        ("20111700260023", None),
        ("20111700270022", Building.BLDG_6),
        ("20111700270023", None),
        ("20111700280014", Building.BLDG_7),
        ("20111700280023", None),
        ("20111700170001", Building.BLDG_8),
        ("20111700990001", Building.BLDG_1),
        ("20111700990002", Building.BLDG_2),
    )
    phases = phases_for_blocks(situated, reports)
    assert parcel_block("201-1170-022-0016") == "022"
    assert phases["022"].phase == 3
    assert phases["023"].phase == 8
    assert phases["024"].phase == 2
    assert phases["025"].phase == 7
    assert phases["026"].phase == 6
    assert phases["027"].phase == 5
    assert phases["028"].phase == 4
    assert phases["017"].phase == 1
    assert "099" not in phases


def test_the_original_phase_includes_the_common_area_day():
    from datetime import date

    from jason.community.reports import deed_in_phase

    reports = {item.phase: item for item in mystique().public_reports()}
    assert deed_in_phase(date(2007, 9, 28), reports[1])
    assert deed_in_phase(date(2007, 10, 26), reports[1])
    assert deed_in_phase(date(2007, 11, 15), reports[1])
    assert not deed_in_phase(date(2007, 9, 24), reports[1])
    assert deed_in_phase(date(2007, 9, 26), reports[1])
    assert not deed_in_phase(date(2007, 9, 25), reports[1])
    assert deed_in_phase(date(2008, 6, 27), reports[1])
    assert deed_in_phase(date(2022, 3, 16), reports[8])
    assert not deed_in_phase(date(2022, 3, 14), reports[8])
    assert deed_in_phase(date(2008, 2, 1), reports[2])
    assert deed_in_phase(date(2008, 2, 25), reports[2])
    assert not deed_in_phase(date(2007, 12, 19), reports[2])


def test_a_developer_deed_belongs_to_the_phase_that_had_just_opened():
    from datetime import date

    from jason.community.reports import phase_on

    reports = mystique().public_reports()
    assert phase_on(date(2007, 11, 15), reports).phase == 1
    assert phase_on(date(2008, 2, 29), reports).phase == 2
    assert phase_on(date(2020, 2, 28), reports).phase == 3
    assert phase_on(date(2020, 4, 20), reports).phase == 4
    assert phase_on(date(2021, 2, 24), reports).phase == 5
    assert phase_on(date(2021, 11, 30), reports).phase == 6
    assert phase_on(date(2021, 12, 28), reports).phase == 7
    assert phase_on(date(2022, 3, 16), reports).phase == 8
    assert phase_on(date(2022, 3, 15), reports).phase == 8
    assert phase_on(date(2022, 3, 14), reports).phase == 7
    assert phase_on(date(2012, 3, 27), reports).phase == 2


def test_a_building_3_unit_left_off_the_receiver_deed_was_already_sold():
    from jason.community.reports import plan_unit, still_held

    community = mystique()
    blocks = community.plan_blocks()
    held = community.held_units()[0]
    assert held.number == "201010121565"
    assert plan_unit("201-1170-024-0004", blocks) == 24
    assert plan_unit("20111700240005", blocks) == 25
    assert plan_unit("20111700240010", blocks) == 30
    assert plan_unit("20111700240002", blocks) == 22
    assert plan_unit("20111700240009", blocks) == 29
    assert plan_unit("20111700240013", blocks) is None
    assert plan_unit("20111700170001", blocks) == 81
    assert plan_unit("20111700170011", blocks) == 91
    assert plan_unit("20111700170013", blocks) is None
    assert still_held("20111700240005", blocks, held) is True
    assert still_held("20111700240006", blocks, held) is True
    assert still_held("20111700240007", blocks, held) is True
    assert still_held("20111700240010", blocks, held) is True
    assert still_held("20111700240002", blocks, held) is False
    assert still_held("20111700240009", blocks, held) is False
    assert still_held("20111700170005", blocks, held) is None


def test_a_plan_unit_names_the_parcel_and_a_parent_parcel_names_none():
    from jason.community.reports import parent_parcel, plan_unit, unit_parcel

    blocks = mystique().plan_blocks()
    assert unit_parcel(88, blocks) == "20111700170008"
    assert unit_parcel(22, blocks) == "20111700240002"
    assert unit_parcel(93, blocks) is None
    assert unit_parcel(20, blocks) is None
    assert plan_unit(unit_parcel(91, blocks), blocks) == 91
    assert parent_parcel("201-1170-004-0000") is True
    assert parent_parcel("201-1170-016-0000") is True
    assert parent_parcel("201-1170-017-0006") is False
    assert parent_parcel("2011170004") is False
    from jason.community.reports import plan_block

    assert plan_block("20111700240004", blocks).parent_parcels == ("20111700160000",)
    assert plan_block("20111700250017", blocks) is None  # a Watt building is not a plan block


def test_watt_reused_the_2007_plans_unit_numbers_and_a_unit_number_lists_both():
    from jason.community.reports import plan_unit, unit_parcel, unit_parcels

    blocks = mystique().unit_blocks()
    assert plan_unit("20111700220010", blocks) == 1 and plan_unit("20111700220016", blocks) == 7
    assert plan_unit("20111700230014", blocks) == 8 and plan_unit("20111700230023", blocks) == 17
    assert plan_unit("20111700250017", blocks) == 21 and plan_unit("20111700240001", blocks) == 21
    assert plan_unit("20111700260018", blocks) == 32 and plan_unit("20111700240012", blocks) == 32
    assert plan_unit("20111700280022", blocks) == 56 and plan_unit("20111700280023", blocks) == 57
    assert plan_unit("20111700170011", blocks) == 91
    both = unit_parcels(24, blocks)
    assert [(block.building.value, apn) for block, apn in both] == [(3, "20111700240004"), (4, "20111700250020")]
    assert unit_parcel(24, blocks) is None  # ambiguous
    assert unit_parcel(91, blocks) == "20111700170011" and unit_parcel(5, blocks) == "20111700220014"
    overlapping = sorted(unit for unit in range(1, 93) if len(unit_parcels(unit, blocks)) > 1)
    assert overlapping == list(range(21, 33))
    assert all(block.parent_parcels == () for block in mystique().unit_blocks() if block.plan == "Watt numbering")
