from jason.community.tags import PayhoaTag, TagPurpose, TagScope
from jason.tasks.owner_responses import Context, Outcome, triage

TAGS = (PayhoaTag("Rental", TagScope.UNIT, TagPurpose.OCCUPANCY, value="Rented out"),
        PayhoaTag("Owner Occupied", TagScope.UNIT, TagPurpose.OCCUPANCY, value="Owner-occupied"),
        PayhoaTag("Unconfirmed Address", TagScope.MEMBER, TagPurpose.UNCONFIRMED))


def person(pid, given, family, email="", tags=(), address=""):
    return {"id": pid, "email": email, "tags": [{"tag": t} for t in tags],
            "profile": {"givenNames": given, "familyName": family, "address1": address}}


def ctx(answers, *, unit_tags=(), records=None, me=1, tests=()):
    records = records or [person(1, "Ann", "Example", "ann@example.com")]
    owners = [p for p in records if not any(t["tag"] == "Unconfirmed Address" for t in p["tags"])]
    return Context(9, "1 EXAMPLE WALK", 70, me, answers, owners, records, {t.casefold() for t in unit_tags}, TAGS,
                   set(tests))


def outcomes(c):
    return {(f.rule, f.outcome) for f in triage(c)}


def test_a_complete_consistent_answer_is_only_recorded():
    c = ctx({"answering-for": ["Myself only"], "delivery": ["By email"], "email": "ann@example.com",
             "occupancy": ["Owner-occupied"], "mailing-address": "Same as my unit address"}, unit_tags=("Owner Occupied",))
    assert outcomes(c) == {("delivery", Outcome.RECORD)}


def test_a_test_accounts_answer_is_ignored_and_nothing_else_is_read():
    assert outcomes(ctx({"delivery": ["By email"]}, tests=(1,))) == {("test-account", Outcome.IGNORE)}


def test_answering_for_co_owners_and_a_co_owners_email_go_to_the_board_and_the_owner():
    records = [person(1, "Ann", "Example", "ann@example.com"), person(2, "Kim", "Sample")]
    c = ctx({"answering-for": ["All owners of this unit"], "second-email": "kimsample@example.org",
             "occupancy": ["Owner-occupied"]}, unit_tags=("Owner Occupied",), records=records)
    got = outcomes(c)
    assert ("for-co-owners", Outcome.BOARD) in got and ("second-is-co-owner", Outcome.CONFIRM) in got


def test_a_rental_the_tag_does_not_show_waits_for_the_board_and_its_mail_is_confirmed():
    records = [person(1, "Ann", "Example", "ann@example.com"),
               person(3, "Ann", "Example", tags=("Unconfirmed Address",))]
    c = ctx({"occupancy": ["Rented out"], "delivery": ["By email"], "email": "ann@example.com"}, records=records)
    got = outcomes(c)
    assert ("occupancy-vs-tag", Outcome.BOARD) in got
    assert ("rented-mail-at-unit", Outcome.CONFIRM) in got
    assert ("unconfirmed-record", Outcome.PERSON) in got
    board = [f for f in triage(c) if f.rule == "occupancy-vs-tag"][0]
    assert board.board_item == "rental-approvals-4-15"
