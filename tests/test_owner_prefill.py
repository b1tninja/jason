"""What is on file for each owner, printed beside the blank form, and a returned form read against it."""

from datetime import date

from jason.community.forms import FormAnswers, FormKey
from jason.community.postal import normalize_address
from jason.community.spec import spec_module
from jason.community.tags import PayhoaTag, TagPurpose, TagScope
from jason.tasks.owner_prefill import compare, fingerprints, on_file, prefill, prefills

M, U = TagScope.MEMBER, TagScope.UNIT
FORM = spec_module("forms").OWNER_INFO
TAGS = (PayhoaTag("Notices by Email", M, TagPurpose.NOTICE_DELIVERY, "email"),
        PayhoaTag("Notices by Mail", M, TagPurpose.NOTICE_DELIVERY, "mail"),
        PayhoaTag("Rental", U, TagPurpose.OCCUPANCY, "Rented out", answer="occupancy"),
        PayhoaTag("Owner Occupied", U, TagPurpose.OCCUPANCY, "Owner-occupied", answer="occupancy"),
        PayhoaTag("Paper Statements", U, TagPurpose.STATEMENTS, "paper"),
        PayhoaTag("Additional Deliveries", M, TagPurpose.SECONDARY_CONTACT),
        PayhoaTag("Legal Representative", M, TagPurpose.LEGAL_REPRESENTATIVE))


def _unit(uid, title, tags, owners):
    return {"id": uid, "title": title, "tags": [{"tag": t} for t in tags],
            "address": {"line1": title, "city": "Sacramento", "region": "California", "postalCode": "95835"},
            "owners": [{"membershipId": m, "deletedAt": None, "createdAt": "2024-01-17T00:00:00Z"} for m in owners]}


def _person(pid, name, tags=(), email="", address=None):
    given, family = name.split(" ", 1)
    profile = {"givenNames": given, "familyName": family}
    if address:
        profile.update(address1=address[0], city=address[1], state=address[2], zip=address[3])
    return {"id": pid, "email": email, "tags": [{"tag": t} for t in tags], "profile": profile}


UNITS = [_unit(1, "3015 MESMERIZING WALK", ["Paper Statements", "Owner Occupied"], [10]),
         _unit(2, "3007 MESMERIZING WALK", ["Rental"], [11, 30, 31]),
         _unit(3, "3009 MESMERIZING WALK", ["Rental"], [12])]
PEOPLE = [_person(10, "Al Vexley", ["Notices by Mail"], "al@example.com"),
          _person(11, "Mo Zu", ["Notices by Mail"], "mo@example.com", ("88 Quarry Ridge Drive", "Alamo", "CA", "94507")),
          _person(30, "Copy Zu", ["Additional Deliveries"], "copy@example.com"),
          _person(31, "Rae Agent", ["Legal Representative"], "rae@example.com"),
          _person(12, "Lu Fenwhistle", ["Notices by Mail"], "lu@example.com")]


def test_the_record_as_printed():
    found = {p.membership_id: p for p in prefills(UNITS, PEOPLE, TAGS, FORM)}
    assert set(found) == {10, 11, 12}                                       # copy and representative records are not owners
    al = found[10]
    assert al.values["unit-address"] == "3015 MESMERIZING WALK, Sacramento, CA 95835"
    assert al.values["delivery.by-mail"] is True                             # Paper Statements, owner since before PayHOA
    assert al.values["occupancy"] == "Owner-occupied" and "mailing-address" not in al.values
    mo = found[11]
    assert mo.values["mailing-address"].startswith("88 Quarry Ridge Drive\nAlamo, CA 94507")
    assert "delivery.by-mail" not in mo.values                               # the law's default is never pre-checked
    assert mo.values["second-email"] == "copy@example.com" and mo.values["representative-name"] == "Rae Agent"
    assert mo.values["representative-email"] == "rae@example.com"
    lu = found[12]
    assert lu.values["email"] == "lu@example.com" and lu.withheld == ["email"]  # on their emailed copy, not the letter
    rows = dict(on_file(lu, FORM))
    assert rows["6. Email address for notices"].startswith("On file (not printed")
    assert rows["4. How should the Association deliver notices to you?"].startswith("No choice on file")


