"""Answers gathered outside PayHOA (a hand-made Google Form) read into the owner information definition and matched to
PayHOA's current owners, so a person can record the preferences in PayHOA, the record owners keep themselves."""

import json
import sqlite3
from datetime import date

from jason.community.base import read_unit_address
from jason.community.forms import CONTACT, AnswerCycle, FormImport, FormKey, Freshness, ImportRule
from jason.community.symbols import Street
from jason.tasks.forms import form_items, import_responses, response_rows
from jason.tasks.member_preferences import Standing, match, payhoa_owners, review_rows, summary

# A cycle that opened May 1, 2025: r2 (June 2025) is this year's answer, r1 (February 2025) last year's.
CYCLE = AnswerCycle(year=2026, opened=date(2025, 5, 1))
TODAY = date(2025, 9, 1)

RULES = FormImport(
    key="test", source="FORM", form=FormKey.OWNER_INFO, title="Test registration",
    rules=(
        ImportRule("Unit Address", "unit-address"),
        *(ImportRule(t, f"{CONTACT}{slot}", section=s, role="owner")
          for s in ("Owner", "Additional Owner") for t, slot in (("Owner Name", "name"), ("Email", "email"))),
        ImportRule("Delivery", "delivery", options=(("Mail", "By mail"), ("E-Mail", "By email"))),
        ImportRule("Mailing Address", "mailing-address"),
        ImportRule("Occupied?", "occupancy", options=(("Rental", "Rented out"), ("Owner Occupied", "Owner-occupied"))),
        ImportRule("Name", f"{CONTACT}name", section="Resident", role="resident"),
    ),
)


def _q(qid, title, kind="textQuestion"):
    return {"title": title, "questionItem": {"question": {"questionId": qid, kind: {}}}}


FORM = {"items": [
    {"title": "Owner", "pageBreakItem": {}}, _q("a", "Unit Address"), _q("b", "Owner Name"), _q("c", "Email"),
    {"title": "Additional Owner", "pageBreakItem": {}}, _q("d", "Owner Name"), _q("e", "Email"),
    {"title": "Additional Owner", "pageBreakItem": {}}, _q("f", "Owner Name"), _q("g", "Email"),
    {"title": "Preferences", "pageBreakItem": {}}, _q("h", "Delivery", "choiceQuestion"), _q("i", "Mailing Address"),
    _q("j", "Occupied?", "choiceQuestion"), _q("k", "Lease copy", "fileUploadQuestion"),
    {"title": "Resident", "pageBreakItem": {}}, _q("l", "Name"),
]}


def _answer(**values):
    return {qid: ({"fileUploadAnswers": {"answers": [{"fileId": "x"}]}} if qid == "k" else
                  {"textAnswers": {"answers": [{"value": v} for v in (value if isinstance(value, list) else [value])]}})
            for qid, value in values.items()}


def _response(rid, when, **values):
    return {"responseId": rid, "lastSubmittedTime": when, "answers": _answer(**values)}


SAVED = {"form": FORM, "responses": [
    # a current owner, by email; a co-owner in the second owner section; email delivery; a lease upload never read
    _response("r1", "2025-02-01T10:00:00Z", a="3007 Enchanted Wk.", b="Pat Lee", c="PAT@example.com",
              d="Sam Lee", e="sam@example.com", h="E-Mail", i="PO Box 1", j="Owner Occupied", k="lease.pdf"),
    # the same unit later, by name, with both methods: the latest for the unit
    _response("r2", "2025-06-01T10:00:00Z", a="3007 enchanted walk", b="Patricia Ann Lee", c="new@example.com",
              h=["Mail", "E-Mail"], j="Owner Occupied"),
    # a prior owner of another unit, sent before the current owners took title
    _response("r3", "2024-10-01T10:00:00Z", a="5655 Whimsical Lane", b="Old Owner", c="old@example.com", j="Rental",
              l="A Tenant"),
    # a tenant registering, after the current owners took title
    _response("r4", "2025-08-01T10:00:00Z", a="5655 Whimsical Ln", b="A Tenant", c="tenant@example.com", j="Rental"),
    # not a Mystique address
    _response("r5", "2025-08-02T10:00:00Z", a="12 Main St", b="Someone", c="s@example.com", j="Rental"),
]}


