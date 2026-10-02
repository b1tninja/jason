"""PayHOA tags as the record of owners' 4041 choices, and the Civil Code 4040 delivery they decide."""

from jason.community.tags import Channel, PayhoaTag, TagPurpose, TagScope, delivery
from jason.tasks.notice_delivery import plan

U, M = TagScope.UNIT, TagScope.MEMBER
TAGS = (
    PayhoaTag("Notices by Email", M, TagPurpose.NOTICE_DELIVERY, "email"),
    PayhoaTag("Notices by Mail", M, TagPurpose.NOTICE_DELIVERY, "mail"),
    PayhoaTag("Owner Info 2027", M, TagPurpose.ANSWERED, "2027"),
    PayhoaTag("Rental", U, TagPurpose.OCCUPANCY, "Rented out"),
    PayhoaTag("Paper Statements", U, TagPurpose.STATEMENTS, "paper"),
    PayhoaTag("Building 3", U, TagPurpose.BUILDING, "3"),
)


def test_delivery_follows_the_members_election_and_the_law_without_one():
    email = delivery(TAGS, {"notices by email"}, valid_email=True, mailing_address=True)
    assert email.channels == (Channel.EMAIL,) and email.send_to == ""
    both = delivery(TAGS, {"notices by email", "notices by mail"}, valid_email=True, mailing_address=False)
    assert set(both.channels) == {Channel.EMAIL, Channel.MAIL} and both.send_to == "unit"
    none = delivery(TAGS, set(), valid_email=True, mailing_address=True)
    assert none.channels == (Channel.MAIL,) and "4040(a)(2)" in none.reason and none.send_to == "mailing"
    bounced = delivery(TAGS, {"notices by email"}, valid_email=False, mailing_address=True)
    assert bounced.channels == (Channel.MAIL,) and "no valid email" in bounced.reason


def _unit(uid, title, tags, owners):
    return {"id": uid, "title": title, "tags": [{"tag": t} for t in tags],
            "owners": [{"membershipId": m, "deletedAt": None, "hasInvalidEmailAddress": bad} for m, bad in owners]}


def _person(pid, tags, email="x@example.com", address=""):
    return {"id": pid, "email": email, "tags": [{"tag": t} for t in tags],
            "profile": {"givenNames": f"Owner{pid}", "familyName": "Test", "address1": address}}


def test_the_plan_gives_each_current_owner_a_channel_and_the_sending_lists():
    units = [_unit(1, "3007 ENCHANTED WALK", ["Building 3", "Rental"], [(10, False), (11, False)]),
             _unit(2, "3009 ENCHANTED WALK", ["Paper Statements"], [(12, False)]),
             _unit(3, "3011 ENCHANTED WALK", [], [(13, True)])]
    people = [_person(10, ["Notices by Email", "Owner Info 2027"]),
              _person(11, ["Notices by Mail"], address="PO Box 1"),
              _person(12, [], address=""),
              _person(13, ["Notices by Email"])]
    found = plan(units, people, TAGS)
    assert found.email_ids == [10]
    assert {o.membership_id: o.send_to for o in found.mail()} == {11: "mailing", 12: "unit", 13: "unit"}
    totals = found.summary()
    assert totals["answeredThisYear"] == 1 and totals["paperStatementsWithNoNoticeElection"] == 1
    assert any("no valid email" in reason for reason in totals["byReason"])
    owner10 = next(o for o in found.owners if o.membership_id == 10)
    assert owner10.unit_tags == ["occupancy: Rental"]                                  # buildings are not shown


def test_a_notice_reaches_exactly_who_the_law_requires_and_the_audit_makes_filters_work():
    from jason.community.notices import NoticeKind, NoticeRule
    from jason.tasks.notice_delivery import audience, audit, filters

    tags = TAGS + (PayhoaTag("Additional Deliveries", M, TagPurpose.SECONDARY_CONTACT),
                   PayhoaTag("General Notices Individually", M, TagPurpose.GENERAL_INDIVIDUALLY))
    units = [_unit(1, "3007 ENCHANTED WALK", ["Building 3"], [(10, False), (11, False), (14, False)]),
             _unit(2, "5655 WHIMSICAL LN", [], [(12, False)])]
    people = [_person(10, ["Notices by Email"]), _person(11, ["General Notices Individually"]),
              _person(12, []), _person(14, ["Additional Deliveries"], email="", address="PO Box 9")]
    found = plan(units, people, tags)
    assert [o.membership_id for o in found.owners] == [10, 11, 12] and found.secondary_contacts[0].membership_id == 14

    report = NoticeRule("annual-budget-report", "Annual budget report", "CIV 5300", NoticeKind.INDIVIDUAL, secondary_copies=True)
    who = audience(found, report, tags)
    assert who.email_ids == [10] and {o.membership_id for o in who.mail} == {11, 12}       # no election: mail
    assert [s.membership_id for s in who.secondary] == [14]                                  # 4040(b) copy
    flood = NoticeRule("flood-policy", "Flood", "practice", NoticeKind.INDIVIDUAL, reach="unit tag")
    assert {o.membership_id for o in audience(found, flood, tags, unit_tag="Building 3").mail} == {11}
    assert not audience(found, flood, tags, unit_tag="Building 3").secondary                # no 4040(b) copy here
    meeting = NoticeRule("board-meeting", "Meeting", "CIV 4920", NoticeKind.GENERAL)
    general = audience(found, meeting, tags)
    assert general.posted and {o.membership_id for o in general.mail} == {11}                # asked for it individually
    assert any("Post it" in line for line in filters(meeting, tags))

    changes = {(row["member"], row["change"]) for row in audit(found, tags)}
    assert changes == {(11, "+Notices by Mail"), (12, "+Notices by Mail")}                  # every owner gets a tag