def test_paper_statements_after_a_sale_is_not_the_new_owners_choice():
    one = prefill(UNITS[0], UNITS[0]["owners"][0], {10: PEOPLE[0]}, TAGS, FORM, deed=date(2024, 6, 1))
    assert "delivery.by-mail" not in one.values


def test_formatting_is_not_a_change_and_blank_keeps_what_is_on_file():
    assert normalize_address("3028 Macon Drive, Sacramento, California 95835-1234") == \
        normalize_address("3028 MACON DR. SACRAMENTO CA 95835")
    mo = next(p for p in prefills(UNITS, PEOPLE, TAGS, FORM) if p.membership_id == 11)
    sent = fingerprints(mo)
    assert "88 Q" not in str(sent) and "mo@example.com" not in str(sent)       # hashes only
    same = FormAnswers(FormKey.OWNER_INFO, {"mailing-address": "88 QUARRY RIDGE DR, Alamo, California 94507",
                                            "delivery": ["By email"], "occupancy": ["Rented out"],
                                            "representative-name": "none"})
    got = compare(sent, same.answers, FORM)
    assert got["mailing-address"] == "unchanged" and got["email"] == "unchanged"          # reformatted; blank
    assert got["delivery.by-email"] == "added" and got["occupancy"] == "unchanged"
    assert got["representative-name"] == "cleared"                                         # "none" removes it
    moved = compare(sent, {"mailing-address": "9 Elm Ave, Reno, NV 89501"}, FORM)
    assert moved["mailing-address"] == "changed"


def test_suggestions_fill_only_what_the_owner_has_not_chosen():
    from jason.community.forms import SuggestedChoices
    from jason.tasks.owner_prefill import Activity, suggested

    rule, today = SuggestedChoices(), date(2026, 10, 1)
    found = {p.membership_id: p for p in prefills(UNITS, PEOPLE, TAGS, FORM)}
    active = Activity(last_login="2026-09-01", delivered=40, opened=30)
    mo = found[11]                                                              # no choice of their own, reads email
    assert suggested(mo, active, rule, today=today) == {"delivery.by-email": True, "ballots": "Electronic ballot by email"}
    assert "delivery.by-email" not in mo.values                                  # not "on file": the page never shows it
    al = found[10]                                                              # chose mail (paper statements)
    assert suggested(al, active, rule, today=today) == {"ballots": "Paper ballot by mail"}
    assert suggested(mo, Activity(last_login="2024-01-01"), rule, today=today) == {}          # not reading email
    assert suggested(mo, Activity(last_login="2026-09-01", unsubscribed=1), rule, today=today) == {}
    assert suggested(found[12], active, rule, today=today)["delivery.by-email"]  # their own copy may suggest email
    assert suggested(mo, active, SuggestedChoices(apply=False), today=today) == {}


