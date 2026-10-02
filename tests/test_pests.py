"""The pest program: visit notes read into buildings and rodent activity, and products aggregated across visits."""

from __future__ import annotations

from jason.community.pest_visits import Activity, read_note, rodent_activity
from jason.community.symbols import Building
from jason.tasks.pests import product_uses, rodent_program


def test_notes_name_the_buildings_in_every_wording() -> None:
    assert read_note("I inspected and treated the exterior of buildings 5,6,7 and 8.").buildings == (
        Building.BLDG_5, Building.BLDG_6, Building.BLDG_7, Building.BLDG_8)
    assert len(read_note("treated the buildings of 1,2,3, and 4. Refilled stations").buildings) == 4
    assert len(read_note("Today inspected and treated buildings one, two, three, and four.").buildings) == 4
    assert len(read_note("today I treated 5,6,7,8 for seasonal pests").buildings) == 4
    assert read_note("Great seeing you. De-webbed the eaves.").buildings == ()


def test_rodent_activity_takes_the_highest_rating_and_needs_the_stations() -> None:
    assert rodent_activity("refilled bait stations, which had moderate and live activity.") is Activity.LIVE
    assert rodent_activity("rodent bait stations which all had minimal to moderate activity") is Activity.MINIMAL_TO_MODERATE
    assert rodent_activity("Bait stations look good minimal activity") is Activity.MINIMAL
    assert rodent_activity("checked stations, no activity") is Activity.NONE
    assert rodent_activity("treated for ants, minimal activity") is None
    reading = read_note("Checked rodent stations and refilled all; minimal activity. Treated for ants and spiders.")
    assert reading.stations_checked and reading.stations_refilled and set(reading.pests) >= {"ants", "spiders", "rodents"}


def _account() -> dict:
    return {
        "customer": {"name": "Mystique Community"},
        "applications": [
            {"day": "2026-08-19", "product": "SELONTRA", "epa_number": "7969-382", "diluted": "100.000 grams",
             "concentrated": "0.075 grams", "areas": "Exterior, Rodent Stations", "targets": "Rats, Mice"},
            {"day": "2025-06-19", "product": "SELONTRA", "epa_number": "7969-382", "diluted": "50.000 grams",
             "concentrated": "0.0375 grams", "areas": "Rodent Stations", "targets": "Rats"},
        ],
        "services": [
            {"day": "2026-08-19", "notes": "Checked rodent stations, minimal activity, buildings 5,6,7 and 8.",
             "products": [{"name": "SELONTRA", "epa_number": "7969-382", "manufacturer": "BASF",
                           "active_ingredient": "CHOLECALCIFEROL 0.075%", "method": "Bait Placement"}]},
            {"day": "2025-06-19", "notes": "Refilled bait stations, moderate activity in stations. Buildings 1,2,3,4.", "products": []},
        ],
    }


def test_products_add_up_across_visits() -> None:
    (use,) = product_uses([_account()])
    assert use.applications == 2 and use.diluted == {"grams": 150.0} and round(use.concentrated["grams"], 4) == 0.1125
    assert (use.first, use.last, use.manufacturer, use.by_year) == ("2025-06-19", "2026-08-19", "BASF", {"2025": 1, "2026": 1})
    assert "Rodent Stations" in use.areas and "Bait Placement" in use.methods


def test_rodent_program_reports_the_months_above_minimal() -> None:
    program = rodent_program(_account())
    assert program["monthlyHighest"] == {"2025-06": "moderate", "2026-08": "minimal"}
    assert program["moderateOrMore"] == [("2025-06-19", "moderate")]


def test_termidor_limits_are_tested_per_building_and_ask_when_buildings_are_unknown() -> None:
    from jason.community.pesticide_facts import check_applications

    def row(day: str, dilution: str = "0.3 flozs / 1 gals", diluted: str = "4.000 gals") -> dict:
        return {"day": day, "product": "TERMIDOR SC", "epa_number": "7969-210", "dilution": dilution, "diluted": diluted,
                "areas": "Exterior Foundations"}

    apps = [row("2025-03-25"), row("2025-05-21"), row("2025-12-02"), row("2024-04-03"), row("2024-04-17"),
            row("2023-10-11", dilution="0.8 flozs / 1 gals"), row("2023-09-19", diluted="0.000 gals")]
    found = check_applications(apps, {"2025-03-25": (5, 6), "2025-05-21": (5, 6), "2025-12-02": (1,)})
    labels = [f for f in found if f["kind"] == "label"]
    assert any(f["date"] == "2025-05-21" and f["where"] == "building 5" and "57 days" in f["finding"] for f in labels)
    assert any(f["date"] == "2025-12-02" and "November 1 and February 28" in f["finding"] for f in labels)
    assert any(f["date"] == "2023-10-11" and "0.8 fl oz" in f["finding"] for f in labels)
    # The zero-volume row is no application; the 2024 pair has no buildings, so it is a question.
    assert not any(f["date"] == "2023-10-11" and "days after" in f["finding"] for f in found)
    assert any(f["kind"] == "question" and f["date"] == "2024-04-17" for f in found)


def test_a_neonicotinoid_on_landscape_areas_since_2025_is_a_question() -> None:
    from jason.community.pesticide_facts import check_applications, ingredients_of

    apps = [{"day": "2025-06-19", "product": "DOMINION FOR GENERAL PEST", "areas": "Landscape Areas, Perimeter"},
            {"day": "2024-06-19", "product": "DOMINION FOR GENERAL PEST", "areas": "Landscape Areas"},
            {"day": "2025-06-19", "product": "DOMINION FOR GENERAL PEST", "areas": "Exterior Foundations"}]
    found = check_applications(apps, labels={"DOMINION FOR GENERAL PEST": "Imidacloprid  21.4%"})
    assert [(f["kind"], f["date"]) for f in found] == [("question", "2025-06-19")]
    assert [i.name for i in ingredients_of("Esfenvalerate 6.4% Prallethrin")] == ["esfenvalerate"]
    assert [i.chemical_class for i in ingredients_of("", "FENDONA CS")] == ["pyrethroid"]


def test_the_license_roster_names_a_technician_by_either_spelling() -> None:
    from datetime import date

    from jason.community.base import LicensedPerson, VendorLicense

    roster = VendorLicense("Structural Pest Control Board", "6993", "Company Registration", ("Branch 2", "Branch 3"), "CLEAR",
                           date(2014, 3, 20), date(2026, 9, 29),
                           (LicensedPerson("TURNER, KYLE T", "President"), LicensedPerson("TURNER, KYLE T", "Operator", "12674", "CLEAR"),
                            LicensedPerson("RODRIGUEZ, SAUL E", "Field Representative", "28829", "CLEAR")), 3, 113)
    assert roster.person("Saul Rodriguez (COM/NORTH").number == "28829"
    assert roster.person("Kyle Turner").role == "Operator"
    assert roster.person("Keith Huffman (NORTH)") is None