def _catalog(tmp_path):
    db = tmp_path / "payhoa.db"
    con = sqlite3.connect(db)
    con.execute("create table people (id, name, email)")
    con.execute("create table units (id, label, raw_json)")
    con.executemany("insert into people values (?, ?, ?)", [(1, "Pat Lee", "pat@example.com"), (2, "Pat Lee", "pat2@x.com"),
                                                            (3, "New Buyer", "buyer@example.com")])
    units = [
        (10, "3007 ENCHANTED WALK", {"occupancies": [{"fromDate": "2024-01-14T00:00:00Z", "toDate": None}],
                                     "owners": [{"membershipId": 1, "deletedAt": None}]}),
        (11, "5655 WHIMSICAL LN", {"occupancies": [{"fromDate": "2024-01-14T00:00:00Z", "toDate": "2025-01-01"},
                                                   {"fromDate": "2025-01-02T00:00:00Z", "toDate": None}],
                                   "owners": [{"membershipId": 3, "deletedAt": None}, {"membershipId": 2, "deletedAt": "2025"}]}),
    ]
    con.executemany("insert into units values (?, ?, ?)", [(i, label, json.dumps(raw)) for i, label, raw in units])
    con.commit()
    con.close()
    return db


def test_a_typed_address_is_read_to_a_street_number_and_street():
    assert read_unit_address("3007 Enchanted Wk., Sacramento CA 95834") == (3007, Street.ENCHANTED_WALK)
    assert read_unit_address("Unit 5655 whimsical lane #2") == (5655, Street.WHIMSICAL_LN)
    assert read_unit_address("3006 Magicl Walk") == (3006, Street.MAGICAL_WALK)          # a typo
    assert read_unit_address("12 Main St") == (None, None) and read_unit_address("") == (None, None)


def test_repeated_sections_and_titles_keep_every_answer():
    items = form_items(SAVED)
    owners = [(i["section"], i["occurrence"]) for i in items if i["title"] == "Owner Name"]
    assert owners == [("Owner", 1), ("Additional Owner", 1), ("Additional Owner", 2)]
    row = next(r for r in response_rows(SAVED) if r["responseId"] == "r1")
    assert row["Owner 1: Owner Name"] == "Pat Lee" and row["Additional Owner 1: Owner Name"] == "Sam Lee"


def test_an_outside_forms_responses_read_into_the_definition():
    r1 = import_responses(SAVED, RULES)[1]                                               # sorted by time
    assert r1.source == "google:r1"
    assert r1.answers["delivery"] == ["By email"] and r1.answers["occupancy"] == ["Owner-occupied"]
    assert r1.answers["name"] == "Pat Lee" and r1.answers["email"] == "PAT@example.com"   # Sam is a contact
    assert [p["role"] for p in r1.contacts] == ["owner", "owner"]
    assert "lease.pdf" not in json.dumps(r1.answers)                                    # uploads are never read
    r3 = next(r for r in import_responses(SAVED, RULES) if r.source == "google:r3")
    assert {"role": "resident", "name": "A Tenant"} in r3.contacts


def test_responses_are_matched_to_current_owners_and_the_latest_says_what_to_record(tmp_path):
    units = payhoa_owners(_catalog(tmp_path))
    found = {m.source: m for m in match(import_responses(SAVED, RULES), units, cycle=CYCLE, today=TODAY)}
    assert found["google:r1"].standing is Standing.CURRENT_OWNER and found["google:r1"].how == "email"
    assert found["google:r2"].standing is Standing.CURRENT_OWNER and found["google:r2"].how == "name"
    assert found["google:r2"].latest and not found["google:r1"].latest                  # the later one wins
    assert found["google:r2"].record["delivery"] == "mail and email"
    assert found["google:r2"].record["email"] == "new@example.com"                       # differs from PayHOA's
    assert found["google:r1"].record["mailing address"].startswith("given on the form")
    assert found["google:r3"].standing is Standing.BEFORE_OWNERSHIP                      # a prior owner's answers
    assert found["google:r4"].standing is Standing.NOT_AN_OWNER                          # a tenant
    assert found["google:r5"].standing is Standing.NO_UNIT
    assert found["google:r2"].freshness is Freshness.CURRENT and found["google:r2"].age == "3 months"
    assert found["google:r1"].freshness is Freshness.PRIOR
    totals = summary(list(found.values()))
    assert totals["unitsWithACurrentOwnerAnswer"] == 1 and totals["toApply"] == 1
    rows = review_rows(list(found.values()))
    assert all("PO Box" not in cell for row in rows for cell in row)                     # no address is written