def test_letters_go_one_send_a_building_and_an_owners_second_unit_gets_its_own():
    from jason.community.notices import NoticeKind, NoticeRule
    from jason.community.tags import TagPurpose as P
    from jason.tasks.owner_send import mail_items, occupancy_signals, send_plan

    tags = TAGS + (PayhoaTag("Building 3", U, P.BUILDING, "3"),)
    units = [_unit(1, "3015 MESMERIZING WALK", ["Building 3", "Owner Occupied"], [10]),
             _unit(2, "3007 MESMERIZING WALK", ["Building 3"], [11]),
             _unit(3, "3009 MESMERIZING WALK", ["Building 3", "Rental"], [11, 12])]
    for u in units:
        for i, o in enumerate(u["owners"]):
            o["id"] = 700000 + u["id"] * 10 + i                         # the Mailroom's owner-row ids
    people = [_person(10, "Al Vexley", ["Notices by Mail"], "al@example.com", ("9 Elm Ave", "Reno", "NV", "89501")),
              _person(11, "Mo Zu", ["Notices by Mail"], "mo@example.com", ("88 Quarry Ridge Drive", "Alamo", "CA", "94507")),
              _person(12, "Lu Fenwhistle", ["Notices by Email"], "lu@example.com", ("3009 Mesmerizing Walk", "Sacramento", "CA", "95835"))]
    rule = NoticeRule("owner-info-solicitation", "Request", "CIV 4041(b)", NoticeKind.INDIVIDUAL, courtesy_email=True)
    rows = send_plan(units, people, tags, FORM, rule, None, {}, today=date(2026, 10, 1))
    items = mail_items(rows, units, tags)
    assert [(k, p["unitIds"]) for k, _, p in items] == [("building-3", [1, 2]), ("building-3-(another-unit)", [3])]
    assert items[1][2]["ownerIds"] == [700030]                          # the email elector is not mailed
    signals = {s.unit: s for s in occupancy_signals(units, rows, tags)}
    assert signals["3015 MESMERIZING WALK"].finding.startswith("tagged Owner Occupied, but the evidence says")
    assert signals["3007 MESMERIZING WALK"].finding.startswith("likely not owner-occupied")
    assert signals["3009 MESMERIZING WALK"].finding.startswith("tagged Rental, but the evidence says an owner lives")


def test_the_units_own_address_written_differently_is_the_unit():
    from jason.tasks.owner_prefill import is_unit_address, place_of

    assert is_unit_address("3007 Enchanted Wk., Sacramento CA", "3007 ENCHANTED WALK")
    assert is_unit_address("3007 Enchantd Walk #2\nSacramento, CA 95835", "3007 ENCHANTED WALK")    # a typo, a unit no.
    assert not is_unit_address("3009 Enchanted Walk", "3007 ENCHANTED WALK")
    assert not is_unit_address("88 Quarry Ridge Drive", "3007 ENCHANTED WALK")
    from jason.community.base import read_unit_address

    unit = _unit(1, "3007 ENCHANTED WALK", [], [10])
    community = {read_unit_address("3007 ENCHANTED WALK"): "3007 ENCHANTED WALK",
                 read_unit_address("3009 ENCHANTED WALK"): "3009 ENCHANTED WALK"}
    def person(line1, city="Sacramento", zip_code="95835"):
        return {"profile": {"address1": line1, "city": city, "zip": zip_code}}
    assert place_of(person("3007 Enchanted Wk"), unit, community)[0] == "unit"                     # a short form
    assert place_of(person("3007 Enchantd Walk Apt 2"), unit, community)[0] == "unit, written differently"
    assert place_of(person("3007 Enchanted Walk", "Elk Grove", "95624"), unit, community)[0] == "elsewhere"
    assert place_of(person("3009 Enchanted Walk"), unit, community) == ("another unit", "3009 ENCHANTED WALK")
    sent = {"unit": "3007 ENCHANTED WALK", "fields": {}}
    assert compare(sent, {"mailing-address": "3007 Enchanted Wk, Sacramento"}, FORM).get("mailing-address") is None