def test_copies_go_to_additional_owner_records_by_their_fields_and_unit_contacts_are_flagged():
    from jason.community.notices import NoticeKind, NoticeRule
    from jason.tasks.notice_delivery import audience, audit, filters

    tags = TAGS + (PayhoaTag("Additional Deliveries", M, TagPurpose.SECONDARY_CONTACT),)
    units = [_unit(1, "3007 ENCHANTED WALK", ["Building 3"], [(10, False), (20, False)]),
             _unit(2, "5655 WHIMSICAL LN", [], [(12, False), (21, False), (22, False)])]
    people = [_person(10, ["Notices by Mail"]), _person(12, ["Notices by Mail"]),
              _person(20, ["Additional Deliveries"], email="copy@example.com"),                  # an email only: copies by email
              _person(21, ["Additional Deliveries"], email="", address="PO Box 7"),              # an address only: by mail
              _person(22, ["Additional Deliveries"], email="")]                                  # neither: reaches no one
    contacts = {1: [{"id": 30689, "name": "Tenant", "email": "t@example.com"}]}
    found = plan(units, people, tags, unit_contacts=contacts)
    assert [o.membership_id for o in found.owners] == [10, 12]                             # copy records are not owners
    report = NoticeRule("annual-policy-statement", "APS", "CIV 5310", NoticeKind.INDIVIDUAL, secondary_copies=True)
    increase = NoticeRule("assessment-increase", "Increase", "CIV 5615", NoticeKind.INDIVIDUAL)
    who = audience(found, report, tags)
    assert who.email_ids == [20]                                  # the mail-electing owner's second email still gets it
    assert who.summary()["secondaryCopiesByEmail"] == 1 and who.summary()["secondaryCopiesByMail"] == 1
    assert next(s for s in who.secondary if s.membership_id == 21).send_to == "mailing"
    assert audience(found, increase, tags).secondary == []                                  # 5615: no copies
    lines = filters(report, tags)
    assert any("member tag 'Additional Deliveries'" in line and "no mailing address" in line for line in lines)
    changes = {(row["member"], row["change"]) for row in audit(found, tags)}
    assert (22, "add the email or address") in changes and (None, "confirm") in changes     # the unit contact flagged


def test_a_courtesy_email_goes_to_everyone_and_never_replaces_the_letter():
    from jason.community.notices import NoticeKind, NoticeRule
    from jason.tasks.notice_delivery import audience

    units = [_unit(1, "3007 ENCHANTED WALK", [], [(10, False), (11, False), (12, True)])]
    people = [_person(10, ["Notices by Email"]), _person(11, []), _person(12, [])]
    found = plan(units, people, TAGS)
    rule = NoticeRule("owner-info-solicitation", "Request", "CIV 4041(b)", NoticeKind.INDIVIDUAL, courtesy_email=True)
    who = audience(found, rule, TAGS)
    assert [o.membership_id for o in who.email] == [10]                          # the law's delivery by email
    assert [o.membership_id for o in who.courtesy] == [11]                        # a courtesy copy; 12 has no good email
    assert {o.membership_id for o in who.mail} == {11, 12}                        # still mailed: no election
    assert who.email_ids == [10, 11] and who.summary()["noDeliverableEmail"] == 1


class _Agent:
    def __init__(self, client):
        self.client, self.org_id = client, 27889

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def payhoa(self):
        return self.client


class _Live:
    """PayHOA read live: one page of units and the people; records tag writes."""

    def __init__(self):
        self.writes = []

    def list_units(self, org_id, *, page=1):
        return {"data": [_unit(1, "3007 ENCHANTED WALK", [], [(10, False), (11, False)])], "meta": {"lastPage": 1}}

    def iter_people(self, org_id):
        return iter([_person(10, ["Notices by Email"]), _person(11, [])])

    def update_member_tags(self, org_id, ids, *, add=(), remove=()):
        self.writes.append((tuple(ids), tuple(add)))
        return []


def test_applying_the_audit_reads_payhoa_live_and_writes_only_with_yes(capsys):
    import argparse

    from jason.commands.delivery import _apply

    live = _Live()
    args = argparse.Namespace(yes=False)
    assert _apply(args, lambda a: _Agent(live), TAGS) == 0
    assert live.writes == [] and "add 'Notices by Mail' to 1 member(s)" in capsys.readouterr().out
    args.yes = True
    _apply(args, lambda a: _Agent(live), TAGS)
    assert live.writes == [((11,), ("Notices by Mail",))]                                   # only the owner with none


def test_the_specifications_tags_cover_every_4041_answer():
    from jason.community import mystique

    tags = mystique().payhoa_tags()
    purposes = {t.purpose for t in tags}
    for needed in (TagPurpose.NOTICE_DELIVERY, TagPurpose.SECONDARY_CONTACT, TagPurpose.LEGAL_REPRESENTATIVE,
                   TagPurpose.OCCUPANCY, TagPurpose.ANSWERED):
        assert needed in purposes, needed
    assert {t.value for t in tags if t.purpose is TagPurpose.NOTICE_DELIVERY} == {"email", "mail"}
    occupancy = {t.value for t in tags if t.purpose is TagPurpose.OCCUPANCY}
    owner_info = mystique().packet("owner-information")                            # the form's own options
    from jason.community.spec import spec_module

    options = set(spec_module("forms").OWNER_INFO.question("occupancy").options)
    assert occupancy <= options and owner_info
    assert len({(t.scope, t.name.casefold()) for t in tags}) == len(tags)            # no tag named twice