def test_a_current_owners_answers_propose_tag_changes(tmp_path):
    from jason.community.tags import PayhoaTag, TagPurpose, TagScope

    tags = (PayhoaTag("Notices by Email", TagScope.MEMBER, TagPurpose.NOTICE_DELIVERY, "email", exists=False),
            PayhoaTag("Notices by Mail", TagScope.MEMBER, TagPurpose.NOTICE_DELIVERY, "mail", exists=False),
            PayhoaTag("Rental", TagScope.UNIT, TagPurpose.OCCUPANCY, "Rented out", answer="occupancy"))
    db = _catalog(tmp_path)
    con = sqlite3.connect(db)                       # the unit is tagged Rental, though its owner says owner-occupied
    raw = json.loads(con.execute("select raw_json from units where id = 10").fetchone()[0])
    raw["tags"] = [{"tag": "Rental"}]
    con.execute("update units set raw_json = ? where id = 10", (json.dumps(raw),))
    con.commit()
    con.close()
    found = {m.source: m for m in match(import_responses(SAVED, RULES), payhoa_owners(db), tags, cycle=CYCLE, today=TODAY)}
    latest = found["google:r2"]                      # mail and email, owner-occupied
    assert latest.tag_changes == ["+Notices by Email (member) [create the tag]", "+Notices by Mail (member) [create the tag]",
                                  "-Rental (unit)"]
    assert found["google:r1"].tag_changes == []      # superseded: only the latest response proposes
    assert summary(list(found.values()))["toApply"] == 1


def test_an_old_answer_is_a_question_for_the_owner_not_a_change(tmp_path):
    late = AnswerCycle(year=2027, opened=date(2026, 10, 1))                     # every test answer is from before it
    units = payhoa_owners(_catalog(tmp_path))
    found = {m.source: m for m in match(import_responses(SAVED, RULES), units, (), cycle=late, today=date(2026, 10, 1))}
    latest = found["google:r2"]
    assert latest.freshness is Freshness.STALE and latest.age == "16 months"
    assert latest.tag_changes == [] and not latest.record.get("email")
    assert any(c.startswith("email new@example.com (answered 2025-06-01, 16 months ago") for c in latest.confirm)
    nothing = {m.source: m for m in match(import_responses(SAVED, RULES), units)}
    assert not nothing["google:r2"].actionable                                   # no cycle: nothing is this year's


def test_an_owners_later_profile_update_is_never_overwritten(tmp_path):
    db = _catalog(tmp_path)
    con = sqlite3.connect(db)
    con.execute("alter table people add column raw_json")
    con.execute("update people set raw_json = ? where id = 1", (json.dumps({"profile": {"updatedAt": "2025-07-15T00:00:00Z"}}),))
    con.commit()
    con.close()
    latest = next(m for m in match(import_responses(SAVED, RULES), payhoa_owners(db), cycle=CYCLE, today=TODAY) if m.latest)
    assert latest.owner.profile_updated.startswith("2025-07-15")
    assert "email" not in latest.record and "mailing address" not in latest.record
    assert any("profile changed 2025-07-15, after this answer" in n for n in latest.notes)


def test_a_deed_recorded_after_the_answer_makes_it_the_prior_titles(tmp_path):
    deeds = {"3007 ENCHANTED WALK": date(2025, 7, 1)}                          # recorded after both answers
    found = {m.source: m for m in match(import_responses(SAVED, RULES), payhoa_owners(_catalog(tmp_path), deeds),
                                        cycle=CYCLE, today=TODAY)}
    latest = found["google:r2"]                     # the same owner, before re-titling: still only a question
    assert latest.standing is Standing.CURRENT_OWNER and latest.tag_changes == []
    assert any("deed recorded 2025-07-01, after this answer" in n for n in latest.notes)
    assert summary(list(found.values()))["answeredBeforeTheLatestDeed"] == 3     # r1, r2, and r3 (a prior owner)


def test_the_specifications_import_reads_every_mapped_option():
    from jason.community.spec import spec_module

    forms = spec_module("forms")
    owner_info = forms.OWNER_INFO
    for rules in forms.FORM_IMPORTS:
        for rule in rules.rules:
            if rule.field.startswith(CONTACT):
                continue
            question = owner_info.question(rule.field)                                   # a field the definition has
            for _, ours in rule.options:
                assert ours in question.options, (rules.key, rule.title, ours)