def test_the_county_and_the_deed_weigh_into_the_reading_and_check_the_owners():
    from jason.community.notices import NoticeKind, NoticeRule
    from jason.tasks.owner_county import ParcelFacts
    from jason.tasks.owner_send import occupancy_signals, send_plan

    units = [_unit(1, "3015 MESMERIZING WALK", ["Rental"], [10]), _unit(2, "3007 MESMERIZING WALK", [], [11]),
             _unit(3, "3009 MESMERIZING WALK", ["Owner Occupied"], [12])]
    people = [_person(10, "Al Vexley", ["Notices by Mail"], "al@example.com", ("3015 Mesmerizing Walk", "Sacramento", "CA", "95835")),
              _person(11, "Mo Zu", ["Notices by Mail"], "mo@example.com"),
              _person(12, "Lu Fenwhistle", ["Notices by Mail"], "lu@example.com", ("9 Elm Ave", "Reno", "NV", "89501"))]
    rule = NoticeRule("owner-info-solicitation", "Request", "CIV 4041(b)", NoticeKind.INDIVIDUAL, courtesy_email=True)
    rows = send_plan(units, people, TAGS, FORM, rule, None, {}, today=date(2026, 10, 1))
    roll = date(2026, 1, 1)

    def facts(apn, unit, ho, mail, deed, grantees):
        return ParcelFacts(apn, unit, homeowner_exemption=ho, exemption_as_of=roll, county_mail=mail, roll_as_of=roll,
                           roll_deed=deed, latest_deed=deed, grantees=grantees)

    county = {"3015 MESMERIZING WALK": facts("1", "3015 MESMERIZING WALK", True, "property", date(2020, 1, 1), ["VEXLEY AL"]),
              "3007 MESMERIZING WALK": facts("2", "3007 MESMERIZING WALK", False, "elsewhere", date(2025, 3, 1),
                                             ["SAMPLE HOLDINGS LLC"]),
              "3009 MESMERIZING WALK": facts("3", "3009 MESMERIZING WALK", False, "elsewhere", date(2019, 1, 1), ["FENWHISTLE LU"])}
    s = {x.unit: x for x in occupancy_signals(units, rows, TAGS, county, today=date(2026, 10, 1))}
    assert s["3015 MESMERIZING WALK"].reading == "owner-occupied"
    assert s["3015 MESMERIZING WALK"].finding.startswith("tagged Rental, but the evidence says an owner lives there")
    zu = s["3007 MESMERIZING WALK"]
    assert zu.entity and zu.reading == "not owner-occupied" and zu.deed_names_owner is False
    assert "likely not owner-occupied" in zu.finding and "names none of PayHOA's owners" in zu.finding
    assert s["3009 MESMERIZING WALK"].finding.startswith("tagged Owner Occupied, but the evidence says the owners live")


def test_county_facts_from_before_a_sale_are_not_used():
    from jason.tasks.owner_county import ParcelFacts, lien_date

    assert lien_date(date(2026, 7, 1)) == date(2026, 1, 1) and lien_date(date(2026, 3, 1)) == date(2025, 1, 1)
    roll = date(2026, 1, 1)
    sold = ParcelFacts("1", "U", True, roll, "elsewhere", roll, date(2021, 2, 24), date(2026, 7, 21), ["NEW OWNER"])
    assert sold.current_exemption is None and sold.current_county_mail == ""          # the former owner's
    known = ParcelFacts("2", "U", True, roll, "property", roll, date(2026, 5, 29), date(2026, 5, 29), ["NEW OWNER"])
    assert known.current_county_mail == "property"                                    # the extract knew the new deed
    assert known.current_exemption is None                                            # but the exemption is January's
    trust = ParcelFacts("3", "U", True, roll, "property", roll, date(2021, 6, 28), date(2021, 7, 27), ["OWNER TRUST"])
    assert trust.current_county_mail == "property" and trust.current_exemption is True  # no sale since the roll's date


def test_an_old_county_address_weighs_half_and_a_move_out_is_a_lead():
    from jason.tasks.owner_send import OccupancySignal, _reading

    today = date(2026, 10, 1)
    old = OccupancySignal("U", 1, "", "every owner elsewhere", county_mail="property", county_since=date(2008, 2, 29))
    _reading(old, today)
    assert "county mail to the unit since 2008" in old.evidence and old.reading == "unclear"
    fresh = OccupancySignal("U", 1, "", "every owner elsewhere", county_mail="elsewhere", county_since=date(2025, 1, 1))
    _reading(fresh, today)
    assert fresh.reading == "not owner-occupied"                      # 1 + 1: both current
    stale = OccupancySignal("U", 1, "", "every owner elsewhere", county_mail="elsewhere", county_since=date(2010, 1, 1))
    _reading(stale, today)
    assert stale.reading == "not owner-occupied"                      # 1 + 0.5 still reaches 1.5
