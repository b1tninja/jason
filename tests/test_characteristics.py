from datetime import date

from jason.community.assessor import SacramentoCountyAssessor
from jason.community.characteristics import (
    CharacteristicsStore,
    FloorPlan,
    UnitCharacteristics,
    classify_plan,
    parse_characteristics,
    per_sqft,
)
from jason.tasks.sync_characteristics import sync_characteristics

PAYLOAD = {
    "resChars": {
        "PARCEL_NUMBER": "20111700170001", "LAND_USE_CODE": "A1F00A", "AREA_FOR_MOD": "1312", "GARAGE_AREA": "420",
        "CARPORT_AREA": "0", "PARKING_SPACES": "2", "POOL_YN": "0", "SPA_HOT_TUB": "0",
        "BuildingCharacteristics": [{
            "TYPE_OF_HOME": "Primary", "FIRST_FLR_AREA": "600", "SECOND_FLOOR_AREA": "712", "FINISHED_BASEMENT_AREA": "0",
            "TOTAL_LIVING_SQ_FT": "1312", "BEDROOM_COUNT": "3", "TOTAL_BATH_COUNT": "2.5", "YEAR_BUILT": "2007",
            "EFFECTIVE_YEAR_BUILT": "2007", "FLOOR_LEVEL": "2",
        }],
    },
    "commChars": None,
}

PLANS = (
    FloorPlan("Unit 3", "John Laing Homes", 3, 1_312, 2),
    FloorPlan("Unit 6", "John Laing Homes", 3, 1_527, 2),
    FloorPlan("Plan 1", "Watt Communities at Mystique", 3, 1_492, 2, baths=2.5),
    FloorPlan("Plan 2", "Watt Communities at Mystique", 3, 1_502, 2, baths=2.5),
    FloorPlan("Plan 4B", "Watt Communities at Mystique", 2, 1_326, 3, baths=2.5),
)


def test_the_viewer_payload_becomes_one_record():
    unit = parse_characteristics(PAYLOAD, fetched=date(2026, 9, 28))
    assert unit is not None
    assert unit.apn == "20111700170001" and unit.living_sqft == 1312 and unit.bedrooms == 3 and unit.baths == 2.5
    assert unit.year_built == 2007 and unit.floor_level == 2 and unit.garage_sqft == 420 and unit.parking_spaces == 2
    assert per_sqft(unit, 39_360_000) == 30_000
    assert parse_characteristics({"resChars": None, "commChars": None}) is None
    assert parse_characteristics(None) is None


def test_a_plan_is_the_nearest_stated_area_for_the_developer_and_bedrooms():
    unit = UnitCharacteristics("1", living_sqft=1312, bedrooms=3)
    assert classify_plan(unit, PLANS, "John Laing Homes").name == "Unit 3"
    # Watt's Plan 1 and Plan 2 are ten feet apart; the nearer one wins, and the developer filter keeps John Laing's out.
    assert classify_plan(UnitCharacteristics("2", living_sqft=1_498, bedrooms=3), PLANS, "Watt Communities at Mystique").name == "Plan 2"
    assert classify_plan(UnitCharacteristics("3", living_sqft=1_495, bedrooms=3), PLANS, "Watt Communities at Mystique").name == "Plan 1"
    # A three-bedroom area with a two-bedroom count matches nothing, and so does an area far from every plan.
    assert classify_plan(UnitCharacteristics("4", living_sqft=1_312, bedrooms=2), PLANS, "John Laing Homes") is None
    assert classify_plan(UnitCharacteristics("5", living_sqft=1_100, bedrooms=3), PLANS, "John Laing Homes") is None
    assert classify_plan(UnitCharacteristics("6", living_sqft=None, bedrooms=3), PLANS) is None


def test_the_store_and_the_sync(tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        if url.endswith("20111700170001/buildingcharacteristics"):
            return PAYLOAD
        if url.endswith("20111700170002/buildingcharacteristics"):
            raise RuntimeError("boom")
        return None

    with CharacteristicsStore(tmp_path / "characteristics.db") as store:
        result = sync_characteristics(store, SacramentoCountyAssessor(), ("201-1170-017-0001", "20111700170002", "20111700170003"), fetch=fetch)
        assert result.synced == 1 and result.missed == ["20111700170003"] and result.errors[0].startswith("20111700170002")
        assert calls[0].endswith("/parcels/20111700170001/buildingcharacteristics")
        stored = store.get("201-1170-017-0001")
        assert stored is not None and stored.living_sqft == 1312 and stored.baths == 2.5 and stored.fetched == date.today()
        assert list(store.all()) == ["20111700170001"]
    assert "synced=1" in result.summary()