def test_a_second_address_that_is_the_owners_own_email_is_no_second_delivery():
    from jason.tasks.member_preferences import Owner, _to_record

    owner = Owner(1, "Eliza Fairbanks", "liz@example.org")
    record, notes = _to_record({"second-address": "Liz@Example.org"}, owner, "2026-06-08")
    assert "secondary delivery" not in record and any("owner's own email" in n for n in notes)
    assert _to_record({"second-address": "other@example.org"}, owner, "2026-06-08")[0]["secondary delivery"]
    assert _to_record({"second-address": "12 Elm St, Davis, CA 95616"}, owner, "2026-06-08")[0]["secondary delivery"]


def test_a_property_manager_becomes_the_record_the_owner_chose():
    from jason.tasks.member_preferences import MANAGER_CONTACT, MANAGER_COPIES, Owner, _to_record

    owner = Owner(membership_id=1, name="Pat Lee", email="pat@example.com")
    base = {"manager-name": "Acme Property Services", "manager-email": "office@acme.example"}
    on_file = _to_record(base, owner, "2026-10-05")[0]["property manager"]
    assert on_file.startswith("other contact")                                   # neither box: on file, no notices
    copies = _to_record({**base, "manager-role": [MANAGER_COPIES]}, owner, "2026-10-05")[0]["property manager"]
    assert "Property Manager and Additional Deliveries" in copies
    both = _to_record({**base, "manager-role": [MANAGER_COPIES, MANAGER_CONTACT]}, owner, "2026-10-05")[0]
    assert both["property manager"].endswith("Additional Deliveries and Legal Representative")
    _, notes = _to_record({"manager-name": "Acme", "manager-role": [MANAGER_COPIES]}, owner, "2026-10-05")
    assert any("no manager email" in n for n in notes)
    _, notes = _to_record({**base, "manager-role": [MANAGER_CONTACT], "representative-name": "Rae"}, owner, "2026-10-05")
    assert any("both named" in n for n in notes)
    record, notes = _to_record({"manager-role": [MANAGER_COPIES]}, owner, "2026-10-05")
    assert "property manager" not in record and any("no manager is named" in n for n in notes)


def test_a_street_line_at_a_community_unit_is_completed_and_anything_else_is_read_as_written():
    from jason.community.postal import COMPLETED, read_mailing_address

    city = "Sacramento, CA 95835"
    for typed in ("5651 WHIMSICAL LN", "5651 Whimsical Lane", "3006 magical wlk", "3006 Magical Wk.",
                  "3028 Macon Drive, Sacramento", "3007 Mesmerising Walk, CA 95835"):
        found, how = read_mailing_address(typed, city)
        assert how == COMPLETED and (found.city, found.state, found.zip) == ("Sacramento", "CA", "95835"), typed
    assert read_mailing_address("5651 WHIMSICAL LN", city)[0].line1 == "5651 WHIMSICAL LN"
    assert read_mailing_address("5651 Whimsical Court", city) == (None, "")       # another street
    assert read_mailing_address("12 Elm St", city) == (None, "")                  # not ours, and no city
    found, how = read_mailing_address("12 Elm St, Davis, CA 95616", city)
    assert how == "" and found.city == "Davis"                                    # as written
    assert read_mailing_address("5651 WHIMSICAL LN") == (None, "")                # no community city line: a miss


def test_a_misread_or_missing_state_is_put_right_from_the_zip():
    from jason.community.form_hints import _state_from_zip
    from jason.community.postal import state_for_zip

    assert (state_for_zip("95835"), state_for_zip("89501"), state_for_zip("97205"), state_for_zip("00901")) == \
        ("CA", "NV", "OR", "")
    assert _state_from_zip("1200 Sunset Way Folsom, cn 95630") == "1200 Sunset Way Folsom, CA 95630"
    assert _state_from_zip("19500 Lincoln Blvd Roseville, 95661") == "19500 Lincoln Blvd Roseville, CA 95661"
    assert _state_from_zip("10 Main St Reno NV 89501") == "10 Main St Reno NV 89501"            # a state stays
    assert _state_from_zip("123 Main St") == "123 Main St"                                      # no ZIP, no guess
